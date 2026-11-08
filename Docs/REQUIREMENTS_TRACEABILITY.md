# Requirements traceability

ISEF items 24, 25, 54: each design criterion as a measurable target → the test that proves it → the result. A
criterion with no test yet says **target**; nothing is claimed from a test that has not been run. Edit the numbers
in the "target" column to the team's own criteria (item 24); keep the test column honest.

## Criteria

| # | Criterion | Target (team to confirm) | Test that proves it | Result today |
|---|---|---|---|---|
| C1 | Detection limit | ≤ 10 µg/L (ideally ≤ 5) | ≥ 10 blanks: LOD = 3.3 σ/slope (`POST /api/qc/runs` blank; calibration endpoints) | **Target.** Strip specification 20 µg/L; not yet measured (`CLAIMS_REGISTER` M1) |
| C2 | Sensitivity at 10 µg/L vs ICP-MS | ≥ 90 % with lower CI bound stated | `Analysis/paired_validation.py` on ≥ 40 paired samples | **Target.** Tooling ready; no real pairs yet |
| C3 | Specificity at 10 µg/L | ≥ 80 % | same | **Target** |
| C4 | Result time | ≤ 15 min per test | Firmware `[TIMING] first result` + stopwatch for hands-on time | **Target.** Firmware reports the number; bench run needed |
| C5 | Measurement uncertainty known per reading | ± U (k = 2) on every result | `tests/test_v58_pipeline.py::TestScreeningOutcome`; coverage check in `paired_validation.py` | **Software done**; the 5 % calibration term is assumed until replicates give a value |
| C6 | No value from a bad scan | 100 % of malformed / saturated / shoulder-less scans rejected | `tests/test_v58_pipeline.py::TestPipelineRobustness` (7 fault classes) | **Pass** (software) |
| C7 | Browser and server agree | ≤ 0.05 µg/L difference on the same trace | `test_asv_js_matches_the_python_pipeline` (17 traces) | **Pass** |
| C8 | Traceability | every result → scan, checksum, calibration ID, firmware, analysis version | `TestScanEvidence`; PDF versions line (`test_certificate_names_every_version`) | **Pass** |
| C9 | Works without network | readings kept and delivered once when the link returns | Firmware LittleFS ring buffer; `tests/test_v58_bridge.py::test_outbox_survives_a_server_outage` | **Pass** (software); 3-day unplug test on a board still to log (item 183) |
| C10 | Unattended operation | ≥ 30 days | `/api/metrics` uptime; deployment (item 114) | **Target** |
| C11 | Power | runs on a 5 V solar supply; battery life ≥ N days | Power meter per mode (item 165) | **Target** |
| C12 | Cost | ≤ ₹ X per test, ≤ ₹ Y per device | `Analysis/project_figures.py cost` from receipts | **Target.** BOM template has no prices yet |
| C13 | Daily QC | 10 µg/L check standard at start and end of each field day within 80–120 % | `app/qc.py` gates; `Analysis/control_chart.py` | **Pass** (software) |
| C14 | No false reassurance | nothing below the LOD is ever called "safe to drink" | `tests/test_ui_safety_gates.py`, `test_v57_safety.py` | **Pass** |
| C15 | Local languages | alert and verdict text in EN, HI, BN, AS, PA | `tests/test_v56_ui.py` (every safety key present in every language) | **Pass** (strings machine-assisted; native-speaker check pending, item 196) |
| C16 | Accessibility | WCAG 2.1 AA on the dashboard | `tests_e2e` axe run | **Pass** |
| C17 | Security of the pilot | writes only from this computer or a keyed device; bodies ≤ 2 MB | `test_v57_safety.py`, `test_oversized_bodies_are_refused` | **Pass** |
| C18 | As(III) vs total arsenic stated | species on every result | `arsenic_species` on readings, PDF, public page | **Pass** (software); total-As recovery is lab work (item 66) |

## Constraints (item 25) and what the software does about each

| Constraint | Response |
|---|---|
| No laboratory skills at the source | One-button test; outcome in plain words in five languages; QR page per source; SOP in `Docs/SOP_MEASUREMENT.md` |
| No fridge; samples cannot be preserved | `SampleMeta.preservation` and `collection_to_analysis_min` recorded so hold-time effects can be analysed (item 82) |
| Unreliable power | Low-power firmware build, deep sleep, offline buffer; power budget still to measure (item 165) |
| Unreliable network | Ring buffer on the node, outbox in the bridge, idempotent uploads, service-worker-cached dashboard |
| Local languages | EN/HI/BN/AS/PA throughout |
| Hard water, iron and manganese | Interference tooling (`Analysis/interference.py`); matrix handled by standard addition and spike-recovery QC; chemistry results pending |
| Monsoon temperature range | Temperature logged per reading; correction after item 69; enclosure tests are hardware work |

Keep this file next to the poster's criteria panel; when a target is met, replace "Target" with the measured value,
its interval, n and the date.
