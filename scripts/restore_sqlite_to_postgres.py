import os
import sqlite3
import sys
from pathlib import Path
from pprint import pprint

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wcag_auditor.settings')

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction, models
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def find_sqlite_database():
    candidate = BASE_DIR / os.getenv('SQLITE_NAME', 'db.sqlite3')
    if candidate.exists():
        return candidate

    for ext in ('*.sqlite3', '*.db', '*.sqlite'):
        found = list(BASE_DIR.glob(ext))
        if found:
            return found[0]

    raise FileNotFoundError('Could not automatically detect the old SQLite database file in the project root.')


def parse_value(field, value):
    if value is None:
        return None

    if isinstance(field, models.BooleanField):
        return bool(value)
    if isinstance(field, models.IntegerField):
        return int(value)
    if isinstance(field, models.FloatField):
        return float(value)
    if isinstance(field, (models.DateTimeField, models.DateField)):
        if isinstance(value, str):
            parsed = parse_datetime(value)
            if parsed is None:
                return value
            if getattr(settings, 'USE_TZ', False) and timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed)
            return parsed
    return value


def parse_datetime_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_datetime(value)
    else:
        parsed = value
    if parsed is None:
        return value
    if getattr(settings, 'USE_TZ', False) and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def build_row_data(model, row, overrides=None):
    data = {}
    overrides = overrides or {}
    for key, value in row.items():
        if key == 'id' or key not in model._meta.fields_map and key.endswith('_id'):
            # IDs are handled explicitly or as raw FK IDs
            pass
        if key == 'id' or key in [f.name for f in model._meta.fields]:
            field = model._meta.get_field(key)
            data[key] = parse_value(field, value)

    data.update(overrides)
    return data


def copy_rows(sql_conn, table_name):
    sql_conn.row_factory = sqlite3.Row
    cursor = sql_conn.cursor()
    cursor.execute(f'SELECT * FROM "{table_name}"')
    return [dict(row) for row in cursor.fetchall()]


def get_or_create_contenttype(source_row, content_type_map):
    defaults = {}
    if 'name' in source_row and source_row['name'] is not None:
        defaults['name'] = source_row['name']
    target_ct, created = ContentType.objects.get_or_create(
        app_label=source_row['app_label'],
        model=source_row['model'],
        defaults=defaults
    )
    content_type_map[source_row['id']] = target_ct.id
    return target_ct


