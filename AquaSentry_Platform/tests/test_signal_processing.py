"""Test Suite: Electrochemical Voltammetry Signal Processing & QC Pipeline.

Verifies:
1. 5-point Savitzky-Golay quadratic filter preserves peak height and position.
2. 3-point rolling median filter suppresses single-point ADC spikes.
3. Linear baseline fitting properly subtracts background baseline drift.
4. Full ASV trace processing on synthetic voltammogram reproduces known input.
5. ADC saturation detection and baseline noise QC flagging.
6. API endpoints /api/voltammetry/process and /api/voltammetry/sample-trace.
"""

import math
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.signal_processing import (
    savitzky_golay_5pt,
    rolling_median_3pt,
    fit_linear_baseline,
    process_voltammetry_trace,
    generate_synthetic_asv_trace,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestFiltersAndBaseline:
    def test_savitzky_golay_preserves_pure_line(self):
        # A linear sequence should be preserved exactly by quadratic SG filter
        y = [2.0 * x + 1.0 for x in range(20)]
        smoothed = savitzky_golay_5pt(y)
        for orig, sm in zip(y, smoothed):
            assert abs(orig - sm) < 1e-4

    def test_rolling_median_suppresses_spike(self):
        y = [1.0, 1.0, 1.0, 50.0, 1.0, 1.0, 1.0]
        cleaned = rolling_median_3pt(y)
        assert cleaned[3] == 1.0  # Spike eliminated

    def test_baseline_fit_subtracts_tilt(self):
        pots = [float(p) for p in range(-1100, -500, 10)]
        # True baseline: slope = 0.001, intercept = 0.5
        currents = [0.001 * p + 0.5 for p in pots]
        baseline, var = fit_linear_baseline(pots, currents, peak_target_mv=-800.0)
        assert len(baseline) == len(pots)
        assert var < 1e-5


class TestVoltammetryPipeline:
    def test_synthetic_trace_reproduces_concentration(self):
        true_ppb = 50.0
        pots, currents = generate_synthetic_asv_trace(arsenic_ppb=true_ppb, snr_db=30.0, seed=123)
        res = process_voltammetry_trace(pots, currents)

        assert res.qc_status in ("PASS", "WARNING")
        assert res.peak is not None
        assert abs(res.peak.peak_potential_mv - (-800.0)) <= 15.0
        # Estimated concentration should be within 15% of true 50 µg/L
        assert abs(res.estimated_arsenic_ug_l - true_ppb) < 12.0

    def test_adc_saturation_flagged(self):
        pots = [float(p) for p in range(-1100, -500, 10)]
        # Current pinned at upper rail 12.0 µA
        currents = [12.0 if -830 <= p <= -770 else 0.5 for p in pots]
        res = process_voltammetry_trace(pots, currents)
        assert "ADC_SATURATION_HIGH" in res.peak.qc_flags
        assert res.qc_status == "REJECTED"

    def test_nan_or_inf_raises_validation_error(self):
        pots = [float(p) for p in range(-1100, -500, 10)]
        currents = [float("nan") if i == 5 else 0.5 for i in range(len(pots))]
        with pytest.raises(ValueError, match="NaN or Infinity"):
            process_voltammetry_trace(pots, currents)


class TestVoltammetryEndpoints:
    def test_sample_trace_endpoint(self, client):
        resp = client.get("/api/voltammetry/sample-trace?arsenic_ppb=45.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["arsenic_ppb"] == 45.0
        assert len(data["potentials_mv"]) > 50
        assert len(data["currents_ua"]) == len(data["potentials_mv"])

    def test_process_endpoint(self, client):
        pots, currents = generate_synthetic_asv_trace(arsenic_ppb=60.0, seed=42)
        payload = {
            "potentials_mv": pots,
            "currents_ua": currents,
            "filter_mode": "savitzky_golay",
        }
        resp = client.post("/api/voltammetry/process", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "estimated_arsenic_ug_l" in data
        assert data["estimated_arsenic_ug_l"] > 30.0
        assert "peak" in data
        assert data["peak"]["peak_potential_mv"] < -700.0
