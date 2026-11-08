"""
Pydantic schemas: define validated shapes accepted and returned by the API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from datetime import timezone
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


# ---------- Incoming: what the Arduino / bridge sends ----------

class ReadingCreate(BaseModel):
    device_code: str = Field(..., description="Unique ID of the robot, e.g. 'AQUA-001'", min_length=2, max_length=64,
                             pattern=r"^[A-Za-z0-9_.:-]{2,64}$")
    arsenic_ppb: Optional[float] = Field(None, ge=0, le=50000, description="Measured arsenic concentration in µg/L (ppb)")
    arsenic_concentration_mg_l: Optional[float] = Field(None, ge=0, le=50.0, description="Measured arsenic concentration in mg/L")

    @model_validator(mode="before")
    @classmethod
    def check_arsenic_inputs(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ppb = data.get("arsenic_ppb")
            mg_l = data.get("arsenic_concentration_mg_l")
            if ppb is None and mg_l is not None:
                data["arsenic_ppb"] = round(float(mg_l) * 1000.0, 4)
            elif ppb is None and mg_l is None:
                raise ValueError("Either 'arsenic_ppb' or 'arsenic_concentration_mg_l' must be provided.")
        return data

    ph: Optional[float] = Field(None, ge=0, le=14, description="Water pH (0-14)")
    temperature_c: Optional[float] = Field(None, ge=-10, le=60, description="Water temperature in °C")
    conductivity_us_cm: Optional[float] = Field(None, ge=0, le=50000, description="Electrical conductivity in µS/cm")
    turbidity_ntu: Optional[float] = Field(None, ge=0, le=1000, description="Turbidity in NTU")
    dissolved_oxygen_mg_l: Optional[float] = Field(None, ge=0, le=50, description="Dissolved oxygen in mg/L")

    latitude: Optional[float] = Field(None, ge=-90, le=90, description="GPS Latitude in degrees")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="GPS Longitude in degrees")

    confidence: Optional[float] = Field(None, ge=0, le=1, description="Analytical/sensor confidence score 0.0-1.0")
    battery_pct: Optional[float] = Field(None, ge=0, le=100, description="Battery state of charge 0-100%")
    source_label: Optional[str] = Field(None, max_length=64, description="Sampling station or sector label")

    source_type: Optional[Literal["simulated", "hardware", "manual_import", "synthetic_fixture", "synthetic_demo"]] = Field(
        "simulated", description="simulated | hardware | manual_import | synthetic_fixture | synthetic_demo")
    idempotency_key: Optional[str] = Field(None, max_length=64, description="Unique client transmission ID to prevent duplicates")

    recorded_at: Optional[datetime] = Field(
        None, description="Timestamp the sample was taken. Defaults to server UTC if omitted."
    )
    raw_payload: Optional[str] = Field(
        None, description="Original raw payload string received over Bluetooth/serial for audit lineage."
    )
    firmware_version: Optional[str] = Field(None, max_length=32, description="Firmware version reported by the device")
    # v5.6 measurement quality
    arsenic_species: Optional[Literal["total", "as3_only", "unknown"]] = Field(
        None, description="What the method can see: total arsenic (acid + reductant step) or As(III) only")
    peak_current_ua: Optional[float] = Field(None, ge=-1000, le=1000, description="Net arsenic stripping peak (µA)")
    cu_peak_ua: Optional[float] = Field(None, ge=0, le=1000, description="Copper stripping peak (µA), if scanned")
    calibration_ref: Optional[str] = Field(None, max_length=64, description="calibration_id the node used")
    # v5.7 scan quality and timing, reported by the device (qc_status is required for hardware readings)
    qc_status: Optional[Literal["pass", "fail"]] = Field(
        None, description="Result of the device's own scan checks. Hardware readings without it are 'Test Failed'.")
    qc_scan_flags: Optional[List[str]] = Field(
        None, max_length=20, description="QC codes from the device, e.g. FLAT_SIGNAL, NOISE_ABOVE_LOD, PEAK_SHIFTED")
    snr: Optional[float] = Field(None, ge=0, le=1e6, description="Averaged peak signal-to-noise ratio")
    peak_potential_mv: Optional[float] = Field(None, ge=-2000, le=2000)
    scans_averaged: Optional[int] = Field(None, ge=0, le=100)
    age_seconds: Optional[float] = Field(None, ge=0, le=60 * 60 * 24 * 400,
                                         description="For a device without a set clock: how long ago the sample was taken")

    @field_validator("recorded_at", mode="after")
    @classmethod
    def _recorded_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Store every sample time in UTC. A device clock more than a day in the future is ignored."""
        if v is None:
            return None
        v = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
        from datetime import timedelta as _td
        if v > datetime.now(timezone.utc) + _td(days=1):
            return None
        return v


