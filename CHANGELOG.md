# Changelog

## v5.3 — ESP32 hardening and the "field kit" dashboard
**ESP32 firmware (5.3.0)**
- **Offline buffer moved from NVS to LittleFS.** The old buffer promised 500 readings in NVS, but NVS is meant for small values (a blob costs 3+ entries), the default NVS partition is shared with Wi-Fi, and `putBytes` failures were never checked, so readings were silently lost after roughly a hundred. Now a fixed-size ring file (`/offline.bin`, 1,000 readings), formatted on first boot, with a RAM fallback if LittleFS cannot mount.
- **ESP32-S3 and ESP32-C3 support.** Pin profiles per chip that avoid flash/PSRAM pins, strapping pins and ADC2 (which stops working with Wi-Fi). The measurement task is no longer pinned to core 1 on single-core chips, where task creation would fail and nothing would be measured.
- **Setup without reflashing.** If Wi-Fi is not set or fails for 45 s, the board opens a WPA2 hotspot `AquaSentry-XXXX` (per-board password from the MAC, printed on Serial) with a setup page for Wi-Fi, server address, device name and API key, saved in flash. Measuring continues meanwhile. On the LAN the page needs the OTA login.
- `/status.json` and a status page (firmware, board, Wi-Fi RSSI, buffered/dropped readings, last result, free heap). Firmware version is sent with each reading and shown on the dashboard.
- `analogReadResolution(12)` set explicitly, long pump runs yield to other tasks, queue-full readings are counted instead of vanishing, `uint32_t` printf arguments cast for ESP-IDF 5 (where `uint32_t` is `unsigned long`), OTA needs an 8+ character password.
- `Firmware/platformio.ini` (esp32dev, esp32-s3, esp32-c3) for PlatformIO users.
- **Real ESP32 compile in CI**: new GitHub Actions job builds the sketch with Espressif's Arduino core for `esp32`, `esp32s3` and `esp32c3`. Locally, `Firmware/host_check/` stand-in headers let `python main.py --test` type-check the sketch for all three chips with `-Wall -Wextra -Werror` and link the C engines from C++.

**Server**
- `GET /api/devices`: every device with online / late / offline / demo status (from the hourly test interval), reading and unsafe counts, firmware version and latest result.
- `GET /api/readings/history`: compact arsenic history for charts, per device or all, by time window.

**Dashboard redesign ("field kit")**
- The hero is now the way an arsenic test is actually read: a printed **colour chart** (0 / 10 / 20 / 50 / 100 / 150 / 300 µg/L in test-strip colours) with "your water" placed on it, and verdict bands whose edges sit exactly on the 10, 20 and 150 µg/L swatches. The marker shows the colour the strip would turn.
- The verdict is a flat **painted panel** in the colours arsenic programmes paint on tube wells (green / ochre / red / maroon). "No arsenic detected" has its own blue-slate paint so it is never confused with a confirmed "safe".
- New **Devices and history** section: device list (click one to filter) with status and firmware, demo and imported sources folded away, and a history chart whose vertical scale is the same colour chart.
- Light paper theme is the default (readable outdoors on phones); the dark theme is restyled to match. Type: Anek (Ek Type, condensed widths, Latin + Devanagari, bundled offline) for headings and numbers, Mukta for body text. The ring gauge, scrolling facts strip, WebGL background, cursor effects and tilt are gone; the one animation left is the marker moving to the new reading (off with reduced motion). Contrast checked to WCAG AA for text on every paint.
- Applies to every page through a new `frontend/field.css` layer on top of `app.css`.

**Tests**: 167 (22 toolkit + 145 platform), including firmware type-checks for three chips, pin-safety rules, NVS name lengths, fleet/history API, every dashboard string present in English and Hindi, and the chart geometry.


