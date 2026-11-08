# AquaSentry Platform (server + dashboard)

The FastAPI server, SQLite database and web dashboard of AquaSentry. For the whole project (firmware, neural network, hardware, competition plan) start at the [top-level README](../README.md).

> **Screening, not a certified lab test.** The arsenic method detects down to about **20 µg/L**, which is above the **10 µg/L** limit in WHO guidance and IS 10500 (no relaxation since Amendment 1, 2015). A clean reading therefore says *"No arsenic detected"* and asks for one lab test; it never says "safe to drink". Any arsenic the sensor detects is at least **Unsafe**; above 150 µg/L is **Hazardous**.

## Run it

From the repository root (recommended): `python main.py --serve` and open http://localhost:8000. Every way of running it (desktop window, Windows double-click, Docker, ESP32 on the network, the demo database) is in [`Docs/HOW_TO_RUN.md`](../Docs/HOW_TO_RUN.md).

From this folder:

| What | Command |
| --- | --- |
| Server + dashboard (Windows double-click) | `START_AQUASENTRY.bat` (API on 8000, static pages on 8001) |
| Server + dashboard (macOS / Linux) | `./start_aquasentry.sh` |
| Server only | `python -m uvicorn app.main:app --port 8000` |
| Open the pages without Python | `OPEN_OFFLINE_WEBSITES.bat`, or open `frontend/index.html` |
| Tests | `python run_tests.py` (or `RUN_TESTS.bat`); browser tests: `python -m pytest tests_e2e` |
| Demo field programme | `python scripts/seed_field_demo.py --db demo_field.db`, then `DATABASE_URL=sqlite:///demo_field.db python -m uvicorn app.main:app` |
| Command line tools | `python main.py --csv data/example_data.csv --cal data/calibration.json` (process one scan) |

Settings come from environment variables or a `.env` file; `.env.example` lists every one (API keys, read protection, alerts, Gemini key for the optional assistant). Never commit `.env`.

## What is in this folder

```text
AquaSentry_Platform/
├── app/                     FastAPI application
│   ├── main.py              app setup, readings, devices, dashboard, export/import, chat, health, metrics
│   ├── routers/             science (lab results, validation, calibrations), field (sites, map, QR pages, JJM CSV),
│   │                        alerts (push, WhatsApp, SMS), auth, reports (PDF), firmware (OTA)
│   ├── classification.py    verdict rules; the safety rules run after AquaNet and can only make a verdict stricter
│   ├── standards.py         one place for limits, units and the detection limit
│   ├── quality.py           what the sensor can see (As(III) only, copper interference, calibration age)
│   ├── signal_processing.py voltammetry: smoothing, baseline, peak, calibration
│   ├── aquanet_v3.py        AquaNet-V3 (5-16-12-4, 352 weights); neural_classifier.py = V1
│   ├── trends.py            Mann-Kendall + Sen's slope on daily medians
│   ├── notify.py            Web Push, WhatsApp Cloud API, SMS (MSG91 / Twilio)
│   ├── webhooks.py          signed webhooks (Standard Webhooks) with retries
│   ├── security.py          headers and Content-Security-Policy
│   ├── database.py, models.py, schemas.py, migrations/   SQLite + Alembic
│   └── logs.py, metrics.py, events.py, deps.py           JSON logs, Prometheus, live events, shared dependencies
├── frontend/                dashboard (index.html), device page (device.html), market, sales, device simulator,
│                            translations (English, Hindi, Bengali, Assamese, Punjabi), vendored Leaflet and QR code,
│                            fonts, service worker; legacy_v1/ is the first dashboard, still served for reference
├── data/                    example scans and calibration used by the command line tools and tests
├── bridge/serial_bridge.py  forwards readings from a USB/Bluetooth serial device to the API
├── scripts/                 training, model install, stress test, demo data, PDF export, maintenance
├── tests/                   unit and API tests        tests_e2e/  browser tests + accessibility audit
├── aquasentry.db            starter database (test, imported and demo readings only; no real field data)
└── alembic.ini, requirements.txt, main.py, run_tests.py, launchers (.bat / .sh)
```

The same AquaNet code and weights also live in `../Neural_Network/` (training and stand-alone toolkit) and `../Firmware/esp32_firmware/` (C for the ESP32). They are kept as copies on purpose so each part runs on its own; `tests/test_repo_layout.py` fails if the copies ever differ.

## API in one table

Interactive documentation is at http://localhost:8000/docs when the server runs.

| Area | Endpoints |
| --- | --- |
| Readings | `POST /api/readings` (from devices, idempotent), `GET /api/readings`, `/latest`, `/history`, `GET /api/dashboard/latest`, `GET /api/stats` |
| Devices | `GET /api/devices`, `/api/devices/{code}`, `/api/devices/{code}/trend`, `/api/devices/{code}/calibration`, `PUT /api/admin/devices/{code}/site`, device keys under `/api/admin/devices/{code}/key` |
| Lab and calibration | `POST/GET /api/lab-results`, `GET /api/validation`, `POST /api/admin/calibrations/external`, `/standard-addition`, `GET /api/calibrations` |
| Field programme | `GET /api/public/devices/{code}` (QR page), `GET /api/data/export/jjm`, `GET /api/data/export`, import preview/commit |
| Alerts | `GET /api/alerts/recent`, `/api/alerts/channels`, Web Push subscribe/unsubscribe, admin subscriptions and test |
| Science tools | `POST /api/voltammetry/process`, `GET /api/voltammetry/sample-trace`, `/api/neural/inference`, `/api/neural/v3`, `/api/analytes` |
| Reports | `GET /api/reports/certificate/pdf` (screening report, not a lab certificate) |
| Firmware | `POST /api/admin/firmware`, `GET /api/firmware/latest`, `/api/firmware/download/{board}/{version}` |
| Operations | `GET /api/health`, `/api/metrics` (Prometheus), `/api/events` (live updates), `POST /api/admin/backup`, `/api/admin/db/compact`, auth login/logout/status, `POST /api/chat` |

The older description of this folder (v1, with the catamaran-first framing and the withdrawn 50 µg/L limit) is kept in [`Docs/archive/PLATFORM_README_v1.md`](../Docs/archive/PLATFORM_README_v1.md).
