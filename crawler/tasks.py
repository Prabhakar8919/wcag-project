from celery import shared_task
from .engine import CrawlerEngine
import logging
import time
import redis
from django.conf import settings
from django.db.models import F

logger = logging.getLogger(__name__)

@shared_task
def crawl_and_analyze(scan_id):
    logger.info(f"CELERY: Starting crawl_and_analyze for scan {scan_id}")
    try:
        engine = CrawlerEngine(scan_id=scan_id) 
        engine.start()
        logger.info(f"CELERY: Finished crawl_and_analyze for scan {scan_id}")
    except Exception as e:
        logger.error(f"CELERY ERROR in crawl_and_analyze {scan_id}: {e}")

def compile_final_scan_report(scan, llm):
    from core.models import Report
    from rules.models import Issue
    from django.utils import timezone
    
    total_pages = scan.pages.count()
    all_issues_count = Issue.objects.filter(scan=scan).count()
    ai_issues_count = Issue.objects.filter(scan=scan, rule__check_type='llm').count()
    
    # Fetch all issues for this scan to compute advanced analytics
    all_issues = Issue.objects.filter(scan=scan).select_related('rule')
    
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

    total_pages_max = max(1, total_pages)
    score_perceivable = max(0.0, 100.0 - (perceivable / total_pages_max * 15.0))
    score_operable = max(0.0, 100.0 - (operable / total_pages_max * 15.0))
    score_understandable = max(0.0, 100.0 - (understandable / total_pages_max * 15.0))
    score_robust = max(0.0, 100.0 - (robust / total_pages_max * 15.0))
    
    compliance_20 = max(0.0, 100.0 - (ver_20 / total_pages_max * 10.0))
    compliance_21 = max(0.0, 100.0 - (ver_21 / total_pages_max * 10.0))
    compliance_22 = max(0.0, 100.0 - (ver_22 / total_pages_max * 10.0))
    
    score = int((score_perceivable + score_operable + score_understandable + score_robust) / 4)

    Report.objects.update_or_create(
        scan=scan,
        defaults={
            'total_pages_scanned': total_pages,
            'total_issues_found': all_issues_count,
            'ai_issues_found': ai_issues_count,
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
    
    scan.status = 'Completed'
    scan.completed_at = timezone.now()
    scan.save()
    
    llm.generate_executive_reports(scan)


@shared_task(bind=True, max_retries=10, default_retry_delay=10)
def analyze_page_with_llm(self, page_id):
    from core.models import Page, Scan, Report
    from rules.models import Rule, Issue
    from llm.service import GroqService

    start_time = time.time()
    
    # Redis client for lightweight concurrency limit
    try:
        r = redis.Redis.from_url(getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        max_concurrent = getattr(settings, 'MAX_LLM_CONCURRENCY', 2)
        
        # Check current active tasks
        active_ai_tasks = r.get("active_ai_tasks")
        active_ai_tasks = int(active_ai_tasks) if active_ai_tasks else 0
        
        if active_ai_tasks >= max_concurrent:
            logger.info(f"AI Throttling: Max concurrency ({max_concurrent}) reached. Retrying task for page {page_id}")
            raise self.retry(countdown=2)
            
        # Increment active tasks counter
        r.incr("active_ai_tasks")
        r.expire("active_ai_tasks", 300) # Failsafe expiry (5 mins)
    except redis.RedisError as re:
        logger.warning(f"Redis error during throttling check: {re}. Continuing without throttle.")
        r = None # Ignore throttle if redis is unreachable
    
    try:
        page = Page.objects.get(id=page_id)
        scan = page.scan
        url = page.url
        
        logger.info(f"AI START: Analysis for {url}")
        
        if not page.html_snapshot:
            logger.warning(f"AI SKIP: No HTML snapshot for {url}")
            return
            
        llm = GroqService()
        if not llm.enabled:
            logger.warning("AI DISABLED: GroqService is not enabled in settings.")
            return
            
        # Call Groq API
        issues = llm.analyze_semantics(page.html_snapshot)
        count = len(issues)
        
        # Save semantic accessibility suggestions using bulk_create for performance
        issues_to_create = []
        for raw_issue in issues:
            wcag_id = raw_issue.get("rule_id", "LLM_UX")
            rule = Rule.objects.filter(wcag_id=wcag_id).first() or Rule.objects.filter(wcag_id="LLM_UX").first()
                
            if rule:
                issues_to_create.append(
                    Issue(
                        scan=scan,
                        page=page,
                        rule=rule,
                        severity=raw_issue.get("severity", "medium"),
                        message=raw_issue.get("message", "AI detected issue"),
                        element_html="",
                        fix_suggestion=raw_issue.get("fix", ""),
                        corrected_html=raw_issue.get("corrected_html", "")
                    )
                )
                
        if issues_to_create:
            Issue.objects.bulk_create(issues_to_create)
        
        # Update Metrics safely
        processing_time = time.time() - start_time
        Scan.objects.filter(id=scan.id).update(
            ai_pages_processed=F('ai_pages_processed') + 1,
            ai_total_time=F('ai_total_time') + processing_time
        )
        
        # Update Report AI Count
        if hasattr(scan, 'report'):
            Report.objects.filter(scan=scan).update(
                ai_issues_found=F('ai_issues_found') + count
            )
                
        logger.info(f"AI FINISH: {url} | Found: {count} issues | Time: {processing_time:.2f}s")

        # Check if all pages are now resolved to compile final report
        try:
            scan.refresh_from_db()
            total_pages = scan.pages.count()
            completed_ai_pages = scan.ai_pages_processed + scan.ai_errors_count
            if scan.status in ('Completed', 'Analyzing') and completed_ai_pages >= total_pages:
                logger.info(f"AI Completion: All {completed_ai_pages}/{total_pages} tasks resolved on success. Recompiling summaries.")
                compile_final_scan_report(scan, llm)
        except Exception as report_e:
            logger.error(f"AI Completion Error: {report_e}")

    except Exception as e:
        # If it's a retry exception, bubble it up so Celery can retry
        if isinstance(e, self.retry.TaskError) or isinstance(e, self.Retry):
            raise
            
        logger.error(f"AI ERROR for page {page_id}: {str(e)}")
        # Log error in scan metrics safely
        try:
            page = Page.objects.get(id=page_id)
            scan = page.scan
            Scan.objects.filter(id=scan.id).update(ai_errors_count=F('ai_errors_count') + 1)
            
            # Check if all pages are now resolved even on failure
            scan.refresh_from_db()
            total_pages = scan.pages.count()
            completed_ai_pages = scan.ai_pages_processed + scan.ai_errors_count
            if scan.status in ('Completed', 'Analyzing') and completed_ai_pages >= total_pages:
                logger.info(f"AI Completion: All {completed_ai_pages}/{total_pages} tasks resolved on error. Recompiling summaries.")
                from llm.service import GroqService
                llm = GroqService()
                compile_final_scan_report(scan, llm)
        except Exception as inner_e:
            logger.error(f"Could not log AI error count or complete scan: {inner_e}")
            
    finally:
        # Decrement active tasks counter safely
        if r:
            try:
                current = r.decr("active_ai_tasks")
                if current < 0:
                    r.set("active_ai_tasks", 0)
            except redis.RedisError:
                pass
