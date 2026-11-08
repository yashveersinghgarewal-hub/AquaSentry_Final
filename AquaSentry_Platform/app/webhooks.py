"""
Outgoing alert webhooks, signed the Standard Webhooks way (https://www.standardwebhooks.com).

Each delivery carries three headers:
    webhook-id         the alert id (receivers de-duplicate on it; retries reuse it)
    webhook-timestamp  Unix seconds when this attempt was signed
    webhook-signature  "v1,<base64 HMAC-SHA256 of '{id}.{timestamp}.{body}'>"

The secret comes from ALERT_WEBHOOK_SECRET. A "whsec_" prefix means the rest is base64 (the format
Svix and the Standard Webhooks libraries generate); anything else is used as raw UTF-8 bytes.
Without a secret the request is sent unsigned, as before.

Delivery runs on a background thread so a slow receiver never delays the ESP32's upload. Network
errors, 408, 429 and 5xx responses are retried with exponential back-off; other 4xx are not.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}

STATS = {"sent": 0, "failed": 0, "retried": 0}
_STATS_LOCK = threading.Lock()


def _bump(key: str, n: int = 1):
    with _STATS_LOCK:
        STATS[key] += n


def secret_bytes(secret: Optional[str]) -> Optional[bytes]:
    if not secret:
        return None
    if secret.startswith("whsec_"):
        try:
            return base64.b64decode(secret[len("whsec_"):], validate=True)
        except Exception:
            pass
    return secret.encode("utf-8")


def sign(msg_id: str, timestamp: int, body: bytes, secret: bytes) -> str:
    to_sign = f"{msg_id}.{timestamp}.".encode("utf-8") + body
    return "v1," + base64.b64encode(hmac.new(secret, to_sign, hashlib.sha256).digest()).decode()


def verify(headers: Dict[str, str], body: bytes, secret: Optional[str], tolerance_s: int = 300,
           now: Optional[float] = None) -> bool:
    """Receiver-side check (used in the tests and handy for anyone writing a receiver in Python)."""
    key = secret_bytes(secret)
    h = {k.lower(): v for k, v in headers.items()}
    try:
        msg_id, ts = h["webhook-id"], int(h["webhook-timestamp"])
    except (KeyError, ValueError):
        return False
    if key is None or abs((now or time.time()) - ts) > tolerance_s:
        return False
    expected = sign(msg_id, ts, body, key).split(",", 1)[1]
    for part in h.get("webhook-signature", "").split():
        version, _, sig = part.partition(",")
        if version == "v1" and hmac.compare_digest(sig, expected):
            return True
    return False


def valid_url(url: Optional[str]) -> bool:
    """Only http(s) URLs: urllib would otherwise happily open file:// or ftp:// targets."""
    if not url:
        return False
    p = urllib.parse.urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc)


def deliver(url: str, payload: Dict[str, Any], secret: Optional[str] = None, attempts: int = 3,
            backoff_s: float = 1.0, timeout_s: float = 5.0,
            sleep: Callable[[float], None] = time.sleep,
            opener: Callable[..., Any] = urllib.request.urlopen) -> Dict[str, Any]:
    """POST the payload, retrying transient failures. Returns {"ok", "attempts", "status", "error"}."""
    if not valid_url(url):
        _bump("failed")
        return {"ok": False, "attempts": 0, "status": None, "error": "ALERT_WEBHOOK_URL must be an http(s) URL"}
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    msg_id = str(payload.get("id") or hashlib.sha256(body).hexdigest()[:32])
    key = secret_bytes(secret)
    status, error = None, None
    for n in range(1, max(1, attempts) + 1):
        ts = int(time.time())
        headers = {"Content-Type": "application/json", "User-Agent": "AquaSentry-Alerts/1",
                   "webhook-id": msg_id, "webhook-timestamp": str(ts)}
        if key:
            headers["webhook-signature"] = sign(msg_id, ts, body, key)
        try:
            resp = opener(urllib.request.Request(url, data=body, headers=headers, method="POST"), timeout=timeout_s)
            status = getattr(resp, "status", None) or resp.getcode()
            resp.close()
            if 200 <= status < 300:
                _bump("sent")
                return {"ok": True, "attempts": n, "status": status, "error": None}
            error = f"HTTP {status}"
        except urllib.error.HTTPError as e:
            status, error = e.code, f"HTTP {e.code}"
        except Exception as e:          # DNS, refused, timeout, TLS
            status, error = None, f"{type(e).__name__}: {e}"
        if status is not None and status not in RETRYABLE:
            break
        if n < attempts:
            _bump("retried")
            sleep(backoff_s * (4 ** (n - 1)))      # 1 s, 4 s, 16 s ...
    _bump("failed")
    print(f"Warning: alert webhook failed after {n} attempt(s): {error}")
    return {"ok": False, "attempts": n, "status": status, "error": error}


def deliver_in_background(url: str, payload: Dict[str, Any]) -> threading.Thread:
    th = threading.Thread(
        target=deliver, args=(url, payload),
        kwargs={"secret": os.getenv("ALERT_WEBHOOK_SECRET"),
                "attempts": int(os.getenv("ALERT_WEBHOOK_ATTEMPTS", "3"))},
        daemon=True)
    th.start()
    return th
