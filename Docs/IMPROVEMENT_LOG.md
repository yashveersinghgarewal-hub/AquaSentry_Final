# AquaSentry improvement log (v5.1 → v5.7)

Every change made to this repository since the v5.1 baseline (commit `667a469`, "black & blue UI with a motion layer"), with the reason for it, where it lives, and how it is tested. Newest release last, so it reads as a story; `CHANGELOG.md` has the short version.

| Release | Commit | Focus |
| --- | --- | --- |
| v5.1 | `667a469` | Baseline as received |
| v5.2 | `1ec3697` | Correct arsenic limit, honest verdicts, bug fixes, write protection, retrained AquaNet-V3 |
| v5.3 | `8fba1a6` | ESP32 hardening, device fleet API, "field kit" dashboard |
| v5.4 | `52eae72` | Backend hardening (keys, rate limits, CSP, backups), live updates, trend early warning, UI accessibility and offline mode |
| v5.5 | `d8c0c6e` | Signed + retried alerts, Prometheus metrics, faster and more honest trends, offline chat, optional HTTPS / battery / deep sleep on the ESP32, Docker and GitHub readiness, lint and accessibility audit |
| v5.6 | this release | Measurement honesty (As(III)-only, copper, calibration), lab confirmation, field tools (map, QR pages, JJM export), alerts to phones / WhatsApp / SMS, three more languages, migrations, browser tests |

Tests: **110 → 139 → 167 → 185 → 206 → 236** (22 neural toolkit + 214 platform), plus 9 browser tests. Run them with `python main.py --test`.

---

