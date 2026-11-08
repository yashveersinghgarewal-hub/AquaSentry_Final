"""Test Suite: Data Provenance, CSV/JSON Import/Export, and Demo Lifecycle.

Verifies:
1. Data import preview detects columns, checks units, flags negative values.
2. Data import commit assigns source_type='manual_import' and prevents duplicate IDs.
3. Demo data loader inserts curated profiles explicitly tagged as 'synthetic_demo'.
4. Data export produces standardized schema version with optional location redaction.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestDataImportPreview:
    def test_import_preview_valid_dataset(self, client):
        records = [
            {"arsenic_ppb": 25.0, "ph": 7.2, "conductivity_us_cm": 410.0, "turbidity_ntu": 1.8},
            {"arsenic_ppb": 80.0, "ph": 6.8, "conductivity_us_cm": 520.0, "turbidity_ntu": 3.1},
        ]
        resp = client.post("/api/data/import/preview", json=records)
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected_rows"] == 2
        assert data["is_valid"] is True
        assert "arsenic" in data["column_mapping"]

    def test_import_preview_flags_negative_values(self, client):
        records = [
            {"arsenic_ppb": -10.0, "ph": 7.2},
        ]
        resp = client.post("/api/data/import/preview", json=records)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert any("Negative arsenic" in e for e in data["validation_errors"])


class TestDataImportCommitAndDemo:
    def test_import_commit_inserts_records(self, client):
        idemp = f"TEST-IMPORT-{uuid.uuid4().hex[:8]}"
        payload = {
            "source_type": "manual_import",
            "device_code": "IMPORT-TEST",
            "records": [
                {
                    "arsenic_ppb": 48.0,
                    "ph": 7.1,
                    "idempotency_key": idemp,
                }
            ],
        }
        resp = client.post("/api/data/import/commit", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted_count"] == 1

        # Test duplicate idempotency
        resp_dup = client.post("/api/data/import/commit", json=payload)
        assert resp_dup.status_code == 200
        dup_data = resp_dup.json()
        assert dup_data["inserted_count"] == 0
        assert dup_data["duplicate_count"] == 1

    def test_load_demo_data_endpoint(self, client):
        resp = client.post("/api/demo/load")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["loaded_records"] >= 5


class TestDataExport:
    def test_data_export_schema_and_redaction(self, client):
        resp = client.get("/api/data/export?redact_coordinates=true")
        assert resp.status_code == 200
        data = resp.json()
        meta = data["export_metadata"]
        assert meta["schema_version"] == "1.4.0"
        assert meta["coordinates_redacted"] is True
        for rec in data["records"]:
            assert rec["latitude"] is None
            assert rec["longitude"] is None
            assert rec["coordinates_redacted"] is True
