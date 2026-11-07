# AquaSentry v3 — every fix, with file and line

> Note (v4): file paths below are as they were in v3. In v4 the ESP32 files moved into `Firmware/esp32_firmware/` so the Arduino IDE can open the sketch directly. See `CHANGELOG.md`.

**Use `AquaSentry_v3.zip`.** It replaces v2. Line numbers below are for the v3 files. The issue numbers (#1–#22) match the error list given earlier. Two problems were found while fixing and are marked "new".

**Checked before release:**
- All 101 tests pass (22 neural + 79 platform).
- The shipped `aquasentry.db` is byte-for-byte unchanged after running the tests.
- The C engine compiles with `-Wall -Wextra -Werror`.
- The firmware compiles against stand-in Arduino libraries, and its new measurement code was run on simulated scans. 0, 10, 35, 60, 120 and 300 µg/L came back as 1, 10, 37, 60, 121 and 299 µg/L.
- **Not done here:** flashing a real ESP32. That needs the ESP32 toolchain, which couldn't be downloaded in this environment.

## Server — `AquaSentry_Platform/app/main.py`

| # | Lines | Was | Now |
| --- | --- | --- | --- |
| 2 | 1264–1310 | With no readings, the PDF made up "Safe", 98.5% confidence, pH 7.4, etc. | Returns **404 "No reading found"**. Only stored values are printed; a missing sensor shows "Not measured". |
| 3 | 177–333 | Titled "LABORATORY WATER CERTIFICATE", printed "SHA-256 Validated" (no hash was calculated), always listed Cd/Pb/Cu as "Below Detectable Limit", claimed a calibration check that never happens, and used sensor confidence as "AI confidence". | Titled "**Water Screening Report**", with "not an accredited laboratory certificate" under the title. A **real SHA-256** of the printed values is shown. No made-up metal results. Model confidence and uncertainty are recalculated from the reading. Below 20 µg/L it says a lab test is needed. Uses the Vera font that ships with ReportLab, so "µ" prints (it was blank before). Long cells wrap. |
| 12 | 1247–1248 | WebSocket read `peak.net_current_ua` / `peak.potential_mv`, which don't exist, so it crashed at the end of every scan. | Uses `net_peak_height_ua` / `peak_potential_mv`. |
| 13 | 1228 | Passed mg/L into a function that expects µg/L (1000× too small). | Multiplies by 1000. Checked: 60 µg/L in → 60.3 µg/L out. |
| 8 | 1132 | Chatbot was told V1 was "trained with Adam on 8,000 samples, 99.7%". | Told the truth: V1 is hand-built from the arsenic limits; V2 is trained (99.6% on synthetic test data). |
| 6 | 102 | Health check reported `AquaNet-V1-Adam`. | `AquaNet-V1`. |
| — | 39–40 | — | Imports the calibration constants that the report prints. |

## Firmware — `Firmware/esp32_firmware.ino` (706 lines)

| # | Lines | Was | Now |
| --- | --- | --- | --- |
| 4 | 351–366, 411, 534 | Sent `arsenic_ppm` and `tds_ppm` with no `device_code`, so every upload was rejected (HTTP 422). | `build_reading_json()` sends `device_code`, `arsenic_concentration_mg_l` and `source_type:"hardware"`, plus an `idempotency_key` so re-sent readings aren't stored twice. Checked against the server: accepted (200) and stored as hardware data. |
| ESP32 | 50–61 | Placeholder Wi-Fi/IP with no explanation. | One clearly marked **CHANGE THESE BEFORE FLASHING** block (Wi-Fi, server URL, `DEVICE_CODE`, OTA login), with how to start the server. |
| ESP32 | 63–82 | Deposited at −0.8 V and swept from −800 to +300 mV, starting on top of the arsenic peak. | Deposit −1.1 V, sweep −1100 → −500 mV. Peak centre, search window, background exclusion and calibration are `#define`s matching `app/standards.py`. |
| ESP32 | 259–332 | Took the largest raw current between −400 and −100 mV: wrong place, no smoothing, no background removal. | `execute_asv_cycle()` records every point, smooths it (5-point Savitzky-Golay), fits and subtracts the background, then finds the peak between −860 and −740 mV. It returns the net peak, the peak position and the signal-to-noise ratio. |
| ESP32 | 612–614 | `arsenic = peak / 28.5` | `arsenic = (peak − 0.0096) / 0.8563`, the same as the server. |
| ESP32 | 335–338, 597–605 | pH 7.4, conductivity 580, turbidity 1.8 and temperature 24.5 were hard-coded and uploaded as if measured. | `read_ph()` etc. return NAN until you wire a sensor. NAN values are **not uploaded**. The on-device AquaNet uses typical values for them, for its local estimate only. |
| 21 | 218–219 | `0x84` set the ADC to continuous mode, but the comment said single-shot. | `0x85` (true single-shot). |
| new | 375–383 | When the 500-reading offline buffer was full, the oldest reading was overwritten but the read pointer didn't move. | The read pointer now moves too. |
| new | 451, 468, 474 | Anyone on the Wi-Fi could upload new firmware at `/update`. | Requires the `OTA_USER` / `OTA_PASS` login. |
| — | 341–348 | — | Reading counter kept in flash, using its own handle so the two tasks don't clash. |

`Firmware/README.md` is rewritten: setup, starting the server for the ESP32, the exact data sent, the measurement steps, and a Serial Monitor troubleshooting table.

## Neural network claims

| # | File | Lines | Change |
| --- | --- | --- | --- |
| 6 | `AquaSentry_Platform/app/neural_classifier.py` and `Neural_Network/aquanet_classifier.py` (identical) | 13–19, 53, 278–279, 479 | "Trained with Adam, 99.70% / 100%" is replaced by "hand-constructed from the arsenic thresholds; only arsenic affects V1; see V2". The accuracy text still contains "Synthetic", as the tests require. |
| 7 | `Neural_Network/aquanet_v1_weights.json`, `AquaSentry_Platform/app/aquanet_v1_weights.json` | `metadata` | Replaced "Adam / 8000 samples / 99.70%" with how V1 was made and which inputs it uses. |
| 6 | `Neural_Network/main.py` (lines 6, 18), `AquaSentry_Platform/main.py` (line 27) | | Banner text corrected. |
| 6 | `Neural_Network/aquanet_neural.js` | 256 | Provenance text corrected. |
| 6 | `Docs/AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.md`, `Neural_Network/` copy, `Docs/AQUANET_RETRAINING_REPORT.md` | top | Correction note added. The PDF versions of these documents are unchanged. |

## Signal processing

| # | File | Lines | Change |
| --- | --- | --- | --- |
| 15 | `AquaSentry_Platform/app/asv_extractor.py` and `Neural_Network/asv_extractor.py` (identical) | 7, 48, 114–115, 159, 227–236 | The peak window was −850…−740 mV centred on −795. It is now −860…−740 mV centred on −800, the same as `app/standards.py`. Results on the sample files are unchanged (the peak is at −800 mV). |

## Scripts — `AquaSentry_Platform/scripts/`

| # | File | Change |
| --- | --- | --- |
| 14 | `sync_neural_network.py` | **Rewritten.** It used the missing `AquaSentry_Complete_System` folder. It would also have overwritten the 22-test neural test file with an older 18-test version, replaced `aquanet_neural.js` with an incompatible file, and written the false "Adam 99.7%" metadata. It now copies only the classifier, the signal extractor and the C engine (to `Firmware/`), and writes honest metadata. Tested on a copy: the test file is left untouched. |
| 14 | `train_and_deploy_aquanet_v2.py` | Lines 18–24: correct folders, plus a note that it only fine-tunes the hand-built weights. Lines 233–260: writes to `app/neural_classifier.py` and `Neural_Network/aquanet_classifier.py`, matches both the old and new comment, and reports "not found" instead of silently doing nothing. Does not touch the new dashboard. |
| 14 | `aquanet_stress_test_benchmark.py` | Line 27: correct folder. Line 35: the report goes to the package `Docs/` folder. The mirror copy to a missing folder is removed. |

## Tests and the database

| # | File | Change |
| --- | --- | --- |
| new | `AquaSentry_Platform/tests/conftest.py` (new file) | Tests used to write test readings into the real `aquasentry.db` you ship. They now use a temporary database. |

## Text, paths and tools

| # | File | Lines | Change |
| --- | --- | --- | --- |
| 16 | `main.py` | 10, 130 | "97 tests" → "101 tests" |
| 17 | `README.md` | 121, 141, 146 | 97 → 101 tests; "18 Standalone" → "22" |
| 17 | `START_HERE_OPERATIONS_GUIDE.md` | 130–131, 151 | Same corrections |
| 18 | `main.py`, `AquaSentry_Platform/run_tests.py` | candidate list | Removed the original author's Mac path. `README.md` links now point to files in the package. |
| 19 | `AI_Agent/main.py` | whole file | Uses Claude or OpenAI, depending on which key is in `AI_Agent/.env`. Default models are `claude-sonnet-5-5` and `gpt-4o`; change them with `AGENT_MODEL`. Handles both answer formats, and gives a clear message if there's no key. New `AI_Agent/.env.example`. |
| 19 | `README.md` | 62 | Description of the agent corrected. |
| 20 | `AquaSentry_Platform/bridge/serial_bridge.py` | 9–13 | No longer points to the missing Arduino sketch. Explains the line format and that the ESP32 doesn't need the bridge. |
| — | `AquaSentry_Platform/QUICK_START.txt` | folder list | Correct folder name, test counts and contents |
| — | `AquaSentry_Platform/frontend/i18n.js` | 204–205, 414–415 | "PDF certificate" → "PDF screening report" (English and Hindi) |

## ESP32 connection (desktop app)

| File | Change |
| --- | --- |
| `desktop_app.py` (lines 79–87, 104–118) | New `--lan` option. It listens on your Wi-Fi on port 8000 and prints the exact `BACKEND_API_URL` to put in the firmware. |
| `Start AquaSentry for ESP32.bat` (new) | Double-click to start in that mode. |
| `.vscode/launch.json` | New launch option: "Network mode for ESP32". |

## Duplicates removed (#22)

Each of these was either identical to the copy that is kept, or an older version of it. Nothing loaded them; the tests confirm nothing broke.

- `AquaSentry_Platform/neural_network/` (older copy of `Neural_Network/`)
- `AquaSentry_Platform/analysis/` (identical to `Analysis/`)
- `AquaSentry_Platform/docs/` (older subset of `Docs/`)
- `AquaSentry_Platform/asv_extractor.py` (older), `legacy_asv_regressor.py`, `aquanet_v1.c/.h`, `aquanet_v1_weights.json`
- `AquaSentry_Platform/bridge/aquanet_v1.c/.h`
- `Neural_Network/aquanet_v1.o` (build output)

Kept on purpose: `AquaSentry_Platform/data/` (the tests use it), `Firmware/aquanet_v1.c/.h` (Arduino needs them next to the sketch), and `frontend/legacy_v1/` (the old design, for reference).

## Not changed

The API routes, the database contents, the AquaNet-V1 weights, the tests, the dashboard design, the data files, the 3D models, and the PDF documents in `Docs/`.

**#1 (API key):** the key file was already removed in v2. You still need to cancel that key in Google AI Studio.
