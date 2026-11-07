# AquaSentry Universal — Code Guide & Neural Network Primer

> Diagrams and the interactive chart are in the online version: https://claude.ai/artifact/VkY98xHzQNgkj16KS3wNCz


Nov 7, 2026 · @Suri

## 1. What AquaSentry is

AquaSentry is a water-safety system that measures arsenic electrochemically, reads four other water sensors, and labels the water **Safe, Caution, Unsafe or Hazardous** using a small neural network (AquaNet-V1) wrapped in hard safety rules.

The problem it targets is arsenic in groundwater (a major issue in the Ganges–Brahmaputra basin). The WHO guideline is 10 µg/L (0.010 mg/L); India's BIS 10500 allows up to 50 µg/L only when no other source exists. Lab tests (ICP-MS) are accurate but slow and expensive, so AquaSentry aims to be a cheap, continuous *screening* device — the code repeatedly says it is not a certified lab instrument.

### The five parts of the package

| Part | Folder | Language | What it does |
| --- | --- | --- | --- |
| Web platform | `AquaSentry_Platform/` | Python (FastAPI) + HTML/JS | Stores readings, classifies them, serves a REST API, dashboard, chatbot, PDF certificate |
| Neural toolkit | `Neural_Network/` | Python, JavaScript, C99 | The AquaNet-V1 model in three languages, plus the arsenic signal extractor and parity tests |
| Firmware | `Firmware/` | Arduino C++ (ESP32) | Runs the real hardware: pump, voltage sweep, ADC reading, on-device AI, Wi-Fi upload |
| Research agent | `AI_Agent/` | Python (LangChain) | A separate command-line research assistant (web + Wikipedia search) |
| Data, analysis, docs, 3D | `Data/`, `Analysis/`, `Docs/`, `models_3d/` | CSV, Python, PDF, STL | Sample scans, calibration, synthetic-data generators, specs, printable enclosure |

### Tech stack in one line each

- **FastAPI + Uvicorn** — the Python web server and REST API.
- **SQLAlchemy + SQLite** — the database (`aquasentry.db`), in WAL mode for safe concurrent writes.
- **Pydantic** — checks every incoming JSON body (e.g. pH must be 0–14).
- **Plain HTML/CSS/JS** — the dashboard; no React or build step.
- **NumPy** — only used by the training scripts; the live model is pure Python math.
- **ReportLab** — draws the PDF potability certificate.
- **Google Gemini** — powers the in-dashboard chatbot when an API key is set.
- **ESP32 + FreeRTOS** — the microcontroller; ADS1115 (16-bit ADC) reads current, MCP4725 (12-bit DAC) sets voltage.

### A note on duplicated files

Many files exist in two to four places (for example `aquanet_v1.c` is in `Neural_Network/`, `Firmware/`, `AquaSentry_Platform/` and `AquaSentry_Platform/bridge/`). I compared them: the copies in `Neural_Network/`, `Firmware/`, `AquaSentry_Platform/app/` and `bridge/` are identical. `AquaSentry_Platform/neural_network/` is an **older, different** copy. This guide describes the canonical versions in `AquaSentry_Platform/app/` and `Neural_Network/`.

## 2. Every important file and what it does

The code that matters lives in about 25 files; the rest are copies, PDFs of the Markdown docs, images and 3D models. Paths below are relative to `AquaSentry_Universal/`.

### Launchers and project setup

| File | What it does |
| --- | --- |
| `main.py` | The master command line. `--serve` starts the web API, `--test` runs both test suites, `--csv <file>` analyses a voltammetry scan and prints the verdict as JSON, `--neural` runs six demo water scenarios, `--version` prints the architecture. |
| `setup_and_run.sh` / `.bat` | One-click setup: finds Python, makes a `.venv`, installs `requirements.txt`, then runs `main.py --serve` and opens the browser. |
| `run_all_tests.sh` / `.bat` | Activates the venv and runs `main.py --test`. |
| `requirements.txt` | Python packages: fastapi, uvicorn, sqlalchemy, pydantic, pyserial, requests, google-genai, python-dotenv, pytest, httpx, numpy, reportlab. |
| `Dockerfile`, `docker-compose.yml` | Builds a container (Python 3.11), compiles the C engine as a check, exposes port 8000 with a health check on `/api/health`. |
| `.github/workflows/ci.yml` | GitHub Actions: on every push, installs deps on Python 3.10 and 3.11, compiles the C file with `-Werror`, runs all tests. |

### Backend — `AquaSentry_Platform/app/`

This is the brain of the web platform. Requests come in through `main.py`, get validated by `schemas.py`, classified by `classification.py` + `neural_classifier.py`, and saved through `models.py` / `database.py`.

