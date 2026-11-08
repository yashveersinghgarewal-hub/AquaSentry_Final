"""
SQLAlchemy ORM models for AquaSentry.

Tables:
- Device                 : physical robot / probe unit registry
- Reading                : water sample / arsenic measurement event (backwards-compatible)
- Sample                 : canonical multi-analyte water sample session container
- AnalyteResult          : individual contaminant concentration measurement
- RawVoltammetryTrace    : raw electrochemical potential & current array evidence
- CalibrationRecord      : versioned analytical calibration curve registry (per device / electrode lot)
- LabResult              : accredited-lab confirmation of a node's sample (ICP-MS, HG-AAS, field kit)
- AlertSubscription      : who gets alerts, by web push, WhatsApp or SMS
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy import Index
from sqlalchemy.orm import relationship

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=True)
    location_label = Column(String(128), nullable=True)  # e.g. "Powai Lake North"
    firmware_version = Column(String(32), default="v1.0.0")
    status = Column(String(32), default="online")        # online | offline | maintenance
    api_key_hash = Column(String(64), nullable=True)     # SHA-256 of the device's own API key (never the key)
    api_key_hint = Column(String(16), nullable=True)     # first characters, to tell keys apart
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)

    # --- Site (v5.6): where the node draws water from, for the map and Jal Jeevan Mission style reports ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    state = Column(String(64), nullable=True)
    district = Column(String(64), nullable=True)
    block = Column(String(64), nullable=True)
    panchayat = Column(String(64), nullable=True)
    village = Column(String(64), nullable=True)
    source_kind = Column(String(32), nullable=True)      # handpump | tubewell | borewell | piped | open_well | surface | other

    readings = relationship(
        "Reading", back_populates="device", cascade="all, delete-orphan"
    )
    samples = relationship(
        "Sample", back_populates="device", cascade="all, delete-orphan"
    )


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    # --- Core analytical measurement ---
    arsenic_ppb = Column(Float, nullable=False)          # micrograms per litre (µg/L)
    classification = Column(String(32), nullable=False)  # Safe | Caution | Unsafe | Hazardous | Below LOD
    analytical_status = Column(String(64), default="within_calibrated_range") # below_detection_limit | within_calibrated_range | etc.
    regulatory_tier = Column(String(64), default="Caution")
    is_safe_to_drink = Column(Boolean, nullable=True)     # False if unsafe; None if unverified below LOD
    uncertainty_ppb = Column(Float, nullable=True)       # +/- uncertainty
    confidence = Column(Float, nullable=True)            # 0.0 to 1.0 (model/sensor confidence)

    # --- Data provenance & simulation tracking ---
    source_type = Column(String(32), default="simulated", index=True) # simulated | hardware | manual_import
    is_simulated = Column(Boolean, default=True, index=True)
    method_version = Column(String(32), default="MAS-G1-v1.2")
    model_version = Column(String(32), default="AquaNet-V1")
    idempotency_key = Column(String(64), nullable=True, index=True)

    # --- Supporting water-quality context ---
    ph = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    conductivity_us_cm = Column(Float, nullable=True)
    turbidity_ntu = Column(Float, nullable=True)
    dissolved_oxygen_mg_l = Column(Float, nullable=True)

    # --- Geo / Trace ---
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # --- Device & telemetry status ---
    battery_pct = Column(Float, nullable=True)
    source_label = Column(String(64), nullable=True)

    # --- Measurement quality (v5.6) ---
    arsenic_species = Column(String(16), nullable=True)   # total | as3_only | unknown (what the method can see)
    cu_peak_ua = Column(Float, nullable=True)             # copper stripping peak, if the node scanned for it
    qc_flags = Column(String(128), nullable=True)         # comma list, e.g. "copper_interference"
    qc_status = Column(String(16), nullable=True)         # v5.7: pass | warning | fail (hardware readings)
    time_source = Column(String(24), nullable=True)       # v5.7: device_clock | device_age | unknown | server_receipt
    calibration_ref = Column(String(64), nullable=True)   # calibration_id the node used

    # --- Bookkeeping & Raw Evidence ---
    recorded_at = Column(DateTime, default=utc_now, index=True)
    received_at = Column(DateTime, default=utc_now)
    raw_payload = Column(Text, nullable=True)  # original unparsed payload

    device = relationship("Device", back_populates="readings")

    __table_args__ = (Index("ix_readings_device_recorded", "device_id", "recorded_at"),)

    @property
    def device_code(self):
        """v5.7: returned with every reading, so the dashboard shows the right device."""
        return self.device.device_code if self.device is not None else None


class Sample(Base):
    """Normalized Sample event container supporting multi-analyte observations."""
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, index=True)
    sample_uuid = Column(String(64), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    site_label = Column(String(128), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    source_type = Column(String(32), default="simulated", index=True) # physical_sensor | synthetic_demo | manual_import
    evidence_status = Column(String(32), default="screening_prototype")
    collection_time = Column(DateTime, default=utc_now, index=True)
    received_time = Column(DateTime, default=utc_now)
    water_matrix = Column(String(64), default="groundwater") # groundwater | surface_water | tap | treated

    # Water-quality physical matrix
    ph = Column(Float, nullable=True)
    conductivity_us_cm = Column(Float, nullable=True)
    turbidity_ntu = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    dissolved_oxygen_mg_l = Column(Float, nullable=True)

    device = relationship("Device", back_populates="samples")
    analyte_results = relationship("AnalyteResult", back_populates="sample", cascade="all, delete-orphan")
    traces = relationship("RawVoltammetryTrace", back_populates="sample", cascade="all, delete-orphan")


class AnalyteResult(Base):
    """Individual contaminant determination linked to a parent sample."""
    __tablename__ = "analyte_results"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False, index=True)
    analyte_identifier = Column(String(64), nullable=False, index=True) # arsenic | lead | cadmium etc.
    method_identifier = Column(String(64), default="ASV-MAS-G1")
    concentration_ug_l = Column(Float, nullable=False)
    concentration_mg_l = Column(Float, nullable=False)
    uncertainty_ug_l = Column(Float, nullable=True)
    lod_ug_l = Column(Float, nullable=False, default=20.0)
    loq_ug_l = Column(Float, nullable=False, default=30.0)
    analytical_status = Column(String(64), default="within_calibrated_range")
    regulatory_tier = Column(String(64), default="Caution")
    is_safe_to_drink = Column(Boolean, nullable=True)
    is_below_lod = Column(Boolean, default=False)
    qc_flag = Column(String(64), default="PASS")
    recorded_at = Column(DateTime, default=utc_now)

    sample = relationship("Sample", back_populates="analyte_results")


class RawVoltammetryTrace(Base):
    """Immutable electrochemical signal observation trace."""
    __tablename__ = "raw_voltammetry_traces"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=True, index=True)
    trace_uuid = Column(String(64), unique=True, default=lambda: str(uuid.uuid4()))
    analyte_identifier = Column(String(64), default="arsenic")
    scan_rate_mv_s = Column(Float, default=50.0)
    deposition_time_s = Column(Float, default=120.0)
    deposition_potential_mv = Column(Float, default=-1100.0)
    peak_potential_mv = Column(Float, default=-800.0)
    measured_peak_current_ua = Column(Float, nullable=True)
    snr = Column(Float, nullable=True)
    electrode_lot = Column(String(64), default="MAS-G1-2026A")
    raw_potentials_json = Column(Text, nullable=False) # JSON array of potentials
    raw_currents_json = Column(Text, nullable=False)   # JSON array of currents
    is_synthetic = Column(Boolean, default=True)
    recorded_at = Column(DateTime, default=utc_now)

    sample = relationship("Sample", back_populates="traces")


class CalibrationRecord(Base):
    """Audit record of analytical calibration curves."""
    __tablename__ = "calibration_records"

    id = Column(Integer, primary_key=True, index=True)
    calibration_id = Column(String(64), unique=True, index=True)
    analyte_identifier = Column(String(64), default="arsenic")
    slope = Column(Float, nullable=False)
    intercept = Column(Float, nullable=False)
    r_squared = Column(Float, nullable=False)
    lod_ug_l = Column(Float, nullable=False)
    loq_ug_l = Column(Float, nullable=False)
    cal_range_min_ug_l = Column(Float, nullable=False)
    cal_range_max_ug_l = Column(Float, nullable=False)
    calibration_date = Column(DateTime, default=utc_now)
    is_active = Column(Boolean, default=True)
    approved_by = Column(String(64), default="Scientific QA Lead")
    # v5.6: calibrations can belong to one node or one electrode batch, and record how they were made
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    electrode_lot = Column(String(64), nullable=True)
    method = Column(String(32), default="external_standards")   # external_standards | standard_addition
    points_json = Column(Text, nullable=True)                    # the (added µg/L, peak µA) points used
    notes = Column(Text, nullable=True)


class LabResult(Base):
    """A laboratory (or official field-test-kit) result for water a node also measured. Pairs of node
    reading + lab result are how the sensor's real accuracy is established."""
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    reading_id = Column(Integer, ForeignKey("readings.id"), nullable=True)   # the node reading it confirms
    sample_code = Column(String(64), nullable=True)                          # lab's sample number
    sampled_at = Column(DateTime, nullable=False, default=utc_now)
    lab_name = Column(String(128), nullable=True)
    lab_method = Column(String(32), nullable=False, default="ICP-MS")        # ICP-MS | HG-AAS | GF-AAS | FTK | other
    arsenic_ug_l = Column(Float, nullable=False)
    as3_ug_l = Column(Float, nullable=True)                                  # As(III) only, if the lab speciated
    nabl_accredited = Column(Boolean, nullable=True)
    notes = Column(Text, nullable=True)
    entered_at = Column(DateTime, default=utc_now)

    device = relationship("Device")
    reading = relationship("Reading")


