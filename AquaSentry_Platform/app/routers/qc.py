"""v5.7: quality-control runs (blank / check standard) and the trust status of each device."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import field, models, qc, schemas
from ..database import get_db
from ..deps import _check_device_key, _get_or_create_device, now_utc, require_writer

router = APIRouter()


@router.post("/api/qc/runs", tags=["Quality Control"], dependencies=[Depends(require_writer)])
def record_qc_run(payload: schemas.QcRunCreate, request: Request, db: Session = Depends(get_db)):
    """Record a blank (arsenic-free water) or check-standard (known arsenic solution) run.

    Hardware readings are only trusted with a passing check standard from the last QC_CHECK_MAX_AGE_HOURS
    (default 7 days): without one, a LOW reading is reported as "Test Failed" because a dead or drifting electrode
    reads low. The ESP32 runs these from its /qc page; a lab can also enter them here."""
    _check_device_key(db, payload.device_code, request)
    dev = _get_or_create_device(db, payload.device_code)
    measured = payload.measured_ug_l
    if payload.peak_current_ua is not None:
        cal = field.active_calibration(db, dev)
        slope, icpt = cal["slope_ua_per_mgl"], cal["intercept_ua"]
        measured = max(0.0, (payload.peak_current_ua - icpt) / slope * 1000.0) if payload.peak_current_ua > icpt else 0.0
    if measured is None:
        raise HTTPException(status_code=422, detail="Give measured_ug_l or peak_current_ua.")
    expected = 0.0 if payload.run_type == "blank" else payload.expected_ug_l
    passed, recovery, detail = qc.judge_qc_run(payload.run_type, expected, measured, payload.qc_scan_flags or [])
    run = models.QcRun(device_code=payload.device_code, run_type=payload.run_type, expected_ug_l=expected,
                       measured_ug_l=round(measured, 3), peak_current_ua=payload.peak_current_ua,
                       recovery_pct=round(recovery, 1) if recovery is not None else None, passed=passed, detail=detail,
                       recorded_at=payload.recorded_at or now_utc())
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"id": run.id, "passed": passed, "recovery_pct": run.recovery_pct, "detail": detail,
            "status": qc.qc_status(db, payload.device_code)}


@router.get("/api/qc/status", tags=["Quality Control"])
def get_qc_status(device_code: Optional[str] = None, db: Session = Depends(get_db)):
    """Is this device's sensor verified? Last check standard, calibration in use and its age, recent blanks."""
    return qc.qc_status(db, device_code)


@router.get("/api/qc/runs", tags=["Quality Control"])
def list_qc_runs(device_code: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(models.QcRun)
    if device_code:
        q = q.filter(models.QcRun.device_code == device_code)
    rows = q.order_by(models.QcRun.recorded_at.desc()).limit(max(1, min(limit, 500))).all()
    return [{"id": r.id, "device_code": r.device_code, "run_type": r.run_type, "expected_ug_l": r.expected_ug_l,
             "measured_ug_l": r.measured_ug_l, "recovery_pct": r.recovery_pct, "passed": r.passed, "detail": r.detail,
             "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None} for r in rows]