def transfer_models():
    sqlite_path = find_sqlite_database()
    print(f'Using source SQLite database: {sqlite_path}')

    if 'postgresql' not in settings.DATABASES['default']['ENGINE']:
        raise RuntimeError('Target Django database must be PostgreSQL for this restore script.')

    print('Running Postgres migrations first...')
    call_command('migrate', interactive=False, run_syncdb=True)
    print('Migrations complete.')

    sql_conn = sqlite3.connect(str(sqlite_path))
    sql_conn.row_factory = sqlite3.Row

    with transaction.atomic():
        content_type_map = {}
        print('Copying django_content_type rows into target mapping...')
        for row in copy_rows(sql_conn, 'django_content_type'):
            get_or_create_contenttype(row, content_type_map)
        print(f'Mapped {len(content_type_map)} content types.')

        group_map = {}
        print('Copying auth_group rows...')
        for row in copy_rows(sql_conn, 'auth_group'):
            group = Group.objects.filter(name=row['name']).first()
            if group is None:
                group = Group(id=row['id'], name=row['name'])
                group.save(force_insert=True)
            group_map[row['id']] = group.id
        print(f'Copied {len(group_map)} groups.')

        perm_map = {}
        print('Copying auth_permission rows...')
        for row in copy_rows(sql_conn, 'auth_permission'):
            target_ct_id = content_type_map.get(row['content_type_id'])
            if target_ct_id is None:
                raise RuntimeError(f"Missing content type mapping for permission id {row['id']}")
            target_ct = ContentType.objects.get(id=target_ct_id)
            existing = Permission.objects.filter(content_type=target_ct, codename=row['codename']).first()
            if existing is None:
                permission = Permission(
                    id=row['id'],
                    content_type=target_ct,
                    codename=row['codename'],
                    name=row['name']
                )
                permission.save(force_insert=True)
                perm_map[row['id']] = permission.id
            else:
                perm_map[row['id']] = existing.id
        print(f'Copied or mapped {len(perm_map)} permissions.')

        user_map = {}
        print('Copying auth_user rows...')
        for row in copy_rows(sql_conn, 'auth_user'):
            existing = User.objects.filter(username=row['username']).first() or User.objects.filter(email=row['email']).first()
            if existing is not None:
                user_map[row['id']] = existing.id
                continue

            # Build user record with explicit primary key and hashed password
            user = User(
                id=row['id'],
                username=row['username'],
                email=row['email'],
                password=row['password'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                is_staff=bool(row['is_staff']),
                is_superuser=bool(row['is_superuser']),
                is_active=bool(row['is_active']),
            )
            if row['last_login']:
                user.last_login = parse_datetime_value(row['last_login'])
            if row['date_joined']:
                user.date_joined = parse_datetime_value(row['date_joined'])
            user.save(force_insert=True)
            user_map[row['id']] = user.id
        print(f'Copied or mapped {len(user_map)} users.')

        print('Copying auth_user_groups associations...')
        user_groups = copy_rows(sql_conn, 'auth_user_groups')
        for row in user_groups:
            user_id = user_map.get(row['user_id'])
            group_id = group_map.get(row['group_id'])
            if user_id is None or group_id is None:
                continue
            if not User.objects.get(pk=user_id).groups.filter(pk=group_id).exists():
                User.objects.get(pk=user_id).groups.add(group_id)
        print(f'Copied {len(user_groups)} user-group memberships.')

        print('Copying auth_user_user_permissions associations...')
        user_perms = copy_rows(sql_conn, 'auth_user_user_permissions')
        for row in user_perms:
            user_id = user_map.get(row['user_id'])
            perm_id = perm_map.get(row['permission_id'])
            if user_id is None or perm_id is None:
                continue
            user = User.objects.get(pk=user_id)
            if not user.user_permissions.filter(pk=perm_id).exists():
                user.user_permissions.add(perm_id)
        print(f'Copied {len(user_perms)} user-permission assignments.')

        print('Copying auth_group_permissions associations...')
        group_perms = copy_rows(sql_conn, 'auth_group_permissions')
        for row in group_perms:
            group_id = group_map.get(row['group_id'])
            perm_id = perm_map.get(row['permission_id'])
            if group_id is None or perm_id is None:
                continue
            group = Group.objects.get(pk=group_id)
            if not group.permissions.filter(pk=perm_id).exists():
                group.permissions.add(perm_id)
        print(f'Copied {len(group_perms)} group-permission assignments.')

        print('Copying core_profile rows...')
        for row in copy_rows(sql_conn, 'core_profile'):
            target_user_id = user_map.get(row['user_id'])
            if target_user_id is None:
                print(f'Warning: skipping profile for missing user id {row["user_id"]}')
                continue
            existing = Profile.objects.filter(user_id=target_user_id).first()
            if existing:
                continue
            profile = Profile(
                id=row['id'],
                user_id=target_user_id,
                company=row['company'],
                api_key=row['api_key'],
                default_wcag_level=row['default_wcag_level'],
                is_email_verified=bool(row['is_email_verified']),
            )
            for dt_key in ('otp_created_at', 'otp_expiry', 'otp_last_resent'):
                if row[dt_key]:
                    setattr(profile, dt_key, parse_datetime_value(row[dt_key]))
            profile.otp_code = row['otp_code']
            profile.otp_attempts = int(row['otp_attempts'])
            profile.save(force_insert=True)
        print('Copied profiles.')

        print('Copying core_project rows...')
        for row in copy_rows(sql_conn, 'core_project'):
            if not User.objects.filter(pk=row['user_id']).exists():
                print(f'Warning: skipping project {row["id"]} due missing user {row["user_id"]}')
                continue
            if Project.objects.filter(pk=row['id']).exists():
                continue
            project = Project(
                id=row['id'],
                user_id=row['user_id'],
                domain=row['domain'],
                wcag_level=row['wcag_level'],
                crawl_limit=row['crawl_limit'],
                crawl_depth=row['crawl_depth'],
                sitemap_enabled=bool(row['sitemap_enabled']),
                estimated_pages=row['estimated_pages'],
            )
            if row['created_at']:
                project.created_at = parse_datetime_value(row['created_at'])
            if row['updated_at']:
                project.updated_at = parse_datetime_value(row['updated_at'])
            project.save(force_insert=True)
        print('Copied projects.')

        print('Copying core_scan rows...')
        for row in copy_rows(sql_conn, 'core_scan'):
            if not Project.objects.filter(pk=row['project_id']).exists():
                print(f'Warning: skipping scan {row["id"]} due missing project {row["project_id"]}')
                continue
            if Scan.objects.filter(pk=row['id']).exists():
                continue
            scan = Scan(
                id=row['id'],
                project_id=row['project_id'],
                status=row['status'],
                ai_pages_processed=row['ai_pages_processed'],
                ai_total_time=row['ai_total_time'],
                ai_errors_count=row['ai_errors_count'],
            )
            if row['started_at']:
                scan.started_at = parse_datetime_value(row['started_at'])
            if row['completed_at']:
                scan.completed_at = parse_datetime_value(row['completed_at'])
            scan.save(force_insert=True)
        print('Copied scans.')

        print('Copying core_page rows...')
        for row in copy_rows(sql_conn, 'core_page'):
            if not Scan.objects.filter(pk=row['scan_id']).exists():
                print(f'Warning: skipping page {row["id"]} due missing scan {row["scan_id"]}')
                continue
            if Page.objects.filter(pk=row['id']).exists():
                continue
            page = Page(
                id=row['id'],
                scan_id=row['scan_id'],
                url=row['url'],
                html_snapshot=row['html_snapshot'],
                title=row['title'],
                status_code=row['status_code'],
                page_size=row['page_size'],
                status=row['status'],
            )
            if row['created_at']:
                page.created_at = parse_datetime_value(row['created_at'])
            page.save(force_insert=True)
        print('Copied pages.')

        print('Copying core_report rows...')
        for row in copy_rows(sql_conn, 'core_report'):
            if not Scan.objects.filter(pk=row['scan_id']).exists():
                print(f'Warning: skipping report {row["id"]} due missing scan {row["scan_id"]}')
                continue
            if Report.objects.filter(pk=row['id']).exists():
                continue
            report = Report(
                id=row['id'],
                scan_id=row['scan_id'],
                total_pages_scanned=row['total_pages_scanned'],
                total_issues_found=row['total_issues_found'],
                ai_issues_found=row['ai_issues_found'],
                score=row['score'],
                score_perceivable=row['score_perceivable'],
                score_operable=row['score_operable'],
                score_understandable=row['score_understandable'],
                score_robust=row['score_robust'],
                compliance_20=row['compliance_20'],
                compliance_21=row['compliance_21'],
                compliance_22=row['compliance_22'],
                level_a_issues=row['level_a_issues'],
                level_aa_issues=row['level_aa_issues'],
                level_aaa_issues=row['level_aaa_issues'],
                ai_summary=row['ai_summary'],
                ai_health_report=row['ai_health_report'],
                ai_legal_insights=row['ai_legal_insights'],
                ai_risk_analysis=row['ai_risk_analysis'],
            )
            if row['generated_at']:
                report.generated_at = parse_datetime_value(row['generated_at'])
            report.save(force_insert=True)
        print('Copied reports.')

        print('Copying rules_rule rows...')
        for row in copy_rows(sql_conn, 'rules_rule'):
            if Rule.objects.filter(pk=row['id']).exists():
                continue
            rule = Rule(
                id=row['id'],
                wcag_id=row['wcag_id'],
                title=row['title'],
                level=row['level'],
                category=row['category'],
                check_type=row['check_type'],
                version=row['version'],
                logic=row['logic'],
                fix_suggestion=row['fix_suggestion'],
            )
            rule.save(force_insert=True)
        print('Copied WCAG rules.')

        print('Copying rules_issue rows...')
        for row in copy_rows(sql_conn, 'rules_issue'):
            if not Scan.objects.filter(pk=row['scan_id']).exists() or not Page.objects.filter(pk=row['page_id']).exists() or not Rule.objects.filter(pk=row['rule_id']).exists():
                print(f'Warning: skipping issue {row["id"]} due missing related scan/page/rule')
                continue
            if Issue.objects.filter(pk=row['id']).exists():
                continue
            issue = Issue(
                id=row['id'],
                scan_id=row['scan_id'],
                page_id=row['page_id'],
                rule_id=row['rule_id'],
                severity=row['severity'],
                message=row['message'],
                element_html=row['element_html'],
                fix_suggestion=row['fix_suggestion'],
                corrected_html=row['corrected_html'],
            )
            if row['created_at']:
                issue.created_at = parse_datetime_value(row['created_at'])
            issue.save(force_insert=True)
        print('Copied issues.')

        print('Copying django_session rows...')
        for row in copy_rows(sql_conn, 'django_session'):
            if Session.objects.filter(session_key=row['session_key']).exists():
                continue
            session = Session(
                session_key=row['session_key'],
                session_data=row['session_data'],
            )
            if row['expire_date']:
                session.expire_date = parse_datetime_value(row['expire_date'])
            session.save(force_insert=True)
        print('Copied session records.')

        print('Copying django_admin_log rows...')
        for row in copy_rows(sql_conn, 'django_admin_log'):
            if LogEntry.objects.filter(pk=row['id']).exists():
                continue
            content_type_id = content_type_map.get(row['content_type_id']) if row['content_type_id'] else None
            if row['user_id'] and not User.objects.filter(pk=row['user_id']).exists():
                print(f'Warning: skipping admin log {row["id"]} due missing user {row["user_id"]}')
                continue
            log = LogEntry(
                id=row['id'],
                action_time=parse_datetime_value(row['action_time']),
                user_id=row['user_id'],
                content_type_id=content_type_id,
                object_id=row['object_id'],
                object_repr=row['object_repr'],
                action_flag=row['action_flag'],
                change_message=row['change_message'],
            )
            log.save(force_insert=True)
        print('Copied admin log entries.')

        reset_sequences([
            User, Group, Permission, ContentType, Profile, Project, Scan, Page, Report, Rule, Issue
        ])

    print('Data restore completed successfully.')


def reset_sequences(models_list):
    conn = connections['default']
    with conn.cursor() as cursor:
        for model in models_list:
            table_name = model._meta.db_table
            pk_name = model._meta.pk.column
            cursor.execute('SELECT pg_get_serial_sequence(%s, %s)', [table_name, pk_name])
            seq = cursor.fetchone()[0]
            if not seq:
                print(f'No sequence found for {table_name}.{pk_name}; skipping sequence reset.')
                continue
            cursor.execute(f'SELECT MAX({pk_name}) FROM {table_name}')
            max_id = cursor.fetchone()[0]
            if max_id is None:
                cursor.execute('SELECT setval(%s, 1, false)', [seq])
                print(f'Reset {seq} to 1 (empty table).')
            else:
                cursor.execute('SELECT setval(%s, %s, true)', [seq, max_id])
                print(f'Reset {seq} to {max_id} (next value will be {max_id + 1}).')


if __name__ == '__main__':
    django.setup()
    from django.contrib.auth.models import User, Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from django.contrib.sessions.models import Session
    from django.contrib.admin.models import LogEntry
    from core.models import Profile, Project, Scan, Page, Report
    from rules.models import Rule, Issue

    transfer_models()
