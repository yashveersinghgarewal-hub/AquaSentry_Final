"""
HTTP hardening for the AquaSentry server.

- Security headers on every response, with a Content-Security-Policy built from SHA-256 hashes of the
  dashboard's own inline <script> blocks (so no 'unsafe-inline' for scripts on the main pages).
- A small in-memory sliding-window rate limiter for write and chat endpoints (per client IP).
- Per-device API keys: random tokens, stored only as SHA-256 hashes.

Everything here is dependency-free so it runs on a field laptop or a Raspberry Pi.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Iterable, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ---------------------------------------------------------------------------- CSP
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)


def inline_script_hashes(frontend_dir: Path, pages: Iterable[str]) -> list:
    """'sha256-...' sources for every inline <script> in the given pages."""
    out = []
    for name in pages:
        p = frontend_dir / name
        if not p.is_file():
            continue
        for body in _INLINE_SCRIPT.findall(p.read_text(encoding="utf-8")):
            digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
            out.append(f"'sha256-{digest}'")
    return sorted(set(out))


def tile_origin() -> str:
    """Origin of the map tile server (MAP_TILE_URL overrides OpenStreetMap's), for img-src."""
    from urllib.parse import urlparse
    u = urlparse(os.getenv("MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"))
    return f"{u.scheme}://{u.netloc}" if u.scheme in ("http", "https") and u.netloc else ""


def build_csp(script_hashes: list, strict_style: bool = False) -> str:
    """strict_style: no inline styles at all (the dashboard and the public device page set geometry through
    the CSSOM, which CSP allows); the older project pages still use style="" attributes."""
    return "; ".join([
        "default-src 'self'",
        "script-src 'self' " + " ".join(script_hashes),
        "style-src 'self'" if strict_style else "style-src 'self' 'unsafe-inline'",
        ("img-src 'self' data: blob: " + tile_origin()).strip(),
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",          # the device simulator embeds mas-g1-display.html
        "worker-src 'self'",
        "manifest-src 'self'",
    ])


# The archived v1 UI uses inline event handlers and Google Fonts; it gets a looser policy of its own.
LEGACY_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
              "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'self'")

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), payment=(), usb=(), accelerometer=(), gyroscope=(), magnetometer=()",
}


STRICT_STYLE_PAGES = {"/", "/index.html", "/device.html"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, csp: str, strict_csp: Optional[str] = None):
        super().__init__(app)
        self.csp = csp
        self.strict_csp = strict_csp or csp

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for k, v in BASE_HEADERS.items():
            response.headers.setdefault(k, v)
        path = request.url.path
        ctype = response.headers.get("content-type", "")
        if "text/html" in ctype:
            policy = LEGACY_CSP if path.startswith("/legacy_v1/") else (
                self.strict_csp if path in STRICT_STYLE_PAGES else self.csp)
            response.headers.setdefault("Content-Security-Policy", policy)
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


# ---------------------------------------------------------------------------- rate limiting
class RateLimiter:
    """Sliding-window limiter: at most `limit` requests per `window` seconds per key."""

    def __init__(self):
        self._hits: Dict[Tuple[str, str], Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, bucket: str, key: str, limit: int, window: float = 60.0) -> Optional[int]:
        """None if allowed, else seconds until the next request would be allowed."""
        if limit <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault((bucket, key), deque())
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(window - (now - q[0])) + 1)
            q.append(now)
            if len(self._hits) > 10000:      # forget idle clients so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window]:
                    self._hits.pop(k, None)
            return None

    def reset(self):
        with self._lock:
            self._hits.clear()


LIMITER = RateLimiter()

# (method, path prefix) -> (bucket, env var, default per minute)
RATE_RULES = [
    ("POST", "/api/readings", "readings", "RATE_LIMIT_READINGS_PER_MIN", 240),
    ("POST", "/api/data/import", "import", "RATE_LIMIT_IMPORT_PER_MIN", 20),
    ("POST", "/api/chat", "chat", "RATE_LIMIT_CHAT_PER_MIN", 20),
    ("POST", "/api/demo/load", "demo", "RATE_LIMIT_DEMO_PER_MIN", 10),
    ("POST", "/api/admin", "admin", "RATE_LIMIT_ADMIN_PER_MIN", 30),
]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        for method, prefix, bucket, env, default in RATE_RULES:
            if request.method == method and request.url.path.startswith(prefix):
                limit = int(os.getenv(env, str(default)))
                wait = LIMITER.check(bucket, client_ip(request), limit)
                if wait is not None:
                    return JSONResponse({"detail": f"Too many requests. Try again in {wait} s."},
                                        status_code=429, headers={"Retry-After": str(wait)})
                break
        return await call_next(request)


# ---------------------------------------------------------------------------- device keys
KEY_PREFIX = "aqs_"


def new_device_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(24)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def key_matches(given: Optional[str], stored_hash: Optional[str]) -> bool:
    if not given or not stored_hash:
        return False
    return hmac.compare_digest(hash_key(given), stored_hash)
