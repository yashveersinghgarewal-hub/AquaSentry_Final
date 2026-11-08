"""v5.9: the software-closable items of the ISEF roadmap that touched the server.

  111/112  sample metadata (how the bottle was taken) stored with a reading or scan and flattened into the paired export
  89/91/98 QC runs for field blanks, spike recovery and the auxiliary sensors' own standards
  30/199   coordinates in the shareable export are rounded unless precise values are asked for
  161/191  the certificate names firmware, model, analysis and calibration versions
"""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.signal_processing import generate_synthetic_asv_trace


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


SAMPLE = {"source_kind": "handpump", "depth_m": 45, "purge_minutes": 5, "bottle_id": "B-16-1", "preservation": "none",
          "collector": "YSG", "collected_at": "2026-11-20T06:40:00Z", "custody_note": "handed to district lab 09:10",
          "split_for_lab": True, "collection_to_analysis_min": 22}


class TestSampleMetadata:
    def test_reading_keeps_sample_metadata(self, client):
        r = client.post("/api/readings", json={"device_code": "SM-01", "arsenic_ppb": 12, "source_type": "hardware",
                                               "qc_status": "pass", "sample_code": "W16-01", "sample": SAMPLE})
        assert r.status_code == 200, r.text
        out = r.json()["reading"]
        assert out["sample"]["source_kind"] == "handpump" and out["sample"]["depth_m"] == 45
        assert out["sample"]["split_for_lab"] is True and out["sample_code"] == "W16-01"
        latest = client.get("/api/readings/latest?device_code=SM-01").json()
        assert latest["sample"]["bottle_id"] == "B-16-1"

    def test_scan_keeps_sample_metadata_and_export_flattens_it(self, client):
        P, C = generate_synthetic_asv_trace(60, seed=2)
        r = client.post("/api/scans", json={"device_code": "SM-02", "potentials_mv": P, "currents_ua": C,
                                            "source_type": "recorded_replay", "sample_code": "W17-01", "sample": SAMPLE})
        assert r.status_code == 200, r.text
        assert r.json()["result"]["reading"]["sample"]["purge_minutes"] == 5
        rows = client.get("/api/data/export/paired?device_code=SM-02&format=json").json()
        assert rows["rows"][0]["sample_source_kind"] == "handpump" and rows["rows"][0]["sample_depth_m"] == 45
        assert rows["rows"][0]["source_kind"] == "handpump"          # falls back to the sample when the site has none
        for col in ("sample_bottle_id", "sample_preservation", "sample_collector", "sample_collected_at",
                    "sample_custody_note", "sample_split_for_lab", "sample_field_blank", "sample_collection_to_analysis_min"):
            assert col in rows["columns"], col

    def test_sample_metadata_is_validated(self, client):
        bad = client.post("/api/readings", json={"device_code": "SM-03", "arsenic_ppb": 12,
                                                 "sample": {"source_kind": "ocean"}})
        assert bad.status_code == 422
        bad = client.post("/api/readings", json={"device_code": "SM-03", "arsenic_ppb": 12, "sample": {"depth_m": -3}})
        assert bad.status_code == 422
        ok = client.post("/api/readings", json={"device_code": "SM-03", "arsenic_ppb": 12})
        assert ok.status_code == 200 and ok.json()["reading"]["sample"] is None


