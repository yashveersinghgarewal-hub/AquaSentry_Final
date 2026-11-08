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


# ---------------------------------------------------------------- v5.9 scripts (ISEF roadmap items)
def _run_script(script, args, timeout=300):
    r = subprocess.run([sys.executable, os.path.join(ANALYSIS, script), *args], capture_output=True, text=True, timeout=timeout)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_aquanet_v3_field_eval_demo(tmp_path):
    out = str(tmp_path / "v3")
    _run_script("aquanet_v3_field_eval.py", ["--demo", "--out", out])
    m = json.load(open(os.path.join(out, "metrics.json"), encoding="utf-8"))
    assert m["parameters"] == 352 and m["safety_rule_holds"] is True            # item 155, 154
    assert set(m["ablation"]) == {"ph", "conductivity", "turbidity", "temperature"}
    assert "rule_on_node_value" in m and "logistic_leave_one_site_out" in m
    assert 0 <= m["reliability"]["expected_calibration_error"] <= 1


def test_interference_fits_slopes_with_intervals(tmp_path):
    out = str(tmp_path / "intf")
    _run_script("interference.py", ["--demo", "--out", out])
    m = json.load(open(os.path.join(out, "metrics.json"), encoding="utf-8"))
    cu = m["interferents"]["copper"]
    assert cu["slope_pct_per_unit"] > 0 and cu["slope_ci95"][0] < cu["slope_pct_per_unit"] < cu["slope_ci95"][1]
    assert cu["slope_significant"] is True and cu["leaves_window_at"] is not None
    assert os.path.exists(os.path.join(out, "recovery_copper.svg"))


def test_run_order_is_blinded_and_reproducible(tmp_path):
    out = str(tmp_path / "runs")
    _run_script("run_order.py", ["--samples", "S-01", "S-02", "--standards", "0", "10", "50", "--replicates", "2", "--blanks", "1",
                                 "--day", "2026-12-03", "--seed", "7", "--out", out])
    sheet = open(os.path.join(out, "run_sheet_2026-12-03.csv"), encoding="utf-8").read().splitlines()
    key = open(os.path.join(out, "key_2026-12-03.csv"), encoding="utf-8").read().splitlines()
    assert "seed 7" in sheet[0] and sheet[2].startswith("1,CHECK-OPEN") and sheet[-1].split(",")[1] == "CHECK-CLOSE"
    assert len(sheet) == 2 + 2 + 2 * 2 + 3 * 2 + 1          # header lines + 2 checks + samples + standards + blank
    assert "S-01" not in "\n".join(sheet[1:]) and "S-01" in "\n".join(key)      # operator sheet carries no sample names
    _run_script("run_order.py", ["--samples", "S-01", "S-02", "--standards", "0", "10", "50", "--replicates", "2", "--blanks", "1",
                                 "--day", "2026-12-03", "--seed", "7", "--out", str(tmp_path / "again")])
    assert open(os.path.join(str(tmp_path / "again"), "run_sheet_2026-12-03.csv"), encoding="utf-8").read().splitlines() == sheet


def test_control_chart_flags_drift(tmp_path):
    out = str(tmp_path / "cc")
    _run_script("control_chart.py", ["--demo", "--out", out])
    m = json.load(open(os.path.join(out, "metrics.json"), encoding="utf-8"))
    assert m["flags"] and any(f["index"] >= 30 for f in m["flags"])          # the demo electrode fades from run 29
    assert m["warning_limits_pct"][0] < m["centre_pct"] < m["warning_limits_pct"][1]


def test_peak_check_agrees_with_generator_truth(tmp_path):
    out = str(tmp_path / "pk")
    _run_script("peak_check.py", ["--demo", "--out", out])
    m = json.load(open(os.path.join(out, "metrics.json"), encoding="utf-8"))
    assert m["compared"] >= 50 and abs(m["height"]["relative_bias_pct"]) < 5 and 0.95 < m["height"]["deming_slope"] < 1.05


def test_project_figures_and_poster_builder(tmp_path):
    out = str(tmp_path / "proj")
    _run_script("project_figures.py", ["all", "--out", out])
    for f in ("gantt.svg", "design_history.svg", "landscape.svg", "cost.md", "cost.json", "qr.svg", "qr.pdf"):
        assert os.path.exists(os.path.join(out, f)), f
    cost = json.load(open(os.path.join(out, "cost.json"), encoding="utf-8"))
    assert cost["parts_without_price"]                      # the template ships without prices: nothing is invented
    assert "AquaSentry research year" in open(os.path.join(out, "gantt.svg"), encoding="utf-8").read()
    poster = str(tmp_path / "poster")
    _run_script("make_poster_figures.py", ["--demo", "--out", poster], timeout=600)
    idx = open(os.path.join(poster, "index.md"), encoding="utf-8").read()
    assert "SYNTHETIC" in idx and "FAILED" not in idx
