"""Field programme API (v5.6): sites, lab confirmations + validation, calibrations, JJM-style export,
and the public per-device page used by the QR stickers."""
import csv
import io
import json
import uuid
from datetime import datetime
from typing import List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import field, models
from ..database import get_db
from ..deps import _check_device_key, _utc, now_utc, require_admin, require_writer
from ..quality import caveats
from ..standards import LOD_UG_L

router = APIRouter()


def _device(db: Session, code: str) -> models.Device:
    d = db.query(models.Device).filter_by(device_code=code).first()
    if d is None:
        raise HTTPException(status_code=404, detail=f"No device '{code}'.")
    return d


# ---------------------------------------------------------------------------- sites
class SiteIn(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    location_label: Optional[str] = Field(None, max_length=128)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    state: Optional[str] = Field(None, max_length=64)
    district: Optional[str] = Field(None, max_length=64)
    block: Optional[str] = Field(None, max_length=64)
    panchayat: Optional[str] = Field(None, max_length=64)
    village: Optional[str] = Field(None, max_length=64)
    source_kind: Optional[Literal[field.SOURCE_KINDS]] = None


@router.put("/api/admin/devices/{device_code}/site", tags=["Field"], dependencies=[Depends(require_admin)])
def set_site(device_code: str, site: SiteIn, db: Session = Depends(get_db)):
    """Where the node draws water from: shown on the map, on its QR page and in the JJM-style export."""
    d = _device(db, device_code)
    for k, v in site.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    db.commit()
    return {"device_code": d.device_code, "site": field.site_dict(d)}


# ---------------------------------------------------------------------------- lab results
class LabIn(BaseModel):
    device_code: str = Field(..., max_length=64)
    arsenic_ug_l: float = Field(..., ge=0, le=50000)
    as3_ug_l: Optional[float] = Field(None, ge=0, le=50000, description="As(III) only, if the lab speciated")
    sampled_at: Optional[datetime] = None
    reading_id: Optional[int] = Field(None, description="Node reading this confirms; found automatically if omitted")
    lab_name: Optional[str] = Field(None, max_length=128)
    lab_method: Literal[field.LAB_METHODS] = "ICP-MS"
    sample_code: Optional[str] = Field(None, max_length=64)
    nabl_accredited: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=2000)
    # v5.8 (review item 26): censored results keep their reporting limit and "<" instead of becoming a number
    reporting_limit_ug_l: Optional[float] = Field(None, ge=0, le=1000, description="The lab's reporting limit")
    qualifier: Optional[Literal["<"]] = Field(None, description='"<" when the lab reported below its reporting limit')
    species: Optional[Literal["total", "as3", "as5", "dissolved"]] = Field(None, description="What the lab value is")


@router.post("/api/lab-results", tags=["Field"], dependencies=[Depends(require_writer)])
def add_lab_result(body: LabIn, request: Request, db: Session = Depends(get_db)):
    """Record a laboratory (or official field-test-kit) result for water this node also tested. Without
    reading_id it is paired with the node's reading closest in time (within 48 h)."""
    d = _device(db, body.device_code)
    _check_device_key(db, body.device_code, request)
    when = _utc(body.sampled_at) or now_utc()
    reading = None
    if body.reading_id is not None:
        reading = db.get(models.Reading, body.reading_id)
        if reading is None or reading.device_id != d.id:
            raise HTTPException(status_code=422, detail="reading_id does not belong to this device.")
    else:
        reading = field.nearest_reading(db, d.id, when)
    if body.as3_ug_l is not None and body.as3_ug_l > body.arsenic_ug_l * 1.1 + 1:
        raise HTTPException(status_code=422, detail="As(III) cannot be more than total arsenic.")
    if body.qualifier == "<" and body.reporting_limit_ug_l is None:
        raise HTTPException(status_code=422, detail='A "<" result needs reporting_limit_ug_l (the value is then the limit).')
    if body.qualifier == "<" and body.arsenic_ug_l > body.reporting_limit_ug_l:
        raise HTTPException(status_code=422, detail='A "<" result cannot be above its reporting limit.')
    # a sample_code shared with the node reading links the lab split to the exact sample (review item 21)
    if reading is None and body.sample_code:
        reading = (db.query(models.Reading).filter(models.Reading.device_id == d.id,
                                                   models.Reading.sample_code == body.sample_code)
                   .order_by(models.Reading.recorded_at.desc()).first())
    row = models.LabResult(device_id=d.id, reading_id=reading.id if reading else None, sample_code=body.sample_code,
                           sampled_at=when, lab_name=body.lab_name, lab_method=body.lab_method,
                           arsenic_ug_l=body.arsenic_ug_l, as3_ug_l=body.as3_ug_l,
                           nabl_accredited=body.nabl_accredited, notes=body.notes,
                           reporting_limit_ug_l=body.reporting_limit_ug_l, qualifier=body.qualifier,
                           species=body.species)
    db.add(row)
    db.commit()
    db.refresh(row)
    return field.lab_dict(row)


