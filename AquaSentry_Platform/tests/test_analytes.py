"""Test Suite: Multi-Contaminant Registry & Capability Matrix.

Verifies:
1. Canonical catalog registration for Arsenic, Lead, Cadmium, Mercury, Chromium, Fluoride, Nitrate.
2. Only Arsenic is marked as actively monitored by catamaran hardware.
3. Planned/experimental status for metals requiring different electrodes or reagents.
4. Scientific boundary evaluation: Arsenic below LOD (20 µg/L) is unverified potability.
5. API endpoints /api/analytes and /api/analytes/{id}.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.analytes import (
    ANALYTE_REGISTRY,
    get_analyte_profile,
    list_supported_analytes,
    list_hardware_active_analytes,
    evaluate_analyte_concentration,
    AnalyteSupportStatus,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestAnalyteRegistry:
    def test_catalog_contains_expected_species(self):
        analytes = list_supported_analytes()
        ids = {a.identifier for a in analytes}
        expected = {"arsenic", "lead", "cadmium", "mercury", "chromium_total", "chromium_vi", "fluoride", "nitrate"}
        assert expected.issubset(ids)

    def test_only_arsenic_is_hardware_active(self):
        active = list_hardware_active_analytes()
        assert len(active) == 1
        assert active[0].identifier == "arsenic"
        assert active[0].is_actively_monitored_by_hardware is True

    def test_planned_analytes_not_hardware_active(self):
        lead = get_analyte_profile("lead")
        assert lead is not None
        assert lead.is_actively_monitored_by_hardware is False
        assert lead.support_status == AnalyteSupportStatus.PLANNED

        cadmium = get_analyte_profile("cadmium")
        assert cadmium is not None
        assert cadmium.is_actively_monitored_by_hardware is False
        assert cadmium.support_status == AnalyteSupportStatus.PLANNED

    def test_arsenic_lod_guardrail(self):
        # 15 µg/L is below LOD (20 µg/L)
        res = evaluate_analyte_concentration("arsenic", 15.0)
        assert res["is_below_lod"] is True
        assert res["status"] == "below_detection_limit"
        assert res["is_safe"] is None  # Cannot confirm safe because 10 < 20
        assert "below method detection limit" in res["message"].lower()

    def test_arsenic_35_exceeds_amended_bis(self):
        # 35 µg/L used to be "within BIS permissible 50". IS 10500 Amendment 1 (2015): 10 µg/L, no relaxation.
        res = evaluate_analyte_concentration("arsenic", 35.0, jurisdiction="bis_10500")
        assert res["is_below_lod"] is False
        assert res["severity"] >= 2
        assert "Permissible" not in res["tier"]
        assert res["is_safe"] is False

    def test_arsenic_hazardous_exceedance(self):
        # 180 µg/L exceeds BIS (50) and hazard threshold
        res = evaluate_analyte_concentration("arsenic", 180.0)
        assert res["severity"] == 3
        assert "Hazardous" in res["tier"]
        assert res["is_safe"] is False


class TestAnalyteEndpoints:
    def test_get_all_analytes(self, client):
        resp = client.get("/api/analytes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 8
        as_entry = next((a for a in data if a["identifier"] == "arsenic"), None)
        assert as_entry is not None
        assert as_entry["lod_ug_l"] == 20.0
        assert as_entry["is_actively_monitored_by_hardware"] is True

    def test_get_single_analyte(self, client):
        resp = client.get("/api/analytes/lead")
        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "lead"
        assert data["chemical_formula"] == "Pb (Pb²⁺)"
        assert data["support_status"] == "planned"

    def test_unknown_analyte_returns_404(self, client):
        resp = client.get("/api/analytes/kryptonite")
        assert resp.status_code == 404
