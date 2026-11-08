"""v5.5 backend: signed + retried alert webhooks, Prometheus metrics, trend cache and daily-median
aggregation, X-Total-Count paging, grounded offline chat, request-ID sanitising."""
import base64
import json
import threading
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app import webhooks
from app.chat_policy import offline_answer
from app.main import app
from app.trends import analyse, reduce_series


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------ webhook signing
SECRET = "whsec_" + base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()


def test_signature_round_trip_and_tamper_detection():
    body = b'{"id":"a1","arsenic_ppb":42.0}'
    ts = int(time.time())
    sig = webhooks.sign("a1", ts, body, webhooks.secret_bytes(SECRET))
    assert sig.startswith("v1,") and len(base64.b64decode(sig[3:])) == 32
    h = {"webhook-id": "a1", "webhook-timestamp": str(ts), "webhook-signature": sig}
    assert webhooks.verify(h, body, SECRET)
    assert not webhooks.verify(h, body.replace(b"42", b"4"), SECRET)              # body changed
    assert not webhooks.verify(h, body, "whsec_" + base64.b64encode(b"x" * 32).decode())  # other secret
    assert not webhooks.verify(h, body, SECRET, now=ts + 301)                     # replay outside 5 min
    # rotation: several signatures in one header, any valid one is enough
    assert webhooks.verify({**h, "webhook-signature": "v1,AAAA " + sig}, body, SECRET)
    # a secret without the whsec_ prefix is used as plain text
    assert webhooks.secret_bytes("plain-secret") == b"plain-secret"


class _Resp:
    def __init__(self, status):
        self.status = status

    def getcode(self):
        return self.status

    def close(self):
        pass


def _opener(statuses):
    calls = []

    def opener(req, timeout):
        calls.append(req)
        st = statuses[min(len(calls) - 1, len(statuses) - 1)]
        if st >= 400:
            raise urllib.error.HTTPError(req.full_url, st, "x", {}, None)
        return _Resp(st)
    return opener, calls


def test_deliver_retries_transient_errors_only():
    opener, calls = _opener([503, 502, 200])
    sleeps = []
    out = webhooks.deliver("http://example.test/hook", {"id": "r1"}, secret=SECRET, attempts=3,
                           sleep=sleeps.append, opener=opener)
    assert out["ok"] and out["attempts"] == 3 and sleeps == [1.0, 4.0]
    assert len({c.headers["Webhook-id"] for c in calls}) == 1, "retries must reuse the id so receivers de-duplicate"

    opener, calls = _opener([400])
    out = webhooks.deliver("http://example.test/hook", {"id": "r2"}, attempts=3, sleep=lambda s: None, opener=opener)
    assert not out["ok"] and out["attempts"] == 1 and len(calls) == 1      # a 400 will not get better

    assert not webhooks.deliver("file:///etc/passwd", {"id": "r3"})["ok"]
    assert not webhooks.valid_url("ftp://x") and webhooks.valid_url("https://hooks.example.org/a")


def test_alert_webhook_end_to_end_is_signed(client, monkeypatch):
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            got["headers"] = {k.lower(): v for k, v in self.headers.items()}
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    monkeypatch.setenv("ALERT_WEBHOOK_URL", f"http://127.0.0.1:{srv.server_port}/hook")
    monkeypatch.setenv("ALERT_WEBHOOK_SECRET", SECRET)
    r = client.post("/api/readings", json={"device_code": "HOOK-01", "arsenic_ppb": 180, "source_type": "hardware"})
    assert r.status_code == 200
    deadline = time.time() + 5
    while "body" not in got and time.time() < deadline:
        time.sleep(0.05)
    srv.server_close()
    assert webhooks.verify(got["headers"], got["body"], SECRET)
    alert = json.loads(got["body"])
    assert alert["device_code"] == "HOOK-01" and alert["level"] == "CRITICAL" and got["headers"]["webhook-id"] == alert["id"]
    assert client.get("/api/health").json()["diagnostics"]["alert_webhook"] == "signed"


# ------------------------------------------------------------------ metrics
def test_metrics_exposition(client):
    client.get("/api/devices/HOOK-01")
    client.get("/api/devices/NOPE-404")
    text = client.get("/api/metrics").text
    assert "# TYPE aquasentry_readings gauge" in text and "aquasentry_devices{status=\"online\"}" in text
    assert 'route="/api/devices/{device_code}"' in text, "requests are grouped by route template"
    assert "NOPE-404" not in text, "raw paths must never become label values"
    assert 'aquasentry_http_request_duration_seconds_bucket{method="GET",route="/api/devices/{device_code}",le="+Inf"}' in text
    assert "aquasentry_build_info" in text and "aquasentry_alerts_raised_total" in text
    # every sample line is "name{labels} number"
    for line in text.splitlines():
        if line and not line.startswith("#"):
            float(line.rsplit(" ", 1)[1])


def test_metrics_can_be_restricted(monkeypatch):
    from starlette.requests import Request
    monkeypatch.setenv("METRICS_PUBLIC", "0")
    req = Request({"type": "http", "client": ("10.0.0.5", 1), "headers": [], "method": "GET", "path": "/api/metrics"})
    with pytest.raises(Exception) as e:
        app_main.prometheus_metrics(req, db=None)
    assert e.value.status_code == 403