class TestQcRunTypes:
    def test_field_blank_is_judged_like_a_blank(self, client):
        r = client.post("/api/qc/runs", json={"device_code": "QC-59", "run_type": "field_blank", "measured_ug_l": 3.0})
        assert r.status_code == 200 and r.json()["passed"] is True and "Field blank" in r.json()["detail"]
        r = client.post("/api/qc/runs", json={"device_code": "QC-59", "run_type": "field_blank", "measured_ug_l": 14.0})
        assert r.json()["passed"] is False and "contamination" in r.json()["detail"]

    def test_spike_recovery_needs_baseline_and_judges_recovery(self, client):
        r = client.post("/api/qc/runs", json={"device_code": "QC-59", "run_type": "spike_recovery", "expected_ug_l": 50,
                                              "measured_ug_l": 70})
        assert r.json()["passed"] is False and "baseline" in r.json()["detail"]
        r = client.post("/api/qc/runs", json={"device_code": "QC-59", "run_type": "spike_recovery", "expected_ug_l": 50,
                                              "baseline_ug_l": 20, "measured_ug_l": 66})
        assert r.json()["passed"] is True and abs(r.json()["recovery_pct"] - 92.0) < 0.1
        r = client.post("/api/qc/runs", json={"device_code": "QC-59", "run_type": "spike_recovery", "expected_ug_l": 50,
                                              "baseline_ug_l": 20, "measured_ug_l": 50})
        assert r.json()["passed"] is False and "standard addition" in r.json()["detail"]
        runs = client.get("/api/qc/runs?device_code=QC-59&run_type=spike_recovery").json()
        assert len(runs) == 3 and runs[0]["baseline_ug_l"] == 20

    def test_sensor_checks_against_their_standards(self, client):
        ok = client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "ph_buffer", "expected_ug_l": 7.0, "measured_ug_l": 7.12})
        assert ok.json()["passed"] is True
        bad = client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "ph_buffer", "expected_ug_l": 7.0, "measured_ug_l": 7.5})
        assert bad.json()["passed"] is False and "Recalibrate" in bad.json()["detail"]
        ec = client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "conductivity_standard", "expected_ug_l": 1413,
                                               "measured_ug_l": 1450})
        assert ec.json()["passed"] is True and abs(ec.json()["recovery_pct"] - 102.6) < 0.1
        tu = client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "turbidity_standard", "expected_ug_l": 20,
                                               "measured_ug_l": 23})
        assert tu.json()["passed"] is False
        te = client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "temperature_reference", "expected_ug_l": 25.0,
                                               "measured_ug_l": 25.3})
        assert te.json()["passed"] is True
        status = client.get("/api/qc/status?device_code=QC-60").json()["sensor_checks"]
        assert status["ph_buffer"]["verified"] is False          # the latest pH check failed
        assert status["conductivity_standard"]["verified"] is True
        assert status["turbidity_standard"]["verified"] is False
        assert status["temperature_reference"]["verified"] is True
        missing = client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "ph_buffer", "measured_ug_l": 7.0})
        assert missing.json()["passed"] is False and "needs the standard" in missing.json()["detail"]

    def test_unknown_run_type_is_rejected(self, client):
        assert client.post("/api/qc/runs", json={"device_code": "QC-60", "run_type": "vibes", "measured_ug_l": 1}).status_code == 422


def test_paired_export_rounds_coordinates_unless_asked(client):
    client.post("/api/readings", json={"device_code": "GEO-59", "arsenic_ppb": 30, "source_type": "hardware", "qc_status": "pass"})
    assert client.put("/api/admin/devices/GEO-59/site", json={"latitude": 25.60123456, "longitude": 87.04567891}).status_code == 200
    row = client.get("/api/data/export/paired?device_code=GEO-59&format=json").json()["rows"][0]
    assert row["latitude"] == 25.601 and row["longitude"] == 87.046
    row = client.get("/api/data/export/paired?device_code=GEO-59&format=json&precise_coordinates=true").json()["rows"][0]
    assert abs(row["latitude"] - 25.60123456) < 1e-9
    pub = client.get("/api/public/devices/GEO-59").json()
    assert "latitude" not in pub and "longitude" not in pub       # the QR page never carries coordinates


def test_certificate_names_every_version(client):
    pypdf = pytest.importorskip("pypdf")
    r = client.post("/api/readings", json={"device_code": "VER-59", "arsenic_ppb": 35, "source_type": "hardware",
                                           "qc_status": "pass", "firmware_version": "5.9.0", "electrode_lot": "LOT-A",
                                           "sample_code": "W18-02"})
    assert r.status_code == 200, r.text
    rid = r.json()["reading"]["id"]
    pdf = client.get(f"/api/reports/certificate/pdf?reading_id={rid}")
    text = " ".join("".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(pdf.content)).pages).split())
    assert "firmware 5.9.0" in text and "model AquaNet" in text and "electrode lot LOT-A" in text and "sample W18-02" in text
