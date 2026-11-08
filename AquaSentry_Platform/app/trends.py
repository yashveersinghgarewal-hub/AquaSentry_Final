"""
Arsenic trend detection for one water source: Mann-Kendall test + Sen's slope.

Why: a well can be "fine" every month while slowly getting worse. Groundwater-quality studies use the
non-parametric Mann-Kendall test (no normality assumption, robust to outliers) to decide whether a
monotonic trend exists, and Sen's slope (the median of all pairwise slopes) for how fast it changes.

Choices, following common groundwater practice:
- values below the sensor's detection limit are set to the detection limit (one shared "non-detect"
  value), so the sensor's noise below 20 µg/L cannot fake a trend; they become ties
- the variance uses the tie correction
- a trend is reported at p < 0.10 with a non-zero Sen's slope and at least 6 readings
  (4 is the mathematical minimum for p < 0.10; 6 gives a usable test)
- the projection to the next limit is a straight-line estimate, labelled as such
- when a node reports several times a day, the series is reduced to daily medians first: hourly
  readings are serially correlated, which makes Mann-Kendall report trends that are not there
  (Hirsch & Slack 1984, USGS). It also keeps the O(n^2) pair loops small (90 days -> 90 points)
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional, Sequence, Tuple

ALPHA = 0.10
PROJECTION_HORIZON_DAYS = 730          # v5.10: straight-line projections beyond two years are not shown as a date
MIN_POINTS = 6
MAX_POINTS = 400        # beyond this even daily medians are thinned to weekly medians


def _bucket_medians(pts: List[Tuple[datetime, float]], seconds: float) -> List[Tuple[datetime, float]]:
    """Median value per time bucket, stamped at the bucket's median time. pts must be sorted."""
    out, cur, key = [], [], None
    for t, v in pts:
        k = int(t.timestamp() // seconds)
        if key is not None and k != key:
            out.append(cur)
            cur = []
        cur.append((t, v))
        key = k
    if cur:
        out.append(cur)
    return [(b[len(b) // 2][0], median(v for _, v in b)) for b in out]


def reduce_series(pts: List[Tuple[datetime, float]]) -> Tuple[List[Tuple[datetime, float]], str]:
    """Daily (or weekly) medians when there is more than one reading per day; raw readings otherwise."""
    daily = _bucket_medians(pts, 86400.0)
    if len(daily) == len(pts) or len(daily) < MIN_POINTS:
        return pts, "none"
    if len(daily) > MAX_POINTS:
        return _bucket_medians(pts, 7 * 86400.0), "weekly median"
    return daily, "daily median"


def _norm_sf(z: float) -> float:
    """Upper tail of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def mann_kendall(values: Sequence[float]) -> Dict[str, float]:
    n = len(values)
    s = 0
    for i in range(n - 1):
        xi = values[i]
        for j in range(i + 1, n):
            d = values[j] - xi
            s += (d > 0) - (d < 0)
    ties = Counter(values).values()
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties if t > 1)) / 18.0
    if var <= 0:
        z = 0.0
    elif s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0
    p = 2 * _norm_sf(abs(z))
    pairs = n * (n - 1) / 2
    return {"n": n, "S": s, "var_S": round(var, 3), "Z": round(z, 4), "p_value": round(min(1.0, p), 5),
            "tau": round(s / pairs, 4) if pairs else 0.0}


def sens_slope(times_days: Sequence[float], values: Sequence[float]) -> Optional[float]:
    slopes = []
    n = len(values)
    for i in range(n - 1):
        for j in range(i + 1, n):
            dt = times_days[j] - times_days[i]
            if dt > 1e-9:
                slopes.append((values[j] - values[i]) / dt)
    if not slopes:
        return None
    slopes.sort()
    m = len(slopes)
    return slopes[m // 2] if m % 2 else 0.5 * (slopes[m // 2 - 1] + slopes[m // 2])


def _p_text(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def analyse(points: List[Tuple[datetime, float]], lod: float, limits: Sequence[float] = (20.0, 150.0)) -> Dict:
    """points: (time, arsenic µg/L), any order. Returns a JSON-ready summary."""
    raw = sorted(points, key=lambda p: p[0])
    # censor non-detects first, so a day's median is never pulled around by sub-LOD noise
    pts, aggregation = reduce_series([(t, max(v, lod)) for t, v in raw])
    n = len(pts)
    out: Dict = {"n": n, "readings": len(raw), "aggregation": aggregation,
                 "method": "Mann-Kendall (tie-corrected) + Sen's slope", "alpha": ALPHA,
                 "non_detects_as": f"{lod:g} µg/L (sensor detection limit)"}
    if n < MIN_POINTS:
        out.update(direction="insufficient_data", significant=False,
                   message=f"Needs at least {MIN_POINTS} readings to judge a trend ({n} so far).")
        return out
    t0 = pts[0][0]
    days = [(t - t0).total_seconds() / 86400.0 for t, _ in pts]
    vals = [v for _, v in pts]
    mk = mann_kendall(vals)
    slope = sens_slope(days, vals) or 0.0
    significant = mk["p_value"] < ALPHA and abs(slope) > 1e-9
    direction = ("rising" if slope > 0 else "falling") if significant else "no_trend"
    recent = sorted(vals[-3:])[len(vals[-3:]) // 2]
    out.update(mann_kendall=mk, significant=significant, direction=direction,
               sen_slope_ug_per_week=round(slope * 7, 3), span_days=round(days[-1], 1),
               recent_median_ug_l=round(recent, 1), first=pts[0][0].isoformat(), last=pts[-1][0].isoformat())
    nxt = next((L for L in limits if recent < L), None)
    if direction == "rising" and nxt is not None and slope > 0:
        days_to = (nxt - recent) / slope
        out["projection"] = {"limit_ug_l": nxt, "days": round(days_to, 1),
                             "note": "Straight-line estimate from Sen's slope; real aquifers can change faster or slower."}
        # v5.10: a straight line is not a forecast years ahead; beyond two years say so instead of "in about 4539 days"
        if days_to > PROJECTION_HORIZON_DAYS:
            out["message"] = (f"Arsenic is rising slowly, by about {slope * 7:.1f} µg/L per week. At this rate it would not "
                              f"reach {nxt:g} µg/L within two years.")
        elif days_to > 60:
            out["message"] = (f"Arsenic is rising by about {slope * 7:.1f} µg/L per week. "
                              f"At this rate it would reach {nxt:g} µg/L in about {days_to / 30.4:.0f} months.")
        else:
            out["message"] = (f"Arsenic is rising by about {slope * 7:.1f} µg/L per week. "
                              f"At this rate it would reach {nxt:g} µg/L in about {days_to:.0f} days.")
    elif direction == "rising":
        out["message"] = f"Arsenic is rising by about {slope * 7:.1f} µg/L per week."
    elif direction == "falling":
        out["message"] = f"Arsenic is falling by about {abs(slope) * 7:.1f} µg/L per week."
    else:
        out["message"] = f"No clear trend over {days[-1]:.0f} days."
    per = f" ({aggregation}s of {len(raw)} readings)" if aggregation != "none" else ""
    out["evidence"] = f"Mann-Kendall {_p_text(mk['p_value'])}, n = {n}{per}, {days[-1]:.0f} days"
    return out