| File | What it does |
| --- | --- |
| `main.py` (\~1,400 lines) | The FastAPI app. Defines every API route (table below), the emergency-alert dispatcher, the PDF certificate generator, the Gemini chatbot with its system prompt, and a WebSocket that streams a simulated scan point by point. |
| `neural_classifier.py` | **AquaNet-V1 in Python.** Holds the weights, normalisation constants, ReLU, softmax and entropy functions, `forward_pass()` (the network plus safety rules) and `predict_int8()` (an integer-only version that mimics the microcontroller). Identical to `Neural_Network/aquanet_classifier.py`. |
| `classification.py` | Combines the neural verdict with the regulatory rules. `classify_arsenic_neural()` rejects impossible inputs (e.g. pH 12), runs the network, then forces **Unsafe** if arsenic > 50 µg/L and marks **Below Sensor LOD** if arsenic < 20 µg/L. |
| `standards.py` | Single source of truth for numbers: WHO 10 µg/L, BIS 10/50 µg/L, hazard 150 µg/L, sensor LOD 20 and LOQ 30 µg/L, calibration slope 0.8563 and intercept 0.0096. `evaluate_measurement()` turns a concentration into a status, tier, message, recommended action and uncertainty. |
| `signal_processing.py` | The full-quality voltammetry pipeline: checks the scan is valid, smooths it (Savitzky-Golay or rolling median), fits and subtracts a baseline, finds the arsenic peak, measures its height, width, area and signal-to-noise ratio, converts to concentration, and raises QC flags (saturation, unstable baseline, below LOD, above range). Also generates synthetic test scans. |
| `asv_extractor.py` | A lighter version of the same pipeline used by the command line: reads a CSV, smooths, subtracts baseline, finds the peak between −850 and −740 mV, converts to mg/L, then calls the network. Also estimates cadmium, lead and copper peaks and has a standard-addition calculator. |
| `analytes.py` | A catalogue of eight contaminants (arsenic, lead, cadmium, mercury, total and hexavalent chromium, fluoride, nitrate) with their limits and whether the hardware can actually measure them. Only arsenic is hardware-active. |
| `chat_policy.py` | Screens chat messages before they reach the AI: blocks prompt-injection attempts, answers poisoning emergencies with a seek-medical-help message, refuses off-topic questions, and builds a "grounding" block from the latest real reading so the AI never invents numbers. |
| `models.py` | Database tables: `Device`, `Reading` (arsenic, pH, temperature, conductivity, turbidity, GPS, battery, classification, audit fields), `Sample` and `AnalyteResult`. |
| `database.py` | Connects to SQLite (or PostgreSQL via `DATABASE_URL`), turns on WAL mode, adds any missing columns without deleting data, and has a `compact_database()` maintenance routine. |
| `schemas.py` | Pydantic shapes for every request and response. `ReadingCreate` requires `device_code` plus arsenic in either ppb or mg/L, and range-checks every sensor value. |
| `aquanet_v1_weights.json` | The same weights as `neural_classifier.py`, in JSON, with the class names, input ranges and potability limits. |

**API routes in `app/main.py`**

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Is the server and database up? |
| `POST /api/readings` | Ingest a reading from a device or the bridge; classify, store, maybe raise an alert. |
| `GET /api/readings`, `/api/readings/latest`, `/api/stats`, `/api/dashboard/latest` | Query history, newest reading, summary counts, and a dashboard-ready view. |
| `GET /api/analytes`, `/api/analytes/{id}` | The contaminant catalogue. |
| `POST /api/voltammetry/process` | Run the signal pipeline on a scan sent as JSON. |
| `GET /api/voltammetry/sample-trace` | Make a synthetic scan for a given arsenic level. |
| `POST /api/data/import/preview`, `/commit`, `GET /api/data/export` | Bulk import with a dry run, and CSV/JSON export. |
| `POST /api/demo/load` | Fill the database with demo readings. |
| `GET` or `POST /api/neural/inference` | Run AquaNet-V1 directly on five numbers. |
| `POST /api/chat` | The chatbot. |
| `WS /ws/voltammetry` | Streams a simulated scan to the dashboard. |
| `GET /api/reports/certificate/pdf` | Downloads a PDF certificate for a reading. |
| `GET /api/alerts/recent` | Last 20 emergency alerts. |
| `POST /api/admin/db/compact` | Database maintenance. |

### Dashboard — `AquaSentry_Platform/frontend/`

| File | What it does |
| --- | --- |
| `index.html` | Live dashboard (v5): verdict with water-caustics effect and arsenic gauge, "what to do if arsenic is high", contact local authorities (incident report + directory), test a sample, AquaNet panel, 3D device viewer, contaminants, standards and methods, impact, report. |
| `app.js` | Dashboard controller: readings, voltammetry maths (same as the server), AquaNet panel, incident report (email / copy / share / print) and saved local contacts, 3D viewer, CSV export. |
| `shell.js` | Shared by every page: theme, mobile menu, sliding nav highlight, server connection pill, chat assistant, scroll reveal, cursor spotlight, 3D tilt, number counters, WebGL water shader. |
| `motion.js` | Motion layer on every page: moving dotted-wave background, cursor light, scroll progress, heading reveals, magnetic buttons, parallax. |
| `app.css` | The one design system for all pages (carbon black + light theme, glass cards, gradients, animations). |
| `neural.js` | AquaNet V1 and V3 in JavaScript; draws the network as SVG. |
| `i18n.js`, `i18n-v5.js`, `i18n-pages.js` | English and Hindi text for the dashboard, new sections and project pages. |
| `charts.js` | Small offline SVG chart library (bar, line, donut, sparkline). |
| `device3d.js`, `device3d-data.js` | WebGL viewer of the real enclosure STL files (shell, lid, sample well, strainer) with an exploded view. |
| `globe.js` | Rotating dotted globe with priority arsenic regions (market page). |
| `market-research.html`, `sales-expansion.html`, `pages.js` | Market research (charts, competitor table, globe) and sales & expansion (revenue charts, ROI calculator, roadmap). |
| `device-simulator.html`, `mas-g1-display.html` | Handheld MAS-G1 meter screen simulator (import real CSV scans and calibration). |
| `legacy_v1/` | The original v1 dashboard, kept for reference. |

