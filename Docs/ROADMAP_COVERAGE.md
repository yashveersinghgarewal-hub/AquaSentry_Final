# Roadmap coverage: what the software has done, what needs the bench and the field

Two documents guide the project: the **Research and Engineering Review** (8 Nov 2026, 60 targeted improvements) and
the **ISEF list** (`Docs/ISEF_ROADMAP.md`, 267 items). This page maps every software-closable item to the code and
tests that close it, and says plainly which items can only be closed with chemicals, a laboratory and real hardware.
A ✅ here means "the code and its test exist", never "the sensor has been shown to work".

## Research and Engineering Review (60 items)

### Measurement and safety

| # | Item | Status | Where |
|---|---|---|---|
| 01 | Choose one arsenic measurement | ✅ recorded, ⏳ lab | `arsenic_species` on every reading, PDF and dashboard say As(III) unless total was measured. Species recovery is lab work. |
| 02 | Qualify the assay around the target | ⏳ lab | Software reports LOD 20 µg/L as a specification (`Docs/CLAIMS_REGISTER.md` M1). |
| 03 | Secure matched reference results | ✅ data model, ⏳ lab | `POST /api/lab-results` with `sample_code`, `species`, `reporting_limit_ug_l`, `qualifier`; `Data/field/README.md`. |
| 04 | Replace the four safety labels | ✅ v5.8 | One **screening outcome** (invalid / not detected / retest / screen positive) with a guard band = expanded uncertainty; the BIS 50 µg/L relaxation was removed in v5.7. `classification.screening_outcome`, dashboard, device page, PDF. |
| 05 | Separate simulation from measured data | ✅ v5.7 + v5.8 | Modes: live / **recorded replay** / simulation / demo / import, badge on the dashboard; replay is real data (no demo stamp) but never a live alert; data age shown. |
| 06 | Correct every performance claim | ✅ v5.8 | Factory calibration labelled **synthetic example** everywhere (`CALIBRATION_PROVENANCE`); `Docs/CLAIMS_REGISTER.md`; chatbot prompt updated. |
| 07 | Supervised lab work | ⏳ people | Not software. |
| 08–10 | LOD/LOQ, interference, drift | ⏳ bench | Software side ready: check standards (v5.7), calibration records with IDs, `paired_validation.py`. |

### AquaNet V2 model design

| # | Item | Status | Where |
|---|---|---|---|
| 11 | Train on laboratory concentration | ✅ tooling | `Analysis/aquanet_v2_pipeline.py` uses `lab_ug_l` as target, joined by sample ID through the paired export. |
| 12 | Extract features that preserve signal | ✅ v5.8 | `PeakCharacteristics`: net height, potential, width, baseline slope, shoulder noise, secondary peaks; stored in `features_json` with each scan. |
| 13 | Keep chemical baselines in the study | ✅ tooling | Calibration-line baseline is model 1 in the pipeline; standard addition exists (`/api/admin/calibrations/standard-addition`). |
| 14 | Fit a small statistical baseline | ✅ tooling | Ridge and PLS with inner leave-one-site-out tuning. |
| 15 | Try a compact residual network | ✅ tooling | Residual MLP (numpy, early stopping on an inner site, kept only if it beats no-correction). |
| 16 | Test which inputs add signal | ◐ | Context features are in the pipeline; the waveform-only vs context-only ablation is a one-line change the team should run once data exist. |
| 17 | Small waveform CNN | ⏳ later | P2, after the learning curve supports it. |
| 18 | Calibrate measurement uncertainty | ✅ v5.8 | Split-conformal 90 % intervals with coverage in the pipeline; per-reading ± U (k = 2) on the node; "interval crosses the cutoff → retest". |
| 19 | Detect conditions outside training | ◐ | Malformed/odd-shape scans are rejected (`BASELINE_OUTLIERS`, `PEAK_SHIFTED`, secondary peaks); calibration age and check-standard age gate low readings (v5.7). Context range checks are a target. |
| 20 | Adaptive retesting | ◐ | Firmware re-scans near limits (v5.6) and the node reports **retest**; the budgeted replay study needs the blinded set. |

### Datasets and model evaluation

| # | Item | Status | Where |
|---|---|---|---|
| 21 | Primary paired dataset | ✅ v5.8 | Native scan stored with SHA-256, firmware, analysis version, calibration ID, QC, chemistry; `sample_code` links scan ↔ lab; `GET /api/data/export/paired`; `Data/field/paired_template.csv`. |
| 22–23 | Bench and field datasets | ⏳ lab/field | Templates and workflow in `Data/field/README.md`. |
| 24 | Group related samples before splitting | ✅ tooling | Pipeline splits by site only; stops below 4 sites / 40 pairs. |
| 25 | Blind the final comparison | ⏳ people | Rule written in `Data/field/README.md`; analysis version and calibration IDs are recorded so settings can be frozen. |
| 26 | Preserve censored data and units | ✅ v5.8 | `qualifier "<"`, `reporting_limit_ug_l`, `species` stored; censored rows count as "below" for decisions and are excluded from (or substituted in) regression with the count reported. |
| 27 | Public chemistry for strata | ⏳ team | Sources listed in the review; not software. |
| 28 | Waveform test library | ◐ | Synthetic faults are labelled software tests (`tests/test_v58_pipeline.py`, `test_v57_safety.py`); the public workbooks (Bullen, NIST, Warwick) still need to be downloaded and run through `parse_scan_csv` / the pipeline. |
| 29 | Report errors where decisions change | ✅ tooling | Near-cutoff band, Wilson intervals, rule-of-three note, false negatives/referrals in `paired_validation.py`. |
| 30 | Package the evidence for reruns | ✅ tooling | Data dictionary (`Data/field/README.md`), evaluation commands, `metrics.json` + per-model predictions; licences and access dates are for the team to add. |

