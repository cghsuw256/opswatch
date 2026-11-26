FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.patched \
    PATCHED_DATA_DIR=/data

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --home-dir /app --shell /usr/sbin/nologin appuser \
    && install -d -o appuser -g appuser -m 700 /data /app/staticfiles

WORKDIR /app/app

COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/manage.py ./
COPY app/config/__init__.py app/config/common.py app/config/patched.py app/config/patched_urls.py app/config/wsgi.py ./config/
COPY app/unit_portal/ ./unit_portal/
COPY app/patched_portal/ ./patched_portal/
COPY app/operations/__init__.py app/operations/admin_settings.py app/operations/apps.py app/operations/charts.py app/operations/models.py app/operations/overview.py ./operations/
COPY app/operations/migrations/ ./operations/migrations/
COPY app/operations/templates/inventory/base.html app/operations/templates/inventory/login.html app/operations/templates/inventory/dashboard.html app/operations/templates/inventory/staff.html ./operations/templates/inventory/
COPY app/operations/static/opswatch/app.css app/operations/static/opswatch/dashboard.js ./operations/static/opswatch/

COPY docker/patched-entrypoint.sh /usr/local/bin/patched-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/patched-entrypoint && chmod 755 /usr/local/bin/patched-entrypoint

USER appuser
RUN DJANGO_SECRET_KEY=collectstatic-build-only python manage.py collectstatic --noinput
EXPOSE 8000
ENTRYPOINT ["patched-entrypoint"]
