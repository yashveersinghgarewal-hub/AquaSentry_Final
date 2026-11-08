# Failure modes and effects (FMEA)

ISEF items 53 and 61: for each way the measurement can go wrong, how the device or the software detects it, what
the user sees, and which test proves the detection works. Severity: **H** = could produce a wrong "safe";
**M** = wrong or missing number but visibly so; **L** = inconvenience.

| Failure mode | Sev. | Detected by | What is reported | Proved by |
|---|---|---|---|---|
| Electrode fouled / passivated (small, broad or absent peak) | H | Scan QC: `FLAT_SIGNAL`, `LOW_SNR`, `PEAK_TOO_WIDE`; check standard reads low (< 80 %) | **Test failed**, "clean or replace the electrode"; the day's low readings are not trusted without a passing check standard | `tests/test_v57_safety.py`, `test_v58_pipeline.py` |
| Bubble in the cell / no contact | H | Bubble sensor (firmware) + `FLAT_SIGNAL` / `TOO_FEW_POINTS` | Test failed, retry prompted | firmware host build; scan QC tests |
| Saturated current (range too low, short) | M | `SATURATED` flag (clipped samples) | Test failed; no concentration | `TestPipelineRobustness` |
| Peak shifted (wrong reference, different species, copper overlap) | H | `PEAK_SHIFTED`, `secondary_peaks`, `BASELINE_OUTLIERS`; copper check scan | Warning or failure depending on severity; evidence stored for review | copper-bump and shifted-peak tests |
| Wrong or stale calibration | H | Calibration age > 90 days, invalid slope (`INVALID_CALIBRATION`), check-standard recovery outside 80–120 %, LOD floor | Low readings not trusted; "recalibrate" message; certificate names the calibration ID | `test_v57_safety.py`, `test_v58_pipeline.py` |
| Interference biases the value upward (Cu, Fe) | M | Spike-recovery QC outside 80–120 %; `Analysis/interference.py` | "Use standard addition for this source" | `test_v59_roadmap.py::TestQcRunTypes` |
| Pump failure / wrong volume | M | Bubble sensor, scan QC; fluidics tests (hardware, item 167) | Test failed | firmware |
| Low battery / brown-out | M | Battery ADC, brown-out reset counter in `/status.json`; readings carry `battery_pct` | Low-battery warning on the dashboard; readings buffered | firmware; `/api/devices` |
| Wi-Fi / server loss | L | HTTP failure → LittleFS ring buffer; bridge outbox | Nothing lost; readings arrive once with their original time; "stale" badge on the dashboard | `test_v58_bridge.py`, firmware tests |
| Clock not set on the node | M | `time_source` = server_receipt / unknown | Certificate says the time is the server's receipt time | `test_v56_field.py` |
| Replayed or simulated data mistaken for live | H | `source_type` on every reading; mode badge; demo data never alerts or enters reports | "Simulation / Recorded replay / Demo" badge | `test_v57_safety.py`, `test_v58_pipeline.py` |
| Malformed upload (jumbled sweep, NaN, mismatched arrays, huge body) | M | Schema validation; `NONMONOTONIC_SWEEP`, `NON_FINITE`, `MALFORMED_TRACE`; 2 MB cap | 422 / 413, or a failed test with the reason stored | `test_v58_pipeline.py` |
| Tampered stored scan | M | SHA-256 checksum verified before reprocessing | 409; original value untouched | `TestScanEvidence` |
| Unauthorised writes | M | Write lock (local only or device key), CORS, rate limits | 401 / 429 | `test_v57_safety.py` |
| Network model tries to call unsafe water safe | H | Hard safety rules wrap the model; rules can tighten, never relax | Rule verdict wins | `test_aquanet_v3.py`, `aquanet_v3_field_eval.py` |
| Auxiliary sensor drift (pH, EC, turbidity, temperature) | L | Sensor checks against standards (`ph_buffer`, …); `sensor_checks.verified` | Values shown as unverified until checked | `test_v59_roadmap.py` |

## Safety by design (item 61)

- Low voltage only (3.3 V logic, 5 V supply); sealed electronics; no exposed mains.
- No arsenic at the booth: a dummy cell (resistor network) drives the demonstration.
- Waste: the sample well and rinse volumes are small (15 mL); collect, label and hand to a licensed route — write the
  chemistry part of this list with your supervisor (section O).
- Software never invents a value: a failed scan is a failed test; a missing sensor is "not measured"; demo data is
  labelled and kept out of alerts and reports.
- Every result is traceable to its scan, calibration, firmware and analysis version.
