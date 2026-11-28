"""Patched presentation site. It uses the same SQLite database and login session as the legacy site."""

import os

from .common import *


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "lab-only-not-a-real-secret-opswatch-local-exercise",
)
DEBUG = True
ALLOWED_HOSTS = ["intranet.localhost", "127.0.0.1", "localhost"]
if lan_host := os.environ.get("OPSWATCH_PATCHED_HOST"):
    ALLOWED_HOSTS.append(lan_host)
ROOT_URLCONF = "config.patched_urls"
INSTALLED_APPS = [*INSTALLED_APPS, "patched_portal"]
PATCHED_SITE = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("OPSWATCH_DB", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"timeout": 20},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 14},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

CSRF_COOKIE_NAME = "intranet_csrf"
CSRF_COOKIE_HTTPONLY = True