### Hardware link — `AquaSentry_Platform/bridge/` and `Firmware/`

| File | What it does |
| --- | --- |
| `bridge/serial_bridge.py` | Runs on a laptop paired with the Arduino's HC-05 Bluetooth module. Reads lines like `AS:6.20,PH:7.10,T:26.40,EC:420.00,TURB:3.10`, turns them into JSON and POSTs them to `/api/readings`. Never crashes on a bad line. |
| `Firmware/esp32_firmware/esp32_firmware.ino` | The ESP32 program. Core 1 runs the measurement loop every hour: pump water into the chamber, check for bubbles, apply a +1.2 V cleaning pulse, hold −0.8 V for 60 s to plate arsenic onto the electrode, sweep the voltage up in 5 mV steps while reading current, convert the peak to mg/L, and run `aquanet_predict_int8()`. Core 0 handles Wi-Fi, uploads readings, stores up to 500 readings in flash when offline, and serves an over-the-air update page. |
| `Neural_Network/aquanet_v1.c`, `.h` | **AquaNet-V1 in C99** for microcontrollers. No `malloc`. Has a float version, an INT8 version (weights stored as 8-bit integers, maths in Q10 fixed point = scaled by 1024), the same safety rules, entropy and standard addition. |
| `Firmware/README.md` | Pin map (I2C on GPIO 21/22, stepper on 25/26/27, bubble sensor on 34) and flashing steps. |

### Neural toolkit and training — `Neural_Network/` and `AquaSentry_Platform/scripts/`

| File | What it does |
| --- | --- |
| `Neural_Network/main.py` | Small CLI that runs demo scenarios through the network. |
| `Neural_Network/test_aquanet_parity.py` | 22 tests: topology counts, softmax sums to 1, out-of-range inputs never return Safe, arsenic rules always win, INT8 matches float. |
| `Neural_Network/legacy_asv_regressor.py` | An older, different network: takes all 81 points of a scan, one hidden layer of 10,000 ReLU neurons, outputs a concentration number. Trained on synthetic scans with mean-squared error. Useful as a contrast (see section 4). |
| `scripts/train_aquanet_v2.py` | A real from-scratch trainer in NumPy: generates 120,000 synthetic samples, He initialisation, cross-entropy loss with 4× penalty for calling dangerous water safe, backpropagation, Adam, cosine learning-rate decay, keeps the best weights with zero "toxic false negatives". Writes to `/tmp`; not wired into the app. |
| `scripts/train_and_deploy_aquanet_v2.py` | Builds the weights **by hand from the thresholds**, then fine-tunes them, then writes them into `neural_classifier.py` and `neural.js`. This is where the deployed weights came from (section 4 explains). |
| `scripts/sync_neural_network.py` | Copies model files between folders so all copies match. |
| `scripts/aquanet_stress_test_benchmark.py` | Runs \~2.4 million simulated scans (seasons, electrode fouling, edge cases, faults) and writes a report. |

### Tests — `AquaSentry_Platform/tests/` (79 tests)

| File | Tests | Checks |
| --- | --- | --- |
| `test_neural_parity.py` | 18 | Python and JS/C networks agree; guardrails hold |
| `test_scientific_standards.py` | 13 | Thresholds, unit conversions, status labels |
| `test_api_contracts.py` | 10 | Every endpoint returns the right shape and codes |
| `test_analytes.py` | 9 | Contaminant catalogue |
| `test_chat_policy.py` | 8 | Injection and emergency filters |
| `test_signal_processing.py` | 8 | Smoothing, baseline, peak finding |
| `test_ui_safety_gates.py` | 8 | The UI never shows an unearned "Safe" |
| `test_data_provenance.py` | 5 | Simulated vs hardware data stay labelled |

### Other folders

- **`Data/`** — `example_data.csv` (81 points from −1000 to −600 mV, columns `potential_mV,current_uA`), two more arsenic scans, and `calibration.json` (slope 0.856 µA per mg/L, intercept 0.0096 µA, R² 0.997 from four standards: 0.03, 0.10, 0.25, 0.50 mg/L).
- **`Analysis/`** — `generate_arsenic_data.py` makes fake scans (noisy baseline + Gaussian peak at −800 mV); `mas_g1_arsenic_analysis.py` is a standalone calibrate/quantify tool for the MAS-G1 reader using SciPy.
- **`AI_Agent/`** — `main.py` builds a LangChain agent on Claude 3.5 Sonnet that answers a research question in a fixed JSON shape; `tools.py` gives it DuckDuckGo search, Wikipedia and save-to-file. It is not connected to the platform.
- **`Docs/`** — the long neural-network guide, stress-test and retraining reports, catamaran and household-tank hardware specs, and a home assembly manual.
- **`models_3d/`** — STL/3MF files for the 120 mm electronics shell, lid, tank bracket, 15 mL sample well and suction strainer.

## 3. How a water test flows through the system

A test turns a tiny electrical current into a concentration, the concentration plus four sensor values into a neural-network verdict, and the verdict — after safety rules — into a stored, displayed and (if dangerous) alerted reading.

