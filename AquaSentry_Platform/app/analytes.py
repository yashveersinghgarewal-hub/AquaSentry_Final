"""
AquaSentry Multi-Contaminant & Analyte Registry.

Defines the canonical catalog of water quality contaminants, sensing capabilities,
analytical methods, regulatory thresholds, and detection boundaries.

SCIENTIFIC INTEGRITY ENFORCEMENT:
AquaSentry's current autonomous hardware prototype physically features an
Anodic Stripping Voltammetry (ASV) sensor specifically functionalized for Arsenic (As).
Other contaminants (e.g., Lead, Cadmium, Mercury, Chromium, Fluoride) are explicitly
cataloged as 'Planned', 'Experimental', or 'Requires Laboratory Confirmation' so the UI
and API never falsely claim that a single sensor detects every chemical species.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class AnalyteSupportStatus(str, Enum):
    SUPPORTED_SCREENING = "supported_screening"       # Autonomous field screening verified
    EXPERIMENTAL = "experimental"                     # Lab prototype / bench validation in progress
    PLANNED = "planned"                               # Roadmap / requires dedicated sensor driver
    LAB_REFERENCE_ONLY = "lab_reference_only"         # Requires external laboratory instrumentation (e.g. ICP-MS)


class SensingModality(str, Enum):
    ASV_CARBON_STRIP = "asv_carbon_strip"             # Anodic Stripping Voltammetry on Screen-Printed Carbon
    ASV_BISMUTH_FILM = "asv_bismuth_film"             # ASV on Bismuth Modified Electrode
    ASV_GOLD_FILM = "asv_gold_film"                   # ASV on Gold Microelectrode
    ION_SELECTIVE = "ion_selective_electrode"         # Potentiometric ISE (Fluoride, Nitrate)
    OPTICAL_COLORIMETRIC = "optical_colorimetric"     # Photometric / Colorimetric Reagent
    ELECTROCHEMICAL_PROBE = "electrochemical_probe"   # Galvanic / Amperometric (pH, DO, EC)
    EXTERNAL_LAB_ICP = "external_lab_icp_ms"          # Inductively Coupled Plasma Mass Spectrometry


@dataclass(frozen=True)
class RegulatoryLimit:
    standard_name: str
    jurisdiction: str
    acceptable_limit: float
    permissible_limit: Optional[float]
    unit: str
    citation: str
    effective_edition: str


@dataclass(frozen=True)
class AnalyteCapability:
    identifier: str
    name: str
    chemical_formula: str
    support_status: AnalyteSupportStatus
    modality: SensingModality
    method_name: str
    sensor_model: str
    canonical_unit: str
    lod_ug_l: Optional[float]                         # Limit of Detection in µg/L
    loq_ug_l: Optional[float]                         # Limit of Quantification in µg/L
    cal_range_min_ug_l: Optional[float]
    cal_range_max_ug_l: Optional[float]
    sample_prep_required: str
    known_interferences: List[str]
    standards: Dict[str, RegulatoryLimit]
    health_significance: str
    operational_notes: str
    is_actively_monitored_by_hardware: bool = False


# ==============================================================================
# CANONICAL ANALYTE CATALOG
# ==============================================================================

ANALYTE_REGISTRY: Dict[str, AnalyteCapability] = {
    "arsenic": AnalyteCapability(
        identifier="arsenic",
        name="Total Dissolved Arsenic",
        chemical_formula="As (As(III) / As(V))",
        support_status=AnalyteSupportStatus.SUPPORTED_SCREENING,
        modality=SensingModality.ASV_CARBON_STRIP,
        method_name="Anodic Stripping Voltammetry (ASV) - MAS-G1 Protocol",
        sensor_model="MAS-G1 As-M003050 (Gold/Bismuth Modified Carbon)",
        canonical_unit="µg/L",
        lod_ug_l=20.0,
        loq_ug_l=30.0,
        cal_range_min_ug_l=30.0,
        cal_range_max_ug_l=500.0,
        sample_prep_required="Pre-reduction buffer (0.1M HCl + ascorbic acid) for total dissolved As.",
        known_interferences=["Copper (Cu²⁺ > 50 µg/L)", "Lead (Pb²⁺ > 100 µg/L)", "High organic matter/humic acids"],
        standards={
            "who": RegulatoryLimit(
                standard_name="WHO Guidelines for Drinking-water Quality",
                jurisdiction="International",
                acceptable_limit=10.0,
                permissible_limit=None,
                unit="µg/L",
                citation="WHO GDWQ 4th Edition (2017) / 2022 Addenda",
                effective_edition="4th Ed with Addenda",
            ),
            "bis_10500": RegulatoryLimit(
                standard_name="IS 10500:2012 Drinking Water Specification",
                jurisdiction="India",
                acceptable_limit=10.0,
                permissible_limit=10.0,  # Amendment No. 1 (2015): "no relaxation" (was 50)
                unit="µg/L",
                citation="Bureau of Indian Standards IS 10500:2012 (Second Revision), Amendment No. 1 (2015)",
                effective_edition="IS 10500:2012 reaffirmed 2018",
            ),
            "us_epa": RegulatoryLimit(
                standard_name="US EPA National Primary Drinking Water Regulations",
                jurisdiction="United States",
                acceptable_limit=10.0,
                permissible_limit=10.0,
                unit="µg/L",
                citation="40 CFR Part 141 (Safe Drinking Water Act)",
                effective_edition="Current Standard",
            ),
        },
        health_significance="Group 1 human carcinogen. Chronic exposure causes arsenicosis, skin keratosis, cardiovascular and neurological disease.",
        operational_notes="Screening sensor active on AquaSentry catamaran. Because LOD (20 µg/L) > WHO guideline (10 µg/L), readings <20 µg/L cannot certify compliance with WHO 10 µg/L.",
        is_actively_monitored_by_hardware=True,
    ),

    "lead": AnalyteCapability(
        identifier="lead",
        name="Dissolved Lead",
        chemical_formula="Pb (Pb²⁺)",
        support_status=AnalyteSupportStatus.PLANNED,
        modality=SensingModality.ASV_BISMUTH_FILM,
        method_name="Differential Pulse ASV (DP-ASV) at -450 mV Peak",
        sensor_model="Planned Pb-02 Bismuth-film Sensor",
        canonical_unit="µg/L",
        lod_ug_l=5.0,
        loq_ug_l=10.0,
        cal_range_min_ug_l=10.0,
        cal_range_max_ug_l=100.0,
        sample_prep_required="Acetate buffer (pH 4.5); in-situ bismuth plating solution.",
        known_interferences=["Cadmium (Cd²⁺ overlap at -600 mV)", "Copper (Cu²⁺ stripping interference)"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 10.0, None, "µg/L", "WHO GDWQ 4th Ed", "2017"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 10.0, None, "µg/L", "IS 10500:2012", "2012"),
            "us_epa": RegulatoryLimit("US EPA Action Level", "United States", 15.0, 15.0, "µg/L", "Lead & Copper Rule", "2021"),
        },
        health_significance="Potent neurotoxin, especially damaging to fetal and childhood brain development, cognitive function, and kidney function.",
        operational_notes="Hardware adapter in development. Not measurable by current MAS-G1 arsenic strip.",
        is_actively_monitored_by_hardware=False,
    ),

    "cadmium": AnalyteCapability(
        identifier="cadmium",
        name="Dissolved Cadmium",
        chemical_formula="Cd (Cd²⁺)",
        support_status=AnalyteSupportStatus.PLANNED,
        modality=SensingModality.ASV_BISMUTH_FILM,
        method_name="DP-ASV at -600 mV Peak",
        sensor_model="Planned Cd-01 Sensor Module",
        canonical_unit="µg/L",
        lod_ug_l=1.0,
        loq_ug_l=3.0,
        cal_range_min_ug_l=3.0,
        cal_range_max_ug_l=50.0,
        sample_prep_required="Acetate buffer (pH 4.6).",
        known_interferences=["Lead (Pb²⁺ proximity)", "Thallium"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 3.0, None, "µg/L", "WHO GDWQ 4th Ed", "2017"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 3.0, None, "µg/L", "IS 10500:2012", "2012"),
        },
        health_significance="Kidney damage, bone demineralization (Itai-Itai disease), classified as human carcinogen.",
        operational_notes="Requires future dual-analyte stripping waveform controller.",
        is_actively_monitored_by_hardware=False,
    ),

    "mercury": AnalyteCapability(
        identifier="mercury",
        name="Total Dissolved Mercury",
        chemical_formula="Hg (Hg²⁺)",
        support_status=AnalyteSupportStatus.EXPERIMENTAL,
        modality=SensingModality.ASV_GOLD_FILM,
        method_name="Square Wave ASV on Gold Microelectrode Array",
        sensor_model="Experimental Au-Array Hg-X1",
        canonical_unit="µg/L",
        lod_ug_l=0.5,
        loq_ug_l=1.5,
        cal_range_min_ug_l=1.5,
        cal_range_max_ug_l=20.0,
        sample_prep_required="Strong acid digestion (0.5M HNO3) and chlorine pre-conditioning.",
        known_interferences=["Silver (Ag⁺)", "Copper (Cu²⁺)", "Halide precipitation"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 6.0, None, "µg/L", "WHO GDWQ 4th Ed", "2017 (Inorganic)"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 1.0, None, "µg/L", "IS 10500:2012", "2012"),
        },
        health_significance="Severe central nervous system toxicity, sensory impairment, kidney damage.",
        operational_notes="Currently restricted to bench laboratory validation due to gold surface passivization.",
        is_actively_monitored_by_hardware=False,
    ),

    "chromium_total": AnalyteCapability(
        identifier="chromium_total",
        name="Total Chromium",
        chemical_formula="Cr (Total Cr)",
        support_status=AnalyteSupportStatus.LAB_REFERENCE_ONLY,
        modality=SensingModality.EXTERNAL_LAB_ICP,
        method_name="Standard Methods 3120B / ICP-MS",
        sensor_model="External Laboratory ICP-MS",
        canonical_unit="µg/L",
        lod_ug_l=0.2,
        loq_ug_l=1.0,
        cal_range_min_ug_l=1.0,
        cal_range_max_ug_l=200.0,
        sample_prep_required="Nitric acid preservation to pH < 2.",
        known_interferences=["Iron spectral overlaps in optical ICP"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 50.0, None, "µg/L", "WHO GDWQ 4th Ed", "2017"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 50.0, None, "µg/L", "IS 10500:2012", "2012"),
        },
        health_significance="Dermatitis, allergic reactions; chronic industrial contamination indicator.",
        operational_notes="Speciation required to distinguish benign Cr(III) from toxic Cr(VI).",
        is_actively_monitored_by_hardware=False,
    ),

    "chromium_vi": AnalyteCapability(
        identifier="chromium_vi",
        name="Hexavalent Chromium",
        chemical_formula="Cr(VI) (CrO₄²⁻ / Cr₂O₇²⁻)",
        support_status=AnalyteSupportStatus.PLANNED,
        modality=SensingModality.OPTICAL_COLORIMETRIC,
        method_name="Diphenylcarbazide (DPC) Colorimetry at 540 nm",
        sensor_model="Planned Microfluidic DPC Colorimeter",
        canonical_unit="µg/L",
        lod_ug_l=2.0,
        loq_ug_l=5.0,
        cal_range_min_ug_l=5.0,
        cal_range_max_ug_l=100.0,
        sample_prep_required="Acidification with phosphoric acid and addition of 1,5-diphenylcarbazide.",
        known_interferences=["Iron (Fe³⁺)", "Molybdenum", "Vanadium"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 50.0, None, "µg/L", "WHO Guideline for Total Cr covers Cr(VI)", "2017"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 50.0, None, "µg/L", "Covered under Total Cr limit", "2012"),
        },
        health_significance="Known human carcinogen (pulmonary, gastrointestinal), mutagenic and corrosive.",
        operational_notes="Requires microfluidic reagent cartridge not present on current prototype.",
        is_actively_monitored_by_hardware=False,
    ),

    "fluoride": AnalyteCapability(
        identifier="fluoride",
        name="Fluoride Ion",
        chemical_formula="F⁻",
        support_status=AnalyteSupportStatus.PLANNED,
        modality=SensingModality.ION_SELECTIVE,
        method_name="Lanthanum Fluoride Single Crystal ISE",
        sensor_model="Planned LaF3 Solid-State Probe",
        canonical_unit="mg/L",
        lod_ug_l=100.0,  # 0.1 mg/L
        loq_ug_l=200.0,  # 0.2 mg/L
        cal_range_min_ug_l=200.0,
        cal_range_max_ug_l=10000.0, # 0.2 to 10 mg/L
        sample_prep_required="TISAB buffer addition to buffer pH and decomplex fluoride.",
        known_interferences=["Hydroxide (OH⁻ at pH > 8.5)", "Aluminum complexes"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 1.5, None, "mg/L", "WHO GDWQ 4th Ed", "2017"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 1.0, 1.5, "mg/L", "IS 10500:2012", "2012"),
        },
        health_significance="Excess fluoride (>1.5 mg/L) causes dental fluorosis and crippling skeletal fluorosis.",
        operational_notes="Groundwater co-contaminant commonly co-occurring with arsenic in endemic regions of India.",
        is_actively_monitored_by_hardware=False,
    ),

    "nitrate": AnalyteCapability(
        identifier="nitrate",
        name="Nitrate (as NO₃)",
        chemical_formula="NO₃⁻",
        support_status=AnalyteSupportStatus.PLANNED,
        modality=SensingModality.OPTICAL_COLORIMETRIC,
        method_name="Cadmium Reduction / Direct UV Absorbance (220 nm)",
        sensor_model="Planned Dual-UV Absorbance Probe",
        canonical_unit="mg/L",
        lod_ug_l=500.0,   # 0.5 mg/L
        loq_ug_l=1000.0,  # 1.0 mg/L
        cal_range_min_ug_l=1000.0,
        cal_range_max_ug_l=100000.0, # 1.0 to 100 mg/L
        sample_prep_required="Filtration to remove turbidity interference; organic carbon compensation at 275 nm.",
        known_interferences=["Dissolved organic carbon", "Nitrite", "High chloride"],
        standards={
            "who": RegulatoryLimit("WHO GDWQ", "International", 50.0, None, "mg/L", "WHO GDWQ 4th Ed", "2017"),
            "bis_10500": RegulatoryLimit("IS 10500:2012", "India", 45.0, None, "mg/L", "IS 10500:2012", "2012"),
        },
        health_significance="Methemoglobinemia ('blue baby syndrome') in infants; agricultural runoff indicator.",
        operational_notes="Planned optical absorption channel for catchment-wide agricultural surveillance.",
        is_actively_monitored_by_hardware=False,
    ),
}


def get_analyte_profile(analyte_id: str) -> Optional[AnalyteCapability]:
    """Retrieve capability metadata for a registered analyte."""
    return ANALYTE_REGISTRY.get(analyte_id.lower().strip())


def list_supported_analytes() -> List[AnalyteCapability]:
    """Return all analytes registered in the system."""
    return list(ANALYTE_REGISTRY.values())


def list_hardware_active_analytes() -> List[AnalyteCapability]:
    """Return only analytes that are physically measurable by the current robot hardware."""
    return [a for a in ANALYTE_REGISTRY.values() if a.is_actively_monitored_by_hardware]


def evaluate_analyte_concentration(
    analyte_id: str,
    concentration_ug_l: float,
    jurisdiction: str = "who"
) -> Dict:
    """
    Evaluate a contaminant concentration against its authoritative standards and LOD.
    Returns status, severity, whether below LOD, and guidance.
    """
    analyte = get_analyte_profile(analyte_id)
    if not analyte:
        return {
            "error": f"Analyte '{analyte_id}' is not in the recognized registry.",
            "is_valid": False,
        }

    std = analyte.standards.get(jurisdiction.lower()) or analyte.standards.get("who")
    limit_acceptable = std.acceptable_limit if std else 10.0
    limit_permissible = std.permissible_limit if (std and std.permissible_limit) else limit_acceptable

    # Check against LOD
    is_below_lod = analyte.lod_ug_l is not None and concentration_ug_l < analyte.lod_ug_l
    is_above_cal = analyte.cal_range_max_ug_l is not None and concentration_ug_l > analyte.cal_range_max_ug_l

    if is_below_lod:
        # Check if LOD is above acceptable standard (as in Arsenic!)
        lod_exceeds_standard = analyte.lod_ug_l is not None and analyte.lod_ug_l > limit_acceptable
        return {
            "analyte": analyte.name,
            "status": "below_detection_limit",
            "tier": "Unverified (Below LOD)" if lod_exceeds_standard else "Pass",
            "severity": 0,
            "is_safe": None if lod_exceeds_standard else True,
            "is_below_lod": True,
            "lod_ug_l": analyte.lod_ug_l,
            "threshold_ug_l": limit_acceptable,
            "standard_cited": std.standard_name if std else "WHO GDWQ",
            "message": (
                f"Concentration (<{analyte.lod_ug_l} µg/L) is below method detection limit. "
                + (f"Note: Sensor LOD ({analyte.lod_ug_l} µg/L) is above guideline ({limit_acceptable} µg/L); lab testing required for certification." if lod_exceeds_standard else "Sample meets health guideline limit.")
            ),
        }
    elif concentration_ug_l <= limit_acceptable:
        return {
            "analyte": analyte.name,
            "status": "within_calibrated_range",
            "tier": "Acceptable",
            "severity": 0,
            "is_safe": True,
            "is_below_lod": False,
            "lod_ug_l": analyte.lod_ug_l,
            "threshold_ug_l": limit_acceptable,
            "standard_cited": std.standard_name if std else "WHO GDWQ",
            "message": f"Concentration ({concentration_ug_l:.1f} µg/L) meets the {std.standard_name if std else 'WHO'} acceptable guideline.",
        }
    elif concentration_ug_l <= limit_permissible:
        return {
            "analyte": analyte.name,
            "status": "within_calibrated_range",
            "tier": "Caution (Permissible)",
            "severity": 1,
            "is_safe": False,
            "is_below_lod": False,
            "lod_ug_l": analyte.lod_ug_l,
            "threshold_ug_l": limit_permissible,
            "standard_cited": std.standard_name if std else "BIS 10500",
            "message": f"Concentration ({concentration_ug_l:.1f} µg/L) exceeds ideal guideline ({limit_acceptable} µg/L) but is within permissible limits ({limit_permissible} µg/L) if no alternative source exists.",
        }
    else:
        # Arsenic uses the same 150 µg/L acute-hazard level as the rest of the system; others keep 3x the limit.
        hazard_at = 150.0 if analyte.identifier == "arsenic" else limit_permissible * 3.0
        return {
            "analyte": analyte.name,
            "status": "above_calibrated_range" if is_above_cal else "within_calibrated_range",
            "tier": "Hazardous" if concentration_ug_l > hazard_at else "Unsafe (Exceeds Limit)",
            "severity": 3 if concentration_ug_l > hazard_at else 2,
            "is_safe": False,
            "is_below_lod": False,
            "lod_ug_l": analyte.lod_ug_l,
            "threshold_ug_l": limit_permissible,
            "standard_cited": std.standard_name if std else "Regulatory Limit",
            "message": f"Concentration ({concentration_ug_l:.1f} µg/L) exceeds permissible limits ({limit_permissible} µg/L). Ingestion unadvised without specialized treatment.",
        }