# ---------- Outgoing: what the API returns ----------

class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    device_id: int
    arsenic_ppb: float
    classification: str
    analytical_status: Optional[str] = "within_calibrated_range"
    regulatory_tier: Optional[str] = "Caution"
    is_safe_to_drink: Optional[bool] = None
    uncertainty_ppb: Optional[float] = None
    confidence: Optional[float] = None

    source_type: Optional[str] = "simulated"
    is_simulated: Optional[bool] = True
    method_version: Optional[str] = "MAS-G1-v1.2"
    model_version: Optional[str] = "AquaNet-V1"

    ph: Optional[float] = None
    temperature_c: Optional[float] = None
    conductivity_us_cm: Optional[float] = None
    turbidity_ntu: Optional[float] = None
    dissolved_oxygen_mg_l: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    battery_pct: Optional[float] = None
    source_label: Optional[str] = None
    arsenic_species: Optional[str] = None
    cu_peak_ua: Optional[float] = None
    qc_flags: Optional[str] = None
    qc_status: Optional[str] = None
    time_source: Optional[str] = None
    calibration_ref: Optional[str] = None
    recorded_at: datetime
    received_at: datetime

    @field_validator("recorded_at", "received_at", mode="after")
    @classmethod
    def _as_utc(cls, v: datetime) -> datetime:
        """SQLite hands back naive datetimes; they are UTC, so say so (the JSON then ends in +00:00)."""
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


class ReadingResponse(BaseModel):
    reading: ReadingOut
    label: str
    severity: int
    message: str
    action: str
    analytical_status: str
    regulatory_tier: str
    is_safe_to_drink: Optional[bool]
    uncertainty_ppb: float
    is_simulated: bool
    disclaimer: str


class DashboardReading(BaseModel):
    contaminant: str = "Arsenic (As)"
    value: float                       # concentration in mg/L
    value_ppb: float                   # concentration in µg/L
    unit: str = "mg/L"
    safeLimit: float = 0.010           # WHO guideline in mg/L
    confidencePct: Optional[float] = None
    confirmedByHomes: int = 0
    source: str
    detectedAt: str
    detectedAtIso: Optional[str] = None
    batteryPct: Optional[float] = None
    lastPatrolMin: Optional[float] = None
    nextPatrolMin: Optional[int] = None
    classification: str
    analyticalStatus: str
    regulatoryTier: str
    isSafeToDrink: Optional[bool] = None
    isSimulated: bool = True
    isStale: bool = False
    uncertaintyMgL: float = 0.005
    methodLOD: float = 0.020           # 0.02 mg/L
    disclaimer: str

    # snake_case properties for API test contracts
    analytical_status: Optional[str] = None
    regulatory_tier: Optional[str] = None
    is_safe_to_drink: Optional[bool] = None
    is_simulated: Optional[bool] = None
    is_stale: Optional[bool] = None
    uncertainty_ppb: Optional[float] = None
    synapses_count: int = 112
    method_lod_ug_l: float = 20.0
    # v5.6: quality flags and the plain-language caveats that go with them; latest lab confirmation
    qcFlags: List[str] = []
    caveats: List[str] = []
    labConfirmation: Optional[dict] = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_code: str
    name: Optional[str] = None
    location_label: Optional[str] = None
    firmware_version: Optional[str] = "v1.0.0"
    status: Optional[str] = "online"
    first_seen: datetime
    last_seen: datetime


class DeviceLatestOut(BaseModel):
    arsenic_ppb: float
    classification: str
    recorded_at: datetime
    battery_pct: Optional[float] = None


class TrendSummary(BaseModel):
    direction: str                     # rising | falling | no_trend | insufficient_data
    significant: bool = False
    sen_slope_ug_per_week: Optional[float] = None
    p_value: Optional[float] = None
    days_to_next_limit: Optional[float] = None
    next_limit_ug_l: Optional[float] = None
    message: Optional[str] = None


class DeviceStatusOut(BaseModel):
    device_code: str
    firmware_version: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    status: str                        # online | late | offline | demo
    minutes_since_seen: Optional[float] = None
    reading_count: int
    unsafe_count: int
    is_hardware: bool
    has_device_key: bool = False
    trend: Optional[TrendSummary] = None
    latest: Optional[DeviceLatestOut] = None
    site: Optional[dict] = None              # v5.6: name, village, district, lat/lon, source kind
    lab: Optional[dict] = None               # v5.6: latest lab confirmation


class HistoryPoint(BaseModel):
    t: datetime
    ppb: float
    cls: str
    device_code: Optional[str] = None


