from django.db import models
from django.contrib.auth.models import User
# This model stores project details for each user
# Each project represents a domain to scan
class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    domain = models.URLField(max_length=2000)
    wcag_level = models.CharField(max_length=3, default='AA')
    crawl_limit = models.IntegerField(default=50)
    crawl_depth = models.IntegerField(default=3)
    sitemap_enabled = models.BooleanField(default=False)
    estimated_pages = models.IntegerField(default=0, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'domain'], name='unique_user_project_domain')
        ]

    def __str__(self):
        return self.domain
# This model stores scan information for a project
# Each scan represents one crawling process
class Scan(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Crawling', 'Crawling'),
        ('Analyzing', 'Analyzing'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='scans')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_index=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # AI Processing Metrics
    ai_pages_processed = models.IntegerField(default=0)
    ai_total_time = models.FloatField(default=0.0) # in seconds
    ai_errors_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Scan {self.id} for {self.project.domain}"
# This model stores each crawled page
# It keeps html content and status
class Page(models.Model):
    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name='pages')
    url = models.URLField(max_length=2000, db_index=True)
    html_snapshot = models.TextField(blank=True, null=True)
    title = models.CharField(max_length=500, blank=True, null=True)
    status_code = models.IntegerField(blank=True, null=True)
    page_size = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.url
# This model stores final report of scan
# It contains total pages issues and score
class Report(models.Model):
    scan = models.OneToOneField(Scan, on_delete=models.CASCADE, related_name='report')
    total_pages_scanned = models.IntegerField(default=0)
    total_issues_found = models.IntegerField(default=0)
    ai_issues_found = models.IntegerField(default=0)
    score = models.FloatField(default=0.0)
    
    # POUR Principles Scores
    score_perceivable = models.FloatField(default=100.0)
    score_operable = models.FloatField(default=100.0)
    score_understandable = models.FloatField(default=100.0)
    score_robust = models.FloatField(default=100.0)
    
    # Compliance Targets Version Scores
    compliance_20 = models.FloatField(default=100.0)
    compliance_21 = models.FloatField(default=100.0)
    compliance_22 = models.FloatField(default=100.0)
    
    # Level Breakdown Counts
    level_a_issues = models.IntegerField(default=0)
    level_aa_issues = models.IntegerField(default=0)
    level_aaa_issues = models.IntegerField(default=0)
    
    # AI Executive Summaries
    ai_summary = models.TextField(blank=True, null=True)
    ai_health_report = models.TextField(blank=True, null=True)
    ai_legal_insights = models.TextField(blank=True, null=True)
    ai_risk_analysis = models.TextField(blank=True, null=True)
    
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Report for Scan {self.scan.id}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    company = models.CharField(max_length=255, blank=True, null=True)
    api_key = models.CharField(max_length=64, blank=True, null=True)
    default_wcag_level = models.CharField(max_length=3, default='AA')
    
    # Email OTP Verification fields
    is_email_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=128, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    otp_attempts = models.IntegerField(default=0)
    otp_last_resent = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"
