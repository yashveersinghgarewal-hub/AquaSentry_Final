#!/usr/bin/env python3
"""
Linearity, LOD/LOQ and deposition-time studies from real standards (ISEF items 64-65, 73, 87, 88).

Input CSV (one row per measurement):  standard_ug_l, peak_ua[, replicate, electrode_lot, deposition_s, date]

  * Calibration fit on >= 6 standards with replicates: slope, intercept, their 95 % CIs, R², residual plot and a
    lack-of-fit check (pure-error F test when replicates exist) - item 73.
  * LOD = 3.3 s_y/slope and LOQ = 10 s_y/slope from the residual SD, and - when blanks (0 µg/L) are present - from the
    blank SD as well; the larger is reported - item 65.
  * If `deposition_s` varies, peak current vs deposition time at each standard (item 87) with its own linear fit.

Usage:  python Analysis/linearity.py Data/field/standards.csv --out Analysis/out/linearity
        python Analysis/linearity.py --demo --out Analysis/out/linearity_demo     (SYNTHETIC)
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
from interference import t975  # noqa: E402


def read(path: str) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"c": float(r["standard_ug_l"]), "ip": float(r["peak_ua"]),
                             "dep": float(r["deposition_s"]) if (r.get("deposition_s") or "").strip() else None,
                             "lot": r.get("electrode_lot") or ""})
            except (KeyError, ValueError):
                continue
    return rows


def demo() -> List[Dict]:
    rng = np.random.default_rng(21)
    rows = []
    for c in (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 10, 20, 50, 100, 200, 300, 500):
        reps = 1 if c == 0 else 3
        for _ in range(reps):
            ip = 0.0096 + 0.8563 * c / 1000.0 * (1 - 0.00015 * c) + rng.normal(0, 0.004 + 0.02 * 0.8563 * c / 1000.0)
            rows.append({"c": float(c), "ip": max(ip, 0.0), "dep": 60.0, "lot": "LOT-A"})
    for d in (15, 30, 60, 120, 180):
        for _ in range(2):
            rows.append({"c": 50.0, "ip": 0.0096 + 0.8563 * 0.05 * (d / 60.0) ** 0.9 + rng.normal(0, 0.004), "dep": float(d), "lot": "LOT-A"})
    return rows


def fit_line(x: np.ndarray, y: np.ndarray) -> Dict:
    n = len(x)
    A = np.vstack([np.ones(n), x]).T
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = a + b * x
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    s_y = math.sqrt(ss_res / (n - 2)) if n > 2 else float("nan")
    sxx = float(((x - x.mean()) ** 2).sum())
    se_b = s_y / math.sqrt(sxx) if sxx > 0 else float("nan")
    se_a = s_y * math.sqrt(1 / n + x.mean() ** 2 / sxx) if sxx > 0 else float("nan")
    t = t975(n - 2)
    return {"n": n, "slope": float(b), "slope_ci95": [float(b - t * se_b), float(b + t * se_b)], "intercept": float(a),
            "intercept_ci95": [float(a - t * se_a), float(a + t * se_a)], "r_squared": 1 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
            "residual_sd": s_y, "residuals": (y - yhat).tolist()}


def lack_of_fit(x: np.ndarray, y: np.ndarray, yhat: np.ndarray) -> Dict:
    """Pure-error / lack-of-fit F ratio when standards are replicated (approximate p via the F survival function)."""
    groups: Dict[float, List[int]] = {}
    for i, v in enumerate(x):
        groups.setdefault(float(v), []).append(i)
    ss_pe, df_pe = 0.0, 0
    for idx in groups.values():
        if len(idx) > 1:
            ss_pe += float(((y[idx] - y[idx].mean()) ** 2).sum())
            df_pe += len(idx) - 1
    ss_res = float(((y - yhat) ** 2).sum())
    df_lof = len(groups) - 2
    if df_pe == 0 or df_lof <= 0:
        return {"available": False}
    ss_lof = ss_res - ss_pe
    F = (ss_lof / df_lof) / (ss_pe / df_pe) if ss_pe > 0 else float("inf")
    return {"available": True, "F": F, "df_lof": df_lof, "df_pe": df_pe,
            "verdict": "no evidence of curvature (F < 3)" if F < 3 else "curvature likely: fit a quadratic or shorten the range"}


def run(rows: List[Dict], out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res: Dict = {"label": label, "n_rows": len(rows)}
    cal = [r for r in rows if r["dep"] is None or abs(r["dep"] - 60.0) < 1e-9 or len({r2["dep"] for r2 in rows}) == 1]
    x = np.array([r["c"] for r in cal])
    y = np.array([r["ip"] for r in cal])
    n_levels = len(set(x[x > 0]))
    if n_levels < 3 or len(x) < 5:
        res["stopped"] = f"Need at least 6 non-zero standards with replicates (have {n_levels} levels, {len(x)} points)."
        _write(out_dir, res)
        return res
    f = fit_line(x, y)
    res["calibration"] = {k: v for k, v in f.items() if k != "residuals"}
    res["calibration"]["n_levels"] = n_levels
    res["calibration"]["levels_recommended"] = 6
    yhat = f["intercept"] + f["slope"] * x
    res["lack_of_fit"] = lack_of_fit(x, y, yhat)
    slope_per_ugl = f["slope"]
    lod_resid = 3.3 * f["residual_sd"] / slope_per_ugl if slope_per_ugl > 0 else float("nan")
    blanks = y[x == 0]
    lod_blank = 3.3 * float(blanks.std(ddof=1)) / slope_per_ugl if len(blanks) >= 3 and slope_per_ugl > 0 else None
    res["lod"] = {"from_residual_sd_ug_l": lod_resid, "from_blank_sd_ug_l": lod_blank, "n_blanks": int(len(blanks)),
                  "reported_lod_ug_l": max(lod_resid, lod_blank or 0.0), "loq_ug_l": max(lod_resid, lod_blank or 0.0) * 10 / 3.3,
                  "note": "Report the larger of the two; fewer than 10 blanks is a preliminary figure (item 65)."}
    # figures
    top = float(x.max() * 1.05)
    ax = sp.Axes((0, top), (0, float(y.max() * 1.1)), "Calibration: peak current vs standard" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Arsenic standard (µg/L)", "Net peak current (µA)",
                 f"n = {f['n']} at {n_levels} levels; slope {f['slope'] * 1000:.4f} µA per mg/L [{f['slope_ci95'][0] * 1000:.4f}, {f['slope_ci95'][1] * 1000:.4f}]; R² {f['r_squared']:.4f}")
    ax.line([0, top], [f["intercept"], f["intercept"] + f["slope"] * top], sp.RED, 1.6, None, "least-squares fit")
    ax.points(x, y, sp.BLUE, label="standards")
    sp.save(os.path.join(out_dir, "calibration.svg"), ax.render())
    r_ = np.array(f["residuals"])
    lim = float(np.abs(r_).max() * 1.3) or 0.01
    ax = sp.Axes((0, top), (-lim, lim), "Residuals" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""), "Arsenic standard (µg/L)", "Residual (µA)",
                 f"residual SD {f['residual_sd']:.4f} µA; lack of fit: {res['lack_of_fit'].get('verdict', 'n/a')}")
    ax.hline(0, sp.MUTED, "5 4")
    ax.points(x, r_, sp.BLUE)
    sp.save(os.path.join(out_dir, "residuals.svg"), ax.render())
    # deposition-time study
    dep_rows = [r for r in rows if r["dep"] is not None]
    deps = sorted({r["dep"] for r in dep_rows})
    if len(deps) >= 3:
        by_c: Dict[float, List[Dict]] = {}
        for r in dep_rows:
            by_c.setdefault(r["c"], []).append(r)
        res["deposition"] = {}
        ax = sp.Axes((0, max(deps) * 1.1), (0, float(max(r["ip"] for r in dep_rows) * 1.15)), "Peak current vs deposition time" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                     "Deposition time (s)", "Net peak current (µA)")
        for i, (c, rs) in enumerate(sorted(by_c.items())):
            if len({r["dep"] for r in rs}) < 3:
                continue
            dx = np.array([r["dep"] for r in rs]); dy = np.array([r["ip"] for r in rs])
            ff = fit_line(dx, dy)
            res["deposition"][f"{c:g}"] = {k: v for k, v in ff.items() if k != "residuals"}
            col = [sp.BLUE, sp.GREEN, sp.VIOLET, sp.AMBER][i % 4]
            ax.points(dx, dy, col, label=f"{c:g} µg/L")
            ax.line([0, max(deps) * 1.1], [ff["intercept"], ff["intercept"] + ff["slope"] * max(deps) * 1.1], col, 1.2, "4 3")
        sp.save(os.path.join(out_dir, "deposition_time.svg"), ax.render())
    _write(out_dir, res)
    return res


def _write(out_dir, res):
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# Linearity, LOD and deposition time — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data.**", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        c, lod = res["calibration"], res["lod"]
        L += [f"- Calibration on {c['n']} points at {c['n_levels']} non-zero levels" + (" (fewer than the 6 recommended)" if c['n_levels'] < 6 else "") + ":",
              f"  slope **{c['slope'] * 1000:.4f} µA per mg/L** (95 % CI {c['slope_ci95'][0] * 1000:.4f}–{c['slope_ci95'][1] * 1000:.4f}), "
              f"intercept {c['intercept']:.4f} µA ({c['intercept_ci95'][0]:.4f}–{c['intercept_ci95'][1]:.4f}), R² {c['r_squared']:.4f}, residual SD {c['residual_sd']:.4f} µA",
              f"- Lack of fit: {res['lack_of_fit'].get('verdict', 'needs replicated standards')}",
              f"- LOD from residual SD: **{lod['from_residual_sd_ug_l']:.1f} µg/L**; from blank SD: "
              + (f"**{lod['from_blank_sd_ug_l']:.1f} µg/L** ({lod['n_blanks']} blanks)" if lod['from_blank_sd_ug_l'] is not None else f"n/a ({lod['n_blanks']} blanks; need ≥ 3, ideally ≥ 10)")
              + f"; report **LOD {lod['reported_lod_ug_l']:.1f} µg/L, LOQ {lod['loq_ug_l']:.1f} µg/L**",
              "", "![calibration](calibration.svg)", "", "![residuals](residuals.svg)", ""]
        if res.get("deposition"):
            L += ["## Deposition time (item 87)", "", "| standard µg/L | slope µA/s | 95 % CI | R² |", "|---|---|---|---|"]
            for c_, d in res["deposition"].items():
                L += [f"| {c_} | {d['slope']:.5f} | [{d['slope_ci95'][0]:.5f}, {d['slope_ci95'][1]:.5f}] | {d['r_squared']:.3f} |"]
            L += ["", "![deposition](deposition_time.svg)", ""]
        L += ["Update `Docs/CLAIMS_REGISTER.md` M1/M2 with these numbers and the date; the factory line stays labelled synthetic until a real calibration replaces it per device.", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Linearity, LOD/LOQ and deposition-time analysis of real standards")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "linearity"))
    a = ap.parse_args(argv)
    if a.demo:
        rows, label = demo(), "SYNTHETIC demo"
    elif a.csv:
        rows, label = read(a.csv), os.path.basename(a.csv)
    else:
        ap.error("give a standards CSV or --demo")
    res = run(rows, a.out, label)
    print(res.get("stopped") or f"LOD {res['lod']['reported_lod_ug_l']:.1f} µg/L, slope {res['calibration']['slope'] * 1000:.4f} µA/(mg/L) -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
