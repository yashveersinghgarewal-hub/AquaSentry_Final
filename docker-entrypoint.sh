#!/bin/sh
# Seed an empty data volume with the demo database once, then start the server on all interfaces.
set -e
DB="${DATABASE_URL#sqlite:///}"
case "$DATABASE_URL" in
  sqlite:*)
    if [ ! -f "$DB" ] && [ -f AquaSentry_Platform/aquasentry.db ]; then
      cp AquaSentry_Platform/aquasentry.db "$DB"
      echo "[entrypoint] Created $DB from the demo database."
    fi ;;
esac
exec python main.py --serve --host 0.0.0.0 --port "${PORT:-8000}"
