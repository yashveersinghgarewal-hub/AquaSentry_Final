"""
Arsenic Risk Classification & Precedence Layer.

Integrates:
- Standard analytical evaluation (LOD, LOQ, WHO, BIS 10500) from `app.standards`
- AquaNet-V1 Multimodal Deep Neural Classifier from `app.neural_classifier`
- Conservative Public Health Precedence Rules
"""

from dataclasses import dataclass
from typing import Optional

from .standards import (
    evaluate_measurement,
    AnalyticalStatus,
    RegulatoryTier,
    SourceType,
    LOD_UG_L,
    LOQ_UG_L,
    BIS_PERMISSIBLE_LIMIT_UG_L,
    WHO_GUIDELINE_UG_L,
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


def classify_arsenic_neural(
    arsenic_ppb: float,
    ph: float = 7.2,
    conductivity_us_cm: float = 400.0,
    turbidity_ntu: float = 2.0,
    temperature_c: float = 24.0,
    source_type: str = "simulated",
) -> ClassificationResult:
    """
    Classify water safety with AquaNet-V3 (default; set AQUANET_MODEL=v1 for the original hand-built V1),
    strictly subject to CONSERVATIVE PUBLIC HEALTH PRECEDENCE RULES (rules can only make a verdict stricter).
    """
    if ph < 3.0 or ph > 11.5:
        raise ValueError(f"Water pH ({ph:.2f}) is outside plausible environmental range (3.0 - 11.5).")
    if temperature_c < -5.0 or temperature_c > 55.0:
        raise ValueError(f"Water temperature ({temperature_c:.1f} °C) is outside plausible range.")
    if conductivity_us_cm < 0.0 or conductivity_us_cm > 20000.0:
        raise ValueError(f"Conductivity ({conductivity_us_cm:.0f} µS/cm) is outside plausible range.")
    if turbidity_ntu < 0.0 or turbidity_ntu > 1000.0:
        raise ValueError(f"Turbidity ({turbidity_ntu:.1f} NTU) is outside plausible range.")

    import os
    model_choice = os.getenv("AQUANET_MODEL", "v3").lower()
    base_result = classify_arsenic(arsenic_ppb, source_type=source_type)
    arsenic_mg_l = arsenic_ppb / 1000.0

    if model_choice == "v1":
        from .neural_classifier import forward_pass
        nn_res = forward_pass(arsenic_mg_l=arsenic_mg_l, ph=ph, conductivity_us_cm=conductivity_us_cm,
                              turbidity_ntu=turbidity_ntu, temperature_c=temperature_c)
        model_name, nn_label = "AquaNet-V1", str(nn_res["predicted_class"])
        reasons = [str(r) for r in nn_res.get("reason_codes", [])]
        non_arsenic_issue = any(k in r for r in reasons for k in ("pH", "Turbidity", "Conductivity", "Out-of-bounds"))
    else:
        from .aquanet_v3 import predict
        nn_res = predict(arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c)
        model_name, nn_label = "AquaNet-V3", str(nn_res["predicted_class"])
        reasons = nn_res["reasons"]
        non_arsenic_issue = any(k in r for r in reasons for k in ("PH", "TURBIDITY", "SALINITY", "CONDUCTIVITY", "OUT_OF_BOUNDS"))
    conf = nn_res["confidence_pct"]

    # --- SAFETY PRECEDENCE RULES ---
    # 1. A measured arsenic level above the BIS limit can never be shown as Safe or Caution.
    effective_label = nn_label
    precedence_note = ""
    if arsenic_ppb > BIS_PERMISSIBLE_LIMIT_UG_L and nn_label in ("Safe", "Caution"):
        effective_label = "Unsafe"
        precedence_note = (f" [Precedence Override: Measured concentration ({arsenic_ppb:.1f} µg/L) "
                           f"exceeds BIS permissible limit; ML downgrade prohibited.]")
    elif arsenic_ppb < LOD_UG_L:
        # 2. Below the sensor's detection limit the arsenic result is unverified. Only show "Below Sensor LOD"
        #    when nothing else is wrong; a pH / turbidity / conductivity problem must stay visible.
        precedence_note = (f" [Method Limit Notice: arsenic is below the sensor LOD ({LOD_UG_L:.0f} µg/L); "
                           f"cannot confirm WHO guideline compliance without a laboratory test.]")
        if effective_label in ("Safe", "Caution") and not non_arsenic_issue:
            effective_label = "Below Sensor LOD"

    sev_map = {"Below Sensor LOD": 0, "Below LOD": 0, "Safe": 0, "Caution": 1, "Unsafe": 2, "Hazardous": 3}
    severity = sev_map.get(effective_label, base_result.severity)
    is_safe = base_result.is_safe_to_drink
    if severity >= 1:
        is_safe = False

    messages = {
        "Below Sensor LOD": f"{model_name}: arsenic below sensor LOD ({LOD_UG_L:.0f} µg/L); other readings within limits.{precedence_note}",
        "Safe": f"{model_name}: Safe ({conf}% confidence). All indicators within limits.{precedence_note}",
        "Caution": f"{model_name}: Caution ({conf}% confidence). Filtration and a laboratory test are advised.{precedence_note}",
        "Unsafe": f"{model_name}: Unsafe ({conf}% confidence). One or more readings exceed drinking-water limits.{precedence_note}",
        "Hazardous": f"{model_name}: Hazardous ({conf}% confidence). Critical toxicity risk detected.{precedence_note}",
    }

    return ClassificationResult(
        label=effective_label,
        severity=severity,
        message=messages.get(effective_label, base_result.message),
        action=base_result.action,
        analytical_status=base_result.analytical_status,
        regulatory_tier=base_result.regulatory_tier,
        is_safe_to_drink=is_safe,
        uncertainty_ppb=base_result.uncertainty_ppb,
        disclaimer=base_result.disclaimer,
    )


def classify_water(
    arsenic_mg_l: float,
    ph: float = 7.2,
    conductivity: float = 400.0,
    turbidity: float = 2.0,
    temperature: float = 24.0,
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
    override_applied = arsenic_ppb > BIS_PERMISSIBLE_LIMIT_UG_L and ("Precedence Override" in res.message)
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
