"""Test Suite: Scientific Standards, Units, LOD Auditing, and Safety Precedence.

Verifies:
1. Physical unit conversions (mg/L <-> µg/L <-> ppb) with strict round-trip fidelity.
2. Scientific assessment against WHO (10 µg/L) and BIS 10500 (50 µg/L) guidelines.
3. Method Limit of Detection (LOD = 20 µg/L) and Quantitation (LOQ = 30 µg/L) statuses.
4. Prohibition on certifying drinking potability when below LOD.
5. Conservative safety precedence: ML model cannot declare 'Safe' when arsenic > 50 µg/L.
"""

import pytest
import math
from app.standards import (
    WHO_ARSENIC_GUIDELINE_UG_L,
    BIS_ARSENIC_ACCEPTABLE_UG_L,
    BIS_ARSENIC_PERMISSIBLE_UG_L,
    METHOD_LOD_UG_L,
    METHOD_LOQ_UG_L,
    CALIBRATION_MAX_UG_L,
    AnalyticalStatus,
    RegulatoryTier,
    ScientificAssessment,
    mg_l_to_ug_l,
    ug_l_to_mg_l,
    assess_water_quality,
    STANDARD_REGISTRY,
)
from app.classification import classify_water


class TestUnitConversions:
    """Test unit conversions and boundary values."""

    def test_mg_l_to_ug_l_nominal(self):
        assert mg_l_to_ug_l(0.010) == pytest.approx(10.0, rel=1e-6)
        assert mg_l_to_ug_l(0.050) == pytest.approx(50.0, rel=1e-6)
        assert mg_l_to_ug_l(0.020) == pytest.approx(20.0, rel=1e-6)

    def test_ug_l_to_mg_l_nominal(self):
        assert ug_l_to_mg_l(10.0) == pytest.approx(0.010, rel=1e-6)
        assert ug_l_to_mg_l(50.0) == pytest.approx(0.050, rel=1e-6)
        assert ug_l_to_mg_l(20.0) == pytest.approx(0.020, rel=1e-6)

    def test_round_trip_conversion(self):
        test_values = [0.001, 0.005, 0.010, 0.020, 0.030, 0.050, 0.100, 0.500]
        for val in test_values:
            ug = mg_l_to_ug_l(val)
            round_trip = ug_l_to_mg_l(ug)
            assert round_trip == pytest.approx(val, rel=1e-9)

    def test_negative_values_raise_error(self):
        with pytest.raises(ValueError):
            mg_l_to_ug_l(-0.01)
        with pytest.raises(ValueError):
            ug_l_to_mg_l(-10.0)


class TestAnalyticalStatusAndStandards:
    """Test LOD auditing and WHO/BIS compliance tiering."""

    def test_below_lod_status(self):
        """Readings below 20 µg/L must be flagged below LOD and CANNOT be certified safe."""
        assessment = assess_water_quality(0.008)  # 8 µg/L
        assert assessment.analytical_status == AnalyticalStatus.BELOW_DETECTION_LIMIT
        assert assessment.regulatory_tier == RegulatoryTier.BELOW_LOD
        # Critical rule: Cannot certify safe when LOD > WHO limit
        assert assessment.is_safe_to_drink is not True
        assert "detection" in assessment.advisory_text.lower()
        assert "icp-ms" in assessment.action_plan.lower()

    def test_not_quantifiable_status(self):
        """Readings between LOD (20 µg/L) and LOQ (30 µg/L) are detectable but not quantifiable."""
        assessment = assess_water_quality(0.025)  # 25 µg/L
        assert assessment.analytical_status == AnalyticalStatus.NOT_QUANTIFIABLE
        assert assessment.regulatory_tier == RegulatoryTier.ABOVE_WHO_GUIDELINE
        assert assessment.is_safe_to_drink is False

    def test_within_calibrated_range_is_unsafe(self):
        """30-50 µg/L used to be 'within BIS permissible'. IS 10500 Amendment 1 (2015) removed that relaxation."""
        assessment = assess_water_quality(0.040)  # 40 µg/L
        assert assessment.analytical_status == AnalyticalStatus.WITHIN_CALIBRATED_RANGE
        assert assessment.regulatory_tier == RegulatoryTier.UNSAFE
        assert assessment.is_safe_to_drink is False
        assert "unsafe" in assessment.status_label.lower()
        assert "permissible" not in assessment.message.lower()

    def test_above_bis_permissible_action_required(self):
        """Readings exceeding 50 µg/L exceed national drinking standard."""
        assessment = assess_water_quality(0.065)  # 65 µg/L
        assert assessment.analytical_status == AnalyticalStatus.WITHIN_CALIBRATED_RANGE
        assert assessment.regulatory_tier == RegulatoryTier.ABOVE_BIS_PERMISSIBLE
        assert assessment.is_safe_to_drink is False
        assert "do not use for drinking" in assessment.action_plan.lower()

    def test_above_calibrated_range(self):
        """Readings exceeding 500 µg/L exceed sensor upper calibration."""
        assessment = assess_water_quality(0.650)  # 650 µg/L
        assert assessment.analytical_status == AnalyticalStatus.ABOVE_CALIBRATED_RANGE
        assert assessment.regulatory_tier == RegulatoryTier.HAZARDOUS
        assert assessment.is_safe_to_drink is False
        assert "dilution" in assessment.advisory_text.lower()


class TestConservativeSafetyPrecedence:
    """Test that machine learning predictions NEVER override high chemical measurements."""

    def test_safety_override_triggered_when_arsenic_exceeds_bis(self):
        """When arsenic > 0.050 mg/L, classification cannot be 'Safe'."""
        classification, metadata = classify_water(
            arsenic_mg_l=0.080,  # 80 µg/L > 50 µg/L BIS limit
            ph=7.2,
            conductivity=400.0,
            turbidity=2.0,
            temperature=24.0,
        )
        assert classification in ("Unsafe", "Hazardous")
        assert metadata["is_safe_to_drink"] is False

    def test_below_lod_advisory_in_classification(self):
        """When arsenic < 0.020 mg/L, classification notes below LOD and does not certify potability."""
        classification, metadata = classify_water(
            arsenic_mg_l=0.005,  # 5 µg/L
            ph=7.2,
            conductivity=350.0,
            turbidity=1.5,
            temperature=22.0,
        )
        assert metadata["analytical_status"] == AnalyticalStatus.BELOW_DETECTION_LIMIT.value
        assert metadata["is_safe_to_drink"] in (False, None)
        assert "ICP-MS" in metadata["action_plan"]


class TestStandardsRegistry:
    """Verify standards registry entries and citations."""

    def test_who_standard_exists(self):
        assert "who_gdwq_2017" in STANDARD_REGISTRY
        std = STANDARD_REGISTRY["who_gdwq_2017"]
        assert std.numeric_threshold == 10.0
        assert std.unit == "µg/L"

    def test_bis_standard_exists(self):
        assert "bis_10500_2012_acceptable" in STANDARD_REGISTRY
        assert "bis_10500_2012_permissible" in STANDARD_REGISTRY
        assert STANDARD_REGISTRY["bis_10500_2012_acceptable"].numeric_threshold == 10.0
        # Amendment No. 1 (2015): arsenic permissible limit = acceptable limit = 10 µg/L ("no relaxation").
        assert STANDARD_REGISTRY["bis_10500_2012_permissible"].numeric_threshold == 10.0
        assert "relaxation" in STANDARD_REGISTRY["bis_10500_2012_permissible"].notes.lower()
