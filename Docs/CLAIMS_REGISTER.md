# Claims and evidence register

Review item 55: every claim the project makes about limits, accuracy, cost, autonomy or power is listed here with its
evidence, or marked as a **target**. A claim with no dated test must be presented as a target, nowhere else. Keep this
file current; when slides, README, dashboard and chatbot disagree, this register wins and the others are corrected.

Status key: **Measured** (a dated test on real samples or hardware exists and is linked) · **Software check** (a
reproducible test on simulated data or on the code itself) · **Specification** (a manufacturer's figure, not
reproduced here) · **Target** (not yet demonstrated).

## Measurement

| # | Claim | Status | Evidence / where stated | Notes |
|---|---|---|---|---|
| M1 | The node detects arsenic with a 20 µg/L detection limit | **Specification** | `app/standards.py LOD_UG_L`; AccuSensing As-M003050 strip spec | Not yet measured with our blanks (review item 08). Every verdict text says "detection limit 20 µg/L; cannot see the 10 µg/L limit". |
| M2 | Quantification range 30–500 µg/L | **Specification** | `app/standards.py`; strip spec | Values above 500 are reported as "above calibrated range". |
| M3 | The strip measures As(III), not total arsenic | **Specification** | `arsenic_species` field, dashboard and PDF label "As(III) only" unless a pre-reduction step is recorded | A total-arsenic claim needs lab recovery on As(V) spikes (item 01). |
| M4 | Factory calibration As (mg/L) = (Ip − 0.0096) / 0.8563, R² 0.9967 | **Software check** | `Analysis/mas_g1_arsenic_analysis.py`; `CALIBRATION_PROVENANCE` | The four standards are **synthetic** scans from the generator. The dashboard, PDF and `/api/scans` now say so. A laboratory calibration (external standards or standard addition) replaces it per device (`/api/admin/calibrations/*`). |
| M5 | Measurement uncertainty ± U (k = 2) shown with each result | **Software check** | `signal_processing.estimate_uncertainty`; `tests/test_v58_pipeline.py` | U = 2·√(u_noise² + u_cal²); u_noise is measured from the scan's shoulder noise, u_cal is **assumed 5 %** until calibration replicates give a measured value. Coverage is checked by `paired_validation.py` when pairs exist. |
| M6 | The pipeline rejects malformed scans and never reports a value for them | **Software check** | `tests/test_v58_pipeline.py::TestPipelineRobustness`, `TestScanEvidence` | Jumbled sweep, too few points, NaN, missing shoulders, saturation, invalid calibration. |
| M7 | Browser and server give the same answer for the same trace | **Software check** | `test_asv_js_matches_the_python_pipeline` (17 traces, tolerance 0.05 µg/L) | Analysis version `asv-1.2.0` is stored with each result. |
| M8 | Copper and other interferents do not bias the result | **Target** | item 09, 67 | A copper-like bump is now handled by the robust baseline in software (test exists), but the chemistry has not been measured. |
| M9 | Repeatability / intermediate precision / electrode lifetime | **Target** | items 70–72 | Scan-to-scan disagreement is a QC rule (`QC_SCANS_DISAGREE`), not a measured figure. |

## Decisions

| # | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| D1 | One screening outcome per test: invalid / not detected / retest / screen positive | **Software check** | `classification.screening_outcome`; tests | Guard band = the reading's expanded uncertainty. |
| D2 | Limits: IS 10500 Amendment 1 (2015) 10 µg/L, no relaxation; WHO 10 µg/L | **Measured** (documentary) | `app/standards.py`, BIS and WHO documents | The former 50 µg/L "relaxation" tier was removed in v5.7. |
| D3 | Sensitivity ≥ 90 % at 10 µg/L against ICP-MS | **Target** | item 31 of the ISEF list; `Analysis/paired_validation.py` computes it | Needs the paired dataset. With zero misses in 30 positives the 95 % upper miss rate is still ~10 % (rule of three). |
| D4 | Corroboration = other QC-passed hardware nodes at the same place within 24 h | **Software check** | `main.corroborating_devices`; tests | Unrelated devices never corroborate each other. |

## Model

| # | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| N1 | AquaNet-V3 exact-reading and end-to-end accuracy figures | **Software check** | `Docs/neural/AQUANET_V3_REPORT.md` (table of candidates) | Accuracy on a **synthetic** rule-labelled benchmark: it measures agreement with the rules on simulated readings, not with laboratory arsenic. Must never be quoted as field accuracy. |
| N2 | AquaNet-V1 "trained with Adam on 8 000 samples, 99.7 %" | **Withdrawn** | `Docs/CODE_GUIDE.md` §4.9 | The V1 weights were hand-set; the claim was wrong and is kept only as history. |
| N3 | A learned model improves on the calibration line on unseen sites | **Target** | `Analysis/aquanet_v2_pipeline.py` (grouped by site, conformal intervals) | Runs today only on labelled synthetic data; the verdict line of its report is the claim to make once real pairs exist. |
| N4 | Inference time on the ESP32 | **Measured on boot** | firmware 5.8 self-test prints `AquaNet-V3 inference: N us` and `/status.json` carries it | Record the number from a real board in the logbook; no figure is claimed here until then. |

## System

| # | Claim | Status | Evidence | Notes |
|---|---|---|---|---|
| S1 | Every result is traceable: raw trace, checksum, analysis version, calibration ID, firmware | **Software check** | `/api/scans`, `RawVoltammetryTrace`, PDF footer, `tests/test_v58_pipeline.py::TestScanEvidence` | Reprocessing with another calibration creates a new reading linked to the first; the first is never changed. |
| S2 | Readings survive a lost link | **Software check** (firmware host build + bridge tests) | firmware LittleFS ring buffer; `bridge_outbox.jsonl`; `tests/test_v58_bridge.py` | A disconnect/reconnect test on real hardware is still to be run and logged (item 45). |
| S3 | Only this computer, or a device with its key, can write | **Software check** | `deps.require_writer`, `SECURITY.md`, tests | Body size capped at 2 MB; rate limits; CORS limited to the dashboard origins. |
| S4 | Works 30 days unattended / on a 5 V solar supply | **Target** | ISEF list items 24, 39 | No energy budget has been measured. |
| S5 | Cost per test / per device | **Target** | ISEF list item 58 | No bill of materials with prices yet. |
| S6 | Autonomous sampling (pump, boat) | **Target** | item 38 | Present the handpump screening workflow; the boat is future work until paired data exist. |

## How to add a claim

Add a row before the claim appears anywhere else. Link the test (file, date, who ran it). When a target is met, change
its status and link the evidence; do not delete the old row, strike it through so the history stays visible.
