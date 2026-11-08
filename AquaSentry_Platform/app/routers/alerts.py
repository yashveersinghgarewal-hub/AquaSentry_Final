"""Alert subscriptions (v5.6): browsers subscribe themselves for push; WhatsApp and SMS numbers are
added by an admin (they cost money per message and need the person's consent)."""
import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, notify
from ..database import get_db
from ..deps import require_admin
from .auth import reader_allowed

router = APIRouter()


@router.get("/api/alerts/channels", tags=["Alerts"])
def channels():
    """Which channels this server can send on, and the public key browsers need to subscribe for push."""
    return notify.channels_status()


class PushKeys(BaseModel):
    p256dh: str = Field(..., max_length=200)
    auth: str = Field(..., max_length=100)


class PushSubscription(BaseModel):
    endpoint: str = Field(..., max_length=1000, pattern=r"^https://")
    keys: PushKeys


class PushIn(BaseModel):
    subscription: PushSubscription
    device_code: Optional[str] = Field(None, max_length=64)
    min_level: Literal["CRITICAL", "WARNING"] = "CRITICAL"
    language: Literal["en", "hi", "bn", "as", "pa"] = "en"


@router.post("/api/alerts/subscribe/webpush", tags=["Alerts"])
def subscribe_webpush(body: PushIn, request: Request, db: Session = Depends(get_db)):
    if not reader_allowed(request):
        raise HTTPException(status_code=401, detail="Sign in first.")
    if notify.vapid()[1] is None:
        raise HTTPException(status_code=503, detail="Push alerts need the pywebpush package on the server.")
    target = json.dumps(body.subscription.model_dump(), separators=(",", ":"))
    h = notify.target_hash("webpush", body.subscription.endpoint)
    sub = db.query(models.AlertSubscription).filter_by(target_hash=h).first()
    if sub is None:
        sub = models.AlertSubscription(channel="webpush", target=target, target_hash=h)
        db.add(sub)
    sub.target, sub.device_code, sub.min_level, sub.language, sub.active, sub.failures = (
        target, body.device_code, body.min_level, body.language, True, 0)
    db.commit()
    return {"status": "subscribed", "id": sub.id}


class UnsubIn(BaseModel):
    endpoint: str = Field(..., max_length=1000)


@router.post("/api/alerts/unsubscribe/webpush", tags=["Alerts"])
def unsubscribe_webpush(body: UnsubIn, db: Session = Depends(get_db)):
    sub = db.query(models.AlertSubscription).filter_by(target_hash=notify.target_hash("webpush", body.endpoint)).first()
    if sub is not None:
        db.delete(sub)
        db.commit()
    return {"status": "unsubscribed"}


class PhoneIn(BaseModel):
    channel: Literal["whatsapp", "sms"]
    phone: str = Field(..., max_length=20)
    device_code: Optional[str] = Field(None, max_length=64)
    min_level: Literal["CRITICAL", "WARNING"] = "CRITICAL"
    language: Literal["en", "hi"] = "hi"
    label: Optional[str] = Field(None, max_length=64)


def _out(s: models.AlertSubscription) -> dict:
    tgt = notify.mask_phone(s.target) if s.channel != "webpush" else json.loads(s.target)["endpoint"][:40] + "…"
    return {"id": s.id, "channel": s.channel, "target": tgt, "device_code": s.device_code, "min_level": s.min_level,
            "language": s.language, "label": s.label, "active": s.active, "last_sent_at": s.last_sent_at,
            "last_error": s.last_error}


@router.post("/api/admin/alerts/subscriptions", tags=["Alerts"], dependencies=[Depends(require_admin)])
def add_phone(body: PhoneIn, db: Session = Depends(get_db)):
    try:
        phone = notify.norm_phone(body.phone)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    h = notify.target_hash(body.channel, phone)
    sub = db.query(models.AlertSubscription).filter_by(target_hash=h).first() or models.AlertSubscription(
        channel=body.channel, target=phone, target_hash=h)
    sub.device_code, sub.min_level, sub.language, sub.label, sub.active = (
        body.device_code, body.min_level, body.language, body.label, True)
    db.add(sub)
    db.commit()
    out = _out(sub)
    configured = notify.channels_status()[body.channel]["available"]
    out["warning"] = None if configured else f"{body.channel} is not configured on this server yet (see .env.example)."
    return out


@router.get("/api/admin/alerts/subscriptions", tags=["Alerts"], dependencies=[Depends(require_admin)])
def list_subs(db: Session = Depends(get_db)):
    return [_out(s) for s in db.query(models.AlertSubscription).order_by(models.AlertSubscription.id).all()]


@router.delete("/api/admin/alerts/subscriptions/{sub_id}", tags=["Alerts"], dependencies=[Depends(require_admin)])
def delete_sub(sub_id: int, db: Session = Depends(get_db)):
    s = db.get(models.AlertSubscription, sub_id)
    if s is None:
        raise HTTPException(status_code=404, detail="No such subscription.")
    db.delete(s)
    db.commit()
    return {"status": "deleted"}


@router.post("/api/admin/alerts/test", tags=["Alerts"], dependencies=[Depends(require_admin)])
def test_alert(device_code: Optional[str] = None):
    """Send a clearly marked test alert to every matching subscription, now (ignores the repeat timer)."""
    notify.reset_for_tests()
    return {"results": notify.deliver_alert({"classification": "Unsafe", "arsenic_ppb": 0,
                                             "device_code": device_code or "TEST", "place": "TEST MESSAGE"})}
