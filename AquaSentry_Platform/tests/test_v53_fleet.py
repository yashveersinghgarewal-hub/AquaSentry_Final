"""v5.3: device fleet status, reading history and firmware version reporting."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _post(client, **kw):
    body = {"device_code": "FLEET-HW", "arsenic_ppb": 5.0, "source_type": "hardware"}
    body.update(kw)
    r = client.post("/api/readings", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_firmware_version_and_online_status(client):
    _post(client, firmware_version="5.3.0", idempotency_key="FLEET-HW-1")
    devs = {d["device_code"]: d for d in client.get("/api/devices").json()}
    d = devs["FLEET-HW"]
    assert d["firmware_version"] == "5.3.0"
    assert d["status"] == "online" and d["is_hardware"] is True
    assert d["latest"]["classification"] == "Below Sensor LOD"
    assert d["last_seen"].endswith("+00:00") or d["last_seen"].endswith("Z")


def test_demo_devices_are_not_reported_online(client):
    client.post("/api/readings", json={"device_code": "FLEET-SIM", "arsenic_ppb": 40.0})
    d = {x["device_code"]: x for x in client.get("/api/devices").json()}["FLEET-SIM"]
    assert d["status"] == "demo" and d["unsafe_count"] >= 1 and d["firmware_version"] is None


def test_history_is_oldest_first_and_filtered(client):
    base = datetime.now(timezone.utc) - timedelta(hours=5)
    for i, ppb in enumerate([3.0, 25.0, 60.0]):
        _post(client, device_code="FLEET-HIST", arsenic_ppb=ppb, recorded_at=(base + timedelta(hours=i)).isoformat(),
              idempotency_key=f"FLEET-HIST-{i}")
    pts = client.get("/api/readings/history?device_code=FLEET-HIST&hours=24").json()
    assert [p["ppb"] for p in pts] == [3.0, 25.0, 60.0]
    assert [p["cls"] for p in pts] == ["Below Sensor LOD", "Unsafe", "Unsafe"]
    assert client.get("/api/readings/history?device_code=FLEET-HIST&hours=1").json() == []
