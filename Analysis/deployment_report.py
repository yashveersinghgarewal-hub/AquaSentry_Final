#!/usr/bin/env python3
"""
Deployment report for the unattended / soak test (ISEF items 114-115, 182-183, 185).

Input: the readings export of one device - GET /api/data/export?device_code=NODE-01&format=json (the "records" list)
or format=csv, saved to a file - plus the test interval. Reports, with nothing invented:

  * period covered, readings expected vs received, uptime % (share of expected intervals with a reading),
    the longest gap, and every gap longer than two intervals
  * late deliveries: readings whose recorded time is far before the server's receipt (the offline buffer at work)
  * QC: passed / warning / failed tests, and the flag counts
  * outcomes: screen positive / retest / not detected / invalid per day
  * battery: start, end, slope per day, and the projected day it reaches 20 %
  * "false alarms": screen positives that the next reading did not repeat (needs lab confirmation to call them false)

Usage:  python Analysis/deployment_report.py node01_export.json --interval-min 60 --out Analysis/out/deployment
        python Analysis/deployment_report.py --demo --out Analysis/out/deployment_demo     (SYNTHETIC 30 days)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load(path: str) -> List[Dict]:
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("records", data.get("readings", data.get("rows", data))) if isinstance(data, dict) else data
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        t = _dt(r.get("recorded_at"))
        if t is None:
            continue
        out.append({"t": t, "received": _dt(r.get("received_at")) or t, "ug": float(r.get("arsenic_ppb") or 0),
                    "qc": (r.get("qc_status") or "").lower(), "flags": r.get("qc_flags") or "", "outcome": r.get("screening_outcome") or "",
                    "battery": float(r["battery_pct"]) if r.get("battery_pct") not in (None, "") else None,
                    "sim": str(r.get("is_simulated", "")).lower() in ("true", "1")})
    out.sort(key=lambda r: r["t"])
    return [r for r in out if not r["sim"]]


def demo(days: int = 30, interval_min: int = 60) -> List[Dict]:
    rng = np.random.default_rng(12)
    t0 = datetime(2027, 1, 20, 6, tzinfo=timezone.utc)
    rows = []
    n = days * 24 * 60 // interval_min
    battery = 100.0
    for i in range(n):
        t = t0 + timedelta(minutes=i * interval_min)
        if 300 <= i < 330:          # a day and a bit of Wi-Fi outage: readings buffered, delivered late
            received = t0 + timedelta(minutes=331 * interval_min)
        elif 500 <= i < 506:        # six hours of nothing (power loss)
            continue
        else:
            received = t + timedelta(seconds=20)
        battery = max(5.0, battery - 0.09 + (0.6 if 6 <= t.hour <= 16 else 0.0) * 0.2 - 0.02 * rng.random())
        base = 28 + 6 * np.sin(i / 40.0)
        ug = max(0.0, base + rng.normal(0, 4))
        qc = "pass" if rng.random() > 0.04 else "fail"
        if qc == "fail":
            ug = 0.0
        outcome = "invalid" if qc == "fail" else ("screen_positive" if ug >= 24 else "retest" if ug >= 16 else "not_detected")
        rows.append({"t": t, "received": received, "ug": ug, "qc": qc, "flags": "FLAT_SIGNAL" if qc == "fail" else "",
                     "outcome": outcome, "battery": round(battery, 1), "sim": False})
    return rows


def run(rows: List[Dict], interval_min: int, out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res: Dict = {"label": label, "n_readings": len(rows), "interval_min": interval_min}
    if len(rows) < 5:
        res["stopped"] = "Fewer than 5 readings."
        _write(out_dir, res)
        return res
    t0, t1 = rows[0]["t"], rows[-1]["t"]
    span_h = (t1 - t0).total_seconds() / 3600.0
    expected = int(round(span_h * 60 / interval_min)) + 1
    gaps = [(rows[i]["t"], rows[i + 1]["t"], (rows[i + 1]["t"] - rows[i]["t"]).total_seconds() / 60.0) for i in range(len(rows) - 1)]
    long_gaps = [g for g in gaps if g[2] > 2.5 * interval_min]
    missed = sum(int(round(g[2] / interval_min)) - 1 for g in gaps if g[2] > 1.5 * interval_min)
    late = [r for r in rows if (r["received"] - r["t"]).total_seconds() > 3 * interval_min * 60]
    res.update({"period": {"start": t0.isoformat(), "end": t1.isoformat(), "days": round(span_h / 24.0, 2)},
                "expected_readings": expected, "received_readings": len(rows), "missed_intervals": int(missed),
                "uptime_pct": 100.0 * (expected - missed) / expected if expected else None,
                "longest_gap_min": max((g[2] for g in gaps), default=0.0),
                "gaps_over_2_intervals": [{"from": a.isoformat(), "to": b.isoformat(), "minutes": round(m)} for a, b, m in long_gaps],
                "late_deliveries": {"count": len(late), "max_delay_hours": max(((r["received"] - r["t"]).total_seconds() / 3600 for r in late), default=0.0),
                                    "note": "readings that arrived long after their time: the offline buffer delivered them (item 183)"},
                "qc": {"pass": sum(r["qc"] == "pass" for r in rows), "warning": sum(r["qc"] == "warning" for r in rows),
                       "fail": sum(r["qc"] == "fail" for r in rows), "unreported": sum(r["qc"] == "" for r in rows)},
                "outcomes": {k: sum(r["outcome"] == k for r in rows) for k in ("screen_positive", "retest", "not_detected", "invalid")}})
    flags: Dict[str, int] = {}
    for r in rows:
        for f in str(r["flags"]).split(","):
            if f.strip():
                flags[f.strip()] = flags.get(f.strip(), 0) + 1
    res["qc_flag_counts"] = flags
    # unrepeated positives
    unrep = 0
    for i in range(len(rows) - 1):
        if rows[i]["outcome"] == "screen_positive" and rows[i + 1]["qc"] != "fail" and rows[i + 1]["outcome"] == "not_detected":
            unrep += 1
    res["positives_not_repeated_next_reading"] = {"count": unrep, "note": "candidates for 'false alarm'; only a laboratory result can decide"}
    # battery
    bat = [(r["t"], r["battery"]) for r in rows if r["battery"] is not None]
    if len(bat) >= 5:
        xs = np.array([(t - t0).total_seconds() / 86400.0 for t, _ in bat])
        ys = np.array([b for _, b in bat])
        slope, icpt = np.polyfit(xs, ys, 1)
        res["battery"] = {"start_pct": ys[0], "end_pct": ys[-1], "slope_pct_per_day": float(slope),
                          "projected_day_to_20pct": float((20 - icpt) / slope) if slope < 0 else None}
        ax = sp.Axes((0, float(xs.max()) * 1.02), (0, 100), "Battery over the deployment" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                     "Day", "Battery (%)", f"slope {slope:+.2f} %/day")
        ax.hline(20, sp.RED, "4 4", "20 % floor")
        ax.line(xs.tolist(), ys.tolist(), sp.BLUE, 1.4)
        sp.save(os.path.join(out_dir, "battery.svg"), ax.render())
    # readings over time
    xs = [(r["t"] - t0).total_seconds() / 86400.0 for r in rows]
    ys = [r["ug"] for r in rows]
    ax = sp.Axes((0, max(xs) * 1.02), (0, max(max(ys) * 1.1, 30)), "Readings over the deployment" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Day", "Arsenic (µg/L)", f"{len(rows)} readings; uptime {res['uptime_pct']:.1f} %; {res['qc']['fail']} failed tests")
    ax.hline(20, sp.VIOLET, "4 4", "20 µg/L LOD")
    ax.hline(10, sp.AMBER, "4 4", "10 µg/L limit")
    ok = [i for i, r in enumerate(rows) if r["qc"] != "fail"]
    ax.points([xs[i] for i in ok], [ys[i] for i in ok], sp.BLUE, 2.4, 0.7, "passed QC")
    bad = [i for i, r in enumerate(rows) if r["qc"] == "fail"]
    if bad:
        ax.points([xs[i] for i in bad], [0] * len(bad), sp.RED, 3.0, 0.9, "failed test")
    for a, b, _ in long_gaps:
        ax.band((a - t0).total_seconds() / 86400.0, (b - t0).total_seconds() / 86400.0, sp.RED, 0.12)
    sp.save(os.path.join(out_dir, "readings.svg"), ax.render())
    _write(out_dir, res)
    return res


def _write(out_dir, res):
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# Deployment report — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data.**", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        p = res["period"]
        L += [f"- Period: {p['start'][:16]} → {p['end'][:16]} UTC ({p['days']} days); one test every {res['interval_min']} min",
              f"- Readings: **{res['received_readings']} of {res['expected_readings']} expected**; missed intervals {res['missed_intervals']}; "
              f"**uptime {res['uptime_pct']:.1f} %**; longest gap {res['longest_gap_min']:.0f} min",
              f"- Delivered late by the offline buffer: {res['late_deliveries']['count']} readings (max delay {res['late_deliveries']['max_delay_hours']:.1f} h)",
              f"- QC: pass {res['qc']['pass']}, warning {res['qc']['warning']}, fail {res['qc']['fail']}, unreported {res['qc']['unreported']}; flags: "
              + (", ".join(f"{k} {v}" for k, v in res["qc_flag_counts"].items()) or "none"),
              f"- Outcomes: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in res["outcomes"].items()),
              f"- Screen positives not repeated by the next reading: {res['positives_not_repeated_next_reading']['count']} ({res['positives_not_repeated_next_reading']['note']})"]
        if res.get("battery"):
            b = res["battery"]
            L += [f"- Battery: {b['start_pct']:.0f} % → {b['end_pct']:.0f} %, {b['slope_pct_per_day']:+.2f} %/day"
                  + (f"; reaches 20 % around day {b['projected_day_to_20pct']:.0f}" if b.get("projected_day_to_20pct") else "")]
        if res["gaps_over_2_intervals"]:
            L += ["", "## Gaps longer than two intervals", "", "| from | to | minutes |", "|---|---|---|"]
            for g in res["gaps_over_2_intervals"]:
                L += [f"| {g['from'][:16]} | {g['to'][:16]} | {g['minutes']} |"]
        L += ["", "![readings](readings.svg)", ""]
        if res.get("battery"):
            L += ["![battery](battery.svg)", ""]
        L += ["Write the cause of each gap in the logbook (power, Wi-Fi, maintenance); the gaps and the late deliveries together are the "
              "evidence for items 182–183.", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Uptime, QC, outcomes and battery for an unattended deployment")
    ap.add_argument("path", nargs="?", help="GET /api/data/export?device_code=...&format=json saved to a file")
    ap.add_argument("--interval-min", type=int, default=60)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "deployment"))
    a = ap.parse_args(argv)
    if a.demo:
        rows, label = demo(interval_min=a.interval_min), "SYNTHETIC 30-day demo"
    elif a.path:
        rows, label = load(a.path), os.path.basename(a.path)
    else:
        ap.error("give an export file or --demo")
    res = run(rows, a.interval_min, a.out, label)
    print(res.get("stopped") or f"uptime {res['uptime_pct']:.1f} %, {res['qc']['fail']} failed tests, {res['late_deliveries']['count']} late deliveries -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