&#91;embedded content: end-to-end flow · 6 stages plus the on-device path\]

Steps 1–3 can run on the device or on the server; steps 4–6 only happen once a reading reaches the API.

### Stage A — Measuring arsenic with stripping voltammetry (hardware)

Anodic Stripping Voltammetry (ASV) is how the device "sees" arsenic. The firmware's `execute_asv_cycle()` does it in three steps:

1. **Clean** — hold the electrode at +1.2 V for 2 s to strip off old deposits.
2. **Deposit** — hold it at −0.8 V for 60 s. Dissolved arsenic ions are pulled onto the electrode and turn into solid metal, concentrating them.
3. **Strip** — sweep the voltage upward in 5 mV steps. At arsenic's characteristic voltage the metal dissolves back into ions all at once, releasing electrons. That shows up as a **peak in current**. More arsenic = taller peak.

The DAC (MCP4725) sets each voltage; the ADC (ADS1115) reads the current through a 100 kΩ resistor (100 mV = 1 µA). Before this, the stepper pump fills a 15 mL chamber and an optical sensor checks there are no air bubbles; if the chamber is dry the cycle aborts.

### Stage B — Turning the scan into a concentration (software)

The scan is a list of (voltage, current) pairs — `Data/example_data.csv` has 81 of them from −1000 to −600 mV. `asv_extractor.py` and `signal_processing.py` process it:

1. **Smooth** — a 5-point Savitzky-Golay filter replaces each point with a weighted average of itself and its neighbours (weights −3, 12, 17, 12, −3, divided by 35). It removes jitter but keeps the peak's shape.
2. **Remove the baseline** — the current drifts slightly across the scan even with no arsenic. The code fits a straight line through the points *far from* the peak (more than 105 mV from −795 mV) and subtracts it.
3. **Find the peak** — the biggest leftover current between −850 and −740 mV is the net peak current, Ip.
4. **Calibrate** — a lab calibration with four known standards gave the straight line Ip = 0.8563 × \[As\] + 0.0096. Rearranged: \[As\] = (Ip − 0.0096) / 0.8563 mg/L.
5. **Quality checks** — flags for ADC saturation, a noisy baseline, a result below the 20 µg/L detection limit, or above the 500 µg/L calibrated range (dilute and retest).

**Worked example (I recomputed this from the file):** for `example_data.csv` the peak sits at −800 mV, the smoothed current there is 0.0684 µA and the baseline is 0.0524 µA, so Ip = 0.0160 µA. Then \[As\] = (0.0160 − 0.0096) / 0.8563 = **0.0074 mg/L (7.4 µg/L)**. The same steps on `arsenic_voltammetry_example.csv` give Ip = 0.198 µA and **0.220 mg/L** — a hazardous sample.

### Stage C — Classifying the water

The network takes five numbers: arsenic (mg/L), pH, conductivity (µS/cm), turbidity (NTU) and temperature (°C). Section 4 explains what happens inside. After the network picks a class, `forward_pass()` applies rules in this order:

1. **Out-of-range gate** — any sensor outside its valid range (e.g. pH outside 4.5–10.5) means the result can't be Safe or Caution; it becomes Unsafe.
2. **Arsenic rules win** — above 0.150 mg/L is always Hazardous; 0.050 mg/L or more is at least Unsafe; below 0.020 mg/L adds a "below detection limit" notice.
3. **Other water standards** — pH outside 6.5–8.5 bumps Safe to Caution (outside 6.0–9.0 forces Unsafe); turbidity above 5 NTU → Caution, above 10 NTU → Unsafe; conductivity above 1500 µS/cm → Caution, above 2000 → Unsafe.
4. **Uncertainty check** — if the network's answer is "spread out" (normalised entropy above 0.65) and it said Safe, it becomes Caution.

The rules can only make a verdict **stricter**, never more lenient. In the web platform, `classification.py` adds one more layer: below 20 µg/L the label becomes **Below Sensor LOD**, because the sensor can't prove water is under the 10 µg/L WHO line.

For the worked example (7.4 µg/L, pH 7.2, 400 µS/cm, 2 NTU, 24 °C) the network says Safe with \~100% confidence, plus the detection-limit notice; the web platform would store it as Below Sensor LOD.

### Stage D — Storing, showing, alerting

1. The reading arrives at `POST /api/readings` (from the Bluetooth bridge, a device, an import, or the demo loader). Pydantic validates it; an `idempotency_key` stops the same reading being saved twice.
2. It is classified (Stage C), saved to SQLite with full audit info (source type, method version, model version, raw payload), and linked to its device.
3. If arsenic is 50 µg/L or more, `dispatch_emergency_alert()` records a WARNING (or CRITICAL at 150+) and POSTs it to a webhook if `ALERT_WEBHOOK_URL` is set.
4. The dashboard polls `/api/dashboard/latest`, recolours the status card, and syncs the neural-network picture to the new arsenic value.
5. Optional extras: a PDF certificate (`/api/reports/certificate/pdf`) and the chatbot, which is fed the latest reading so it talks about real data.

### Two other paths through the system

- **On the device itself:** the ESP32 runs the INT8 version of the network locally, so it can show a verdict with no internet. When Wi-Fi is down it saves up to 500 readings in flash and uploads them later.
- **From the command line:** `python3 main.py --csv Data/example_data.csv --ph 7.4` runs Stages B and C and prints the full JSON, with no server or database.

