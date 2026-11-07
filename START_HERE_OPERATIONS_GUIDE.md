# AquaSentry Universal All-In-One Operations Guide
### *Complete Step-by-Step Instructions: From Unzipping to Full Execution*

---

## 1. Welcome to AquaSentry

You have received the consolidated **AquaSentry Universal All-In-One Distribution**. This package contains everything required to analyze electrochemical water quality traces, run real-time artificial neural network classifications, host a full-stack water safety monitoring dashboard, deploy edge firmware to microcontrollers, and perform AI toxicology research.

### What is Inside This Folder
When you open this folder, you will see the following layout:
* **`START_HERE_OPERATIONS_GUIDE.pdf`**: *This document.*
* **`setup_and_run.sh`**: 1-Click launcher for macOS & Linux.
* **`setup_and_run.bat`**: 1-Click launcher for Windows.
* **`run_all_tests.sh` / `run_all_tests.bat`**: 1-Click automated test runners.
* **`main.py`**: The universal master command-line interface.
* **`requirements.txt`**: Consolidated Python dependencies.
* **`AquaSentry_Platform/`**: Full-stack FastAPI web application, interactive HTML5 dashboard, database, and serial bridge.
* **`Neural_Network/`**: Dedicated AquaNet-V1 ML engine (Python, JavaScript, C99 microcontroller source, parity test suite).
* **`AI_Agent/`**: LLM research agent for toxicology and environmental safety queries.
* **`Data/`**: Real and synthetic square-wave ASV voltammetric scan CSV files and calibration matrices.
* **`Analysis/`**: Signal processing, baseline subtraction, and data generation utilities.
* **`Docs/`**: Full engineering blueprints, catamaran hardware specs, and technical reports.

---

## 2. 3-Minute Quick Start on Any New Computer

### System Requirements
* **Operating System**: macOS, Windows 10/11, or Linux (Ubuntu, Debian, Fedora, Arch).
* **Python**: Python 3.9, 3.10, 3.11, or 3.12 installed on your system.
  *(To verify, open terminal or command prompt and run `python3 --version` or `python --version`).*

---

### Option A: macOS or Linux (Recommended 1-Click)
1. Open your **Terminal** application.
2. Navigate to this unzipped folder:
   ```bash
   cd path/to/AquaSentry_Universal
   ```
3. Run the automated launcher:
   ```bash
   chmod +x setup_and_run.sh
   ./setup_and_run.sh
   ```
4. **What happens automatically:**
   * The script detects your Python version.
   * It creates a clean, isolated virtual environment (`.venv`) customized for your exact operating system and CPU architecture.
   * It installs all dependencies from `requirements.txt`.
   * It starts the AquaSentry web server at `http://localhost:8000` and automatically opens your web browser.

---

### Option B: Windows (Recommended 1-Click)
1. Open the unzipped folder in **Windows File Explorer**.
2. **Double-click** the file named:
   ```bat
   setup_and_run.bat
   ```
   *(Or open Command Prompt / PowerShell, navigate to the folder, and type `setup_and_run.bat`).*
3. **What happens automatically:**
   * Windows detects Python, creates `.venv`, installs dependencies, launches the server, and opens `http://localhost:8000` in your default browser.

---

### Option C: Manual Setup (For Advanced Developers)
If you prefer complete manual control over your terminal environment:
```bash
# 1. Create a virtual environment
python3 -m venv .venv

# 2. Activate it
# On macOS / Linux:
source .venv/bin/activate
# On Windows (cmd):
.venv\Scripts\activate.bat
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Install packages
pip install --upgrade pip
pip install -r requirements.txt

# 4. Launch the web platform
python main.py --serve --port 8000
```

---

## 3. How to Use the Web Platform & Interactive Dashboard

Once the server is running (`http://localhost:8000`):

1. **Dashboard Overview**:
   * View live hydrogeochemical parameters: Arsenic ($[As]$), pH, Electrical Conductivity (EC), Turbidity, and Temperature.
   * View the real-time safety potability classification (`Safe`, `Caution`, `Unsafe`, `Hazardous`).
2. **Upload & Process Voltammetric Trace (ASV)**:
   * In the UI, navigate to the **Voltammetry** tab.
   * Upload any scan file from the `Data/` folder (such as `Data/example_data.csv`).
   * The system applies a 5-point Savitzky-Golay filter, removes baseline tilt, identifies the net Faradaic stripping peak, inverts calibration to find $[As]$, and passes it through the AquaNet neural network.
3. **Interactive AI Safety Assistant**:
   * Open the **Chat** widget in the bottom right corner.
   * Ask questions such as: *"Is this water safe to drink?"*, *"What does 0.035 mg/L arsenic mean?"*, or *"Explain WHO guidelines."*
   * The assistant enforces emergency toxicology guardrails and warns against drinking contaminated water.
4. **Interactive REST API Documentation (Swagger)**:
   * Visit `http://localhost:8000/docs` to view and execute any of the 15+ interactive REST endpoints.

---

## 4. Running the Complete Verification Test Suite

To verify that every component, mathematical calculation, and safety rule works with 100% precision:

### On macOS / Linux:
```bash
./run_all_tests.sh
```

### On Windows:
```bat
run_all_tests.bat
```

### Or using the Universal CLI:
```bash
python3 main.py --test
```

