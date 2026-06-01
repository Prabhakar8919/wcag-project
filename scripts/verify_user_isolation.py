import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wcag_auditor.settings')

import django
django.setup()
from django.contrib.auth.models import User
from core.models import Project, Scan, Page, Report

for user in User.objects.all():
    projects = Project.objects.filter(user=user).count()
    scans = Scan.objects.filter(project__user=user).count()
    pages = Page.objects.filter(scan__project__user=user).count()
    reports = Report.objects.filter(scan__project__user=user).count()
    print(f'user={user.username} email={user.email} projects={projects} scans={scans} pages={pages} reports={reports}')
