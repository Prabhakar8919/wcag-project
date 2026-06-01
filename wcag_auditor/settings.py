from pathlib import Path
import os
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-ozh_u)mm8(17k(tk5s!u!17z=kdcf-vab@0z_=*3%yf^j9ksif')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "crawler",
    "rules",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.SaaSAuthRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

ROOT_URLCONF = "wcag_auditor.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "wcag_auditor.wsgi.application"



DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
DB_ENGINE = os.getenv('DB_ENGINE', 'django.db.backends.postgresql').strip()
DB_NAME = os.getenv('DB_NAME', 'wcag_auditor').strip()
DB_USER = os.getenv('DB_USER', 'postgres').strip()
DB_PASSWORD = os.getenv('DB_PASSWORD', '').strip()
DB_HOST = os.getenv('DB_HOST', 'localhost').strip()
DB_PORT = os.getenv('DB_PORT', '5432').strip()
DB_CONN_MAX_AGE = int(os.getenv('DB_CONN_MAX_AGE', 600))
DB_CONNECT_TIMEOUT = int(os.getenv('DB_CONNECT_TIMEOUT', 10))
DB_SSLMODE = os.getenv('DB_SSLMODE', 'prefer').strip()

if DATABASE_URL:
    parsed_url = urlparse(DATABASE_URL)
    if parsed_url.scheme in ('postgres', 'postgresql'):
        DB_ENGINE = 'django.db.backends.postgresql'
    elif parsed_url.scheme in ('sqlite', 'sqlite3'):
        DB_ENGINE = 'django.db.backends.sqlite3'

    DB_NAME = unquote(parsed_url.path[1:] if parsed_url.path else '') or DB_NAME
    DB_USER = unquote(parsed_url.username) if parsed_url.username else DB_USER
    DB_PASSWORD = unquote(parsed_url.password) if parsed_url.password else DB_PASSWORD
    DB_HOST = parsed_url.hostname or DB_HOST
    DB_PORT = str(parsed_url.port or DB_PORT)

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / os.getenv('SQLITE_NAME', 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'CONN_MAX_AGE': DB_CONN_MAX_AGE,
            'OPTIONS': {
                'connect_timeout': DB_CONNECT_TIMEOUT,
                'sslmode': DB_SSLMODE,
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# LLM Integration Settings
LLM_ENABLED = True
LLM_MODEL = "llama-3.1-8b-instant"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_TIMEOUT = 30
CELERY_TIMEZONE = TIME_ZONE

# Phase 5 Optimization Settings
MAX_CRAWLER_WORKERS = 5
MAX_LLM_CONCURRENCY = 5
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3

# SMTP Email Configuration (Gmail App Password)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or 'no-reply@wcagauditor.com'

