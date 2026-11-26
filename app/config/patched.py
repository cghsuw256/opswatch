"""Patched intranet. It uses the same MySQL database and account as the legacy site."""

import os
import sys

from .common import *


SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "lab-only-patched-signing-key-not-a-database-credential",
)
DEBUG = False
ALLOWED_HOSTS = ["intranet.localhost"]
ROOT_URLCONF = "config.patched_urls"
INSTALLED_APPS = [*INSTALLED_APPS, "patched_portal"]
PATCHED_SITE = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE", "opswatch"),
        "USER": os.environ.get("MYSQL_USER", "opswatch"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", "opswatch-lab-only"),
        "HOST": os.environ.get("MYSQL_HOST", "db"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}
if any(arg in {"test", "makemigrations", "check"} for arg in sys.argv):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
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
