#!/usr/bin/env python3
"""
Blinded, randomised run sheets (ISEF items 95, 96, 109).

Someone other than the operator runs this script once per measurement day. It produces:

  run_sheet_<day>.csv   - what the OPERATOR gets: run order, coded sample IDs, which runs are the opening and
                          closing 10 µg/L check standards and the blanks, columns to write results into
  key_<day>.csv         - what the SUPERVISOR keeps sealed until the lab results are in: code -> real sample /
                          standard concentration

Standards and samples are interleaved at random (seeded, so the sheet is reproducible from the seed written on
it); the opening and closing check standards are fixed first and last because that is their purpose (item 90).

Usage:
  python Analysis/run_order.py --samples S-01 S-02 S-03 --standards 0 10 50 100 --replicates 2 --day 2026-12-03 --out Analysis/out/runs
  python Analysis/run_order.py --samples-file Data/field/today_samples.txt ...
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import random
import secrets
import sys
from typing import List

HERE = os.path.dirname(os.path.abspath(__file__))


def build(samples: List[str], standards: List[float], replicates: int, blanks: int, seed: int, day: str):
    rng = random.Random(seed)
    items = []
    for s in samples:
        for r in range(replicates):
            items.append(("sample", s, None, r + 1))
    for c in standards:
        for r in range(replicates):
            items.append(("standard", f"STD-{c:g}", c, r + 1))
    for b in range(blanks):
        items.append(("blank", "BLANK", 0.0, b + 1))
    rng.shuffle(items)
    # coded IDs that reveal nothing about order of preparation
    codes = [f"{day.replace('-', '')[2:]}-{rng.randrange(100, 999)}{chr(65 + i % 26)}" for i in range(len(items))]
    seen = set()
    for i, c in enumerate(codes):
        while c in seen:
            c = f"{c}{rng.randrange(0, 9)}"
        codes[i] = c
        seen.add(c)
    sheet = [{"run": 1, "code": "CHECK-OPEN", "kind": "check standard 10 µg/L (opening)", "result_ug_l": "", "qc_flags": "", "operator_note": ""}]
    key = [{"run": 1, "code": "CHECK-OPEN", "kind": "check_standard", "true_ug_l": 10.0, "sample": "", "replicate": ""}]
    for i, ((kind, name, conc, rep), code) in enumerate(zip(items, codes), start=2):
        sheet.append({"run": i, "code": code, "kind": "sample" if kind == "sample" else ("blank" if kind == "blank" else "standard"),
                      "result_ug_l": "", "qc_flags": "", "operator_note": ""})
        key.append({"run": i, "code": code, "kind": kind, "true_ug_l": "" if conc is None else conc, "sample": name if kind == "sample" else "",
                    "replicate": rep})
    n = len(sheet) + 1
    sheet.append({"run": n, "code": "CHECK-CLOSE", "kind": "check standard 10 µg/L (closing)", "result_ug_l": "", "qc_flags": "", "operator_note": ""})
    key.append({"run": n, "code": "CHECK-CLOSE", "kind": "check_standard", "true_ug_l": 10.0, "sample": "", "replicate": ""})
    return sheet, key


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Blinded, randomised run sheet + sealed key")
    ap.add_argument("--samples", nargs="*", default=[])
    ap.add_argument("--samples-file", help="one sample code per line")
    ap.add_argument("--standards", nargs="*", type=float, default=[0, 10, 20, 50, 100])
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--blanks", type=int, default=2)
    ap.add_argument("--day", default=dt.date.today().isoformat())
    ap.add_argument("--seed", type=int, default=None, help="omit for a fresh random seed (printed on the sheet)")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "runs"))
    a = ap.parse_args(argv)
    samples = list(a.samples)
    if a.samples_file:
        with open(a.samples_file, encoding="utf-8") as f:
            samples += [ln.strip() for ln in f if ln.strip()]
    if not samples and not a.standards:
        ap.error("give --samples and/or --standards")
    seed = a.seed if a.seed is not None else secrets.randbelow(10 ** 8)
    sheet, key = build(samples, a.standards, a.replicates, a.blanks, seed, a.day)
    os.makedirs(a.out, exist_ok=True)
    sp_ = os.path.join(a.out, f"run_sheet_{a.day}.csv")
    kp = os.path.join(a.out, f"key_{a.day}.csv")
    with open(sp_, "w", newline="", encoding="utf-8") as f:
        f.write(f"# AquaSentry run sheet {a.day} - seed {seed} - operator: ______  supervisor: ______  electrode lot: ______  calibration ID: ______\n")
        w = csv.DictWriter(f, fieldnames=list(sheet[0].keys()))
        w.writeheader()
        w.writerows(sheet)
    with open(kp, "w", newline="", encoding="utf-8") as f:
        f.write(f"# SEALED KEY {a.day} - seed {seed} - open only after the operator's results are recorded\n")
        w = csv.DictWriter(f, fieldnames=list(key[0].keys()))
        w.writeheader()
        w.writerows(key)
    print(f"{len(sheet)} runs ({len(samples)} samples × {a.replicates}, {len(a.standards)} standards × {a.replicates}, {a.blanks} blanks, 2 check standards)")
    print(f"operator sheet: {sp_}\nsealed key:     {kp}\nseed: {seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
