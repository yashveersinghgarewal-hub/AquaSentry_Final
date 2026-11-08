"""
Shared request helpers: write / admin / read protection, small value helpers and the device lookup.
Imported by app.main and the routers in app/routers (kept out of main.py to avoid circular imports).
"""
import hmac
import ipaddress
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from . import models, security


def active_model_name() -> str:
    """The model that classifies stored readings (AQUANET_MODEL=v1 switches back to the hand-built V1)."""
    return "AquaNet-V1" if os.getenv("AQUANET_MODEL", "v3").lower() == "v1" else "AquaNet-V3"


def _is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def _val(x, default):
    """`x or default` treats a real 0 (0 NTU, 0 °C, 0 µS/cm) as missing. This does not."""
    return default if x is None else x


def now_utc():
    return datetime.now(timezone.utc)


def _api_key() -> Optional[str]:
    key = (os.getenv("AQUASENTRY_API_KEY") or "").strip()
    return key or None


def _is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if host in ("testclient", "localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _key_ok(request: Request) -> bool:
    key = _api_key()
    given = request.headers.get("x-api-key") or ""
    return bool(key) and hmac.compare_digest(given.encode(), key.encode())


def _check_device_key(db: Session, device_code: str, request: Request):
    dev = db.query(models.Device).filter_by(device_code=device_code).first()
    if dev is not None and dev.api_key_hash:
        given = request.headers.get("x-api-key")
        if not (security.key_matches(given, dev.api_key_hash) or _key_ok(request)):
            raise HTTPException(status_code=401, detail=f"Device '{device_code}' has its own API key; send it as X-API-Key.")


def trusted_origins() -> list:
    """Browser origins allowed to call the API (CORS) and to write from this computer."""
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if raw and raw != "*":
        return [o.strip() for o in raw.split(",") if o.strip()]
    port = os.getenv("AQUASENTRY_PORT", "8000")
    return sorted({f"http://localhost:{port}", f"http://127.0.0.1:{port}", "http://localhost:8000", "http://127.0.0.1:8000"})


def _origin_ok(request: Request) -> bool:
    """A web page you visit runs in your browser on this computer, so its requests also come from 127.0.0.1.
    Browsers send an Origin header with such requests; only the dashboard's own origin may write."""
    origin = request.headers.get("origin")
    if origin is None:
        return True                       # not a browser cross-site request (ESP32, scripts, same-origin GET)
    host = request.headers.get("host", "")
    return origin in (f"http://{host}", f"https://{host}") or origin in trusted_origins()


def require_writer(request: Request):
    """Writes are allowed from this computer (but not from another website open in its browser), with the global
    key, or with any registered device key (then checked against the body's device_code by _check_device_key).
    v5.7: with no AQUASENTRY_API_KEY set, network clients can no longer write (was: open to the whole network)."""
    if _key_ok(request):
        return
    if _is_loopback(request):
        if not _origin_ok(request):
            raise HTTPException(status_code=403, detail="Writes from another website are not allowed.")
        return
    given = request.headers.get("x-api-key")
    if given and given.startswith(security.KEY_PREFIX):
        from .database import SessionLocal
        with SessionLocal() as db:
            if db.query(models.Device).filter(models.Device.api_key_hash == security.hash_key(given)).first():
                return
    if _api_key() is None and os.getenv("AQUASENTRY_OPEN_WRITES") == "1":
        return                            # explicit opt-in for a closed test network only
    raise HTTPException(status_code=401, detail="Missing or wrong X-API-Key header. Set AQUASENTRY_API_KEY in .env "
                                                "on the server and the same key in the device.")


def require_admin(request: Request):
    """Admin actions never run for an anonymous network client, even with writes open."""
    if _key_ok(request) or (_is_loopback(request) and _origin_ok(request)):
        return
    raise HTTPException(status_code=403, detail="Admin endpoints are only available from this computer or with X-API-Key.")


# ---------------------------------------------------------------------------
# Device Helpers
# ---------------------------------------------------------------------------

def _get_or_create_device(db: Session, device_code: str, firmware_version: Optional[str] = None) -> models.Device:
    device = db.query(models.Device).filter_by(device_code=device_code).first()
    ts = now_utc()
    if device is None:
        device = models.Device(
            device_code=device_code,
            first_seen=ts,
            last_seen=ts,
            status="online",
            firmware_version=firmware_version or None,
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    else:
        device.last_seen = ts
        if firmware_version:
            device.firmware_version = firmware_version
        db.commit()
    return device


def _utc(d: Optional[datetime]) -> Optional[datetime]:
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
