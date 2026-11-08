#!/usr/bin/env python3
"""
2^k factorial design of the SWASV parameters (ISEF item 86): main effects, interactions and their confidence intervals.

Design: each factor at a low (-1) and high (+1) level, every combination run >= 2 times in random order
(use Analysis/run_order.py for the order). Default factors for the node: deposition potential (mV), deposition
time (s), square-wave frequency (Hz); the response is the net peak current (µA) of a fixed standard.

  python Analysis/doe_factorial.py --plan --factors dep_mv:-1200:-1000 dep_s:30:90 freq_hz:15:50 --replicates 2 --out Analysis/out/doe
      -> writes doe_plan.csv (randomised run list with a 'response' column to fill)
  python Analysis/doe_factorial.py doe_plan_filled.csv --out Analysis/out/doe
      -> effects, 95 % CIs, Pareto chart, which settings maximise the response
  python Analysis/doe_factorial.py --demo --out Analysis/out/doe_demo     (SYNTHETIC response)
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import random
import sys
from typing import Dict, List, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402
from interference import t975  # noqa: E402


def parse_factors(specs: List[str]) -> List[Tuple[str, float, float]]:
    out = []
    for s in specs:
        name, lo, hi = s.split(":")
        out.append((name, float(lo), float(hi)))
    return out


def plan(factors, replicates: int, seed: int) -> List[Dict]:
    runs = []
    for combo in itertools.product((-1, 1), repeat=len(factors)):
        for rep in range(replicates):
            row = {"run": 0, "replicate": rep + 1}
            for (name, lo, hi), lv in zip(factors, combo):
                row[name] = lo if lv < 0 else hi
                row[f"{name}_coded"] = lv
            row["response"] = ""
            runs.append(row)
    random.Random(seed).shuffle(runs)
    for i, r in enumerate(runs, start=1):
        r["run"] = i
    return runs


def analyse(rows: List[Dict], factors: List[str]) -> Dict:
    X = np.array([[float(r[f"{f}_coded"]) for f in factors] for r in rows])
    y = np.array([float(r["response"]) for r in rows])
    names, cols = [], [np.ones(len(y))]
    for k in range(1, len(factors) + 1):
        for combo in itertools.combinations(range(len(factors)), k):
            names.append("×".join(factors[i] for i in combo))
            cols.append(np.prod(X[:, list(combo)], axis=1))
    A = np.vstack(cols).T
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = A @ coef
    df = len(y) - A.shape[1]
    s2 = float(((y - yhat) ** 2).sum() / df) if df > 0 else float("nan")
    se = np.sqrt(s2 / len(y)) if df > 0 else float("nan")        # orthogonal design: identical SE for every coefficient
    t = t975(df) if df > 0 else float("nan")
    effects = {}
    for name, c in zip(names, coef[1:]):
        eff = 2 * float(c)                                        # effect = change from low to high level
        effects[name] = {"effect": eff, "ci95": [eff - 2 * t * se, eff + 2 * t * se] if df > 0 else None,
                         "significant": bool(abs(eff) > 2 * t * se) if df > 0 else None}
    best = max(((tuple(r[f"{f}_coded"] for f in factors), float(r["response"])) for r in rows), key=lambda kv: kv[1])
    return {"n_runs": len(y), "grand_mean": float(coef[0]), "residual_sd": float(np.sqrt(s2)) if df > 0 else None, "df_error": df,
            "effects": effects, "best_observed_setting": {f: lv for f, lv in zip(factors, best[0])}, "best_observed_response": best[1]}


def demo() -> Tuple[List[Dict], List[str]]:
    factors = [("dep_mv", -1200, -1000), ("dep_s", 30, 90), ("freq_hz", 15, 50)]
    rows = plan(factors, 2, 3)
    rng = np.random.default_rng(3)
    for r in rows:
        resp = 0.05 + 0.012 * r["dep_s_coded"] - 0.004 * r["dep_mv_coded"] + 0.006 * r["freq_hz_coded"] + 0.004 * r["dep_s_coded"] * r["freq_hz_coded"]
        r["response"] = round(float(resp + rng.normal(0, 0.003)), 5)
    return rows, [f[0] for f in factors]


def run(rows: List[Dict], factors: List[str], out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    rows = [r for r in rows if str(r.get("response", "")).strip() != ""]
    res: Dict = {"label": label, "factors": factors}
    if len(rows) < 2 ** len(factors) + 1:
        res["stopped"] = f"Need every combination run and at least one replicate ({2 ** len(factors) + 1}+ rows); have {len(rows)}."
    else:
        res.update(analyse(rows, factors))
        eff = sorted(res["effects"].items(), key=lambda kv: -abs(kv[1]["effect"]))
        top = max(abs(v["effect"]) for _, v in eff) * 1.25 or 1
        ax = sp.Axes((-top, top), (0, len(eff) + 1), "Factorial effects on peak current" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                     "Effect on response (high − low)", "", f"n = {res['n_runs']} runs; bars = effects, whiskers = 95 % CI")
        ax.vline(0, sp.MUTED, None)
        for i, (name, v) in enumerate(eff):
            yy = len(eff) - i
            ax.line([0, v["effect"]], [yy, yy], sp.BLUE if v["significant"] else sp.MUTED, 10)
            if v["ci95"]:
                ax.line([v["ci95"][0], v["ci95"][1]], [yy, yy], sp.INK, 1.2)
            ax.text(-top * 0.98, yy + 0.25, name, sp.INK, 11)
        sp.save(os.path.join(out_dir, "effects.svg"), ax.render())
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# SWASV factorial design — {label}", ""]
    if "SYNTHETIC" in label:
        L += ["> **SYNTHETIC demonstration response.**", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        L += [f"- Runs: {res['n_runs']}; grand mean {res['grand_mean']:.4f} µA; residual SD {res['residual_sd']:.4f} µA ({res['df_error']} df)", "",
              "| term | effect (µA) | 95 % CI | significant |", "|---|---|---|---|"]
        for name, v in sorted(res["effects"].items(), key=lambda kv: -abs(kv[1]["effect"])):
            L += [f"| {name} | {v['effect']:+.4f} | [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}] | {'yes' if v['significant'] else 'no'} |"]
        L += ["", f"Best observed setting: {res['best_observed_setting']} → {res['best_observed_response']:.4f} µA", "",
              "![effects](effects.svg)", "",
              "A longer deposition usually raises the peak but also the copper and background; confirm the chosen setting with the "
              "interference study before changing the firmware defaults (VOLT_DEP_MV, VOLT_DEP_TIME_MS).", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="2^k factorial plan and analysis for SWASV parameters")
    ap.add_argument("csv", nargs="?", help="filled doe_plan.csv")
    ap.add_argument("--plan", action="store_true", help="write a randomised plan to fill in")
    ap.add_argument("--factors", nargs="*", default=["dep_mv:-1200:-1000", "dep_s:30:90", "freq_hz:15:50"], help="name:low:high")
    ap.add_argument("--replicates", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "doe"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    if a.plan:
        factors = parse_factors(a.factors)
        rows = plan(factors, a.replicates, a.seed)
        path = os.path.join(a.out, "doe_plan.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} runs -> {path} (fill the 'response' column, then rerun with the file)")
        return 0
    if a.demo:
        rows, factors = demo()
        label = "SYNTHETIC demo"
    elif a.csv:
        with open(a.csv, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        factors = [k[:-6] for k in rows[0].keys() if k.endswith("_coded")]
        label = os.path.basename(a.csv)
    else:
        ap.error("give a filled plan, --plan or --demo")
    res = run(rows, factors, a.out, label)
    print(res.get("stopped") or "; ".join(f"{k} {v['effect']:+.4f}{'*' if v['significant'] else ''}" for k, v in res["effects"].items()))
    print(f"-> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
