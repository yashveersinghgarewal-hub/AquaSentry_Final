"""
Regression tests for the v5.2 audit fixes.

1. India's IS 10500 arsenic limit is 10 µg/L with no relaxation (Amendment No. 1, 2015), not 50 µg/L.
2. Real zero readings (0 NTU, 0 °C, 0 µS/cm) are not swapped for default values.
3. CSV / JSON import detects columns by whole words and keeps units, zeros and sample times.
4. Write and admin endpoints honour AQUASENTRY_API_KEY.
5. API timestamps are explicit UTC; alerts come from the database and cover every Unsafe verdict.
6. The four copies of the AquaNet-V3 safety rules (server, Neural_Network, browser, ESP32) agree.
7. The firmware's upload JSON is valid and carries the real sample time.
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from starlette.requests import Request

from app import main as app_main
from app.main import app, _val, detect_columns, require_writer, require_admin
from app.aquanet_v3 import predict
from app.classification import classify_arsenic_neural
from app.standards import BIS_PERMISSIBLE_LIMIT_UG_L, WHO_GUIDELINE_UG_L, evaluate_measurement

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PLATFORM)
FW = os.path.join(ROOT, "Firmware", "esp32_firmware")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _request(host: str, headers=None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "client": (host, 5555), "headers": raw, "method": "POST", "path": "/"})


# ---------------------------------------------------------------- 1. standards
class TestAmendedArsenicLimit:
    def test_bis_limit_is_10(self):
        assert BIS_PERMISSIBLE_LIMIT_UG_L == 10.0 == WHO_GUIDELINE_UG_L

    @pytest.mark.parametrize("ppb", [20.0, 25.0, 35.0, 49.9, 50.0, 120.0])
    def test_detected_arsenic_is_unsafe_everywhere(self, ppb):
        assert evaluate_measurement(ppb).severity >= 2
        res = classify_arsenic_neural(ppb, 7.2, 400, 2, 24)
        assert res.label in ("Unsafe", "Hazardous") and res.is_safe_to_drink is False
        assert "permissible" not in res.message.lower()
        assert predict(ppb / 1000, 7.2, 400, 2, 24)["predicted_class"] in ("Unsafe", "Hazardous")

    def test_between_limit_and_lod_is_caution(self):
        r = predict(0.015, 7.2, 400, 2, 24)
        assert r["predicted_class"] == "Caution"
        # even when the network itself votes Safe, the rule lifts 10-20 µg/L to Caution
        from app.aquanet_v3 import apply_rules
        final, reasons, _ = apply_rules("Safe", [0.015, 7.2, 400, 2, 24], 0.1)
        assert final == "Caution" and "POTABILITY_ADVISORY_ARSENIC_ABOVE_WHO" in reasons

    def test_api_35_ppb_unsafe_and_alerts(self, client):
        r = client.post("/api/readings", json={"device_code": "REG-35", "arsenic_ppb": 35.0, "ph": 7.2})
        assert r.status_code == 200
        body = r.json()
        assert body["label"] == "Unsafe" and body["is_safe_to_drink"] is False
        assert "Exceeds" in body["regulatory_tier"]
        alerts = client.get("/api/alerts/recent").json()["alerts"]
        assert any(a["reading_id"] == body["reading"]["id"] for a in alerts)

    def test_pdf_uses_amended_limit(self, client):
        rid = client.post("/api/readings", json={"device_code": "REG-PDF", "arsenic_ppb": 30.0}).json()["reading"]["id"]
        r = client.get(f"/api/reports/certificate/pdf?reading_id={rid}")
        assert r.status_code == 200 and r.content[:4] == b"%PDF"


# ---------------------------------------------------------------- 2. zeros
class TestZeroValues:
    def test_val_keeps_zero(self):
        assert _val(0.0, 2.0) == 0.0 and _val(None, 2.0) == 2.0

    def test_zero_readings_are_stored_as_zero(self, client):
        r = client.post("/api/readings", json={"device_code": "REG-ZERO", "arsenic_ppb": 0.0, "turbidity_ntu": 0.0,
                                               "temperature_c": 0.0, "conductivity_us_cm": 0.0, "ph": 7.0})
        assert r.status_code == 200
        rd = r.json()["reading"]
        assert rd["turbidity_ntu"] == 0.0 and rd["temperature_c"] == 0.0 and rd["conductivity_us_cm"] == 0.0

    def test_neural_post_accepts_zero_arsenic(self, client):
        r = client.post("/api/neural/inference", json={"arsenic_mg_l": 0.0, "arsenic_ppb": 300.0})
        assert r.status_code == 200
        assert r.json()["predicted_class"] != "Hazardous"   # used to fall through to arsenic_ppb


# ---------------------------------------------------------------- 3. import
class TestImportColumns:
    def test_words_not_substrings(self):
        m = detect_columns(["class", "measured_at", "basin", "phosphate_mg_l", "recorded_at", "As (µg/L)", "pH", "EC"])
        assert m.get("arsenic_ppb") == "As (µg/L)"
        assert m.get("ph") == "pH"
        assert m.get("conductivity_us_cm") == "EC"
        assert "class" not in m.values() and "basin" not in m.values() and "phosphate_mg_l" not in m.values()
        assert m.get("recorded_at") == "recorded_at"

    def test_commit_units_zero_and_time(self, client):
        recs = [
            {"sample_id": "IMP-A", "arsenic_mg_l": 0.035, "recorded_at": "2026-03-01T10:00:00+05:30", "turbidity_ntu": 0},
            {"sample_id": "IMP-B", "arsenic_ppb": 0, "ph": 7.1},
        ]
        r = client.post("/api/data/import/commit", json={"records": recs, "device_code": "REG-IMP"})
        assert r.json()["inserted_count"] == 2, r.json()
        rows = {x["sample_id"]: x for x in client.get("/api/data/export").json()["records"] if x["sample_id"].startswith("IMP-")}
        assert rows["IMP-A"]["arsenic_ppb"] == pytest.approx(35.0)
        assert rows["IMP-A"]["classification"] == "Unsafe"
        assert rows["IMP-A"]["recorded_at"].startswith("2026-03-01T04:30")
        assert rows["IMP-A"]["turbidity_ntu"] == 0.0
        assert rows["IMP-B"]["arsenic_ppb"] == 0.0

    def test_bare_arsenic_in_mg_l_is_converted(self, client):
        recs = [{"sample_id": "IMP-C", "arsenic": 0.06}, {"sample_id": "IMP-D", "arsenic": 0.004}]
        prev = client.post("/api/data/import/preview", json=recs).json()
        assert prev["column_mapping"]["arsenic_unit"] == "mg/L"
        client.post("/api/data/import/commit", json={"records": recs})
        rows = {x["sample_id"]: x for x in client.get("/api/data/export").json()["records"]}
        assert rows["IMP-C"]["arsenic_ppb"] == pytest.approx(60.0)

    def test_duplicate_ids_in_same_file(self, client):
        recs = [{"sample_id": "IMP-DUP", "arsenic_ppb": 5}, {"sample_id": "IMP-DUP", "arsenic_ppb": 6}]
        out = client.post("/api/data/import/commit", json={"records": recs}).json()
        assert out["inserted_count"] == 1 and out["duplicate_count"] == 1


# ---------------------------------------------------------------- 4. auth
class TestWriteProtection:
    def test_lan_writes_closed_without_key(self, monkeypatch):
        # v5.7: with no key configured, only this computer can write (was: the whole network)
        monkeypatch.delenv("AQUASENTRY_API_KEY", raising=False)
        monkeypatch.delenv("AQUASENTRY_OPEN_WRITES", raising=False)
        with pytest.raises(HTTPException) as e:
            require_writer(_request("192.168.1.50"))
        assert e.value.status_code == 401
        require_writer(_request("127.0.0.1"))

    def test_open_writes_opt_in(self, monkeypatch):
        monkeypatch.delenv("AQUASENTRY_API_KEY", raising=False)
        monkeypatch.setenv("AQUASENTRY_OPEN_WRITES", "1")
        require_writer(_request("192.168.1.50"))   # explicit opt-in for a closed test network

    def test_key_required_for_lan_device(self, monkeypatch):
        monkeypatch.setenv("AQUASENTRY_API_KEY", "s3cret-key")
        with pytest.raises(Exception) as e:
            require_writer(_request("192.168.1.50"))
        assert getattr(e.value, "status_code", None) == 401
        with pytest.raises(HTTPException):
            require_writer(_request("192.168.1.50", {"X-API-Key": "wrong"}))
        require_writer(_request("192.168.1.50", {"X-API-Key": "s3cret-key"}))
        require_writer(_request("127.0.0.1"))     # the dashboard on this computer still works
        require_writer(_request("::1"))

    def test_admin_never_open_to_network(self, monkeypatch):
        monkeypatch.delenv("AQUASENTRY_API_KEY", raising=False)
        with pytest.raises(Exception) as e:
            require_admin(_request("10.0.0.7"))
        assert getattr(e.value, "status_code", None) == 403
        require_admin(_request("127.0.0.1"))

    def test_health_reports_auth_and_model(self, client):
        d = client.get("/api/health").json()["diagnostics"]
        assert d["write_auth"] in ("open", "api_key")
        assert d["model_version"] == "AquaNet-V3"
        assert "2015" in d["standards_version"]


# ---------------------------------------------------------------- 5. time + dashboard
class TestTimestamps:
    def test_reading_times_are_utc(self, client):
        rd = client.post("/api/readings", json={"device_code": "REG-TZ", "arsenic_ppb": 5,
                                                "recorded_at": "2026-05-01T12:00:00+05:30"}).json()["reading"]
        assert rd["recorded_at"].endswith("+00:00") or rd["recorded_at"].endswith("Z")
        assert rd["recorded_at"].startswith("2026-05-01T06:30")

    def test_future_device_clock_ignored(self, client):
        rd = client.post("/api/readings", json={"device_code": "REG-TZ2", "arsenic_ppb": 5,
                                                "recorded_at": "2099-01-01T00:00:00Z"}).json()["reading"]
        assert not rd["recorded_at"].startswith("2099")

    def test_dashboard_unsafe_with_other_devices(self, client):
        client.post("/api/readings", json={"device_code": "REG-D1", "arsenic_ppb": 90})
        client.post("/api/readings", json={"device_code": "REG-D2", "arsenic_ppb": 95})
        d = client.get("/api/dashboard/latest").json()
        assert d["classification"] == "Unsafe" and d["confirmedByHomes"] >= 1
        assert d["detectedAtIso"] and d["detectedAt"].endswith("UTC")

    def test_websocket_rejects_bad_input(self, client):
        with client.websocket_connect("/ws/voltammetry") as ws:
            ws.send_json({"command": "simulate", "arsenic_mg_l": "lots"})
            assert ws.receive_json()["type"] == "error"
            ws.send_json({"command": "ping"})
            assert ws.receive_json()["type"] == "pong"


# ---------------------------------------------------------------- 6. rule parity across engines
def _cases(n=4000, seed=11):
    rng = random.Random(seed)
    edges = {0: [0.010, 0.020, 0.150], 1: [6.0, 6.5, 8.5, 9.0], 2: [1500, 2000], 3: [5, 10]}
    out = []
    for i in range(n):
        r = [math.exp(rng.uniform(math.log(0.0005), math.log(0.5))), rng.uniform(4.6, 10.4),
             math.exp(rng.uniform(math.log(60), math.log(4900))), math.exp(rng.uniform(math.log(0.05), math.log(90))),
             rng.uniform(6, 44)]
        if i % 2:
            f = rng.randrange(4)
            r[f] = rng.choice(edges[f]) * (1 + rng.uniform(-0.03, 0.03))
        out.append([round(v, 6) for v in r])
    return out


def _near_edge(r):
    a, ph, ec, tu, _ = r
    return (min(abs(a - e) for e in (0.010, 0.020, 0.150)) < 1e-6 or min(abs(ph - e) for e in (6.0, 6.5, 8.5, 9.0)) < 1e-6
            or min(abs(ec - e) for e in (1500, 2000)) < 1e-3 or min(abs(tu - e) for e in (5, 10)) < 1e-6)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_engine_matches_server():
    cases = _cases()
    js = os.path.join(PLATFORM, "frontend", "neural.js")
    harness = ("global.window = {}; global.document = undefined;"
               f"require({json.dumps(js)});"
               "const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
               "console.log(JSON.stringify(cases.map(c => window.AquaNet.evaluate(c[0], c[1], c[2], c[3], c[4], 'v3').final)));")
    out = subprocess.run(["node", "-e", harness], input=json.dumps(cases), capture_output=True, text=True, check=True)
    got = json.loads(out.stdout)
    bad = [(c, g, predict(*c)["predicted_class"]) for c, g in zip(cases, got)
           if not _near_edge(c) and g != predict(*c)["predicted_class"]]
    assert not bad, bad[:5]


def test_neural_network_copy_matches_server():
    import importlib.util
    spec = importlib.util.spec_from_file_location("nn_v3", os.path.join(ROOT, "Neural_Network", "aquanet_v3.py"))
    nn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nn)
    for c in _cases(1500, 3):
        assert nn.predict(*c)["predicted_class"] == predict(*c)["predicted_class"], c


@pytest.mark.skipif(shutil.which("gcc") is None and shutil.which("cc") is None, reason="no C compiler")
def test_firmware_c_engine_matches_server():
    cc = shutil.which("gcc") or shutil.which("cc")
    work = tempfile.mkdtemp()
    main_c = os.path.join(work, "m.c")
    open(main_c, "w").write(
        '#include <stdio.h>\n#include "aquanet_v3.h"\n'
        'int main(void){float a,p,e,t,T; while(scanf("%f %f %f %f %f",&a,&p,&e,&t,&T)==5){'
        'aquanet_result_t r=aquanet_v3_predict(a,p,e,t,T); printf("%d\\n",(int)r.predicted_class);} return 0;}\n')
    exe = os.path.join(work, "m")
    subprocess.run([cc, "-std=c99", "-O1", "-I", FW, main_c, os.path.join(FW, "aquanet_v3.c"),
                    os.path.join(FW, "aquanet_v1.c"), "-lm", "-o", exe], check=True)
    cases = _cases(3000, 7)
    out = subprocess.run([exe], input="\n".join(" ".join(map(str, c)) for c in cases),
                         capture_output=True, text=True, check=True).stdout.split()
    names = ["Safe", "Caution", "Unsafe", "Hazardous"]
    bad = [(c, names[int(g)], predict(*c)["predicted_class"]) for c, g in zip(cases, out)
           if not _near_edge(c) and names[int(g)] != predict(*c)["predicted_class"]]
    assert len(bad) <= 3, bad[:5]   # float32 vs float64 may flip a vote that sits on a 50/50 split


# ---------------------------------------------------------------- 7. firmware upload JSON
@pytest.mark.skipif(shutil.which("g++") is None, reason="no C++ compiler")
def test_firmware_upload_json_is_valid():
    src = open(os.path.join(FW, "esp32_firmware.ino"), encoding="utf-8").read()
    types = open(os.path.join(FW, "aquasentry_types.h"), encoding="utf-8").read()
    struct = re.search(r"typedef struct \{\n    float arsenic_mg_l;.*?\} sensor_reading_t;", types, re.S).group(0)
    utc = re.search(r"uint32_t utc_now_or_zero\(\) \{.*?\n\}\n", src, re.S).group(0)
    build = re.search(r"int build_reading_json\(.*?\n\}\n", src, re.S).group(0)
    work = tempfile.mkdtemp()
    cpp = os.path.join(work, "j.cpp")
    open(cpp, "w").write(
        "#include <cstdio>\n#include <cstdint>\n#include <math.h>\n#include <ctime>\n#include <cstddef>\nusing std::isnan;\n"
        'const char* DEVICE_CODE = "TANK-001";\n#define FIRMWARE_VERSION "9.9.9"\n'
        'char cal_id[48] = "CAL-20261108-abc123";\nvolatile uint16_t cal_tag_now = 777;\n' + struct + "\n" + utc + "\n" + build +
        "int main(){ sensor_reading_t r = {}; r.arsenic_mg_l = 0.0351f; r.ph = NAN; r.conductivity_us_cm = 512.0f;"
        " r.turbidity_ntu = 0.0f; r.temperature_c = NAN; r.seq = 42; r.cu_peak_ua = NAN; r.peak_current_ua = 0.04f;"
        " r.arsenic_species = 1; r.cal_tag = 777;"
        " char out[640]; r.timestamp_unix = 1793000000u; build_reading_json(&r, out, sizeof out); puts(out);"
        " r.timestamp_unix = 3600u; build_reading_json(&r, out, sizeof out); puts(out); return 0; }\n")
    exe = os.path.join(work, "j")
    subprocess.run(["g++", "-std=c++11", cpp, "-o", exe], check=True)
    lines = subprocess.run([exe], capture_output=True, text=True, check=True).stdout.strip().splitlines()
    with_time, legacy = json.loads(lines[0]), json.loads(lines[1])
    assert with_time["idempotency_key"] == "TANK-001-42"
    assert with_time["firmware_version"] == "9.9.9"
    assert with_time["turbidity_ntu"] == 0.0 and "ph" not in with_time and "temperature_c" not in with_time
    assert with_time["recorded_at"].endswith("Z") and with_time["recorded_at"].startswith("2026-10")
    assert "recorded_at" not in legacy   # uptime-based stamps from old firmware are not sent as 1970 dates
    assert with_time["arsenic_species"] == "as3_only" and with_time["calibration_ref"] == "CAL-20261108-abc123"
    assert with_time["peak_current_ua"] == pytest.approx(0.04) and "cu_peak_ua" not in with_time
    from app.schemas import ReadingCreate
    assert ReadingCreate(**with_time).arsenic_ppb == pytest.approx(35.1)
