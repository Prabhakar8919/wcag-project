import logging
import json
import re
import time
from bs4 import BeautifulSoup
from django.conf import settings
from groq import Groq
from .prompts import SEMANTIC_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)

def robust_json_cleaner(s):
    in_string = False
    escaped = False
    result = []
    i = 0
    n = len(s)
    
    while i < n:
        char = s[i]
        
        if char == '"' and not escaped:
            if in_string:
                # Look ahead to see if it behaves like a structural ending double quote
                is_end = False
                j = i + 1
                while j < n and s[j].isspace():
                    j += 1
                if j >= n or s[j] in (',', '}', ']', ':'):
                    is_end = True
                
                if is_end:
                    in_string = False
                else:
                    result.append('\\"')
                    i += 1
                    continue
            else:
                in_string = True
            
            result.append(char)
        elif char == '\\' and in_string:
            escaped = not escaped
            result.append(char)
        else:
            if escaped:
                escaped = False
            
            if in_string:
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                else:
                    result.append(char)
            else:
                result.append(char)
        i += 1
        
    return "".join(result)

class GroqService:
    def __init__(self):
        self.api_key = getattr(settings, 'GROQ_API_KEY', None)
        self.model = getattr(settings, 'LLM_MODEL', 'llama-3.1-8b-instant')
        self.timeout = getattr(settings, 'LLM_TIMEOUT', 30)
        self.enabled = getattr(settings, 'LLM_ENABLED', False)
        
        if self.enabled and self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                self.client = None
        else:
            self.client = None

    def preprocess_html(self, html_content):
        
        if not html_content:
            return ""
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Completely remove non-semantic/heavy tags
        for tag in soup(['script', 'style', 'svg', 'noscript', 'iframe', 'meta', 'link']):
            tag.decompose()
            
        # Extract meaningful interactive and structural elements
        important_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'button', 'input', 'label', 'form', 'nav', 'main', 'header', 'footer']
        elements_to_keep = soup.find_all(important_tags)
        
        compact_text = []
        for el in elements_to_keep:
            tag_name = el.name
            text = el.get_text(separator=' ', strip=True)
            aria_label = el.get('aria-label', '')
            role = el.get('role', '')
            
            if text or aria_label or role:
                props = []
                if aria_label: props.append(f"aria-label='{aria_label}'")
                if role: props.append(f"role='{role}'")
                
                prop_str = f" ({', '.join(props)})" if props else ""
                compact_text.append(f"<{tag_name}{prop_str}> {text}")
                
        # Limit to 2000 characters to stay within efficient token limits
        result = "\n".join(compact_text)
        return result[:2000]

    def analyze_semantics(self, html_content):
        
        if not self.enabled or not self.client:
            logger.warning("GroqService is disabled or API key is missing.")
            return []

        clean_text = self.preprocess_html(html_content)
        if len(clean_text) < 20:
            return []

        prompt = SEMANTIC_ANALYSIS_PROMPT.format(html_content=clean_text)
        
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"Groq API Request (Attempt {attempt+1}/{max_retries}) using {self.model}")
                
                # small delay to avoid Groq API rate-limit spikes
                logger.info("AI request delayed briefly to avoid API throttling.")
                time.sleep(1)
                
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a specialized accessibility analysis tool that only outputs valid JSON arrays."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1000,
                    timeout=self.timeout
                )
                
                response_text = completion.choices[0].message.content
                return self.parse_json_response(response_text)

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    logger.warning("Groq rate limit hit. Retrying request safely...")
                else:
                    logger.error(f"Groq API error on attempt {attempt+1}: {error_msg}")
                    
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error("Max retries reached for Groq API.")
        
        return []

    def parse_json_response(self, text):
        
        try:
            # Attempt to find a JSON array in the text if the model included conversational filler
            match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                json_str = text.strip()

            issues = json.loads(json_str)
            
            if isinstance(issues, list):
                return issues
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Groq JSON response: {e}. Raw: {text}")
            return []

    def generate_executive_reports(self, scan):
        if not self.enabled or not self.client:
            logger.warning("GroqService disabled or missing key. Skipping AI summaries.")
            return
            
        from rules.models import Issue
        from core.models import Report
        
        # Gather up to 30 issues to construct a context
        issues = Issue.objects.filter(scan=scan).select_related('rule')[:30]
        
        issues_summary = []
        for idx, issue in enumerate(issues):
            issues_summary.append(
                f"- Issue #{idx+1}: Rule {issue.rule.wcag_id} ({issue.rule.category}) | {issue.severity.upper()} | {issue.message}"
            )
            
        issues_text = "\n".join(issues_summary) if issues_summary else "No major issues detected during the scan."
        
        prompt = f"""You are an elite executive accessibility consultant and legal risk analyst. Analyze the following summary of accessibility violations found on the website '{scan.project.domain}' and generate four comprehensive reports in clean, standard, professional markdown (no preamble, no concluding conversational text):

CRITICAL: Return ONLY a raw JSON object containing these four fields, and absolutely nothing else. Inside the JSON string values, NEVER use unescaped double quotes; use single quotes instead to avoid breaking the JSON format.

JSON schema template:
{{
  "ai_summary": "Generate a beautiful, high-level business-focused summary of the audit findings. Focus on user impact, overall compliance posture, and business value of resolving these.",
  "ai_health_report": "Provide a thorough health check analysis, listing top problem areas, critical technical hurdles, and an actionable roadmap to achieve WCAG compliance.",
  "ai_legal_insights": "Analyze accessibility legal exposure, including risks under the ADA (Americans with Disabilities Act) Title III, Section 508, European Accessibility Act, and WCAG criteria.",
  "ai_risk_analysis": "Perform a detailed accessibility technical risk analysis. Assess risk score (1-100), identify high-priority vulnerabilities, and estimate technical debt."
}}

WCAG ISSUES FOUND:
{issues_text}
"""
        try:
            logger.info("AI: Querying Groq LLaMA for executive summaries...")
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a specialized accessibility legal and risk advisor that only outputs valid JSON objects."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
                timeout=self.timeout
            )
            response_text = completion.choices[0].message.content
            
            # Robust JSON extraction by finding matching outer braces
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            if first_brace != -1 and last_brace != -1:
                json_str = response_text[first_brace:last_brace+1]
            else:
                json_str = response_text.strip()
            
            # Parse JSON using our robust cleaner to handle unescaped quotes/newlines in values
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as jde:
                logger.warning(f"Standard JSON parse failed, attempting robust character-by-character cleaning: {jde}")
                try:
                    cleaned_str = robust_json_cleaner(json_str)
                    data = json.loads(cleaned_str)
                except Exception as inner_e:
                    logger.error(f"Robust cleaning failed to parse JSON: {inner_e}")
                    raise
            
            def sanitize_value(val):
                if isinstance(val, dict):
                    lines = []
                    for k, v in val.items():
                        title = k.replace('_', ' ').capitalize()
                        if isinstance(v, list):
                            lines.append(f"\n### {title}")
                            for item in v:
                                lines.append(f"- {item}")
                        elif isinstance(v, dict):
                            lines.append(f"\n### {title}")
                            for subk, subv in v.items():
                                lines.append(f"  - **{subk.replace('_', ' ').capitalize()}:** {subv}")
                        else:
                            lines.append(f"**{title}:** {v}")
                    return "\n".join(lines)
                elif isinstance(val, list):
                    return "\n".join([f"- {item}" for item in val])
                return str(val)
            
            # Save to report
            report, _ = Report.objects.get_or_create(scan=scan)
            report.ai_summary = sanitize_value(data.get("ai_summary", "Business Summary generated successfully."))
            report.ai_health_report = sanitize_value(data.get("ai_health_report", "Health check completed."))
            report.ai_legal_insights = sanitize_value(data.get("ai_legal_insights", "Legal risk analysis completed."))
            report.ai_risk_analysis = sanitize_value(data.get("ai_risk_analysis", "Technical risk analysis completed."))
            report.save()
            
            logger.info("AI: Successfully compiled and saved all AI executive reports.")
        except Exception as e:
            logger.error(f"AI ERROR: Failed to generate executive summaries: {str(e)}")
