"""v5.6 alert channels: subscriptions, delivery rules, repeat suppression, message text, providers."""
import json
import time
import urllib.error

import pytest
from fastapi.testclient import TestClient

from app import notify
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fake_senders():
    sent = []

    def fake(target, msg, lang, alert):
        sent.append((target, msg, lang, alert))
        return True, None, False
    notify.reset_for_tests()
    for ch in ("webpush", "whatsapp", "sms"):
        notify.SENDERS[ch] = fake
    yield sent
    notify.SENDERS.clear()


SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc123", "keys": {"p256dh": "BOr" + "x" * 80, "auth": "y" * 22}}


def _wait(cond, t=5):
    end = time.time() + t
    while not cond() and time.time() < end:
        time.sleep(0.05)


def test_channels_and_vapid_key(client):
    ch = client.get("/api/alerts/channels").json()
    assert ch["webpush"]["available"] and len(ch["webpush"]["public_key"]) > 80   # 65-byte P-256 point, base64url
    assert ch["whatsapp"]["available"] is False and ch["sms"]["available"] is False


def test_subscriptions_and_delivery_rules(client, fake_senders):
    assert client.post("/api/alerts/subscribe/webpush", json={"subscription": SUB}).json()["status"] == "subscribed"
    r = client.post("/api/admin/alerts/subscriptions", json={"channel": "whatsapp", "phone": "98765 43210", "language": "hi",
                                                             "device_code": "ALRT-01", "label": "Panchayat office"}).json()
    assert r["target"].startswith("9198") and "•" in r["target"] and "not configured" in r["warning"]
    assert client.post("/api/admin/alerts/subscriptions", json={"channel": "sms", "phone": "12"}).status_code == 422
    # demo readings never notify anyone
    client.post("/api/readings", json={"device_code": "ALRT-01", "arsenic_ppb": 300})
    time.sleep(0.3)
    assert fake_senders == []
    # a real unsafe reading reaches both (the WhatsApp one is limited to ALRT-01, in Hindi)
    client.post("/api/readings", json={"device_code": "ALRT-01", "arsenic_ppb": 80, "source_type": "hardware"})
    _wait(lambda: len(fake_senders) >= 2)
    assert len(fake_senders) == 2
    wa = [s for s in fake_senders if s[0].startswith("91")][0]
    assert wa[2] == "hi" and "असुरक्षित" in wa[1]["body"] and "80" in wa[1]["body"]
    # within the repeat window the same level is not sent again ...
    client.post("/api/readings", json={"device_code": "ALRT-01", "arsenic_ppb": 90, "source_type": "hardware"})
    time.sleep(0.4)
    assert len(fake_senders) == 2 and notify.STATS["suppressed"] >= 2
    # ... and another node only reaches the all-nodes push subscriber
    client.post("/api/readings", json={"device_code": "ALRT-02", "arsenic_ppb": 60, "source_type": "hardware"})
    _wait(lambda: len(fake_senders) >= 3)
    assert len(fake_senders) == 3 and fake_senders[-1][0].startswith("{")
    subs = client.get("/api/admin/alerts/subscriptions").json()
    assert {s["channel"] for s in subs} >= {"webpush", "whatsapp"}
    assert client.post("/api/alerts/unsubscribe/webpush", json={"endpoint": SUB["endpoint"]}).json()["status"] == "unsubscribed"


def test_gone_push_subscription_is_switched_off(client):
    notify.reset_for_tests()
    notify.SENDERS["webpush"] = lambda *a: (False, "push service 410", True)
    try:
        sub = {**SUB, "endpoint": "https://fcm.googleapis.com/fcm/send/gone"}
        client.post("/api/alerts/subscribe/webpush", json={"subscription": sub})
        res = notify.deliver_alert({"level": "CRITICAL", "device_code": "X", "arsenic_ppb": 50})
        assert any(r["error"] == "push service 410" for r in res)
        subs = client.get("/api/admin/alerts/subscriptions").json()
        assert [s for s in subs if "gone" in s["target"]][0]["active"] is False
    finally:
        notify.SENDERS.clear()


def test_message_text():
    m = notify.compose({"level": "CRITICAL", "classification": "Hazardous", "arsenic_ppb": 212.4, "place": "School handpump"})
    assert "212" in m["body"] and "HAZARDOUS" in m["body"] and "10 µg/L" in m["body"]
    assert len(notify.compose({"arsenic_ppb": 50, "device_code": "N1"}, "hi")["body"]) < 300


def test_whatsapp_and_sms_request_shapes(monkeypatch):
    calls = []

    class R:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def opener(req, timeout):
        calls.append(req)
        return R()
    monkeypatch.setenv("WHATSAPP_TOKEN", "t")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setenv("WHATSAPP_TEMPLATE", "arsenic_alert")
    msg = notify.compose({"arsenic_ppb": 55, "place": "Well 4"})
    assert notify.send_whatsapp("919876543210", msg, "hi", opener=opener)[0]
    body = json.loads(calls[-1].data)
    assert calls[-1].full_url.endswith("/123/messages") and body["template"]["language"]["code"] == "hi"
    assert [p["text"] for p in body["template"]["components"][0]["parameters"]][:2] == ["Well 4", "55"]
    monkeypatch.setenv("SMS_PROVIDER", "msg91")
    monkeypatch.setenv("MSG91_AUTHKEY", "k")
    monkeypatch.setenv("MSG91_TEMPLATE_ID", "tpl")
    assert notify.send_sms("919876543210", msg, opener=opener)[0]
    b = json.loads(calls[-1].data)
    assert b["template_id"] == "tpl" and b["recipients"][0]["mobiles"] == "919876543210" and calls[-1].headers["Authkey"] == "k"

    def failing(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "x", {}, None)
    ok, err, _ = notify.send_sms("919876543210", msg, opener=failing)
    assert not ok and "401" in err


def test_phone_normalisation():
    assert notify.norm_phone("+91 98765-43210") == "919876543210"
    assert notify.norm_phone("9876543210") == "919876543210"
    with pytest.raises(ValueError):
        notify.norm_phone("12345")