## 4. Neural networks, taught through AquaNet-V1

A neural network is a function built from many tiny weighted sums; AquaNet-V1 is a 5-8-6-4 network that maps five water measurements to four safety classes. This section builds it up from one neuron, then opens the real weights and shows exactly what each neuron does — including something surprising about how they were made.

### 4.1 The big idea

Ordinary code is rules a person writes: `if arsenic > 0.05: unsafe`. A neural network instead has **parameters** (numbers called weights and biases) and a fixed recipe for combining them with the input. Training means adjusting those numbers automatically until the outputs match known examples. Once trained, running the network on new input is called **inference** or a **forward pass** — that is what `forward_pass()` in `neural_classifier.py` does.

### 4.2 One neuron

A neuron takes some inputs, multiplies each by a weight, adds them up, adds a bias, and passes the total through an **activation function**:

```latex
z = w_1x_1 + w_2x_2 + \dots + w_nx_n + b \qquad a = f(z)
```

- The **weights** say how much each input matters, and in which direction (negative weight = "more of this input pushes me down").
- The **bias** shifts the point at which the neuron switches on.
- The **activation** adds a bend. Without it, stacking layers would still only give a straight-line function.

AquaNet uses **ReLU** (Rectified Linear Unit): `relu(z) = max(0, z)`. Negative totals become 0 ("off"); positive totals pass through unchanged. In the code: `def relu(x): return max(0.0, x)`.

### 4.3 Layers and the 5-8-6-4 shape

Neurons are arranged in layers. Every neuron in one layer connects to every neuron in the next ("fully connected" or "dense"). AquaNet-V1 has:

| Layer | Neurons | Activation | Connections into it |
| --- | --- | --- | --- |
| Input | 5 (arsenic, pH, conductivity, turbidity, temperature) | none | — |
| Hidden 1 | 8 | ReLU | 5 × 8 = 40 |
| Hidden 2 | 6 | ReLU | 8 × 6 = 48 |
| Output | 4 (Safe, Caution, Unsafe, Hazardous) | softmax | 6 × 4 = 24 |

That is 23 nodes and 112 weights (the "synapses" the code keeps mentioning), plus 18 biases. A whole layer is just a matrix multiplication: `h1 = relu(W1 · x + B1)`, where W1 is an 8×5 grid of numbers. In the code each layer is one list comprehension:

```python
h1 = [relu(sum(w * val for w, val in zip(W1[i], x)) + B1[i]) for i in range(8)]
```

Read it as: for each of the 8 neurons, multiply its 5 weights by the 5 inputs, add, add the bias, apply ReLU.

### 4.4 Step zero: normalising the inputs

The raw inputs have wildly different sizes: arsenic around 0.01, conductivity around 600. If fed in raw, conductivity would swamp everything. So each input is converted to a **z-score** — how many "typical spreads" it is from a typical value:

```latex
x_i = \frac{\text{raw}_i - \text{mean}_i}{\text{std}_i}
```

AquaNet uses mean = \[0.08, 7.5, 600, 4.0, 25\] and std = \[0.10, 0.7, 300, 3.0, 4.0\]. Example: arsenic 0.0074 mg/L becomes (0.0074 − 0.08) / 0.10 = −0.726; pH 7.2 becomes (7.2 − 7.5) / 0.7 = −0.43. Now every input lives on a similar scale near zero.

### 4.5 Softmax: turning scores into probabilities

The output layer produces four raw scores called **logits**. Softmax turns them into probabilities that are all positive and add up to 1:

```latex
p_k = \frac{e^{z_k}}{\sum_{j=1}^{4} e^{z_j}}
```

Bigger logit → bigger probability, and because of the exponential, a lead of even 10 points makes one class almost certain. Logits of \[25, 0, 0, 0\] give Safe ≈ 100%; logits of \[0, 0, 0, 0\] give 25% each — the network has no idea. The code subtracts the largest logit first (`math.exp(val - max_logit)`) so the exponentials never overflow; it doesn't change the answer.

The predicted class is simply the one with the highest probability, and that probability is reported as **confidence**.

### 4.6 Entropy: measuring "how unsure"

Confidence only looks at the winner. **Shannon entropy** looks at the whole spread:

```latex
H = -\frac{1}{\ln 4}\sum_{k=1}^{4} p_k \ln p_k
```

Dividing by ln 4 scales it to 0 (one class has 100%) through 1 (all four at 25%). `calculate_entropy()` computes this, and if H > 0.65 a Safe verdict is downgraded to Caution. This is a simple, honest way for a model to say "I'm on a boundary, don't trust me".

### 4.7 How a network learns

The deployed weights weren't learned this way (see 4.9), but `scripts/train_aquanet_v2.py` contains a complete, correct training loop written from scratch in NumPy. It is the best file in the project to learn from. The ingredients:

