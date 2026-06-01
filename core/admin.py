from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import Project, Scan, Page, Report
from crawler.tasks import crawl_and_analyze
# This inline shows pages inside scan admin view
# It displays page details in table format
class PageInline(admin.TabularInline):
    model = Page
    extra = 0
    readonly_fields = ('url', 'status', 'created_at')
    can_delete = False
# This registers Project model in admin panel
# It shows project details and allows search
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('domain', 'user', 'created_at')
    search_fields = ('domain',)
    ordering = ('-created_at',)
# This registers Scan model in admin panel
# It manages scan data and actions
@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'status_colored', 'started_at', 'completed_at')
    list_filter = ('status',)
    date_hierarchy = 'started_at'
    readonly_fields = ('started_at', 'completed_at')
    inlines = [PageInline]
    actions = ['start_crawl_action']
# This method shows colored status
    def status_colored(self, obj):
        colors = {
            'Completed': 'green',
            'Failed': 'red',
            'Crawling': 'orange',
            'Pending': 'gray',
            'Analyzing': 'blue'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.status)
    status_colored.short_description = 'Status'
 # This action starts crawling for selected scans
    @admin.action(description="Start Crawl for selected Scans")
    def start_crawl_action(self, request, queryset):
        for scan in queryset:
            try:
                crawl_and_analyze.delay(scan.id)
                self.message_user(request, f"Scan {scan.id} for {scan.project.domain} queued successfully.", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Failed to queue scan {scan.id}: {str(e)}", messages.ERROR)
# This registers Page model in admin panel
# It shows page details and related issues
@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('url', 'scan', 'status')
    search_fields = ('url',)
    list_filter = ('scan', 'status')
    
    def get_inline_instances(self, request, obj=None):
        try:
            from rules.admin import IssueInline
            return [IssueInline(self.model, self.admin_site)]
        except ImportError:
            return []
# This registers Report model in admin panel
# It shows final scan results
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('scan', 'score', 'total_pages_scanned', 'total_issues_found', 'generated_at')
    readonly_fields = ('scan', 'score', 'total_pages_scanned', 'total_issues_found', 'generated_at')
    date_hierarchy = 'generated_at'
 # Disable adding new reports manually
    def has_add_permission(self, request):
        return False
