# AquaSentry Pro / Household Tank Sentry — ESP32 Production Firmware

This directory contains the production firmware for the AquaSentry autonomous water quality surveillance system.

**Supported boards:** ESP32 (WROOM/WROVER DevKit), ESP32-S3 and ESP32-C3, with Espressif's Arduino core 2.0.x or 3.x. The sketch picks pins and CPU cores for the chip you select in the IDE. Every push is compiled for all three chips in GitHub Actions (job `firmware`), and `python main.py --test` type-checks the sketch on your PC (`Firmware/host_check/`).

## Key Features & Architecture
- **Dual-Core FreeRTOS Architecture**:
  - **Core 0 (Telemetry Task)**: Wi-Fi management, HTTP REST telemetry client, Web Browser OTA updates at `http://<ip>/update`, the setup hotspot, the status page and a 1,000-reading offline buffer on LittleFS.
  - **Core 1 (Measurement Task)**: High-precision Anodic Stripping Voltammetry (ASV) sweep timing, ADS1115 16-bit differential ADC readout, MCP4725 12-bit DAC potential generator, A4988 stepper pump intake, optical dry-run/bubble safety gate, and local AquaNet-V3 AI inference.
- **Electrochemical Conditioning**: +1.200 V pre-cleaning pulse for 2.0 seconds prior to cathodic deposition to strip biofouling and contaminants from the electrode surface.
- **I2C 9-Pulse Bus Recovery**: Automatic hardware clock cycling to release hung I2C slave devices.
- **Peristaltic Tubing Anti-Set**: 1/4-turn ($90^\circ$) reverse stroke after each purge to release roller compression on silicone tubing.
- **Adaptive re-scanning**: every test starts with **3 voltammetry scans** (`SCANS_PER_READING`). If the averaged arsenic reading is within 2 standard errors (`RESCAN_Z`) of 10, 20 or 150 µg/L (the 10 µg/L IS 10500 / WHO limit, the 20 µg/L detection limit above which arsenic counts as detected, and the hazard level), the board takes 3 more scans, and again up to 9 (`MAX_SCANS_PER_READING`). Clear readings finish in about 3½ minutes; borderline ones take up to about 10½. In simulation this lifts overall accuracy from 93.4% to 94.6% for about 1.5× the average scan time. The Serial Monitor shows `close to a limit ... scanning again` when it happens.
- **Local Edge AI Inference (AquaNet-V3)**: after scanning, the board runs `aquanet_v3_predict()` on the ESP32 itself — no Wi-Fi or cloud needed. The network is a trained 5-16-12-4 model: 352 float32 weights (1.4 KB of flash), no `malloc`, under 200 bytes of stack, only `<math.h>`. The same safety rules as the server are applied afterwards and can only make the verdict stricter. The old hand-built V1 engine (`aquanet_v1.c`) is kept because V3 reuses its result type and entropy function.

## Hardware Pinout
| Function | ESP32 | ESP32-S3 | ESP32-C3 | Connected Component |
| :--- | :--- | :--- | :--- | :--- |
| **I2C SDA** | GPIO 21 | GPIO 8 | GPIO 6 | ADS1115 ADC & MCP4725 DAC |
| **I2C SCL** | GPIO 22 | GPIO 9 | GPIO 7 | ADS1115 ADC & MCP4725 DAC |
| **Optical Bubble Sense** | GPIO 34 (ADC1) | GPIO 4 (ADC1) | GPIO 3 (ADC1) | Phototransistor / IR Liquid Detector |
| **Status LED** | GPIO 2 | GPIO 2 | GPIO 10 | LED |
| **Stepper STEP** | GPIO 25 | GPIO 5 | GPIO 4 | A4988 Stepper Driver |
| **Stepper DIR** | GPIO 26 | GPIO 6 | GPIO 5 | A4988 Stepper Driver |
| **Stepper ENABLE** | GPIO 27 | GPIO 7 | GPIO 1 | A4988 Driver (Active LOW) |

No pin is a flash/PSRAM pin or (apart from the onboard LED on GPIO 2) a strapping pin, and the bubble sensor is always on **ADC1**: ADC2 pins stop working while Wi-Fi is on. On single-core chips (ESP32-C3) the measurement task runs on core 0. A test checks these rules for every profile.

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

