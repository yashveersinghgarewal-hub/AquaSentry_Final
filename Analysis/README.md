# Analysis

| Script | What it does | Data it needs |
|---|---|---|
| `mas_g1_arsenic_analysis.py` | The scan generator and the **synthetic example** calibration (4 simulated standards, R² 0.9967 on those points). This is where the factory line in `app/standards.py` comes from; it is not a laboratory calibration. | none (generates) |
| `generate_arsenic_data.py` | Synthetic scan files for software tests and demos. | none |
| `paired_validation.py` | Node vs laboratory: Deming regression with bootstrap CIs, Bland–Altman, confusion matrices at 10 and 20 µg/L with Wilson intervals, ROC/AUC, near-cutoff band, censored-result handling, rule-of-three note, uncertainty coverage. Writes `report.md`, `metrics.json` and SVG figures. | `GET /api/data/export/paired` CSV, or `--demo` |
| `aquanet_v2_pipeline.py` | Can a learned model beat the calibration line on **unseen sites**? Leave-one-site-out comparison of the calibration line, ridge, PLS and a residual MLP, split-conformal 90 % intervals with coverage, reliability table, referral-vs-missed-unsafe curve. Refuses to run below 4 sites / 40 pairs. | same CSV, or `--demo` |
| `aquanet_v3_field_eval.py` | The deployed AquaNet-V3 on paired rows: confusion vs the laboratory class, threshold-rule and logistic baselines, ablation, reliability diagram, safety-rule check, parameter count (ISEF 148–155). | paired CSV or `--demo` |
| `interference.py` | Recovery vs interferent concentration (Cu, Fe, pH, temperature …): least-squares slope with 95 % CI, where recovery leaves 80–120 % (ISEF 67–69, 139). | interference CSV or `--demo` |
| `run_order.py` | Blinded, randomised run sheet for the operator and a sealed key for the supervisor; opening and closing check standards fixed (ISEF 90, 95, 96). | sample codes |
| `control_chart.py` | Shewhart chart of the daily check standard with Western Electric rules (ISEF 90, 99). | `/api/qc/runs` export or `--demo` |
| `peak_check.py` | The pipeline's peaks against ≥ 50 hand-measured peaks: bias, limits of agreement, Deming slope, worst disagreements (ISEF 76). | hand-peaks CSV + scan files, or `--demo` |
| `project_figures.py` | Gantt from `Docs/planning/timeline.csv`, design-history figure, cost-vs-LOD landscape, cost model from the BOM, printable QR (ISEF 21, 47, 50, 58, 210, 236). | CSVs in Docs/planning and Data/field |
| `make_poster_figures.py` | Runs everything above and writes an index: every poster figure from the raw files in one command (ISEF 138, 264). | the same inputs or `--demo` |
| `roadmap_status.py` | Renders `Docs/ISEF_ROADMAP_STATUS.md` from the status CSV. | – |
| `svg_plots.py` | Dependency-free SVG plotting (Okabe-Ito palette) used by every script. | – |

All scripts need only numpy (the QR figure uses reportlab, already a dependency). `--demo` runs on **labelled synthetic** data and says so in every title; it shows what
the scripts produce and nothing about the sensor. The field dataset and its minimum record are described in
[`../Data/field/README.md`](../Data/field/README.md).

```
python Analysis/paired_validation.py paired.csv --out Analysis/out/validation
python Analysis/aquanet_v2_pipeline.py paired.csv --out Analysis/out/aquanet_pipeline
```