@router.get("/api/lab-results", tags=["Field"])
def list_lab_results(device_code: Optional[str] = None, limit: int = Query(200, ge=1, le=2000),
                     db: Session = Depends(get_db)):
    q = db.query(models.LabResult)
    if device_code:
        q = q.filter(models.LabResult.device_id == _device(db, device_code).id)
    return [field.lab_dict(r) for r in q.order_by(models.LabResult.sampled_at.desc()).limit(limit).all()]


@router.delete("/api/admin/lab-results/{lab_id}", tags=["Field"], dependencies=[Depends(require_admin)])
def delete_lab_result(lab_id: int, db: Session = Depends(get_db)):
    row = db.get(models.LabResult, lab_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such lab result.")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": lab_id}


@router.get("/api/validation", tags=["Field"])
def validation(device_code: Optional[str] = None, db: Session = Depends(get_db)):
    """How the nodes compare with the lab: missed unsafe samples, sensitivity (with 95% interval), false
    alarms, bias, error and, when the lab speciated, the As(III) share and the node's recovery."""
    q = db.query(models.LabResult).filter(models.LabResult.reading_id.isnot(None))
    if device_code:
        q = q.filter(models.LabResult.device_id == _device(db, device_code).id)
    pairs = [(r.reading.arsenic_ppb, r.arsenic_ug_l, r.as3_ug_l) for r in q.all() if r.reading is not None]
    out = field.validation_stats(pairs)
    out["device_code"] = device_code
    out["unpaired_lab_results"] = db.query(models.LabResult).filter(models.LabResult.reading_id.is_(None)).count()
    return out


# ---------------------------------------------------------------------------- calibration
class CalPoint(BaseModel):
    ug_l: float = Field(..., ge=0, le=5000)
    peak_ua: float = Field(..., ge=-100, le=1000)


class ExternalCalIn(BaseModel):
    device_code: Optional[str] = None
    electrode_lot: Optional[str] = Field(None, max_length=64)
    standards: List[CalPoint] = Field(..., min_length=3, max_length=20)
    approved_by: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = Field(None, max_length=2000)
    activate: bool = True


class StdAddIn(BaseModel):
    device_code: Optional[str] = None
    electrode_lot: Optional[str] = Field(None, max_length=64)
    sample_peak_ua: float = Field(..., ge=-100, le=1000)
    additions: List[CalPoint] = Field(..., min_length=2, max_length=10, description="µg/L added and peak µA")
    blank_peak_ua: Optional[float] = Field(None, ge=-100, le=1000)
    approved_by: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = Field(None, max_length=2000)
    activate: bool = True