class StatsOut(BaseModel):
    total_readings: int
    total_devices: int
    average_arsenic_ppb: Optional[float] = None
    hazardous_count: int
    simulated_count: int
    hardware_count: int
    method_lod_ug_l: float = 20.0
    units: str = "µg/L (ppb)"
    timestamp: datetime


class NeuralInferenceResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    predicted_class: str
    confidence_pct: float
    model_version: str
    dataset_provenance: str
    nodes_count: int = 23
    synapses_count: int = 112  # True fully connected edge count: 5*8 + 8*6 + 6*4 = 112
    is_out_of_bounds: bool
    probabilities: Dict[str, float]
    activations: Dict[str, List[float]]
    reason_codes: List[str]
    latency_ms: Optional[float] = 0.45
    disclaimer: str


# ---------- Multi-Analyte Schemas ----------

class RegulatoryLimitOut(BaseModel):
    standard_name: str
    jurisdiction: str
    acceptable_limit: float
    permissible_limit: Optional[float] = None
    unit: str
    citation: str
    effective_edition: str


class AnalyteCapabilityOut(BaseModel):
    identifier: str
    name: str
    chemical_formula: str
    support_status: str
    modality: str
    method_name: str
    sensor_model: str
    canonical_unit: str
    lod_ug_l: Optional[float] = None
    loq_ug_l: Optional[float] = None
    cal_range_min_ug_l: Optional[float] = None
    cal_range_max_ug_l: Optional[float] = None
    sample_prep_required: str
    known_interferences: List[str]
    standards: Dict[str, RegulatoryLimitOut]
    health_significance: str
    operational_notes: str
    is_actively_monitored_by_hardware: bool


# ---------- Voltammetric Signal Processing Schemas ----------

class VoltammetryProcessRequest(BaseModel):
    potentials_mv: List[float] = Field(..., description="Array of potentials in millivolts")
    currents_ua: List[float] = Field(..., description="Array of measured currents in microamperes")
    filter_mode: Optional[str] = Field("savitzky_golay", description="savitzky_golay | rolling_median | raw")
    target_peak_mv: Optional[float] = -800.0
    search_window_mv: Optional[float] = 60.0


class PeakCharacteristicsOut(BaseModel):
    peak_potential_mv: float
    peak_current_raw_ua: float
    baseline_current_ua: float
    net_peak_height_ua: float
    peak_area_ua_mv: float
    half_height_width_mv: float
    snr: float
    baseline_residual_variance: float
    is_valid_peak: bool
    qc_flags: List[str]


class VoltammetryProcessResponse(BaseModel):
    estimated_arsenic_ug_l: float
    estimated_arsenic_mg_l: float
    filter_type: str
    qc_status: str
    qc_messages: List[str]
    peak: Optional[PeakCharacteristicsOut] = None
    raw_potentials_mv: List[float]
    raw_currents_ua: List[float]
    smoothed_currents_ua: List[float]
    baseline_currents_ua: List[float]
    subtracted_currents_ua: List[float]


class SyntheticTraceResponse(BaseModel):
    arsenic_ppb: float
    potentials_mv: List[float]
    currents_ua: List[float]
    method: str = "ASV-MAS-G1 Synthetic Model"
    is_synthetic: bool = True


# ---------- Data Import / Export Schemas ----------

class DataImportPreviewResponse(BaseModel):
    detected_rows: int
    detected_columns: List[str]
    column_mapping: Dict[str, str]
    preview_records: List[Dict[str, Any]]
    validation_errors: List[str]
    is_valid: bool
    source_type_inferred: str


class DataImportCommitRequest(BaseModel):
    records: List[Dict[str, Any]]
    source_type: Optional[str] = "manual_import"
    device_code: Optional[str] = "IMPORT-01"


class DataImportCommitResponse(BaseModel):
    inserted_count: int
    duplicate_count: int
    error_count: int
    status: str
    message: str


# ---------- Chat Schemas ----------

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = "in_scope"
    grounded: Optional[bool] = True


class QcRunCreate(BaseModel):
    """v5.7: a blank (arsenic-free water) or check-standard (known arsenic) run on a device."""
    device_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    run_type: Literal["blank", "check_standard"]
    expected_ug_l: Optional[float] = Field(None, ge=0, le=5000, description="True value of the check standard")
    measured_ug_l: Optional[float] = Field(None, ge=0, le=50000)
    peak_current_ua: Optional[float] = Field(None, ge=-1000, le=1000,
                                             description="If given, arsenic is computed from it with the device's calibration")
    qc_scan_flags: Optional[List[str]] = Field(None, max_length=20)
    recorded_at: Optional[datetime] = None
