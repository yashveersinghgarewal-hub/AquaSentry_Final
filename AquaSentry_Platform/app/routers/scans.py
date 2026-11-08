"""v5.8: native voltammetry scans as evidence (review items 21, 31, 41, 42, 44, 48).

POST /api/scans            the device / bridge / dashboard replay sends the potential and current arrays. The server
                           runs the ONE analysis pipeline (app/signal_processing.py), stores the trace with a SHA-256
                           checksum, the analysis version and the calibration used, and creates the reading from it
                           through the same path as every other reading (QC, check standards, verdict).
GET  /api/scans/{id}       the stored trace plus the processed arrays and features, for the dashboard's trace viewer.
GET  /api/scans            list (by device / reading / sample code).
POST /api/scans/{id}/reprocess   recompute the result from the original trace with another calibration or the
                           current analysis version. The original reading is never overwritten; with store=true a new
                           reading is created that points at the same trace and at the reading it was derived from.
"""
import hashlib
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import field, models, schemas
from ..database import get_db
from ..deps import _check_device_key, _get_or_create_device, _utc, now_utc, require_writer
from ..signal_processing import ANALYSIS_VERSION, process_voltammetry_trace
from ..standards import CALIBRATION_PROVENANCE, LOD_UG_L, QC_FAULT_FLAGS

router = APIRouter()


def _reprocess_key(trace_uuid: str, cal_id: str, analysis_version: str) -> str:
    """One stored re-computation per (scan, calibration, analysis version); kept under the 64-char key limit."""
    digest = hashlib.sha256(f"{trace_uuid}|{cal_id}|{analysis_version}".encode()).hexdigest()[:20]
    return f"reproc-{trace_uuid[:18]}-{digest}"


