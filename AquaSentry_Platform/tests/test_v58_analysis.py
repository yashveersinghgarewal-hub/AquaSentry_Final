"""The two v5.8 analysis scripts must run end to end on their labelled synthetic demo data and write the judge
figures. They are the evaluation commands the evidence package points at (review items 29, 30, 54)."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANALYSIS = os.path.join(ROOT, "Analysis")


def _run(script, out):
    r = subprocess.run([sys.executable, os.path.join(ANALYSIS, script), "--demo", "--out", out],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_paired_validation_demo(tmp_path):
    out = str(tmp_path / "val")
    _run("paired_validation.py", out)
    for f in ("report.md", "metrics.json", "scatter.svg", "bland_altman.svg", "roc.svg"):
        assert os.path.exists(os.path.join(out, f)), f
    m = json.load(open(os.path.join(out, "metrics.json"), encoding="utf-8"))
    assert "SYNTHETIC" in m["label"] and m["n_pairs"] >= 100 and m["n_censored_lab"] > 0
    assert 0.8 < m["regression"]["slope"] < 1.0 and m["regression"]["slope_ci95"][0] < m["regression"]["slope"]
    d10 = m["decisions"]["10"]
    assert 0 <= d10["sensitivity"]["ci95"][0] <= d10["sensitivity"]["value"] <= d10["sensitivity"]["ci95"][1] <= 1
    assert d10["auc"] > 0.9 and "near_cutoff_band" in d10
    report = open(os.path.join(out, "report.md"), encoding="utf-8").read()
    assert "SYNTHETIC" in report and "Wilson" in report and "rule of three" in report.lower()


def test_aquanet_pipeline_demo(tmp_path):
    out = str(tmp_path / "pipe")
    stdout = _run("aquanet_v2_pipeline.py", out)
    assert "calibration line" in stdout
    m = json.load(open(os.path.join(out, "metrics.json"), encoding="utf-8"))
    assert m["n_sites"] >= 4 and m["split"].startswith("leave-one-site-out")
    for name in ("calibration line", "ridge", "PLS", "residual MLP"):
        d = m["models"][name]
        assert d["mae_ug_l"] > 0 and 0.7 <= d["conformal"]["empirical_coverage"] <= 1.0
        assert len(d["referral_curve"]["referred"]) == len(d["referral_curve"]["missed_unsafe"])
    assert os.path.exists(os.path.join(out, "referral_curve.svg")) and os.path.exists(os.path.join(out, "reliability.svg"))


def test_pipeline_refuses_too_little_data(tmp_path):
    sys.path.insert(0, ANALYSIS)
    import aquanet_v2_pipeline as p
    X, y, cens, sites, _ = p.demo(n_sites=2, per_site=10)
    res = p.run(X, y, cens, sites, str(tmp_path / "small"), "SYNTHETIC tiny")
    assert "stopped" in res and "models" not in res
