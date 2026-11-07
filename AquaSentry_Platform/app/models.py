"""
SQLAlchemy ORM models for AquaSentry.

Tables:
- Device                 : physical robot / probe unit registry
- Reading                : water sample / arsenic measurement event (backwards-compatible)
- Sample                 : canonical multi-analyte water sample session container
- AnalyteResult          : individual contaminant concentration measurement
- RawVoltammetryTrace    : raw electrochemical potential & current array evidence
- CalibrationRecord      : versioned analytical calibration curve registry
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
    first_seen = Column(DateTime, default=utc_now)
    last_seen = Column(DateTime, default=utc_now)

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

    # --- Bookkeeping & Raw Evidence ---
    recorded_at = Column(DateTime, default=utc_now, index=True)
    received_at = Column(DateTime, default=utc_now)
    raw_payload = Column(Text, nullable=True)  # original unparsed payload

    device = relationship("Device", back_populates="readings")


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