1. **Training data** — examples with known answers. The script generates 120,000 synthetic water samples and labels each by arsenic alone: < 0.010 Safe, 0.010–0.050 Caution, 0.050–0.150 Unsafe, > 0.150 Hazardous. It over-samples the regions near each threshold, because that is where mistakes happen.
2. **Initialisation** — weights start as small random numbers. "He initialisation" scales them by √(2 / inputs) so signals neither die out nor explode through ReLU layers.
3. **Loss function** — one number saying how wrong the network is. For classification it's **cross-entropy**: −ln(probability given to the correct class). Give the right class 90% → loss 0.11; give it 1% → loss 4.6.
4. **Asymmetric cost** — the script multiplies the error by 4 when truly Unsafe/Hazardous water is pushed toward Safe/Caution. In a safety product a false "safe" is far worse than a false alarm, and this is how you tell the network that.
5. **Backpropagation** — calculus (the chain rule) that works backwards from the loss to find, for every weight, which way to nudge it to reduce the loss. For softmax + cross-entropy the starting gradient is beautifully simple: `probs − Y_onehot`. Each earlier layer multiplies by the next layer's weights and by ReLU's slope (1 if the neuron was on, 0 if off).
6. **Gradient descent with Adam** — move every weight a small step downhill: weight ← weight − learning\_rate × gradient. Adam is a smarter version that keeps a running average of past gradients (momentum) and scales each weight's step by how noisy its gradient has been.
7. **Mini-batches and epochs** — instead of all 100,000 examples at once, it updates after every batch of 256. One full pass over the data is an epoch; the script runs 160.
8. **Learning-rate schedule** — a cosine curve starts with big steps and ends with tiny ones, to settle into a good spot.
9. **L2 regularisation** — a small penalty on large weights, which discourages over-complicated solutions.
10. **Validation** — 20,000 examples are held back and never trained on. Every 10 epochs it measures accuracy on them, and it only keeps a set of weights if it has zero "toxic false negatives" (dangerous water called Safe).

### 4.8 Opening the real weights: what each neuron does

Here is the key insight for this project. Look at `W1` in `aquanet_v1_weights.json`: in every row, only the first column (arsenic) is non-zero, and the values are exactly ±50. Substituting the normalisation, each hidden-1 neuron simplifies to a ramp in arsenic (As in mg/L):

| Neuron | Weight on As | Bias | Simplifies to | Plain meaning |
| --- | --- | --- | --- | --- |
| h1\[0\] | +50 | +35 | relu(500·As − 5) | How far **above** 10 µg/L (WHO) |
| h1\[1\] | −50 | −35 | relu(5 − 500·As) | How far **below** 10 µg/L |
| h1\[2\] | +50 | +15 | relu(500·As − 25) | How far above 50 µg/L (BIS) |
| h1\[3\] | −50 | −15 | relu(25 − 500·As) | How far below 50 µg/L |
| h1\[4\] | +50 | −35 | relu(500·As − 75) | How far above 150 µg/L (hazard) |
| h1\[5\] | −50 | +35 | relu(75 − 500·As) | How far below 150 µg/L |
| h1\[6\], h1\[7\] | 0 | 0 | always 0 | Unused ("dead") neurons |

&#91;embedded content: AquaNet-V1 non-zero weights · from aquanet\_v1\_weights.json\]

The four lower inputs and two hidden neurons are wired in but carry zero weight, so they can never change the network's answer.

So layer 1 is three pairs of **threshold detectors**, one pair per regulatory limit. Layer 2 then combines them, and the output scores become:

- **Safe** = 20 × h1\[1\] — grows the further you are below 10 µg/L.
- **Caution** = 20 × min(h1\[0\], h1\[3\]) — a "tent": zero at 10 and 50 µg/L, highest at 30 µg/L. Layer 2 builds the min with the ReLU trick min(a, b) = a − relu(a − b).
- **Unsafe** = 20 × min(h1\[2\], h1\[5\]) — a tent between 50 and 150 µg/L, peaking at 100.
- **Hazardous** = 20 × h1\[4\] — grows above 150 µg/L.

&#91;embedded content: computed from Neural\_Network/aquanet\_v1\_weights.json · arsenic 0–200 µg/L in 5 µg/L steps\]

Softmax then picks whichever score is highest, so each class wins exactly inside its own band — and at the three dashed lines nothing wins.

Each logit literally measures "how deep inside my band is this reading". Tracing three inputs through the real network (I computed these from the weights file; other inputs held at pH 7.2, 400 µS/cm, 2 NTU, 24 °C):

| Arsenic | Non-zero hidden-1 values | Logits \[Safe, Caution, Unsafe, Hazardous\] | Verdict |
| --- | --- | --- | --- |
| 7.5 µg/L | h1\[1\]=1.25, h1\[3\]=21.25, h1\[5\]=71.25 | \[25, 0, 0, 0\] | Safe, 100% |
| 35 µg/L | h1\[0\]=12.5, h1\[3\]=7.5, h1\[5\]=57.5 | \[0, 150, 0, 0\] | Caution, 100% |
| 200 µg/L | h1\[0\]=95, h1\[2\]=75, h1\[4\]=25 | \[0, 0, 0, 500\] | Hazardous, 100% |
| exactly 10 or 50 or 150 µg/L | — | \[0, 0.0001, 0, 0\] | Caution at 25% — total uncertainty |

At each exact threshold every score hits zero, so the network is maximally unsure (entropy = 1.0). That is why the rule layer exists: it decides those knife-edge cases conservatively.

### 4.9 The honest finding: these weights were designed, not learned

The code comments, the JSON metadata and the chatbot prompt all say AquaNet-V1 was "trained with Adam on 8,000 synthetic samples, 99.7% accuracy". The weights tell a different story:

- They are round numbers (50, 35, 15, 20, 1) — trained weights are never this tidy.
- `scripts/train_and_deploy_aquanet_v2.py` **constructs exactly these values by hand** from the thresholds (S = 50, bias = −S × normalised threshold) before any training, and the deployed weights match that starting point.
- Only **20 of the 112 weights are non-zero**, and none touches pH, conductivity, turbidity or temperature. I checked: changing pH from 5 to 9 doesn't move the network's probabilities at all. Those four inputs only affect the result through the hand-written `if` rules after the network.

This isn't a disaster — it's a clever construction, and it proves a neural network *can* represent the arsenic rules exactly. But it means AquaNet-V1 is really a hand-wired arsenic threshold classifier, not a learned multimodal model. If you present the project, describe it accurately: "a 5-8-6-4 network whose weights were analytically constructed to encode the WHO/BIS thresholds".

It also explains *why* training could never learn the other inputs: in both training scripts the labels depend only on arsenic, so pH etc. carry no information about the answer. A network can only learn patterns that exist in its labels. To make it genuinely multimodal you would need labels that depend on all five inputs (for example, from lab-graded real samples), then train from random weights with `train_aquanet_v2.py`.

### 4.10 Squeezing it onto a microcontroller: INT8 quantisation

The ESP32 is happier with whole numbers than decimals. `aquanet_predict_int8()` (C) and `predict_int8()` (Python) store each weight as an 8-bit integer (−128 to 127) and represent inputs in **Q10 fixed point**: multiply by 1024 and round, so 0.726 becomes 743. All the multiply-adds then happen in integers, and the logits are divided by 1024 at the end. Because these weights are already whole numbers, nothing is lost here; with real trained weights (like 0.3172) you'd need to scale them before rounding or accuracy would suffer.

### 4.11 A contrast: the legacy regressor

`legacy_asv_regressor.py` is a different kind of network that's worth comparing:

|  | AquaNet-V1 | Legacy regressor |
| --- | --- | --- |
| Task | Classification (4 classes) | Regression (one number: concentration) |
| Input | 5 summary measurements | All 81 current values of a raw scan |
| Hidden layers | 2 (8 and 6 neurons) | 1 (10,000 neurons) |
| Output | Softmax probabilities | Linear (no activation) |
| Loss | Cross-entropy | Mean squared error |
| Parameters | 130 | \~830,000 |

The regressor tries to replace the whole signal-processing pipeline (smooth → baseline → peak → calibrate) by learning it from examples. 10,000 hidden neurons is far more than this job needs; a few dozen would do.

### 4.12 Try it yourself

1. Open the dashboard's neural panel and slide arsenic slowly through 10, 50 and 150 µg/L. Watch confidence collapse to 25% at each threshold.
2. Slide pH from 5 to 9 with arsenic fixed. The bars won't move — only the rule-based verdict changes.
3. Run `scripts/train_aquanet_v2.py` and compare its printed weights with the deployed ones. Notice how messy learned weights look.
4. Change the labels in that script so turbidity above 10 NTU is always Unsafe, retrain, and check whether the new W1 puts weight on the turbidity column.

## 5. Running it, issues found, and a glossary

The project runs with one command, but a code review turned up one urgent security fix and several places where parts don't actually connect; fix those before demoing or presenting.

### How to run it

1. **Set up:** `./setup_and_run.sh` (Mac/Linux) or double-click `setup_and_run.bat` (Windows). This makes a `.venv`, installs packages and starts the API on port 8000.
2. **See the API:** open `http://localhost:8000/docs` for the interactive Swagger page where you can try every route.
3. **See the dashboard:** open `AquaSentry_Platform/frontend/index.html` in a browser, or run `AquaSentry_Platform/START_AQUASENTRY.bat` / `start_aquasentry.sh`, which also serves it at `http://localhost:8001/index.html`. (Opening `localhost:8000` itself shows "Not Found" — see issue 4.)
4. **Analyse a scan without the server:** `python3 main.py --csv Data/example_data.csv --ph 7.4 --ec 450 --turb 1.8 --temp 25`.
5. **Run tests:** `python3 main.py --test` (22 neural + 88 platform = 110 tests).
6. **Chatbot:** copy `.env.example` to `.env` and add a `GEMINI_API_KEY`; without it the chat answers in offline mode.

I read every file but couldn't execute the project's own code here, so the numbers in sections 3 and 4 come from my own small script that re-implements the same maths on the shipped data and weights.

### Issues I found

> **Fixed in v3:** everything in this table has been fixed. See `FIXES_v3.md` for each file and line.

**Key points at a glance**

- **Leaked API key** — a live Gemini key ships inside the zip; revoke it and remove `.env`.
- **Fake certificate** — the PDF says "Laboratory Certificate … Safe" even with no readings in the database.
- **Device can't upload** — the ESP32 sends fields the API rejects, so every reading fails with HTTP 422.
- **Dashboard not served** — the launcher opens `localhost:8000`, which shows "Not Found".
- **Firmware and software disagree** — different arsenic peak window and calibration slope; other sensors are hard-coded.
- **Network claims are overstated** — the weights are hand-built and only arsenic affects them, not "trained to 99.7%".
- **Small bugs and clutter** — the live-scan WebSocket crashes, files are duplicated, test counts don't match.

The full table with fixes follows.

