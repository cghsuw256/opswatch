"""Settings for the separate, loopback-only patched intranet."""

import os
from pathlib import Path

from .common import *

DATA_DIR = Path(os.environ.get("PATCHED_DATA_DIR", BASE_DIR / ".patched-data"))
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (DATA_DIR / "secret-key").read_text(encoding="ascii").strip()
DEBUG = False
ALLOWED_HOSTS = ["intranet.localhost"]
ROOT_URLCONF = "config.patched_urls"
INSTALLED_APPS = [*INSTALLED_APPS, "patched_portal"]
PATCHED_SITE = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "intranet.sqlite3",
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
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
