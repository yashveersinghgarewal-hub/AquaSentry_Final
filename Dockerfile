# AquaSentry server + dashboard
#   docker compose up -d        then open http://localhost:8000
# The database lives in the "aquasentry-data" volume (/data), so rebuilding the image keeps it.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATABASE_URL=sqlite:////data/aquasentry.db \
    AQUASENTRY_BACKUP_DIR=/data/backups

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an unprivileged user; /data is the only writable place it needs.
# The shipped demo database is copied in on first start if the volume is empty.
RUN useradd --system --uid 10001 --home /app aquasentry \
 && mkdir -p /data/backups \
 && chown -R aquasentry /data \
 && chmod +x docker-entrypoint.sh
USER aquasentry
VOLUME ["/data"]

EXPOSE 8000

# No curl in the image: Python does the health probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
