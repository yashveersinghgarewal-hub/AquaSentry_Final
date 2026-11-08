#!/usr/bin/env python3
"""
Peak-finding algorithm against hand-measured peaks (ISEF item 76).

A person measures the arsenic peak on ≥ 50 printed or plotted scans by hand (ruler on the baseline, read the peak
height and potential) and writes them to a CSV:

    scan_file, hand_peak_ua, hand_potential_mv[, operator]

Each scan file (potential_mV,current_uA columns, as the bridge and the dashboard read them) is run through the
platform's pipeline (app/signal_processing.py, the same code the server and the browser use) and compared: bias,
limits of agreement, Deming slope, and the scans where the two disagree most. If the algorithm disagrees with a
careful hand measurement by more than the method's own noise, the algorithm (or the hand method) needs work before
any number from it goes on a poster.

Usage:  python Analysis/peak_check.py Data/field/hand_peaks.csv --scans Data/field/scans --out Analysis/out/peak_check
        python Analysis/peak_check.py --demo --out Analysis/out/peak_check_demo    (SYNTHETIC scans + "hand" values with 3 % error)
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
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "AquaSentry_Platform"))
import svg_plots as sp  # noqa: E402
from app.signal_processing import generate_synthetic_asv_trace, process_voltammetry_trace  # noqa: E402
from bridge.serial_bridge import parse_scan_csv  # noqa: E402


def deming(x, y, lam=1.0):
    mx, my = x.mean(), y.mean()
    sxx, syy, sxy = ((x - mx) ** 2).mean(), ((y - my) ** 2).mean(), ((x - mx) * (y - my)).mean()
    if sxy == 0:
        return 0.0, float(my)
    b = (syy - lam * sxx + math.sqrt((syy - lam * sxx) ** 2 + 4 * lam * sxy ** 2)) / (2 * sxy)
    return float(b), float(my - b * mx)


def run_rows(rows: List[Dict], out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res: Dict = {"label": label, "n": len(rows)}
    if len(rows) < 5:
        res["stopped"] = "Fewer than 5 hand-measured scans; measure at least 50 (item 76)."
        _write(out_dir, res)
        return res
    algo_h, hand_h, algo_e, hand_e, rejected, names = [], [], [], [], 0, []
    for r in rows:
        out = process_voltammetry_trace(r["P"], r["C"], strict=False)
        if out.qc_status == "REJECTED" or out.peak is None:
            rejected += 1
            continue
        algo_h.append(out.peak.net_peak_height_ua)
        hand_h.append(r["hand_ua"])
        algo_e.append(out.peak.peak_potential_mv)
        hand_e.append(r["hand_mv"])
        names.append(r["name"])
    a, h = np.array(algo_h), np.array(hand_h)
    d = a - h
    sl, ic = deming(h, a)
    res.update({"compared": int(len(a)), "rejected_by_algorithm": rejected,
                "height": {"bias_ua": float(d.mean()), "sd_ua": float(d.std(ddof=1)) if len(d) > 1 else None,
                           "loa_ua": [float(d.mean() - 1.96 * d.std(ddof=1)), float(d.mean() + 1.96 * d.std(ddof=1))] if len(d) > 1 else None,
                           "relative_bias_pct": float((d / np.where(h == 0, np.nan, h) * 100).mean()) if len(h) else None,
                           "deming_slope": sl, "deming_intercept_ua": ic, "pearson_r": float(np.corrcoef(h, a)[0, 1]) if len(h) > 2 else None},
                "potential": {"bias_mv": float((np.array(algo_e) - np.array(hand_e)).mean()),
                              "max_abs_mv": float(np.abs(np.array(algo_e) - np.array(hand_e)).max())}})
    worst = np.argsort(-np.abs(d))[:10]
    res["largest_disagreements"] = [{"scan": names[i], "hand_ua": float(h[i]), "algorithm_ua": float(a[i]), "diff_ua": float(d[i])} for i in worst]
    top = float(max(a.max(), h.max()) * 1.08)
    ax = sp.Axes((0, top), (0, top), "Algorithm vs hand-measured peak height" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Hand-measured net peak (µA)", "Algorithm net peak (µA)", f"n = {len(a)}; Deming slope {sl:.3f}, intercept {ic:.4f} µA")
    ax.line([0, top], [0, top], sp.MUTED, 1.2, "5 4", "1 : 1")
    ax.line([0, top], [ic, ic + sl * top], sp.RED, 1.6, None, "Deming fit")
    ax.points(h, a, sp.BLUE, label="scans")
    sp.save(os.path.join(out_dir, "peak_scatter.svg"), ax.render())
    _write(out_dir, res)
    return res


def _write(out_dir, res):
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# Peak-finding check — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data** (the 'hand' values are the generator's truth with 3 % noise).", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        hgt, pot = res["height"], res["potential"]
        L += [f"- Scans compared: {res['compared']} (algorithm rejected {res['rejected_by_algorithm']} as malformed)",
              f"- Peak height: bias {hgt['bias_ua']:+.4f} µA ({hgt['relative_bias_pct']:+.1f} %), limits of agreement "
              f"{hgt['loa_ua'][0]:+.4f} to {hgt['loa_ua'][1]:+.4f} µA; Deming slope {hgt['deming_slope']:.3f}; r = {hgt['pearson_r']:.3f}",
              f"- Peak potential: bias {pot['bias_mv']:+.1f} mV, largest difference {pot['max_abs_mv']:.1f} mV", "",
              "![scatter](peak_scatter.svg)", "", "## Largest disagreements", "", "| scan | hand µA | algorithm µA | difference |", "|---|---|---|---|"]
        for w in res["largest_disagreements"]:
            L += [f"| {w['scan']} | {w['hand_ua']:.4f} | {w['algorithm_ua']:.4f} | {w['diff_ua']:+.4f} |"]
        L += ["", "Look at each of these scans. A consistent sign means a baseline-placement difference between the person and the algorithm; "
              "scattered signs at low peaks mean the noise floor. Write the finding in the logbook (item 140).", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare the pipeline's peaks with hand-measured peaks")
    ap.add_argument("csv", nargs="?", help="scan_file, hand_peak_ua, hand_potential_mv")
    ap.add_argument("--scans", default=".", help="folder holding the scan files named in the CSV")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "peak_check"))
    a = ap.parse_args(argv)
    rows = []
    if a.demo:
        rng = np.random.default_rng(2)
        for i in range(60):
            ppb = float(np.exp(rng.uniform(np.log(20), np.log(400))))
            P, C = generate_synthetic_asv_trace(ppb, seed=100 + i)
            true_h = 0.0096 + 0.8563 * ppb / 1000.0      # the generator's peak = calibration line
            rows.append({"name": f"demo_{i:02d}", "P": P, "C": C, "hand_ua": true_h * (1 + rng.normal(0, 0.03)), "hand_mv": -800 + rng.normal(0, 4)})
        label = "SYNTHETIC demo"
    elif a.csv:
        with open(a.csv, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                path = os.path.join(a.scans, r["scan_file"])
                try:
                    with open(path, encoding="utf-8-sig", errors="ignore") as sf:
                        P, C = parse_scan_csv(sf.read())
                    rows.append({"name": r["scan_file"], "P": P, "C": C, "hand_ua": float(r["hand_peak_ua"]), "hand_mv": float(r["hand_potential_mv"])})
                except (OSError, KeyError, ValueError) as e:
                    print(f"skipping {r.get('scan_file')}: {e}")
        label = os.path.basename(a.csv)
    else:
        ap.error("give the hand-measured CSV or --demo")
    res = run_rows(rows, a.out, label)
    print(res.get("stopped") or f"{res['compared']} scans compared; height bias {res['height']['bias_ua']:+.4f} µA -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
