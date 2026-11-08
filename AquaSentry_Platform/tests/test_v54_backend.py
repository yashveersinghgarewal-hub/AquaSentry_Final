"""v5.4 backend: security headers + CSP, rate limiting, per-device keys, arsenic trend detection,
early-warning alerts, CSV export, live events (SSE), backups, request IDs and input validation."""
import base64
import csv
import hashlib
import io
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from starlette.requests import Request

from app import main as app_main
from app.main import app
from app.security import LIMITER, RateLimiter, hash_key, key_matches, new_device_key
from app.trends import analyse, mann_kendall, sens_slope

FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _req(host, headers=None):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "client": (host, 1234), "headers": raw, "method": "POST", "path": "/"})


# ------------------------------------------------------------------ headers / CSP
def test_security_headers_and_csp_allow_only_our_inline_script(client):
    r = client.get("/index.html")
    assert r.status_code == 200
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in h["content-security-policy"]
    assert "'unsafe-inline'" not in h["content-security-policy"].split("script-src")[1].split(";")[0]
    body = re.search(r"<script>(.*?)</script>", r.text, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    assert f"'sha256-{digest}'" in h["content-security-policy"], "inline theme script must be allowed by hash"
    api = client.get("/api/health")
    assert api.headers["cache-control"] == "no-store" and "x-request-id" in api.headers
    assert "server-timing" in api.headers


def test_request_id_is_echoed(client):
    assert client.get("/api/health", headers={"X-Request-ID": "abc123"}).headers["x-request-id"] == "abc123"


# ------------------------------------------------------------------ rate limiting
def test_rate_limiter_window():
    rl = RateLimiter()
    assert all(rl.check("b", "1.2.3.4", 3) is None for _ in range(3))
    wait = rl.check("b", "1.2.3.4", 3)
    assert wait is not None and wait >= 1
    assert rl.check("b", "5.6.7.8", 3) is None      # other clients are not affected


def test_rate_limit_returns_429(client, monkeypatch):
    LIMITER.reset()
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "2")
    codes = [client.post("/api/chat", json={"message": "what is the arsenic limit?"}).status_code for _ in range(3)]
    assert codes[:2] == [200, 200] and codes[2] == 429
    r = client.post("/api/chat", json={"message": "hi"})
    assert int(r.headers["retry-after"]) >= 1
    LIMITER.reset()


# ------------------------------------------------------------------ device keys
def test_key_helpers():
    k = new_device_key()
    assert k.startswith("aqs_") and len(k) > 30
    assert key_matches(k, hash_key(k)) and not key_matches(k + "x", hash_key(k)) and not key_matches(None, hash_key(k))


def test_device_key_locks_the_device(client, monkeypatch):
    out = client.post("/api/admin/devices/KEYED-01/key").json()
    key = out["api_key"]
    assert out["hint"] == key[:8]
    # no key -> refused, even from this computer, because the device has its own key
    assert client.post("/api/readings", json={"device_code": "KEYED-01", "arsenic_ppb": 5}).status_code == 401
    assert client.post("/api/readings", json={"device_code": "KEYED-01", "arsenic_ppb": 5},
                       headers={"X-API-Key": "aqs_wrong"}).status_code == 401
    ok = client.post("/api/readings", json={"device_code": "KEYED-01", "arsenic_ppb": 5}, headers={"X-API-Key": key})
    assert ok.status_code == 200
    # the key also opens the door for a LAN device when a global key is configured
    monkeypatch.setenv("AQUASENTRY_API_KEY", "global-secret")
    app_main.require_writer(_req("192.168.1.9", {"X-API-Key": key}))
    with pytest.raises(HTTPException):
        app_main.require_writer(_req("192.168.1.9", {"X-API-Key": "aqs_not_a_key"}))
    monkeypatch.delenv("AQUASENTRY_API_KEY")
    assert client.delete("/api/admin/devices/KEYED-01/key").json()["status"] == "revoked"
    assert client.post("/api/readings", json={"device_code": "KEYED-01", "arsenic_ppb": 5}).status_code == 200


def test_admin_key_endpoint_rejects_network_clients():
    with pytest.raises(Exception) as e:
        app_main.require_admin(_req("10.1.1.1"))
    assert e.value.status_code == 403


# ------------------------------------------------------------------ trend maths
def test_mann_kendall_known_values():
    mk = mann_kendall([1, 2, 3, 4, 5, 6])
    assert mk["S"] == 15 and mk["tau"] == 1.0 and mk["p_value"] < 0.01
    assert mann_kendall([3, 3, 3, 3, 3, 3])["p_value"] == 1.0
    assert sens_slope([0, 1, 2, 3], [0, 2, 4, 6]) == pytest.approx(2.0)


