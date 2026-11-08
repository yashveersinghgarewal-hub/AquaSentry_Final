#!/usr/bin/env python3
"""
Shewhart control chart for the daily check standard (ISEF items 90, 99).

Input: the platform's QC runs (GET /api/qc/runs?run_type=check_standard&limit=500 saved as JSON, or the same as
CSV with columns recorded_at, measured_ug_l, expected_ug_l, device_code), or --demo.

Centre line and limits come from the first `--baseline` passing runs (default 10): mean ± 2 SD (warning) and
± 3 SD (action). Western Electric rules flag: one point beyond 3 SD, two of three beyond 2 SD on the same side,
eight in a row on one side of the centre. The 80-120 % recovery gate the platform applies per day is drawn too,
so the chart shows drift before it becomes a failed day (item 90).

Usage:  python Analysis/control_chart.py qc_runs.json --out Analysis/out/control_chart
        python Analysis/control_chart.py --demo --out Analysis/out/control_chart_demo
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402


def load(path: str) -> List[Dict]:
    rows = []
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data = data.get("rows", data) if isinstance(data, dict) else data
        for r in data:
            if r.get("run_type", "check_standard") != "check_standard":
                continue
            rows.append({"t": r["recorded_at"], "measured": float(r["measured_ug_l"]), "expected": float(r.get("expected_ug_l") or 10.0),
                         "device": r.get("device_code", "")})
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({"t": r["recorded_at"], "measured": float(r["measured_ug_l"]),
                                 "expected": float(r.get("expected_ug_l") or 10.0), "device": r.get("device_code", "")})
                except (KeyError, ValueError):
                    continue
    rows.sort(key=lambda r: r["t"])
    return rows


def demo() -> List[Dict]:
    rng = np.random.default_rng(9)
    t0 = datetime(2026, 12, 1, 8, tzinfo=timezone.utc)
    rows = []
    for i in range(40):
        drift = 0.0 if i < 28 else -0.12 * (i - 27)         # electrode starts to fade after four weeks
        rows.append({"t": (t0 + timedelta(days=i)).isoformat(), "measured": 10.0 + drift + rng.normal(0, 0.45),
                     "expected": 10.0, "device": "DEMO-01"})
    return rows


def western_electric(z: np.ndarray) -> List[Dict]:
    flags = []
    for i in range(len(z)):
        if abs(z[i]) > 3:
            flags.append({"index": i, "rule": "1 point beyond 3 SD"})
        if i >= 2:
            w = z[i - 2:i + 1]
            if (w > 2).sum() >= 2 or (w < -2).sum() >= 2:
                flags.append({"index": i, "rule": "2 of 3 beyond 2 SD (same side)"})
        if i >= 7:
            w = z[i - 7:i + 1]
            if (w > 0).all() or (w < 0).all():
                flags.append({"index": i, "rule": "8 in a row on one side"})
    return flags


def run(rows: List[Dict], out_dir: str, label: str, baseline: int = 10) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res: Dict = {"label": label, "n": len(rows), "baseline_runs": baseline}
    if len(rows) < max(5, baseline):
        res["stopped"] = f"Need at least {max(5, baseline)} check-standard runs; have {len(rows)}."
        _write(out_dir, res)
        return res
    rec = np.array([r["measured"] / r["expected"] * 100.0 for r in rows])
    base = rec[:baseline]
    mu, sd = float(base.mean()), float(base.std(ddof=1))
    sd = max(sd, 0.5)       # a perfectly flat baseline would make every later point an alarm
    z = (rec - mu) / sd
    res.update({"centre_pct": mu, "sd_pct": sd, "warning_limits_pct": [mu - 2 * sd, mu + 2 * sd],
                "action_limits_pct": [mu - 3 * sd, mu + 3 * sd], "flags": western_electric(z),
                "days_outside_80_120": int(((rec < 80) | (rec > 120)).sum())})
    res["first_flag"] = res["flags"][0] if res["flags"] else None
    xs = list(range(1, len(rows) + 1))
    lo = min(75.0, float(rec.min()) - 3)
    hi = max(125.0, float(rec.max()) + 3)
    ax = sp.Axes((0.5, len(rows) + 0.5), (lo, hi), "Daily 10 µg/L check standard — control chart" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Run (chronological)", "Recovery of the check standard (%)",
                 f"centre {mu:.1f} %, SD {sd:.1f} % from the first {baseline} runs; {len(res['flags'])} rule flag(s)")
    ax.hline(mu, sp.INK, None, "centre")
    ax.hline(mu + 2 * sd, sp.AMBER, "6 4", "± 2 SD warning")
    ax.hline(mu - 2 * sd, sp.AMBER, "6 4")
    ax.hline(mu + 3 * sd, sp.RED, "3 3", "± 3 SD action")
    ax.hline(mu - 3 * sd, sp.RED, "3 3")
    ax.hline(80, sp.VIOLET, "2 4", "80-120 % day gate")
    ax.hline(120, sp.VIOLET, "2 4")
    ax.line(xs, rec.tolist(), sp.BLUE, 1.4)
    ax.points(xs, rec.tolist(), sp.BLUE, 3.4)
    flagged = sorted({f["index"] for f in res["flags"]})
    if flagged:
        ax.points([xs[i] for i in flagged], [rec[i] for i in flagged], sp.RED, 5.0, 0.9, "rule flag")
    sp.save(os.path.join(out_dir, "control_chart.svg"), ax.render())
    _write(out_dir, res)
    return res


def _write(out_dir: str, res: Dict) -> None:
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# Check-standard control chart — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data.**", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        L += [f"- Runs: {res['n']}; centre {res['centre_pct']:.1f} %, SD {res['sd_pct']:.1f} % (first {res['baseline_runs']} runs)",
              f"- Warning limits {res['warning_limits_pct'][0]:.1f}–{res['warning_limits_pct'][1]:.1f} %; action limits "
              f"{res['action_limits_pct'][0]:.1f}–{res['action_limits_pct'][1]:.1f} %; days outside the 80–120 % gate: {res['days_outside_80_120']}",
              f"- Western Electric flags: {len(res['flags'])}" + (f"; first at run {res['first_flag']['index'] + 1} ({res['first_flag']['rule']})" if res["first_flag"] else ""),
              "", "![chart](control_chart.svg)", "",
              "A flag means the electrode or the standard changed before the day gate would have caught it: recalibrate, replace the electrode or "
              "remake the standard, and write what was found in the logbook.", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Shewhart chart of the daily check standard")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--baseline", type=int, default=10)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "control_chart"))
    a = ap.parse_args(argv)
    if a.demo:
        rows, label = demo(), "SYNTHETIC demo"
    elif a.path:
        rows, label = load(a.path), os.path.basename(a.path)
    else:
        ap.error("give the QC runs file or --demo")
    res = run(rows, a.out, label, a.baseline)
    print(res.get("stopped") or f"{res['n']} runs, {len(res['flags'])} flag(s) -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