class AlertSubscription(Base):
    """Someone who wants Unsafe / Hazardous alerts: a browser (web push), a WhatsApp number or an SMS number."""
    __tablename__ = "alert_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String(16), nullable=False)           # webpush | whatsapp | sms
    target = Column(Text, nullable=False)                  # push subscription JSON, or E.164 phone number
    target_hash = Column(String(64), unique=True, index=True, nullable=False)
    device_code = Column(String(64), nullable=True)        # None = every node
    min_level = Column(String(16), default="CRITICAL")     # CRITICAL (Unsafe/Hazardous) | WARNING (also trends)
    language = Column(String(8), default="en")
    label = Column(String(64), nullable=True)              # e.g. "Gram panchayat office"
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    last_sent_at = Column(DateTime, nullable=True)
    last_error = Column(String(255), nullable=True)
    failures = Column(Integer, default=0)


class QcRun(Base):
    """v5.7: a blank or check-standard run. Proves the sensor still reads correctly (catches drift and dead
    electrodes, which read LOW and would otherwise look like clean water)."""
    __tablename__ = "qc_runs"

    id = Column(Integer, primary_key=True, index=True)
    device_code = Column(String(64), index=True, nullable=False)
    run_type = Column(String(24), nullable=False)          # blank | check_standard
    expected_ug_l = Column(Float, nullable=True)           # true value of the check standard (0 for a blank)
    measured_ug_l = Column(Float, nullable=True)
    peak_current_ua = Column(Float, nullable=True)
    recovery_pct = Column(Float, nullable=True)
    passed = Column(Boolean, nullable=False)
    detail = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=utc_now, index=True)
