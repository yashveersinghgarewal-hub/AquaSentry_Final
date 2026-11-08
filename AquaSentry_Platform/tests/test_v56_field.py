"""v5.6 field programme: sites, lab confirmations and validation, calibration (external standards and
standard addition), quality flags, JJM-style export, public QR pages, read protection, migrations."""
import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import field
from app.main import app
from app.routers import auth


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _post(client, code, ppb, **kw):
    body = {"device_code": code, "arsenic_ppb": ppb, "source_type": "hardware", **kw}
    r = client.post("/api/readings", json=body)
    assert r.status_code == 200, r.text
    return r.json()["reading"]


# ------------------------------------------------------------------ quality flags
def test_quality_flags_and_caveats(client):
    r = _post(client, "QC-01", 5, arsenic_species="as3_only", peak_current_ua=0.02, cu_peak_ua=1.5)
    flags = r["qc_flags"].split(",")
    assert {"as3_only", "copper_interference", "uncalibrated"} <= set(flags)
    dash = client.get("/api/dashboard/latest?device_code=QC-01").json()
    assert any("As(III)" in c for c in dash["caveats"]) and any("copper" in c for c in dash["caveats"])
    r = _post(client, "QC-02", 60, arsenic_species="total", peak_current_ua=0.06, cu_peak_ua=0.05, calibration_ref="CAL-x")
    assert r["qc_flags"] is None
    # demo data is never flagged
    r = client.post("/api/readings", json={"device_code": "QC-03", "arsenic_ppb": 5, "arsenic_species": "as3_only"}).json()
    assert r["reading"]["qc_flags"] is None


# ------------------------------------------------------------------ sites
def test_site_metadata_flows_to_devices_and_public_page(client):
    _post(client, "SITE-01", 42)
    r = client.put("/api/admin/devices/SITE-01/site", json={
        "name": "School handpump", "latitude": 25.6, "longitude": 85.1, "state": "Bihar", "district": "Bhojpur",
        "village": "Simri", "source_kind": "handpump"})
    assert r.status_code == 200 and r.json()["site"]["village"] == "Simri"
    assert client.put("/api/admin/devices/SITE-01/site", json={"source_kind": "lake"}).status_code == 422
    dev = [d for d in client.get("/api/devices").json() if d["device_code"] == "SITE-01"][0]
    assert dev["site"]["latitude"] == 25.6 and dev["site"]["source_kind"] == "handpump"
    pub = client.get("/api/public/devices/SITE-01").json()
    assert pub["name"] == "School handpump" and pub["latest"]["arsenic_ug_l"] == 42.0
    assert pub["latest"]["classification"] == "Unsafe" and "readings" not in pub


# ------------------------------------------------------------------ lab results + validation
def test_lab_results_pair_and_validation_reports_misses(client):
    now = datetime.now(timezone.utc)
    pairs = [(5, 35), (25, 30), (60, 55), (150, 140), (5, 4), (30, 6)]  # node, lab
    for i, (node, lab) in enumerate(pairs):
        t = now - timedelta(days=10 - i)
        _post(client, "LAB-01", node, recorded_at=t.isoformat())
        r = client.post("/api/lab-results", json={"device_code": "LAB-01", "arsenic_ug_l": lab, "lab_method": "ICP-MS",
                                                   "sampled_at": (t + timedelta(hours=3)).isoformat(),
                                                   "as3_ug_l": lab * 0.4, "lab_name": "District lab"})
        assert r.status_code == 200 and r.json()["node_arsenic_ug_l"] == node, r.text
    v = client.get("/api/validation?device_code=LAB-01").json()
    assert v["n_pairs"] == 6 and v["lab_above_limit"] == 4 and v["missed_unsafe"] == 1
    assert v["sensitivity"] == 0.75 and v["false_alarms"] == 1 and "missed 1 of 4" in v["message"]
    assert v["lab_as3_fraction"] == pytest.approx(0.4, abs=0.01)
    lo, hi = v["sensitivity_95ci"]
    assert lo < 0.75 < hi
    dev = [d for d in client.get("/api/devices").json() if d["device_code"] == "LAB-01"][0]
    assert dev["lab"]["arsenic_ug_l"] == 6 and dev["lab"]["above_limit"] is False
    assert client.post("/api/lab-results", json={"device_code": "LAB-01", "arsenic_ug_l": 10, "as3_ug_l": 50}).status_code == 422
    assert client.post("/api/lab-results", json={"device_code": "NOPE", "arsenic_ug_l": 10}).status_code == 404


