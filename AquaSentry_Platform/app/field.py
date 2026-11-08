"""
Field-programme logic (v5.6): device sites, lab confirmations and the sensor-vs-lab validation numbers,
calibration fitting (external standards and standard addition), and the Jal Jeevan Mission style export.

Pure functions where possible, so they are easy to test and to reuse from scripts.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from . import models
from .standards import BIS_PERMISSIBLE_LIMIT_UG_L, CALIBRATION_INTERCEPT, CALIBRATION_SLOPE, LOD_UG_L

SOURCE_KINDS = ("handpump", "tubewell", "borewell", "piped", "open_well", "surface", "other")
LAB_METHODS = ("ICP-MS", "HG-AAS", "GF-AAS", "ICP-OES", "FTK", "other")


def _utc(d: Optional[datetime]) -> Optional[datetime]:
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)


# ---------------------------------------------------------------------------- sites
def site_dict(d: "models.Device") -> Optional[Dict]:
    fields = ("name", "location_label", "latitude", "longitude", "state", "district", "block", "panchayat",
              "village", "source_kind")
    out = {f: getattr(d, f, None) for f in fields}
    return out if any(v is not None for v in out.values()) else None


# ---------------------------------------------------------------------------- lab results
def lab_dict(r: "models.LabResult") -> Dict:
    return {"id": r.id, "device_code": r.device.device_code if r.device is not None else None,
            "reading_id": r.reading_id, "sample_code": r.sample_code, "sampled_at": _utc(r.sampled_at),
            "lab_name": r.lab_name, "lab_method": r.lab_method, "arsenic_ug_l": r.arsenic_ug_l,
            "as3_ug_l": r.as3_ug_l, "nabl_accredited": r.nabl_accredited, "notes": r.notes,
            "reporting_limit_ug_l": r.reporting_limit_ug_l, "qualifier": r.qualifier, "species": r.species,
            "censored": r.qualifier == "<",
            "node_arsenic_ug_l": r.reading.arsenic_ppb if r.reading is not None else None,
            "node_outcome": r.reading.screening_outcome if r.reading is not None else None}


def latest_lab(db: Session, device_id: Optional[int]) -> Optional[Dict]:
    if device_id is None:
        return None
    r = (db.query(models.LabResult).filter(models.LabResult.device_id == device_id)
         .order_by(models.LabResult.sampled_at.desc()).first())
    if r is None:
        return None
    d = lab_dict(r)
    d["above_limit"] = r.arsenic_ug_l > BIS_PERMISSIBLE_LIMIT_UG_L
    return d


def nearest_reading(db: Session, device_id: int, when: datetime, window_h: float = 48.0) -> Optional["models.Reading"]:
    """The node reading closest in time to a lab sample (within ±window_h hours)."""
    when = _utc(when).replace(tzinfo=None)
    lo, hi = when - timedelta(hours=window_h), when + timedelta(hours=window_h)
    rows = (db.query(models.Reading).filter(models.Reading.device_id == device_id,
                                            models.Reading.recorded_at >= lo, models.Reading.recorded_at <= hi).all())
    if not rows:
        return None
    return min(rows, key=lambda r: abs((r.recorded_at.replace(tzinfo=None) - when).total_seconds()))


def _wilson(k: int, n: int, z: float = 1.96) -> Optional[Tuple[float, float]]:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)


def validation_stats(pairs: Iterable[Tuple[float, float, Optional[float]]], lod: float = LOD_UG_L,
                     limit: float = BIS_PERMISSIBLE_LIMIT_UG_L) -> Dict:
    """pairs: (node µg/L, lab µg/L, lab As(III) µg/L or None).

    Safety numbers first: of the samples the lab found above the legal limit, how many did the node flag
    (detected, i.e. at or above its detection limit)? A miss is a node "No arsenic detected" on water the
    lab says is unsafe. Then accuracy where both are above the detection limit: bias, MAE, RMSE, slope."""
    pairs = list(pairs)
    n = len(pairs)
    out: Dict = {"n_pairs": n, "lod_ug_l": lod, "limit_ug_l": limit}
    if n == 0:
        out["message"] = "No lab results paired with node readings yet."
        return out
    unsafe = [(a, b) for a, b, _ in pairs if b > limit]
    detected = [p for p in unsafe if p[0] >= lod]
    missed = len(unsafe) - len(detected)
    clean = [(a, b) for a, b, _ in pairs if b <= limit]
    false_alarm = sum(1 for a, _ in clean if a >= lod)
    out["lab_above_limit"] = len(unsafe)
    out["node_flagged_of_those"] = len(detected)
    out["missed_unsafe"] = missed
    out["sensitivity"] = round(len(detected) / len(unsafe), 3) if unsafe else None
    out["sensitivity_95ci"] = _wilson(len(detected), len(unsafe))
    out["lab_within_limit"] = len(clean)
    out["false_alarms"] = false_alarm
    out["specificity"] = round(1 - false_alarm / len(clean), 3) if clean else None
    quant = [(a, b) for a, b, _ in pairs if a >= lod and b >= lod]
    out["n_quantified"] = len(quant)
    if quant:
        diffs = [a - b for a, b in quant]
        out["mean_bias_ug_l"] = round(sum(diffs) / len(diffs), 2)
        out["mae_ug_l"] = round(sum(abs(x) for x in diffs) / len(diffs), 2)
        out["rmse_ug_l"] = round(math.sqrt(sum(x * x for x in diffs) / len(diffs)), 2)
        rel = [(a - b) / b for a, b in quant if b > 0]
        out["mean_relative_bias_pct"] = round(100 * sum(rel) / len(rel), 1) if rel else None
        if len(quant) >= 3:
            fit = linear_fit([b for _, b in quant], [a for a, _ in quant])
            out["node_vs_lab_slope"] = round(fit["slope"], 3)
            out["node_vs_lab_r2"] = round(fit["r_squared"], 3)
    spec = [(a, b, c) for a, b, c in pairs if c is not None and b > 0]
    if spec:
        out["lab_as3_fraction"] = round(sum(c / b for _, b, c in spec) / len(spec), 3)
        recov = [a / b for a, b, _ in spec if b >= lod]
        if recov:
            out["node_total_recovery"] = round(sum(recov) / len(recov), 3)
    if missed:
        out["message"] = (f"The node missed {missed} of {len(unsafe)} lab-confirmed unsafe samples. "
                          "Do not rely on a node 'No arsenic detected' here until this is resolved.")
    elif unsafe:
        out["message"] = f"The node flagged all {len(unsafe)} lab-confirmed unsafe samples."
    else:
        out["message"] = "No lab-confirmed unsafe samples yet, so the node's ability to catch them is untested."
    return out


# ---------------------------------------------------------------------------- calibration
def linear_fit(x: Sequence[float], y: Sequence[float]) -> Dict[str, float]:
    n = len(x)
    if n < 2:
        raise ValueError("At least two points are needed.")
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx == 0:
        raise ValueError("The x values are all the same.")
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_res = sum((b - (slope * a + intercept)) ** 2 for a, b in zip(x, y))
    ss_tot = sum((b - my) ** 2 for b in y)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    s_y = math.sqrt(ss_res / (n - 2)) if n > 2 else 0.0
    return {"slope": slope, "intercept": intercept, "r_squared": r2, "s_y": s_y, "n": n, "sxx": sxx, "mean_x": mx}


def fit_external(points: Sequence[Tuple[float, float]]) -> Dict:
    """Standards of known concentration (µg/L) vs peak (µA). Returns slope in µA per mg/L (the unit the
    firmware and app.standards use), intercept in µA, R² and LOD / LOQ from the residual standard deviation."""
    if len(points) < 3:
        raise ValueError("Use at least three standards (for example 0, 20 and 50 µg/L).")
    f = linear_fit([c for c, _ in points], [p for _, p in points])
    if f["slope"] <= 0:
        raise ValueError("The peak does not grow with concentration; check the standards and the electrode.")
    lod = 3.3 * f["s_y"] / f["slope"] if f["s_y"] > 0 else None
    return {"method": "external_standards", "slope_ua_per_mgl": f["slope"] * 1000.0, "intercept_ua": f["intercept"],
            "r_squared": f["r_squared"], "lod_ug_l": lod, "loq_ug_l": (lod * 10 / 3.3) if lod else None,
            "range_ug_l": (min(c for c, _ in points), max(c for c, _ in points)), "n": f["n"]}


def fit_standard_addition(sample_peak_ua: float, additions: Sequence[Tuple[float, float]],
                          blank_peak_ua: Optional[float] = None) -> Dict:
    """Standard addition: the sample alone, then the same sample spiked with known amounts of arsenic
    (µg/L added, peak µA). The line through the points crosses zero current at minus the sample's own
    concentration. Because the spikes sit in the real water, the slope already includes the matrix
    effects (copper, organics, salinity) that make factory calibrations wrong in the field."""
    if len(additions) < 2:
        raise ValueError("Use at least two additions (for example +20 and +40 µg/L).")
    blank = CALIBRATION_INTERCEPT if blank_peak_ua is None else blank_peak_ua
    pts = [(0.0, sample_peak_ua)] + list(additions)
    f = linear_fit([c for c, _ in pts], [p - blank for _, p in pts])
    if f["slope"] <= 0:
        raise ValueError("The peak does not grow with the additions; check the spikes and the electrode.")
    c0 = f["intercept"] / f["slope"]
    # uncertainty of the extrapolated concentration (standard addition formula)
    se = None
    if f["n"] > 2 and f["s_y"] > 0:
        ybar = sum(p - blank for _, p in pts) / f["n"]
        se = (f["s_y"] / f["slope"]) * math.sqrt(1 / f["n"] + ybar ** 2 / (f["slope"] ** 2 * f["sxx"]))
    return {"method": "standard_addition", "sample_ug_l": max(0.0, c0), "sample_ug_l_se": se,
            "slope_ua_per_mgl": f["slope"] * 1000.0, "intercept_ua": blank, "r_squared": f["r_squared"],
            "lod_ug_l": (3.3 * f["s_y"] / f["slope"]) if f["s_y"] > 0 else None, "n": f["n"],
            "range_ug_l": (0.0, max(c for c, _ in additions))}


def factory_calibration() -> Dict:
    from .standards import CALIBRATION_PROVENANCE, CALIBRATION_SOURCE
    return {"calibration_id": "factory", "slope_ua_per_mgl": CALIBRATION_SLOPE, "intercept_ua": CALIBRATION_INTERCEPT,
            "lod_ug_l": LOD_UG_L, "source": "factory", "origin": CALIBRATION_SOURCE, "provenance": CALIBRATION_PROVENANCE}


def active_calibration(db: Session, device: "models.Device") -> Dict:
    """This node's calibration: its own, else its electrode lot's, else a global one, else factory."""
    q = db.query(models.CalibrationRecord).filter(models.CalibrationRecord.is_active.is_(True))
    own = q.filter(models.CalibrationRecord.device_id == device.id).order_by(models.CalibrationRecord.calibration_date.desc()).first()
    rec, source = own, "device"
    if rec is None:
        rec = q.filter(models.CalibrationRecord.device_id.is_(None)).order_by(models.CalibrationRecord.calibration_date.desc()).first()
        source = "global"
    if rec is None:
        return factory_calibration()
    return {"calibration_id": rec.calibration_id, "slope_ua_per_mgl": rec.slope, "intercept_ua": rec.intercept,
            "lod_ug_l": rec.lod_ug_l, "source": source, "method": rec.method, "electrode_lot": rec.electrode_lot,
            "calibrated_at": _utc(rec.calibration_date), "r_squared": rec.r_squared}


# ---------------------------------------------------------------------------- JJM-style export
JJM_COLUMNS = ["State", "District", "Block", "Gram Panchayat", "Village", "Source Type", "Source ID", "Latitude",
               "Longitude", "Sample ID", "Sample Date", "Test Type", "Method", "Parameter", "Result", "Unit",
               "Acceptable Limit", "Permissible Limit", "Result Status", "Laboratory", "Remarks"]


def _status_mg_l(value_ug_l: float, test_type: str, lod: float) -> str:
    if test_type == "Sensor (ASV)" and value_ug_l < lod:
        return "Not detected (below sensor detection limit; lab test needed)"
    return "Above limit" if value_ug_l > BIS_PERMISSIBLE_LIMIT_UG_L else "Within limit"


def jjm_rows(devices: List["models.Device"], readings: List["models.Reading"], labs: List["models.LabResult"]) -> List[List]:
    by_id = {d.id: d for d in devices}
    limit = round(BIS_PERMISSIBLE_LIMIT_UG_L / 1000.0, 3)

    def site(dev):
        if dev is None:
            return ["", "", "", "", "", "", "", "", ""]
        return [dev.state or "", dev.district or "", dev.block or "", dev.panchayat or "", dev.village or "",
                dev.source_kind or "", dev.device_code, dev.latitude if dev.latitude is not None else "",
                dev.longitude if dev.longitude is not None else ""]

    rows = []
    for r in readings:
        dev = by_id.get(r.device_id)
        remarks = []
        if r.qc_flags:
            remarks.append("QC: " + r.qc_flags.replace(",", "; "))
        if r.arsenic_species == "as3_only":
            remarks.append("As(III) only")
        rows.append(site(dev) + [f"AQS-{r.id}", _utc(r.recorded_at).strftime("%d-%m-%Y"), "Sensor (ASV)",
                                 "Anodic stripping voltammetry", "Arsenic (as As)", round(r.arsenic_ppb / 1000.0, 4),
                                 "mg/L", limit, limit, _status_mg_l(r.arsenic_ppb, "Sensor (ASV)", LOD_UG_L),
                                 "", "; ".join(remarks)])
    for lab in labs:
        dev = by_id.get(lab.device_id)
        rows.append(site(dev) + [lab.sample_code or f"LAB-{lab.id}", _utc(lab.sampled_at).strftime("%d-%m-%Y"),
                                 "Laboratory" if lab.lab_method != "FTK" else "Field Test Kit", lab.lab_method,
                                 "Arsenic (as As)", round(lab.arsenic_ug_l / 1000.0, 4), "mg/L", limit, limit,
                                 _status_mg_l(lab.arsenic_ug_l, "Laboratory", LOD_UG_L), lab.lab_name or "",
                                 ("NABL accredited" if lab.nabl_accredited else "")])
    return rows
