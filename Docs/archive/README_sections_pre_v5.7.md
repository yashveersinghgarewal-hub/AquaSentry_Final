# README sections retired in v5.7

These sections were in the top-level `README.md` up to v5.6. They were moved here word for word when the repository was reorganised (v5.7), so nothing is lost. The same release notes are in `CHANGELOG.md`; the current folder layout and run steps are in `README.md` and `Docs/HOW_TO_RUN.md`.

> Paths below are as they were before v5.7: `setup_and_run.*`, `run_all_tests.*` and `build_desktop_exe.bat` are now in `scripts/`; `IMPROVEMENT_LOG.md` is `Docs/IMPROVEMENT_LOG.md`; the Docs PDFs were removed (the Markdown files are the source; `AquaSentry_Platform/scripts/convert_all_md_to_pdf.py` makes PDFs again).

---

## What changed in v5.5

- **Alerts you can trust:** webhooks are signed (Standard Webhooks HMAC-SHA256) and retried on failure; low-battery notices for battery-powered nodes.
- **Monitoring:** `/api/metrics` in Prometheus format (readings, devices by status, alerts, webhook deliveries, request latency per route).
- **Faster, more honest trends:** hourly readings are reduced to daily medians before the Mann-Kendall test (hourly values are correlated and overstate trends); 90 days of hourly data takes 3 ms instead of 570 ms, and results are cached.
- **Chat works offline:** with no Gemini key or no internet, the assistant answers from your own readings, devices and trends.
- **ESP32 (firmware 5.5.0), all optional:** HTTPS with certificate checking, a battery monitor, and a low-power mode that deep-sleeps between tests.
- **Docker:** non-root, read-only container, database in a volume, health check; automatic protection against the SQLite WAL-reset bug on older SQLite builds.
- **GitHub:** lint in CI, ESP32 builds with the optional features on, Dependabot, security policy, PR and issue templates.

## What changed in v5.4

