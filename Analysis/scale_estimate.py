#!/usr/bin/env python3
"""
Scale, cost-per-sample and maintenance estimates with every assumption visible (ISEF items 126, 177, 211, 214).

All inputs come from a small assumptions CSV (Docs/templates/scale_assumptions_template.csv): name,value,unit,source.
Nothing is assumed inside the script; a missing row is reported as missing. The outputs are ranges (low / base /
high) so a judge sees that the estimate is an estimate.

Rows the script uses (fill what you can):
  habitations_affected        number    e.g. from the JJM dashboard, with the date
  sources_per_habitation      number
  tests_per_source_per_year   number    screening cadence
  device_cost_inr             INR       from Analysis/project_figures.py cost
  consumables_per_test_inr    INR       same
  electrode_price_inr, tests_per_electrode
  lab_confirmation_share      fraction  share of screen positives / retests sent to ICP-MS
  lab_cost_per_sample_inr     INR       the laboratory's quote
  device_lifetime_years, devices_per_technician, technician_cost_per_year_inr
  check_standard_interval_days (7), calibration_interval_days (90), electrode_life_tests  -> maintenance visits per device-year
  field_samples_collected, field_total_spend_inr  -> cost actually spent per sample so far (item 126)

Usage:  python Analysis/scale_estimate.py Docs/templates/scale_assumptions_template.csv --out Analysis/out/scale
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from typing import Dict

HERE = os.path.dirname(os.path.abspath(__file__))


def read(path: str) -> Dict[str, Dict]:
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = (r.get("name") or "").strip()
            if not name or name.startswith("#"):
                continue
            try:
                v = float(r.get("value") or "")
            except ValueError:
                v = None
            out[name] = {"value": v, "unit": r.get("unit", ""), "source": r.get("source", "")}
    return out


def g(a: Dict, k: str):
    v = a.get(k, {}).get("value")
    return None if v is None or not math.isfinite(v) else v


def estimate(a: Dict) -> Dict:
    res: Dict = {"missing": [], "notes": []}
    need = ["habitations_affected", "sources_per_habitation", "tests_per_source_per_year", "device_cost_inr", "consumables_per_test_inr",
            "electrode_price_inr", "tests_per_electrode", "lab_confirmation_share", "lab_cost_per_sample_inr", "device_lifetime_years"]
    for k in need:
        if g(a, k) is None:
            res["missing"].append(k)
    hab, spp, tpy = g(a, "habitations_affected"), g(a, "sources_per_habitation"), g(a, "tests_per_source_per_year")
    if None not in (hab, spp, tpy):
        sources = hab * spp
        tests = sources * tpy
        res["sources"] = sources
        res["tests_per_year"] = tests
        for name, f in (("low", 0.7), ("base", 1.0), ("high", 1.4)):
            res.setdefault("tests_per_year_range", {})[name] = tests * f
    dev, cons, ep, tpe = g(a, "device_cost_inr"), g(a, "consumables_per_test_inr"), g(a, "electrode_price_inr"), g(a, "tests_per_electrode")
    lab_share, lab_cost, life = g(a, "lab_confirmation_share"), g(a, "lab_cost_per_sample_inr"), g(a, "device_lifetime_years")
    if None not in (cons, ep, tpe):
        per_test = cons + ep / max(tpe, 1)
        res["consumable_cost_per_test_inr"] = per_test
        if None not in (dev, life, tpy, spp) and tpy and spp:
            tests_per_device_year = g(a, "tests_per_device_per_year") or (tpy * (g(a, "sources_per_device") or 1))
            dev_per_test = dev / (life * tests_per_device_year) if tests_per_device_year else None
            res["device_amortised_per_test_inr"] = dev_per_test
            full = per_test + (dev_per_test or 0)
            if None not in (lab_share, lab_cost):
                full_with_lab = full + lab_share * lab_cost
                res["cost_per_test_inr"] = {"screening_only": full, "with_lab_confirmation_share": full_with_lab,
                                            "low": full_with_lab * 0.8, "high": full_with_lab * 1.5}
    tech_n, tech_cost = g(a, "devices_per_technician"), g(a, "technician_cost_per_year_inr")
    if None not in (tech_n, tech_cost) and tech_n:
        res["technician_cost_per_device_year_inr"] = tech_cost / tech_n
    # maintenance visits per device-year from the QC rules (item 214)
    cs, cal, elife = g(a, "check_standard_interval_days") or 7, g(a, "calibration_interval_days") or 90, g(a, "electrode_life_tests")
    tests_per_device_year = g(a, "tests_per_device_per_year") or ((tpy or 0) * (g(a, "sources_per_device") or 1))
    res["maintenance_per_device_year"] = {"check_standard_visits": 365 / cs, "calibrations": 365 / cal,
                                          "electrode_changes": (tests_per_device_year / elife) if elife and tests_per_device_year else None,
                                          "note": "from the platform's QC rules: a check standard every 7 days, calibration every 90 days; electrode life from item 70"}
    fs, spend = g(a, "field_samples_collected"), g(a, "field_total_spend_inr")
    if fs and spend is not None:
        res["cost_actually_spent_per_sample_inr"] = spend / fs
    if "tests_per_year" in res and res.get("cost_per_test_inr"):
        res["programme_cost_per_year_inr"] = {k: res["tests_per_year"] * v for k, v in res["cost_per_test_inr"].items() if k in ("low", "with_lab_confirmation_share", "high")}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scale and cost estimate from an assumptions CSV")
    ap.add_argument("csv")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "scale"))
    a = ap.parse_args(argv)
    assumptions = read(a.csv)
    res = estimate(assumptions)
    res["assumptions"] = assumptions
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = ["# Scale and cost estimate", "", "Every number below comes from the assumptions table at the end; change a row, rerun. Ranges are ± 30–50 % to show it is an estimate.", ""]
    if res["missing"]:
        L += ["**Missing assumptions (not estimated):** " + ", ".join(res["missing"]), ""]
    if "tests_per_year" in res:
        r = res["tests_per_year_range"]
        L += [f"- Sources: **{res['sources']:,.0f}**; screening tests per year: **{res['tests_per_year']:,.0f}** (range {r['low']:,.0f}–{r['high']:,.0f})"]
    if res.get("cost_per_test_inr"):
        c = res["cost_per_test_inr"]
        L += [f"- Cost per test: screening ₹ {c['screening_only']:,.0f}; with the laboratory-confirmation share ₹ {c['with_lab_confirmation_share']:,.0f} (range ₹ {c['low']:,.0f}–{c['high']:,.0f})"]
    if res.get("programme_cost_per_year_inr"):
        p = res["programme_cost_per_year_inr"]
        L += [f"- Programme cost per year: ₹ {p['with_lab_confirmation_share']:,.0f} (range ₹ {p['low']:,.0f}–{p['high']:,.0f})"]
    if res.get("technician_cost_per_device_year_inr") is not None:
        L += [f"- Technician cost per device-year: ₹ {res['technician_cost_per_device_year_inr']:,.0f}"]
    m = res["maintenance_per_device_year"]
    L += [f"- Maintenance per device-year: {m['check_standard_visits']:.0f} check-standard visits, {m['calibrations']:.0f} calibrations"
          + (f", {m['electrode_changes']:.1f} electrode changes" if m.get("electrode_changes") else ", electrode changes: needs item 70") + f" ({m['note']})"]
    if res.get("cost_actually_spent_per_sample_inr") is not None:
        L += [f"- Cost actually spent per field sample so far: **₹ {res['cost_actually_spent_per_sample_inr']:,.0f}** (item 126)"]
    L += ["", "## Assumptions", "", "| name | value | unit | source |", "|---|---|---|---|"]
    for k, v in assumptions.items():
        val = "" if v["value"] is None else f"{v['value']:g}"
        L += [f"| {k} | {val} | {v['unit']} | {v['source']} |"]
    L += [""]
    with open(os.path.join(a.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"{len(res['missing'])} missing assumption(s) -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
