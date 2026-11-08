"""
v5.7: can this device reading be trusted?

A dead, dry, worn or drifting electrode reads LOW, and a low arsenic reading looks like clean water. So a
hardware reading is only accepted at face value when:
  1. the device reports that its own scan checks passed (flat signal, noise, peak position, enough good scans,
     liquid present), and
  2. the sensor passed a check standard (a known arsenic solution) within QC_CHECK_MAX_AGE_HOURS (7 days), and
  3. it has a calibration made on this electrode (not the factory line) no older than CALIBRATION_MAX_AGE_DAYS.

If 1 fails: "Test Failed", whatever the number.
If 2 or 3 fail and the reading is LOW (below the detection limit): "Test Failed" (it may be a sensor reading low).
If 2 or 3 fail and arsenic was DETECTED: the verdict stands (detected arsenic is evidence) with a warning.

Simulated, demo and imported readings are not checked here; they are labelled as such instead.
Set QC_REQUIRE_FOR_HARDWARE=0 only for bench testing.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from . import field as field_mod, models
from .deps import _utc, now_utc
from .standards import LOD_UG_L, QC_BLANK_MAX_UG_L, QC_CHECK_RECOVERY, QC_FAULT_FLAGS, QC_SENSOR_TOLERANCE, QC_SPIKE_RECOVERY


def check_max_age_hours() -> float:
    return float(os.getenv("QC_CHECK_MAX_AGE_HOURS", "168"))


def calibration_max_age_days() -> float:
    return float(os.getenv("CALIBRATION_MAX_AGE_DAYS", "90"))


def qc_required() -> bool:
    return os.getenv("QC_REQUIRE_FOR_HARDWARE", "1") != "0"


# Plain-language names for the QC codes (dashboard, PDF, alerts)
QC_TEXT = {
    "FLAT_SIGNAL": "flat signal: electrode disconnected, dry or worn out",
    "REF_UNSTABLE": "cell did not settle at rest: check the reference electrode, counter lead and fill level",
    "BASELINE_UNSTABLE": "background too unstable",
    "NOISE_ABOVE_LOD": "too noisy to detect arsenic at the detection limit",
    "PEAK_AT_WINDOW_EDGE": "arsenic peak outside the search window",
    "NO_POINTS_IN_WINDOW": "no data in the arsenic window",
    "ADC_SATURATION_HIGH": "signal clipped (too high)",
    "ADC_SATURATION_LOW": "signal clipped (too low)",
    "TOO_FEW_GOOD_SCANS": "too few good scans",
    "SCANS_DISAGREE": "repeat scans disagree",
    "NO_LIQUID": "no water in the cell",
    "QC_NOT_REPORTED": "the device did not report its scan checks",
    "DEVICE_REPORTED_FAIL": "the device reported a failed scan",
    "CHECK_STANDARD_MISSING": "no check standard run on this device",
    "CHECK_STANDARD_FAILED": "the last check standard failed",
    "CHECK_STANDARD_OVERDUE": "the last check standard is too old",
    "CALIBRATION_MISSING": "not calibrated on this electrode (factory line only)",
    "CALIBRATION_EXPIRED": "calibration too old",
    "TIME_UNKNOWN": "the device did not say when the sample was taken",
    "PEAK_SHIFTED": "arsenic peak shifted from where it is expected",
    "LOW_SNR": "weak peak (estimate only)",
}


def describe(flags: List[str]) -> List[str]:
    return [QC_TEXT.get(f, f) for f in flags]


# ---------------------------------------------------------------------------
# Check standards and blanks
# ---------------------------------------------------------------------------

SENSOR_UNITS = {"ph_buffer": "pH", "conductivity_standard": "µS/cm", "turbidity_standard": "NTU", "temperature_reference": "°C"}


def judge_qc_run(run_type: str, expected: Optional[float], measured: float, flags: List[str],
                 baseline: Optional[float] = None):
    """Returns (passed, recovery_pct or None, plain-language detail).

    v5.9 adds field blanks (judged like reagent blanks), spike recovery on a real sample (the added arsenic must be
    recovered at 80-120 %) and the auxiliary sensors' checks against their own standards (pH buffer, conductivity
    standard, turbidity standard, reference thermometer) - without those, pH / EC / turbidity stay out of any claim."""
    if run_type in QC_SENSOR_TOLERANCE:
        if expected is None:
            return False, None, f"A {run_type.replace('_', ' ')} check needs the standard's value (expected_ug_l, in {SENSOR_UNITS[run_type]})."
        tol = QC_SENSOR_TOLERANCE[run_type]
        unit = SENSOR_UNITS[run_type]
        if run_type in ("conductivity_standard", "turbidity_standard"):
            if expected <= 0:
                return False, None, "The standard's value must be above zero."
            err = abs(measured - expected) / expected
            ok = err <= tol
            return ok, round(measured / expected * 100.0, 1), (f"Sensor read {measured:g} {unit} against a {expected:g} {unit} standard "
                                                               f"({err * 100:.1f} % off; allowed {tol * 100:.0f} %)." +
                                                               ("" if ok else " Recalibrate the sensor before using its values."))
        err = abs(measured - expected)
        ok = err <= tol
        return ok, None, (f"Sensor read {measured:g} {unit} against a {expected:g} {unit} reference ({err:.2f} {unit} off; "
                          f"allowed {tol:g}).") + ("" if ok else " Recalibrate the sensor before using its values.")
    faults = [f for f in flags if f in QC_FAULT_FLAGS]
    if faults:
        return False, None, "Scan failed its own checks: " + "; ".join(describe(faults)) + "."
    if run_type in ("blank", "field_blank"):
        ok = measured < QC_BLANK_MAX_UG_L
        what = "Field blank" if run_type == "field_blank" else "Blank"
        return ok, None, (f"{what} read {measured:.1f} µg/L" +
                          ("." if ok else f" (must be below {QC_BLANK_MAX_UG_L:g}); check for contamination or carry-over."))
    if run_type == "spike_recovery":
        if not expected or expected <= 0:
            return False, None, "A spike-recovery run needs the amount of arsenic added (expected_ug_l)."
        if baseline is None:
            return False, None, "A spike-recovery run needs the unspiked sample's reading (baseline_ug_l)."
        rec = (measured - baseline) / expected * 100.0
        lo, hi = QC_SPIKE_RECOVERY
        ok = lo <= rec <= hi
        return ok, rec, (f"Spiked {expected:g} µg/L into a sample reading {baseline:.1f} µg/L; read {measured:.1f} µg/L "
                         f"({rec:.0f} % recovery; allowed {lo:g}-{hi:g} %)." +
                         ("" if ok else " A matrix effect or interference is likely: use standard addition for this source."))
    if not expected or expected <= 0:
        return False, None, "A check standard needs its true value (expected_ug_l)."
    rec = measured / expected * 100.0
    lo, hi = QC_CHECK_RECOVERY
    ok = lo <= rec <= hi
    return ok, rec, (f"Check standard {expected:g} µg/L read {measured:.1f} µg/L ({rec:.0f}% recovery; allowed "
                     f"{lo:g}-{hi:g}%)." + ("" if ok else " Recalibrate or replace the electrode."))


def last_check(db: Session, device_code: str) -> Optional[models.QcRun]:
    return (db.query(models.QcRun).filter(models.QcRun.device_code == device_code,
                                          models.QcRun.run_type == "check_standard")
            .order_by(models.QcRun.recorded_at.desc(), models.QcRun.id.desc()).first())


def _calibration_problem(db: Session, device: models.Device) -> Optional[tuple]:
    cal = field_mod.active_calibration(db, device)
    if cal.get("source") == "factory":
        return "CALIBRATION_MISSING", "the sensor has not been calibrated on this electrode"
    at = cal.get("calibrated_at")
    if at is not None:
        age = (now_utc() - _utc(at)).total_seconds() / 86400.0
        if age > calibration_max_age_days():
            return "CALIBRATION_EXPIRED", f"the calibration is {age:.0f} days old"
    return None


def qc_status(db: Session, device_code: Optional[str]) -> Dict:
    out = {"check_max_age_hours": check_max_age_hours(), "calibration_max_age_days": calibration_max_age_days(),
           "required_for_hardware": qc_required()}
    if not device_code:
        return out
    dev = db.query(models.Device).filter_by(device_code=device_code).first()
    chk = last_check(db, device_code)
    if chk is None:
        out["last_check_standard"], out["check_ok"] = None, False
    else:
        age_h = (now_utc() - _utc(chk.recorded_at)).total_seconds() / 3600.0
        out["last_check_standard"] = {"recorded_at": _utc(chk.recorded_at).isoformat(), "passed": chk.passed,
                                      "recovery_pct": chk.recovery_pct, "age_hours": round(age_h, 1), "detail": chk.detail}
        out["check_ok"] = bool(chk.passed) and age_h <= check_max_age_hours()
    if dev is not None:
        prob = _calibration_problem(db, dev)
        out["calibration"] = field_mod.active_calibration(db, dev)
        out["calibration_ok"] = prob is None
        out["calibration_problem"] = prob[1] if prob else None
    blanks = (db.query(models.QcRun).filter(models.QcRun.device_code == device_code, models.QcRun.run_type == "blank")
              .order_by(models.QcRun.recorded_at.desc()).limit(20).all())
    out["recent_blanks"] = [{"recorded_at": _utc(b.recorded_at).isoformat(), "measured_ug_l": b.measured_ug_l,
                             "passed": b.passed} for b in blanks]
    # v5.9: the auxiliary sensors are "verified" only while their last check against a standard passed within the
    # calibration window; the dashboard greys out pH / EC / turbidity / temperature otherwise (ISEF item 98).
    sensors = {}
    for rt in QC_SENSOR_TOLERANCE:
        last = (db.query(models.QcRun).filter(models.QcRun.device_code == device_code, models.QcRun.run_type == rt)
                .order_by(models.QcRun.recorded_at.desc()).first())
        if last is None:
            sensors[rt] = {"verified": False, "last": None}
        else:
            age_d = (now_utc() - _utc(last.recorded_at)).total_seconds() / 86400.0
            sensors[rt] = {"verified": bool(last.passed) and age_d <= calibration_max_age_days(),
                           "last": {"recorded_at": _utc(last.recorded_at).isoformat(), "passed": last.passed,
                                    "expected": last.expected_ug_l, "measured": last.measured_ug_l, "age_days": round(age_d, 1)}}
    out["sensor_checks"] = sensors
    out["trusted"] = bool(out.get("check_ok")) and bool(out.get("calibration_ok"))
    return out


# ---------------------------------------------------------------------------
# Deciding whether one hardware reading can be trusted
# ---------------------------------------------------------------------------

@dataclass
class ReadingQc:
    failed: bool = False
    reasons: List[str] = field(default_factory=list)    # plain-language reasons it failed
    flags: List[str] = field(default_factory=list)      # QC codes stored with the reading
    warnings: List[str] = field(default_factory=list)
    status: Optional[str] = None                        # pass | warning | fail (hardware only)


def assess_reading(db: Session, *, source_type: Optional[str], device: models.Device, arsenic_ppb: float,
                   device_qc_status: Optional[str], device_flags: Optional[List[str]]) -> ReadingQc:
    q = ReadingQc(flags=[f for f in (device_flags or []) if f])
    is_hardware = source_type == "hardware"

    # v5.8: a scan the pipeline rejected (or a device-reported fail) is a failed test whatever the source -
    # a recorded replay or a practice scan of a dead electrode must never be stored as "0 µg/L, not detected".
    faults = [f for f in q.flags if f in QC_FAULT_FLAGS]
    if device_qc_status is None:
        if is_hardware and qc_required():
            q.flags.append("QC_NOT_REPORTED")
            q.failed = True
            q.reasons.append(QC_TEXT["QC_NOT_REPORTED"])
    elif device_qc_status.lower() != "pass" or faults:
        if device_qc_status.lower() != "pass":
            q.flags.append("DEVICE_REPORTED_FAIL")
        q.failed = True
        q.reasons.extend(describe(faults) or [QC_TEXT["DEVICE_REPORTED_FAIL"]])
    if not is_hardware:
        return q   # check standards and calibration age are duties of a live instrument only

    if qc_required() and not q.failed:
        stale: List[str] = []
        chk = last_check(db, device.device_code)
        if chk is None:
            q.flags.append("CHECK_STANDARD_MISSING")
            stale.append(QC_TEXT["CHECK_STANDARD_MISSING"])
        else:
            age_h = (now_utc() - _utc(chk.recorded_at)).total_seconds() / 3600.0
            if not chk.passed:
                q.flags.append("CHECK_STANDARD_FAILED")
                stale.append(QC_TEXT["CHECK_STANDARD_FAILED"])
            elif age_h > check_max_age_hours():
                q.flags.append("CHECK_STANDARD_OVERDUE")
                stale.append(f"the last check standard is {age_h / 24:.0f} days old")
        prob = _calibration_problem(db, device)
        if prob:
            q.flags.append(prob[0])
            stale.append(prob[1])
        if stale:
            if arsenic_ppb < LOD_UG_L:
                # A low reading from an unverified sensor could be a drifting / dead electrode: not reported as low.
                q.failed = True
                q.reasons.extend(stale)
            else:
                q.warnings.append("Sensor not verified (" + "; ".join(stale) + "). Arsenic was detected, so the "
                                  "result is kept, but the true level may differ.")

    q.status = "fail" if q.failed else ("warning" if q.warnings or any(f in QC_TEXT for f in q.flags) else "pass")
    return q


def merge_flags(*lists: List[str], limit: int = 128) -> Optional[str]:
    """Comma list for Reading.qc_flags (String(128)); keeps order, drops duplicates, never cuts a code in half."""
    out: List[str] = []
    for lst in lists:
        for f in lst or []:
            if f and f not in out:
                out.append(f)
    s = ""
    for f in out:
        nxt = f if not s else s + "," + f
        if len(nxt) > limit:
            break
        s = nxt
    return s or None