- **Backend:** per-device API keys, rate limiting, security headers with a hash-based Content-Security-Policy, SQLite tuning and online backups, live updates over Server-Sent Events, real CSV export, and an **arsenic trend early warning** (Mann-Kendall + Sen's slope) that flags a source getting worse before it crosses a limit.
- **Dashboard:** live indicator and toasts, a warnings list (rising arsenic, silent devices, unsafe readings), trend notes, accessible chart with a table view, offline mode.
- Every change since v5.1, with reasons and sources: **`IMPROVEMENT_LOG.md`**.

## What changed in v5.3

- **ESP32:** offline buffer moved to LittleFS (the NVS one silently overflowed), ESP32-S3 and ESP32-C3 support, a setup hotspot so Wi-Fi and the server address can be changed without reflashing, a `/status.json` page, and a CI job that compiles the firmware with Espressif's core for all three chips.
- **Dashboard:** redesigned around the arsenic test-kit colour chart, painted verdict panel, and a new Devices and history section backed by `/api/devices` and `/api/readings/history`. Details in `CHANGELOG.md`.

## What changed in v5.2 (audit release)

- **Arsenic limit corrected.** India's IS 10500 arsenic limit has been 10 µg/L with *no relaxation* since Amendment No. 1 (2015); the old 50 µg/L "permissible" value was withdrawn. Every engine (server, browser, ESP32 C, Neural_Network copy) now treats any arsenic the sensor detects (≥ 20 µg/L LOD) as at least **Unsafe**, 10–20 µg/L as **Caution** (unconfirmed, lab test), and > 150 µg/L as **Hazardous**. Alerts fire on every Unsafe/Hazardous verdict.
- **No more "Safe to drink" below the detection limit.** The sensor cannot see 10 µg/L, so a clean reading now says **"No arsenic detected"** and asks for one lab test.
- **Write protection** with `AQUASENTRY_API_KEY` (the ESP32 sends it as `X-API-Key`); admin endpoints are never open to the network.
- Fixes: real zeros (0 NTU, 0 °C) were replaced by defaults; CSV import read columns like `class` or `recorded_at` as arsenic/conductivity; timestamps lacked a time zone; the firmware retried a rejected reading forever and stamped offline readings with upload time; OTA accepted the default password; health/PDF named the wrong model.
- **AquaNet-V3 retrained** on the corrected edges: its own vote now matches the rules 98.6% of the time (was 88.6%), and with the firmware's adaptive re-scan it misses 11% fewer dangerous samples in simulation. Same 352-parameter size; C ↔ Python parity 0 mismatches on 100,000 inputs.
- `scripts/reclassify_readings.py` re-applies the current rules to stored readings.
- 29 new regression and cross-engine parity tests (Python ↔ browser JS ↔ ESP32 C). Details: `CHANGELOG.md`.


---

## 1. Package Directory Layout

When unzipped on any computer, this package contains everything organized into clear, dedicated directories:

```text
AquaSentry_Universal/
├── setup_and_run.sh            # 1-Click launcher for macOS & Linux (auto venv + pip + server)
├── setup_and_run.bat           # 1-Click launcher for Windows (auto venv + pip + server)
├── run_all_tests.sh            # 1-Click test runner for macOS & Linux (236 tests)
├── run_all_tests.bat           # 1-Click test runner for Windows
├── main.py                     # Root universal command-line interface
├── requirements.txt            # Unified project dependencies
├── Dockerfile                  # Production container image
├── docker-compose.yml          # One-click Docker container deployment
├── README.md                   # This documentation guide
├── README.pdf                  # Formatted PDF publication
│
├── AquaSentry_Platform/        # Universal Fullstack Web Application
│   ├── app/                    # FastAPI backend (WebSocket, PDF certs, alerts, WAL DB)
│   ├── frontend/               # Interactive PWA dashboard with real-time UI & manifest
│   ├── bridge/                 # ADS1115 / ESP32 serial bridge and microcontroller bindings
│   ├── tests/                  # 214 automated API, safety, parity, firmware and scientific tests
│   ├── aquasentry.db           # Pre-configured SQLite database (WAL mode enabled)
│   ├── main.py                 # Platform-specific runner
│   └── run_tests.py            # Platform test runner with auto-venv detection
│
├── Neural_Network/             # Standalone AquaNet-V1 Neural Toolkit
│   ├── aquanet_classifier.py   # Python inference with Shannon entropy & INT8 Q10 mode
│   ├── aquanet_neural.js       # Pure-JavaScript browser inference engine
│   ├── aquanet_v1.h            # C99 header (Float32 + INT8 fixed-point forward passes)
│   ├── aquanet_v1.c            # C99 embedded engine (zero dynamic malloc, 148 bytes ROM)
│   ├── aquanet_v1_weights.json # Canonical 112 weight and bias floating-point matrices
│   ├── asv_extractor.py        # Multi-analyte deconvolution (As, Cd, Pb, Cu) & standard addition
│   ├── test_aquanet_parity.py  # 22-point neural topology, INT8 & strict parity test suite
│   ├── main.py                 # Standalone ML CLI
│   └── AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.pdf
│
├── Firmware/                   # ESP32 Production Microcontroller Firmware
│   ├── esp32_firmware/         # Arduino sketch folder (open the .ino from here)
│   │   ├── esp32_firmware.ino  # FreeRTOS dual-core tasks, adaptive 3-9 scan averaging, NVS buffer, Web OTA
│   │   ├── aquanet_v3.h/.c     # AquaNet-V3 edge AI (generated float32 C99, 1.4 KB)
│   │   └── aquanet_v1.h/.c     # V1 engine (shared result type + entropy)
│   └── README.md               # Pinout diagram, flashing & OTA guide
│
├── models_3d/                  # 3D Print CAD Models (Watertight STLs & 3MF)
│   ├── aquasentry_shell_base_full_120mm.stl # 120x85mm full-fit electronics shell base
│   ├── aquasentry_shell_lid_full_120mm.stl  # Lid with 2.5mm overhang drip skirt & gasket groove
│   ├── aquasentry_tank_bracket.stl          # Rigid dual-clamp overhead water tank bracket
│   ├── aquasentry_sample_well_15ml.stl      # 15 mL fluidic reaction & sensor well
│   ├── aquasentry_suction_strainer.stl      # 100-mesh weighted intake suction strainer
│   ├── aquasentry_complete_slicer_plate_120mm.stl # All components on single 3D printer bed
│   ├── aquasentry_complete_slicer_plate_120mm.3mf # Multi-part slicer project with print settings
│   └── aquasentry_shell_3d_rendering.png    # High-resolution photorealistic CAD rendering
│
├── AI_Agent/                   # AI Water Quality Research Agent
│   ├── main.py                 # Research agent: Claude (Anthropic) or GPT (OpenAI), chosen by which API key is set
│   ├── tools.py                # Specialized search & toxicology query tools
│   └── requirements.txt        # Agent dependencies
│
├── Data/                       # Raw Analytical Datasets & Calibration Curves
│   ├── example_data.csv        # Standard 81-point ASV square-wave scan
│   ├── arsenic_voltammetry_example.csv
│   ├── voltammetry2_arsenic_example.csv
│   └── example_calibration.json# Slope and intercept calibration constants
│
├── Analysis/                   # Signal Processing & Trace Generators
│   ├── generate_arsenic_data.py# Synthetic voltammogram generation with noise models
│   └── mas_g1_arsenic_analysis.py # Historical baseline subtractor
│
└── Docs/                       # Complete Engineering Specifications & Blueprints
    ├── AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.pdf
    ├── CATAMARAN_PROTOTYPE_SPEC.pdf
    ├── PERSONAL_TANK_SENTRY_BLUEPRINT.pdf
    ├── AQUASENTRY_HOME_ASSEMBLY_MANUAL.pdf
    ├── AQUANET_RETRAINING_REPORT.pdf
    └── AQUANET_V1_STRESS_TEST_REPORT.pdf
```

---

## 2. Quick Start on Any New Computer

### macOS & Linux (1-Click)
In your terminal, navigate to the unzipped folder and run:
```bash
chmod +x setup_and_run.sh
./setup_and_run.sh
```
*What this does automatically:*
1. Detects system `python3`.
2. Creates an isolated local virtual environment (`.venv`).
3. Installs all required packages from `requirements.txt`.
4. Launches the AquaSentry web platform on `http://localhost:8000` and opens your browser.

### Windows (1-Click)
Simply double-click:
```bat
setup_and_run.bat
```
or from the Command Prompt:
```cmd
setup_and_run.bat
```

---

## 3. Universal Command-Line Interface (`main.py`)

The root `main.py` provides immediate access to all subsystems:

```bash
# 1. Start the interactive web dashboard and REST API
python3 main.py --serve --port 8000

# 2. Run the complete automated test suite (all 236 tests)
python3 main.py --test

# 3. Analyze raw ASV voltammetric scan CSV and classify water safety
python3 main.py --csv Data/example_data.csv

# 4. Supply specific geochemical field parameters along with CSV
python3 main.py --csv Data/example_data.csv --ph 7.4 --ec 450 --turb 1.8 --temp 25.0

# 5. Run standalone AquaNet-V1 neural network evaluation scenarios
python3 main.py --neural

# 6. Display system architecture topology and versions
python3 main.py --version
```

---

## 4. Running the Complete Test Suite

You can run all 236 tests across the entire platform in a single command:
```bash
./run_all_tests.sh
```
*Test Coverage Breakdown:*
* **22 Standalone Neural Parity Tests** ([`Neural_Network/test_aquanet_parity.py`](Neural_Network/test_aquanet_parity.py)):
  * Exact 23-node, 112-synapse topology verification.
  * Out-of-bounds (OOB) physical sensor fail-safes.
  * Multi-parameter WHO/BIS 10500 potability downgrades (pH, Turbidity, Conductivity).
  * Conservative precedence overrides for arsenic limits.
  * Numerical stability (softmax sum = 1.0, float64 scaling).
* **214 Platform Tests** ([`AquaSentry_Platform/run_tests.py`](AquaSentry_Platform/run_tests.py)):
  * REST API endpoints, health checks, reading ingestion, deduplication.
  * Signal processing (Savitzky-Golay filters, baseline tilt subtraction).
  * Chat policy prompt-injection filters & emergency toxicology gates.
  * Data export/import schema integrity.

---

