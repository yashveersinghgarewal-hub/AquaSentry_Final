"""
Logging for the AquaSentry server.

LOG_FORMAT=text (default) prints readable lines; LOG_FORMAT=json prints one JSON object per line for
log collectors (Loki, CloudWatch, journald with a JSON parser). Every record carries the current
request's X-Request-ID, so a reading, its alert and its webhook delivery can be traced together.
LOG_LEVEL sets the level (INFO by default).
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in ("device_code", "event", "status", "attempts"):
            if hasattr(record, key):
                out[key] = getattr(record, key)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


_configured = False


def setup_logging() -> logging.Logger:
    """Configure the 'aquasentry' logger once (idempotent; uvicorn keeps its own access log)."""
    global _configured
    log = logging.getLogger("aquasentry")
    if _configured:
        return log
    handler = logging.StreamHandler(sys.stderr)
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"))
    handler.addFilter(_RequestIdFilter())
    log.addHandler(handler)
    log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    log.propagate = False
    _configured = True
    return log


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"aquasentry.{name}")
