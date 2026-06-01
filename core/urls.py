from django.urls import path
from . import views

urlpatterns = [
    path('', views.global_dashboard, name='home'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('crawler/', views.crawler_view, name='crawler'),
    path('dashboard/', views.global_dashboard, name='global_dashboard'),
    path('dashboard/<int:project_id>/', views.dashboard_view, name='dashboard'),
    path('projects/', views.projects_list, name='projects'),
    path('project/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/api-key/rotate/', views.rotate_api_key_api, name='rotate_api_key'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('verify-otp/resend/', views.resend_otp_view, name='resend_otp'),
    path('api/crawl-status/<int:project_id>/', views.crawl_status_api, name='crawl_status_api'),
    path('api/neural-issues/<int:project_id>/', views.get_neural_issues_api, name='get_neural_issues_api'),
    path('api/estimate-pages/', views.estimate_pages_api, name='estimate_pages_api'),
    path('page/<int:page_id>/', views.page_detail, name='page_detail'),
    path('page/<int:page_id>/overlay/', views.page_overlay_view, name='page_overlay'),
    path('export/<int:project_id>/csv/', views.export_csv, name='export_csv'),
    path('export/<int:project_id>/pdf/', views.export_pdf, name='export_pdf'),
    path('export/<int:project_id>/excel/', views.export_excel, name='export_excel'),
]