**PlatformIO instead of the Arduino IDE:** open the `Firmware/` folder in VS Code with the PlatformIO extension and pick `esp32dev`, `esp32-s3` or `esp32-c3` (`platformio.ini`).

## Setup without reflashing
You do not have to edit the sketch for Wi-Fi at all. If no Wi-Fi is set, or the board cannot join it within 45 seconds, it opens its own hotspot **`AquaSentry-XXXX`**. The password (unique per board, from its MAC address) is printed on the Serial Monitor. Join it from your phone, open **http://192.168.4.1/setup**, and enter your Wi-Fi, the server address, the device name and the API key. They are saved in flash, take priority over the defaults in the sketch, and survive firmware updates. Measurements continue (and are buffered) while the hotspot is open.

On your own network the same page is available at `http://<device-ip>/setup`, but only after you change `OTA_PASS`, and it asks for that login.

## Status page
`http://<device-ip>/` shows firmware, Wi-Fi signal, server address, readings waiting to upload and the last result. **`/status.json`** gives the same as JSON (device code, firmware version, board, uptime, RSSI, buffered and dropped readings, last arsenic value and verdict, free heap, whether the server address is https, battery percent and millivolts, low-power mode and the number of wake-ups).

## Offline buffer
Readings that cannot be uploaded are kept in a fixed-size ring file on **LittleFS** (`/offline.bin`, 1,000 readings, about six weeks of hourly tests). The older firmware kept 500 in NVS, but NVS is meant for small settings, the default NVS partition is shared with Wi-Fi, and it filled up after roughly a hundred readings without any error. LittleFS uses the `spiffs` partition of the default partition scheme and is formatted automatically the first time. If it cannot be mounted the board falls back to a 24-reading RAM buffer and says so.

## Start the server so the ESP32 can reach it
The server must listen on your network, not just on your PC:
- Double-click **`Start AquaSentry for ESP32.bat`** (in the package root), **or**
- run `python main.py --serve --host 0.0.0.0 --port 8000`.

Allow Python through Windows Firewall on **Private** networks when asked. The network-mode launcher prints the exact `BACKEND_API_URL` to use.

## What the firmware sends
`POST /api/readings` with JSON in the format the server expects:
`{"device_code":"TANK-001","arsenic_concentration_mg_l":0.0371,"source_type":"hardware","source_label":"ESP32 node","idempotency_key":"TANK-001-42","firmware_version":"5.6.0","recorded_at":"2026-11-08T04:00:12Z", ...}`.
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

## Optional features (all off by default)
Set them near the top of the sketch, or as build flags (PlatformIO: the `esp32dev-lowpower` environment, or `build_flags = -DLOW_POWER_MODE=1 -DPIN_BATTERY_ADC=35`).

| Feature | Setting | What it does |
| --- | --- | --- |
| **HTTPS** | `https://...` server address + `ROOT_CA_PEM` | Uploads over TLS and checks the server certificate and host name. Without a certificate the node does **not** send (readings wait in the offline buffer) unless `ALLOW_INSECURE_TLS 1`, which encrypts but cannot tell the real server from an impostor. |
| **Battery monitor** | `PIN_BATTERY_ADC`, `BATTERY_DIVIDER` | Reads the cell through a resistor divider (two equal resistors, `BATTERY_DIVIDER 2.0`) on an ADC1 pin: 35 on ESP32, 1 on S3, 0 on C3. Sends `battery_pct` with every reading (resting Li-ion curve, read before the pump starts) and shows it on `/status.json`. |
| **Low-power mode** | `LOW_POWER_MODE 1` | Deep-sleeps between tests (chip about 10 µA). After a test it stays awake up to 90 s (`LOW_POWER_AWAKE_MS`) to upload it and the offline backlog, then sleeps for the rest of the hour. Pages and OTA work only while it is awake; it never sleeps while the setup hotspot is open. **Fit a 10 kΩ pull-up from the A4988 EN pin to 3.3 V**: Pololu-style boards pull EN low (motor ON) and the pin is otherwise floating during sleep. The firmware also holds EN high through sleep (`gpio_hold_en`, plus `gpio_deep_sleep_hold_en` on C3/S3). |

For HTTPS the `ROOT_CA_PEM` is the certificate of the authority that signed the server's certificate (for Let's Encrypt, *ISRG Root X1*), pasted as a C string with `\n` line endings. The telemetry task has 16 KB of stack for the TLS handshake.

