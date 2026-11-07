"""
Pydantic schemas: define validated shapes accepted and returned by the API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ---------- Incoming: what the Arduino / bridge sends ----------

class ReadingCreate(BaseModel):
    device_code: str = Field(..., description="Unique ID of the robot, e.g. 'AQUA-001'", min_length=2, max_length=64)
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

    source_type: Optional[str] = Field("simulated", description="simulated | hardware | manual_import | synthetic_fixture")
    idempotency_key: Optional[str] = Field(None, max_length=64, description="Unique client transmission ID to prevent duplicates")

    recorded_at: Optional[datetime] = Field(
        None, description="Timestamp the sample was taken. Defaults to server UTC if omitted."
    )
    raw_payload: Optional[str] = Field(
        None, description="Original raw payload string received over Bluetooth/serial for audit lineage."
    )


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
    recorded_at: datetime
    received_at: datetime


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
