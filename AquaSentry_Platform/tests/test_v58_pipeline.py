"""v5.8 regression tests: the native-scan evidence pipeline and the single screening outcome.

Covers the Research & Engineering Review items the v5.8 release claims to close:
  * one outcome per test (invalid | not_detected | retest | screen_positive) with a guard band equal to the
    reading's expanded uncertainty (k = 2), measured from the scan when a trace was processed;
  * native scans stored as evidence with a SHA-256 checksum, analysis version and calibration id, and
    re-processable without overwriting the original value;
  * malformed scans (jumbled sweep, too short, non-finite, missing baseline shoulders) rejected, not estimated;
  * the browser copy of the pipeline (frontend/asv.js) giving the same answer as the Python pipeline;
  * corroboration only by other real, QC-passed nodes at the same place;
  * censored ("<") laboratory results and the paired node-vs-lab export;
  * bounded, finite inputs on the neural inference endpoint;
  * the PDF leading with the outcome, the uncertainty and the calibration provenance.
"""
import json
import math
import os
import random
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.classification import screening_outcome
from app.main import app
from app.signal_processing import (
    ANALYSIS_VERSION,
    estimate_uncertainty,
    generate_synthetic_asv_trace,
    process_voltammetry_trace,
)
from app.standards import CALIBRATION_SOURCE, LOD_UG_L, QC_FAULT_FLAGS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASV_JS = os.path.join(ROOT, "frontend", "asv.js")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _trace(ppb, seed=42):
    return generate_synthetic_asv_trace(ppb, seed=seed)