def test_validation_stats_edge_cases():
    assert field.validation_stats([])["n_pairs"] == 0
    s = field.validation_stats([(50, 45, None), (100, 110, None), (200, 190, None)])
    assert s["missed_unsafe"] == 0 and s["sensitivity"] == 1.0 and abs(s["mean_bias_ug_l"]) < 6
    assert s["node_vs_lab_slope"] == pytest.approx(1.0, abs=0.1)


# ------------------------------------------------------------------ calibration
def test_standard_addition_recovers_the_sample_concentration():
    # true sample 30 µg/L, matrix slope 0.6 µA per mg/L (lower than the factory 0.8563), blank 0.0096
    m = 0.6 / 1000
    peaks = lambda c: 0.0096 + m * c
    fit = field.fit_standard_addition(peaks(30), [(20, peaks(50)), (40, peaks(70)), (60, peaks(90))])
    assert fit["sample_ug_l"] == pytest.approx(30, abs=0.01) and fit["slope_ua_per_mgl"] == pytest.approx(0.6, rel=1e-6)
    with pytest.raises(ValueError):
        field.fit_standard_addition(0.05, [(20, 0.04), (40, 0.03)])


def test_external_calibration_and_device_fetch(client):
    _post(client, "CAL-01", 10)
    assert client.get("/api/devices/CAL-01/calibration").json()["source"] == "factory"
    std = [{"ug_l": c, "peak_ua": 0.01 + 0.0009 * c + e} for c, e in ((0, 0.0004), (20, -0.0003), (50, 0.0002), (100, -0.0001))]
    r = client.post("/api/admin/calibrations/external", json={"device_code": "CAL-01", "standards": std, "electrode_lot": "L7"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["slope_ua_per_mgl"] == pytest.approx(0.9, abs=0.02) and out["r_squared"] > 0.99
    cal = client.get("/api/devices/CAL-01/calibration").json()
    assert cal["source"] == "device" and cal["calibration_id"] == out["calibration_id"] and cal["electrode_lot"] == "L7"
    # a newer one replaces it as the active calibration
    r2 = client.post("/api/admin/calibrations/standard-addition", json={
        "device_code": "CAL-01", "sample_peak_ua": 0.04, "additions": [{"ug_l": 20, "peak_ua": 0.058}, {"ug_l": 40, "peak_ua": 0.076}]}).json()
    assert client.get("/api/devices/CAL-01/calibration").json()["calibration_id"] == r2["calibration_id"]
    actives = [c for c in client.get("/api/calibrations?device_code=CAL-01").json() if c["active"]]
    assert len(actives) == 1
    bad = client.post("/api/admin/calibrations/external", json={"standards": [{"ug_l": 0, "peak_ua": 1}, {"ug_l": 10, "peak_ua": 0.5}, {"ug_l": 20, "peak_ua": 0.1}]})
    assert bad.status_code == 422


# ------------------------------------------------------------------ JJM export
def test_jjm_export(client):
    r = client.get("/api/data/export/jjm?device_code=SITE-01")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
    assert rows[0] == field.JJM_COLUMNS
    row = dict(zip(rows[0], rows[1]))
    assert row["State"] == "Bihar" and row["Village"] == "Simri" and row["Unit"] == "mg/L"
    assert row["Result"] == "0.042" and row["Result Status"] == "Above limit" and row["Permissible Limit"] == "0.01"
    nd = dict(zip(rows[0], list(csv.reader(io.StringIO(client.get("/api/data/export/jjm?device_code=QC-01").text.lstrip("﻿"))))[1]))
    assert nd["Result Status"].startswith("Not detected") and "As(III) only" in nd["Remarks"]


# ------------------------------------------------------------------ read protection
def _req(host, headers=None, cookies=""):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        raw.append((b"cookie", cookies.encode()))
    return Request({"type": "http", "client": (host, 1), "headers": raw, "method": "GET", "path": "/api/readings"})


def test_read_protection(client, monkeypatch):
    monkeypatch.setenv("AQUASENTRY_READ_KEY", "viewer-secret")
    assert auth.reader_allowed(_req("127.0.0.1"))                       # this computer
    assert not auth.reader_allowed(_req("192.168.1.20"))
    assert auth.reader_allowed(_req("192.168.1.20", {"X-API-Key": "viewer-secret"}))
    good = auth._sign(int(datetime.now().timestamp()) + 60, "viewer-secret")
    assert auth.reader_allowed(_req("192.168.1.20", cookies=f"{auth.COOKIE}={good}"))
    expired = auth._sign(int(datetime.now().timestamp()) - 1, "viewer-secret")
    assert not auth.reader_allowed(_req("192.168.1.20", cookies=f"{auth.COOKIE}={expired}"))
    tampered = good[:-1] + ("1" if good[-1] == "0" else "0")
    assert not auth.reader_allowed(_req("192.168.1.20", cookies=f"{auth.COOKIE}={tampered}"))
    assert client.post("/api/auth/login", json={"key": "wrong"}).status_code == 401
    ok = client.post("/api/auth/login", json={"key": "viewer-secret"})
    assert ok.status_code == 200 and auth.COOKIE in ok.cookies
    assert client.get("/api/auth/status").json()["read_protected"] is True
    assert client.get("/api/health").json()["diagnostics"]["read_auth"] == "key"


def test_read_protection_middleware_blocks_network_reads(monkeypatch):
    monkeypatch.setenv("AQUASENTRY_READ_KEY", "viewer-secret")
    with TestClient(app, client=("10.0.0.7", 5000)) as c:
        assert c.get("/api/readings").status_code == 401
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/public/devices/SITE-01").status_code == 200
        assert c.get("/api/readings", headers={"X-API-Key": "viewer-secret"}).status_code == 200
        c.post("/api/auth/login", json={"key": "viewer-secret"})
        assert c.get("/api/devices").status_code == 200                 # cookie from the sign-in


def test_health_reports_schema_revision(client):
    assert client.get("/api/health").json()["diagnostics"]["schema_revision"].startswith("0003")


def test_firmware_upload_latest_and_download(client):
    fake = bytes([0xE9]) + b"\x00" * 1000
    assert client.post("/api/admin/firmware?board=esp32&version=5.6.1", content=b"nope").status_code == 422
    assert client.post("/api/admin/firmware?board=esp8266&version=5.6.1", content=fake).status_code == 422
    up = client.post("/api/admin/firmware?board=esp32&version=5.6.1", content=fake).json()
    assert up["size"] == 1001 and len(up["md5"]) == 32
    lat = client.get("/api/firmware/latest?board=esp32&current=5.6.0").json()
    assert lat["version"] == "5.6.1" and lat["url"] == "/api/firmware/download/esp32/5.6.1"
    assert client.get("/api/firmware/latest?board=esp32&current=5.6.1").status_code == 204
    assert client.get("/api/firmware/latest?board=esp32c3&current=5.6.0").status_code == 204
    dl = client.get(lat["url"])
    assert dl.content == fake and dl.headers["x-md5"] == up["md5"]


@pytest.mark.parametrize("single", ["0", "1"])
def test_old_database_upgrades_in_both_connection_modes(single, tmp_path):
    """Docker runs single-connection (Debian's SQLite lacks the WAL-reset fix). Upgrading a v5.5
    database there once deadlocked at start-up; run the real start-up in a fresh process."""
    import os
    import shutil
    import subprocess
    import sys
    platform = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db = tmp_path / "old.db"
    shutil.copy(os.path.join(platform, "aquasentry.db"), db)
    code = ("from app.database import init_db, schema_revision; print(init_db(), schema_revision()); "
            "print(init_db(), schema_revision())")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "SQLITE_SINGLE_CONNECTION": single}
    out = subprocess.run([sys.executable, "-c", code], cwd=platform, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    lines = out.stdout.strip().splitlines()
    assert lines[0].startswith("migrated 0003") and lines[1].startswith("upgraded 0003"), lines
