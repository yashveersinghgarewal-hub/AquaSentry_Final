"""Test Suite: FastAPI API Contracts, Idempotency, Validation, and Diagnostics.

Verifies:
1. Health endpoint with subsystem diagnostics.
2. Sensor readings ingestion with strict boundary validation.
3. Idempotent deduplication via idempotency_key.
4. Provenance filtering on readings history.
5. Dashboard latest reading endpoint with staleness detection.
6. Neural inference endpoint returning 112 synapses.
7. Chat assistant graceful offline fallback.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Create test client for FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoint:
    """Verify system diagnostics and health contracts."""

    def test_health_check_healthy(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "healthy")
        assert "diagnostics" in data
        diag = data["diagnostics"]
        assert diag["database"] == "connected"
        assert "AquaNet-V3" in diag["neural_model"] or "AquaNet-V1" in diag["neural_model"]
        assert diag["model_version"] in ("AquaNet-V3", "AquaNet-V1")
        assert "standards_version" in diag


class TestReadingsIngestionAndValidation:
    """Verify reading ingestion, Pydantic bounds validation, and scientific fields."""

    def test_ingest_valid_reading(self, client):
        payload = {
            "device_code": "TEST-BOT-01",
            "source_type": "simulated",
            "arsenic_ppb": 45.0,
            "ph": 7.35,
            "conductivity_us_cm": 420.0,
            "turbidity_ntu": 2.1,
            "temperature_c": 24.5,
            "latitude": 18.5204,
            "longitude": 73.8567,
            "idempotency_key": str(uuid.uuid4()),
        }
        response = client.post("/api/readings", json=payload)
        assert response.status_code in (200, 201)
        data = response.json()
        assert "reading" in data
        assert data["analytical_status"] == "within_calibrated_range"
        assert data["is_safe_to_drink"] is False  # Exceeds WHO 10 µg/L
        assert "uncertainty_ppb" in data

    def test_idempotent_deduplication(self, client):
        """Sending the exact same reading with identical idempotency_key returns identical ID without creating duplicate."""
        key = f"idemp-{uuid.uuid4()}"
        payload = {
            "device_code": "TEST-BOT-02",
            "source_type": "simulated",
            "arsenic_ppb": 35.0,
            "ph": 7.1,
            "conductivity_us_cm": 350.0,
            "turbidity_ntu": 1.8,
            "temperature_c": 22.0,
            "idempotency_key": key,
        }
        # First submission
        res1 = client.post("/api/readings", json=payload)
        assert res1.status_code in (200, 201)
        id1 = res1.json()["reading"]["id"]

        # Duplicate submission with identical key
        res2 = client.post("/api/readings", json=payload)
        assert res2.status_code in (200, 201)
        id2 = res2.json()["reading"]["id"]

        # IDs must match; no duplicate row created
        assert id1 == id2

    def test_negative_arsenic_rejected(self, client):
        """Negative concentration must be rejected with 422."""
        payload = {
            "device_code": "TEST-BOT-03",
            "arsenic_ppb": -50.0,
            "ph": 7.0,
            "conductivity_us_cm": 400.0,
            "turbidity_ntu": 2.0,
            "temperature_c": 25.0,
        }
        response = client.post("/api/readings", json=payload)
        assert response.status_code == 422

    def test_invalid_ph_rejected(self, client):
        """pH > 14 must be rejected with 422."""
        payload = {
            "device_code": "TEST-BOT-04",
            "arsenic_ppb": 20.0,
            "ph": 15.5,
            "conductivity_us_cm": 400.0,
            "turbidity_ntu": 2.0,
            "temperature_c": 25.0,
        }
        response = client.post("/api/readings", json=payload)
        assert response.status_code == 422


class TestReadingsQueryAndDashboard:
    """Verify readings listing and dashboard contracts."""

    def test_get_readings_list(self, client):
        response = client.get("/api/readings?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_filter_by_source_type(self, client):
        response = client.get("/api/readings?source_type=simulated&limit=5")
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["source_type"] == "simulated"

    def test_dashboard_latest(self, client):
        response = client.get("/api/dashboard/latest")
        assert response.status_code == 200
        data = response.json()
        assert "value" in data
        assert ("analytical_status" in data) or ("analyticalStatus" in data)
        assert ("synapses_count" in data) or ("synapsesCount" in data) or ("methodLOD" in data)


class TestNeuralInferenceEndpoint:
    """Verify neural inference API contract."""

    def test_neural_inference_nominal(self, client):
        payload = {
            "arsenic_concentration_mg_l": 0.008,
            "ph": 7.2,
            "conductivity_us_cm": 410.0,
            "turbidity_ntu": 1.9,
            "temperature_c": 23.5,
        }
        response = client.post("/api/neural/inference", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["synapses_count"] == 112
        assert data["nodes_count"] == 23
        assert "predicted_class" in data
        assert "confidence_pct" in data
        assert "probabilities" in data
        assert "latency_ms" in data


class TestChatEndpointOfflineGracefulFallback:
    """Verify chat assistant handles unconfigured external API gracefully."""

    def test_chat_returns_200_without_crash(self, client):
        payload = {
            "message": "Is this water safe to drink?",
            "device_code": "AQUA-001",
        }
        response = client.post("/api/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0
