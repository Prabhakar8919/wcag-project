import sqlite3
import os
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wcag_auditor.settings')

import django
from django.conf import settings
from django.db import connections

django.setup()

sqlite_path = BASE_DIR / 'db.sqlite3'
if not sqlite_path.exists():
    raise FileNotFoundError(f'Could not find sqlite database at {sqlite_path}')

src = sqlite3.connect(sqlite_path)
cur = src.cursor()
source_tables = [
    'auth_user', 'auth_group', 'auth_permission', 'auth_user_groups', 'auth_user_user_permissions',
    'auth_group_permissions', 'core_profile', 'core_project', 'core_scan', 'core_page', 'core_report',
    'rules_rule', 'rules_issue', 'django_session', 'django_admin_log', 'django_content_type'
]
print('SQLite counts:')
for table in source_tables:
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    print(f'{table}:', cur.fetchone()[0])

print('\nPostgres counts:')
conn = connections['default']
cur2 = conn.cursor()
for table in source_tables:
    cur2.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'{table}:', cur2.fetchone()[0])
cur2.close()
src.close()
