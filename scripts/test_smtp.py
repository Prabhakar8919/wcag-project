import os
import sys
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)
load_dotenv(find_dotenv())

print('Loaded env')
print('EMAIL_HOST_USER=', repr(os.getenv('EMAIL_HOST_USER')))
print('EMAIL_HOST_PASSWORD=', repr(os.getenv('EMAIL_HOST_PASSWORD')))
print('EMAIL_HOST=', os.getenv('EMAIL_HOST'))
print('EMAIL_PORT=', os.getenv('EMAIL_PORT'))
print('EMAIL_USE_TLS=', os.getenv('EMAIL_USE_TLS'))

from django.conf import settings
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wcag_auditor.settings')
django.setup()

from django.core.mail import EmailMessage, get_connection

connection = get_connection(fail_silently=False)
print('Email backend:', type(connection), connection.host, connection.port, connection.use_tls)

try:
    connection.open()
    print('SMTP connection opened successfully')
except Exception as e:
    print('SMTP connection failed:', repr(e))
    raise

try:
    msg = EmailMessage(
        'WCAG Auditor SMTP Test',
        'This is a test message from WCAG Auditor SMTP test.',
        settings.DEFAULT_FROM_EMAIL,
        [os.getenv('EMAIL_HOST_USER')],
        connection=connection,
    )
    msg.send()
    print('Test email sent successfully')
except Exception as e:
    print('Test email send failed:', repr(e))
    raise
finally:
    try:
        connection.close()
    except Exception:
        pass
