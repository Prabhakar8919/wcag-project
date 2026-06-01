import json

# Optimized prompt for LLaMA 3 via Groq to ensure strict JSON array output
SEMANTIC_ANALYSIS_PROMPT = """You are an expert accessibility auditor. Analyze the provided HTML fragment for semantic, structural, UX, and cognitive accessibility issues.

CRITICAL: Return ONLY a raw JSON array of objects. No markdown formatting, no code blocks, no preamble, and no concluding text.

Focus areas:
1. LLM_SEMANTICS: Vague link/button text (e.g. "click here"), missing headings, incorrect semantic tagging, or bad layouts.
2. LLM_READABILITY: Complex jargon, dense text blocks, or poor readability for screen readers and cognitive accessibility.
3. LLM_ARIA: Missing aria-labels, incorrect roles, or redundant/broken ARIA attributes.
4. LLM_UX: Confusing interaction patterns or accessibility-related user experience friction.

Each issue MUST follow this JSON structure precisely:
[
  {{
    "rule_id": "LLM_SEMANTICS",
    "severity": "high" | "medium" | "low",
    "message": "Specific description of the accessibility issue.",
    "fix": "Actionable, clear instruction to resolve the issue.",
    "corrected_html": "<a href='/target' aria-label='Read more about target'>Read More</a>"
  }}
]

Important for "corrected_html":
- Provide a clean, modern, fully accessible, and semantic HTML replacement code block representing how the element SHOULD be coded to be fully accessible.
- If no elements are directly affected (e.g., text readability), set "corrected_html" to null or an empty string.

If no issues are found, return exactly: []

HTML CONTENT TO ANALYZE:
{html_content}
"""
