from django.contrib import admin
from django.utils.html import format_html
from .models import Rule, Issue
# This inline shows issues inside rule or related admin view
# It displays issue data in table format without editing option
class IssueInline(admin.TabularInline):
    model = Issue
    extra = 0
    readonly_fields = ('severity', 'rule', 'scan', 'message', 'created_at')
    can_delete = False
# This registers Rule model in admin panel
# It controls how rules are displayed searched and filtered
@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ('wcag_id', 'title', 'level', 'category', 'check_type')
    list_filter = ('level', 'category', 'check_type')
    search_fields = ('wcag_id', 'title')
    ordering = ('wcag_id',)
# This registers Issue model in admin panel
# It controls how issues are displayed and managed
@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ('id', 'severity_colored', 'rule', 'page', 'scan')
    list_filter = ('severity', 'rule')
    search_fields = ('message', 'element_html')
    readonly_fields = ('scan', 'page', 'rule', 'severity', 'message', 'element_html', 'created_at')
 # This method shows severity with color styling
    def severity_colored(self, obj):
        colors = {
            'critical': 'red',
            'high': 'orange',
            'medium': 'blue',
            'low': 'gray',
        }
        color = colors.get(obj.severity, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_severity_display())
    
    severity_colored.short_description = 'Severity'
