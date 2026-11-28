"""Legacy presentation site; use fake data on localhost only."""

import os

from .common import *

# Local demonstration only; do not deploy.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "lab-only-not-a-real-secret-opswatch-local-exercise",
)

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

ROOT_URLCONF = "config.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("OPSWATCH_DB", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = []
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "unit_portal.hashers.LegacyPBKDF2SHA256PasswordHasher",
]

OPSWATCH_PATCHED_URL = f"http://{os.environ.get('OPSWATCH_PATCHED_HOST', '127.0.0.1')}:8001/"