def _store_cal(db: Session, fit: dict, device_code, lot, approved_by, notes, activate, points) -> dict:
    dev = _device(db, device_code) if device_code else None
    if activate:
        q = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.is_active.is_(True))
        q = q.filter(models.CalibrationRecord.device_id == dev.id) if dev else q.filter(models.CalibrationRecord.device_id.is_(None))
        for old in q.all():
            old.is_active = False
    # v5.8: the LOD a few standards imply (3.3 s_y / slope) is floored at the validated method LOD. A perfect-looking
    # fit (s_y ~ 0) would otherwise claim an LOD near zero, and every scan would then fail the noise-vs-LOD check.
    fit_lod = fit.get("lod_ug_l")
    lod = max(fit_lod, LOD_UG_L) if fit_lod else LOD_UG_L
    fit = {**fit, "lod_ug_l": lod, "loq_ug_l": lod * 10 / 3.3, "fit_lod_ug_l": fit_lod}
    rec = models.CalibrationRecord(
        calibration_id=f"CAL-{now_utc():%Y%m%d}-{uuid.uuid4().hex[:6]}", analyte_identifier="arsenic",
        slope=round(fit["slope_ua_per_mgl"], 6), intercept=round(fit["intercept_ua"], 6), r_squared=round(fit["r_squared"], 5),
        lod_ug_l=round(lod, 2), loq_ug_l=round(lod * 10 / 3.3, 2),
        cal_range_min_ug_l=fit["range_ug_l"][0], cal_range_max_ug_l=fit["range_ug_l"][1], calibration_date=now_utc(),
        is_active=activate, approved_by=approved_by or "not recorded", device_id=dev.id if dev else None,
        electrode_lot=lot, method=fit["method"], points_json=json.dumps(points), notes=notes)
    db.add(rec)
    db.commit()
    warn = []
    if fit["r_squared"] < 0.98:
        warn.append(f"R² is {fit['r_squared']:.3f}; below 0.98 usually means a bad standard or a fouled electrode.")
    if fit_lod is None or fit_lod < LOD_UG_L:
        warn.append(f"The standards imply an LOD of {0 if fit_lod is None else fit_lod:.1f} µg/L, below the validated method "
                    f"LOD; {LOD_UG_L:.0f} µg/L is used until a laboratory study demonstrates better.")
    return {"calibration_id": rec.calibration_id, "active": activate, **{k: v for k, v in fit.items() if k != "range_ug_l"},
            "warnings": warn}


@router.post("/api/admin/calibrations/external", tags=["Field"], dependencies=[Depends(require_admin)])
def calibrate_external(body: ExternalCalIn, db: Session = Depends(get_db)):
    """Calibrate from standards of known arsenic concentration."""
    pts: List[Tuple[float, float]] = [(p.ug_l, p.peak_ua) for p in body.standards]
    try:
        fit = field.fit_external(pts)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _store_cal(db, fit, body.device_code, body.electrode_lot, body.approved_by, body.notes, body.activate, pts)


@router.post("/api/admin/calibrations/standard-addition", tags=["Field"], dependencies=[Depends(require_admin)])
def calibrate_standard_addition(body: StdAddIn, db: Session = Depends(get_db)):
    """Standard addition in the real water: returns the sample's arsenic and a matrix-matched slope."""
    adds = [(p.ug_l, p.peak_ua) for p in body.additions]
    try:
        fit = field.fit_standard_addition(body.sample_peak_ua, adds, body.blank_peak_ua)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _store_cal(db, fit, body.device_code, body.electrode_lot, body.approved_by, body.notes, body.activate,
                      [(0.0, body.sample_peak_ua)] + adds)


@router.get("/api/calibrations", tags=["Field"])
def list_calibrations(device_code: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.CalibrationRecord)
    if device_code:
        q = q.filter(models.CalibrationRecord.device_id == _device(db, device_code).id)
    return [{"calibration_id": r.calibration_id, "method": r.method, "slope_ua_per_mgl": r.slope,
             "intercept_ua": r.intercept, "r_squared": r.r_squared, "lod_ug_l": r.lod_ug_l, "active": r.is_active,
             "device_id": r.device_id, "electrode_lot": r.electrode_lot, "approved_by": r.approved_by,
             "calibrated_at": _utc(r.calibration_date)} for r in q.order_by(models.CalibrationRecord.calibration_date.desc()).all()]


@router.get("/api/devices/{device_code}/calibration", tags=["Field"])
def device_calibration(device_code: str, db: Session = Depends(get_db)):
    """What the node should use: its own calibration, else a global one, else the factory numbers.
    The firmware fetches this at start-up and once a day."""
    return field.active_calibration(db, _device(db, device_code))


