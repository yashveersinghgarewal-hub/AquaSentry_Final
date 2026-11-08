"""v5.7: the harm review fixes.

1. A dead / flat / noisy electrode or a peak outside the window is "Test Failed", never a low (clean-looking) value.
2. Hardware readings must report their scan QC, and a LOW reading needs a passing check standard and a calibration
   made on the electrode; DETECTED arsenic is kept (with a warning) even when the sensor is unverified.
3. Sensors that are not fitted are "not measured" everywhere: verdict, message, storage (no assumed 7.2 / 400 / 2 / 24).
4. Simulated / demo data: PDF stamped "NOT A REAL WATER TEST", never sent to the alert webhook.
5. Writes: closed to the network without a key, and closed to other websites through the browser.
6. Python, JavaScript and C give the same verdicts when inputs are missing.
"""
import io
import json
import math
import os
import shutil
import subprocess
import tempfile

import pytest
from fastapi.testclient import TestClient

from app import qc
from app.aquanet_v3 import predict, CLASSES
from app.classification import classify_arsenic_neural
from app.main import app
from app.signal_processing import generate_synthetic_asv_trace, process_voltammetry_trace

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PLATFORM)
FW = os.path.join(ROOT, "Firmware", "esp32_firmware")
P = [-1100.0 + 5 * i for i in range(121)]


