"""
Arsenic Risk Classification & Precedence Layer.

Integrates:
- Standard analytical evaluation (LOD, LOQ, WHO, BIS 10500) from `app.standards`
- AquaNet-V1 Multimodal Deep Neural Classifier from `app.neural_classifier`
- Conservative Public Health Precedence Rules
"""

from dataclasses import dataclass
from typing import List, Optional

from .standards import (
    evaluate_measurement,
    AnalyticalStatus,
    RegulatoryTier,
    SourceType,
    LOD_UG_L,
    BIS_PERMISSIBLE_LIMIT_UG_L,
    WHO_GUIDELINE_UG_L,
    HAZARD_THRESHOLD_UG_L,
)


@dataclass
class ClassificationResult:
    label: str               # Short UI label: Safe | Caution | Unsafe | Hazardous | Below LOD
    severity: int            # 0 (best) - 3 (worst)
    message: str             # Public health summary
    action: str              # Recommended action
    analytical_status: str   # below_detection_limit | not_quantifiable | within_calibrated_range | etc.
    regulatory_tier: str     # Formal regulatory standard alignment
    is_safe_to_drink: Optional[bool] # None if unverified below LOD, False if >= WHO limit
    uncertainty_ppb: float   # Analytical measurement uncertainty (+/- ppb)
    disclaimer: str          # Regulatory screening disclaimer


def classify_arsenic(
    arsenic_ppb: float,
    confidence: Optional[float] = None,
    source_type: str = "simulated",
) -> ClassificationResult:
    """
    Classify an arsenic concentration (µg/L, i.e. ppb) into an evidence-based risk assessment.
    """
    st_enum = SourceType.SIMULATED
    if source_type in [e.value for e in SourceType]:
        st_enum = SourceType(source_type)

    assessment = evaluate_measurement(arsenic_ppb, confidence=confidence, source_type=st_enum)

    if assessment.analytical_status == AnalyticalStatus.BELOW_LOD:
        label = "Below Sensor LOD"
    elif assessment.regulatory_tier == RegulatoryTier.CAUTION:
        label = "Caution"
    elif assessment.regulatory_tier == RegulatoryTier.UNSAFE:
        label = "Unsafe"
    else:
        label = "Hazardous"

    return ClassificationResult(
        label=label,
        severity=assessment.severity,
        message=assessment.message,
        action=assessment.action,
        analytical_status=assessment.analytical_status.value,
        regulatory_tier=assessment.regulatory_tier.value,
        is_safe_to_drink=assessment.is_safe_to_drink,
        uncertainty_ppb=assessment.uncertainty_ppb,
        disclaimer=assessment.potability_disclaimer,
    )


TEST_FAILED = "Test Failed"
NOT_MEASURED_NAMES = {"ph": "pH", "conductivity": "conductivity", "turbidity": "turbidity", "temperature": "temperature"}


