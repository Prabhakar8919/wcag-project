from django.db import models
from core.models import Scan, Page
# This model stores all WCAG rules used for accessibility checking
# Each rule has id title level and logic for validation
class Rule(models.Model):
    LEVEL_CHOICES = [
        ('A', 'A'),
        ('AA', 'AA'),
        ('AAA', 'AAA'),
    ]
    CHECK_TYPE_CHOICES = [
        ('deterministic', 'Deterministic'),
        ('heuristic', 'Heuristic'),
        ('llm', 'LLM'),
    ]
# This defines how the rule will be checked like deterministic heuristic or llm
    wcag_id = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    level = models.CharField(max_length=3, choices=LEVEL_CHOICES)
    category = models.CharField(max_length=100)
    check_type = models.CharField(max_length=20, choices=CHECK_TYPE_CHOICES)
    version = models.CharField(max_length=50, default="2.0,2.1,2.2")
    logic = models.TextField(blank=True, null=True)
    fix_suggestion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['wcag_id']

    def __str__(self):
        return f"{self.wcag_id}: {self.title}"
# This model stores issues found during scan
# Each issue is linked to scan page and rule
class Issue(models.Model):
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    scan = models.ForeignKey(Scan, on_delete=models.CASCADE, related_name='issues')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='issues')
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name='issues')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    message = models.TextField()
    element_html = models.TextField(blank=True, null=True)
    fix_suggestion = models.TextField(blank=True, null=True)
    corrected_html = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
# Orders issues by latest first
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Issue on {self.page.url} ({self.rule.wcag_id})"