@pytest.fixture
def strict(monkeypatch):
    """Production behaviour: hardware readings need scan QC, a check standard and a calibration."""
    monkeypatch.setenv("QC_REQUIRE_FOR_HARDWARE", "1")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _hw(client, code, ppb, **kw):
    r = client.post("/api/readings", json={"device_code": code, "arsenic_ppb": ppb, "source_type": "hardware", **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _calibrate(client, code):
    client.post("/api/qc/runs", json={"device_code": code, "run_type": "blank", "measured_ug_l": 0})   # registers the device
    std = [{"ug_l": c, "peak_ua": 0.0096 + 0.0008563 * c + e} for c, e in ((0, 0.0003), (20, -0.0002), (50, 0.0002), (100, -0.0001))]
    r = client.post("/api/admin/calibrations/external", json={"device_code": code, "standards": std})
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ 1. scan QC
class TestScanQc:
    def test_good_scans_pass(self):
        for ug in (0, 15, 45, 400):
            res = process_voltammetry_trace(*generate_synthetic_asv_trace(ug))
            assert res.qc_status == "PASS" and res.peak.is_valid_peak, ug

    def test_flat_scan_from_a_dead_electrode_is_rejected(self):
        # what a disconnected / dry electrode gives: ADC noise of a few counts and nothing else
        res = process_voltammetry_trace(P, [0.000625 * (i % 3 - 1) for i in range(121)])
        assert res.qc_status == "REJECTED" and "FLAT_SIGNAL" in res.peak.qc_flags and not res.peak.is_valid_peak

    def test_scan_too_noisy_to_see_the_lod_is_rejected(self):
        import random
        rng = random.Random(4)
        res = process_voltammetry_trace(P, [-0.15 + 0.00015 * (p + 1100) + rng.gauss(0, 0.02) for p in P])
        assert res.qc_status == "REJECTED"
        assert {"NOISE_ABOVE_LOD", "BASELINE_UNSTABLE"} & set(res.peak.qc_flags)

    def test_peak_outside_the_window_is_not_reported_as_low(self):
        cur = [-0.15 + 0.00015 * (p + 1100) + 0.06 * math.exp(-0.5 * ((p + 925) / 30) ** 2) for p in P]
        res = process_voltammetry_trace(P, cur)
        assert res.qc_status == "REJECTED", res.peak.qc_flags

    def test_search_window_is_wider_than_the_expected_window(self):
        cur = [-0.15 + 0.00015 * (p + 1100) + 0.06 * math.exp(-0.5 * ((p + 870) / 35) ** 2) for p in P]
        res = process_voltammetry_trace(P, cur)
        assert res.peak.peak_potential_mv == pytest.approx(-870, abs=10)    # found (was clipped at -860 before)
        assert {"PEAK_SHIFTED", "NOISE_ABOVE_LOD", "PEAK_AT_WINDOW_EDGE"} & set(res.peak.qc_flags)


# ------------------------------------------------------------------ 2. trusting a hardware reading
class TestHardwareTrust:
    def test_no_qc_report_means_test_failed(self, client, strict):
        out = _hw(client, "QC-NOREP", 5)
        assert out["label"] == "Test Failed" and out["is_safe_to_drink"] is None
        assert "QC_NOT_REPORTED" in out["reading"]["qc_flags"] and out["reading"]["qc_status"] == "fail"

    def test_device_reported_fault_fails_even_when_arsenic_is_high(self, client, strict):
        out = _hw(client, "QC-FLAT", 80, qc_status="fail", qc_scan_flags=["FLAT_SIGNAL"])
        assert out["label"] == "Test Failed" and "electrode" in out["message"]

    def test_low_reading_from_unverified_sensor_fails(self, client, strict):
        out = _hw(client, "QC-UNVER", 5, qc_status="pass")
        assert out["label"] == "Test Failed"
        assert "CHECK_STANDARD_MISSING" in out["reading"]["qc_flags"]
        assert "CALIBRATION_MISSING" in out["reading"]["qc_flags"]

    def test_detected_arsenic_is_kept_even_when_unverified(self, client, strict):
        out = _hw(client, "QC-UNVER2", 80, qc_status="pass")
        assert out["label"] == "Unsafe" and "not verified" in out["message"]

    def test_verified_sensor_reports_below_lod(self, client, strict):
        code = "QC-OK"
        _calibrate(client, code)
        r = client.post("/api/qc/runs", json={"device_code": code, "run_type": "check_standard", "expected_ug_l": 50,
                                              "measured_ug_l": 47.5})
        assert r.status_code == 200 and r.json()["passed"] and r.json()["recovery_pct"] == 95.0
        assert r.json()["status"]["trusted"] is True
        out = _hw(client, code, 5, qc_status="pass")
        assert out["label"] == "Below Sensor LOD" and out["is_safe_to_drink"] is None
        assert "not confirmed safe" in out["message"]

    def test_failed_check_standard_blocks_low_readings(self, client, strict):
        code = "QC-DRIFT"
        _calibrate(client, code)
        r = client.post("/api/qc/runs", json={"device_code": code, "run_type": "check_standard", "expected_ug_l": 50,
                                              "measured_ug_l": 30})      # electrode drifting low: 60 % recovery
        assert r.json()["passed"] is False
        assert _hw(client, code, 5, qc_status="pass")["label"] == "Test Failed"

    def test_blank_and_bad_check_inputs(self, client):
        assert client.post("/api/qc/runs", json={"device_code": "QC-B", "run_type": "blank", "measured_ug_l": 3}).json()["passed"]
        assert not client.post("/api/qc/runs", json={"device_code": "QC-B", "run_type": "blank", "measured_ug_l": 25}).json()["passed"]
        assert client.post("/api/qc/runs", json={"device_code": "QC-B", "run_type": "check_standard"}).status_code == 422
        assert client.get("/api/qc/status?device_code=QC-B").json()["recent_blanks"]

    def test_stored_failed_reading_stays_failed_on_resend(self, client, strict):
        body = {"device_code": "QC-IDEM", "arsenic_ppb": 4, "source_type": "hardware", "idempotency_key": "QC-IDEM-1"}
        first = client.post("/api/readings", json=body).json()
        again = client.post("/api/readings", json=body).json()
        assert first["label"] == again["label"] == "Test Failed"

    def test_buffered_reading_keeps_its_age(self, client):
        out = _hw(client, "QC-AGE", 30, qc_status="pass", age_seconds=7200)
        assert out["reading"]["time_source"] == "device_age"
        out2 = _hw(client, "QC-NOTIME", 30, qc_status="pass")
        assert out2["reading"]["time_source"] == "unknown" and "did not say when" in out2["message"]

    def test_latest_real_device_reading(self, client):
        _hw(client, "QC-LATEST", 40, qc_status="pass")
        client.post("/api/readings", json={"device_code": "SIM-DASHBOARD", "arsenic_ppb": 3, "source_type": "simulated"})
        d = client.get("/api/readings/latest?source_type=hardware").json()
        assert d["source_type"] == "hardware"


# ------------------------------------------------------------------ 3. not measured
class TestNotMeasured:
    def test_missing_sensors_are_not_assumed(self, client):
        out = client.post("/api/readings", json={"device_code": "NM-01", "arsenic_ppb": 9, "source_type": "simulated"}).json()
        rd = out["reading"]
        assert rd["ph"] is None and rd["conductivity_us_cm"] is None and rd["turbidity_ntu"] is None
        assert "Not measured: pH, conductivity, turbidity and temperature" in out["message"]
        assert "within limits" not in out["message"]

    def test_measured_problem_still_counts(self):
        assert classify_arsenic_neural(5, ph=5.5).label == "Unsafe"
        assert classify_arsenic_neural(5, turbidity_ntu=15).label == "Unsafe"

    def test_v3_rules_skip_missing_inputs(self):
        r = predict(0.005, None, None, None, None)
        assert not r["is_out_of_bounds"] and r["not_measured"] == ["ph", "conductivity", "turbidity", "temperature"]
        assert all(not x.startswith(("SAFETY_OVERRIDE_SEVERE_PH", "SAFETY_OVERRIDE_HIGH")) for x in r["reasons"])
        assert predict(float("nan"), None, None, None, None)["predicted_class"] in ("Unsafe", "Hazardous")


# ------------------------------------------------------------------ 4. simulated data stays practice
class TestSimulatedData:
    def test_pdf_of_simulated_reading_is_stamped(self, client):
        pypdf = pytest.importorskip("pypdf")
        rid = client.post("/api/readings", json={"device_code": "SIM-PDF", "arsenic_ppb": 60, "source_type": "simulated"}).json()["reading"]["id"]
        pdf = client.get(f"/api/reports/certificate/pdf?reading_id={rid}")
        assert pdf.status_code == 200
        text = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf.content)).pages)
        assert "NOT A REAL WATER TEST" in text and "As(III) only" in text

    def test_pdf_of_failed_test(self, client, strict):
        pypdf = pytest.importorskip("pypdf")
        rid = _hw(client, "QC-PDF", 3)["reading"]["id"]
        text = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(
            client.get(f"/api/reports/certificate/pdf?reading_id={rid}").content)).pages)
        assert "TEST FAILED" in text and "NOT A REAL WATER TEST" not in text

    def test_pdf_without_id_uses_a_real_reading(self, client):
        _hw(client, "QC-REAL", 70, qc_status="pass")
        client.post("/api/readings", json={"device_code": "SIM-X", "arsenic_ppb": 1, "source_type": "simulated"})
        pypdf = pytest.importorskip("pypdf")
        text = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(
            client.get("/api/reports/certificate/pdf").content)).pages)
        assert "NOT A REAL WATER TEST" not in text

    def test_simulated_alert_never_reaches_the_webhook(self, client, monkeypatch):
        from app import main as m
        sent = []
        monkeypatch.setattr(m.webhooks, "deliver_in_background", lambda url, alert: sent.append(alert))
        monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://127.0.0.1:9/hook")
        client.post("/api/readings", json={"device_code": "SIM-HOOK", "arsenic_ppb": 200, "source_type": "simulated"})
        assert sent == []
        _hw(client, "HW-HOOK", 200, qc_status="pass")
        assert sent and sent[-1]["source_type"] == "hardware"