### Sampling hardware and field reliability

| # | Item | Status | Where |
|---|---|---|---|
| 31 | Capture the reader's native trace | ✅ v5.8 | Firmware 5.8 uploads the last scan of every reading to `/api/scans`; the bridge accepts `TRACE_BEGIN … TRACE_END`, one-line `TRACE:` and CSV files; the dashboard **Replay a recorded scan** button imports one file with its sample ID and shows the stored trace. |
| 32–39 | Front end, pump/radio interference, fill volume, materials, carryover, hold time, endurance | ⏳ bench | Hardware work; firmware already stores QC per attempt (item 34's "store the failure with the attempted scan" is covered by `qc_status`/`qc_flags` per scan). |
| 40 | Test failure recovery | ◐ | Software: offline ring buffer, idempotent uploads, bridge outbox tests; the physical fault matrix is to be run. |

### Software and pilot operations

| # | Item | Status | Where |
|---|---|---|---|
| 41 | One measurement pipeline | ✅ v5.8 | `frontend/asv.js` is a checked port of `app/signal_processing.py`; parity test on 17 traces; the server result is used whenever reachable; `analysis_version` stored. |
| 42 | Reject malformed scans | ✅ v5.8 | `MALFORMED_TRACE`, `TOO_FEW_POINTS`, `NON_FINITE`, `INVALID_CALIBRATION`, `NONMONOTONIC_SWEEP`, `INSUFFICIENT_BASELINE`, `PARTIAL_WINDOW`, saturation; the reason is stored and no concentration is reported. A rejected scan is a failed test for **every** source type. |
| 43 | Standardise units and boundaries | ✅ v5.8 | µg/L internally; inference endpoint rejects negative, NaN and infinite values with a 422 (not a 500); tests at 19.9 / 20 / 20.1 and at the guard-band edges. |
| 44 | Version the path from scan to result | ✅ v5.8 | Checksum, firmware, analysis version, calibration ID with every scan; `POST /api/scans/{id}/reprocess?calibration_id=…&store=true` creates a **new** reading linked to the first; checksum verified before reprocessing. |
| 45 | Queue scans when the link drops | ✅ v5.8 | Bridge: durable `bridge_outbox.jsonl`, acknowledge only on 2xx, stable content-hash scan IDs, server uniqueness on `idempotency_key`; firmware: trace kept until stored, offline buffer. |
| 46 | Tie confirmations to the same source | ✅ v5.8 | `corroborating_devices`: other QC-passed hardware nodes within 2 km or the same village, last 24 h; UTC storage with local display (v5.7); stale readings marked. |
| 47 | Protect the field pilot | ✅ v5.7 + v5.8 | Device keys, write lock, CORS, rate limits, **2 MB body cap**, secrets in `.env`; invalid-key tests. Public exports still list device coordinates: round or withhold private wells before publishing. |
| 48 | Make the dashboard explain a decision | ✅ v5.8 | Raw / smoothed / baseline trace, peak, method range, QC reason, corroboration, data age, mode badge, outcome chip, ± U, **View stored scan**, calibration provenance note. |
| 49 | Map observed sites and gaps honestly | ◐ | Demo data has no coordinates (v5.7); a "sampled vs unknown" layer is a target. |
| 50 | Fresh install reproduces the demo | ✅ | Pinned `requirements.txt`, launchers, chatbot optional; replay tests (valid scan, bad scan, outage) in `tests/test_v58_bridge.py`. |

### Competition evidence and deployment

| # | Item | Status | Where |
|---|---|---|---|
| 51 | Choose one deployment | ⏳ team | Recommendation recorded in `Docs/CLAIMS_REGISTER.md` S6: handpump screening workflow. |
| 52–53 | Prior-work comparison, success criteria | ⏳ team | Templates: `paired_validation.py` metrics are the pre-registered comparison. |
| 54 | Three judge figures | ✅ tooling | `scatter.svg`, near-cutoff metrics, `referral_curve.svg` from the two analysis scripts; a raw failure trace is stored with every failed test. |
| 55 | Claim and evidence register | ✅ v5.8 | `Docs/CLAIMS_REGISTER.md`. |
| 56–60 | Workflow timing, replication, submissions | ⏳ team | Not software. |

## ISEF list (267 items): the software's share

Most of the 267 items are research, chemistry, documentation and presentation work that no code can do. The items
the software contributes to:

- **B 24–26, 30, 34**: measurable criteria and honest limits; the dashboard, PDF and chatbot state IS 10500 Amendment 1 (2015) and WHO 10 µg/L, and never call the device "AI-powered" as the problem statement.
- **D 53 (FMEA)**: the fault table is live in code: scan QC flags, check standards, calibration age, offline buffer, body limits; `Docs/IMPROVEMENT_LOG.md` §8 lists how each is verified.
- **E 75–76**: raw voltammograms are stored and viewable per reading; the peak-finding algorithm has fixtures (synthetic bumps, spikes, shifted peaks) — the ≥ 50 hand-measured scans remain to be collected.
- **F 88–92**: blanks and check standards (`/api/qc/runs`), calibration records printed on each result, factory calibration marked synthetic.
- **G–H (data analysis and statistics)**: `Analysis/paired_validation.py` (Deming, Bland–Altman, Wilson CIs, ROC, rule of three) and `Analysis/aquanet_v2_pipeline.py` (grouped CV, conformal intervals, referral curve).
- **K (software quality)**: the server tests, browser + accessibility tests, firmware host build for three chips, CI.

Everything else in the list is for the team's logbook, not this repository. The item-by-item status is `Docs/ISEF_ROADMAP_STATUS.md`; what is left is `Docs/REMAINING_WORK.md`.
