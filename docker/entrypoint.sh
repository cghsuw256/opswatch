#!/bin/sh
set -eu

python - <<'PY'
import os
import time

import pymysql

host = os.environ.get("MYSQL_HOST", "db")
user = os.environ.get("MYSQL_USER", "opswatch")
password = os.environ.get("MYSQL_PASSWORD", "opswatch-lab-only")
database = os.environ.get("MYSQL_DATABASE", "opswatch")

for _ in range(60):
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            connect_timeout=2,
        )
        conn.close()
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("MySQL was not ready")
PY

python manage.py migrate --noinput
python manage.py seed_lab
exec gunicorn opswatch.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 1 \
  --threads 2 \
  --timeout 30 \
  --access-logfile -