def _post_scan(client, code, P, C, **extra):
    body = {"device_code": code, "potentials_mv": P, "currents_ua": C, "source_type": "simulated"}
    body.update(extra)
    r = client.post("/api/scans", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- 1. the screening outcome
class TestScreeningOutcome:
    def test_failed_test_is_invalid(self):
        assert screening_outcome(50, 5, failed=True)[0] == "invalid"

    def test_guard_band_is_the_expanded_uncertainty(self):
        # 15 µg/L with ± 4 is clearly below the 20 µg/L LOD -> not detected; with ± 8 it overlaps -> retest
        assert screening_outcome(15, 4)[0] == "not_detected"
        assert screening_outcome(15, 8)[0] == "retest"
        assert screening_outcome(19.9, 1)[0] == "retest"
        assert screening_outcome(20, 1)[0] == "screen_positive"
        assert screening_outcome(0, 3)[0] == "not_detected"

    def test_unknown_uncertainty_uses_the_method_typical_value(self):
        # without a scan the guard band falls back to 10 µg/L, never to zero
        assert screening_outcome(12, None)[0] == "retest"
        assert screening_outcome(9, None)[0] == "not_detected"

    def test_outcome_text_never_calls_not_detected_safe(self):
        _, note = screening_outcome(3, 2)
        assert "safe" in note.lower() and "not confirmation" in note.lower()

    def test_uncertainty_grows_with_noise_and_shrinks_with_averaging(self):
        u1 = estimate_uncertainty(50, 0.002, 0.8563)
        u2 = estimate_uncertainty(50, 0.004, 0.8563)
        u4 = estimate_uncertainty(50, 0.004, 0.8563, n_scans=4)
        assert u2 > u1 and u4 < u2
        # k = 2 expanded: at zero noise only the 5 % calibration term is left -> 2 * 0.05 * 50 = 5
        assert abs(estimate_uncertainty(50, 0.0, 0.8563) - 5.0) < 1e-9


# ---------------------------------------------------------------- 2. the pipeline on real-shaped traces
class TestPipelineRobustness:
    def test_clean_traces_recover_the_concentration(self):
        for ppb in (25, 45, 120, 400):
            P, C = _trace(ppb)
            r = process_voltammetry_trace(P, C)
            assert r.qc_status != "REJECTED" and r.analysis_version == ANALYSIS_VERSION
            assert abs(r.estimated_arsenic_ug_l - ppb) < max(3.0, 0.06 * ppb), (ppb, r.estimated_arsenic_ug_l)
            assert r.peak.uncertainty_ug_l > 0

    def test_descending_sweep_is_reversed_not_rejected(self):
        P, C = _trace(45)
        fwd = process_voltammetry_trace(P, C)
        rev = process_voltammetry_trace(P[::-1], C[::-1])
        assert rev.sweep_reversed and abs(rev.estimated_arsenic_ug_l - fwd.estimated_arsenic_ug_l) < 0.01

    def test_copper_like_bump_does_not_tilt_the_baseline(self):
        P, C = _trace(45)
        bumped = [c + 0.08 * math.exp(-0.5 * ((x + 550) / 25) ** 2) for x, c in zip(P, C)]
        r = process_voltammetry_trace(P, bumped)
        assert r.qc_status != "REJECTED"
        assert abs(r.estimated_arsenic_ug_l - 45) < 4.0, r.estimated_arsenic_ug_l
        assert "BASELINE_OUTLIERS" in r.qc_flags and r.peak.secondary_peaks >= 1

    def test_single_spike_is_clipped_out(self):
        P, C = _trace(45)
        spiked = [c + (0.5 if i == 10 else 0.0) for i, c in enumerate(C)]
        r = process_voltammetry_trace(P, spiked)
        assert r.qc_status != "REJECTED" and abs(r.estimated_arsenic_ug_l - 45) < 1.0

    @pytest.mark.parametrize("name, mutate, flag", [
        ("jumbled", lambda P, C: (random.Random(1).sample(P, len(P)), C), "NONMONOTONIC_SWEEP"),
        ("too_short", lambda P, C: (P[:5], C[:5]), "TOO_FEW_POINTS"),
        ("non_finite", lambda P, C: (P, C[:60] + [float("nan")] + C[61:]), "NON_FINITE"),
        ("no_right_shoulder", lambda P, C: (P[:66], C[:66]), "INSUFFICIENT_BASELINE"),
        ("length_mismatch", lambda P, C: (P, C[:-1]), "MALFORMED_TRACE"),
    ])
    def test_malformed_scans_are_rejected_with_a_fault(self, name, mutate, flag):
        P, C = _trace(45)
        P2, C2 = mutate(list(P), list(C))
        with pytest.raises(ValueError):          # strict mode (the science endpoint) raises
            process_voltammetry_trace(P2, C2)
        r = process_voltammetry_trace(P2, C2, strict=False)   # the scan store records the fault
        assert r.qc_status == "REJECTED", (name, r.qc_status, r.qc_flags)
        assert flag in r.qc_flags and flag in QC_FAULT_FLAGS, (name, r.qc_flags)

    def test_invalid_calibration_is_a_fault(self):
        P, C = _trace(45)
        r = process_voltammetry_trace(P, C, slope=0.0, strict=False)
        assert r.qc_status == "REJECTED" and "INVALID_CALIBRATION" in r.qc_flags

    def test_factory_calibration_is_labelled_synthetic(self):
        assert CALIBRATION_SOURCE == "synthetic_example"


# ---------------------------------------------------------------- 3. the browser port must match
@pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to run frontend/asv.js")
def test_asv_js_matches_the_python_pipeline():
    cases = {}
    for ppb in (0, 8, 15, 25, 45, 120, 400):
        cases[f"clean{ppb}"] = _trace(ppb)
    P, C = _trace(45)
    cases["cu_bump"] = (P, [c + 0.08 * math.exp(-0.5 * ((x + 550) / 25) ** 2) for x, c in zip(P, C)])
    cases["spike"] = (P, [c + 0.5 * (i == 10) for i, c in enumerate(C)])
    cases["reversed"] = (P[::-1], C[::-1])
    cases["shift905"] = (P, [-0.15 + 0.00015 * (x + 1100) + 0.06 * math.exp(-0.5 * ((x + 905) / 30) ** 2) for x in P])
    rng = random.Random(4)
    cases["noisy"] = (P, [-0.15 + 0.00015 * (x + 1100) + rng.gauss(0, 0.02) for x in P])
    cases["flat"] = (P, [0.000625 * (i % 3 - 1) for i in range(121)])
    Q = list(P)
    random.Random(1).shuffle(Q)
    cases["jumbled"] = (Q, C)
    cases["noshoulder"] = (P[50:], C[50:])
    cases["short"] = (P[:5], C[:5])

    py = {}
    for k, (p, c) in cases.items():
        r = process_voltammetry_trace(p, c, strict=False)
        py[k] = {"status": r.qc_status, "ug": r.estimated_arsenic_ug_l, "flags": sorted(r.qc_flags),
                 "u": r.peak.uncertainty_ug_l if r.peak else None, "mv": r.peak.peak_potential_mv if r.peak else None}
    script = ("global.window={};require(process.argv[1]);const A=window.AquaASV;"
              "const cases=JSON.parse(require('fs').readFileSync(0,'utf8'));const out={};"
              "for(const k in cases){const r=A.process(cases[k][0],cases[k][1]);"
              "out[k]={status:r.status,ug:r.asUgL,flags:r.flags.slice().sort(),"
              "u:r.peakIdx<0?null:r.uncertaintyUg,mv:r.peakIdx<0?null:r.peakMv};}"
              "console.log(JSON.stringify(out))")
    js = subprocess.run(["node", "-e", script, ASV_JS], input=json.dumps(cases), capture_output=True, text=True)
    assert js.returncode == 0, js.stderr
    js = json.loads(js.stdout)
    for k in cases:
        a, b = py[k], js[k]
        assert a["status"] == b["status"], (k, a, b)
        assert a["flags"] == b["flags"], (k, a, b)
        if a["status"] != "REJECTED":
            assert abs(a["ug"] - b["ug"]) < 0.05, (k, a, b)
            assert a["mv"] == b["mv"], (k, a, b)
            assert abs(a["u"] - b["u"]) < 0.05, (k, a, b)


# ---------------------------------------------------------------- 4. scans as evidence
class TestScanEvidence:
    def test_scan_is_stored_with_checksum_and_linked_to_its_reading(self, client):
        P, C = _trace(60)
        out = _post_scan(client, "SCN-01", P, C, sample_code="W-16/2026", electrode_lot="L9")
        scan = out["scan"]
        assert len(scan["checksum_sha256"]) == 64 and scan["analysis_version"] == ANALYSIS_VERSION
        assert scan["n_points"] == 121 and scan["qc_status"] in ("PASS", "WARN")
        assert out["pipeline"]["calibration_provenance"]  # the factory calibration says it is synthetic
        res = out["result"]
        assert res["screening_outcome"] == "screen_positive" and res["uncertainty_source"] == "measured_from_scan"
        assert res["reading"]["trace_id"] == scan["id"] and res["reading"]["sample_code"] == "W-16/2026"
        assert abs(res["reading"]["arsenic_ppb"] - 60) < 4

        full = client.get(f"/api/scans/{scan['id']}").json()
        assert full["processed"]["checksum_matches"] is True
        assert full["readings"][0]["id"] == out["reading_id"]
        assert len(full["potentials_mv"]) == 121 and len(full["processed"]["smoothed_currents_ua"]) == 121

        listed = client.get("/api/scans?device_code=SCN-01").json()
        assert listed and listed[0]["id"] == scan["id"] and "potentials_mv" not in listed[0]
        assert client.get(f"/api/scans?reading_id={out['reading_id']}").json()[0]["id"] == scan["id"]

    def test_same_scan_twice_is_one_scan(self, client):
        P, C = _trace(30)
        a = _post_scan(client, "SCN-02", P, C, idempotency_key="scan-dup-1")
        b = _post_scan(client, "SCN-02", P, C, idempotency_key="scan-dup-1")
        assert b.get("duplicate") is True and b["scan"]["id"] == a["scan"]["id"]
        assert len(client.get("/api/scans?device_code=SCN-02").json()) == 1

    def test_mismatched_arrays_are_rejected(self, client):
        P, C = _trace(30)
        r = client.post("/api/scans", json={"device_code": "SCN-03", "potentials_mv": P, "currents_ua": C[:-1],
                                            "source_type": "simulated"})
        assert r.status_code == 422

    def test_malformed_scan_becomes_an_invalid_reading(self, client):
        P, C = _trace(45)
        Q = list(P)
        random.Random(3).shuffle(Q)
        out = _post_scan(client, "SCN-04", Q, C)
        assert out["scan"]["qc_status"] == "REJECTED" and out["scan"]["estimated_ug_l"] is None
        res = out["result"]
        assert res["screening_outcome"] == "invalid" and res["reading"]["classification"] == "Test Failed"
        assert "NONMONOTONIC_SWEEP" in (out["scan"]["qc_flags"] or "")

    def test_reprocess_does_not_overwrite_the_original(self, client):
        P, C = _trace(80)
        out = _post_scan(client, "SCN-05", P, C)
        sid, rid = out["scan"]["id"], out["reading_id"]
        original = client.get(f"/api/readings?device_code=SCN-05").json()[0]["arsenic_ppb"]
        # a steeper external calibration halves the estimate
        std = [{"ug_l": 0, "peak_ua": 0.01}, {"ug_l": 100, "peak_ua": 0.01 + 1.7126 * 0.1},
               {"ug_l": 200, "peak_ua": 0.01 + 1.7126 * 0.2}, {"ug_l": 400, "peak_ua": 0.01 + 1.7126 * 0.4}]
        cal = client.post("/api/admin/calibrations/external",
                          json={"device_code": "SCN-05", "standards": std, "electrode_lot": "L9"})
        assert cal.status_code == 200, cal.text
        cal_id = cal.json()["calibration_id"]
        rp = client.post(f"/api/scans/{sid}/reprocess?calibration_id={cal_id}&store=true").json()
        assert rp["original_reading_id"] == rid and abs(rp["original_ug_l"] - original) < 1e-9
        assert abs(rp["recomputed"]["estimated_ug_l"] - original / 2) < 2.0, rp
        assert rp["recomputed"]["calibration_id"] == cal_id
        # the original reading is untouched; the recomputed value is a NEW reading that points back to it
        rows = client.get(f"/api/scans/{sid}").json()["readings"]
        assert rows[0]["id"] == rid and rows[0]["arsenic_ppb"] == original
        assert len(rows) == 2 and rows[1]["reprocessed_from_id"] == rid and rows[1]["calibration_id"] == cal_id

    def test_unknown_calibration_and_scan_are_404(self, client):
        assert client.get("/api/scans/999999").status_code == 404
        P, C = _trace(30)
        sid = _post_scan(client, "SCN-06", P, C)["scan"]["id"]
        assert client.post(f"/api/scans/{sid}/reprocess?calibration_id=nope").status_code == 404

    def test_recorded_replay_is_not_a_simulation(self, client):
        P, C = _trace(35, seed=7)
        out = _post_scan(client, "SCN-07", P, C, source_type="recorded_replay", raw_file_name="well16.csv")
        res = out["result"]
        assert res["reading"]["source_type"] == "recorded_replay" and res["reading"]["is_simulated"] is False
        pub = client.get("/api/public/devices/SCN-07").json()
        assert pub["latest"]["is_demo"] is False and pub["latest"]["screening_outcome"] == "screen_positive"


# ---------------------------------------------------------------- 5. the reading endpoint carries the outcome
class TestReadingOutcome:
    def test_averaged_reading_without_a_scan_uses_the_typical_uncertainty(self, client):
        r = client.post("/api/readings", json={"device_code": "OUT-01", "arsenic_ppb": 14}).json()
        assert r["screening_outcome"] == "retest" and r["uncertainty_source"] == "method_typical"
        r = client.post("/api/readings", json={"device_code": "OUT-01", "arsenic_ppb": 4}).json()
        assert r["screening_outcome"] == "not_detected"
        r = client.post("/api/readings", json={"device_code": "OUT-01", "arsenic_ppb": 40}).json()
        assert r["screening_outcome"] == "screen_positive" and r["outcome_note"].startswith("Arsenic detected")

    def test_failed_reading_has_no_outcome_but_invalid(self, client):
        r = client.post("/api/readings", json={"device_code": "OUT-02", "arsenic_ppb": 40, "source_type": "hardware",
                                               "qc_status": "fail", "qc_scan_flags": ["FLAT_SIGNAL"]}).json()
        assert r["reading"]["classification"] == "Test Failed" and r["screening_outcome"] == "invalid"

    def test_sample_code_is_validated(self, client):
        bad = client.post("/api/readings", json={"device_code": "OUT-03", "arsenic_ppb": 4, "sample_code": "a b;drop"})
        assert bad.status_code == 422


# ---------------------------------------------------------------- 6. corroboration by place, not by count
def test_only_nearby_real_nodes_corroborate(client):
    for code, lat, src in (("COR-A", 24.00, "hardware"), ("COR-B", 24.01, "hardware"), ("COR-SIM", 24.00, "simulated"),
                           ("COR-FAR", 25.50, "hardware")):
        r = client.post("/api/readings", json={"device_code": code, "arsenic_ppb": 120, "source_type": src, "qc_status": "pass"})
        assert r.status_code == 200, r.text
        assert client.put(f"/api/admin/devices/{code}/site", json={"latitude": lat, "longitude": 88.0}).status_code == 200
    d = client.get("/api/dashboard/latest?device_code=COR-A").json()
    assert d["confirmedByHomes"] == 1      # COR-B (1.1 km); not the simulation, not the node 170 km away
    # a nearby node whose only detection failed QC does not count either
    client.post("/api/readings", json={"device_code": "COR-C", "arsenic_ppb": 120, "source_type": "hardware",
                                       "qc_status": "fail", "qc_scan_flags": ["NOISE_ABOVE_LOD"]})
    assert client.put("/api/admin/devices/COR-C/site", json={"latitude": 24.005, "longitude": 88.0}).status_code == 200
    d = client.get("/api/dashboard/latest?device_code=COR-A").json()
    assert d["confirmedByHomes"] == 1


# ---------------------------------------------------------------- 7. censored lab results and the paired export
class TestLabPairing:
    def test_censored_result_needs_its_reporting_limit(self, client):
        client.post("/api/readings", json={"device_code": "LAB-58", "arsenic_ppb": 4, "source_type": "hardware",
                                           "qc_status": "pass", "sample_code": "S-1"})
        r = client.post("/api/lab-results", json={"device_code": "LAB-58", "arsenic_ug_l": 3, "qualifier": "<",
                                                  "lab_name": "District lab", "lab_method": "ICP-MS"})
        assert r.status_code == 422
        r = client.post("/api/lab-results", json={"device_code": "LAB-58", "arsenic_ug_l": 5, "qualifier": "<",
                                                  "reporting_limit_ug_l": 3, "lab_name": "District lab", "lab_method": "ICP-MS"})
        assert r.status_code == 422
        r = client.post("/api/lab-results", json={"device_code": "LAB-58", "arsenic_ug_l": 3, "qualifier": "<",
                                                  "reporting_limit_ug_l": 3, "sample_code": "S-1",
                                                  "lab_name": "District lab", "lab_method": "ICP-MS", "species": "total"})
        assert r.status_code == 200, r.text
        row = r.json()
        assert row["censored"] is True and row["qualifier"] == "<" and row["reporting_limit_ug_l"] == 3
        assert row["reading_id"] is not None and row["node_outcome"] == "not_detected"

    def test_paired_export_has_one_row_per_real_reading(self, client):
        csv = client.get("/api/data/export/paired?device_code=LAB-58")
        assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
        text = csv.content.decode("utf-8-sig")
        header = text.splitlines()[0].split(",")
        for col in ("sample_code", "device_ug_l", "device_uncertainty_ug_l", "screening_outcome", "qc_status",
                    "lab_ug_l", "lab_qualifier", "lab_reporting_limit_ug_l", "scan_checksum_sha256", "calibration_id",
                    "analysis_version", "firmware_version", "pair_gap_hours"):
            assert col in header, col
        rows = client.get("/api/data/export/paired?device_code=LAB-58&format=json").json()["rows"]
        assert len(rows) == 1 and rows[0]["lab_qualifier"] == "<" and rows[0]["lab_ug_l"] == 3
        assert rows[0]["sample_code"] == "S-1" and rows[0]["screening_outcome"] == "not_detected"
        # simulated readings are left out unless asked for
        client.post("/api/readings", json={"device_code": "LAB-58", "arsenic_ppb": 50})
        assert len(client.get("/api/data/export/paired?device_code=LAB-58&format=json").json()["rows"]) == 1
        assert len(client.get("/api/data/export/paired?device_code=LAB-58&format=json&include_demo=true").json()["rows"]) == 2
        assert client.get("/api/data/export/paired?device_code=NOPE").status_code == 404


# ---------------------------------------------------------------- 8. inference inputs are bounded
def test_neural_inference_rejects_nonsense(client):
    ok = client.post("/api/neural/inference", json={"arsenic_mg_l": 0.03, "ph": 7.0, "conductivity_us_cm": 500,
                                                        "turbidity_ntu": 2})
    assert ok.status_code == 200, ok.text
    for bad in ('{"arsenic_mg_l": 1e999}', '{"arsenic_mg_l": NaN}', '{"arsenic_mg_l": -1}', '{"arsenic_mg_l": 0.03, "ph": 19}',
                '{"arsenic_mg_l": 0.03, "conductivity_us_cm": -5}'):
        r = client.post("/api/neural/inference", content=bad, headers={"content-type": "application/json"})
        assert r.status_code == 422, (bad, r.status_code, r.text)


def test_oversized_bodies_are_refused(client):
    r = client.post("/api/readings", content=b"x" * 10, headers={"content-type": "application/json", "content-length": str(3 * 1024 * 1024)})
    assert r.status_code == 413


# ---------------------------------------------------------------- 9. the PDF leads with the outcome
def test_pdf_leads_with_outcome_uncertainty_and_provenance(client):
    pypdf = pytest.importorskip("pypdf")
    import io
    P, C = _trace(60)
    out = _post_scan(client, "PDF-58", P, C)
    rid = out["reading_id"]
    pdf = client.get(f"/api/reports/certificate/pdf?reading_id={rid}")
    assert pdf.status_code == 200
    text = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf.content)).pages)
    flat = " ".join(text.split())
    assert "ARSENIC DETECTED" in flat and "CONFIRM IN A LABORATORY" in flat
    assert "±" in flat and "k = 2" in flat
    assert "synthetic" in flat.lower() and out["scan"]["checksum_sha256"][:12] in flat
    assert ANALYSIS_VERSION in flat and "factory" in flat.lower()
    assert LOD_UG_L == 20
