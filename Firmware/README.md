# AquaSentry Pro / Household Tank Sentry — ESP32 Production Firmware

This directory contains the production firmware for the AquaSentry autonomous water quality surveillance system.

## Key Features & Architecture
- **Dual-Core FreeRTOS Architecture**:
  - **Core 0 (Telemetry Task)**: Wi-Fi management, HTTP REST telemetry client, Web Browser OTA updates at `http://<ip>/update`, and 500-sample offline NVS flash circular buffer synchronization.
  - **Core 1 (Measurement Task)**: High-precision Anodic Stripping Voltammetry (ASV) sweep timing, ADS1115 16-bit differential ADC readout, MCP4725 12-bit DAC potential generator, A4988 stepper pump intake, optical dry-run/bubble safety gate, and local AquaNet-V3 AI inference.
- **Electrochemical Conditioning**: +1.200 V pre-cleaning pulse for 2.0 seconds prior to cathodic deposition to strip biofouling and contaminants from the electrode surface.
- **I2C 9-Pulse Bus Recovery**: Automatic hardware clock cycling to release hung I2C slave devices.
- **Peristaltic Tubing Anti-Set**: 1/4-turn ($90^\circ$) reverse stroke after each purge to release roller compression on silicone tubing.
- **Adaptive re-scanning**: every test starts with **3 voltammetry scans** (`SCANS_PER_READING`). If the averaged arsenic reading is within 2 standard errors (`RESCAN_Z`) of 10, 20 or 150 µg/L (the 10 µg/L IS 10500 / WHO limit, the 20 µg/L detection limit above which arsenic counts as detected, and the hazard level), the board takes 3 more scans, and again up to 9 (`MAX_SCANS_PER_READING`). Clear readings finish in about 3½ minutes; borderline ones take up to about 10½. In simulation this lifts overall accuracy from 93.4% to 94.6% for about 1.5× the average scan time. The Serial Monitor shows `close to a limit ... scanning again` when it happens.
- **Local Edge AI Inference (AquaNet-V3)**: after scanning, the board runs `aquanet_v3_predict()` on the ESP32 itself — no Wi-Fi or cloud needed. The network is a trained 5-16-12-4 model: 352 float32 weights (1.4 KB of flash), no `malloc`, under 200 bytes of stack, only `<math.h>`. The same safety rules as the server are applied afterwards and can only make the verdict stricter. The old hand-built V1 engine (`aquanet_v1.c`) is kept because V3 reuses its result type and entropy function.

## Hardware Pinout
| Function | ESP32 GPIO | Connected Component |
| :--- | :--- | :--- |
| **I2C SDA** | GPIO 21 | ADS1115 ADC & MCP4725 DAC |
| **I2C SCL** | GPIO 22 | ADS1115 ADC & MCP4725 DAC |
| **Optical Bubble Sense** | GPIO 34 (ADC1) | Phototransistor / IR Liquid Detector |
| **Status LED** | GPIO 2 | Blue Onboard LED |
| **Stepper STEP** | GPIO 25 | A4988 Stepper Driver |
| **Stepper DIR** | GPIO 26 | A4988 Stepper Driver |
| **Stepper ENABLE** | GPIO 27 | A4988 Driver (Active LOW) |

## Flashing Instructions
1. Open **`Firmware/esp32_firmware/esp32_firmware.ino`** in the **Arduino IDE** (or PlatformIO). The Arduino IDE needs the sketch to sit in a folder with the same name, so keep the folder `esp32_firmware` as it is.
2. Install the **ESP32 by Espressif Systems** board package (`Tools -> Board -> ESP32 Arduino -> ESP32 Dev Module`).
3. Keep `aquanet_v3.c`, `aquanet_v3.h`, `aquanet_v1.c` and `aquanet_v1.h` in the same folder as `esp32_firmware.ino` (they already are). The Arduino IDE compiles them automatically.
4. Edit the block marked **CHANGE THESE BEFORE FLASHING** near the top of the sketch:
   ```cpp
   const char* WIFI_SSID        = "YOUR_WIFI_NAME";
   const char* WIFI_PASS        = "YOUR_WIFI_PASSWORD";
   const char* BACKEND_API_URL  = "http://<your PC's IPv4 address>:8000/api/readings";
   const char* DEVICE_CODE      = "TANK-001";
   const char* OTA_USER         = "admin";
   const char* OTA_PASS         = "change-me";   // OTA is disabled until you change this
   const char* DEVICE_API_KEY   = "";            // same value as AQUASENTRY_API_KEY in the server's .env
   ```