## v5.2 — audit release: correct arsenic limit, honest verdicts, hardening
**Public-health correctness**
- **India's arsenic limit is 10 µg/L, not 50.** IS 10500:2012 originally allowed 0.05 mg/L "in the absence of an alternate source"; Amendment No. 1 (2015) removed that relaxation (CGWA's reply to the NGT in OA 538/2024 states the limit "was revised from 0.05 mg/L (50 ppb) to 0.01 mg/L (10 ppb) in the year 2015"). The whole stack used 50. Fixed in `standards.py`, `analytes.py`, the classification layer, all four AquaNet-V3 rule copies (server, `Neural_Network/`, browser `neural.js`, ESP32 `aquanet_v3.c` + its generator), PDF reports, the chat assistant's knowledge, the dashboard strip/gauge/standards table, and the docs.
- Because the sensor's LOD (20 µg/L) is already twice that limit, the rules are now: **≥ 20 µg/L (detected) → at least Unsafe**, **10–20 µg/L → Caution** (above the limit but not confirmable, lab test), **> 150 µg/L → Hazardous**. The network weights are unchanged; the rules only make verdicts stricter.
- **No more "Safe to drink" below the detection limit.** The dashboard now says **"No arsenic detected"** with a one-line ask for a lab test (English and Hindi). Previously 4.5 µg/L showed a large green "Safe to drink", while the server itself said "cannot confirm".
- Server and dashboard now agree for 10–20 µg/L (server said "Below LOD", dashboard said "Caution").
- Alerts fire on **every Unsafe/Hazardous verdict** (they used to need ≥ 50 µg/L, so 20–49 µg/L and pH/turbidity failures never alerted). `/api/alerts/recent` is built from the database, so alerts survive a restart; the webhook runs in a background thread instead of blocking the ESP32 upload.
- `scripts/reclassify_readings.py` re-applies the current rules to stored readings (preview, then `--apply` with a backup). Applied to the shipped `aquasentry.db`: 130 readings updated (105 were "Caution" at 20–50 µg/L).

**Bugs fixed**
- Real zeros were replaced by defaults (`x or default`): 0 NTU, 0 °C, 0 µS/cm and `arsenic_mg_l: 0` were classified as 2 NTU, 24 °C, 400 µS/cm and "use arsenic_ppb instead".
- CSV/JSON import matched column names by substring: `class`, `basin`, `measured_at` became arsenic, `recorded_at` became conductivity, `phosphate` became pH. Now whole-word matching shared by preview and commit, mg/L vs µg/L detection, sample times kept, zero arsenic accepted, duplicates inside one file caught, 20,000-row cap.
- The dashboard showed made-up pH/EC/turbidity/temperature (7.3, 420, 2.0, 25) for hardware readings that did not measure them. Now "–" / "Not measured"; typical values are used only for the model vote, as on the ESP32.
- API timestamps had no time zone; the dashboard's `detectedAt` showed UTC as if it were local time. All times are now explicit UTC; incoming sample times are converted to UTC and a device clock more than a day ahead is ignored.
- `/api/health`, PDF reports and the chat prompt named AquaNet-V1 while readings were classified by V3; the PDF recomputed confidence with V1. Now the stored model is used everywhere.
- Re-sent readings (idempotency hit) were re-classified with defaults instead of their stored values.
- The dashboard's "confirmed by other homes" query compared naive and aware datetimes.
- The default SQLite path was relative to the current folder, so starting the server elsewhere silently created an empty database.
- The chat endpoint was `async` but made a blocking Gemini call (froze the server while waiting) and returned raw exception text. Model is now configurable (`GEMINI_MODEL`).
- The voltammetry WebSocket crashed on non-numeric input.

**Security**
- Optional write protection: set `AQUASENTRY_API_KEY` and network clients must send `X-API-Key` to add readings, import or load demo data. The dashboard on the same computer keeps working without it. `/api/admin/db/compact` is never available to anonymous network clients. `/api/health` reports `write_auth`.

