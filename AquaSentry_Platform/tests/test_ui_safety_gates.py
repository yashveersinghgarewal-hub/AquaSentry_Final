"""Test Suite: Strict UI & Public Health Safety Gates (Item 563).

Automated release gate verifying that the system NEVER presents an unearned
potability status of 'Safe' when:
1. Input concentration is below the method LOD (20 µg/L) which exceeds the WHO guideline (10 µg/L).
2. Input concentration is between LOD and LOQ (semi-quantitative).
3. Input concentration exceeds WHO guideline (10 µg/L).
4. Input concentration exceeds Indian BIS 10500 limit (50 µg/L).
5. Input concentration exceeds calibrated analytical range (500 µg/L).
6. Geochemical sensor values are missing or physically impossible.
"""

import pytest
from app.classification import classify_arsenic_neural
from app.standards import (
    assess_water_quality,
    evaluate_measurement,
    AnalyticalStatus,
    RegulatoryTier,
    LOD_UG_L,
    WHO_GUIDELINE_UG_L,
    BIS_PERMISSIBLE_LIMIT_UG_L,
    CAL_MAX_UG_L,
)


class TestStrictPotabilitySafetyGates:
    def test_reading_below_lod_never_claims_safe_to_drink(self):
        """Release Gate: Readings below 20 µg/L cannot clear the 10 µg/L WHO threshold."""
        for val in [0.0, 5.0, 10.0, 15.0, 19.9]:
            eval_res = evaluate_measurement(arsenic_ppb=val)
            assert eval_res.is_safe_to_drink is None, (
                f"SAFETY VIOLATION: Reading {val} µg/L (< LOD 20 µg/L) was declared "
                f"{eval_res.is_safe_to_drink}. Must be None (Unverified)."
            )
            assert eval_res.analytical_status == AnalyticalStatus.BELOW_LOD
            assert eval_res.regulatory_tier == RegulatoryTier.UNVERIFIED_BELOW_LOD

    def test_reading_between_lod_and_loq_is_not_safe(self):
        """Release Gate: Semi-quantitative range (20 to 30 µg/L) exceeds WHO 10 µg/L."""
        for val in [20.1, 25.0, 29.9]:
            eval_res = evaluate_measurement(arsenic_ppb=val)
            assert eval_res.is_safe_to_drink is False
            assert eval_res.analytical_status == AnalyticalStatus.NOT_QUANTIFIABLE

    def test_reading_exceeding_who_guideline_is_not_safe(self):
        """Release Gate: any detected arsenic (>= 20 µg/L LOD) is above the 10 µg/L WHO / IS 10500 limit."""
        for val in [20.0, 30.1, 40.0, 50.0]:
            eval_res = evaluate_measurement(arsenic_ppb=val)
            assert eval_res.is_safe_to_drink is False
            assert eval_res.regulatory_tier == RegulatoryTier.UNSAFE
            assert eval_res.severity >= 2

    def test_reading_exceeding_bis_permissible_is_unsafe(self):
        """Release Gate: Readings > 50 µg/L must strictly trigger Unsafe."""
        for val in [50.1, 75.0, 149.0]:
            eval_res = evaluate_measurement(arsenic_ppb=val)
            assert eval_res.is_safe_to_drink is False
            assert eval_res.regulatory_tier == RegulatoryTier.UNSAFE
            assert eval_res.severity >= 2

    def test_reading_exceeding_calibrated_range_is_hazardous(self):
        """Release Gate: Extreme readings (>500 µg/L) must trigger ABOVE_CALIBRATED_RANGE."""
        eval_res = evaluate_measurement(arsenic_ppb=650.0)
        assert eval_res.is_safe_to_drink is False
        assert eval_res.analytical_status == AnalyticalStatus.ABOVE_CALIBRATED_RANGE
        assert eval_res.regulatory_tier == RegulatoryTier.HAZARDOUS

    def test_neural_classification_wrapper_preserves_safety_overrides(self):
        """Neural classifier wrapper must never override safety rules with softmax."""
        res_unsafe = classify_arsenic_neural(
            arsenic_ppb=75.0,
            ph=7.2,
            conductivity_us_cm=400.0,
            turbidity_ntu=2.0,
            temperature_c=24.0,
        )
        assert res_unsafe.is_safe_to_drink is False
        assert res_unsafe.label in ("Unsafe", "Hazardous")

        res_below_lod = classify_arsenic_neural(
            arsenic_ppb=12.0,
            ph=7.2,
            conductivity_us_cm=400.0,
            turbidity_ntu=2.0,
            temperature_c=24.0,
        )
        # 12 µg/L is above the 10 µg/L limit but below what the sensor can confirm: Caution, never Safe.
        assert res_below_lod.is_safe_to_drink is False
        assert res_below_lod.label == "Caution"

        res_clear = classify_arsenic_neural(arsenic_ppb=5.0, ph=7.2, conductivity_us_cm=400.0,
                                            turbidity_ntu=2.0, temperature_c=24.0)
        assert res_clear.is_safe_to_drink is None
        assert res_clear.label == "Below Sensor LOD"

    def test_negative_arsenic_strictly_rejected(self):
        with pytest.raises(ValueError):
            evaluate_measurement(arsenic_ppb=-5.0)

    def test_extreme_ph_rejected_by_geochemical_validator(self):
        with pytest.raises(ValueError, match="Water pH"):
            classify_arsenic_neural(
                arsenic_ppb=40.0,
                ph=1.5,  # Strong acid outside environmental groundwater
                conductivity_us_cm=400.0,
                turbidity_ntu=2.0,
                temperature_c=24.0,
            )
