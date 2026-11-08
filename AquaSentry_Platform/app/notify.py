"""
Alert channels (v5.6): browser / phone push, WhatsApp and SMS, on top of the signed webhook.

Every channel is off until it is configured, and a broken channel never blocks a reading upload:
deliveries run on a background thread, failures are logged and stored on the subscription.

Web Push   VAPID keys from VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY, or generated once and kept next to the
           database (vapid_private.pem). Works on Android / desktop browsers, and on iPhone (iOS 16.4+) once
           the dashboard is added to the Home Screen. Subscriptions that the push service reports as gone
           (404 / 410) are switched off.
WhatsApp   Meta WhatsApp Cloud API with an approved *utility* template (WHATSAPP_TOKEN,
           WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TEMPLATE). The template body takes four parameters:
           {{1}} place, {{2}} arsenic µg/L, {{3}} verdict, {{4}} what to do. About ₹0.145 per message (2026).
SMS        MSG91 flow (India; the template must be registered on DLT, as TRAI requires for business SMS)
           with VAR1..VAR4 as above, or Twilio (SMS_PROVIDER=twilio) with a plain text body.

Repeats: one message per subscription per node per ALERT_REPEAT_MIN (default 360 min) unless the level
rises, so an hourly node in a contaminated area does not send 24 messages a day.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from .logs import get_logger

log = get_logger("notify")

# Subscription levels: CRITICAL = every Unsafe / Hazardous reading; WARNING = those plus rising trends.
# (The reading alerts themselves say WARNING for Unsafe and CRITICAL for Hazardous; both count as 2 here.)
LEVELS = {"WARNING": 1, "CRITICAL": 2}


def alert_rank(alert: Dict[str, Any]) -> int:
    if alert.get("type") == "trend":
        return 1
    return 3 if alert.get("classification") == "Hazardous" else 2
STATS = {"sent": 0, "failed": 0, "suppressed": 0}
_LAST: Dict[Tuple[int, str], Tuple[float, int]] = {}
_LOCK = threading.Lock()
PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


def norm_phone(p: str) -> str:
    p = re.sub(r"[\s\-()]", "", p or "")
    if re.fullmatch(r"[6-9]\d{9}", p):          # a 10-digit Indian mobile number
        p = "91" + p
    p = p.lstrip("+")
    if not PHONE_RE.match(p):
        raise ValueError("Enter the number with its country code, e.g. 91 98765 43210.")
    return p


def mask_phone(p: str) -> str:
    return p[:4] + "•" * max(0, len(p) - 6) + p[-2:]


def target_hash(channel: str, target: str) -> str:
    return hashlib.sha256(f"{channel}:{target}".encode()).hexdigest()


# ---------------------------------------------------------------------------- message text
TEXT = {
    "en": {"CRITICAL": "UNSAFE, do not drink", "HAZARDOUS": "HAZARDOUS, do not drink or cook with it",
           "WARNING": "arsenic is rising", "do": "Use another safe source and ask for a lab test.",
           "fmt": "AquaSentry: arsenic {v} µg/L at {place}: {verdict}. Legal limit 10 µg/L. {do}"},
    "hi": {"CRITICAL": "असुरक्षित, यह पानी न पिएँ", "HAZARDOUS": "बहुत खतरनाक, न पिएँ न खाना बनाएँ",
           "WARNING": "आर्सेनिक बढ़ रहा है", "do": "दूसरे सुरक्षित स्रोत का पानी लें और लैब जाँच करवाएँ।",
           "fmt": "AquaSentry: {place} पर आर्सेनिक {v} µg/L: {verdict}। सीमा 10 µg/L। {do}"},
}


def compose(alert: Dict[str, Any], lang: str = "en") -> Dict[str, str]:
    t = TEXT.get(lang, TEXT["en"])
    place = alert.get("place") or alert.get("device_code") or "a sensor"
    key = "HAZARDOUS" if alert.get("classification") == "Hazardous" else ("WARNING" if alert.get("type") == "trend" else "CRITICAL")
    verdict = t.get(key, t["CRITICAL"])
    v = alert.get("arsenic_ppb")
    v = f"{v:.0f}" if isinstance(v, (int, float)) else "?"
    if alert.get("type") == "trend":
        body = f"AquaSentry: {place}: {alert.get('message', verdict)}"
    else:
        body = t["fmt"].format(v=v, place=place, verdict=verdict, do=t["do"])
    return {"title": f"AquaSentry · {place}", "body": body, "place": place, "value": v, "verdict": verdict, "do": t["do"]}


# ---------------------------------------------------------------------------- web push
_VAPID = None


def _vapid_path() -> str:
    from .database import DATABASE_URL, _PLATFORM_DIR
    base = os.getenv("AQUASENTRY_DATA_DIR")
    if not base and DATABASE_URL.startswith("sqlite:///"):
        base = os.path.dirname(DATABASE_URL[len("sqlite:///"):]) or _PLATFORM_DIR
    return os.path.join(base or _PLATFORM_DIR, "vapid_private.pem")


def vapid():
    """(Vapid object, public key as base64url) or (None, None) if pywebpush is not installed."""
    global _VAPID
    if _VAPID is not None:
        return _VAPID
    try:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from py_vapid import Vapid01
    except ImportError:
        _VAPID = (None, None)
        return _VAPID
    pem = os.getenv("VAPID_PRIVATE_KEY")
    if pem:
        pem = pem.replace("\\n", "\n")
        v = Vapid01.from_pem(pem.encode()) if "BEGIN" in pem else Vapid01.from_string(private_key=pem)
    else:
        path = _vapid_path()
        if os.path.exists(path):
            v = Vapid01.from_file(path)
        else:
            v = Vapid01()
            v.generate_keys()
            try:
                v.save_key(path)
                os.chmod(path, 0o600)
                log.info("Generated web-push (VAPID) keys in %s", path)
            except OSError as e:
                log.warning("Could not save VAPID key (%s); push subscriptions will not survive a restart.", e)
    raw = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    _VAPID = (v, base64.urlsafe_b64encode(raw).decode().rstrip("="))
    return _VAPID


def send_webpush(target: str, msg: Dict[str, str], alert: Dict[str, Any]) -> Tuple[bool, Optional[str], bool]:
    """(ok, error, gone). gone = the push service says this subscription no longer exists."""
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return False, "pywebpush is not installed", False
    v, _ = vapid()
    payload = json.dumps({"title": msg["title"], "body": msg["body"], "tag": f"aqs-{alert.get('device_code')}",
                          "url": f"/device.html?code={urllib.parse.quote(str(alert.get('device_code') or ''))}"})
    try:
        webpush(json.loads(target), payload, vapid_private_key=v,
                vapid_claims={"sub": os.getenv("VAPID_SUBJECT", "mailto:alerts@aquasentry.local")}, ttl=6 * 3600, timeout=10)
        return True, None, False
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        return False, f"push service {code}", code in (404, 410)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", False


# ---------------------------------------------------------------------------- WhatsApp / SMS
def _post_json(url: str, body: Dict, headers: Dict[str, str], opener=urllib.request.urlopen) -> Tuple[bool, Optional[str]]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers},
                                 method="POST")
    try:
        with opener(req, timeout=10) as r:
            return 200 <= r.status < 300, None
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode("utf-8", "replace") if hasattr(e, "read") else ""
        return False, f"HTTP {e.code} {detail}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def whatsapp_configured() -> bool:
    return all(os.getenv(k) for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_TEMPLATE"))


def send_whatsapp(phone: str, msg: Dict[str, str], lang: str, opener=urllib.request.urlopen) -> Tuple[bool, Optional[str], bool]:
    if not whatsapp_configured():
        return False, "WhatsApp is not configured", False
    ver = os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0")
    url = f"https://graph.facebook.com/{ver}/{os.getenv('WHATSAPP_PHONE_NUMBER_ID')}/messages"
    body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": phone, "type": "template",
            "template": {"name": os.getenv("WHATSAPP_TEMPLATE"), "language": {"code": lang if lang in ("en", "hi") else "en"},
                         "components": [{"type": "body", "parameters": [
                             {"type": "text", "text": msg["place"][:60]}, {"type": "text", "text": msg["value"]},
                             {"type": "text", "text": msg["verdict"]}, {"type": "text", "text": msg["do"]}]}]}}
    ok, err = _post_json(url, body, {"Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}"}, opener)
    return ok, err, False


def sms_provider() -> Optional[str]:
    p = (os.getenv("SMS_PROVIDER") or "").lower()
    if p == "msg91" and os.getenv("MSG91_AUTHKEY") and os.getenv("MSG91_TEMPLATE_ID"):
        return "msg91"
    if p == "twilio" and all(os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")):
        return "twilio"
    return None


def send_sms(phone: str, msg: Dict[str, str], opener=urllib.request.urlopen) -> Tuple[bool, Optional[str], bool]:
    prov = sms_provider()
    if prov == "msg91":
        body = {"template_id": os.getenv("MSG91_TEMPLATE_ID"), "flow_id": os.getenv("MSG91_TEMPLATE_ID"),
                "sender": os.getenv("MSG91_SENDER", "AQUSEN"), "short_url": "0",
                "recipients": [{"mobiles": phone, "VAR1": msg["place"][:30], "VAR2": msg["value"],
                                "VAR3": msg["verdict"][:30], "VAR4": msg["do"][:60]}]}
        ok, err = _post_json(os.getenv("MSG91_URL", "https://control.msg91.com/api/v5/flow"), body,
                             {"authkey": os.getenv("MSG91_AUTHKEY")}, opener)
        return ok, err, False
    if prov == "twilio":
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        data = urllib.parse.urlencode({"To": "+" + phone, "From": os.getenv("TWILIO_FROM"), "Body": msg["body"][:600]}).encode()
        auth = base64.b64encode(f"{sid}:{os.getenv('TWILIO_AUTH_TOKEN')}".encode()).decode()
        req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data,
                                     headers={"Authorization": f"Basic {auth}"}, method="POST")
        try:
            with opener(req, timeout=10) as r:
                return 200 <= r.status < 300, None, False
        except Exception as e:
            return False, f"{type(e).__name__}: {e}", False
    return False, "SMS is not configured", False


def channels_status() -> Dict[str, Any]:
    _, pub = vapid()
    return {"webpush": {"available": pub is not None, "public_key": pub},
            "whatsapp": {"available": whatsapp_configured()},
            "sms": {"available": sms_provider() is not None, "provider": sms_provider()}}


# ---------------------------------------------------------------------------- dispatch
SENDERS: Dict[str, Callable] = {}


def _send(channel: str, target: str, msg: Dict[str, str], lang: str, alert: Dict[str, Any]):
    if channel in SENDERS:                       # tests plug fakes in here
        return SENDERS[channel](target, msg, lang, alert)
    if channel == "webpush":
        return send_webpush(target, msg, alert)
    if channel == "whatsapp":
        return send_whatsapp(target, msg, lang)
    if channel == "sms":
        return send_sms(target, msg)
    return False, f"unknown channel {channel}", False


def _due(sub_id: int, device: str, level: int, now: float) -> bool:
    gap = float(os.getenv("ALERT_REPEAT_MIN", "360")) * 60
    with _LOCK:
        prev = _LAST.get((sub_id, device))
        if prev and now - prev[0] < gap and level <= prev[1]:
            return False
        _LAST[(sub_id, device)] = (now, level)
        return True


def deliver_alert(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Send one alert to every matching subscription. Returns one result per subscription tried."""
    from . import models
    from .database import SessionLocal
    level = alert_rank(alert)
    device = alert.get("device_code") or ""
    results = []
    with SessionLocal() as db:
        dev = db.query(models.Device).filter_by(device_code=device).first() if device else None
        if dev is not None:
            alert = {**alert, "place": dev.name or dev.village or dev.location_label or device}
        subs = db.query(models.AlertSubscription).filter(models.AlertSubscription.active.is_(True)).all()
        now = time.time()
        for s in subs:
            if s.device_code and s.device_code != device:
                continue
            if level < LEVELS.get(s.min_level or "CRITICAL", 2):      # a trend (1) only reaches WARNING subscribers
                continue
            if not _due(s.id, device, level, now):
                STATS["suppressed"] += 1
                continue
            ok, err, gone = _send(s.channel, s.target, compose(alert, s.language or "en"), s.language or "en", alert)
            if ok:
                STATS["sent"] += 1
                s.last_sent_at, s.last_error, s.failures = __import__("datetime").datetime.now(), None, 0
            else:
                STATS["failed"] += 1
                s.last_error, s.failures = (err or "failed")[:255], (s.failures or 0) + 1
                if gone or (s.failures or 0) >= 10:
                    s.active = False
                log.warning("Alert via %s failed: %s", s.channel, err, extra={"event": "notify_failed", "device_code": device})
            results.append({"id": s.id, "channel": s.channel, "ok": ok, "error": err})
        db.commit()
    return results


def deliver_in_background(alert: Dict[str, Any]) -> threading.Thread:
    th = threading.Thread(target=deliver_alert, args=(alert,), daemon=True)
    th.start()
    return th


def reset_for_tests():
    with _LOCK:
        _LAST.clear()
    for k in STATS:
        STATS[k] = 0
