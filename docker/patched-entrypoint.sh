#!/bin/sh
set -eu
umask 077

python - <<'PY'
import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

key = Path(os.environ["PATCHED_DATA_DIR"]) / "secret-key"
try:
    with key.open("x", encoding="ascii") as output:
        output.write(get_random_secret_key() + "\n")
except FileExistsError:
    pass
PY

python manage.py migrate --noinput
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 --workers 1 --threads 2 --timeout 30 --access-logfile -
