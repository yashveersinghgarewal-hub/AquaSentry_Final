#!/usr/bin/env python3
"""
Recreate every poster figure from the raw files in one command (ISEF items 138, 264).

    python Analysis/make_poster_figures.py --paired Data/field/paired.csv [--interference ...] [--qc-runs ...] [--hand-peaks ... --scans ...]
                                           [--standards ...] [--electrodes ...] [--power ...] [--deployment ...]
    python Analysis/make_poster_figures.py --demo        (every script on its labelled SYNTHETIC demo data)

Writes Analysis/out/poster/<figure>/... and an index.md listing what was produced, from which input, with which
script, so any number on the poster can be traced to a file and a command.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(cmd, log):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    log.append((cmd, r.returncode, (r.stdout + r.stderr).strip()[-600:]))
    return r.returncode == 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paired", help="paired CSV from GET /api/data/export/paired")
    ap.add_argument("--interference")
    ap.add_argument("--qc-runs", help="JSON or CSV of check-standard runs")
    ap.add_argument("--hand-peaks")
    ap.add_argument("--scans", default=".")
    ap.add_argument("--standards", help="standards CSV for linearity.py")
    ap.add_argument("--electrodes", help="electrode log for electrode_study.py")
    ap.add_argument("--power", help="power log for power_budget.py")
    ap.add_argument("--deployment", help="readings export for deployment_report.py")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "poster"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    log = []
    steps = []
    if a.demo or a.paired:
        src = ["--demo"] if a.demo else [a.paired]
        steps += [("validation", [PY, os.path.join(HERE, "paired_validation.py"), *src]),
                  ("aquanet_pipeline", [PY, os.path.join(HERE, "aquanet_v2_pipeline.py"), *src]),
                  ("aquanet_v3_field", [PY, os.path.join(HERE, "aquanet_v3_field_eval.py"), *src])]
    if a.demo or a.interference:
        steps.append(("interference", [PY, os.path.join(HERE, "interference.py"), *(["--demo"] if a.demo else [a.interference])]))
    if a.demo or a.qc_runs:
        steps.append(("control_chart", [PY, os.path.join(HERE, "control_chart.py"), *(["--demo"] if a.demo else [a.qc_runs])]))
    if a.demo or a.hand_peaks:
        steps.append(("peak_check", [PY, os.path.join(HERE, "peak_check.py"), *(["--demo"] if a.demo else [a.hand_peaks, "--scans", a.scans])]))
    if a.demo or a.standards:
        steps.append(("linearity", [PY, os.path.join(HERE, "linearity.py"), *(["--demo"] if a.demo else [a.standards])]))
    if a.demo or a.electrodes:
        steps.append(("electrodes", [PY, os.path.join(HERE, "electrode_study.py"), *(["--demo"] if a.demo else [a.electrodes])]))
    if a.demo or a.power:
        steps.append(("power", [PY, os.path.join(HERE, "power_budget.py"), *(["--demo"] if a.demo else [a.power])]))
    if a.demo or a.deployment:
        steps.append(("deployment", [PY, os.path.join(HERE, "deployment_report.py"), *(["--demo"] if a.demo else [a.deployment])]))
    steps.append(("project", [PY, os.path.join(HERE, "project_figures.py"), "all"]))
    ok_all = True
    for name, cmd in steps:
        ok_all &= run(cmd + ["--out", os.path.join(a.out, name)], log)
    lines = [f"# Poster figures — generated {dt.datetime.now().isoformat(timespec='minutes')}", "",
             "> " + ("**SYNTHETIC demo data throughout.**" if a.demo else "Inputs are the files named below."), "",
             "| figure set | command | status |", "|---|---|---|"]
    for (cmd, code, _), (name, _) in zip(log, steps):
        lines.append(f"| `{name}/` | `{' '.join(os.path.relpath(c, os.path.dirname(HERE)) if os.path.isabs(c) else c for c in cmd[1:])}` | {'ok' if code == 0 else 'FAILED'} |")
    lines += ["", "Poster panels (item 232): `validation/scatter.svg`, the confusion tables in `validation/report.md`, `aquanet_pipeline/referral_curve.svg`, "
              "`project/design_history.svg`, `project/gantt.svg`, `project/qr.svg`.", ""]
    for cmd, code, tail in log:
        if code != 0:
            lines += [f"## Failure: {' '.join(cmd)}", "", "```", tail, "```", ""]
    with open(os.path.join(a.out, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"-> {a.out}/index.md ({'all ok' if ok_all else 'some steps failed'})")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