# ------------------------------------------------------------------ 5. writes
class TestWriteLock:
    def test_other_website_cannot_write_through_the_browser(self, client):
        body = {"device_code": "CSRF-01", "arsenic_ppb": 1, "source_type": "hardware", "qc_status": "pass"}
        r = client.post("/api/readings", json=body, headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
        ok = client.post("/api/readings", json=body, headers={"Origin": "http://localhost:8000"})
        assert ok.status_code == 200
        assert client.post("/api/admin/backup", headers={"Origin": "https://evil.example"}).status_code == 403

    def test_cors_is_not_wide_open(self, client):
        r = client.options("/api/readings", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")


# ------------------------------------------------------------------ 6. parity with missing inputs
ROWS = [(0.005, None, None, None, None), (0.012, 7.1, None, None, None), (0.03, None, 2500.0, None, 24.0),
        (0.002, 5.6, None, 2.0, None), (0.009, None, None, 14.0, None), (0.25, None, None, None, None),
        (0.004, 7.4, 450.0, 1.0, 22.0), (0.018, None, 1700.0, None, None)]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_browser_model_matches_python_with_missing_inputs():
    script = ("global.window={};global.document={};require(%s);const A=window.AquaNet;"
              "const rows=JSON.parse(process.argv[1]);console.log(JSON.stringify(rows.map(r=>{const e=A.evaluate(r[0],r[1],r[2],r[3],r[4],'v3');return [e.vote,e.final];})))"
              % json.dumps(os.path.join(PLATFORM, "frontend", "neural.js")))
    out = json.loads(subprocess.run(["node", "-e", script, json.dumps(ROWS)], capture_output=True, text=True, check=True).stdout)
    for row, (vote, final) in zip(ROWS, out):
        p = predict(*row)
        assert (vote, final) == (p["network_vote"], p["predicted_class"]), row


@pytest.mark.skipif(shutil.which("gcc") is None and shutil.which("cc") is None, reason="no C compiler")
def test_c_engine_matches_python_with_missing_inputs():
    cc = shutil.which("gcc") or shutil.which("cc")
    work = tempfile.mkdtemp()
    src = os.path.join(work, "h.c")
    open(src, "w").write(r'''
#include <stdio.h>
#include <math.h>
#include "aquanet_v3.h"
static float rd(const char *s){ float v; return sscanf(s, "%f", &v) == 1 ? v : NAN; }
int main(void){ char a[32],b[32],c[32],d[32],e[32]; while(scanf("%31s %31s %31s %31s %31s",a,b,c,d,e)==5){
 aquanet_result_t r=aquanet_v3_predict_measured(rd(a),rd(b),rd(c),rd(d),rd(e));
 printf("%d %d\n",(int)r.raw_model_class,(int)r.predicted_class);} return 0; }''')
    exe = os.path.join(work, "h")
    subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-I", FW, src, os.path.join(FW, "aquanet_v3.c"),
                    os.path.join(FW, "aquanet_v1.c"), "-lm", "-o", exe], check=True)
    inp = "\n".join(" ".join("x" if v is None else repr(v) for v in r) for r in ROWS)
    out = subprocess.run([exe], input=inp, capture_output=True, text=True, check=True).stdout.split()
    for i, row in enumerate(ROWS):
        p = predict(*row)
        assert CLASSES[int(out[2 * i])] == p["network_vote"], row
        assert CLASSES[int(out[2 * i + 1])] == p["predicted_class"], row


