#!/usr/bin/env python3
"""
Weighted decision matrices with a sensitivity check (ISEF items 48, 49, 55, 57).

A decision matrix CSV (see Docs/templates/decision_matrix_template.csv):

    criterion,weight,<option A>,<option B>,...        scores 1-5, weights in any positive unit
    LOD,5,3,4,5
    cost per test,4,5,3,2
    ...
    # lines starting with # are notes

The script normalises the weights, reports each option's weighted score, and then asks the question judges ask:
does the winner survive if the weights are wrong? It perturbs every weight by ± 30 % (1 000 random draws) and
reports how often each option comes first. A choice that wins 95 % of draws is a robust choice; one that wins 52 %
is a coin toss and should be said so on the poster.

Usage:  python Analysis/decision_matrix.py Docs/templates/decision_matrix_template.csv --out Analysis/out/decisions
        python Analysis/decision_matrix.py --demo --out Analysis/out/decisions_demo
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402


def read(path: str) -> Tuple[List[str], List[str], np.ndarray, np.ndarray]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].strip().startswith("#")]
    header = rows[0]
    options = header[2:]
    criteria, weights, scores = [], [], []
    for r in rows[1:]:
        if len(r) < 3 or not r[0].strip():
            continue
        criteria.append(r[0].strip())
        weights.append(float(r[1]))
        scores.append([float(x) for x in r[2:2 + len(options)]])
    return criteria, options, np.array(weights), np.array(scores)


def demo():
    criteria = ["detection limit", "cost per test", "field robustness", "needs reagents", "speed", "repeatability"]
    options = ["gold screen-printed strip", "gold disc electrode", "bismuth film", "mercury film (excluded)"]
    weights = np.array([5, 4, 4, 3, 2, 3], float)
    scores = np.array([[3, 4, 2, 5], [5, 2, 4, 3], [4, 3, 3, 2], [3, 4, 2, 2], [4, 4, 4, 4], [3, 4, 3, 5]], float)
    return criteria, options, weights, scores


def evaluate(weights: np.ndarray, scores: np.ndarray, options: List[str], draws: int = 1000, perturb: float = 0.3, seed: int = 1) -> Dict:
    w = weights / weights.sum()
    total = w @ scores
    order = np.argsort(-total)
    rng = np.random.default_rng(seed)
    wins = np.zeros(len(options))
    for _ in range(draws):
        wp = weights * (1 + rng.uniform(-perturb, perturb, len(weights)))
        wp = np.clip(wp, 1e-6, None)
        wins[np.argmax((wp / wp.sum()) @ scores)] += 1
    return {"normalised_weights": w.tolist(), "weighted_scores": {o: float(t) for o, t in zip(options, total)},
            "ranking": [options[i] for i in order], "win_rate_under_30pct_weight_noise": {o: float(wins[i] / draws) for i, o in enumerate(options)},
            "robust": bool(wins[order[0]] / draws >= 0.8),
            "margin_to_second": float(total[order[0]] - total[order[1]]) if len(order) > 1 else None}


def run(criteria, options, weights, scores, out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    res = {"label": label, "criteria": criteria, "options": options, "weights": weights.tolist(), "scores": scores.tolist()}
    res.update(evaluate(weights, scores, options))
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    # stacked bar per option
    n = len(options)
    top = max(res["weighted_scores"].values()) * 1.15
    ax = sp.Axes((0, n + 1), (0, top), f"Decision matrix: {label}", "", "Weighted score (max 5)",
                 f"winner {res['ranking'][0]} — wins {100 * res['win_rate_under_30pct_weight_noise'][res['ranking'][0]]:.0f} % of 1 000 draws with weights ± 30 %")
    cols = [sp.BLUE, sp.GREEN, sp.AMBER, sp.VIOLET, sp.RED, sp.MUTED]
    w = np.array(res["normalised_weights"])
    for j, o in enumerate(options):
        base = 0.0
        for i, c in enumerate(criteria):
            h = w[i] * scores[i, j]
            ax.parts.append(f"<rect x='{ax.px(j + 0.65):.1f}' y='{ax.py(base + h):.1f}' width='{ax.px(j + 1.35) - ax.px(j + 0.65):.1f}' "
                            f"height='{ax.py(base) - ax.py(base + h):.1f}' fill='{cols[i % len(cols)]}' fill-opacity='0.85'/>")
            base += h
        ax.text(j + 1, base + top * 0.02, o[:22], sp.INK, 10, "middle")
    for i, c in enumerate(criteria):
        ax._legend(f"{c} (w {w[i]:.2f})", cols[i % len(cols)])
    sp.save(os.path.join(out_dir, "matrix.svg"), ax.render())
    L = [f"# Decision matrix — {label}", "", "| criterion | weight | " + " | ".join(options) + " |", "|---|---|" + "---|" * n]
    for i, c in enumerate(criteria):
        L += [f"| {c} | {weights[i]:g} ({w[i]:.2f}) | " + " | ".join(f"{scores[i, j]:g}" for j in range(n)) + " |"]
    L += ["| **weighted score** | | " + " | ".join(f"**{res['weighted_scores'][o]:.2f}**" for o in options) + " |", "",
          f"Ranking: {' > '.join(res['ranking'])}; margin to second {res['margin_to_second']:.2f}.", "",
          "## Does the winner survive wrong weights?", "", "| option | wins with weights ± 30 % |", "|---|---|"]
    for o in options:
        L += [f"| {o} | {100 * res['win_rate_under_30pct_weight_noise'][o]:.0f} % |"]
    L += ["", ("**Robust choice** (wins ≥ 80 % of draws)." if res["robust"] else
               "**Not robust**: say on the poster that the choice depends on the weights, and which criterion decides it."), "",
          "![matrix](matrix.svg)", "", "Scores are the team's judgement (1 = poor, 5 = excellent); write the reason for each score in the decision log (item 48).", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Weighted decision matrix with weight-sensitivity check")
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "decisions"))
    ap.add_argument("--label", default=None)
    a = ap.parse_args(argv)
    if a.demo:
        c, o, w, s = demo()
        label = a.label or "electrode choice (example scores)"
    elif a.csv:
        c, o, w, s = read(a.csv)
        label = a.label or os.path.splitext(os.path.basename(a.csv))[0]
    else:
        ap.error("give a matrix CSV or --demo")
    res = run(c, o, w, s, a.out, label)
    print(f"{res['ranking'][0]} wins ({100 * res['win_rate_under_30pct_weight_noise'][res['ranking'][0]]:.0f} % robust) -> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
