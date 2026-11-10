"""OpsWatch lab settings. All secrets here are fake and local-only."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Lab-only default. Override in Compose. Never use this value outside the exercise.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "lab-only-not-a-real-secret-opswatch-local-exercise",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "inventory",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "opswatch.urls"
WSGI_APPLICATION = "opswatch.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "inventory.context_processors.lab_notice",
            ],
        },
    }
]

_use_sqlite = (
    os.environ.get("OPSWATCH_DATABASE", "").lower() == "sqlite"
    or any(arg in {"test", "makemigrations", "check"} for arg in sys.argv)
)

if _use_sqlite:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("OPSWATCH_SQLITE_NAME", str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("MYSQL_DATABASE", "opswatch"),
            "USER": os.environ.get("MYSQL_USER", "opswatch"),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", "opswatch-lab-only"),
            "HOST": os.environ.get("MYSQL_HOST", "db"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Fake internal token used by the lab support script. Not a real credential.
OPSWATCH_INTERNAL_TOKEN = os.environ.get(
    "OPSWATCH_INTERNAL_TOKEN",
    "ow-lab-internal-9f3c2a1b7e44",
)

# Shell diagnostics run only when both are set inside the lab container.
OPSWATCH_RUNTIME = os.environ.get("OPSWATCH_RUNTIME", "host")
OPSWATCH_ENABLE_DIAGNOSTICS = os.environ.get("OPSWATCH_ENABLE_DIAGNOSTICS", "0") == "1"

SUPPORT_SCRIPT_PATH = BASE_DIR / "support_scripts" / "opswatch-healthcheck.sh"

# INTENTIONAL LAB WEAKNESS: no login attempt limit / lockout is configured.
# AUTH_PASSWORD_VALIDATORS is empty so the seeded maintenance password can stay weak.
