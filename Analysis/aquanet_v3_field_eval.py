#!/usr/bin/env python3
"""
AquaNet-V3 against real data (ISEF items 148-155, 158-161).

The deployed network was trained on simulated readings. This script evaluates it, unchanged, on the paired dataset
(node reading + laboratory value) and answers the questions a judge will ask:

  148/150  confusion matrix of the network's class against the class the LABORATORY value implies (held-out by
           construction: the network never saw real data), and its accuracy
  149      baselines on the same rows: the threshold rule on the node value alone, and a logistic regression
           (numpy, leave-one-site-out) on the same five inputs
  152      ablation: each input replaced by "not measured" (its training mean), effect on accuracy
  153      reliability diagram: stated confidence vs observed accuracy, with expected calibration error
  154      the hard safety rule: the network's vote can never turn a reading above the limit into "Safe"
           (also proved by tests/test_aquanet_v3.py; repeated here on the real rows)
  155      parameter count and memory from the weight file (inference time comes from the firmware self-test)
  160      the rows the network gets wrong, listed
  161      model version string recorded in the output

Usage:  python Analysis/aquanet_v3_field_eval.py paired.csv --out Analysis/out/aquanet_v3_field
        python Analysis/aquanet_v3_field_eval.py --demo --out Analysis/out/aquanet_v3_field_demo   (SYNTHETIC rows)

The class implied by the laboratory value uses the same tiers as the platform's rules (app/standards.py):
Safe < 10, Caution 10-20, Unsafe 20-150, Hazardous ≥ 150 µg/L. "Safe" here means below the legal limit by a
laboratory method; the node itself never says safe below its 20 µg/L detection limit.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "AquaSentry_Platform"))
import svg_plots as sp  # noqa: E402
from app import aquanet_v3 as net  # noqa: E402

CLASSES = net.CLASSES
TIERS = [(10.0, "Safe"), (20.0, "Caution"), (150.0, "Unsafe"), (float("inf"), "Hazardous")]
INPUTS = ["arsenic", "ph", "conductivity", "turbidity", "temperature"]


def tier(ug_l: float) -> str:
    for edge, name in TIERS:
        if ug_l < edge:
            return name
    return "Hazardous"


def _f(v) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load_rows(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            node = _f(r.get("device_ug_l"))
            lab = _f(r.get("lab_ug_l"))
            if node is None or lab is None or (r.get("qc_status") or "").lower() == "fail":
                continue
            if (r.get("lab_qualifier") or "").strip() == "<":
                lab = 0.0       # censored below the reporting limit: certainly below 10 µg/L
            rows.append({"node": node, "lab": lab, "ph": _f(r.get("ph")), "ec": _f(r.get("conductivity_us_cm")),
                         "turb": _f(r.get("turbidity_ntu")), "temp": _f(r.get("temperature_c")),
                         "site": r.get("site_name") or r.get("village") or r.get("device_code") or "",
                         "sample": r.get("sample_code") or ""})
    return rows


def demo_rows(n: int = 160, seed: int = 3) -> List[Dict]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        truth = float(np.exp(rng.uniform(np.log(1.0), np.log(400.0))))
        node = max(0.0, 1.5 + 0.92 * truth + rng.normal(0, 4.0) + truth * rng.normal(0, 0.12))
        out.append({"node": node, "lab": truth * (1 + rng.normal(0, 0.05)), "ph": rng.normal(7.2, 0.4),
                    "ec": float(rng.uniform(200, 1500)), "turb": float(abs(rng.normal(3, 2))), "temp": rng.normal(27, 3),
                    "site": f"Site-{i % 6 + 1}", "sample": f"DEMO-{i + 1:03d}"})
    return out


# ---------------------------------------------------------------- metrics
def confusion(pred: List[str], truth: List[str]) -> Dict:
    m = {t: {p: 0 for p in CLASSES} for t in CLASSES}
    for p, t in zip(pred, truth):
        m[t][p] += 1
    n = len(pred)
    acc = sum(m[c][c] for c in CLASSES) / n if n else float("nan")
    unsafe_truth = [t in ("Caution", "Unsafe", "Hazardous") for t in truth]
    unsafe_pred = [p in ("Caution", "Unsafe", "Hazardous") for p in pred]
    tp = sum(a and b for a, b in zip(unsafe_pred, unsafe_truth))
    fn = sum((not a) and b for a, b in zip(unsafe_pred, unsafe_truth))
    fp = sum(a and (not b) for a, b in zip(unsafe_pred, unsafe_truth))
    tn = sum((not a) and (not b) for a, b in zip(unsafe_pred, unsafe_truth))
    return {"matrix": m, "n": n, "exact_accuracy": acc,
            "above_10": {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
                         "sensitivity": tp / (tp + fn) if tp + fn else float("nan"),
                         "specificity": tn / (tn + fp) if tn + fp else float("nan")}}


def rule_class(node_ug_l: float) -> str:
    return tier(node_ug_l)


def network_class(r: Dict, drop: Optional[str] = None) -> Tuple[str, float, str]:
    args = {"arsenic_mg_l": r["node"] / 1000.0, "ph": r["ph"], "conductivity_us_cm": r["ec"],
            "turbidity_ntu": r["turb"], "temperature_c": r["temp"]}
    if drop == "ph":
        args["ph"] = None
    elif drop == "conductivity":
        args["conductivity_us_cm"] = None
    elif drop == "turbidity":
        args["turbidity_ntu"] = None
    elif drop == "temperature":
        args["temperature_c"] = None
    out = net.predict(**args)
    return out["predicted_class"], out["confidence_pct"] / 100.0, out["network_vote"]


class Logistic:
    """One-vs-rest multinomial logistic regression by gradient descent (numpy only), standardised inputs."""

    def fit(self, X, y, iters=3000, lr=0.1, l2=1e-3):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        Y = np.zeros((len(y), len(CLASSES)))
        for i, c in enumerate(y):
            Y[i, CLASSES.index(c)] = 1
        W = np.zeros((Z.shape[1], len(CLASSES)))
        for _ in range(iters):
            logits = Z @ W
            logits -= logits.max(1, keepdims=True)
            P = np.exp(logits)
            P /= P.sum(1, keepdims=True)
            G = Z.T @ (P - Y) / len(Z) + l2 * W
            W -= lr * G
        self.W = W
        return self

    def predict(self, X):
        Z = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        return [CLASSES[i] for i in (Z @ self.W).argmax(1)]


def features(rows: List[Dict]) -> np.ndarray:
    X = np.array([[math.log10(r["node"] + 1.0), r["ph"] if r["ph"] is not None else 7.2,
                   r["ec"] if r["ec"] is not None else 400.0, r["turb"] if r["turb"] is not None else 2.0,
                   r["temp"] if r["temp"] is not None else 24.0] for r in rows])
    return X


def reliability(conf: List[float], correct: List[bool], bins: int = 5) -> Tuple[List[Dict], float]:
    conf, correct = np.array(conf), np.array(correct, bool)
    edges = np.linspace(0.25, 1.0, bins + 1)
    rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        inb = (conf >= lo) & (conf < hi if hi < 1 else conf <= hi)
        if inb.sum() >= 3:
            rows.append({"bin": [float(lo), float(hi)], "n": int(inb.sum()), "mean_confidence": float(conf[inb].mean()),
                         "accuracy": float(correct[inb].mean())})
            ece += inb.sum() / len(conf) * abs(conf[inb].mean() - correct[inb].mean())
    return rows, float(ece)


# ---------------------------------------------------------------- main
def run(rows: List[Dict], out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    model = net.load(net._resolve(None))
    n_params = sum(len(r) * len(r[0]) for k, r in model["weights"].items() if k.startswith("W")) + \
        sum(len(b) for k, b in model["weights"].items() if k.startswith("B"))
    res: Dict = {"label": label, "n_rows": len(rows), "model": "AquaNet-V3 " + "-".join(map(str, model["topology"])),
                 "parameters": n_params, "weights_bytes_float32": n_params * 4, "weights_bytes_int8": n_params,
                 "inference_time_note": "measured on the ESP32 by the boot self-test (serial line [SELFTEST] AquaNet-V3 inference); not claimed here"}
    if len(rows) < 10:
        res["stopped"] = "Fewer than 10 paired rows: nothing to evaluate yet."
        _write(out_dir, res)
        return res
    truth = [tier(r["lab"]) for r in rows]
    net_pred, conf, votes = zip(*[network_class(r) for r in rows])
    rule_pred = [rule_class(r["node"]) for r in rows]
    res["network"] = confusion(list(net_pred), truth)
    res["rule_on_node_value"] = confusion(rule_pred, truth)
    # the network's raw vote (before the safety rules) - how often the rules had to step in
    res["network_vote_overridden"] = int(sum(v != p for v, p in zip(votes, net_pred)))
    # 154: on no row may the final class be "Safe" while the node value is >= 10 µg/L
    res["safety_rule_holds"] = all(not (p == "Safe" and r["node"] >= 10.0) for p, r in zip(net_pred, rows))
    # 149: logistic regression, leave-one-site-out
    X = features(rows)
    sites = np.array([r["site"] for r in rows])
    lr_pred = [None] * len(rows)
    if len(np.unique(sites)) >= 3:
        for s in np.unique(sites):
            te = sites == s
            if (~te).sum() < 10:
                continue
            m = Logistic().fit(X[~te], [truth[i] for i in np.where(~te)[0]])
            for i, p in zip(np.where(te)[0], m.predict(X[te])):
                lr_pred[i] = p
        ok = [i for i, p in enumerate(lr_pred) if p is not None]
        res["logistic_leave_one_site_out"] = confusion([lr_pred[i] for i in ok], [truth[i] for i in ok])
    # 152: ablation
    base_acc = res["network"]["exact_accuracy"]
    abl = {}
    for inp in INPUTS[1:]:
        p = [network_class(r, drop=inp)[0] for r in rows]
        abl[inp] = {"accuracy_without": confusion(p, truth)["exact_accuracy"], "change": confusion(p, truth)["exact_accuracy"] - base_acc}
    res["ablation"] = abl
    # 153: reliability
    correct = [p == t for p, t in zip(net_pred, truth)]
    rel, ece = reliability(list(conf), correct)
    res["reliability"] = {"bins": rel, "expected_calibration_error": ece}
    # 160: failure cases
    res["wrong_rows"] = [{"sample": r["sample"], "site": r["site"], "node_ug_l": round(r["node"], 1), "lab_ug_l": round(r["lab"], 1),
                          "network": p, "lab_class": t, "rule": q}
                         for r, p, t, q in zip(rows, net_pred, truth, rule_pred) if p != t][:50]
    # figures
    ax = sp.Axes((0.25, 1), (0, 1), "AquaNet-V3 reliability" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                 "Stated confidence", "Observed accuracy", f"n = {len(rows)}; expected calibration error {ece:.3f}")
    ax.line([0.25, 1], [0.25, 1], sp.MUTED, 1.0, "5 4", "perfect")
    if rel:
        ax.line([b["mean_confidence"] for b in rel], [b["accuracy"] for b in rel], sp.BLUE, 1.8, None, "network")
        ax.points([b["mean_confidence"] for b in rel], [b["accuracy"] for b in rel], sp.BLUE, 3.5)
    sp.save(os.path.join(out_dir, "reliability.svg"), ax.render())
    _write(out_dir, res)
    return res


def _cm(d: Dict) -> List[str]:
    m = d["matrix"]
    L = ["| lab → / model ↓ | " + " | ".join(CLASSES) + " |", "|---|" + "---|" * len(CLASSES)]
    for t in CLASSES:
        L.append(f"| **lab {t}** | " + " | ".join(str(m[t][p]) for p in CLASSES) + " |")
    a = d["above_10"]
    L += ["", f"exact-class accuracy {100 * d['exact_accuracy']:.1f} % (n = {d['n']}); above-10 sensitivity {100 * a['sensitivity']:.0f} %, "
          f"specificity {100 * a['specificity']:.0f} %, **missed unsafe {a['fn']}**", ""]
    return L


def _write(out_dir: str, res: Dict) -> None:
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# AquaNet-V3 on paired data — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration rows.** They show what the script reports, nothing about the network's field accuracy.", ""]
    L += [f"- Model: {res['model']} — **{res['parameters']} parameters**, {res['weights_bytes_float32']} bytes as float32, "
          f"{res['weights_bytes_int8']} bytes as INT8; {res['inference_time_note']}.",
          f"- Rows: {res['n_rows']} (node reading with a laboratory value; QC-failed rows excluded; censored lab values count as < 10).", ""]
    if res.get("stopped"):
        L += [res["stopped"], ""]
    else:
        L += ["## Network (hard safety rules applied, as deployed) vs laboratory class", ""] + _cm(res["network"])
        L += ["## Baseline 1: threshold rule on the node value alone", ""] + _cm(res["rule_on_node_value"])
        if res.get("logistic_leave_one_site_out"):
            L += ["## Baseline 2: logistic regression on the same five inputs (leave-one-site-out)", ""] + _cm(res["logistic_leave_one_site_out"])
        L += [f"- The safety rules changed the network's raw vote on **{res['network_vote_overridden']}** rows.",
              f"- Hard rule check (item 154): no row with node ≥ 10 µg/L ended as Safe → **{'holds' if res['safety_rule_holds'] else 'VIOLATED'}**.", "",
              "## Ablation (item 152): accuracy when one input is marked 'not measured'", "", "| input removed | accuracy | change |", "|---|---|---|"]
        for k, v in res["ablation"].items():
            L += [f"| {k} | {100 * v['accuracy_without']:.1f} % | {100 * v['change']:+.1f} pp |"]
        L += ["", f"## Reliability (item 153): expected calibration error {res['reliability']['expected_calibration_error']:.3f}", "",
              "![reliability](reliability.svg)", ""]
        if res["wrong_rows"]:
            L += ["## Rows the network got wrong (item 160)", "", "| sample | site | node µg/L | lab µg/L | network | lab class | rule |", "|---|---|---|---|---|---|---|"]
            for w in res["wrong_rows"]:
                L += [f"| {w['sample']} | {w['site']} | {w['node_ug_l']} | {w['lab_ug_l']} | {w['network']} | {w['lab_class']} | {w['rule']} |"]
            L += [""]
        L += ["## What to conclude", "",
              "- If the network is not clearly better than the threshold rule on the node value, say so and keep the rules primary (item 149).",
              "- Any accuracy quoted for AquaNet before this table existed was measured on simulated readings (`Docs/CLAIMS_REGISTER.md` N1).",
              "- The network's inputs beyond arsenic only matter if the ablation shows a loss when they are removed (item 151).", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the deployed AquaNet-V3 on paired node/lab rows")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "aquanet_v3_field"))
    ap.add_argument("--label", default=None)
    a = ap.parse_args(argv)
    if a.demo:
        rows, label = demo_rows(), a.label or "SYNTHETIC demo rows"
    elif a.csv:
        rows, label = load_rows(a.csv), a.label or os.path.basename(a.csv)
    else:
        ap.error("give a paired CSV or --demo")
    res = run(rows, a.out, label)
    if res.get("stopped"):
        print(res["stopped"])
    else:
        print(f"network exact accuracy {100 * res['network']['exact_accuracy']:.1f} % vs rule {100 * res['rule_on_node_value']['exact_accuracy']:.1f} % "
              f"(n = {res['n_rows']}); safety rule holds: {res['safety_rule_holds']}")
    print(f"-> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