def _join(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def test_failed_result(reasons: Optional[List[str]], not_measured: Optional[List[str]] = None,
                       uncertainty_ppb: float = 10.0) -> ClassificationResult:
    """A measurement that failed its quality checks: no arsenic value is trusted and the water is NOT called clean."""
    why = f" ({_join(reasons)})" if reasons else ""
    nm = f" Not measured: {_join(NOT_MEASURED_NAMES[n] for n in not_measured)}." if not_measured else ""
    return ClassificationResult(
        label=TEST_FAILED,
        severity=1,
        message=(f"Test failed quality checks{why}. The arsenic result cannot be trusted and does not show that "
                 f"the water is clean.{nm}"),
        action="Retest with a fresh electrode. Until a valid result is available, use another water source.",
        analytical_status="sensor_fault",
        regulatory_tier="Not determined (test failed)",
        is_safe_to_drink=None,
        uncertainty_ppb=uncertainty_ppb,
        disclaimer=("SCREENING ADVISORY: This estimate is produced by a field screening prototype. "
                    "It does not substitute for certified NABL / ISO-17025 accredited laboratory analysis."),
    )


def classify_arsenic_neural(
    arsenic_ppb: float,
    ph: Optional[float] = None,
    conductivity_us_cm: Optional[float] = None,
    turbidity_ntu: Optional[float] = None,
    temperature_c: Optional[float] = None,
    source_type: str = "simulated",
    *,
    qc_failed: bool = False,
    qc_reasons: Optional[List[str]] = None,
    arsenic_species: Optional[str] = None,
) -> ClassificationResult:
    """
    Classify water safety with AquaNet-V3 (default; set AQUANET_MODEL=v1 for the original hand-built V1),
    strictly subject to CONSERVATIVE PUBLIC HEALTH PRECEDENCE RULES (rules can only make a verdict stricter).

    v5.7 honesty rules:
    - pH / conductivity / turbidity / temperature = None means NOT MEASURED. No value is assumed for the verdict;
      the message names what was not measured (it never says "other readings within limits" for them).
    - qc_failed=True (dead / flat / noisy electrode, peak outside the window, unverified sensor on a low reading)
      gives "Test Failed": the arsenic number is not trusted and the water is not called clean.
    - arsenic_species='as3_only' (no pre-reduction) adds "total arsenic may be higher" to the message.
    """
    for name, v, lo, hi in (("pH", ph, 3.0, 11.5), ("temperature", temperature_c, -5.0, 55.0),
                            ("conductivity", conductivity_us_cm, 0.0, 20000.0), ("turbidity", turbidity_ntu, 0.0, 1000.0)):
        if v is not None and not (lo <= v <= hi):
            raise ValueError(f"Water {name} ({v}) is outside the plausible environmental range ({lo} - {hi}).")
    not_measured = [n for n, v in (("ph", ph), ("conductivity", conductivity_us_cm), ("turbidity", turbidity_ntu),
                                   ("temperature", temperature_c)) if v is None]

    import os
    model_choice = os.getenv("AQUANET_MODEL", "v3").lower()
    base_result = classify_arsenic(arsenic_ppb, source_type=source_type)
    arsenic_mg_l = arsenic_ppb / 1000.0
    if qc_failed:
        return test_failed_result(qc_reasons, not_measured, base_result.uncertainty_ppb)

    if model_choice == "v1":
        from .neural_classifier import forward_pass
        # V1 cannot take a missing input; its vote only depends on arsenic, and the rules below skip missing values
        nn_res = forward_pass(arsenic_mg_l=arsenic_mg_l, ph=7.2 if ph is None else ph,
                              conductivity_us_cm=400.0 if conductivity_us_cm is None else conductivity_us_cm,
                              turbidity_ntu=2.0 if turbidity_ntu is None else turbidity_ntu,
                              temperature_c=24.0 if temperature_c is None else temperature_c)
        model_name, nn_label = "AquaNet-V1", str(nn_res["predicted_class"])
        reasons = [str(r) for r in nn_res.get("reason_codes", [])]
        non_arsenic_issue = any(k in r for r in reasons for k in ("pH", "Turbidity", "Conductivity", "Out-of-bounds"))
    else:
        from .aquanet_v3 import predict
        nn_res = predict(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c)
        model_name, nn_label = "AquaNet-V3", str(nn_res["predicted_class"])
        reasons = [r for r in nn_res["reasons"] if not r.startswith("NOT_MEASURED_")]
        non_arsenic_issue = any(k in r for r in reasons for k in ("PH", "TURBIDITY", "SALINITY", "CONDUCTIVITY", "OUT_OF_BOUNDS"))
    conf = nn_res["confidence_pct"]

    # --- SAFETY PRECEDENCE RULES (can only make the verdict stricter) ---
    effective_label = nn_label
    precedence_note = ""
    rank = {"Safe": 0, "Caution": 1, "Unsafe": 2, "Hazardous": 3}
    if arsenic_ppb < LOD_UG_L:
        # 1. Below the sensor's detection limit the arsenic result is unverified. Only show "Below Sensor LOD"
        #    when nothing else is wrong; a pH / turbidity / conductivity problem must stay visible.
        precedence_note = (f" [Method Limit Notice: arsenic is below the sensor LOD ({LOD_UG_L:.0f} µg/L); "
                           f"cannot confirm WHO guideline compliance without a laboratory test.]")
        if effective_label in ("Safe", "Caution") and not non_arsenic_issue and arsenic_ppb <= WHO_GUIDELINE_UG_L:
            effective_label = "Below Sensor LOD"
    else:
        # 2. Detected arsenic (>= LOD, which is above the 10 µg/L WHO / IS 10500 limit) is never Safe or Caution.
        floor = "Hazardous" if arsenic_ppb > HAZARD_THRESHOLD_UG_L else "Unsafe"
        if rank.get(effective_label, 0) < rank[floor]:
            effective_label = floor
            precedence_note = (f" [Precedence Override: measured arsenic ({arsenic_ppb:.1f} µg/L) exceeds the "
                               f"IS 10500 / WHO limit ({BIS_PERMISSIBLE_LIMIT_UG_L:.0f} µg/L); ML downgrade prohibited.]")

    sev_map = {"Below Sensor LOD": 0, "Below LOD": 0, "Safe": 0, "Caution": 1, "Unsafe": 2, "Hazardous": 3}
    severity = sev_map.get(effective_label, base_result.severity)
    is_safe = base_result.is_safe_to_drink
    if severity >= 1:
        is_safe = False

    if not_measured:
        lod_detail = "not confirmed safe: a laboratory test is needed"
    else:
        lod_detail = "measured pH, conductivity and turbidity are within limits; not confirmed safe: a laboratory test is needed"
    nm_note = f" Not measured: {_join(NOT_MEASURED_NAMES[n] for n in not_measured)}." if not_measured else ""
    as3_note = (" Only As(III) is measured (no pre-reduction step), so total arsenic may be higher."
                if arsenic_species == "as3_only" else "")
    messages = {
        "Below Sensor LOD": f"{model_name}: arsenic below sensor LOD ({LOD_UG_L:.0f} µg/L); {lod_detail}.{precedence_note}",
        "Safe": f"{model_name}: Safe ({conf}% confidence). All indicators within limits.{precedence_note}",
        "Caution": f"{model_name}: Caution ({conf}% confidence). Filtration and a laboratory test are advised.{precedence_note}",
        "Unsafe": f"{model_name}: Unsafe ({conf}% confidence). One or more readings exceed drinking-water limits.{precedence_note}",
        "Hazardous": f"{model_name}: Hazardous ({conf}% confidence). Critical toxicity risk detected.{precedence_note}",
    }

    return ClassificationResult(
        label=effective_label,
        severity=severity,
        message=messages.get(effective_label, base_result.message) + nm_note + as3_note,
        action=base_result.action,
        analytical_status=base_result.analytical_status,
        regulatory_tier=base_result.regulatory_tier,
        is_safe_to_drink=is_safe,
        uncertainty_ppb=base_result.uncertainty_ppb,
        disclaimer=base_result.disclaimer,
    )


def classify_water(
    arsenic_mg_l: float,
    ph: Optional[float] = None,
    conductivity: Optional[float] = None,
    turbidity: Optional[float] = None,
    temperature: Optional[float] = None,
    source_type: str = "simulated",
):
    """Convenience evaluator accepting concentration in mg/L and returning (label, metadata_dict)."""
    arsenic_ppb = arsenic_mg_l * 1000.0
    res = classify_arsenic_neural(
        arsenic_ppb=arsenic_ppb,
        ph=ph,
        conductivity_us_cm=conductivity,
        turbidity_ntu=turbidity,
        temperature_c=temperature,
        source_type=source_type,
    )
    override_applied = "Precedence Override" in res.message
    reason_code = "SAFETY_OVERRIDE_ARSENIC_EXCEEDS_BIS" if override_applied else "NOMINAL"
    metadata = {
        "severity": res.severity,
        "message": res.message,
        "action_plan": res.action,
        "analytical_status": res.analytical_status,
        "regulatory_tier": res.regulatory_tier,
        "is_safe_to_drink": res.is_safe_to_drink,
        "uncertainty_ppb": res.uncertainty_ppb,
        "override_applied": override_applied,
        "reason_code": reason_code,
    }
    return res.label, metadata
