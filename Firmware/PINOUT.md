# Pin assignments and parts — one table (ISEF items 52, 170, 176)

Taken from the `#define`s at the top of `esp32_firmware/esp32_firmware.ino` (firmware 5.11.0). Change a pin there,
not here; a test (`tests/test_firmware_host_build.py`) checks that no profile uses a flash, PSRAM or ADC2 pin.

## Core (always fitted)

| Function | ESP32 | ESP32-S3 | ESP32-C3 | ESP32-C6 | Part | Notes |
|---|---|---|---|---|---|---|
| I²C SDA | 21 | 8 | 6 | 23 | ADS1115 (0x48), MCP4725 (0x60) | 400 kHz; bus recovery pulses on boot |
| I²C SCL | 22 | 9 | 7 | 22 | same | |
| Bubble / liquid sense | 34 (ADC1_CH6) | 4 (ADC1_CH3) | 3 (ADC1_CH3) | 2 (ADC1_CH2) | IR phototransistor pair | ADC1 only: ADC2 dies with Wi-Fi on |
| Status LED | 2 (onboard) | 2 | 10 | 21 (GPIO 8 is the RGB LED) | LED | on during a scan; off at idle; see legend below |
| Stepper STEP | 25 | 5 | 4 | 18 | A4988 + NEMA-type pump stepper | |
| Stepper DIR | 26 | 6 | 5 | 19 | A4988 | |
| Stepper ENABLE | 27 | 7 | 1 | 20 | A4988 | active LOW |
| Potentiostat cell | — | — | — | — | working: gold strip; reference: Ag/AgCl; counter: Pt/carbon | DAC drives the potential through the front end; ADC reads the current-to-voltage output |

## Optional (default −1 = not fitted; set the `#define` to a pin to enable)

| `#define` | Function | Suggested pin (ESP32 / S3 / C3) | Part | Conditioning constants |
|---|---|---|---|---|
| `PIN_BATTERY_ADC` | battery voltage | 35 / 1 / 0 | divider on the Li-ion cell | `BATTERY_DIVIDER 2.0` |
| `PIN_REAGENT_PUMP` | pre-reduction reagent pump (total arsenic) | 13 / 15 / — | small DC pump via MOSFET | `REAGENT_PUMP_MS 1500`, `REAGENT_MIX_MS 30000` |
| `PIN_TEMP_NTC` | water temperature | 32 / 10 / — | 10 kΩ NTC | `NTC_R25 10000`, `NTC_BETA 3950`, `NTC_SERIES 10000` |
| `PIN_PH_ADC` | pH | 36 / 1 / — | analogue pH board | `PH_DIVIDER 1.5`, `PH_MV_AT_7 2500`, `PH_MV_AT_4 3030` |
| `PIN_EC_ADC` | conductivity | — | EC board | `EC_DIVIDER 1.0`, `EC_CELL_K 1.0` |
| `PIN_TURBIDITY_ADC` | turbidity | — | optical turbidity board | `TURBIDITY_DIVIDER 1.5` |

Every optional sensor must pass its check against a standard (`POST /api/qc/runs`, `run_type` = `ph_buffer`,
`conductivity_standard`, `turbidity_standard`, `temperature_reference`) before its values are shown as verified.

## Status LED legend (print on the lid, item 175)

| LED | Meaning |
|---|---|
| off | idle / asleep |
| steady on | scan in progress — do not move the cell |
| short blinks on boot | self-test running; results on the serial console and `/status.json` |

## Build options that change behaviour

`LOW_POWER_MODE`, `PULL_OTA`, `COPPER_CHECK`, `TRACE_UPLOAD`, `ALLOW_INSECURE_TLS` — see `Firmware/README.md`.
CI compiles eight combinations for the three chips.