def test_qc_flag_list_fits_its_column():
    s = qc.merge_flags(["CHECK_STANDARD_MISSING", "CALIBRATION_MISSING", "QC_NOT_REPORTED", "DEVICE_REPORTED_FAIL",
                        "PEAK_AT_WINDOW_EDGE", "NOISE_ABOVE_LOD", "FLAT_SIGNAL"], ["as3_only", "uncalibrated"])
    assert len(s) <= 128 and not s.endswith(",") and s.startswith("CHECK_STANDARD_MISSING")


# ------------------------------------------------------------------ 7. the ESP32's own scan checks, run on this computer
SKETCH = os.path.join(FW, "esp32_firmware.ino")


@pytest.mark.skipif(shutil.which("g++") is None, reason="no C++ compiler")
def test_firmware_scan_qc_catches_a_dead_electrode():
    """Runs the sketch's real execute_asv_cycle() against a simulated ADC (healthy, dead, noisy, shifted peak)."""
    import re
    src = open(SKETCH, encoding="utf-8").read()
    defines = "\n".join(l for l in src.splitlines()
                        if re.match(r"#define (VOLT_|PEAK_|BASELINE_EXCLUDE|ASV_MAX_POINTS|COPPER_OFFSET|COPPER_HALF|QC_)", l))
    qc_names = re.search(r"static const struct \{ uint16_t bit; const char\* name; \} QC_NAMES\[\] = \{.*?\n\};\n", src, re.S).group(0)
    arrays = "\n".join(re.findall(r"^static float asv_\w+(?:\[ASV_MAX_POINTS\]| = NAN);.*$", src, re.M))
    savgol = re.search(r"static void savgol5\(.*?\n\}\n", src, re.S).group(0)
    cycle = re.search(r"asv_result_t execute_asv_cycle\(\) \{.*?\n\}\n", src, re.S).group(0)
    harness = r'''
#include <cstdio>
#include <cstdint>
#include <cmath>
#include "aquasentry_types.h"
using std::isnan;
#define F(x) (x)
#define COPPER_CHECK 0
struct SerialT { template <class... A> void printf(const char*, A...) {} void println(const char*) {} } Serial;
static void delay(unsigned long) {}
volatile float cal_slope = 0.8563f, cal_icpt = 0.0096f;
static int mode = 0; static float conc = 0.05f, cur_mv = 0; static unsigned seed = 1;
static void dac_set_potential(float mv) { cur_mv = mv; }
static float rnd() { seed = seed * 1103515245u + 12345u; return ((seed >> 16) & 0x7fff) / 32767.0f - 0.5f; }
static int16_t ads1115_read_differential() {
  if (mode == 1) return (int16_t)(rnd() > 0.3f ? 1 : 0);                      // dead electrode: ADC noise only
  float centre = mode == 3 ? -925.0f : -800.0f;
  float ua = -0.15f + 0.00015f * (cur_mv + 1100.0f) + (0.8563f * conc + 0.0096f) * expf(-0.5f * powf((cur_mv - centre) / 35.0f, 2));
  ua += rnd() * (mode == 2 ? 0.12f : 0.002f);
  return (int16_t)lroundf(ua / 0.000625f);
}
''' + defines + "\n" + qc_names + arrays + "\n" + savgol + cycle + r'''
int main() { for (mode = 0; mode < 4; mode++) { asv_result_t r = execute_asv_cycle();
  printf("%d %u %.4f\n", mode, (unsigned)r.qc, r.net_peak_ua); } return 0; }
'''
    work = tempfile.mkdtemp()
    cpp, exe = os.path.join(work, "qc.cpp"), os.path.join(work, "qc")
    open(cpp, "w").write(harness)
    subprocess.run(["g++", "-std=c++17", "-Wall", "-I", FW, cpp, "-o", exe], check=True)
    rows = [l.split() for l in subprocess.run([exe], capture_output=True, text=True, check=True).stdout.split("\n") if l]
    fault = {int(m): int(bits) for m, bits, _ in rows}
    names = {n: int(v, 16) for n, v in re.findall(r"#define (QC_\w+)\s+(0x[0-9A-Fa-f]+)", src)}
    mask = sum(names[k] for k in ("QC_FLAT_SIGNAL", "QC_NOISE_ABOVE_LOD", "QC_BASELINE_UNSTABLE", "QC_PEAK_AT_EDGE",
                                  "QC_TOO_FEW_SCANS", "QC_SCANS_DISAGREE", "QC_ADC_SATURATION"))
    assert fault[0] & mask == 0, rows                                  # healthy electrode, 50 ug/L
    assert fault[1] & names["QC_FLAT_SIGNAL"], rows                     # dead electrode
    assert fault[2] & (names["QC_NOISE_ABOVE_LOD"] | names["QC_BASELINE_UNSTABLE"]), rows
    assert fault[3] & mask, rows                                       # peak at -925 mV, outside the window


@pytest.mark.skipif(shutil.which("g++") is None, reason="no C++ compiler")
def test_offline_record_layout_unchanged_for_buffered_v56_readings():
    work = tempfile.mkdtemp()
    cpp = os.path.join(work, "off.cpp")
    open(cpp, "w").write('#include <cstddef>\n#include "aquasentry_types.h"\n'
                         'static_assert(sizeof(sensor_reading_t) == 60, "size");\n'
                         'static_assert(offsetof(sensor_reading_t, confidence_pct) == 40, "confidence");\n'
                         'static_assert(offsetof(sensor_reading_t, battery_pct) == 49, "battery");\n'
                         'static_assert(offsetof(sensor_reading_t, arsenic_species) == 50, "species");\n'
                         'static_assert(offsetof(sensor_reading_t, cal_tag) == 52, "cal_tag");\n'
                         'static_assert(offsetof(sensor_reading_t, cu_peak_ua) == 56, "copper");\n'
                         'int main(){return 0;}\n')
    out = subprocess.run(["g++", "-std=c++17", "-fsyntax-only", "-I", FW, cpp], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
