#!/usr/bin/env bash
# AquaSentry Desktop (macOS / Linux). Run:  chmod +x run_desktop.sh && ./run_desktop.sh
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python)
[ -x .venv/bin/python ] || "$PY" -m venv .venv
if [ ! -f .venv/.desktop_ready ]; then
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt -r requirements-desktop.txt
  touch .venv/.desktop_ready
fi
exec .venv/bin/python desktop_app.py "$@"