| # | Severity | Where | Problem | Suggested fix |
| --- | --- | --- | --- | --- |
| 1 | Urgent | `AquaSentry_Platform/.env` | A real-looking Gemini API key is inside the zip. Anyone you send the zip to can use it. | Revoke it in Google AI Studio, make a new one, delete `.env` from the package and keep only `.env.example`. |
| 2 | High | `app/main.py`, certificate route | With an empty database the PDF still prints "AQUASENTRY LABORATORY WATER CERTIFICATE", verdict **Safe**, 98.5% confidence and made-up readings. It also says "SHA-256 Validated" without computing a hash. | Return an error when there's no reading; drop "Laboratory" and the hash line; print the screening disclaimer on the PDF. |
| 3 | High | `Firmware/esp32_firmware.ino` | The ESP32 posts `arsenic_ppm` with no `device_code`, but the API requires `device_code` and `arsenic_ppb` or `arsenic_concentration_mg_l`. Every upload would be rejected (HTTP 422) and pile up in the offline buffer. | Send `{"device_code":"TANK-001","arsenic_concentration_mg_l":…,"conductivity_us_cm":…,"source_type":"hardware"}`. |
| 4 | Medium | `main.py --serve`, `setup_and_run` | The launcher opens `localhost:8000`, but FastAPI never serves the `frontend/` folder, so the browser shows "Not Found". | Add `app.mount("/", StaticFiles(directory="frontend", html=True))` after the API routes. |
| 5 | Medium | Firmware vs software | The firmware looks for the arsenic peak between −400 and −100 mV and uses slope 28.5 µA per mg/L; the software uses −850 to −740 mV and 0.8563. Its sweep also *starts* at −800 mV, right where the software expects the peak. | Pick one calibration and window from real measurements and use it everywhere. |
| 6 | Medium | Firmware sensor task | pH, conductivity, turbidity and temperature are fixed numbers (7.4, 580, 1.8, 24.5), not sensor reads. | Wire up the real sensors, or send them as missing so the platform knows. |
| 7 | Medium | `neural_classifier.py`, JSON, chatbot prompt, README | Claims the model was trained with Adam on 8,000 samples to 99.7%; the deployed weights are hand-constructed and use only arsenic (section 4.9). | Describe it accurately, or retrain with labels that depend on all five inputs. |
| 8 | Low | `app/main.py`, `/ws/voltammetry` | Reads `peak.net_current_ua` and `peak.potential_mv`, which don't exist (real names: `net_peak_height_ua`, `peak_potential_mv`), so the stream crashes at the end. It also passes mg/L into a function expecting µg/L. | Fix the two attribute names and multiply by 1000. |
| 9 | Low | Whole package | Files duplicated in up to four folders; `AquaSentry_Platform/neural_network/` is an out-of-date copy. Docs say 97 tests in some places and 101 in others. | Keep one copy and import it; make the test count match. |
| 10 | Low | `AI_Agent/` | README says Gemini/Claude/GPT-4, but the code is hard-wired to an older Claude 3.5 Sonnet model ID that may no longer be available, and it isn't connected to the platform. | Update the model ID or remove the folder from the distribution. |

### Glossary

| Term | Meaning |
| --- | --- |
| ASV (Anodic Stripping Voltammetry) | Plate metal onto an electrode, then dissolve it with a voltage sweep and measure the current peak. |
| Voltammogram / scan / trace | The list of (voltage, current) points from one sweep. |
| Savitzky-Golay filter | Smoothing that fits a small curve through each window of points, keeping peak shape. |
| Baseline | Background current with no arsenic; subtracted before measuring the peak. |
| Calibration | The straight line linking peak current to known concentrations. |
| LOD / LOQ | Limit of Detection (smallest amount reliably seen, 20 µg/L here) / Limit of Quantification (smallest amount reliably measured, 30 µg/L). |
| µg/L, ppb, mg/L, ppm | 1 µg/L = 1 ppb; 1 mg/L = 1 ppm = 1000 µg/L. |
| NTU | Turbidity unit (cloudiness). |
| µS/cm | Conductivity unit (dissolved salts). |
| WHO / BIS 10500 | World Health Organization guideline (10 µg/L arsenic) / Indian drinking-water standard (10 acceptable, 50 permissible). |
| Weight, bias | The adjustable numbers in a neuron. |
| Activation (ReLU) | The bend applied after the weighted sum; ReLU = max(0, z). |
| Logit | A raw output score before softmax. |
| Softmax | Turns logits into probabilities that sum to 1. |
| Entropy | How spread out the probabilities are; 0 = certain, 1 = no idea. |
| Loss / cross-entropy | A number measuring how wrong the network is. |
| Backpropagation | Working out every weight's gradient with the chain rule. |
| Adam | A gradient-descent optimiser with momentum and per-weight step sizes. |
| Epoch / batch | One pass over all training data / the chunk used for one update. |
| Overfitting / validation set | Memorising training data instead of learning / held-back data used to catch it. |
| Quantisation (INT8, Q10) | Storing numbers as small integers; Q10 = scaled by 1024. |
| FastAPI / Pydantic / SQLAlchemy | Python web framework / data validation / database toolkit. |
| Idempotency key | A unique ID that stops one reading being saved twice. |
| WAL (write-ahead log) | SQLite mode that allows reading while writing. |
| FreeRTOS | The mini operating system on the ESP32 that runs two tasks on two cores. |
| OTA | Over-the-air firmware update via Wi-Fi. |