## Measurement quality and sensors (v5.6)

**Total arsenic vs As(III) only.** Groundwater carries arsenic as As(III) and As(V). On a gold electrode, As(V) gives no signal until the sample is acidified with a reducing supporting electrolyte (Metrohm's method uses sulfamic acid, citric acid and KCl). Without that step the node measures **As(III) only** and says so (`"arsenic_species":"as3_only"`); the server then warns that the number can be too low and that "No arsenic detected" cannot rule arsenic out. With a small dosing pump switched by a logic-level MOSFET on `PIN_REAGENT_PUMP` (add a 100 kΩ pull-down on the gate), the node reads the other sensors first, doses the electrolyte (`REAGENT_PUMP_MS`), waits `REAGENT_MIX_MS` and reports total arsenic. **Bench-test the dose, mixing time and deposition potential with As(V) standards before trusting total-arsenic numbers.**

**Copper check.** With `COPPER_CHECK 1` (default) the sweep continues `COPPER_OFFSET_MV` past the arsenic peak and measures the copper peak (`cu_peak_ua`). Copper hides arsenic on gold; the server flags readings where copper is more than `COPPER_FLAG_RATIO` (3) times the arsenic peak. Confirm the copper window with one scan of a copper standard.

**Calibration from the server.** At start-up and once a day the node fetches `GET /api/devices/<code>/calibration` (its own calibration, else a global one, else the factory numbers) and stores it in flash. Make calibrations on the dashboard's API: external standards (`POST /api/admin/calibrations/external`) or **standard addition** in the real water (`POST /api/admin/calibrations/standard-addition`), which builds matrix effects into the slope. Each reading says which calibration it used (`calibration_ref`).

**Water-quality sensors** (all optional, `-1` = not fitted, ADC1 pins only; 5 V boards need a divider):

| Sensor | Setting | Notes |
| --- | --- | --- |
| Temperature | `PIN_TEMP_NTC` | 10 kΩ NTC (B 3950) to GND, 10 kΩ from 3.3 V to the pin |
| pH | `PIN_PH_ADC`, `PH_MV_AT_7`, `PH_MV_AT_4`, `PH_DIVIDER` | Two-buffer calibration; the serial monitor prints the board's mV |
| Conductivity | `PIN_EC_ADC`, `EC_DIVIDER`, `EC_CELL_K` | Compensated to 25 °C with the measured temperature |
| Turbidity | `PIN_TURBIDITY_ADC`, `TURBIDITY_DIVIDER` | SEN0189-style curve |

Free pins that are safe to use (ADC1 for the sensors, because ADC2 stops working when Wi-Fi is on):

| Board | Sensors (ADC1) | Reagent pump (output) | Notes |
| --- | --- | --- | --- |
| ESP32 DevKit | NTC 32, pH 36, EC 39, turbidity 33, battery 35 | 13 | `esp32dev-field` environment in `platformio.ini` |
| ESP32-S3 | 10 and 1 (two sensors; battery takes 1) | 15 | GPIO 11-20 are ADC2; GPIO 3 is a strapping pin |
| ESP32-C3 | 0 (one sensor, or the battery) | 0, if no sensor uses it | Only five ADC1 pins and the node already uses three; 2, 8 and 9 are strapping pins. Use an ESP32 or S3 for a full sensor set |

**Updates from the server** (`PULL_OTA 1`). Upload a build: `curl -X POST --data-binary @build/esp32_firmware.ino.bin -H "X-API-Key: <key>" "http://<server>:8000/api/admin/firmware?board=esp32&version=5.6.1"`. Nodes check `/api/firmware/latest` once a day, never during a test, download with an MD5 check and restart. The new build confirms itself after its first successful upload (`esp_ota_mark_app_valid_cancel_rollback`); with a rollback-enabled bootloader, a build that never gets that far is undone.

Buffered readings from firmware 5.2-5.5 are converted to the new 60-byte record on first start; nothing waiting is lost.

## Over-The-Air (OTA) Updates
Navigate to `http://<device-ip>/update` in any web browser and log in with `OTA_USER` / `OTA_PASS` to upload a compiled `.bin` wirelessly. OTA is **disabled while `OTA_PASS` is still `change-me`** (or shorter than 8 characters), so nobody can flash the board with the default login. Pick a long password, then re-flash over USB once.
