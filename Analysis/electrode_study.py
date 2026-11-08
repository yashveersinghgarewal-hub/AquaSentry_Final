#!/usr/bin/env python3
"""
Electrode lifetime, electrode-to-electrode variability and repeatability (ISEF items 70, 71, 72, 80).

Input CSV (Data/field/electrode_log_template.csv), one row per measurement of a check standard or sample:
    electrode_id, electrode_lot, scan_number, date, standard_ug_l, peak_ua[, session, operator, note]

  * Lifetime (70): for each electrode, the response (peak / standard) vs scan number; the scan at which it drops 10 %
    below its first-five average, with the straight-line drift per 100 scans.
  * Variability (71): slope per electrode (peak vs standard across its runs), mean slope, CV % across electrodes and
    across lots; a one-way comparison of lots (between-lot vs within-lot spread).
  * Repeatability / intermediate precision (72): CV % of repeated measurements of the same standard within a session
    (repeatability) and across sessions / days / operators (intermediate precision).

Usage:  python Analysis/electrode_study.py Data/field/electrode_log.csv --out Analysis/out/electrodes
        python Analysis/electrode_study.py --demo --out Analysis/out/electrodes_demo       (SYNTHETIC)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402


def read(path: str) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"e": r["electrode_id"].strip(), "lot": (r.get("electrode_lot") or "").strip(), "n": int(float(r["scan_number"])),
                             "c": float(r["standard_ug_l"]), "ip": float(r["peak_ua"]), "session": (r.get("session") or r.get("date") or "").strip(),
                             "op": (r.get("operator") or "").strip()})
            except (KeyError, ValueError):
                continue
    return rows


def demo() -> List[Dict]:
    rng = np.random.default_rng(8)
    rows = []
    for e in range(6):
        lot = "LOT-A" if e < 3 else "LOT-B"
        slope = 0.8563 * (1 + rng.normal(0, 0.06 if lot == "LOT-A" else 0.12)) / 1000.0
        life = int(rng.integers(60, 120))
        for n in range(1, 151):
            fade = 1.0 if n < life else max(0.5, 1 - 0.004 * (n - life))
            c = [10, 50, 100][n % 3]
            ip = 0.0096 + slope * c * fade + rng.normal(0, 0.003)
            rows.append({"e": f"E{e + 1}", "lot": lot, "n": n, "c": float(c), "ip": max(ip, 0.0), "session": f"S{(n - 1) // 30 + 1}", "op": "A" if e % 2 else "B"})
    return rows


def run(rows: List[Dict], out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res: Dict = {"label": label, "n_rows": len(rows)}
    by_e: Dict[str, List[Dict]] = {}
    for r in rows:
        by_e.setdefault(r["e"], []).append(r)
    if len(rows) < 10:
        res["stopped"] = "Fewer than 10 rows."
        _write(out_dir, res)
        return res
    life, slopes, lots = {}, {}, {}
    ax = sp.Axes((0, max(r["n"] for r in rows) * 1.02), (0.3, 1.3), "Electrode response vs scan number" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Scan number", "Response relative to the first 5 scans")
    ax.hline(0.9, sp.RED, "4 4", "−10 % (end of life)")
    cols = [sp.BLUE, sp.GREEN, sp.VIOLET, sp.AMBER, sp.RED, sp.MUTED]
    for i, (e, rs) in enumerate(sorted(by_e.items())):
        rs.sort(key=lambda r: r["n"])
        resp = np.array([(r["ip"] - 0.0096) / r["c"] if r["c"] > 0 else np.nan for r in rs])
        n = np.array([r["n"] for r in rs])
        ok = np.isfinite(resp)
        if ok.sum() < 5:
            continue
        ref = float(np.nanmean(resp[ok][:5]))
        rel = resp / ref
        below = np.where(ok & (rel < 0.9))[0]
        # first scan after which three consecutive points are below 0.9
        end = None
        for k in below:
            if k + 2 < len(rel) and (rel[k:k + 3] < 0.9).all():
                end = int(n[k])
                break
        drift = float(np.polyfit(n[ok], rel[ok], 1)[0] * 100)
        life[e] = {"scans_logged": int(len(rs)), "end_of_life_scan": end, "drift_pct_per_100_scans": drift * 100}
        c = np.array([r["c"] for r in rs]); ip = np.array([r["ip"] for r in rs])
        if len(set(c)) >= 2:
            sl = float(np.polyfit(c, ip, 1)[0])
            slopes[e] = sl
            lots.setdefault(rs[0]["lot"], []).append(sl)
        ax.line(n[ok].tolist(), rel[ok].tolist(), cols[i % len(cols)], 1.2, None, e if i < 6 else None)
    sp.save(os.path.join(out_dir, "lifetime.svg"), ax.render())
    res["lifetime"] = life
    if slopes:
        arr = np.array(list(slopes.values()))
        res["variability"] = {"n_electrodes": len(arr), "mean_slope_ua_per_ugl": float(arr.mean()), "cv_pct_across_electrodes": float(arr.std(ddof=1) / arr.mean() * 100) if len(arr) > 1 else None,
                              "by_lot": {lot: {"n": len(v), "mean": float(np.mean(v)), "cv_pct": float(np.std(v, ddof=1) / np.mean(v) * 100) if len(v) > 1 else None} for lot, v in lots.items()}}
        if len(lots) >= 2 and all(len(v) >= 2 for v in lots.values()):
            means = [np.mean(v) for v in lots.values()]
            within = np.mean([np.var(v, ddof=1) for v in lots.values()])
            between = np.var(means, ddof=1) * np.mean([len(v) for v in lots.values()])
            res["variability"]["lot_f_ratio"] = float(between / within) if within > 0 else None
            res["variability"]["lot_note"] = "between-lot spread clearly exceeds within-lot (F > 4): report per lot" if within > 0 and between / within > 4 else "lots look alike at this sample size"
    # precision
    groups_rep: Dict = {}
    groups_int: Dict = {}
    for r in rows:
        groups_rep.setdefault((r["e"], r["c"], r["session"]), []).append(r["ip"])
        groups_int.setdefault((r["e"], r["c"]), []).append(r["ip"])
    def cv(groups):
        vals = [np.std(v, ddof=1) / np.mean(v) * 100 for v in groups.values() if len(v) >= 3 and np.mean(v) > 0]
        return {"n_groups": len(vals), "median_cv_pct": float(np.median(vals)) if vals else None, "p90_cv_pct": float(np.percentile(vals, 90)) if vals else None}
    res["precision"] = {"repeatability_within_session": cv(groups_rep), "intermediate_across_sessions": cv(groups_int)}
    _write(out_dir, res)
    return res


def _write(out_dir, res):
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# Electrode study — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data.**", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        L += ["## Lifetime (item 70)", "", "| electrode | scans logged | end of life (scan) | drift % per 100 scans |", "|---|---|---|---|"]
        for e, d in res["lifetime"].items():
            L += [f"| {e} | {d['scans_logged']} | {d['end_of_life_scan'] if d['end_of_life_scan'] else 'not reached'} | {d['drift_pct_per_100_scans']:+.1f} |"]
        L += ["", "![lifetime](lifetime.svg)", ""]
        if res.get("variability"):
            v = res["variability"]
            L += ["## Variability (item 71)", "", f"- {v['n_electrodes']} electrodes; mean slope {v['mean_slope_ua_per_ugl'] * 1000:.4f} µA per mg/L; "
                  f"CV across electrodes **{v['cv_pct_across_electrodes']:.1f} %**" if v.get("cv_pct_across_electrodes") is not None else "- one electrode only"]
            for lot, d in v["by_lot"].items():
                L += [f"- {lot}: n = {d['n']}, mean slope {d['mean'] * 1000:.4f}, CV {d['cv_pct']:.1f} %" if d.get("cv_pct") is not None else f"- {lot}: n = {d['n']}"]
            if v.get("lot_note"):
                L += [f"- {v['lot_note']} (F = {v['lot_f_ratio']:.1f})"]
            L += [""]
        p = res["precision"]
        L += ["## Precision (item 72)", "",
              f"- Repeatability (same electrode, standard and session): median CV **{p['repeatability_within_session']['median_cv_pct']:.1f} %**, 90th percentile {p['repeatability_within_session']['p90_cv_pct']:.1f} % ({p['repeatability_within_session']['n_groups']} groups)"
              if p["repeatability_within_session"]["median_cv_pct"] is not None else "- Repeatability: need ≥ 3 repeats of a standard within a session",
              f"- Intermediate precision (across sessions / days / operators): median CV **{p['intermediate_across_sessions']['median_cv_pct']:.1f} %**, 90th percentile {p['intermediate_across_sessions']['p90_cv_pct']:.1f} %"
              if p["intermediate_across_sessions"]["median_cv_pct"] is not None else "- Intermediate precision: need repeats across sessions",
              "", "Put the lifetime (scans to −10 %) into the cost model as tests_per_electrode and into the maintenance schedule (items 58, 214).", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Electrode lifetime, variability and precision")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "electrodes"))
    a = ap.parse_args(argv)
    if a.demo:
        rows, label = demo(), "SYNTHETIC demo"
    elif a.csv:
        rows, label = read(a.csv), os.path.basename(a.csv)
    else:
        ap.error("give the electrode log or --demo")
    res = run(rows, a.out, label)
    print(res.get("stopped") or f"{len(res['lifetime'])} electrodes -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