## Contents
1. [Baseline audit (what was found)](#1-baseline-audit-what-was-found)
2. [v5.2: correct limits, honest verdicts, fixes](#2-v52-correct-limits-honest-verdicts-fixes)
3. [v5.3: ESP32 hardening, fleet API, field-kit UI](#3-v53-esp32-hardening-fleet-api-field-kit-ui)
4. [v5.4: backend hardening, live data, trends, UX](#4-v54-backend-hardening-live-data-trends-ux)
4b. [v5.5: alerts, metrics, low-power ESP32, Docker, GitHub](#4b-v55-alerts-metrics-low-power-esp32-docker-github)
4c. [v5.6: can the reading be trusted, and who hears about it](#4c-v56-can-the-reading-be-trusted-and-who-hears-about-it)
4d. [v5.7: competition roadmap and repository clean-up](#4d-v57-competition-roadmap-and-repository-clean-up)
4e. [v5.7: harm review of v5.6 (safety fixes)](#4e-v57-harm-review-of-v56-safety-fixes)
5. [API reference: everything added or changed](#5-api-reference-everything-added-or-changed)
6. [Settings added](#6-settings-added)
7. [Upgrade notes (behaviour that changed)](#7-upgrade-notes-behaviour-that-changed)
8. [How each change is verified](#8-how-each-change-is-verified)
9. [Known limits and next steps](#9-known-limits-and-next-steps)
10. [Sources](#10-sources)

---

## 1. Baseline audit (what was found)

The v5.1 repository ran and its 110 tests passed. Reading the code, running the server and probing the API turned up these problems (all fixed below):

| Area | Problem | Why it mattered |
| --- | --- | --- |
| Standard | India's arsenic limit coded as 50 µg/L "permissible". IS 10500 Amendment No. 1 (2015) removed that relaxation; the limit is 10 µg/L. | 20–50 µg/L water was called "Caution, within BIS permissible", and alerts only fired at 50. |
| Honesty | The dashboard showed a large green **"Safe to drink"** for 4.5 µg/L, though the sensor cannot see below 20 µg/L. | It claimed something the device cannot measure. |
| Consistency | 10–20 µg/L: server said "Below LOD", dashboard said "Caution". | Two answers for one reading. |
| Bugs | `x or default` replaced real zeros (0 NTU, 0 °C, 0 µS/cm, `arsenic_mg_l: 0`) with defaults. | Wrong inputs to the model. |
| Bugs | CSV import matched columns by substring: `class` → arsenic, `recorded_at` → conductivity, `phosphate` → pH. | Silent data corruption on import. |
| Bugs | Timestamps had no time zone; the dashboard showed UTC as local time. | Wrong times in India (UTC+5:30). |
| Bugs | Health, PDF and chat said AquaNet-V1 while V3 classified readings; PDF recomputed confidence with V1. | Reports did not match the stored verdict. |
| Bugs | Export `format=csv` returned JSON. | Feature did not work. |
| Security | No authentication on writes or admin endpoints, while the ESP32 setup binds the server to `0.0.0.0`. | Anyone on the network could add readings or trigger alerts. |
| Firmware | One rejected reading (HTTP 4xx) blocked the offline queue forever; offline readings got the upload time; OTA accepted the default password. | Lost or mistimed data; easy firmware takeover. |
| Firmware | 500-reading offline buffer in NVS (checked in v5.3). | NVS fills after ~100 readings; writes failed silently. |
| Firmware | Measurement task pinned to core 1 (checked in v5.3). | Fails on the single-core ESP32-C3. |

---

## 2. v5.2: correct limits, honest verdicts, fixes

### 2.1 Arsenic limit corrected everywhere
- **Rule now:** below 10 µg/L → within limit; 10–20 µg/L → **Caution** (above the limit but below what the sensor can confirm; lab test); **≥ 20 µg/L (detected) → at least Unsafe**, because the detection limit is already twice the 10 µg/L limit; > 150 µg/L → Hazardous.
- Applied identically in all four copies of the safety rules: `AquaSentry_Platform/app/aquanet_v3.py`, `Neural_Network/aquanet_v3.py`, `frontend/neural.js`, `Firmware/esp32_firmware/aquanet_v3.c` (and its generator `scripts/gen_c_v3.py`).
- Also `app/standards.py` (`BIS_PERMISSIBLE_LIMIT_UG_L = 10`, old value kept only as `BIS_2012_SUPERSEDED_PERMISSIBLE_UG_L`), `app/analytes.py`, `app/classification.py` (precedence order fixed), PDF report text, the chat assistant's system prompt, dashboard strip/gauge/standards table, and the docs.
- Alerts fire on **every Unsafe/Hazardous verdict**, not only ≥ 50 µg/L.

### 2.2 Honest verdict below the detection limit
- "Safe to drink" is never shown when arsenic is below 20 µg/L; the dashboard says **"No arsenic detected"** and asks for one lab test (English and Hindi).

### 2.3 AquaNet-V3 retrained on the corrected edges
- `Neural_Network/v3_training/train_v3.py` labels with `AS_EDGES` (default `10,20,150`). New model `models/aquanet_v3_amd2015_balanced.json` (same 5-16-12-4 size, 352 parameters, 1.4 KB) installed into server, dashboard, firmware and toolkit with `install_aquanet_v3.py`.
- Simulated results (`results/eval_v52_*.json`): network vote agrees with the rules 98.6% (was 88.6%); end-to-end dangerous misses 2,198 → 2,039 at 3 scans (−7%), 1,761 → 1,565 with adaptive re-scan (−11%); about 7% more false alarms; no dangerous sample called Safe. C vs Python: 0 mismatches on 100,000 inputs.

### 2.4 Bug fixes
- Zero values kept (`_val()` helper); idempotent re-sends return the stored verdict.
- CSV/JSON import: whole-word column detection shared by preview and commit, mg/L vs µg/L detection, sample times kept, zero arsenic accepted, duplicates inside one file caught, 20,000-row cap.
- Timestamps returned as explicit UTC; incoming times converted to UTC; a device clock more than a day ahead is ignored.
- Health/PDF/chat name the model that classified each reading.
- Dashboard "confirmed by other homes" naive/aware datetime comparison fixed.
- Default SQLite path is absolute (starting the server from another folder used to create an empty database).
- Chat endpoint no longer blocks the event loop; error text not leaked; `GEMINI_MODEL` setting.
- WebSocket rejects non-numeric input instead of crashing.
- Hardware readings without pH/EC/turbidity/temperature show "Not measured" instead of invented values.

### 2.5 Security
- Optional `AQUASENTRY_API_KEY`: network clients must send `X-API-Key` for writes; the dashboard on the same computer works without it. Admin endpoints never open to anonymous network clients.

### 2.6 Firmware (v5.2 part)
- Sends `X-API-Key`; NTP clock and `recorded_at` on each reading; 4xx rejections dropped instead of blocking the queue; OTA disabled while the password is `change-me`; re-scan edges 10/20/150.

### 2.7 Data and tooling
- `scripts/reclassify_readings.py` re-applies the current rules to stored readings (preview, `--apply` with backup). Shipped `aquasentry.db`: 130 readings updated.
- CI on Python 3.10–3.13, Node syntax check of dashboard scripts.

---

## 3. v5.3: ESP32 hardening, fleet API, field-kit UI

### 3.1 Firmware 5.3.0 (`Firmware/esp32_firmware/esp32_firmware.ino`)
- **Offline buffer on LittleFS** (`/offline.bin`, 1,000 readings, checked writes, RAM fallback). NVS is for small settings, the default partition is shared with Wi-Fi, and `putBytes` failures were ignored.
- **ESP32, ESP32-S3, ESP32-C3** pin profiles avoiding flash/PSRAM pins, strapping pins and ADC2 (unusable with Wi-Fi); measurement task on core 0 on single-core chips.
- **Setup hotspot** `AquaSentry-XXXX` (WPA2, per-board password from the MAC) with `/setup` for Wi-Fi, server URL, device name and key, saved in flash. On the LAN it needs the OTA login.
- `/status.json` and a status page; firmware version sent with readings.
- `analogReadResolution(12)`, pump loops yield, queue-full readings counted, `uint32_t` printf casts for ESP-IDF 5, OTA password ≥ 8 characters.
- `Firmware/platformio.ini`; CI job compiling with Espressif's core for `esp32`, `esp32s3`, `esp32c3`; `Firmware/host_check/` stand-in headers so the test suite type-checks the sketch for all three chips with `-Werror`.

### 3.2 Server
- `GET /api/devices` (online / late / offline / demo) and `GET /api/readings/history`.

### 3.3 Dashboard redesign ("field kit")
- Hero = the arsenic **test-kit colour chart** (0/10/20/50/100/150/300 µg/L swatches) with "your water" placed on it; band edges sit exactly on 10, 20 and 150.
- Verdict as a flat **painted panel** (tube-well paint convention); "not detected" has its own blue-slate paint.
- **Devices and history** section; light paper theme by default; Anek + Mukta fonts bundled offline (Latin + Devanagari); decorative motion removed; WCAG AA contrast; `frontend/field.css` layer on every page.

---

## 4. v5.4: backend hardening, live data, trends, UX

### 4.1 Security (`app/security.py`)
- **Security headers** on every response: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: SAMEORIGIN`, `Cross-Origin-Opener-Policy: same-origin`, a restrictive `Permissions-Policy`, and `Cache-Control: no-store` on `/api/`.
- **Content-Security-Policy** for pages: scripts only from the server itself plus **SHA-256 hashes of the pages' own inline scripts**, computed at start-up (no `'unsafe-inline'` for scripts); `frame-ancestors 'self'` (the device simulator embeds the MAS-G1 screen), `object-src 'none'`, `connect-src 'self'`. The archived `legacy_v1/` pages get a looser policy of their own. Verified in a headless browser with zero CSP violations.
- **Rate limiting** per client IP (sliding window, in memory): readings 240/min, imports 20/min, chat 20/min, demo 10/min, admin 30/min, all configurable. Returns `429` with `Retry-After`; the firmware already treats 429 as "retry later".
- **Per-device API keys**: `POST /api/admin/devices/{code}/key` creates a random key (`aqs_…`), shown once, stored only as a SHA-256 hash; `DELETE` revokes it. A device with its own key must always use it, so nobody else can post as that device; the key also satisfies the global write check.
- **Input validation**: `device_code` pattern, `source_type` restricted to known values.
- CORS limited to the methods and headers the app uses; GZip for large responses; `X-Request-ID` (echoed if sent) and `Server-Timing` on every response.

### 4.2 Database (`app/database.py`, `app/models.py`)
- Per-connection SQLite settings: `busy_timeout=5000` (a writer waits instead of failing with "database is locked"), `foreign_keys=ON`, `synchronous=FULL`; WAL once at start-up; `pool_pre_ping`.
- Composite index `(device_id, recorded_at)` for per-device history and trends (created on existing databases too).
- `POST /api/admin/backup`: consistent copy with SQLite's online backup API into `AquaSentry_Platform/backups/` (git-ignored).
- `/api/health` reports SQLite version and whether it has the fix for the WAL-reset race (SQLite ≥ 3.51.3 or the 3.50.7 / 3.44.6 backports), uptime and live subscribers.

### 4.3 Live updates (`app/events.py`)
- `GET /api/events`: **Server-Sent Events** stream with `reading` (every stored reading) and `alert` (Unsafe/Hazardous) events, a heartbeat every 15 s and automatic browser reconnect. Thread-safe hand-off from the worker threads that store readings; bounded per-client queues; at most 100 subscribers.

### 4.4 Arsenic trend early warning (`app/trends.py`)
- **Mann-Kendall trend test** (tie-corrected) with **Sen's slope** per hardware device over 90 days, following groundwater-quality practice: non-detects (< 20 µg/L) set to the detection limit so sensor noise cannot fake a trend; significance at p < 0.10 with a non-zero slope; at least 6 readings.
- Straight-line projection to the next limit ("would reach 150 µg/L in about 95 days"), labelled as an estimate.
- `GET /api/devices/{code}/trend`, a `trend` summary in `GET /api/devices`, and `GET /api/devices/{code}` (status, trend, last 20 readings, verdict counts).
- `/api/alerts/recent` now also lists **rising-trend** and **silent-device** (offline) notices, not only single unsafe readings. Alert messages rewritten in plain language and include the device.

### 4.5 Export
- `GET /api/data/export?format=csv` returns real CSV (streamed, `Content-Disposition` download), with `device_code` filter and protection against spreadsheet formula injection (cells starting `=`, `+`, `-`, `@` are neutralised unless numeric). The dashboard's "Download CSV" uses it when the server is connected.

### 4.6 Dashboard UX (audited against the UI UX Pro Max guidelines)
The 21st.dev component service and the UI UX Pro Max skill were not installed in this session (21st needs your own API key; its components are React while this dashboard is plain JS). Instead, UI UX Pro Max's public guideline database was used as a checklist, together with the frontend-design skill. Changes:
- **Live**: "Live" indicator in the top bar, the device list and chart refresh on new readings, and a toast for new hardware readings and alerts (one polite status message, not a stream of announcements).
- **Warnings** list in Devices and history: rising arsenic, silent devices and unsafe readings, one line per device, trends first, each with an icon and words (never colour alone).
- **Trend note** above the chart for the selected device, in plain words (the p-value is in the tooltip, not the sentence).
- **Chart accessibility**: series differ by line style as well as colour, direct device labels, and **"Show these readings as a table"** as the data-table fallback.
- **Verdict chips** in the report and history tables show paint *and* words.
- **Focus not obscured**: `scroll-padding-top` so the sticky top bar never hides a focused heading; 44 px touch targets on phones; extra bottom space so the assistant button never covers content; offline devices drawn as a crossed ring instead of a red dot (offline is not "unsafe").
- **Offline mode**: a service worker (`frontend/sw.js`) caches pages and assets on first visit, network-first for pages and never caching `/api/`, so the dashboard opens without a connection on localhost, in the desktop app or over HTTPS. Manifest updated (name, colours, orientation).

---

## 4b. v5.5: alerts, metrics, low-power ESP32, Docker, GitHub

### Code quality and accessibility audit
- **ruff** with bug-finding rules only (`ruff.toml`: syntax errors, undefined names, redefinitions, unused variables, mutable defaults, `raise ... from`): every finding fixed (`raise HTTPException(...) from e` in the import endpoints, a local name that shadowed a function, unused imports). CI now runs `ruff check .`.
- **axe-core WCAG 2.2 AA** run in headless Chrome on the dashboard, device simulator, market research and sales pages, light and dark: it found skipped heading levels (`h4` straight after `h2`, 15 on the dashboard) and low-contrast text on the verdict badge and in dark mode. Fixed with real heading levels styled as before and adjusted colour tokens (dark `--safe #6FC896`, `--caution #EDB858`, `--unsafe #FF8E80`, `--haz #F59AA7`). Result: **0 violations** on all eight page/theme combinations.

### Alerts (server)
- **Why:** the alert webhook was an unsigned POST tried once. A receiver (SMS gateway, Slack relay, the panchayat's own server) could not tell a real Unsafe alert from a forged one, and a single network blip lost the alert.
- **What:** `app/webhooks.py` follows the Standard Webhooks spec used by Svix and others: `webhook-id` (the alert id, reused on retries so receivers de-duplicate), `webhook-timestamp`, and `webhook-signature: v1,<base64 HMAC-SHA256 of "id.timestamp.body">`. Secrets in the `whsec_<base64>` format work with the standard libraries; a plain string also works. Network errors, 408, 425, 429 and 5xx are retried after 1 s, 4 s and 16 s; other 4xx are not (they will not get better). Only `http(s)` URLs are accepted, because `urllib` would otherwise open `file://` targets. Delivery stays on a background thread so the ESP32's upload never waits.
- **Low battery:** a node whose latest reading reports `battery_pct` at or below `LOW_BATTERY_PCT` (15) gets a notice in `/api/alerts/recent`; device cards show the battery level (English and Hindi), and the warnings list ranks it after unsafe readings.

### Monitoring
- `GET /api/metrics` in the Prometheus text format, so Prometheus, Grafana Agent or Netdata can scrape it: readings by verdict and source, devices by status, alerts raised, webhook outcomes, trend-cache hits and misses, live connections, uptime, build info, and per-route request counts and latency histograms. Routes are recorded by **template** (`/api/devices/{device_code}`), never the raw path, so a scanner hitting random URLs cannot create unbounded series. `METRICS_PUBLIC=0` limits it to this computer and API-key holders.

### Trends: faster and more honest
- **Why:** a node that reports hourly sends 2,160 readings in 90 days. Mann-Kendall assumes independent values, but hourly readings of the same well are strongly correlated, which makes the test report significant trends that are not there (Hirsch & Slack 1984, USGS). The pair loops are also O(n²): 2.3 million pairs, about 570 ms per device on every `/api/devices` call.
- **What:** when a node reports more than once a day, the series is reduced to **daily medians** (weekly beyond 400 days), after non-detects are censored to the detection limit so sub-LOD noise cannot move a median. The response says how (`aggregation`, `readings`, and "daily medians of N readings" in the evidence line). 90 days of hourly data now takes about 3 ms. Results are also cached per device, keyed by reading count, newest reading id and the date, so a new or deleted reading always invalidates the entry.

### Chat that works without the internet
- **Why:** on a field laptop with no internet or no Gemini key, the assistant only said it was offline, and a Gemini error (quota, retired model, no network) gave an apology.
- **What:** `offline_answer()` answers the common questions from the database with fixed wording: the latest reading and its device, which nodes show a rising or falling trend, which nodes are offline, and the limits (10 µg/L legal, 20 µg/L sensor detection limit, lab test needed below it). It is used when no key is configured and as the fallback when Gemini fails. When Gemini is available, its prompt now also gets one status and trend line per node.

### Smaller server changes
- `X-Total-Count` header on `GET /api/readings` (exposed through CORS) so clients can page.
- `X-Request-ID` from clients is reduced to `[A-Za-z0-9._:-]`, 64 characters; otherwise a fresh id is generated.
- **SQLite WAL-reset bug guard.** The bug (SQLite 3.7.0 to 3.51.2, fixed in 3.51.3 and the 3.50.7 / 3.44.6 backports) can corrupt a WAL database when two connections write or checkpoint at the same instant. Debian and Ubuntu Python images ship SQLite 3.46, so on an unpatched build the server now keeps **one** database connection (`SQLITE_SINGLE_CONNECTION=auto`), which makes the race impossible. The load of a sensor network is tiny, and 40 parallel uploads to the container all succeeded with `PRAGMA integrity_check` = ok. `/api/health` reports `single_connection_mode`.

### ESP32 firmware 5.5.0 (all new features off by default)
- **HTTPS.** With an `https://` server address the node uses `WiFiClientSecure` and checks the certificate chain and host name against `ROOT_CA_PEM`. With no certificate it does not send at all (readings wait in the offline buffer) unless `ALLOW_INSECURE_TLS 1`, because an unchecked TLS connection cannot tell the real server from an impostor. The telemetry task stack went from 12 to 16 KB for the handshake.
- **Battery monitor.** A two-resistor divider on an ADC1 pin (`PIN_BATTERY_ADC`), read with the factory-calibrated `analogReadMilliVolts`, converted with a resting Li-ion curve, and measured before the pump loads the cell. Sent as `battery_pct` with each reading and shown on `/status.json`. The new record field fits in what was padding, so readings already in the LittleFS buffer stay readable (a host test checks the size), and records are now zeroed before they are written to flash.
- **Low-power mode** (`LOW_POWER_MODE 1`): after a test the node stays awake up to 90 s to upload it and any backlog, then deep-sleeps for the rest of the hour. It never sleeps while the setup hotspot is open. Before sleeping it parks the electrode at 0 mV, switches the A4988 off and holds its EN pin high through sleep (`gpio_hold_en`, plus `gpio_deep_sleep_hold_en` on C3 and S3); Pololu-style boards pull EN low, so a floating pin would power the motor all hour. The README asks for a 10 kΩ pull-up as well. The last result and a wake counter live in RTC memory.
- The options can be set as build flags (`#ifndef` guards); `platformio.ini` has an `esp32dev-lowpower` environment, the host check compiles the sketch with all options on for the three chips, and CI builds them with Espressif's core for ESP32 and ESP32-C3.

### Firmware build fix found by the first real CI run
- **Why:** the ESP32 compile job had never run on GitHub before this release. Its first run failed on every chip: `'asv_result_t' does not name a type`. When building a `.ino`, the Arduino IDE and arduino-cli write a prototype for every function just above the first function in the sketch (`arsenic_ug_from_peak`, line 180), which was above the structs. The local host check compiled the sketch as plain C++, so it never saw the inserted prototypes. This had been broken since v5.2, so anyone opening the sketch in the Arduino IDE would have hit it.
- **What:** `sensor_reading_t`, `asv_result_t` and `offline_header_t` moved to `Firmware/esp32_firmware/aquasentry_types.h`. A new host test inserts prototypes the way arduino-cli does and compiles the result; run on the old sketch it reproduces the exact CI error. The real compiler also warned about `++` on `volatile` counters (deprecated in C++20, which ESP32 core 3.x uses), so those are now plain assignments and the host checks compile as C++20 with `-Wvolatile -Werror`. The CI firmware job is pinned to Ubuntu 24.04 because `arduino/compile-sketches` installs Python 3.12.4, which has no build for the Ubuntu 26.04 image that `ubuntu-latest` now uses.

### Docker and GitHub
- **Dockerfile:** no compilers or curl (smaller, fewer CVEs), non-root user (uid 10001), works on a read-only root filesystem, database and backups in the `/data` volume, the demo database copied in on first start by `docker-entrypoint.sh`, and a Python health check. The old compose file stored the database inside the container (lost on rebuild) and mounted the repo's `Data` folder over the image's; it now uses a named volume, `no-new-privileges` and settings from `.env`. `.dockerignore` keeps `.git`, `.venv`, `Docs` and secrets out of the image. Built and run here: non-root, healthy, readings stored, integrity check ok.
- **GitHub:** CI badge; ruff step; `workflow_dispatch`; read-only token permissions; concurrency cancel; Dependabot for pip, GitHub Actions and Docker; `SECURITY.md` with a deployment checklist; pull-request and bug-report templates.

---

## 4c. v5.6: can the reading be trusted, and who hears about it

This round started from a research pass (web + code) that produced 19 findings; all 19 were acted on. The ones that need the physical world (a bench test with As(V) standards, WhatsApp / SMS accounts) are built and tested against stand-ins, and marked as such.

### 1. The sensor may miss half the arsenic (As(III) vs As(V))
- **Why:** groundwater carries arsenic as As(III) and As(V). On a gold electrode As(V) is electrochemically inactive; Metrohm's gold-electrode method reduces it in an acidic sulfamic / citric acid / KCl electrolyte before measuring total arsenic. The node pumped raw water and deposited at −1100 mV with no electrolyte, so it most likely saw As(III) only and could report "No arsenic detected" for unsafe water.
- **What:** the firmware reports what it can see (`arsenic_species`: `as3_only` without a reagent pump, `total` with one). An optional MOSFET-switched dosing pump (`PIN_REAGENT_PUMP`) adds the electrolyte **after** pH / conductivity / turbidity are read (it changes them), waits `REAGENT_MIX_MS`, then measures. The server turns `as3_only` into a quality flag and a plain-language caveat ("the real level can be higher; confirm with a lab test") on the dashboard, the QR page and the JJM export. The four verdict engines are untouched, so Python / JS / C parity holds.
- **Still to do in the real world:** bench-test dose, mixing time and deposition potential with As(V) standards; the lab-confirmation feature below is how the field answer gets measured.

### 2. Copper interference
- Copper strips near arsenic on gold and forms Cu-As intermetallics that suppress the arsenic peak. With `COPPER_CHECK` (default on) the sweep continues `COPPER_OFFSET_MV` past the arsenic window and measures the copper peak over a straight local baseline; the extension is kept out of the arsenic background fit (a host test checks both loops stop at the arsenic sweep). The server flags `copper_interference` when the copper peak is ≥ `COPPER_FLAG_RATIO` (3) × the arsenic peak (noise floor 0.05 µA).

### 3. The other sensors were stubs
- `read_ph()`, `read_conductivity()`, `read_turbidity()` and `read_temperature()` returned NAN. Now: 10 kΩ NTC thermistor (Beta equation, open / short detection), two-buffer pH calibration (the serial monitor prints the board's mV for it), DFRobot-style EC curve compensated to 25 °C with the measured temperature, SEN0189-style turbidity curve, all through the factory-calibrated `analogReadMilliVolts` on ADC1 pins. All optional (`-1` = not fitted). The suggested pins were checked against each board profile; the first suggestion (34 / 25 on ESP32) collided with the bubble sensor and the stepper and was corrected before release.

### 4. Calibration that matches the electrode and the water
- `POST /api/admin/calibrations/external` (≥ 3 standards: least squares, LOD = 3.3·s/slope, R² warning below 0.98) and `POST /api/admin/calibrations/standard-addition` (sample + ≥ 2 spikes in the real water: the x-intercept gives the sample concentration with its standard error, and the slope includes matrix effects). Per device or global; a new active calibration retires the old one. Nodes fetch `GET /api/devices/{code}/calibration` at start-up and daily (RTC-timed, so low-power nodes do not ask on every wake), sanity-check it (slope 0.05–50 µA per mg/L), keep it in flash and stamp each reading with a CRC of the calibration id, so a reading made before a calibration change is never credited to the new one. A test fits a synthetic 30 µg/L sample with a 0.6 slope and recovers both exactly.

### 5. Lab confirmation: the sensor's real record
- `models.LabResult` + `POST /api/lab-results` (ICP-MS, HG-AAS, GF-AAS, ICP-OES, field test kit; As(III) if speciated; NABL flag). Results without a reading id pair with the node's reading nearest in time (± 48 h).
- `GET /api/validation` leads with safety: of the samples the lab found above 10 µg/L, how many the node flagged (detected at ≥ 20 µg/L), the **missed** count, sensitivity with a Wilson 95% interval, false alarms; then bias, MAE, RMSE, node-vs-lab slope and R²; with speciation, the As(III) share and the node's recovery (which answers finding 1 with field data). The dashboard's Lab checks panel shows this in plain words and has an entry form; device cards and the QR page show the latest lab result.

### 6. Alerts that reach people
- `app/notify.py`: **Web Push** (VAPID keys generated once and stored next to the database; works on Android / desktop, and on iPhone 16.4+ from the Home Screen; 404 / 410 subscriptions switched off), **WhatsApp Cloud API** (approved utility template with 4 parameters: place, µg/L, verdict, what to do; about ₹0.145 per message in 2026, in-window utility messages no longer free from 1 October 2026), **SMS** (MSG91 flow, the template must be DLT-registered as TRAI requires; or Twilio). Messages in English or Hindi.
- Rules: only **hardware** readings notify people (demo loads never do); one message per subscriber per node per `ALERT_REPEAT_MIN` (6 h) unless the level rises; statistically rising trends reach subscribers who chose WARNING. The service worker shows the notification and opens the node's public page on tap. Tests run every rule with fake senders and check the exact WhatsApp / MSG91 request bodies.

### 7–10. Platform
- **Migrations:** Alembic with a v5.5 baseline and a v5.6 revision (idempotent, batch mode for SQLite). `init_db()` creates new databases at head, stamps and upgrades pre-migration databases (after the old column patches), and upgrades current ones; tested on the shipped database, a fresh one and a repeat start.
- **Structure:** `main.py` 2,000 → about 1,350 lines; shared helpers in `app/deps.py`; routers for science, reports, field, auth, alerts and firmware. Names tests used from `app.main` are re-exported.
- **Logging:** `app/logs.py`, text or JSON (`LOG_FORMAT=json`), every line tagged with the request's `X-Request-ID` (a context variable set by the middleware); alerts, webhook deliveries and notification failures are logged with device and event fields.
- **Read protection:** `AQUASENTRY_READ_KEY` guards GET / WebSocket / SSE for network clients. Allowed: this computer, the read or write key, a device key (so nodes can fetch calibration), or a signed 30-day HttpOnly SameSite=Strict cookie from `POST /api/auth/login`. Health, sign-in, QR pages and firmware downloads stay open. The dashboard asks for the key in a dialog.

### 11. Firmware updates from the server
- `POST /api/admin/firmware?board=&version=` stores a build (checks the 0xE9 ESP32 image magic, 4 MB cap) with MD5 / SHA-256 in a manifest; `GET /api/firmware/latest` answers 204 when the node is current; downloads carry `x-MD5`, which the ESP32's HTTPUpdate verifies before installing. With `PULL_OTA` the node checks daily, never during a test, over HTTPS if configured, and confirms the new build after its first successful upload (`esp_ota_mark_app_valid_cancel_rollback`). Flash and NVS encryption for nodes in public places is documented in `SECURITY.md` (it burns eFuses, so it stays a deliberate step).

### 12. Fitting into the government process
- `GET /api/data/export/jjm`: one row per sensor reading and per lab result with the location hierarchy, source type, test type (sensor / laboratory / field test kit), result in mg/L, 0.01 mg/L acceptable and permissible limit, status ("Not detected (below sensor detection limit; lab test needed)" for sensor non-detects) and QC remarks; UTF-8 with BOM for Excel and Indic place names. No public WQMIS upload API or template could be found, so the layout follows the public field list and asks users to confirm with their district laboratory.

### 13–18. Dashboard
- **Map** (Leaflet 1.9.4 bundled, BSD-2; OpenStreetMap tiles, `MAP_TILE_URL` to change), loaded only when the section is near the screen; circle markers in the test-kit colours; popups link to the QR page.
- **QR stickers:** `device.html?code=` is a public page in plain words (verdict, value, age, what to do, caveats, lab result, demo marker); `&sticker=1` prints a QR sticker (qrcode-generator 1.4.4, MIT, error correction M).
- **Bengali, Assamese and Punjabi** for the arsenic-belt states (West Bengal, Assam, Bihar, Punjab, …): a language menu replaces the two buttons; each file loads on demand; the safety-critical text (verdicts, what to do, warnings, reasons, readings, QR page, alerts, lab and map) is translated (206 strings each) and the rest falls back to English. A test checks coverage and that every `{placeholder}` matches English. Machine-assisted: a native-speaker review is still needed.
- **Chart:** with more than four sources the per-source lines made a tangle; it now shows the points plus one dashed "highest reading each day" line.
- **Strict style CSP:** the 28 `style=""` attributes became classes, template-built geometry is applied through the CSSOM (allowed by CSP), and the chart helper sets `style` through `cssText`. The dashboard and the QR page now get `style-src 'self'`; the older project pages keep their inline styles.
- **Lighter first load:** the 176 KB 3D model loads when its section approaches; extra languages and the map load on use; the service worker precaches the new pages and handles push.
- Fixed while testing: the devices grid was 429 px wide on a 390 px phone (grid items' min-content width), "1 lab results" wording, a missing disclosure arrow, English caveats on translated QR pages, and a low-contrast 3D hint.

### 19. Tests that open the pages
- `tests_e2e/` (Playwright): no console errors or CSP violations at 1440 px and 390 px, no sideways scrolling, one map marker per placed node (tiles answered locally, so tests never hit OpenStreetMap), device tools, the lab summary, all five languages and the remembered choice, the QR page and sticker, lazy 3D loading, and an axe-core WCAG 2.2 AA audit in both themes (0 violations). CI runs them plus Lighthouse in CI (advisory; local run: dashboard 96 / 100 / 100 / 100, QR page 100 across the board).

### A bug CI found
- GitHub's runners have SQLite 3.45, so the server ran in its single-connection mode (the WAL-reset guard from v5.5). `/api/health` then asked for a second connection while the request held the only one, waited 30 s and reported no schema revision. Health now reuses the request's session, the full suite was re-run in that mode (205 tests, 8 s), and CI now runs it on every push.
- The Docker smoke test then found a worse one in the same mode: upgrading an existing database at start-up held the only connection while the old column patches asked for another, so **the container never started**. The patches now run before the migration takes its connection; a test starts a fresh process on a copy of the shipped v5.5 database in both connection modes (it fails on the old code), and the image was rebuilt and checked: migrated to 0002, push key in `/data`, 30 parallel uploads, integrity check ok.

---

## 4d. v5.7: competition roadmap and repository clean-up

**Why:** the project is aimed at Regeneron ISEF (through IRIS). ISEF judges score the research problem (10), design and methodology (15), execution and testing (20), creativity and impact (20) and presentation (35, of which the interview is 25). The software already goes far beyond what those criteria reward; the gaps are evidence (real samples against a laboratory), the detection limit (20 µg/L, above the 10 µg/L limit) and paperwork that can disqualify a project.

- **`Docs/ISEF_ROADMAP.md`:** 267 items, each P0/P1/P2, with a "first 30 days" list. Sources: Society for Science judging criteria and Rules for All Projects (2026–27), the IRIS timeline, ISEF risk-assessment guidance, IIT Madras (Stockholm Junior Water Prize India).
- **Demo data that cannot be mistaken for field data:** `scripts/seed_field_demo.py` writes only to a separate database, prefixes every node with `DEMO-` and labels every reading *SIMULATED FIELD DEMO*. The validation panel deliberately includes a missed sample (a 14 µg/L lab result the sensor cannot see), so a demonstration shows the honest picture.
- **Clean-up rules used:** a file was deleted only if a byte-identical copy remains (checked with checksums) or it is a PDF render whose words are all in its Markdown source (checked by text extraction); anything with unique content was moved to `Docs/archive/` unchanged. Deliberate copies that let each part run alone (the C engine inside the Arduino sketch folder, the V3 weights inside the server, the example data) were kept and are now guarded by a test. `Docs/` keeps its capital D because a case-only rename breaks Git on Windows and macOS.
- **Verification:** 22 neural-toolkit tests, 216 platform tests (2 fewer parse checks because two unused scripts were removed, 4 new layout tests), 9 browser tests including the WCAG 2.2 AA audit, `ruff check .` clean.

## 4e. v5.7: harm review of v5.6 (safety fixes)

A review asked one question of every part: *could this make someone drink contaminated water, or send wrong
information to an authority?* v5.6 had already fixed the arsenic limit, the "Safe to drink" headline and the
As(III) blind spot. These were still open:

| # | Problem in v5.6 | Harm | Fix in v5.7 |
| --- | --- | --- | --- |
| 1 | Any scan with 10+ points was averaged; the server rejected only clipped scans | A dead, dry or disconnected electrode gives a flat line = 0 µg/L = "No arsenic detected" | Scan QC on the ESP32 and the server (flat, noise vs LOD, peak at window edge, clipping, scans disagree, < 2 good scans) → **Test failed** |
| 2 | Nothing checked the sensor between calibrations | A drifting electrode reads low, again looking clean | Check standards (`/qc` page, `POST /api/qc/runs`, 80–120 % recovery); low readings need one in the last 7 days and an electrode calibration ≤ 90 days old |
| 3 | Missing sensors were fed to the verdict as pH 7.2, 400 µS/cm, 2 NTU, 24 °C | Verdicts and messages implied checks that never happened | `None` = not measured in Python, JS and C; messages name what was not measured |
| 4 | Dashboard practice tests copied pH 7.3, battery 71 % and GPS 25.61°N 85.14°E; reports had no source line | A practice result could be emailed to a district office with an invented location | Practice tests measure arsenic only, under `SIM-DASHBOARD`; reports show the source and are blocked for practice / demo / failed tests; PDF stamped |
| 5 | Below-LOD values shown as numbers (e.g. 9.6 µg/L) and painted safe-green on the map, QR page and device list | Reads as "measured, under the limit" | "< 20", "Not detected: not confirmed safe", clear-blue paint |
| 6 | No warning when a device's last reading was old; buffered readings without a clock got the upload time | A dead device's last "not detected" stays on screen | 2-hour staleness warning; `time_source` stored; "time unknown" shown |
| 7 | Writes open to the whole network without a key; CORS `*` | Fake readings / alerts from any device, or from a web page via `localhost` | Local-only writes without a key, Origin check, CORS limited |
| 8 | Simulated alerts went to the webhook | False alarms at the receiving end | Only hardware / imported readings |
| 9 | Pages and chatbot claimed LoRa, GPS geotagging, "ready to deploy", accuracy without "simulated", facts about AccuSense | Misleading pitches and answers | Rewritten as planned features / design targets; competitor facts marked as public information only |
| 10 | PDF V3 confidence import pointed at a module that does not exist | Confidence silently missing | Fixed |

**Correction to the first harm review:** it said the BIS 50 µg/L "permissible" limit still applied. It does not:
IS 10500 Amendment No. 1 (June 2015) removed that relaxation, as v5.2 implemented. v5.7 keeps the 10 µg/L limit.

**Verified by:** `tests/test_v57_safety.py` (scan QC on synthetic traces; trust rules; Python / JS / C parity with missing
inputs; PDF text via pypdf; write lock; the sketch's own `execute_asv_cycle()` run on a simulated ADC with a healthy,
dead, noisy and shifted-peak electrode; offline record layout). The browser tests and WCAG 2.2 AA audit pass.

**Next real-world steps:** tune the QC thresholds on real scans; prepare a 50 µg/L check standard (and a blank) for
the weekly check; bench-test firmware 5.7.0 on a board.

---

## 5. API reference: everything added or changed

| Method | Path | Since | Notes |
| --- | --- | --- | --- |
| POST | `/api/readings` | changed v5.2–v5.4 | Write-protected; device key enforced if set; accepts `firmware_version`, `recorded_at` (UTC); validated `device_code` / `source_type`; publishes live events |
| GET | `/api/readings/history` | v5.3 | `device_code`, `hours`, `limit`; oldest first |
| GET | `/api/devices` | v5.3, trend v5.4 | Status, counts, firmware, latest, trend |
| GET | `/api/devices/{code}` | v5.4 | Detail + last 20 readings + verdict counts |
| GET | `/api/devices/{code}/trend` | v5.4 | Mann-Kendall + Sen's slope + projection |
| GET | `/api/events` | v5.4 | Server-Sent Events: `reading`, `alert` |
| GET | `/api/alerts/recent` | changed v5.2, v5.4 | From the database; includes trend and offline notices |
| GET | `/api/data/export` | changed v5.4 | `format=json|csv`, `device_code` |
| POST | `/api/data/import/preview`, `/commit` | changed v5.2 | Word-based column detection, units, times |
| POST | `/api/admin/devices/{code}/key` | v5.4 | Admin only; returns key once |
| DELETE | `/api/admin/devices/{code}/key` | v5.4 | Admin only |
| POST | `/api/admin/backup` | v5.4 | Admin only |
| POST | `/api/admin/db/compact` | changed v5.2 | Admin only |
| GET | `/api/health` | changed v5.2, v5.4, v5.5 | Model, standards, write auth, SQLite, single-connection mode, uptime, webhook status |
| GET | `/api/metrics` | v5.5 | Prometheus text format |
| GET | `/api/readings` | changed v5.5 | `X-Total-Count` header |
| POST | `/api/chat` | changed v5.5 | Grounded offline answers when Gemini is missing or fails |
| PUT | `/api/admin/devices/{code}/site` | v5.6 | Coordinates, state / district / block / panchayat / village, source kind |
| POST, GET | `/api/lab-results` | v5.6 | Lab confirmations, auto-paired with the nearest reading |
| DELETE | `/api/admin/lab-results/{id}` | v5.6 | Admin only |
| GET | `/api/validation` | v5.6 | Sensor vs lab: missed unsafe, sensitivity (95% CI), bias, As(III) share |
| POST | `/api/admin/calibrations/external`, `/standard-addition` | v5.6 | Admin only |
| GET | `/api/calibrations`, `/api/devices/{code}/calibration` | v5.6 | The second is what nodes fetch |
| GET | `/api/data/export/jjm` | v5.6 | Jal Jeevan Mission style CSV |
| GET | `/api/public/devices/{code}` | v5.6 | QR page data; always open (`PUBLIC_DEVICE_PAGES=0` to close) |
| GET | `/api/alerts/channels` | v5.6 | Which channels work, VAPID public key |
| POST | `/api/alerts/subscribe/webpush`, `/unsubscribe/webpush` | v5.6 | Browser push |
| POST, GET, DELETE | `/api/admin/alerts/subscriptions` | v5.6 | WhatsApp / SMS numbers (masked in lists) |
| POST | `/api/admin/alerts/test` | v5.6 | Test message to every subscriber |
| GET, POST | `/api/auth/status`, `/api/auth/login`, `/api/auth/logout` | v5.6 | Read protection sign-in |
| POST | `/api/admin/firmware` | v5.6 | Upload a build (raw body) |
| GET | `/api/firmware`, `/latest`, `/download/{board}/{version}` | v5.6 | Node updates, `x-MD5` header |
| POST | `/api/readings` | changed v5.6 | Accepts `arsenic_species`, `peak_current_ua`, `cu_peak_ua`, `calibration_ref`; stores `qc_flags` |

ESP32 node pages (v5.3): `/`, `/status.json` (v5.5 adds `https`, `battery_pct`, `battery_mv`, `low_power_mode`, `wake_count`), `/setup`, `/update`.

## 6. Settings added

| Setting | Where | Default | Purpose |
| --- | --- | --- | --- |
| `AQUASENTRY_API_KEY` | `.env` | empty | Global write key for network clients |
| `GEMINI_MODEL` | `.env` | `gemini-3.6-flash` | Chat model |
| `RATE_LIMIT_READINGS_PER_MIN`, `_IMPORT_`, `_CHAT_`, `_DEMO_`, `_ADMIN_` | `.env` | 240 / 20 / 20 / 10 / 30 | Per-IP limits (0 = off) |
| `DEVICE_EXPECTED_INTERVAL_MIN` | `.env` | 60 | Online / late / offline thresholds |
| `AQUASENTRY_BACKUP_DIR` | `.env` | `AquaSentry_Platform/backups` | Backup destination |
| `AS_EDGES` | training env | `10,20,150` | Arsenic class edges for retraining |
| `DEVICE_API_KEY` | firmware / setup page | empty | Global or per-device key |
| `OTA_PASS` | firmware | `change-me` (OTA off) | OTA and LAN setup login, 8+ characters |
| `ALERT_WEBHOOK_SECRET` | `.env` | empty | Sign alert webhooks (v5.5) |
| `ALERT_WEBHOOK_ATTEMPTS` | `.env` | 3 | Delivery attempts per alert |
| `METRICS_PUBLIC` | `.env` | 1 | 0 = metrics for this computer / key holders only |
| `LOW_BATTERY_PCT` | `.env` | 15 | Low-battery notice threshold |
| `SQLITE_SINGLE_CONNECTION` | `.env` | auto | One DB connection on SQLite without the WAL-reset fix |
| `ROOT_CA_PEM`, `ALLOW_INSECURE_TLS` | firmware | empty, 0 | HTTPS uploads |
| `PIN_BATTERY_ADC`, `BATTERY_DIVIDER` | firmware | -1, 2.0 | Battery monitor |
| `LOW_POWER_MODE`, `LOW_POWER_AWAKE_MS` | firmware | 0, 90000 | Deep sleep between tests |
| `AQUASENTRY_READ_KEY` | `.env` | empty | Read protection for network clients |
| `PUBLIC_DEVICE_PAGES` | `.env` | 1 | QR sticker pages |
| `LOG_FORMAT`, `LOG_LEVEL` | `.env` | text, INFO | JSON logs with request ids |
| `COPPER_FLAG_RATIO` | `.env` | 3 | Copper interference flag |
| `ALERT_REPEAT_MIN` | `.env` | 360 | Minimum gap between messages per subscriber and node |
| `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | `.env` | generated | Web push keys |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE`, `WHATSAPP_GRAPH_VERSION` | `.env` | empty, v21.0 | WhatsApp alerts |
| `SMS_PROVIDER`, `MSG91_*`, `TWILIO_*` | `.env` | empty | SMS alerts |
| `MAP_TILE_URL` | `.env` | OpenStreetMap | Dashboard map tiles (also added to the CSP) |
| `AQUASENTRY_DATA_DIR` | `.env` | next to the database | VAPID key and firmware builds |
| `PIN_REAGENT_PUMP`, `REAGENT_PUMP_MS`, `REAGENT_MIX_MS` | firmware | -1, 1500, 30000 | Total arsenic |
| `COPPER_CHECK`, `COPPER_OFFSET_MV` | firmware | 1, 250 | Copper scan |
| `PIN_TEMP_NTC`, `PIN_PH_ADC`, `PIN_EC_ADC`, `PIN_TURBIDITY_ADC` (+ calibration constants) | firmware | -1 | Water-quality sensors |
| `PULL_OTA`, `UPDATE_CHECK_HOURS`, `CALIBRATION_CHECK_HOURS` | firmware | 0, 24, 24 | Server updates and calibration |

## 7. Upgrade notes (behaviour that changed)

- **Verdicts for 20–50 µg/L changed from Caution to Unsafe** (the law changed in 2015). Run `python scripts/reclassify_readings.py --apply` on older databases.
- A device given its own key **must** send it, even from the same computer.
- `source_type` values outside `simulated, hardware, manual_import, synthetic_fixture, synthetic_demo` and device codes with spaces or symbols are rejected with 422.
- The dashboard opens in the light theme; the moon button still switches, and the choice is remembered.
- Old firmware's NVS buffer is not migrated to LittleFS; upload pending readings before flashing 5.3.0.
- v5.5: trends for nodes that report more than once a day are computed on daily medians, so `n` in the trend output counts days; `readings` has the raw count.
- v5.5: with an `https://` server address and no `ROOT_CA_PEM`, firmware 5.5.0 keeps readings in its buffer instead of sending them unchecked.
- v5.6: the database is migrated automatically on first start (Alembic); back it up first (`POST /api/admin/backup`).
- v5.6: firmware 5.6.0 converts buffered 5.2–5.5 readings to the new record format on first start.
- v5.6: nodes without a reagent pump now say their readings are As(III) only, and the dashboard shows a caveat. That is the honest state of the hardware, not a regression.

## 8. How each change is verified

| Test file | What it checks |
| --- | --- |
| `tests/test_v52_regressions.py` | Amended limit, zeros, import columns, auth, UTC, alerts, WebSocket, Python/JS/C rule parity, firmware JSON |
| `tests/test_firmware_host_build.py` | Sketch type-checks for 3 chips, C/C++ linkage, NVS names, LittleFS buffer, single-core, pin safety |
| `tests/test_v53_fleet.py` | Devices status, firmware version, history |
| `tests/test_v53_ui.py` | Every dashboard string in English and Hindi, chart geometry, scripts parse, field layer on all pages, service worker never caches the API |
| `tests/test_v54_backend.py` | Headers + CSP hash, request IDs, rate limit 429, device keys, Mann-Kendall maths, trend endpoint + alert, CSV export + injection guard, SSE delivery, backups, validation, health |
| `tests/test_v55_backend.py` | Webhook signature round trip, tampering, replay window, key rotation; retries only on transient errors; signed end-to-end delivery to a local receiver; metrics format and route templates; restricted metrics; `X-Total-Count`; request-ID sanitising; daily-median aggregation; trend cache hit and invalidation; offline and fallback chat; low-battery notice; single-connection guard |
| `tests/test_v56_field.py` | Quality flags, sites, lab pairing and validation (missed unsafe, CI), standard addition recovers a known sample, calibration activation and node fetch, JJM CSV, public page, read protection (cookie, tampering, expiry, middleware), schema revision, firmware upload / latest / download |
| `tests/test_v56_alerts.py` | Subscriptions, demo readings never notify, Hindi WhatsApp text, repeat suppression, per-device filters, gone push subscriptions switched off, WhatsApp / MSG91 request bodies, phone normalisation |
| `tests/test_v56_ui.py` | Bengali / Assamese / Punjabi coverage and placeholders, language menu, strict style CSP on the dashboard and QR page, service-worker cache list and push handler, vendored libraries |
| `tests_e2e/test_browser.py` | Real Chromium: errors, CSP, phone layout, map, languages, QR page, lazy 3D, WCAG 2.2 AA |
| `tests/test_firmware_host_build.py` (v5.5 additions) | Sketch compiled after Arduino-style prototype insertion, as C++20 with `-Wvolatile`; sketch with HTTPS, battery and deep sleep switched on for 3 chips; offline record size unchanged; battery curve monotonic; TLS never unchecked by default; deep sleep keeps the stepper off |
| `Neural_Network/v3_training/results/c_vs_python_parity_100k.txt` | C engine vs Python, 100,000 inputs |
| GitHub Actions `firmware` job | Real ESP32 compile for esp32, esp32s3, esp32c3, plus the optional features on esp32 and esp32c3 |
| GitHub Actions `ruff` step, local axe-core run | Lint clean; 0 WCAG 2.2 AA violations |

Manual checks done for each release: server started, every page loaded in headless Chrome at 1440 px and 390 px, light and dark, English and Hindi, with no console errors or CSP violations; a live reading posted while the page was open produced the toast and refreshed the device list; the service worker took control of the page.

## 9. Known limits and next steps

- All model accuracy figures come from **simulated** data. The next real step is a set of field samples tested by an accredited lab (ICP-MS or HG-AAS) to calibrate the sensor and validate the model.
- The ESP32 sketch has not been flashed to a board in this work; CI compiles it, but do one upload and a bench test before field use.
- Rate limits and live-event subscribers are per server process (fine for one laptop or Pi; use a shared store if you run several workers).
- Trend projections are straight-line estimates; aquifers can change faster around monsoon recharge.
- 21st.dev components could be used if the dashboard moves to React, or if you connect the 21st MCP with your key.
- Deep sleep, battery and HTTPS are compiled and type-checked but not yet bench-tested on a board; measure the real sleep current (development boards with USB chips and LEDs draw milliamps, not microamps).
- The Docker image uses Debian's SQLite 3.46 with the single-connection guard; a base image with SQLite 3.51.3+ would allow a normal connection pool.
- v5.6 needs the physical world next: a bench test of total-arsenic dosing with As(V) standards, a copper-standard scan to confirm the copper window, sensor calibration on real boards, and paired lab samples from the field (the validation endpoint is ready for them).
- WhatsApp and SMS sending are tested against stand-ins; real sending needs a Meta-approved template and an MSG91 DLT template (or Twilio).
- The Bengali, Assamese and Punjabi text is machine-assisted and should be reviewed by native speakers before field use.
- OpenStreetMap's tile servers are for light use; a large deployment should set `MAP_TILE_URL` to its own or a paid tile service.

## 10. Sources

- Bureau of Indian Standards limit change: CGWA reply to the NGT, OA 538/2024 (greentribunal.gov.in); Drishti IAS summary of the revision to 0.01 mg/L.
- Bullen et al. (2022), low-cost electrochemical arsenic detection with an open-source potentiostat, PLoS ONE (PMC8769315).
- Espressif documentation: Arduino-ESP32 2.x → 3.0 migration; Preferences (NVS) limits; ESP32 GPIO (strapping, flash, ADC2 with Wi-Fi); FreeRTOS on single-core ESP32-C3.
- arduino/compile-sketches usage for ESP32 (Arduino forum).
- Mann-Kendall and Sen's slope for groundwater quality trends, including non-detect handling and α = 0.1 (PMC7096367).
- SQLite concurrency: busy_timeout, WAL and the WAL-reset fix (oneuptime.com, 2026).
- HTTP security headers reference: CSP, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP, X-XSS-Protection deprecation (hidekazu-konishi.com).
- Standard Webhooks specification and Svix "Webhook security 101" (signature format, timestamps, retries).
- Hirsch & Slack (1984), *A nonparametric trend test for seasonal data with serial dependence*, USGS: serial correlation and Mann-Kendall.
- Prometheus exposition format 0.0.4 and label-cardinality guidance.
- SQLite WAL-reset bug: conditions and fixed versions (mjtsai.com, Aug 2026; sqlite.org release notes for 3.51.3).
- ESP-IDF GPIO hold in deep sleep (`gpio_hold_en`, `gpio_deep_sleep_hold_en`); Arduino-ESP32 `WiFiClientSecure` and `analogReadMilliVolts`.
- Arduino forum: A4988 carrier boards pull ENABLE low (driver on by default).
- axe-core rules for heading order and colour contrast (Deque).
- Metrohm technical poster: arsenic determination at the gold electrode (As(III) vs total, sulfamic / citric acid / KCl electrolyte, copper removal).
- Analytical Chemistry 1999 (Tufts): ASV arsenic sensor, Cu / Hg / Pb interference studies, standard addition.
- CGWB arsenic report and India Water Portal overview (affected states); Vikaspedia on WQMIS and LIMS (Jal Jeevan Mission).
- PWA Web Push on iOS in 2026 (webscraft.org) and MagicBell's iOS PWA guide; WhatsApp pricing changes (AiSensy, Oct 2026; Meta pricing docs); MSG91 v5 flow API.
- OneUptime, production-ready FastAPI (2026); Alembic documentation (batch mode for SQLite).
- UI UX Pro Max guideline database (github.com/nextlevelbuilder/ui-ux-pro-max-skill) and the 21st MCP README (github.com/21st-dev/magic-mcp).