5. Connect the ESP32 by USB, pick its port, and click **Upload**.
6. Open the Serial Monitor at **115200** baud. The board prints its IP address once Wi-Fi connects.

## Start the server so the ESP32 can reach it
The server must listen on your network, not just on your PC:
- Double-click **`Start AquaSentry for ESP32.bat`** (in the package root), **or**
- run `python main.py --serve --host 0.0.0.0 --port 8000`.

Allow Python through Windows Firewall on **Private** networks when asked. The network-mode launcher prints the exact `BACKEND_API_URL` to use.

## What the firmware sends
`POST /api/readings` with JSON in the format the server expects:
`{"device_code":"TANK-001","arsenic_concentration_mg_l":0.0371,"source_type":"hardware","source_label":"ESP32 node","idempotency_key":"TANK-001-42", ...}`.
pH, conductivity, turbidity and temperature are included **only** when you fit those sensors. Write the code in `read_ph()`, `read_conductivity()`, `read_turbidity()` and `read_temperature()`; until then they return NAN and are not sent. The idempotency key stops a reading that is re-sent from the offline buffer from being stored twice.

Once Wi-Fi connects the board sets its clock by NTP, and each reading carries `"recorded_at"` (UTC), so readings buffered while offline keep the time they were taken. If the server sets `AQUASENTRY_API_KEY`, put the same value in `DEVICE_API_KEY`; the board sends it as the `X-API-Key` header. A reading the server rejects for good (any 4xx except 408/429, e.g. bad data or a wrong key) is logged and dropped instead of blocking the offline queue forever.

## How arsenic is measured (same maths as the server)
Clean at +1.2 V (2 s), deposit at −1.1 V (60 s), then sweep −1100 → −500 mV in 5 mV steps. Then:
- smooth with a 5-point Savitzky-Golay filter
- fit a straight background line outside −905 … −695 mV and subtract it
- take the highest net current between −860 and −740 mV
- convert: arsenic (mg/L) = (peak µA − 0.0096) ÷ 0.8563

These values match `AquaSentry_Platform/app/standards.py` and `signal_processing.py`. If you use a different electrode, recalibrate it and change both files.

## Changing the neural network
Never edit `aquanet_v3.c` by hand. To put a newly trained model on the ESP32, run from `AquaSentry_Platform/`:
```
python scripts/install_aquanet_v3.py <new_model.json>
```
This regenerates `aquanet_v3.c/.h` here **and** updates the server and dashboard with the same weights, so all three always agree. Then re-flash the ESP32. The test `tests/test_aquanet_v3.py` compiles this C file and checks it against Python on 3,000 inputs.

## Troubleshooting (Serial Monitor messages)
| Message | Meaning |
| --- | --- |
| No `[WIFI] Connected!` | Wrong Wi-Fi name/password, or out of range |
| `[HTTP] POST failed (-1)` | Server not reachable: wrong IP, server not started with `--host 0.0.0.0`, or blocked by the firewall |
| `[HTTP] POST failed (422)` | Server rejected the data: the server and firmware versions don't match |
| `[SAFETY] ABORTING ASV` | No water detected in the sample chamber |
| `[ASV] Too few points recorded` | DAC/ADC wiring problem (check I2C on GPIO 21/22) |

## Over-The-Air (OTA) Updates
Navigate to `http://<device-ip>/update` in any web browser and log in with `OTA_USER` / `OTA_PASS` to upload a compiled `.bin` wirelessly. OTA is **disabled while `OTA_PASS` is still `change-me`**, so nobody can flash the board with the default login. Pick a long password, then re-flash over USB once.
