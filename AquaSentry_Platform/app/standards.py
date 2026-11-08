"""
AquaSentry Scientific Standards & Regulatory Reference Registry.

Single source of truth for:
- Measurement units and physical conversions
- Method limits of detection (LOD) and quantification (LOQ)
- Validated calibration ranges
- WHO, India BIS 10500, and public health action thresholds
- Analytical status classifications
- Scientific disclaimers and precedence rules

IMPORTANT PUBLIC HEALTH NOTICE:
AquaSentry is an autonomous screening and spatial surveillance prototype.
It is NOT an ISO 17025 accredited laboratory instrument.
Readings must be confirmed by certified reference methods (e.g., ICP-MS or HG-AAS)
before making regulatory declarations of drinking water potability.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ==============================================================================
# Method Analytical Specifications (MAS-G1 Stripping Voltammetry)
# ==============================================================================
METHOD_NAME = "Anodic Stripping Voltammetry (ASV) - MAS-G1"
METHOD_VERSION = "MAS-G1-v1.2"
SENSOR_STRIP_MODEL = "As-M003050"
STRIP_CHEMISTRY = "Screen-printed carbon with gold nanoparticle / bismuth modifier"
PEAK_POTENTIAL_MV = -800.0  # vs pseudo-reference electrode
SWEEP_WINDOW_MV = 60.0      # +/- where the arsenic peak is expected; a peak found further out is flagged PEAK_SHIFTED
PEAK_SEARCH_MV = 100.0      # +/- how far the peak is searched for (wider, so a shifted peak is not missed)

# ==============================================================================
# Scan quality control (v5.7). A scan that fails these is reported as "Test failed", never as clean water:
# a dead, dry or noisy electrode reads LOW, and a low reading otherwise looks like safe water.
# ==============================================================================
QC_FLAT_RANGE_UA = 0.005        # whole scan varies less than this: electrode disconnected, dry or dead
QC_MAX_NOISE_UA = 0.05          # background noise above this: scan rejected
QC_DETECT_SNR = 3.0             # net peak must be 3x the background noise to count as a detection
QC_MIN_GOOD_SCANS = 2           # the device must average at least this many good scans
QC_CHECK_RECOVERY = (80.0, 120.0)   # a check standard must read 80-120 % of its true value
QC_BLANK_MAX_UG_L = 10.0        # a blank (arsenic-free water) must read below this
# v5.9 (ISEF items 89, 91, 98): field blanks, spike recovery and the auxiliary sensors' own checks
QC_SPIKE_RECOVERY = (80.0, 120.0)                  # spiked sample must recover 80-120 % of the added arsenic
QC_SENSOR_TOLERANCE = {                            # |measured - standard| allowed for each auxiliary sensor
    "ph_buffer": 0.2,                              # pH units against a buffer (4.01 / 7.00 / 10.01)
    "conductivity_standard": 0.05,                 # relative (5 %) against a conductivity standard (e.g. 1413 µS/cm)
    "turbidity_standard": 0.10,                    # relative (10 %) against a formazin / polymer standard
    "temperature_reference": 0.5,                  # °C against a reference thermometer
}
# Fault codes: any of these means the measurement itself is not trustworthy.
QC_FAULT_FLAGS = {
    "ADC_SATURATION_HIGH", "ADC_SATURATION_LOW", "FLAT_SIGNAL", "BASELINE_UNSTABLE", "NOISE_ABOVE_LOD",
    "PEAK_AT_WINDOW_EDGE", "NO_POINTS_IN_WINDOW", "TOO_FEW_GOOD_SCANS", "SCANS_DISAGREE", "NO_LIQUID",
    "QC_NOT_REPORTED", "DEVICE_REPORTED_FAIL",
    # v5.8 (review item 42): a trace that cannot be analysed is a failed test, never a concentration
    "MALFORMED_TRACE", "TOO_FEW_POINTS", "NON_FINITE", "INVALID_CALIBRATION", "NONMONOTONIC_SWEEP",
    "INSUFFICIENT_BASELINE", "PARTIAL_WINDOW",
}

# Detection and Quantification Limits (in micrograms per litre, µg/L = ppb)
LOD_UG_L = 20.0   # 0.020 mg/L - Method Limit of Detection
LOQ_UG_L = 30.0   # 0.030 mg/L - Method Limit of Quantification
CAL_MIN_UG_L = 30.0   # 0.030 mg/L - Lower boundary of validated linear range
CAL_MAX_UG_L = 500.0  # 0.500 mg/L - Upper boundary of validated linear range

# Baseline Calibration Equation: I_peak (µA) = slope * C_As (mg/L) + intercept
CALIBRATION_SLOPE = 0.8563
CALIBRATION_INTERCEPT = 0.0096
CALIBRATION_R2 = 0.9967
# v5.8 (review item 06): where these numbers come from. The four "standards" in Data/calibration.json were produced
# by the synthetic scan generator in Analysis/mas_g1_arsenic_analysis.py, not measured on an electrode. They let the
# software run end to end; they are NOT evidence of accuracy. POST /api/admin/calibrations/external replaces them.
CALIBRATION_SOURCE = "synthetic_example"
CALIBRATION_PROVENANCE = ("Factory example calibration: 4 synthetic standards (30-500 µg/L) from the simulated scan "
                          "generator, R² 0.9967 on those synthetic points. Not a laboratory calibration.")
CALIBRATION_ID = "CAL-AS-2026-M1"


# ==============================================================================
# Regulatory Standards & Public Health Thresholds (µg/L)
# ==============================================================================
# Source: WHO Guidelines for Drinking-water Quality, 4th edition (2017)
WHO_GUIDELINE_UG_L = 10.0  # 0.010 mg/L (Provisional)

# Source: Bureau of Indian Standards IS 10500:2012 (Drinking Water Specification), as amended.
# The 2012 text allowed 0.05 mg/L "in the absence of an alternate source". Amendment No. 1 (2015)
# removed that relaxation: arsenic is now 0.01 mg/L acceptable AND permissible ("no relaxation").
# (CGWA reply to the NGT, OA 538/2024: "revised from 0.05 mg/L (50 ppb) to 0.01 mg/L (10 ppb) in 2015".)
BIS_ACCEPTABLE_LIMIT_UG_L = 10.0   # 0.010 mg/L
BIS_PERMISSIBLE_LIMIT_UG_L = 10.0  # 0.010 mg/L, no relaxation since Amendment No. 1 (2015)
BIS_2012_SUPERSEDED_PERMISSIBLE_UG_L = 50.0  # historical value only; never used for a verdict

# Emergency Action Level / Acute Toxic Hazard Zone
HAZARD_THRESHOLD_UG_L = 150.0      # 0.150 mg/L

# Direct Named Aliases for test suites and schema clarity
WHO_ARSENIC_GUIDELINE_UG_L = WHO_GUIDELINE_UG_L
BIS_ARSENIC_ACCEPTABLE_UG_L = BIS_ACCEPTABLE_LIMIT_UG_L
BIS_ARSENIC_PERMISSIBLE_UG_L = BIS_PERMISSIBLE_LIMIT_UG_L
METHOD_LOD_UG_L = LOD_UG_L
METHOD_LOQ_UG_L = LOQ_UG_L
CALIBRATION_MAX_UG_L = CAL_MAX_UG_L


def mg_l_to_ug_l(mg_l: float) -> float:
    """Convert mg/L to µg/L (ppb)."""
    if mg_l < 0:
        raise ValueError("mg/L cannot be negative")
    return round(mg_l * 1000.0, 6)


def ug_l_to_mg_l(ug_l: float) -> float:
    """Convert µg/L (ppb) to mg/L."""
    if ug_l < 0:
        raise ValueError("µg/L cannot be negative")
    return round(ug_l / 1000.0, 6)


# ==============================================================================
# Analytical & Operational Status Enums
# ==============================================================================
class AnalyticalStatus(str, Enum):
    BELOW_LOD = "below_detection_limit"
    BELOW_DETECTION_LIMIT = "below_detection_limit"
    NOT_QUANTIFIABLE = "not_quantifiable"
    WITHIN_CALIBRATED_RANGE = "within_calibrated_range"
    ABOVE_CALIBRATED_RANGE = "above_calibrated_range"
    SENSOR_FAULT = "sensor_fault"
    INSUFFICIENT_DATA = "insufficient_data"


class RegulatoryTier(str, Enum):
    UNVERIFIED_BELOW_LOD = "Unverified (Below LOD)"
    BELOW_LOD = "Unverified (Below LOD)"
    CAUTION = "Caution (Advisory)"
    UNSAFE = "Unsafe (Exceeds BIS & WHO)"
    ABOVE_WHO_GUIDELINE = "Unsafe (Exceeds BIS & WHO)"
    ABOVE_BIS_PERMISSIBLE = "Unsafe (Exceeds BIS & WHO)"
    HAZARDOUS = "Hazardous (Acute Risk)"


class SourceType(str, Enum):
    SIMULATED = "simulated"
    HARDWARE = "hardware"
    MANUAL_IMPORT = "manual_import"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


@dataclass(frozen=True)
class StandardEntry:
    jurisdiction: str
    standard_code: str
    title: str
    analyte: str
    unit: str
    numeric_threshold: float
    citation: str
    notes: str


STANDARD_REGISTRY = {
    "who_gdwq_2017": StandardEntry(
        jurisdiction="International",
        standard_code="WHO GDWQ 4th Ed.",
        title="WHO Guidelines for Drinking-water Quality",
        analyte="Arsenic (total)",
        unit="µg/L",
        numeric_threshold=10.0,
        citation="World Health Organization (2017). Guidelines for drinking-water quality, 4th edition.",
        notes="Provisional guideline based on practical analytical and treatment feasibility.",
    ),
    "bis_10500_2012_acceptable": StandardEntry(
        jurisdiction="India",
        standard_code="BIS 10500:2012 Acceptable",
        title="Indian Standard Drinking Water — Specification",
        analyte="Arsenic (as As)",
        unit="µg/L",
        numeric_threshold=10.0,
        citation="Bureau of Indian Standards (2012). IS 10500:2012, Second Revision, with Amendment No. 1 (2015).",
        notes="Acceptable limit for drinking water.",
    ),
    "bis_10500_2012_permissible": StandardEntry(
        jurisdiction="India",
        standard_code="BIS 10500:2012 Permissible",
        title="Indian Standard Drinking Water — Specification",
        analyte="Arsenic (as As)",
        unit="µg/L",
        numeric_threshold=10.0,
        citation="Bureau of Indian Standards (2012). IS 10500:2012, Second Revision, with Amendment No. 1 (2015).",
        notes="No relaxation: Amendment No. 1 (2015) withdrew the old 50 µg/L permissible limit.",
    ),
}


@dataclass(frozen=True)
class ScientificAssessment:
    measured_arsenic_ppb: float
    measured_arsenic_mg_l: float
    analytical_status: AnalyticalStatus
    regulatory_tier: RegulatoryTier
    severity: int                     # 0 (lowest) to 3 (critical)
    status_label: str                 # Human readable label
    status_tone: str                  # safe-dim | warning | danger | critical
    is_safe_to_drink: Optional[bool]  # False if unsafe; None if unverified below LOD
    confidence_pct: float
    uncertainty_ppb: float
    message: str
    action: str
    potability_disclaimer: str
    method_provenance: str

    @property
    def advisory_text(self) -> str:
        return self.message

    @property
    def action_plan(self) -> str:
        return self.action


def assess_water_quality(arsenic_mg_l: float) -> ScientificAssessment:
    """Assess water quality from concentration in mg/L."""
    return evaluate_measurement(arsenic_ppb=mg_l_to_ug_l(arsenic_mg_l))


def evaluate_measurement(
    arsenic_ppb: float,
    confidence: Optional[float] = None,
    source_type: SourceType = SourceType.SIMULATED,
) -> ScientificAssessment:
    """
    Evaluate an arsenic measurement against validated analytical ranges and standards.

    SCIENTIFIC INTEGRITY ENFORCEMENT:
    Because the method LOD (20 µg/L) is HIGHER than the WHO guideline (10 µg/L),
    a reading < 20 µg/L CANNOT confirm potability. It is classified as UNVERIFIED_BELOW_LOD.
    """
    if arsenic_ppb is None:
        raise ValueError("arsenic_ppb is required")
    if arsenic_ppb < 0:
        raise ValueError("arsenic_ppb cannot be negative")

    as_mg_l = round(arsenic_ppb / 1000.0, 4)
    conf = round(confidence * 100, 1) if confidence is not None else 95.0

    # 1. Below Detection Limit (< 20 µg/L)
    if arsenic_ppb < LOD_UG_L:
        status = AnalyticalStatus.BELOW_LOD
        tier = RegulatoryTier.UNVERIFIED_BELOW_LOD
        severity = 0
        tone = "safe-dim"
        is_safe = None  # Crucial: Cannot confirm safe because 10 µg/L < 20 µg/L
        uncertainty = 10.0
        label = "Below Sensor LOD (<20 µg/L)"
        message = (
            f"Measured concentration ({arsenic_ppb:.1f} µg/L) is below the prototype's "
            f"Limit of Detection (LOD = {LOD_UG_L:.0f} µg/L). "
            f"Because the LOD is above the WHO guideline ({WHO_GUIDELINE_UG_L:.0f} µg/L), "
            f"this screening test cannot rule out contamination between 10–20 µg/L."
        )
        action = "Routine screening. Laboratory ICP-MS testing required to certify potability below 10 µg/L."

    # 2. Detected (>= LOD). The LOD (20 µg/L) is already twice the WHO and BIS limit (10 µg/L),
    #    so ANY detected arsenic means the water fails both standards.
    elif arsenic_ppb <= HAZARD_THRESHOLD_UG_L:
        quantifiable = arsenic_ppb >= LOQ_UG_L
        status = AnalyticalStatus.WITHIN_CALIBRATED_RANGE if quantifiable else AnalyticalStatus.NOT_QUANTIFIABLE
        tier = RegulatoryTier.UNSAFE
        severity = 2
        tone = "danger"
        is_safe = False
        uncertainty = (7.5 if arsenic_ppb > 50.0 else 5.0) if quantifiable else 8.0
        label = "Unsafe (Exceeds BIS & WHO)"
        semi = "" if quantifiable else (
            f" The value is between the LOD and LOQ ({LOQ_UG_L:.0f} µg/L), so the number itself is approximate, "
            f"but arsenic is clearly present.")
        message = (
            f"Arsenic detected at {arsenic_ppb:.1f} µg/L. This exceeds both the WHO guideline and India's "
            f"IS 10500 limit ({BIS_PERMISSIBLE_LIMIT_UG_L:.0f} µg/L, no relaxation since 2015).{semi}"
        )
        action = ("Do not use for drinking or cooking. Switch to a tested safe source and send a sample to an "
                  "accredited lab (ICP-MS or HG-AAS).")

    # 5. Acute Toxic Hazard (> 150 µg/L)
    else:
        status = (
            AnalyticalStatus.ABOVE_CALIBRATED_RANGE
            if arsenic_ppb > CAL_MAX_UG_L
            else AnalyticalStatus.WITHIN_CALIBRATED_RANGE
        )
        tier = RegulatoryTier.HAZARDOUS
        severity = 3
        tone = "critical"
        is_safe = False
        uncertainty = 15.0 if arsenic_ppb <= CAL_MAX_UG_L else 50.0
        label = "Hazardous (Critical Toxicity)"
        over_range_note = f" (Sample exceeds calibrated range of {CAL_MAX_UG_L:.0f} µg/L; dilution required)" if arsenic_ppb > CAL_MAX_UG_L else ""
        message = (
            f"Arsenic level ({arsenic_ppb:.1f} µg/L) is critically high (>150 µg/L){over_range_note}. "
            f"Severe risk of acute and chronic arsenic toxicity."
        )
        action = "IMMEDIATE PUBLIC HEALTH ALERT: Seal water source immediately. Laboratory confirmation dispatched."

    disclaimer = (
        "SCREENING ADVISORY: This estimate is produced by a field screening prototype. "
        "It does not substitute for certified NABL / ISO-17025 accredited laboratory analysis."
    )
    provenance = f"{METHOD_NAME} | Calibration: {CALIBRATION_ID} | Source: {source_type.value}"

    return ScientificAssessment(
        measured_arsenic_ppb=round(arsenic_ppb, 2),
        measured_arsenic_mg_l=as_mg_l,
        analytical_status=status,
        regulatory_tier=tier,
        severity=severity,
        status_label=label,
        status_tone=tone,
        is_safe_to_drink=is_safe,
        confidence_pct=conf,
        uncertainty_ppb=uncertainty,
        message=message,
        action=action,
        potability_disclaimer=disclaimer,
        method_provenance=provenance,
    )