# ------------------------------------------------------------------ paging, request ids
def test_total_count_header(client):
    for i in range(3):
        client.post("/api/readings", json={"device_code": "PAGE-01", "arsenic_ppb": 5 + i})
    r = client.get("/api/readings?device_code=PAGE-01&limit=2")
    assert len(r.json()) == 2 and r.headers["x-total-count"] == "3"


def test_request_id_is_sanitised(client):
    assert client.get("/api/health", headers={"X-Request-ID": "ab<script>c"}).headers["x-request-id"] == "abscriptc"
    assert len(client.get("/api/health", headers={"X-Request-ID": "<>"}).headers["x-request-id"]) == 16


# ------------------------------------------------------------------ trends: aggregation and cache
def test_hourly_readings_are_reduced_to_daily_medians():
    t0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    pts = [(t0 + timedelta(hours=h), 25 + (h // 24) * 2 + (h % 3)) for h in range(24 * 12)]
    reduced, how = reduce_series(pts)
    assert how == "daily median" and len(reduced) == 12
    t = analyse(pts, lod=20.0)
    assert t["aggregation"] == "daily median" and t["n"] == 12 and t["readings"] == 288
    assert t["direction"] == "rising" and "daily medians of 288 readings" in t["evidence"]
    # two readings a week stay as they are
    few = [(t0 + timedelta(days=3 * i), 30.0 + i) for i in range(8)]
    assert reduce_series(few)[1] == "none"


def test_trend_cache_hits_and_invalidates(client):
    now = datetime.now(timezone.utc)
    for i, v in enumerate([22, 25, 28, 31, 34, 37, 40]):
        client.post("/api/readings", json={"device_code": "CACHE-HW", "arsenic_ppb": v, "source_type": "hardware",
                                           "recorded_at": (now - timedelta(days=(6 - i) * 4)).isoformat()})
    before = dict(app_main.TREND_STATS)
    a = client.get("/api/devices/CACHE-HW/trend").json()
    b = client.get("/api/devices/CACHE-HW/trend").json()
    assert a == b and app_main.TREND_STATS["hits"] > before["hits"]
    client.post("/api/readings", json={"device_code": "CACHE-HW", "arsenic_ppb": 44, "source_type": "hardware"})
    c = client.get("/api/devices/CACHE-HW/trend").json()
    # (two readings on the same day now, so the trend runs on daily medians: count readings, not points)
    assert c["readings"] == a["readings"] + 1, "a new reading must invalidate the cached trend"


# ------------------------------------------------------------------ grounded offline chat
def test_offline_chat_answers_from_the_database(client, monkeypatch):
    monkeypatch.setattr(app_main, "client", None)
    client.post("/api/readings", json={"device_code": "CHAT-01", "arsenic_ppb": 77.0, "source_type": "hardware"})
    r = client.post("/api/chat", json={"message": "is my water safe to drink right now?"}).json()
    assert r["grounded"] and "77.0 µg/L" in r["reply"] and "CHAT-01" in r["reply"]
    r = client.post("/api/chat", json={"message": "which sensor nodes show a rising arsenic trend?"}).json()
    assert "Trends" in r["reply"] and "CACHE-HW" in r["reply"]
    r = client.post("/api/chat", json={"message": "what is the arsenic limit in drinking water?"}).json()
    assert "10 µg/L" in r["reply"] and "20 µg/L" in r["reply"]


def test_offline_answer_with_no_data():
    assert "No readings yet" in offline_answer("latest reading?", None, [])


def test_chat_falls_back_to_offline_answer_when_gemini_fails(client, monkeypatch):
    class Boom:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise RuntimeError("Connection refused")
    monkeypatch.setattr(app_main, "client", Boom())
    r = client.post("/api/chat", json={"message": "what is the latest arsenic reading?"}).json()
    assert r["grounded"] and "could not be reached" in r["reply"] and "Latest reading" in r["reply"]


def test_low_battery_becomes_a_notice(client):
    client.post("/api/readings", json={"device_code": "BATT-01", "arsenic_ppb": 5, "source_type": "hardware", "battery_pct": 11})
    dev = client.get("/api/devices/BATT-01").json()
    assert dev["latest"]["battery_pct"] == 11
    alerts = client.get("/api/alerts/recent").json()["alerts"]
    assert any(a.get("type") == "battery" and a["device_code"] == "BATT-01" for a in alerts)


def test_single_connection_guard_for_unpatched_sqlite(monkeypatch):
    from app import database
    monkeypatch.setattr(database, "DATABASE_URL", "sqlite:////data/x.db")
    monkeypatch.setattr(database, "_sqlite_has_wal_reset_fix", lambda: False)
    monkeypatch.delenv("SQLITE_SINGLE_CONNECTION", raising=False)
    assert database._single_connection() is True          # Debian's 3.46: one connection
    monkeypatch.setenv("SQLITE_SINGLE_CONNECTION", "0")
    assert database._single_connection() is False
    monkeypatch.setattr(database, "_sqlite_has_wal_reset_fix", lambda: True)
    monkeypatch.delenv("SQLITE_SINGLE_CONNECTION")
    assert database._single_connection() is False         # patched SQLite: normal pool
    monkeypatch.setattr(database, "DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("SQLITE_SINGLE_CONNECTION", "1")
    assert database._single_connection() is False
