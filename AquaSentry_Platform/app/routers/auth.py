"""Optional read protection (v5.6).

Set AQUASENTRY_READ_KEY to stop anonymous network clients from reading readings, locations and lab
results. Readers then need one of:
- this computer itself (the dashboard on localhost keeps working),
- X-API-Key: the read key, the write key (AQUASENTRY_API_KEY) or a device key (nodes fetch their calibration),
- the sign-in cookie set by POST /api/auth/login with the read key (what the dashboard uses in a browser;
  EventSource and WebSocket cannot send headers, cookies they can).
Always open: /api/health, /api/auth/*, /api/public/* (QR sticker pages; PUBLIC_DEVICE_PAGES=0 closes them).
"""
import hashlib
import hmac
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .. import models, security
from ..deps import _is_loopback, _key_ok

router = APIRouter()
COOKIE = "aqs_session"
OPEN_PREFIXES = ("/api/health", "/api/auth/", "/api/public/")
SESSION_DAYS = 30


def read_key() -> Optional[str]:
    k = (os.getenv("AQUASENTRY_READ_KEY") or "").strip()
    return k or None


def _sign(expires: int, key: str) -> str:
    mac = hmac.new(key.encode(), f"viewer.{expires}".encode(), hashlib.sha256).hexdigest()
    return f"{expires}.{mac}"


def session_ok(cookie: Optional[str], key: str) -> bool:
    try:
        exp_s, _ = (cookie or "").split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    return exp > time.time() and hmac.compare_digest(cookie, _sign(exp, key))


def _device_key_ok(given: str) -> bool:
    if not given.startswith(security.KEY_PREFIX):
        return False
    from ..database import SessionLocal
    with SessionLocal() as db:
        return db.query(models.Device).filter(models.Device.api_key_hash == security.hash_key(given)).first() is not None


def reader_allowed(request: Request) -> bool:
    key = read_key()
    if key is None or _is_loopback(request) or _key_ok(request):
        return True
    given = request.headers.get("x-api-key") or ""
    if given and (hmac.compare_digest(given.encode(), key.encode()) or _device_key_ok(given)):
        return True
    return session_ok(request.cookies.get(COOKIE), key)


class ReadProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        guarded = (path.startswith("/api/") or path.startswith("/ws/")) and not path.startswith(OPEN_PREFIXES)
        if guarded and request.method in ("GET", "HEAD") and not reader_allowed(request):
            return JSONResponse({"detail": "Sign in to see this data.", "sign_in": "/api/auth/login"}, status_code=401)
        return await call_next(request)


class LoginIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=256)


@router.get("/api/auth/status", tags=["Auth"])
def auth_status(request: Request):
    return {"read_protected": read_key() is not None, "signed_in": reader_allowed(request)}


@router.post("/api/auth/login", tags=["Auth"])
def login(body: LoginIn, request: Request, response: Response):
    key = read_key()
    if key is None:
        return {"read_protected": False, "signed_in": True}
    if not hmac.compare_digest(body.key.encode(), key.encode()):
        raise HTTPException(status_code=401, detail="That key is not right.")
    exp = int(time.time()) + SESSION_DAYS * 86400
    response.set_cookie(COOKIE, _sign(exp, key), max_age=SESSION_DAYS * 86400, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", path="/")
    return {"read_protected": True, "signed_in": True}


@router.post("/api/auth/logout", tags=["Auth"])
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"signed_in": False}
