import queue
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import re
import threading
import concurrent.futures
from core.models import Scan, Page, Report
from rules.models import Rule, Issue
from .analyzer import PageAnalyzer
import logging

logger = logging.getLogger(__name__)

class RuleEngine:
    def __init__(self, scan):
        self.scan = scan
        # Cache rules to avoid DB hits on every issue
        self.rule_cache = list(Rule.objects.all())

    def normalize_wcag_id(self, wcag_id):
        if not wcag_id:
            return ""
        return str(wcag_id).upper().replace('WCAG', '').replace('_', '.').strip().strip('.')

    def process_issues(self, page, raw_issues):
        issues_to_create = []
        for raw_issue in raw_issues:
            raw_id = raw_issue.get('wcag_id')
            normalized_id = self.normalize_wcag_id(raw_id)
            
            # Find matching rule in cache
            rule = next((r for r in self.rule_cache if normalized_id in self.normalize_wcag_id(r.wcag_id)), None)

            if rule:
                issues_to_create.append(
                    Issue(
                        scan=self.scan,
                        page=page,
                        rule=rule,
                        severity=raw_issue.get('severity', 'medium'),
                        message=raw_issue.get('message'),
                        element_html=raw_issue.get('element_html'),
                        fix_suggestion=raw_issue.get('fix_suggestion')
                    )
                )
            else:
                logger.debug(f"Rule {raw_id} not found. Skipping.")
                
        # Bulk create issues for database performance
        if issues_to_create:
            Issue.objects.bulk_create(issues_to_create)
            
        return len(issues_to_create)

def get_registered_domain(netloc):
    netloc = netloc.replace('www.', '').lower()
    parts = netloc.split('.')
    if len(parts) >= 2:
        # Check for co.uk, com.au, org.in, etc.
        if len(parts[-2]) <= 3 and parts[-1] in ('uk', 'jp', 'au', 'nz', 'za', 'br', 'mx', 'in', 'cn', 'org'):
            if len(parts) >= 3:
                return '.'.join(parts[-3:])
        return '.'.join(parts[-2:])
    return netloc

def fetch_html_with_fallback(url, headers):
    user_agent = headers.get('User-Agent', 'Mozilla/5.0')
    import subprocess
    try:
        cmd = ["curl.exe", "-s", "-L", "-A", user_agent, url]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=5)
        if res.returncode == 0 and res.stdout:
            return res.stdout
    except Exception:
        pass
    return None

