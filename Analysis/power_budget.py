#!/usr/bin/env python3
"""
Power budget, battery life and solar sizing from MEASURED currents (ISEF items 165, 171, 190).

Input CSV (Data/field/power_log_template.csv), one row per operating mode measured with a USB power meter or a
shunt:   mode, current_ma, seconds_per_cycle[, voltage_v, note]
e.g.     deep_sleep,0.9,3240 / wake_wifi,120,25 / scan,85,300 / pump,210,20 / upload,160,15

The script sums charge per cycle, scales to a day for the configured cycle interval, and gives battery life for a
stated capacity (with a usable fraction) and the solar panel needed for the local insolation (peak-sun hours),
charger efficiency and days of autonomy you want. Every number traces back to a measured current; nothing here is
a datasheet guess unless you typed it in.

Usage:  python Analysis/power_budget.py Data/field/power_log.csv --cycle-s 3600 --battery-mah 3000 --sun-hours 4.5 --out Analysis/out/power
        python Analysis/power_budget.py --demo --out Analysis/out/power_demo        (SYNTHETIC currents)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402


def read(path: str) -> List[Dict]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"mode": r["mode"].strip(), "ma": float(r["current_ma"]), "s": float(r["seconds_per_cycle"]),
                             "v": float(r.get("voltage_v") or 3.7)})
            except (KeyError, ValueError):
                continue
    return rows


def demo() -> List[Dict]:
    return [{"mode": "deep_sleep", "ma": 0.9, "s": 3240, "v": 3.7}, {"mode": "wake_wifi", "ma": 120, "s": 25, "v": 3.7},
            {"mode": "scan", "ma": 85, "s": 300, "v": 3.7}, {"mode": "pump", "ma": 210, "s": 20, "v": 3.7},
            {"mode": "upload", "ma": 160, "s": 15, "v": 3.7}]


def budget(rows: List[Dict], cycle_s: float, battery_mah: float, usable: float, sun_hours: float, charger_eff: float,
           autonomy_days: float, panel_v: float = 5.0) -> Dict:
    per_cycle_mah = sum(r["ma"] * r["s"] / 3600.0 for r in rows)
    measured_s = sum(r["s"] for r in rows)
    sleep = next((r for r in rows if "sleep" in r["mode"]), None)
    if measured_s < cycle_s and sleep:
        per_cycle_mah += sleep["ma"] * (cycle_s - measured_s) / 3600.0   # the rest of the cycle is sleep
    cycles_per_day = 86400.0 / cycle_s
    mah_day = per_cycle_mah * cycles_per_day
    avg_ma = mah_day / 24.0
    wh_day = sum(r["ma"] * r["v"] * r["s"] / 3600.0 for r in rows) / 1000.0 * cycles_per_day
    life_days = battery_mah * usable / mah_day if mah_day > 0 else float("inf")
    # solar: panel must deliver a day's energy (plus charger losses) in the available peak-sun hours
    panel_w = wh_day / charger_eff / sun_hours if sun_hours > 0 else float("nan")
    reserve_mah = mah_day * autonomy_days / usable
    shares = {r["mode"]: r["ma"] * r["s"] / 3600.0 * cycles_per_day / mah_day for r in rows} if mah_day > 0 else {}
    return {"per_cycle_mah": per_cycle_mah, "cycles_per_day": cycles_per_day, "mah_per_day": mah_day, "average_ma": avg_ma,
            "wh_per_day": wh_day, "battery_life_days": life_days, "battery_mah": battery_mah, "usable_fraction": usable,
            "solar_panel_w_min": panel_w, "solar_panel_w_recommended": panel_w * 1.5 if panel_w == panel_w else None,
            "battery_for_autonomy_mah": reserve_mah, "autonomy_days": autonomy_days, "sun_hours": sun_hours, "charger_efficiency": charger_eff,
            "share_by_mode": shares}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Power budget from measured currents")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--cycle-s", type=float, default=3600.0, help="seconds between tests (SAMPLE_INTERVAL_MS / 1000)")
    ap.add_argument("--battery-mah", type=float, default=3000.0)
    ap.add_argument("--usable", type=float, default=0.8, help="usable fraction of the cell (depth of discharge)")
    ap.add_argument("--sun-hours", type=float, default=4.5, help="peak-sun hours per day at the site in the worst month (NREL/NASA POWER)")
    ap.add_argument("--charger-eff", type=float, default=0.75)
    ap.add_argument("--autonomy-days", type=float, default=3.0, help="days of no sun the battery must bridge")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "power"))
    a = ap.parse_args(argv)
    rows, label = (demo(), "SYNTHETIC demo") if a.demo else (read(a.csv), os.path.basename(a.csv)) if a.csv else (None, None)
    if rows is None:
        ap.error("give a power log CSV or --demo")
    os.makedirs(a.out, exist_ok=True)
    b = budget(rows, a.cycle_s, a.battery_mah, a.usable, a.sun_hours, a.charger_eff, a.autonomy_days)
    b["label"] = label
    b["modes"] = rows
    with open(os.path.join(a.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(b, f, indent=2, default=float)
    # figure: share by mode
    modes = list(b["share_by_mode"])
    ax = sp.Axes((0, 1), (0, len(modes) + 1), "Where the charge goes (per day)" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Share of daily charge", "", f"{b['mah_per_day']:.0f} mAh/day at one test every {a.cycle_s / 60:.0f} min; battery life {b['battery_life_days']:.1f} days on {a.battery_mah:.0f} mAh")
    for i, m in enumerate(modes):
        yy = len(modes) - i
        ax.line([0, b["share_by_mode"][m]], [yy, yy], sp.BLUE, 12)
        ax.text(0.01, yy + 0.3, f"{m}: {100 * b['share_by_mode'][m]:.0f} %", sp.INK, 11)
    sp.save(os.path.join(a.out, "power_share.svg"), ax.render())
    L = [f"# Power budget — {label}", ""]
    if "SYNTHETIC" in label:
        L += ["> **SYNTHETIC currents.** Replace with a power-meter log (Data/field/power_log_template.csv).", ""]
    L += ["| mode | current mA | s per cycle | mAh per cycle |", "|---|---|---|---|"]
    for r in rows:
        L += [f"| {r['mode']} | {r['ma']:g} | {r['s']:g} | {r['ma'] * r['s'] / 3600:.2f} |"]
    L += ["", f"- One test every {a.cycle_s / 60:.0f} min → **{b['mah_per_day']:.0f} mAh/day** ({b['average_ma']:.1f} mA average, {b['wh_per_day']:.2f} Wh/day)",
          f"- Battery {a.battery_mah:.0f} mAh at {100 * a.usable:.0f} % usable → **{b['battery_life_days']:.1f} days** without sun",
          f"- Solar: {a.sun_hours:g} peak-sun hours, charger {100 * a.charger_eff:.0f} % → minimum **{b['solar_panel_w_min']:.1f} W** panel, recommended {b['solar_panel_w_recommended']:.1f} W (× 1.5 for dust and tilt)",
          f"- Battery for {a.autonomy_days:g} days of autonomy: **{b['battery_for_autonomy_mah']:.0f} mAh**", "",
          "![share](power_share.svg)", "",
          "Deep-sleep current dominates when the interval is long: measure it with the pump driver and sensors actually fitted (item 190). "
          "Put the measured figures and the date in `Docs/CLAIMS_REGISTER.md` S4.", ""]
    with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"{b['mah_per_day']:.0f} mAh/day, {b['battery_life_days']:.1f} days battery, {b['solar_panel_w_min']:.1f} W panel -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
