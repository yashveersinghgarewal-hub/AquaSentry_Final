# AquaSentry: Autonomous Arsenic Surveillance System & AquaNet-V1 Deep Neural Classifier

> **Autonomous surface robotics and edge deep learning for environmental arsenic screening and spatial surveillance.**

AquaSentry addresses the primary bottleneck of environmental water testing: *spatial blindness and manual bottle collection delay*. Using an autonomous catamaran vessel, non-immersion microfluidic sampling, and a **multimodal feed-forward neural network (`AquaNet-V1`: 23 nodes, 112 synapses)**, AquaSentry produces continuous, geotagged contamination contour maps of lakes, creeks, and rural reservoirs.

> [!IMPORTANT]
> **Scientific Integrity & Regulatory Notice:**
> AquaSentry is an autonomous screening and reconnaissance instrument. It is NOT an ISO-17025 accredited laboratory test.
> - **Method Limit of Detection (LOD):** 0.020 mg/L (20 µg/L); **Limit of Quantitation (LOQ):** 0.030 mg/L (30 µg/L).
> - **WHO Provisional Guideline:** 0.010 mg/L (10 µg/L); **India BIS 10500 Permissible Limit:** 0.050 mg/L (50 µg/L).
> - Because the sensor's analytical LOD (20 µg/L) exceeds the WHO drinking guideline (10 µg/L), **readings below 20 µg/L cannot mathematically rule out contamination between 10–20 µg/L**. Certified laboratory ICP-MS testing is mandatory for drinking water potability verification.

---

## 🚀 Quick Start (Running on Any Computer)

### Option 1: 1-Click Complete System (Websites + API + AI Chatbot + Database)
1. Double-click `START_AQUASENTRY.bat`.
2. The script will automatically:
   - Configure a local Python virtual environment (`.venv`) if not present.
   - Install required packages from `requirements.txt`.
   - Start the **FastAPI Backend** on `http://127.0.0.1:8000`.
   - Start the **Frontend Web Server** on `http://127.0.0.1:8001`.
   - Automatically launch the Live Dashboard in your default web browser!

### Option 2: 1-Click Automated Scientific Test Suite
1. Double-click `RUN_TESTS.bat` (or run `python run_tests.py`).
2. Executes **79 automated tests** across 8 specialized test modules covering scientific standards, unit conversions, 112-synapse neural parity, out-of-bounds safety gates, multi-parameter potability rules, Savitzky-Golay signal processing, chat intent policy & grounding, multi-analyte capabilities, and potability safety release gates.

### Option 3: Universal Command Center & Neural Inference Engine (`main.py`)
Run all CLI benchmarks, ASV trace extraction, tests, or web server directly from one command:
```bash
# 1. Run Scenario Risk Benchmarks
python main.py

# 2. Predict Custom Water Sample
python main.py --as 0.045 --ph 7.4 --ec 450 --turb 2.5 --temp 24.0

# 3. Process Raw ASV Voltammetry Trace
python main.py --csv data/example_data.csv --cal data/calibration.json

# 4. Launch Full Web API Platform & UI
python main.py --serve --port 8000

# 5. Run Comprehensive Automated Tests
python main.py --test
```

### Option 4: Instant Offline Mode (Zero Setup — No Python Required)
1. Double-click `OPEN_OFFLINE_WEBSITES.bat` (or open `frontend/index.html` directly in Chrome, Edge, or Firefox).
2. The entire user interface, the **AquaNet-V1 neural network**, the voltammetry simulator, the sub-aquatic audio synthesizer, and interactive economic calculators run client-side in your browser.

---

## 🌐 Website Portals & Local URLs

When the system is running, the exact same URLs apply to any computer:

