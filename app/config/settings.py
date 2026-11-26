"""Defense intranet lab settings. All secrets here are fake and local-only."""

import os
import sys

from .common import *

# Lab-only default. Override in Compose. Never use this value outside the exercise.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "lab-only-not-a-real-secret-opswatch-local-exercise",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

ROOT_URLCONF = "config.urls"

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
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "unit_portal.hashers.LegacyPBKDF2SHA256PasswordHasher",
]

CSRF_COOKIE_HTTPONLY = False
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000", "http://localhost:8000"]

# Fake internal token expected by /api/internal/diagnose/. Not a real credential.
# INTENTIONAL LAB WEAKNESS: agent metadata returns this static value.
OPSWATCH_INTERNAL_TOKEN = os.environ.get(
    "OPSWATCH_INTERNAL_TOKEN",
    "ow-lab-internal-9f3c2a1b7e44",
)

# Shell diagnostics are permitted only inside the explicitly enabled container.
OPSWATCH_RUNTIME = os.environ.get("OPSWATCH_RUNTIME", "host")
OPSWATCH_ENABLE_DIAGNOSTICS = os.environ.get("OPSWATCH_ENABLE_DIAGNOSTICS", "0") == "1"
