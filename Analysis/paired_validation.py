#!/usr/bin/env python3
"""
Paired validation: AquaSentry node readings against laboratory results (v5.8, review items 21, 30, 263).

Reads the paired dataset the server exports (GET /api/data/export/paired -> CSV) and produces the figures and
numbers a method-comparison study needs, with their uncertainties:

  * scatter with the 1:1 line and a Deming regression (both methods carry error; ordinary least squares would
    bias the slope towards zero), slope / intercept with bootstrap 95 % confidence intervals
  * Bland-Altman plot: bias and 95 % limits of agreement, with a check for proportional bias
  * confusion matrices at the two decisions that matter - 10 µg/L (the IS 10500 / WHO limit) and 20 µg/L (the
    node's detection limit) - with sensitivity, specificity, PPV, NPV and Wilson score 95 % intervals
  * ROC curve and AUC of the node value against "lab >= cutoff"
  * the near-cutoff band (lab within ± 5 µg/L of a cutoff), where any screening test is weakest
  * censored laboratory results ("< reporting limit") handled explicitly: they count as "below" for the
    decisions and are left out of the regression unless --censored substitute is given
  * the rule of three: with zero observed misses in n pairs, the 95 % upper bound on the miss rate is 3 / n,
    so a small study cannot claim a small miss rate

Usage
-----
  python Analysis/paired_validation.py paired.csv --out Analysis/out/validation
  python Analysis/paired_validation.py --demo --out Analysis/out/validation_demo    (SYNTHETIC demo data)

Everything written by --demo is labelled SYNTHETIC in the report and in every figure title. It shows what the
script does; it says nothing about the sensor. Only pairs collected with real samples count.
numpy is the only dependency.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import svg_plots as sp  # noqa: E402

CUTOFFS = (10.0, 20.0, 50.0)     # legal limit, node LOD, the ISEF list's second reporting cutoff (item 110)
NEAR_BAND = 5.0
BOOT = 2000


# ---------------------------------------------------------------- data
def read_pairs(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        try:
            node = float(r.get("device_ug_l") or r.get("node_ug_l") or "nan")
        except ValueError:
            node = float("nan")
        lab_raw = r.get("lab_ug_l") or ""
        try:
            lab = float(lab_raw)
        except ValueError:
            lab = float("nan")
        if not (math.isfinite(node) and math.isfinite(lab)):
            continue
        qc = (r.get("qc_status") or "").lower()
        if qc == "fail" or (r.get("screening_outcome") or "") == "invalid":
            continue      # a failed test has no value to compare (it is counted separately below)
        out.append({
            "node": node, "lab": lab,
            "censored": (r.get("lab_qualifier") or "").strip() == "<",
            "rl": _f(r.get("lab_reporting_limit_ug_l")),
            "unc": _f(r.get("device_uncertainty_ug_l")),
            "outcome": r.get("screening_outcome") or "",
            "site": r.get("site_name") or r.get("village") or r.get("device_code") or "",
            "sample": r.get("sample_code") or "",
            "lot": r.get("electrode_lot") or "",
        })
    return out


def count_failed(path: str) -> int:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for r in csv.DictReader(f) if (r.get("qc_status") or "").lower() == "fail"
                   or (r.get("screening_outcome") or "") == "invalid")


def _f(v) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def demo_pairs(n: int = 120, seed: int = 7) -> List[Dict]:
    """SYNTHETIC pairs: a log-uniform 'truth' from 1 to 300 µg/L (each sample read twice by the node), a lab with 5 %
    error and a 2 µg/L reporting limit, a node with a 0.92 slope, +1.5 µg/L offset, 12 % proportional noise and
    4 µg/L floor noise, two electrode lots."""
    rng = np.random.default_rng(seed)
    truth = np.repeat(np.exp(rng.uniform(np.log(1.0), np.log(300.0), n // 2)), 2)   # each sample read twice
    lab = truth * (1 + rng.normal(0, 0.05, n))
    node = 1.5 + 0.92 * truth + rng.normal(0, 4.0, n) + truth * rng.normal(0, 0.12, n)
    node = np.clip(node, 0, None)
    out = []
    for i in range(n):
        cens = lab[i] < 2.0
        out.append({"node": float(round(node[i], 2)), "lab": 2.0 if cens else float(round(lab[i], 2)),
                    "censored": bool(cens), "rl": 2.0, "unc": float(round(max(4.0, 0.1 * node[i]) * 2, 1)),
                    "outcome": "", "site": f"Site-{i % 6 + 1}", "sample": f"DEMO-{(i // 2) + 1:03d}", "lot": f"LOT-{i % 2 + 1}"})
    return out


# ---------------------------------------------------------------- statistics
def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def deming(x: np.ndarray, y: np.ndarray, lam: float = 1.0) -> Tuple[float, float]:
    """Deming regression of y on x with error-variance ratio lam = var(err_y) / var(err_x)."""
    mx, my = x.mean(), y.mean()
    sxx = ((x - mx) ** 2).mean()
    syy = ((y - my) ** 2).mean()
    sxy = ((x - mx) * (y - my)).mean()
    if sxy == 0:
        return 0.0, my
    slope = (syy - lam * sxx + math.sqrt((syy - lam * sxx) ** 2 + 4 * lam * sxy * sxy)) / (2 * sxy)
    return float(slope), float(my - slope * mx)


def boot_ci(fn, x: np.ndarray, y: np.ndarray, n_boot: int = BOOT, seed: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    vals = []
    n = len(x)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals.append(fn(x[idx], y[idx]))
    vals = np.asarray(vals)
    return np.percentile(vals, 2.5, axis=0), np.percentile(vals, 97.5, axis=0)


def auc_rank(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney AUC (ties get half credit)."""
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    s = np.concatenate([pos, neg])[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def roc_points(scores: np.ndarray, labels: np.ndarray) -> Tuple[List[float], List[float]]:
    thr = np.unique(scores)[::-1]
    fpr, tpr = [0.0], [0.0]
    P, N = labels.sum(), (~labels).sum()
    for t in thr:
        pred = scores >= t
        tpr.append(float((pred & labels).sum() / P) if P else 0.0)
        fpr.append(float((pred & ~labels).sum() / N) if N else 0.0)
    return fpr, tpr


def confusion(node: np.ndarray, lab_pos: np.ndarray, cutoff: float) -> Dict:
    pred = node >= cutoff
    tp = int((pred & lab_pos).sum())
    fn = int((~pred & lab_pos).sum())
    fp = int((pred & ~lab_pos).sum())
    tn = int((~pred & ~lab_pos).sum())
    d = {"cutoff_ug_l": cutoff, "tp": tp, "fn": fn, "fp": fp, "tn": tn, "n": int(len(node))}
    for name, k, n in (("sensitivity", tp, tp + fn), ("specificity", tn, tn + fp), ("ppv", tp, tp + fp), ("npv", tn, tn + fn)):
        p, lo, hi = wilson(k, n)
        d[name] = {"value": p, "ci95": [lo, hi], "k": k, "n": n}
    d["missed_unsafe"] = fn
    d["rule_of_three_upper_miss_rate"] = (3.0 / (tp + fn)) if fn == 0 and (tp + fn) > 0 else None
    return d


# ---------------------------------------------------------------- main analysis
def analyse(pairs: List[Dict], out_dir: str, label: str, censored_mode: str = "exclude", n_failed: int = 0) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    tag = " (SYNTHETIC demo)" if "SYNTHETIC" in label else ""
    node_all = np.array([p["node"] for p in pairs])
    lab_all = np.array([p["lab"] for p in pairs])
    cens = np.array([p["censored"] for p in pairs])
    res: Dict = {"label": label, "n_pairs": int(len(pairs)), "n_censored_lab": int(cens.sum()),
                 "n_failed_tests_excluded": n_failed, "censored_handling": censored_mode,
                 "sites": sorted({p["site"] for p in pairs if p["site"]})}
    if len(pairs) < 3:
        res["note"] = "Fewer than 3 pairs: nothing can be estimated. Collect paired samples first."
        _write(out_dir, res, [])
        return res

    # regression / agreement on quantified pairs only (a censored lab value is not a number)
    if censored_mode == "substitute":
        lab_q = np.where(cens, np.array([(p["rl"] or p["lab"]) / 2 for p in pairs]), lab_all)
        keep = np.ones(len(pairs), bool)
    else:
        lab_q = lab_all
        keep = ~cens
    x, y = lab_q[keep], node_all[keep]
    if len(x) >= 3:
        slope, icpt = deming(x, y)
        lo, hi = boot_ci(lambda a, b: np.array(deming(a, b)), x, y)
        r = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")
        diff = y - x
        mean = (x + y) / 2
        bias, sd = float(diff.mean()), float(diff.std(ddof=1)) if len(diff) > 1 else float("nan")
        prop = float(np.corrcoef(mean, diff)[0, 1]) if len(diff) > 2 and mean.std() > 0 and diff.std() > 0 else float("nan")
        res["regression"] = {"method": "Deming (error ratio 1)", "n": int(len(x)), "slope": slope, "slope_ci95": [float(lo[0]), float(hi[0])],
                             "intercept_ug_l": icpt, "intercept_ci95": [float(lo[1]), float(hi[1])], "pearson_r": r,
                             "mae_ug_l": float(np.abs(diff).mean()), "rmse_ug_l": float(math.sqrt((diff ** 2).mean()))}
        res["bland_altman"] = {"bias_ug_l": bias, "sd_ug_l": sd, "loa_low": bias - 1.96 * sd, "loa_high": bias + 1.96 * sd,
                               "proportional_bias_r": prop,
                               "note": "difference = node - lab; a |r| above 0.3 between difference and mean means the "
                                       "error grows with concentration (report limits in relative terms)"}
        # figures
        top = float(max(x.max(), y.max()) * 1.08)
        ax = sp.Axes((0, top), (0, top), "Node vs laboratory" + tag, "Laboratory arsenic (µg/L)", "Node arsenic (µg/L)",
                     f"n = {len(x)} quantified pairs; Deming slope {slope:.2f} [{lo[0]:.2f}, {hi[0]:.2f}], intercept {icpt:.1f} µg/L")
        ax.band(10 - NEAR_BAND, 10 + NEAR_BAND, sp.AMBER)
        ax.band(20 - NEAR_BAND, 20 + NEAR_BAND, sp.AMBER)
        ax.line([0, top], [0, top], sp.MUTED, 1.2, "5 4", "1 : 1")
        ax.line([0, top], [icpt, icpt + slope * top], sp.RED, 1.8, None, "Deming fit")
        ax.vline(10, sp.AMBER, "2 3", "10 µg/L limit")
        ax.vline(20, sp.VIOLET, "2 3", "20 µg/L node LOD")
        ax.points(x, y, sp.BLUE, label="pairs")
        if cens.any() and censored_mode != "substitute":
            ax.points(lab_all[cens], node_all[cens], sp.MUTED, 3.0, 0.9, "lab < reporting limit (not fitted)")
        sp.save(os.path.join(out_dir, "scatter.svg"), ax.render())

        ylim = max(abs(diff).max(), abs(bias) + 2.2 * sd) * 1.15 if math.isfinite(sd) else abs(diff).max() * 1.2
        ax = sp.Axes((0, float(mean.max() * 1.08)), (-ylim, ylim), "Bland-Altman" + tag, "Mean of node and lab (µg/L)",
                     "Node − lab (µg/L)", f"bias {bias:+.1f} µg/L; 95 % limits of agreement {bias - 1.96 * sd:+.1f} to {bias + 1.96 * sd:+.1f}")
        ax.hline(0, sp.MUTED, "5 4")
        ax.hline(bias, sp.RED, None, "bias")
        ax.hline(bias + 1.96 * sd, sp.AMBER, "6 4", "± 1.96 SD")
        ax.hline(bias - 1.96 * sd, sp.AMBER, "6 4")
        ax.points(mean, diff, sp.BLUE)
        sp.save(os.path.join(out_dir, "bland_altman.svg"), ax.render())

    # decisions: censored lab values count as below both cutoffs
    res["decisions"] = {}
    roc_ax = sp.Axes((0, 1), (0, 1), "ROC: node value vs laboratory decision" + tag, "False-positive rate (1 − specificity)",
                     "Sensitivity")
    roc_ax.line([0, 1], [0, 1], sp.MUTED, 1.0, "5 4")
    for c, col in zip(CUTOFFS, (sp.AMBER, sp.VIOLET, sp.RED)):
        lab_pos = (lab_all >= c) & ~cens
        d = confusion(node_all, lab_pos, c)
        d["auc"] = auc_rank(node_all, lab_pos)
        near = np.abs(lab_all - c) <= NEAR_BAND
        if near.any():
            agree = ((node_all[near] >= c) == lab_pos[near]).mean()
            d["near_cutoff_band"] = {"half_width_ug_l": NEAR_BAND, "n": int(near.sum()), "agreement": float(agree)}
        res["decisions"][f"{c:.0f}"] = d
        fpr, tpr = roc_points(node_all, lab_pos)
        roc_ax.line(fpr, tpr, col, 1.8, None, f"lab ≥ {c:.0f} µg/L (AUC {d['auc']:.2f})")
    sp.save(os.path.join(out_dir, "roc.svg"), roc_ax.render())

    # screening outcome agreement where the export carried one
    outs = [p["outcome"] for p in pairs if p["outcome"]]
    if outs:
        tab: Dict[str, Dict[str, int]] = {}
        for p in pairs:
            if not p["outcome"]:
                continue
            truth = "lab ≥ 10" if (p["lab"] >= 10 and not p["censored"]) else "lab < 10"
            tab.setdefault(p["outcome"], {}).setdefault(truth, 0)
            tab[p["outcome"]][truth] += 1
        res["outcome_vs_lab"] = tab
        unc = [p["unc"] for p in pairs if p["unc"] and not p["censored"]]
        if unc:
            inside = [abs(p["node"] - p["lab"]) <= p["unc"] for p in pairs if p["unc"] and not p["censored"]]
            res["uncertainty_coverage"] = {"n": len(inside), "fraction_of_lab_values_inside_node_interval": float(np.mean(inside)),
                                           "expected_for_k2": 0.95}
    # v5.9 (ISEF 104, 71): the same numbers per electrode lot and per site, so a bad lot or a hard matrix shows
    res["by_group"] = {"electrode_lot": _group_table(pairs, "lot"), "site": _group_table(pairs, "site")}
    # v5.9 (ISEF 134, 72): repeatability as CV % from repeated node readings of the same sample code
    res["replicate_cv"] = replicate_cv(pairs)
    # v5.9 (ISEF 132, 141): what this sample size can claim, and what a larger study would
    n_unsafe = int(((lab_all >= 10) & ~cens).sum())
    res["sample_size"] = sample_size_table(n_unsafe)
    _write(out_dir, res, pairs)
    return res


def _group_table(pairs: List[Dict], key: str) -> List[Dict]:
    groups: Dict[str, List[Dict]] = {}
    for p in pairs:
        if p.get(key):
            groups.setdefault(p[key], []).append(p)
    out = []
    for g, rows in sorted(groups.items()):
        node = np.array([r["node"] for r in rows])
        lab = np.array([r["lab"] for r in rows])
        cq = np.array([r["censored"] for r in rows])
        q = ~cq
        row = {"group": g, "n": len(rows), "n_quantified": int(q.sum())}
        if q.sum() >= 3:
            diff = node[q] - lab[q]
            row["bias_ug_l"] = float(diff.mean())
            row["mae_ug_l"] = float(np.abs(diff).mean())
            sl, ic = deming(lab[q], node[q])
            row["deming_slope"], row["deming_intercept"] = sl, ic
        pos = (lab >= 10) & ~cq
        if pos.any():
            p_, lo, hi = wilson(int(((node >= 10) & pos).sum()), int(pos.sum()))
            row["sensitivity_10"] = {"value": p_, "ci95": [lo, hi], "k": int(((node >= 10) & pos).sum()), "n": int(pos.sum())}
        out.append(row)
    return out


def replicate_cv(pairs: List[Dict]) -> Dict:
    """CV % of repeated node readings of one sample code, reported in three concentration bands."""
    by_sample: Dict[str, List[float]] = {}
    for p in pairs:
        if p.get("sample"):
            by_sample.setdefault(p["sample"], []).append(p["node"])
    bands = {"low (< 20 µg/L)": [], "medium (20-100 µg/L)": [], "high (> 100 µg/L)": []}
    for vals in by_sample.values():
        if len(vals) < 2:
            continue
        m = float(np.mean(vals))
        if m <= 0:
            continue
        cv = float(np.std(vals, ddof=1) / m * 100.0)
        key = "low (< 20 µg/L)" if m < 20 else "medium (20-100 µg/L)" if m <= 100 else "high (> 100 µg/L)"
        bands[key].append(cv)
    return {k: ({"n_samples": len(v), "median_cv_pct": float(np.median(v)), "max_cv_pct": float(np.max(v))} if v else
                {"n_samples": 0}) for k, v in bands.items()}


def sample_size_table(n_unsafe: int) -> Dict:
    """Wilson 95 % interval width for sensitivity at a few true values, for this study and for planned sizes."""
    def width(n, p):
        if n == 0:
            return None
        k = int(round(p * n))
        _, lo, hi = wilson(k, n)
        return round(hi - lo, 3)
    sizes = sorted({n_unsafe, 20, 30, 50, 100, 200} - {0})
    return {"n_unsafe_in_this_study": n_unsafe,
            "ci_width_at_sensitivity": {str(n): {"0.90": width(n, 0.9), "0.95": width(n, 0.95), "1.00": width(n, 1.0)} for n in sizes},
            "rule_of_three_upper_miss_rate": {str(n): round(3.0 / n, 3) for n in sizes},
            "note": "Width of the 95 % Wilson interval for sensitivity when k = p·n unsafe samples are flagged. "
                    "To claim 'sensitivity ≥ 90 %' with a lower bound above 80 % needs about 100 unsafe samples."}


def _pct(d: Dict) -> str:
    v = d["value"]
    if not math.isfinite(v):
        return "n/a"
    return f"{100 * v:.0f} % [{100 * d['ci95'][0]:.0f}, {100 * d['ci95'][1]:.0f}] ({d['k']}/{d['n']})"


def _write(out_dir: str, res: Dict, pairs: List[Dict]) -> None:
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# Paired validation — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data.** These numbers describe the generator in this script, not the sensor.", ""]
    L += [f"- Pairs analysed: **{res['n_pairs']}** (laboratory results below the reporting limit: {res['n_censored_lab']}, "
          f"handled by *{res['censored_handling']}*; node tests that failed QC and were left out: {res['n_failed_tests_excluded']})",
          f"- Sites: {len(res.get('sites', []))}", ""]
    if res.get("note"):
        L += [res["note"], ""]
    if "regression" in res:
        g, b = res["regression"], res["bland_altman"]
        L += ["## Agreement (quantified pairs)", "",
              f"- Deming regression: node = **{g['slope']:.3f}** × lab + **{g['intercept_ug_l']:.1f}** µg/L "
              f"(slope 95 % CI {g['slope_ci95'][0]:.3f}–{g['slope_ci95'][1]:.3f}; intercept {g['intercept_ci95'][0]:.1f}–{g['intercept_ci95'][1]:.1f}); "
              f"Pearson r = {g['pearson_r']:.3f}; n = {g['n']}",
              f"- MAE {g['mae_ug_l']:.1f} µg/L, RMSE {g['rmse_ug_l']:.1f} µg/L",
              f"- Bland–Altman: bias **{b['bias_ug_l']:+.1f}** µg/L, 95 % limits of agreement {b['loa_low']:+.1f} to {b['loa_high']:+.1f} µg/L; "
              f"difference-vs-mean r = {b['proportional_bias_r']:.2f}" + (" (proportional error: quote relative limits)" if abs(b['proportional_bias_r'] or 0) > 0.3 else ""),
              "", "![scatter](scatter.svg)", "", "![bland-altman](bland_altman.svg)", ""]
    if res.get("decisions"):
        L += ["## Decisions", ""]
        for c, d in res["decisions"].items():
            L += [f"### Node ≥ {c} µg/L vs laboratory ≥ {c} µg/L", "",
                  "| | lab ≥ cutoff | lab < cutoff |", "|---|---|---|",
                  f"| node ≥ cutoff | {d['tp']} | {d['fp']} |", f"| node < cutoff | **{d['fn']}** (missed) | {d['tn']} |", "",
                  f"- Sensitivity {_pct(d['sensitivity'])}; specificity {_pct(d['specificity'])}; PPV {_pct(d['ppv'])}; NPV {_pct(d['npv'])}; AUC {d['auc']:.3f}"]
            if d.get("rule_of_three_upper_miss_rate") is not None:
                L += [f"- No misses were observed among {d['sensitivity']['n']} unsafe samples. By the rule of three the 95 % upper bound on the "
                      f"miss rate is still **{100 * d['rule_of_three_upper_miss_rate']:.0f} %**: zero misses in a small study is not a small miss rate."]
            if d.get("near_cutoff_band"):
                nb = d["near_cutoff_band"]
                L += [f"- Near the cutoff (lab within ± {nb['half_width_ug_l']:.0f} µg/L, n = {nb['n']}): agreement {100 * nb['agreement']:.0f} %. "
                      f"This band is where a screening test is weakest; the node reports *retest* there."]
            L += [""]
        L += ["![roc](roc.svg)", ""]
    if res.get("outcome_vs_lab"):
        L += ["## Screening outcome vs laboratory", "", "| outcome | lab ≥ 10 | lab < 10 |", "|---|---|---|"]
        for o, row in res["outcome_vs_lab"].items():
            L += [f"| {o} | {row.get('lab ≥ 10', 0)} | {row.get('lab < 10', 0)} |"]
        L += [""]
    if res.get("uncertainty_coverage"):
        u = res["uncertainty_coverage"]
        L += [f"- Uncertainty check: the laboratory value fell inside the node's ± U interval for **{100 * u['fraction_of_lab_values_inside_node_interval']:.0f} %** "
              f"of {u['n']} pairs (a k = 2 interval should cover about 95 %; much less means U is understated).", ""]
    if res.get("by_group"):
        for key, title in (("electrode_lot", "By electrode lot"), ("site", "By site")):
            rows = res["by_group"].get(key) or []
            if rows:
                L += [f"## {title}", "", "| group | n | bias µg/L | MAE µg/L | Deming slope | sensitivity @10 |", "|---|---|---|---|---|---|"]
                for g in rows:
                    sens = g.get("sensitivity_10")
                    L += [f"| {g['group']} | {g['n']} | {g.get('bias_ug_l', float('nan')):+.1f} | {g.get('mae_ug_l', float('nan')):.1f} | "
                          f"{g.get('deming_slope', float('nan')):.2f} | {_pct(sens) if sens else 'n/a'} |"]
                L += [""]
    if res.get("replicate_cv"):
        L += ["## Repeatability (repeated node readings of one sample)", "", "| band | samples | median CV % | max CV % |", "|---|---|---|---|"]
        for band, d in res["replicate_cv"].items():
            L += [f"| {band} | {d['n_samples']} | {d.get('median_cv_pct', float('nan')):.1f} | {d.get('max_cv_pct', float('nan')):.1f} |"
                  if d["n_samples"] else f"| {band} | 0 | – | – |"]
        L += [""]
    if res.get("sample_size"):
        ss = res["sample_size"]
        L += ["## What this sample size can claim", "", f"Unsafe (lab ≥ 10 µg/L) samples in this study: **{ss['n_unsafe_in_this_study']}**.", "",
              "| n unsafe | CI width if sensitivity = 90 % | = 95 % | = 100 % | rule-of-three upper miss rate |", "|---|---|---|---|---|"]
        for n, w in ss["ci_width_at_sensitivity"].items():
            L += [f"| {n} | {w['0.90']} | {w['0.95']} | {w['1.00']} | {ss['rule_of_three_upper_miss_rate'][n]} |"]
        L += ["", ss["note"], ""]
    L += ["## How to read this", "",
          "- The node is a **screening** test with a 20 µg/L detection limit; it cannot confirm compliance with the 10 µg/L limit. "
          "Sensitivity at 10 µg/L therefore matters most, and the 10–20 µg/L band is expected to be weak.",
          "- Confidence intervals are Wilson score intervals; regression intervals are bootstrap percentiles (2 000 resamples).",
          "- Laboratory results below the reporting limit are *censored*: they are counted as below both cutoffs and are not fitted as numbers.",
          "- Rule of three: when a study sees **zero** misses among n unsafe samples, the one-sided 95 % upper bound on the miss rate is still "
          "about 3 / n (about 10 % for n = 30). Study size, not the observed zero, sets what can be claimed.",
          ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Node-vs-laboratory paired validation")
    ap.add_argument("csv", nargs="?", help="paired CSV from GET /api/data/export/paired")
    ap.add_argument("--demo", action="store_true", help="run on SYNTHETIC demonstration pairs")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "validation"))
    ap.add_argument("--censored", choices=["exclude", "substitute"], default="exclude",
                    help="censored lab values in the regression: leave out (default) or substitute half the reporting limit")
    ap.add_argument("--label", default=None)
    a = ap.parse_args(argv)
    if a.demo:
        pairs, failed, label = demo_pairs(), 0, a.label or "SYNTHETIC demonstration pairs"
    elif a.csv:
        pairs, failed, label = read_pairs(a.csv), count_failed(a.csv), a.label or os.path.basename(a.csv)
    else:
        ap.error("give a paired CSV or --demo")
    res = analyse(pairs, a.out, label, a.censored, failed)
    print(f"{res['n_pairs']} pairs -> {a.out}/report.md")
    for c, d in (res.get("decisions") or {}).items():
        print(f"  at {c} µg/L: sensitivity {_pct(d['sensitivity'])}, specificity {_pct(d['specificity'])}, AUC {d['auc']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