### What is Tested (139 Automated Test Cases):
* **22 Standalone Neural Parity Tests** (`Neural_Network/test_aquanet_parity.py`):
  * Exact 23-node, 112-synapse forward pass parity.
  * Multi-parameter potability downgrades (pH outside 6.5–8.5, turbidity $> 5.0\text{ NTU}$, conductivity $> 1500\ \mu\text{S/cm}$).
  * Out-of-bounds sensor fail-safes (invalid negative temperatures or extreme pH immediately revoke safe status).
  * Conservative statutory precedence overrides (arsenic $>0.150\text{ mg/L} \to \text{Hazardous}$; $\ge 0.020\text{ mg/L}$ detected $\to \text{Unsafe}$, because the IS 10500 limit is $0.010\text{ mg/L}$ with no relaxation).
* **117 Platform Integration Tests** (`AquaSentry_Platform/run_tests.py`):
  * REST API contracts, reading ingestion, duplicate protection.
  * Digital filtering, Savitzky-Golay convolution, peak detection.
  * Chat policy prompt injection prevention.

---

## 5. Universal Command-Line Interface (`main.py`)

You can execute common tasks directly from your terminal using `main.py`:

| Command | Action |
| :--- | :--- |
| `python3 main.py --serve` | Starts the web platform and API on port 8000. |
| `python3 main.py --serve --port 8080` | Starts on custom port 8080. |
| `python3 main.py --test` | Runs all 139 test cases across both suites. |
| `python3 main.py --csv Data/example_data.csv` | Processes a raw voltammetric CSV file and prints classification JSON. |
| `python3 main.py --csv Data/example_data.csv --ph 7.8 --ec 500 --turb 3.0 --temp 24` | Processes CSV with specific field sensor values. |
| `python3 main.py --neural` | Runs the standalone AquaNet neural network benchmark scenarios. |
| `python3 main.py --version` | Displays architecture topology and installed versions. |

---

## 6. Embedded Microcontroller Deployment (C99 Engine)

If you are deploying AquaSentry on embedded hardware (ESP32, STM32, Arduino, or ARM Cortex-M):

1. The C99 files are located in:
   * Header: `Neural_Network/aquanet_v1.h`
   * Implementation: `Neural_Network/aquanet_v1.c`
2. **Compilation**:
   The engine is written in standard ANSI C99 with **zero dynamic memory allocations** (`malloc`). It compiles with zero warnings:
   ```bash
   cd Neural_Network
   clang -std=c99 -Wall -Wextra -Werror -c aquanet_v1.c
   ```
3. **Firmware Integration Example**:
   ```c
   #include "aquanet_v1.h"

   AquaNetReading reading = {
       .arsenic_mg_l       = 0.0074f,
       .ph                 = 7.2f,
       .conductivity_us_cm = 400.0f,
       .turbidity_ntu      = 2.0f,
       .temperature_c      = 24.0f
   };

   AquaNetResult result;
   aquanet_predict(&reading, &result);

   // result.predicted_class: 0 = Safe, 1 = Caution, 2 = Unsafe, 3 = Hazardous
   // result.confidence_pct:  Confidence percentage (0.0 to 100.0)
   ```

---

## 7. Standards Compliance & Potability Limits

The platform adheres to international drinking water health standards:

| Standard / Parameter | Threshold | Safety Enforcement |
| :--- | :--- | :--- |
| **WHO Arsenic Guideline** | $0.010\text{ mg/L}$ ($10\ \mu\text{g/L}$) | Caution triggered if exceeded. |
| **IS 10500 (Amd. 1, 2015)** | $0.010\text{ mg/L}$ ($10\ \mu\text{g/L}$), no relaxation | Any detected arsenic ($\ge$ 20 µg/L LOD) forces at least `Unsafe`. Downgrades prohibited. |
| **Acute Toxic Hazard** | $> 0.150\text{ mg/L}$ ($150\ \mu\text{g/L}$) | Hard override forces `Hazardous`. |
| **Method Limit of Detection** | $0.020\text{ mg/L}$ ($20\ \mu\text{g/L}$) | Analytical notice attached to output. |
| **Drinking Water pH** | $6.5 - 8.5$ | Violations trigger potability downgrade. |
| **Drinking Water Turbidity**| $\le 5.0\text{ NTU}$ | $> 5.0\text{ NTU}$ triggers potability downgrade. |
| **Conductivity (TDS)** | $\le 1500\ \mu\text{S/cm}$ | $> 1500\ \mu\text{S/cm}$ triggers potability downgrade. |

---

## 8. Troubleshooting & FAQs

* **Q: The terminal says `python3: command not found` or `python: command not found`.**  
  *Fix*: Install Python 3.9+ from [python.org](https://www.python.org/downloads/) and ensure you check *"Add Python to PATH"* during installation on Windows.
* **Q: The server says `Port 8000 is already in use`.**  
  *Fix*: Start on an alternative port by running: `python3 main.py --serve --port 8080`.
* **Q: On macOS/Linux, I get `permission denied: ./setup_and_run.sh`.**  
  *Fix*: Make the script executable by running: `chmod +x setup_and_run.sh run_all_tests.sh`.
* **Q: How do I stop the web server?**  
  *Fix*: Press `Ctrl + C` in the terminal window where the server is running.
