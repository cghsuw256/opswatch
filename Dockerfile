FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --home-dir /app --shell /usr/sbin/nologin appuser \
    && mkdir -p /opt/challenge /app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=appuser:appuser . /app
COPY challenge/flag.txt /opt/challenge/flag.txt

RUN chmod 755 /app/docker/entrypoint.sh \
    && chmod 444 /opt/challenge/flag.txt \
    && chown -R appuser:appuser /app

USER appuser
RUN OPSWATCH_DATABASE=sqlite python manage.py collectstatic --noinput
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