**ESP32 firmware**
- Sends `X-API-Key` (`DEVICE_API_KEY`), syncs its clock by NTP and sends `recorded_at`, so readings buffered offline keep their real time (they used to get the upload time).
- A reading the server rejects for good (4xx other than 408/429) is dropped with a log line. Before, one rejected reading blocked the whole offline buffer forever.
- Web OTA is disabled while `OTA_PASS` is still `change-me`.
- Adaptive re-scan edges are now 10 / 20 / 150 µg/L (the verdict edges) instead of 10 / 50 / 150.

**Tests and CI**
- 29 new tests in `tests/test_v52_regressions.py` (139 total): amended limit, zeros, import columns, auth, UTC times, alerts, WebSocket validation, and **cross-engine parity** of the safety rules (server Python ↔ `Neural_Network/` copy ↔ browser JS under Node ↔ ESP32 C compiled with gcc), plus a check that the firmware's upload JSON is valid and accepted by the API schema.
- CI: Python 3.10–3.13, Node syntax check of every dashboard script, gcc/g++ for the C parity tests.

**AquaNet-V3 retrained for the amended limit**
- `train_v3.py` now labels with the current edges (`AS_EDGES`, default 10 / 20 / 150 µg/L; `10,50,150` reproduces older models). New installed model `models/aquanet_v3_amd2015_balanced.json` (same 5-16-12-4 size, 352 parameters, 1.4 KB on the ESP32), installed with `install_aquanet_v3.py` into the server, dashboard, firmware and toolkit.
- Under the current rules (synthetic test sets, same seeds as before; `results/eval_v52_*.json`): the network's own vote matches the rules 98.6% of the time on exact readings (old model: 88.6%, because it was trained on the 50 µg/L edge). End to end with 3-scan sensor noise, dangerous samples missed fall from 2,198 to 2,039 out of 200,000 (−7%); with the firmware's adaptive re-scan, 1,761 → 1,565 (−11%). The price is about 7% more false alarms. No dangerous sample is ever called Safe.
- C engine vs Python on 100,000 inputs: 0 verdict mismatches (`results/c_vs_python_parity_100k.txt`).
- The previous model stays in `models/aquanet_v3_installed_balanced.json` if you want to compare.

**Known limits**: all accuracy figures are from simulated data; the model still needs checking against real lab-tested samples. The standalone V1 toolkit in `Neural_Network/` (hand-built weights) still encodes 50 µg/L as a historical reference; the server enforces the current limit on top of it.

## v5.1 — black & blue, more motion
- New colour scheme: deep blue-black background with electric blue, cyan and indigo accents (light theme updated to match). Safety colours (green/amber/orange/red) unchanged.
- New `frontend/motion.js` on every page: animated 3D dotted-wave background that ripples around the cursor, soft cursor light, sweeping light beam, scroll progress bar, word-by-word heading reveals, "decode" animation on the verdict title, magnetic buttons, parallax on hero visuals.
- More movement: animated gradient text and buttons, shimmering labels, orbiting particles and pulse ring around the arsenic gauge, scrolling facts strip, floating icons, card lift and glow, self-drawing section dividers, staggered card entrances, page-to-page fade transitions, rippling water floor under the 3D device model.
- Performance: removed expensive blur filters from moving layers (about 3–4× higher frame rate in testing). Reduced-motion users get a still version.