def trace_checksum(potentials: List[float], currents: List[float]) -> str:
    """SHA-256 of the native arrays (6 decimals), so any later change to a stored scan can be detected."""
    canon = json.dumps({"p": [round(float(v), 6) for v in potentials], "c": [round(float(v), 6) for v in currents]},
                       separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _features(res) -> dict:
    pk = res.peak
    if pk is None:
        return {}
    return {"net_peak_height_ua": pk.net_peak_height_ua, "peak_potential_mv": pk.peak_potential_mv,
            "peak_area_ua_mv": pk.peak_area_ua_mv, "half_height_width_mv": pk.half_height_width_mv, "snr": pk.snr,
            "baseline_slope_ua_per_mv": pk.baseline_slope_ua_per_mv, "noise_sigma_ua": pk.noise_sigma_ua,
            "secondary_peaks": pk.secondary_peaks, "baseline_residual_variance": pk.baseline_residual_variance,
            "peak_current_raw_ua": pk.peak_current_raw_ua, "baseline_current_ua": pk.baseline_current_ua}


def run_pipeline(db: Session, device: models.Device, potentials: List[float], currents: List[float]):
    """Process a trace with this device's active calibration. Returns (result, calibration dict)."""
    cal = field.active_calibration(db, device)
    res = process_voltammetry_trace(potentials, currents, slope=cal["slope_ua_per_mgl"], intercept=cal["intercept_ua"],
                                    lod_ug_l=cal.get("lod_ug_l") or LOD_UG_L, strict=False)
    return res, cal


def _trace_out(t: models.RawVoltammetryTrace, with_arrays: bool = True) -> dict:
    out = {
        "id": t.id, "trace_uuid": t.trace_uuid, "device_id": t.device_id, "source_type": t.source_type,
        "checksum_sha256": t.checksum_sha256, "raw_file_name": t.raw_file_name, "n_points": t.n_points,
        "firmware_version": t.firmware_version, "analysis_version": t.analysis_version,
        "calibration_id": t.calibration_id, "estimated_ug_l": t.estimated_ug_l, "uncertainty_ug_l": t.uncertainty_ug_l,
        "qc_status": t.qc_status, "qc_flags": [f for f in (t.qc_flags or "").split(",") if f],
        "features": json.loads(t.features_json) if t.features_json else {},
        "scan_settings": json.loads(t.scan_settings_json) if t.scan_settings_json else {},
        "electrode_lot": t.electrode_lot, "sample_code": t.sample_code,
        "recorded_at": _utc(t.recorded_at), "uploaded_at": _utc(t.uploaded_at), "is_synthetic": t.is_synthetic,
    }
    if with_arrays:
        out["potentials_mv"] = json.loads(t.raw_potentials_json)
        out["currents_ua"] = json.loads(t.raw_currents_json)
    return out


@router.post("/api/scans", tags=["Scans"], dependencies=[Depends(require_writer)])
def create_scan(payload: schemas.ScanCreate, request: Request, db: Session = Depends(get_db)):
    from ..main import ingest_reading   # one ingest path for every reading (imported here to avoid a cycle)

    _check_device_key(db, payload.device_code, request)
    if len(payload.potentials_mv) != len(payload.currents_ua):
        raise HTTPException(status_code=422, detail="potentials_mv and currents_ua must have the same length.")
    checksum = trace_checksum(payload.potentials_mv, payload.currents_ua)
    if payload.idempotency_key:
        dup = db.query(models.RawVoltammetryTrace).filter_by(trace_uuid=payload.idempotency_key).first()
        if dup is not None:
            rd = db.query(models.Reading).filter_by(trace_id=dup.id).order_by(models.Reading.id.asc()).first()
            return {"scan": _trace_out(dup, with_arrays=False), "reading_id": rd.id if rd else None,
                    "duplicate": True}

    device = _get_or_create_device(db, payload.device_code, payload.firmware_version)
    res, cal = run_pipeline(db, device, payload.potentials_mv, payload.currents_ua)
    flags = list(res.qc_flags)
    faults = [f for f in flags if f in QC_FAULT_FLAGS]
    device_flags = [f for f in (payload.device_qc_flags or []) if f]

    trace = models.RawVoltammetryTrace(
        trace_uuid=payload.idempotency_key or None,
        device_id=device.id,
        source_type=payload.source_type,
        checksum_sha256=checksum,
        raw_file_name=payload.raw_file_name,
        n_points=len(payload.potentials_mv),
        firmware_version=payload.firmware_version,
        analysis_version=res.analysis_version,
        calibration_id=cal.get("calibration_id"),
        estimated_ug_l=None if res.qc_status == "REJECTED" else res.estimated_arsenic_ug_l,
        uncertainty_ug_l=res.peak.uncertainty_ug_l if res.peak is not None else None,
        qc_status=res.qc_status,
        qc_flags=",".join(dict.fromkeys(flags + device_flags)) or None,
        features_json=json.dumps(_features(res)) if res.peak is not None else None,
        scan_settings_json=json.dumps(payload.scan_settings) if payload.scan_settings else None,
        sample_code=payload.sample_code,
        electrode_lot=payload.electrode_lot or "unknown",
        raw_potentials_json=json.dumps([round(float(v), 6) for v in payload.potentials_mv]),
        raw_currents_json=json.dumps([round(float(v), 6) for v in payload.currents_ua]),
        is_synthetic=payload.source_type == "simulated",
        measured_peak_current_ua=res.peak.net_peak_height_ua if res.peak is not None else None,
        snr=res.peak.snr if res.peak is not None else None,
        peak_potential_mv=res.peak.peak_potential_mv if res.peak is not None else None,
        recorded_at=(payload.recorded_at or now_utc()).replace(tzinfo=None),
        uploaded_at=now_utc().replace(tzinfo=None),
    )
    if trace.trace_uuid is None:
        import uuid as _uuid
        trace.trace_uuid = str(_uuid.uuid4())
    db.add(trace)
    db.commit()
    db.refresh(trace)

    if payload.reading_idempotency_key:
        # the device already uploaded the averaged reading; attach the trace to it
        rd = db.query(models.Reading).filter_by(idempotency_key=payload.reading_idempotency_key).first()
        if rd is None:
            raise HTTPException(status_code=404, detail="No reading with that idempotency key to attach the trace to.")
        if rd.trace_id is None:
            rd.trace_id = trace.id
            rd.analysis_version = rd.analysis_version or res.analysis_version
            db.commit()
        return {"scan": _trace_out(trace, with_arrays=False), "reading_id": rd.id, "attached": True,
                "pipeline": {"estimated_ug_l": trace.estimated_ug_l, "qc_status": res.qc_status, "qc_flags": flags,
                             "uncertainty_ug_l": trace.uncertainty_ug_l}}

    reading_payload = schemas.ReadingCreate(
        device_code=payload.device_code,
        arsenic_ppb=0.0 if res.qc_status == "REJECTED" else res.estimated_arsenic_ug_l,
        source_type=payload.source_type,
        source_label=payload.source_label or ("Recorded replay" if payload.source_type == "recorded_replay" else None),
        recorded_at=payload.recorded_at, age_seconds=payload.age_seconds,
        idempotency_key=f"scan-{trace.trace_uuid}",
        firmware_version=payload.firmware_version,
        ph=payload.ph, temperature_c=payload.temperature_c, conductivity_us_cm=payload.conductivity_us_cm,
        turbidity_ntu=payload.turbidity_ntu, battery_pct=payload.battery_pct,
        arsenic_species=payload.arsenic_species,
        peak_current_ua=res.peak.net_peak_height_ua if res.peak is not None else None,
        peak_potential_mv=res.peak.peak_potential_mv if res.peak is not None else None,
        snr=res.peak.snr if res.peak is not None else None, scans_averaged=1,
        cu_peak_ua=payload.cu_peak_ua, calibration_ref=cal.get("calibration_id"),
        qc_status="fail" if (faults or res.qc_status == "REJECTED") else "pass",
        qc_scan_flags=list(dict.fromkeys(flags + device_flags)) or None,
        sample_code=payload.sample_code, electrode_lot=payload.electrode_lot,
    )
    resp = ingest_reading(reading_payload, db, trace=trace,
                          uncertainty_ppb=res.peak.uncertainty_ug_l if res.peak is not None else None,
                          analysis_version=res.analysis_version)
    return {"scan": _trace_out(trace, with_arrays=False), "reading_id": resp.reading.id, "result": resp,
            "pipeline": {"estimated_ug_l": trace.estimated_ug_l, "qc_status": res.qc_status, "qc_flags": flags,
                         "qc_messages": res.qc_messages, "uncertainty_ug_l": trace.uncertainty_ug_l,
                         "analysis_version": res.analysis_version, "calibration": cal,
                         "calibration_provenance": CALIBRATION_PROVENANCE if cal.get("source") == "factory" else None}}


@router.get("/api/scans/{scan_id}", tags=["Scans"])
def get_scan(scan_id: int, processed: bool = Query(True, description="also return smoothed / baseline / subtracted arrays"),
             db: Session = Depends(get_db)):
    t = db.query(models.RawVoltammetryTrace).filter_by(id=scan_id).first()
    if t is None:
        raise HTTPException(status_code=404, detail="No such scan.")
    out = _trace_out(t)
    readings = db.query(models.Reading).filter_by(trace_id=t.id).order_by(models.Reading.id.asc()).all()
    out["readings"] = [{"id": r.id, "arsenic_ppb": r.arsenic_ppb, "classification": r.classification,
                        "screening_outcome": r.screening_outcome, "calibration_id": r.calibration_ref,
                        "analysis_version": r.analysis_version, "reprocessed_from_id": r.reprocessed_from_id}
                       for r in readings]
    if processed:
        device = db.query(models.Device).filter_by(id=t.device_id).first() if t.device_id else None
        res = process_voltammetry_trace(out["potentials_mv"], out["currents_ua"], strict=False,
                                        **_cal_kwargs(db, device))
        out["processed"] = {"smoothed_currents_ua": res.smoothed_currents_ua, "baseline_currents_ua": res.baseline_currents_ua,
                            "subtracted_currents_ua": res.subtracted_currents_ua, "qc_status": res.qc_status,
                            "qc_messages": res.qc_messages, "estimated_ug_l": res.estimated_arsenic_ug_l,
                            "peak": _features(res), "analysis_version": res.analysis_version,
                            "checksum_matches": trace_checksum(out["potentials_mv"], out["currents_ua"]) == t.checksum_sha256}
    return out


def _cal_kwargs(db: Session, device) -> dict:
    if device is None:
        return {}
    cal = field.active_calibration(db, device)
    return {"slope": cal["slope_ua_per_mgl"], "intercept": cal["intercept_ua"], "lod_ug_l": cal.get("lod_ug_l") or LOD_UG_L}


@router.get("/api/scans", tags=["Scans"])
def list_scans(device_code: Optional[str] = None, reading_id: Optional[int] = None, sample_code: Optional[str] = None,
               limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    q = db.query(models.RawVoltammetryTrace)
    if reading_id is not None:
        rd = db.query(models.Reading).filter_by(id=reading_id).first()
        if rd is None or rd.trace_id is None:
            return []
        q = q.filter(models.RawVoltammetryTrace.id == rd.trace_id)
    if device_code:
        dev = db.query(models.Device).filter_by(device_code=device_code).first()
        if dev is None:
            return []
        q = q.filter(models.RawVoltammetryTrace.device_id == dev.id)
    if sample_code:
        q = q.filter(models.RawVoltammetryTrace.sample_code == sample_code)
    rows = q.order_by(models.RawVoltammetryTrace.id.desc()).limit(limit).all()
    return [_trace_out(t, with_arrays=False) for t in rows]


@router.post("/api/scans/{scan_id}/reprocess", tags=["Scans"], dependencies=[Depends(require_writer)])
def reprocess_scan(scan_id: int, calibration_id: Optional[str] = Query(None, description="a stored calibration_id; default: the device's active one"),
                   store: bool = Query(False, description="also store the recomputed value as a new reading linked to this trace"),
                   db: Session = Depends(get_db)):
    from ..main import ingest_reading

    t = db.query(models.RawVoltammetryTrace).filter_by(id=scan_id).first()
    if t is None:
        raise HTTPException(status_code=404, detail="No such scan.")
    device = db.query(models.Device).filter_by(id=t.device_id).first() if t.device_id else None
    pots, curs = json.loads(t.raw_potentials_json), json.loads(t.raw_currents_json)
    if trace_checksum(pots, curs) != t.checksum_sha256:
        raise HTTPException(status_code=409, detail="Stored trace does not match its checksum; it was altered.")
    if calibration_id:
        rec = db.query(models.CalibrationRecord).filter_by(calibration_id=calibration_id).first()
        if rec is None:
            raise HTTPException(status_code=404, detail="No such calibration.")
        kwargs = {"slope": rec.slope, "intercept": rec.intercept, "lod_ug_l": rec.lod_ug_l}
        cal_id = rec.calibration_id
    else:
        kwargs = _cal_kwargs(db, device)
        cal_id = field.active_calibration(db, device)["calibration_id"] if device else "factory"
    res = process_voltammetry_trace(pots, curs, strict=False, **kwargs)
    original = db.query(models.Reading).filter_by(trace_id=t.id).order_by(models.Reading.id.asc()).first()
    out = {"scan_id": t.id, "original_reading_id": original.id if original else None,
           "original_ug_l": original.arsenic_ppb if original else None,
           "recomputed": {"estimated_ug_l": res.estimated_arsenic_ug_l if res.qc_status != "REJECTED" else None,
                          "uncertainty_ug_l": res.peak.uncertainty_ug_l if res.peak else None,
                          "qc_status": res.qc_status, "qc_messages": res.qc_messages,
                          "calibration_id": cal_id, "analysis_version": res.analysis_version}}
    if store and device is not None:
        flags = list(res.qc_flags)
        payload = schemas.ReadingCreate(
            device_code=device.device_code,
            arsenic_ppb=0.0 if res.qc_status == "REJECTED" else res.estimated_arsenic_ug_l,
            source_type=t.source_type if t.source_type in ("hardware", "recorded_replay", "simulated") else "recorded_replay",
            source_label=f"Reprocessed with {cal_id}",
            recorded_at=_utc(t.recorded_at), idempotency_key=_reprocess_key(t.trace_uuid, cal_id, res.analysis_version),
            peak_current_ua=res.peak.net_peak_height_ua if res.peak else None,
            peak_potential_mv=res.peak.peak_potential_mv if res.peak else None,
            snr=res.peak.snr if res.peak else None, scans_averaged=1, calibration_ref=cal_id,
            qc_status="fail" if res.qc_status == "REJECTED" or any(f in QC_FAULT_FLAGS for f in flags) else "pass",
            qc_scan_flags=flags or None, sample_code=t.sample_code, electrode_lot=t.electrode_lot,
            arsenic_species=original.arsenic_species if original else None,
        )
        resp = ingest_reading(payload, db, trace=t, uncertainty_ppb=res.peak.uncertainty_ug_l if res.peak else None,
                              analysis_version=res.analysis_version,
                              reprocessed_from_id=original.id if original else None, notify=False)
        out["stored_reading_id"] = resp.reading.id
        out["stored_label"] = resp.label
    return out