def _series(vals, step_days=7):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [(t0 + timedelta(days=i * step_days), v) for i, v in enumerate(vals)]


def test_trend_rising_with_projection():
    t = analyse(_series([4, 6, 9, 12, 14, 17, 18, 19]), lod=20.0)
    # all below the 20 µg/L detection limit: censored to ties, so no false trend from sensor noise
    assert t["direction"] == "no_trend"
    t = analyse(_series([22, 25, 27, 31, 33, 36, 40, 43]), lod=20.0)
    assert t["direction"] == "rising" and t["significant"]
    assert t["sen_slope_ug_per_week"] == pytest.approx(3.0, abs=0.5)
    assert t["projection"]["limit_ug_l"] == 150.0 and t["projection"]["days"] > 0


def test_trend_falling_flat_and_too_few():
    assert analyse(_series([90, 80, 75, 60, 55, 50, 41]), lod=20.0)["direction"] == "falling"
    assert analyse(_series([30, 31, 29, 30, 31, 30, 29]), lod=20.0)["direction"] == "no_trend"
    assert analyse(_series([30, 40, 50]), lod=20.0)["direction"] == "insufficient_data"


def test_trend_endpoint_and_early_warning_alert(client):
    now = datetime.now(timezone.utc)
    for i, v in enumerate([22, 26, 29, 33, 36, 40, 44, 47]):
        client.post("/api/readings", json={"device_code": "TREND-HW", "arsenic_ppb": v, "source_type": "hardware",
                                           "recorded_at": (now - timedelta(days=(7 - i) * 5)).isoformat(),
                                           "idempotency_key": f"TREND-HW-{i}"})
    t = client.get("/api/devices/TREND-HW/trend").json()
    assert t["direction"] == "rising" and t["mann_kendall"]["n"] == 8
    detail = client.get("/api/devices/TREND-HW").json()
    assert detail["trend"]["direction"] == "rising" and len(detail["recent"]) == 8
    alerts = client.get("/api/alerts/recent").json()["alerts"]
    assert any(a.get("type") == "trend" and a["device_code"] == "TREND-HW" for a in alerts)
    assert client.get("/api/devices/NO-SUCH-DEVICE").status_code == 404


# ------------------------------------------------------------------ export
def test_csv_export_is_real_csv_and_injection_safe(client):
    client.post("/api/readings", json={"device_code": "CSV-01", "arsenic_ppb": 12, "source_label": "=HYPERLINK(\"x\")"})
    r = client.get("/api/data/export?format=csv&device_code=CSV-01")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows and rows[0]["device_code"] == "CSV-01" and float(rows[0]["arsenic_ppb"]) == 12.0
    assert client.get("/api/data/export?format=xml").status_code == 422


# ------------------------------------------------------------------ live events
def test_sse_stream_delivers_new_readings(client):
    got = []

    def listen():
        with client.stream("GET", "/api/events?max_events=1") as s:
            for line in s.iter_lines():
                got.append(line)
                if line.startswith("data:"):
                    break

    th = threading.Thread(target=listen, daemon=True)
    th.start()
    deadline = time.time() + 5
    while app_main.HUB.subscriber_count == 0 and time.time() < deadline:
        time.sleep(0.05)
    client.post("/api/readings", json={"device_code": "LIVE-01", "arsenic_ppb": 33})
    th.join(timeout=10)
    assert "event: reading" in got
    assert any('"device_code": "LIVE-01"' in l for l in got)


# ------------------------------------------------------------------ backups and validation
def test_backup_creates_a_readable_copy(client, monkeypatch):
    d = tempfile.mkdtemp()
    monkeypatch.setenv("AQUASENTRY_BACKUP_DIR", d)
    out = client.post("/api/admin/backup").json()
    assert out["status"] == "success" and os.path.getsize(out["file"]) > 0
    import sqlite3
    assert sqlite3.connect(out["file"]).execute("select count(*) from readings").fetchone()[0] > 0


def test_ingest_validation(client):
    assert client.post("/api/readings", json={"device_code": "BAD CODE!", "arsenic_ppb": 5}).status_code == 422
    assert client.post("/api/readings", json={"device_code": "OK-1", "arsenic_ppb": 5, "source_type": "magic"}).status_code == 422


def test_health_reports_sqlite_and_uptime(client):
    d = client.get("/api/health").json()["diagnostics"]
    assert d["sqlite_version"] and isinstance(d["wal_reset_bug_fixed"], bool) and d["uptime_s"] >= 0