# ---------------------------------------------------------------------------- JJM-style export
@router.get("/api/data/export/jjm", tags=["Data Management"])
def export_jjm(device_code: Optional[str] = None, include_demo: bool = False, db: Session = Depends(get_db)):
    """CSV laid out like Jal Jeevan Mission water-quality entries (location hierarchy, test type, result in
    mg/L, limit, status). Laid out from the public WQMIS field list; confirm the exact upload template
    with your district water-testing laboratory."""
    devices = db.query(models.Device).all()
    rq = db.query(models.Reading)
    lq = db.query(models.LabResult)
    if device_code:
        d = _device(db, device_code)
        rq, lq = rq.filter(models.Reading.device_id == d.id), lq.filter(models.LabResult.device_id == d.id)
    if not include_demo:
        rq = rq.filter(models.Reading.source_type.in_(["hardware", "manual_import"]))
    rows = field.jjm_rows(devices, rq.order_by(models.Reading.recorded_at).all(), lq.order_by(models.LabResult.sampled_at).all())

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(field.JJM_COLUMNS)
        for row in rows:
            w.writerow([("'" + c) if isinstance(c, str) and c[:1] in ("=", "+", "-", "@") else c for c in row])
        yield "﻿" + buf.getvalue()      # BOM so Excel opens Hindi / Bengali place names correctly
    return StreamingResponse(gen(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="aquasentry_jjm_arsenic.csv"'})


# ---------------------------------------------------------------------------- public device page (QR)
@router.get("/api/public/devices/{device_code}", tags=["Public"])
def public_device(device_code: str, db: Session = Depends(get_db)):
    """What a villager sees after scanning the QR sticker on a handpump: the latest verdict, when it was
    taken, any caveat, and the latest lab confirmation. No history, keys or other devices."""
    import os
    if os.getenv("PUBLIC_DEVICE_PAGES", "1") == "0":
        raise HTTPException(status_code=404, detail="Public device pages are turned off.")
    d = _device(db, device_code)
    r = (db.query(models.Reading).filter(models.Reading.device_id == d.id)
         .order_by(models.Reading.recorded_at.desc()).first())
    site = field.site_dict(d) or {}
    return {
        "device_code": d.device_code,
        "name": site.get("name") or site.get("location_label"),
        "village": site.get("village"), "district": site.get("district"), "source_kind": site.get("source_kind"),
        "latest": None if r is None else {
            "arsenic_ug_l": round(r.arsenic_ppb, 1), "classification": r.classification,
            "screening_outcome": r.screening_outcome, "uncertainty_ug_l": r.uncertainty_ppb,
            "is_safe_to_drink": r.is_safe_to_drink, "recorded_at": _utc(r.recorded_at),
            "is_demo": r.source_type not in ("hardware", "recorded_replay", "manual_import"), "caveats": caveats(r.qc_flags),
            "qc_flags": [f for f in (r.qc_flags or "").split(",") if f]},
        "lab": field.latest_lab(db, d.id),
        "limit_ug_l": 10.0,
    }


# ---------------------------------------------------------------------------- v5.8 paired dataset export
PAIRED_COLUMNS = [
    "sample_code", "reading_id", "device_code", "site_name", "village", "district", "state", "latitude", "longitude",
    "source_kind", "recorded_at", "time_source", "source_type", "device_ug_l", "device_uncertainty_ug_l",
    "screening_outcome", "classification", "arsenic_species", "qc_status", "qc_flags", "calibration_id",
    "analysis_version", "firmware_version", "electrode_lot", "scan_id", "scan_checksum_sha256",
    "peak_height_ua", "peak_potential_mv", "snr", "ph", "conductivity_us_cm", "turbidity_ntu", "temperature_c",
    "lab_id", "lab_sampled_at", "lab_method", "lab_name", "lab_nabl", "lab_species", "lab_ug_l",
    "lab_reporting_limit_ug_l", "lab_qualifier", "lab_as3_ug_l", "pair_gap_hours",
]


@router.get("/api/data/export/paired", tags=["Data Management"])
def export_paired(device_code: Optional[str] = None, include_demo: bool = False,
                  fmt: Literal["csv", "json"] = Query("csv", alias="format"), db: Session = Depends(get_db)):
    """The paired dataset (review items 21, 30, 263): one row per device reading, joined to its laboratory
    result when there is one, with the trace checksum, QC, calibration and firmware that produced the value.
    Feed the CSV to Analysis/paired_validation.py. Lab results below the reporting limit keep their "<"."""
    devices = {d.id: d for d in db.query(models.Device).all()}
    rq = db.query(models.Reading)
    if device_code:
        dev = next((d for d in devices.values() if d.device_code == device_code), None)
        if dev is None:
            raise HTTPException(status_code=404, detail=f"No device '{device_code}'.")
        rq = rq.filter(models.Reading.device_id == dev.id)
    if not include_demo:
        rq = rq.filter(models.Reading.source_type.in_(["hardware", "recorded_replay", "manual_import"]))
    readings = rq.order_by(models.Reading.recorded_at.asc()).all()
    labs_by_reading = {}
    for lab in db.query(models.LabResult).all():
        if lab.reading_id is not None:
            labs_by_reading.setdefault(lab.reading_id, lab)
    traces = {t.id: t for t in db.query(models.RawVoltammetryTrace).all()} if readings else {}

    rows = []
    for r in readings:
        d = devices.get(r.device_id)
        lab = labs_by_reading.get(r.id)
        t = traces.get(r.trace_id) if r.trace_id else None
        gap = None
        if lab is not None and lab.sampled_at and r.recorded_at:
            gap = round(abs((lab.sampled_at - r.recorded_at).total_seconds()) / 3600.0, 2)
        rows.append({
            "sample_code": r.sample_code or (lab.sample_code if lab else None), "reading_id": r.id,
            "device_code": d.device_code if d else None, "site_name": getattr(d, "name", None),
            "village": getattr(d, "village", None), "district": getattr(d, "district", None),
            "state": getattr(d, "state", None), "latitude": getattr(d, "latitude", None),
            "longitude": getattr(d, "longitude", None), "source_kind": getattr(d, "source_kind", None),
            "recorded_at": _utc(r.recorded_at).isoformat() if r.recorded_at else None, "time_source": r.time_source,
            "source_type": r.source_type, "device_ug_l": r.arsenic_ppb, "device_uncertainty_ug_l": r.uncertainty_ppb,
            "screening_outcome": r.screening_outcome, "classification": r.classification,
            "arsenic_species": r.arsenic_species, "qc_status": r.qc_status, "qc_flags": r.qc_flags,
            "calibration_id": r.calibration_ref, "analysis_version": r.analysis_version,
            "firmware_version": getattr(d, "firmware_version", None), "electrode_lot": r.electrode_lot,
            "scan_id": t.id if t else None, "scan_checksum_sha256": t.checksum_sha256 if t else None,
            "peak_height_ua": t.measured_peak_current_ua if t else None,
            "peak_potential_mv": t.peak_potential_mv if t else None, "snr": t.snr if t else None,
            "ph": r.ph, "conductivity_us_cm": r.conductivity_us_cm, "turbidity_ntu": r.turbidity_ntu,
            "temperature_c": r.temperature_c,
            "lab_id": lab.id if lab else None, "lab_sampled_at": _utc(lab.sampled_at).isoformat() if lab and lab.sampled_at else None,
            "lab_method": lab.lab_method if lab else None, "lab_name": lab.lab_name if lab else None,
            "lab_nabl": lab.nabl_accredited if lab else None, "lab_species": lab.species if lab else None,
            "lab_ug_l": lab.arsenic_ug_l if lab else None,
            "lab_reporting_limit_ug_l": lab.reporting_limit_ug_l if lab else None,
            "lab_qualifier": lab.qualifier if lab else None, "lab_as3_ug_l": lab.as3_ug_l if lab else None,
            "pair_gap_hours": gap,
        })
    if fmt == "json":
        return {"columns": PAIRED_COLUMNS, "rows": rows, "n_readings": len(rows),
                "n_paired": sum(1 for x in rows if x["lab_id"] is not None),
                "note": "Device values are As(III) unless arsenic_species is 'total'. Lab '<' rows are censored at their reporting limit."}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(PAIRED_COLUMNS)
    for x in rows:
        w.writerow(["" if x[c] is None else x[c] for c in PAIRED_COLUMNS])
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=aquasentry_paired_dataset.csv"})
