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
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

ALPHA = 0.10
MIN_POINTS = 6


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
    pts = sorted(points, key=lambda p: p[0])
    n = len(pts)
    out: Dict = {"n": n, "method": "Mann-Kendall (tie-corrected) + Sen's slope", "alpha": ALPHA,
                 "non_detects_as": f"{lod:g} µg/L (sensor detection limit)"}
    if n < MIN_POINTS:
        out.update(direction="insufficient_data", significant=False,
                   message=f"Needs at least {MIN_POINTS} readings to judge a trend ({n} so far).")
        return out
    t0 = pts[0][0]
    days = [(t - t0).total_seconds() / 86400.0 for t, _ in pts]
    vals = [max(v, lod) for _, v in pts]          # censor non-detects to one value
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
        out["message"] = (f"Arsenic is rising by about {slope * 7:.1f} µg/L per week. "
                          f"At this rate it would reach {nxt:g} µg/L in about {days_to:.0f} days.")
    elif direction == "rising":
        out["message"] = f"Arsenic is rising by about {slope * 7:.1f} µg/L per week."
    elif direction == "falling":
        out["message"] = f"Arsenic is falling by about {abs(slope) * 7:.1f} µg/L per week."
    else:
        out["message"] = f"No clear trend over {days[-1]:.0f} days."
    out["evidence"] = f"Mann-Kendall {_p_text(mk['p_value'])}, n = {n}, {days[-1]:.0f} days"
    return out