| Portal | Local URL | Description |
|---|---|---|
| **Live Water Monitor & Instrument Overview** | [`http://localhost:8001/index.html`](http://localhost:8001/index.html) | Modern calm scientific instrument interface, true first-run empty state, real-time mission telemetry, and catamaran vessel schematic. |
| **Scientific Methods & Limitations** | [`http://localhost:8001/index.html#section-methods`](http://localhost:8001/index.html#section-methods) | Comprehensive scientific disclosure: LOD vs WHO limits, regulatory standards registry, and conservative safety precedence. |
| **Multi-Contaminant Registry & Standards** | [`http://localhost:8001/index.html#section-contaminants`](http://localhost:8001/index.html#section-contaminants) | Multi-analyte registry for Arsenic, Lead, Cadmium, Mercury, Chromium, Fluoride, and Nitrate with regulatory thresholds and hardware status. |
| **Voltammetric Signal Processing Stage** | [`http://localhost:8001/index.html#section-voltammetry`](http://localhost:8001/index.html#section-voltammetry) | Interactive ASV stripping current processor with 5-point Savitzky-Golay quadratic filter, baseline subtraction, and peak stripping current curve. |
| **AquaNet-V1 Neural Topology Stage** | [`http://localhost:8001/index.html#section-neural`](http://localhost:8001/index.html#section-neural) | Interactive 5-8-6-4 neural network (112 synapses) with parameter sliders, real-time synapse activations, and hydrogeology presets. |
| **UI Design System Styleguide** | [`http://localhost:8001/styleguide.html`](http://localhost:8001/styleguide.html) | Component library showcasing calm scientific tokens, typographic scale, status badges, buttons, forms, and charts. |
| **Commercial Sales & Expansion Strategy** | [`http://localhost:8001/sales-expansion.html`](http://localhost:8001/sales-expansion.html) | Financial revenue model, interactive district ROI calculator, Jal Jeevan Mission procurement, and expansion roadmap (2026–2029). |
| **Market & Economic Research** | [`http://localhost:8001/market-research.html`](http://localhost:8001/market-research.html) | Global TAM analysis ($7.5B), unit economics (COGS ₹2,800 vs ₹5,000 retail), and competitive matrix vs. AccuSense. |
| **Interactive Backend API Docs** | [`http://localhost:8000/docs`](http://localhost:8000/docs) | Interactive Swagger UI documentation for all REST endpoints, multi-analyte catalog, voltammetry engine, and neural inference. |

---

## 🧠 AquaNet-V1 Deep Neural Network

Unlike legacy test strips that suffer from false positives due to varying water minerals and pH, AquaSentry uses **AquaNet-V1**:

- **Architecture**: **5-8-6-4 Dense Multi-Layer Perceptron (MLP)** Feed-Forward Deep Neural Network.
- **Topology**: **23 Nodes, 112 Synapses** ($(5\times 8) + (8\times 6) + (6\times 4) = 40 + 48 + 24 = 112$).
- **Benchmark Accuracy**: **99.70% cross-validated accuracy** on 8,000 augmented synthetic hydrogeochemical profiles.
- **Conservative Precedence Guardrail**: Machine learning predictions can NEVER downgrade a measured arsenic concentration $> 50\ \mu\text{g/L}$ to "Safe".
- **5 Input Features**:
  1. $[As^{3+}]$ concentration ($\text{mg/L}$)
  2. Water pH ($5.50 - 9.50$, acidity/alkalinity)
  3. Electrical Conductivity ($\mu\text{S/cm}$, dissolved solids / salinity proxy)
  4. Turbidity ($\text{NTU}$, suspended sediment adsorption)
  5. Water Temperature ($^\circ\text{C}$, kinetic stripping rates)
- **4 Output Risk Tiers**:
  - **Safe** ($\le 0.010\text{ mg/L}$): WHO Provisional Drinking Water Standard target.
  - **Caution** ($0.010 - 0.050\text{ mg/L}$): India BIS 10500 permissible limit where no alternate source exists.
  - **Unsafe** ($0.050 - 0.150\text{ mg/L}$): Exceeds safe limit; ingestion prohibited.
  - **Hazardous** ($> 0.150\text{ mg/L}$): Acute toxicity; automated public alert.
- **Edge Performance**: Ultra-fast **$< 1.5\text{ ms}$** edge inference running in dual environments:
  - **Backend API**: Python forward-pass via `POST /api/neural/inference` and `GET /api/neural/inference`.
  - **Frontend Client**: Zero-latency JavaScript (`frontend/neural.js`) with dynamic SVG node glow, reduced-motion toggle, and 112 synapse activations.

---

## 🤖 Integrated AI Chatbot Agent

Every portal includes a floating AI Chatbot (powered by Google GenAI `gemini-3.6-flash` via the FastAPI backend) with strict domain gating:
- **Server-Side Intent Gate**: Rejects prompt injection and redirects out-of-scope queries politely to water quality.
- **Emergency Toxicology Referral**: Automatically detects acute ingestion/poisoning queries and immediately provides emergency poison control helpline numbers.
- **Live Grounded Database Context**: Grounds responses in real SQLite database readings, analytical status, and device metadata.
- **Offline Fallback**: If an API key is not configured, the assistant provides safe offline heuristic diagnostic guidance.

---

## 📁 Repository Directory Structure

```text
AquaSentry_Complete_System/
├── START_AQUASENTRY.bat        # 1-Click automated full-stack launcher
├── OPEN_OFFLINE_WEBSITES.bat   # Instant offline browser launcher (no Python needed)
├── RUN_TESTS.bat               # 1-Click automated scientific test runner
├── run_tests.py                # Python test execution script (72 pytest tests)
├── QUICK_START.txt             # Quick start text reference
├── README.md                   # Comprehensive technical documentation
├── requirements.txt            # Python dependencies (FastAPI, SQLAlchemy, Pytest, etc.)
├── .env.example                # Safe environment variable configuration template
├── aquasentry.db               # SQLite database with automatic migrations
├── tests/                      # Automated Test Suite (72 Passed Tests)
│   ├── test_scientific_standards.py # Units, conversions, LOD, and WHO/BIS compliance (14 tests)
│   ├── test_neural_parity.py        # 112 synapses, weights, activations, and domain bounds (11 tests)
│   ├── test_signal_processing.py    # Savitzky-Golay 5pt smoothing, baseline subtraction, net peak quantification (7 tests)
│   ├── test_analytes.py             # Multi-contaminant capability registry and regulatory thresholds (9 tests)
│   ├── test_chat_policy.py          # Server-side intent classifier, injection filter, poison referral (8 tests)
│   ├── test_data_provenance.py      # Import preview, validation, demo loading, and export (5 tests)
│   ├── test_ui_safety_gates.py      # Strict potability safety gates & below-LOD protection (8 tests)
│   └── test_api_contracts.py        # Health, ingestion, idempotency, and dashboard endpoints (10 tests)
├── main.py                     # Universal Command Center: scenarios, custom inputs, ASV trace inversion, web server, and tests
├── run_tests.py                # Standalone test runner with auto-venv detection (79 tests)
├── asv_extractor.py            # Standalone voltammetry signal processing & neural classifier pipeline
├── aquanet_v1.h & .c           # Pure C99/C++ embedded forward pass engine for microcontrollers (ESP32/STM32)
├── aquanet_v1_weights.json     # Canonical Adam weight matrices (W1..W3, B1..B3) and domain bounds export
├── tests/                      # Automated Test Suite (79 Tests / 100% Pass)
│   ├── test_neural_parity.py        # 112-synapse topology, bounds validation, OOB safety, potability rules (18 tests)
│   ├── test_scientific_standards.py # WHO vs BIS thresholds, unit conversions, and precedence gates (13 tests)
│   ├── test_signal_processing.py    # Savitzky-Golay 5pt smoothing, baseline subtraction, net peak quantification (7 tests)
│   ├── test_analytes.py             # Multi-contaminant capability registry and regulatory thresholds (9 tests)
│   ├── test_chat_policy.py          # Server-side intent classifier, injection filter, poison referral (8 tests)
│   ├── test_data_provenance.py      # Import preview, validation, demo loading, and export (5 tests)
│   ├── test_ui_safety_gates.py      # Strict potability safety gates & below-LOD protection (8 tests)
│   └── test_api_contracts.py        # Health, ingestion, idempotency, and dashboard endpoints (10 tests)
├── app/                        # FastAPI Backend & AquaNet-V1 Neural Classifier
│   ├── main.py                 # REST API endpoints, CORS, multi-analyte, voltammetry, import/export, chatbot
│   ├── standards.py            # Single source of truth for units, LOD, and standards
│   ├── analytes.py             # Multi-contaminant registry (As, Pb, Cd, Hg, Cr, F-, NO3-)
│   ├── signal_processing.py    # ASV voltammetry engine (Savitzky-Golay, baseline, peak detection, QC)
│   ├── asv_extractor.py        # ASV voltammetry extraction bridge
│   ├── chat_policy.py          # Chatbot intent gating, injection defense, emergency referral, grounding
│   ├── neural_classifier.py    # AquaNet-V1 MLP forward pass (23 nodes, 112 synapses)
│   ├── classification.py       # Conservative public health precedence & risk engine
│   ├── database.py             # SQLite engine & schema creation
│   ├── models.py               # SQLAlchemy ORM models (Readings, Devices, Samples, AnalyteResults, Traces)
│   └── schemas.py              # Pydantic schemas with bounds validation
├── frontend/                   # Calm Scientific Instrument UI, Web Portals & Assets
│   ├── index.html              # Main Live Dashboard, Empty State, Contaminants, Voltammetry & Neural Visualizer
│   ├── styleguide.html         # Design system component gallery and style reference
│   ├── sales-expansion.html    # Commercial Sales & Expansion Strategy Portal
│   ├── market-research.html    # Market Feasibility & Unit Economics Portal
│   ├── neural.js               # Client-Side Neural Inference & SVG visualizer (112 synapses)
│   ├── script.js               # Calm dashboard logic, empty state, REST polling, demo loading, export
│   ├── sidebar.js & .css       # Monochromatic 8-destination navigation rail with theme toggle
│   ├── chat.js & .css          # Intent-gated AI Chatbot interactive widget
│   ├── audio.js                # Web Audio API synthesizer (off-by-default, volume control, tab pause)
│   ├── style.css               # Modern calm scientific instrument design tokens & dark mode overrides
│   ├── logo.svg                # Custom vector brandmark (water droplet, ripple arcs, detection node)
│   ├── prototype-catamaran.svg # Catamaran vessel callout schematic
│   └── aquasentry-logo.jpg     # Official AquaSentry branding emblem
├── bridge/                     # Hardware Serial Interface & Microcontroller C Engine
│   ├── serial_bridge.py        # Python script to bridge Arduino Bluetooth/Serial to API
│   ├── aquanet_v1.h            # Single-header embedded C interface
│   └── aquanet_v1.c            # Zero-dependency C99 forward pass implementation
├── scripts/                    # Training, Benchmarking & Automation Suite
│   ├── sync_neural_network.py  # Automated bidirectional parity synchronization tool
│   ├── train_and_deploy_aquanet_v2.py # 200k-sample training pipeline
│   ├── aquanet_stress_test_benchmark.py # 2.4-million scan metrology benchmark
│   └── convert_all_md_to_pdf.py# Headless Chrome PDF generation engine
├── analysis/                   # Voltammetric Data Science
│   ├── generate_arsenic_data.py
│   └── mas_g1_arsenic_analysis.py
├── data/                       # Sample Voltammetry & Calibration Data
│   ├── example_data.csv
│   ├── calibration.json
│   ├── arsenic_voltammetry_example.csv
│   ├── example_calibration.json
│   └── voltammetry2_arsenic_example.csv
└── docs/                       # Technical Documentation & Schematics
    ├── AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.md & .pdf # Exhaustive 800+ line guide
    ├── AQUANET_V1_STRESS_TEST_REPORT.md & .pdf              # 2.4-million scan report
    ├── CATAMARAN_PROTOTYPE_SPEC.md & .pdf                   # Robotic vessel schematic
    └── PERSONAL_TANK_SENTRY_BLUEPRINT.md & .pdf             # Home sentry hardware spec
```

---

## ⚙️ Prototype Hardware Specifications

- **Vessel Airframe**: Twin-hull catamaran (1.05 m × 0.62 m · 11.4 kg displacement).
- **Power Harvesting**: 6V/5W monocrystalline solar panel + MPPT controller + 18650 Li-ion battery (3000mAh buffer), enabling 24/7 autonomous patrol on a 6-hour duty cycle ($0.6 - 1.0\text{ Wh/day}$).
- **Sampling Regime**: Non-immersion microfluidic peristaltic chamber (15 mL sample volume). The electrochemical sensor never directly touches open-water currents, preventing sensor fouling and biofilm buildup.
- **Analytical Engine**: Anodic Stripping Voltammetry (ASV) on 3-electrode screen-printed strips (MAS-G1 strip As-M003050) sampled via an ADS1115 16-bit ADC at −800 mV peak potential.
- **Comms & Telemetry**: LoRa ($2\text{ km+}$ range) + HC-05 Bluetooth + GPS geotagging with zero SIM data cost.

---

## 📄 License & Attribution
Developed for the **HKU Arsenic Sensor Research Project** and **Jal Jeevan Mission Surveillance Initiatives**.
All rights reserved © 2026 AquaSentry Technologies.
