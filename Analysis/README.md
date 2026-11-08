# Analysis

| Script | What it does | Data it needs |
|---|---|---|
| `mas_g1_arsenic_analysis.py` | The scan generator and the **synthetic example** calibration (4 simulated standards, R² 0.9967 on those points). This is where the factory line in `app/standards.py` comes from; it is not a laboratory calibration. | none (generates) |
| `generate_arsenic_data.py` | Synthetic scan files for software tests and demos. | none |
| `paired_validation.py` | Node vs laboratory: Deming regression with bootstrap CIs, Bland–Altman, confusion matrices at 10 and 20 µg/L with Wilson intervals, ROC/AUC, near-cutoff band, censored-result handling, rule-of-three note, uncertainty coverage. Writes `report.md`, `metrics.json` and SVG figures. | `GET /api/data/export/paired` CSV, or `--demo` |
| `aquanet_v2_pipeline.py` | Can a learned model beat the calibration line on **unseen sites**? Leave-one-site-out comparison of the calibration line, ridge, PLS and a residual MLP, split-conformal 90 % intervals with coverage, reliability table, referral-vs-missed-unsafe curve. Refuses to run below 4 sites / 40 pairs. | same CSV, or `--demo` |
| `svg_plots.py` | Dependency-free SVG plotting used by the two scripts. | – |

Both analysis scripts need only numpy. `--demo` runs on **labelled synthetic** data and says so in every title; it shows what
the scripts produce and nothing about the sensor. The field dataset and its minimum record are described in
[`../Data/field/README.md`](../Data/field/README.md).

```
python Analysis/paired_validation.py paired.csv --out Analysis/out/validation
python Analysis/aquanet_v2_pipeline.py paired.csv --out Analysis/out/aquanet_pipeline
```