## v5 — new UI across every page
- **One design system for every page** (`frontend/app.css` + `frontend/shell.js`): carbon-black glass UI with aqua gradients, light theme, English/Hindi on every page, same sidebar, top bar and assistant everywhere.
- **Brought back from the original UI:** "What to do if arsenic is high" (4-step public-health protocol, filter options, health note), **Contact local authorities** (auto-filled incident report you can email, copy, share or print; directory: Gram Panchayat/VWSC, district water department, Jal Jeevan Mission Citizen Corner, CPGRAMS, 108/112; local contacts saved on the device), catamaran robot knowledge base, scientific disclosure, impact numbers, **market research graphs**, **sales graphs**, **ROI calculator**, competitor comparison, roadmap and the **device simulator**.
- **Effects:** WebGL water-caustics hero that changes colour with the verdict, animated gauge, glowing nav highlight, cursor spotlight cards, 3D tilt, number counters, scroll reveal, drawn-in charts, rotating dotted globe, and an **interactive 3D model of the real enclosure** (from `models_3d/*.stl`) with an exploded view. All offline, and turned down for users who prefer reduced motion.
- `market-research.html` and `sales-expansion.html` were broken (their style files no longer existed); both rebuilt. Chart.js from the internet replaced by a small offline chart library (`charts.js`).
- The device simulator (`website`, a file with no extension that the server downloaded instead of showing) is now `device-simulator.html`.
- Fixed: "Load demo data" with the server running looked for the wrong device and fell back to local demo data.
- AquaNet, firmware, server API and tests unchanged (110 tests pass).

## v4.1 — adaptive re-scanning on the ESP32
- The ESP32 takes 3 scans, then 3 more (up to 9) only while the arsenic reading is within 2 standard errors of 10 / 50 / 150 µg/L. Simulated overall accuracy 93.4% → 94.6%; dangerous samples missed 1,755 → 1,508 (out of 200,000); about 1.5× the average scan time instead of 3× for always doing 9 scans.
- 2 new tests check the firmware rule against the training code (110 tests).
- Training code can train and test with the same re-scan rule (`ADAPTIVE=1`, `eval_adaptive.py`). Eight more training runs did not beat the v4 network, so its weights are unchanged.

## v4 — AquaNet-V3, ESP32-ready, GitHub-ready
- **AquaNet-V3** is now the default model on the server, the dashboard and the ESP32. It reads arsenic on a log scale, was trained on readings with realistic sensor noise (3 scans averaged, like the firmware), and is weighted so it misses fewer Unsafe/Hazardous samples. Results: `Docs/AQUANET_V3_REPORT.md`. V1 is still available (`AQUANET_MODEL=v1`, or the V1 button on the dashboard).
- **ESP32:** the firmware runs V3 on the chip (`Firmware/esp32_firmware/aquanet_v3.c`, generated float32 C99, 352 weights = 1.4 KB, no `malloc`). Each reading now averages 3 voltammetry scans (`SCANS_PER_READING`).
- **Firmware moved to `Firmware/esp32_firmware/`** so the Arduino IDE opens it directly (a sketch must sit in a folder with the same name, and the `.c/.h` files must be beside it).
- New `scripts/install_aquanet_v3.py`: one command puts a trained model into the server, the dashboard and the firmware.
- New training code: `Neural_Network/v3_training/`.
- 7 new tests (108 in total at v4), including a C-vs-Python check of the ESP32 engine. CI also compiles the ESP32 engine.
- Repo hygiene: `.gitignore`, `.gitattributes`, no `.env` files, no API keys. `Docs/Canva.htm` (a saved Canva web page containing Canva's embedded Google API keys) is no longer included — GitHub would block the push.

## v3.1 — carbon black theme
- Dashboard defaults to a carbon-black dark theme; light mode still available from the moon button.

## v3 — error fixes
- All errors found in the original package fixed (firmware payload, voltammetry window, calibration, sensor stubs, OTA auth, PDF report, websocket, tests writing to the real database, and more). Full list with files and lines: `FIXES_v3.md`.

## v2 — new dashboard, Hindi, desktop app, AquaNet-V2
- Professional dashboard with English / हिन्दी switch, light and dark mode, offline fonts.
- Desktop app (`desktop_app.py`), VS Code launch settings, explainer video (`Docs/AquaSentry_Explained.mp4`).
- AquaNet-V2 trained on all five readings.
- Removed `.env` (it contained a live Gemini API key — revoke it).
