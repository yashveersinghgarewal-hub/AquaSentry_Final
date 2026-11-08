#!/usr/bin/env python3
"""
Interference and matrix studies with the right statistics (ISEF items 67, 68, 69, 139).

Input CSV, one row per measurement:
    interferent, interferent_conc, unit, as_true_ug_l, as_measured_ug_l[, replicate, matrix, electrode_lot]
e.g. copper spiked 0-200 µg/L into a fixed 50 µg/L arsenic sample; pH 5-9 at fixed arsenic; temperature 15-40 °C.

For every interferent the script fits recovery (%) = a + b × concentration by least squares, reports b with its 95 %
confidence interval and the concentration at which recovery leaves the 80-120 % window, and draws recovery vs
concentration with the fit and the window. "Looked fine" is not a result; a slope with an interval is (item 139).

Usage:  python Analysis/interference.py Data/field/interference.csv --out Analysis/out/interference
        python Analysis/interference.py --demo --out Analysis/out/interference_demo       (SYNTHETIC)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from typing import Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402

WINDOW = (80.0, 120.0)
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def t975(df: int) -> float:
    if df <= 0:
        return float("nan")
    keys = sorted(T975)
    for k in keys:
        if df <= k:
            return T975[k]
    return 1.96


def read(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"interferent": r["interferent"].strip(), "conc": float(r["interferent_conc"]),
                             "unit": (r.get("unit") or "").strip(), "true": float(r["as_true_ug_l"]),
                             "meas": float(r["as_measured_ug_l"]), "matrix": r.get("matrix") or ""})
            except (KeyError, ValueError):
                continue
    return rows


def demo() -> List[Dict]:
    rng = np.random.default_rng(5)
    rows = []
    for c in (0, 25, 50, 100, 150, 200):
        for _ in range(3):
            rows.append({"interferent": "copper", "conc": c, "unit": "µg/L", "true": 50.0,
                         "meas": 50.0 * (1 + 0.0015 * c) + rng.normal(0, 2.5), "matrix": "DI water"})
    for c in (0, 1, 2, 5, 10):
        for _ in range(3):
            rows.append({"interferent": "iron", "conc": c, "unit": "mg/L", "true": 50.0,
                         "meas": 50.0 * (1 - 0.03 * c) + rng.normal(0, 2.5), "matrix": "DI water"})
    for c in (5, 6, 7, 8, 9):
        for _ in range(3):
            rows.append({"interferent": "pH", "conc": c, "unit": "pH", "true": 50.0,
                         "meas": 50.0 * (1 - 0.04 * (c - 7)) + rng.normal(0, 2.0), "matrix": "DI water"})
    return rows


def fit(x: np.ndarray, y: np.ndarray) -> Dict:
    n = len(x)
    if n < 3 or x.std() == 0:
        return {"n": n, "note": "need ≥ 3 points at ≥ 2 concentrations"}
    A = np.vstack([np.ones(n), x]).T
    coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    a, b = coef
    yhat = A @ coef
    s2 = float(((y - yhat) ** 2).sum() / (n - 2))
    sxx = float(((x - x.mean()) ** 2).sum())
    se_b = math.sqrt(s2 / sxx)
    se_a = math.sqrt(s2 * (1 / n + x.mean() ** 2 / sxx))
    t = t975(n - 2)
    out = {"n": n, "intercept_pct": float(a), "intercept_ci95": [float(a - t * se_a), float(a + t * se_a)],
           "slope_pct_per_unit": float(b), "slope_ci95": [float(b - t * se_b), float(b + t * se_b)],
           "residual_sd_pct": math.sqrt(s2), "slope_significant": not (b - t * se_b <= 0 <= b + t * se_b)}
    # where does the fitted recovery leave the window?
    lo, hi = WINDOW
    crossings = []
    for edge in (lo, hi):
        if abs(b) > 1e-12:
            xc = (edge - a) / b
            if x.min() <= xc <= x.max() * 1.5:
                crossings.append(round(float(xc), 3))
    out["leaves_window_at"] = min(crossings) if crossings else None
    return out


def run(rows: List[Dict], out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res: Dict = {"label": label, "window_pct": list(WINDOW), "interferents": {}}
    groups: Dict[str, List[Dict]] = {}
    for r in rows:
        groups.setdefault(r["interferent"], []).append(r)
    for name, g in sorted(groups.items()):
        x = np.array([r["conc"] for r in g])
        rec = np.array([r["meas"] / r["true"] * 100.0 for r in g])
        f = fit(x, rec)
        f["unit"] = g[0]["unit"]
        f["recovery_at_max_pct"] = float(rec[x == x.max()].mean())
        res["interferents"][name] = f
        ax = sp.Axes((float(x.min()) - 0.02 * (x.max() - x.min() or 1), float(x.max()) * 1.05 if x.max() > 0 else 1),
                     (min(60.0, float(rec.min()) - 5), max(140.0, float(rec.max()) + 5)),
                     f"Arsenic recovery vs {name}" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                     f"{name} ({g[0]['unit']})", "Recovery of arsenic (%)",
                     (f"slope {f['slope_pct_per_unit']:+.3f} %/unit [{f['slope_ci95'][0]:+.3f}, {f['slope_ci95'][1]:+.3f}], n = {f['n']}"
                      if "slope_pct_per_unit" in f else "too few points"))
        ax.hline(100, sp.MUTED, "5 4")
        ax.hline(WINDOW[0], sp.AMBER, "6 4", "80-120 % window")
        ax.hline(WINDOW[1], sp.AMBER, "6 4")
        if "slope_pct_per_unit" in f:
            xs = [float(x.min()), float(x.max())]
            ax.line(xs, [f["intercept_pct"] + f["slope_pct_per_unit"] * v for v in xs], sp.RED, 1.8, None, "least-squares fit")
        ax.points(x, rec, sp.BLUE, label="measurements")
        sp.save(os.path.join(out_dir, f"recovery_{name.lower().replace(' ', '_')}.svg"), ax.render())
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, default=float)
    L = [f"# Interference study — {label}", ""]
    if "SYNTHETIC" in label:
        L += ["> **SYNTHETIC demonstration data.**", ""]
    L += ["| interferent | n | slope of recovery (% per unit) | 95 % CI | significant? | recovery at max | leaves 80-120 % at |", "|---|---|---|---|---|---|---|"]
    for name, f in res["interferents"].items():
        if "slope_pct_per_unit" not in f:
            L += [f"| {name} | {f['n']} | – | – | – | – | {f.get('note', '')} |"]
            continue
        L += [f"| {name} | {f['n']} | {f['slope_pct_per_unit']:+.3f} | [{f['slope_ci95'][0]:+.3f}, {f['slope_ci95'][1]:+.3f}] | "
              f"{'yes' if f['slope_significant'] else 'no'} | {f['recovery_at_max_pct']:.0f} % | "
              f"{str(f['leaves_window_at']) + ' ' + f['unit'] if f['leaves_window_at'] is not None else 'not within range tested'} |"]
    L += ["", "A slope whose interval excludes zero is a real interference; the 'leaves window' column is the concentration above which the "
          "method needs a mitigation (standard addition, masking, a different potential window) — item 67.", ""]
    for name in res["interferents"]:
        L += [f"![{name}](recovery_{name.lower().replace(' ', '_')}.svg)", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Recovery vs interferent concentration with confidence intervals")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "interference"))
    a = ap.parse_args(argv)
    if a.demo:
        rows, label = demo(), "SYNTHETIC demo"
    elif a.csv:
        rows, label = read(a.csv), os.path.basename(a.csv)
    else:
        ap.error("give a CSV or --demo")
    res = run(rows, a.out, label)
    for k, v in res["interferents"].items():
        if "slope_pct_per_unit" in v:
            print(f"{k}: slope {v['slope_pct_per_unit']:+.3f} %/unit, CI {v['slope_ci95']}, significant={v['slope_significant']}")
    print(f"-> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