class CrawlerEngine:
    def __init__(self, scan_id):
        self.scan_id = scan_id
        
        # Thread-safe data structures
        self.q = queue.Queue()
        self.visited = set()
        self.visited_lock = threading.Lock()
        
        self.scan = Scan.objects.get(pk=scan_id)
        self.project = self.scan.project
        self.max_pages = self.project.crawl_limit
        self.crawl_depth = getattr(self.project, 'crawl_depth', 3)
        self.sitemap_enabled = getattr(self.project, 'sitemap_enabled', False)
        
        self.start_url = self.project.domain
        if not self.start_url.startswith(('http://', 'https://')):
            self.start_url = 'https://' + self.start_url

        self.base_domain = get_registered_domain(urlparse(self.start_url).netloc)
        self.headers = {'User-Agent': 'WCAG-Auditor/1.0 (Production; Cloud-AI)'}
        self.rule_engine = RuleEngine(self.scan)
        
        # Performance/Resource settings
        self.max_workers = getattr(settings, 'MAX_CRAWLER_WORKERS', 5)
        self.timeout = getattr(settings, 'REQUEST_TIMEOUT', 10)
        self.max_retries = getattr(settings, 'MAX_RETRIES', 3)
        
        # Request session with connection pooling and retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=self.max_workers, pool_maxsize=self.max_workers)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Smart URL Filtering patterns
        self.exclude_patterns = re.compile(
            r'.*\.(jpg|jpeg|png|gif|bmp|svg|webp|mp4|webm|ogv|mp3|wav|flac|pdf|zip|rar|exe|dmg|iso|css|js|woff|woff2|ttf|eot)$|'
            r'.*/cdn-cgi/.*|'
            r'.*wp-content/uploads/.*',
            re.IGNORECASE
        )
        
        self.pages_crawled = 0
        self.pages_submitted = 0
        self.total_issues = 0
        self.stats_lock = threading.Lock()
        
        # For thread pool coordination
        self.active_tasks = 0
        self.active_tasks_lock = threading.Lock()

    def normalize_url(self, base_url, link):
        # Ignore javascript, mailto, tel, anchors
        if not link or link.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
            return None
            
        # Ignore social media / external logins typically found on sites
        lower_link = link.lower()
        if any(social in lower_link for social in ['facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com', 'pinterest.com', 'youtube.com']):
            return None
            
        if 'logout' in lower_link:
            return None
            
        try:
            absolute_url = urljoin(base_url, link)
            url_no_fragment, _ = urldefrag(absolute_url)
            parsed = urlparse(url_no_fragment)
            
            # Normalize path (remove double slashes and trailing slash)
            clean_path = re.sub(r'//+', '/', parsed.path)
            if clean_path.endswith('/') and len(clean_path) > 1:
                clean_path = clean_path[:-1]
                
            normalized = parsed._replace(path=clean_path, query=parsed.query).geturl()
            return normalized
        except Exception:
            return None

    def should_crawl(self, url):
        if not url: return False
        
        with self.visited_lock:
            if url in self.visited:
                return False
                
        if self.exclude_patterns.match(url): return False
        
        parsed = urlparse(url)
        return get_registered_domain(parsed.netloc) == self.base_domain

    def process_url(self, item):
        current_url, depth = item
        with self.visited_lock:
            if current_url in self.visited:
                with self.stats_lock:
                    self.pages_submitted -= 1
                return
            self.visited.add(current_url)

        try:
            # Check limits
            with self.stats_lock:
                if self.pages_crawled >= self.max_pages:
                    self.pages_submitted -= 1
                    return

            logger.info(f"Processing: {current_url} (depth: {depth})")
            response_text = None
            response_url = current_url
            response_status = 200
            
            try:
                response = self.session.get(current_url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type:
                        response_text = response.text
                        response_url = response.url
                        response_status = response.status_code
                else:
                    response_text = fetch_html_with_fallback(current_url, self.headers)
            except Exception as e:
                response_text = fetch_html_with_fallback(current_url, self.headers)

            if not response_text:
                logger.warning(f"Skipping {current_url} (Could not fetch HTML)")
                with self.stats_lock:
                    self.pages_submitted -= 1
                return

            soup = BeautifulSoup(response_text, 'html.parser')
            title = soup.title.string[:500] if soup.title else "No Title"

            # Double-check limits and increment under lock before writing to DB
            with self.stats_lock:
                if self.pages_crawled >= self.max_pages:
                    self.pages_submitted -= 1
                    return
                self.pages_crawled += 1

            with transaction.atomic():
                page = Page.objects.create(
                    scan=self.scan,
                    url=current_url,
                    status_code=response_status,
                    html_snapshot=response_text,
                    title=title,
                    page_size=len(response_text),
                    status='Crawled'
                )

            # Deterministic Analysis
            analyzer = PageAnalyzer(response_text, current_url)
            raw_issues = analyzer.run_checks()
            issues_count = self.rule_engine.process_issues(page, raw_issues)
            
            with self.stats_lock:
                self.total_issues += issues_count
            
            logger.info(f"-> Found {issues_count} deterministic issues on {current_url}.")

            # Dispatch AI Task
            from .tasks import analyze_page_with_llm
            analyze_page_with_llm.delay(page.id)

            # Extract Links safely if depth is within limits
            if depth < self.crawl_depth:
                for a_tag in soup.find_all('a', href=True):
                    next_url = self.normalize_url(response.url, a_tag['href'])
                    if self.should_crawl(next_url):
                        # Prevent adding more to queue if we're near limit to save memory
                        with self.stats_lock:
                            if self.pages_crawled + self.q.qsize() < self.max_pages * 2:
                                self.q.put((next_url, depth + 1))

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error processing {current_url}: {str(e)}")
            with self.stats_lock:
                self.pages_submitted -= 1
        except Exception as e:
            logger.error(f"General error processing {current_url}: {str(e)}")
            with self.stats_lock:
                self.pages_submitted -= 1
            
        finally:
            with self.active_tasks_lock:
                self.active_tasks -= 1

    def parse_sitemap(self):
        logger.info("SITEMAP: Fetching sitemap.xml for target domain...")
        sitemap_url = urljoin(self.start_url, '/sitemap.xml')
        sitemap_text = None
        try:
            response = self.session.get(sitemap_url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                sitemap_text = response.text
            else:
                sitemap_text = fetch_html_with_fallback(sitemap_url, self.headers)
        except Exception as e:
            sitemap_text = fetch_html_with_fallback(sitemap_url, self.headers)

        if sitemap_text:
            try:
                # Try parsing sitemap
                soup = BeautifulSoup(sitemap_text, 'xml')
                locs = soup.find_all('loc')
                if not locs:
                    soup = BeautifulSoup(sitemap_text, 'html.parser')
                    locs = soup.find_all('loc')
                
                urls_found = 0
                for loc in locs:
                    url = loc.get_text().strip()
                    normalized = self.normalize_url(self.start_url, url)
                    if normalized and self.should_crawl(normalized):
                        self.q.put((normalized, 0)) # sitemap URLs are seed URLs at depth 0
                        urls_found += 1
                logger.info(f"SITEMAP: Successfully seeded queue with {urls_found} URLs from sitemap.xml")
                return urls_found > 0
            except Exception as e:
                logger.warning(f"SITEMAP: Failed to parse sitemap: {str(e)}")
        return False

    def start(self):
        logger.info(f"--- Starting Production Crawl for {self.base_domain} (Limit: {self.max_pages}, Depth: {self.crawl_depth}, Sitemap: {self.sitemap_enabled}, Workers: {self.max_workers}) ---")
        self.scan.status = 'Crawling'
        self.scan.save()

        sitemap_seeded = False
        if self.sitemap_enabled:
            sitemap_seeded = self.parse_sitemap()

        if not sitemap_seeded:
            self.q.put((self.start_url, 0))
        
        # Parallel Crawling using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while True:
                # Check if we have completed successfully crawling the required pages
                with self.stats_lock:
                    if self.pages_crawled >= self.max_pages:
                        # Success! Empty queue and exit
                        while not self.q.empty():
                            try:
                                self.q.get_nowait()
                                self.q.task_done()
                            except queue.Empty:
                                break
                        break

                    # If we currently have enough active or crawled tasks to satisfy the limit, pause queue popping
                    if self.pages_submitted >= self.max_pages:
                        time.sleep(0.2)
                        continue

                try:
                    # Non-blocking get with short timeout
                    item = self.q.get(timeout=1)
                    
                    with self.stats_lock:
                        self.pages_submitted += 1
                    
                    with self.active_tasks_lock:
                        self.active_tasks += 1
                        
                    executor.submit(self.process_url, item)
                    self.q.task_done()
                    
                except queue.Empty:
                    # If queue is empty, check if we have any active tasks running
                    with self.active_tasks_lock:
                        if self.active_tasks == 0:
                            # Queue is empty and no workers are running, we are done
                            break
                    time.sleep(0.5)

        # Finalize Scan
        self.finalize_scan()

    def finalize_scan(self):
        with self.stats_lock:
            pages = self.pages_crawled
            issues = self.total_issues
            
        # Fetch all issues for this scan to compute advanced analytics
        from rules.models import Issue
        all_issues = Issue.objects.filter(scan=self.scan).select_related('rule')
        
        level_a = 0
        level_aa = 0
        level_aaa = 0
        
        perceivable = 0
        operable = 0
        understandable = 0
        robust = 0
        
        ver_20 = 0
        ver_21 = 0
        ver_22 = 0
        
        for issue in all_issues:
            if not issue.rule:
                continue
                
            # Level Count
            lvl = issue.rule.level
            if lvl == 'A': level_a += 1
            elif lvl == 'AA': level_aa += 1
            elif lvl == 'AAA': level_aaa += 1
            
            # POUR Categories
            cat = issue.rule.category.lower()
            if 'perceivable' in cat: perceivable += 1
            elif 'operable' in cat: operable += 1
            elif 'understandable' in cat: understandable += 1
            elif 'robust' in cat: robust += 1
            elif 'ai insights' in cat or 'llm' in issue.rule.check_type:
                rule_id = issue.rule.wcag_id.lower()
                if 'semantics' in rule_id or 'images' in rule_id: perceivable += 1
                elif 'ux' in rule_id: operable += 1
                elif 'readability' in rule_id: understandable += 1
                elif 'aria' in rule_id: robust += 1
                
            # WCAG Versions
            vers = issue.rule.version.split(',')
            if '2.0' in vers: ver_20 += 1
            if '2.1' in vers: ver_21 += 1
            if '2.2' in vers: ver_22 += 1
            
        # Calculate POUR percentages
        total_pages = max(1, pages)
        score_perceivable = max(0.0, 100.0 - (perceivable / total_pages * 5.0))
        score_operable = max(0.0, 100.0 - (operable / total_pages * 5.0))
        score_understandable = max(0.0, 100.0 - (understandable / total_pages * 5.0))
        score_robust = max(0.0, 100.0 - (robust / total_pages * 5.0))
        
        # Calculate Version percentages
        compliance_20 = max(0.0, 100.0 - (ver_20 / total_pages * 10.0))
        compliance_21 = max(0.0, 100.0 - (ver_21 / total_pages * 10.0))
        compliance_22 = max(0.0, 100.0 - (ver_22 / total_pages * 10.0))
        
        # Weighted Overall Score
        score = int((score_perceivable + score_operable + score_understandable + score_robust) / 4)
        
        Report.objects.update_or_create(
            scan=self.scan,
            defaults={
                'total_pages_scanned': pages,
                'total_issues_found': issues,
                'score': score,
                'score_perceivable': score_perceivable,
                'score_operable': score_operable,
                'score_understandable': score_understandable,
                'score_robust': score_robust,
                'compliance_20': compliance_20,
                'compliance_21': compliance_21,
                'compliance_22': compliance_22,
                'level_a_issues': level_a,
                'level_aa_issues': level_aa,
                'level_aaa_issues': level_aaa,
            }
        )
        
        # Check if there are still AI tasks running/dispatched
        self.scan.refresh_from_db()
        if self.scan.ai_pages_processed + self.scan.ai_errors_count < pages:
            self.scan.status = 'Analyzing'
        else:
            self.scan.status = 'Completed'
            self.scan.completed_at = timezone.now()
        self.scan.save()
        
        logger.info(f"--- Crawl Finished. Scanned {pages} pages with {issues} issues. Status: {self.scan.status} ---")
        
        # Compile and save scan report and LLaMA Executive Summaries asynchronously or safely if scan is already completed
        if self.scan.status == 'Completed':
            from llm.service import GroqService
            from .tasks import compile_final_scan_report
            try:
                llm = GroqService()
                compile_final_scan_report(self.scan, llm)
            except Exception as e:
                logger.error(f"AI: Final report summary error: {e}")
