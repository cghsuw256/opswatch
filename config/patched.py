"""Patched presentation site with its own local SQLite database."""

import os

from .common import *


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "lab-only-patched-signing-key-not-a-database-credential",
)
DEBUG = False
ALLOWED_HOSTS = ["intranet.localhost", "127.0.0.1", "localhost"]
if lan_host := os.environ.get("OPSWATCH_PATCHED_HOST"):
    ALLOWED_HOSTS.append(lan_host)
ROOT_URLCONF = "config.patched_urls"
INSTALLED_APPS = [*INSTALLED_APPS, "patched_portal"]
PATCHED_SITE = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("OPSWATCH_PATCHED_DB", BASE_DIR / "patched.sqlite3"),
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

SESSION_COOKIE_NAME = "intranet_session"
CSRF_COOKIE_NAME = "intranet_csrf"
CSRF_COOKIE_HTTPONLY = True
