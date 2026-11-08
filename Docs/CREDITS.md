# Credits and licences

ISEF items 11, 45, 255: every contribution, library and reused method credited; unpublished data from others needs
written permission.

## People

| Who | What | Status |
|---|---|---|
| Yashveer Singh Garewal | Project lead; repository owner | team |
| Nalin Aggarwal | v5.2–v5.7 branches (standards fix, firmware hardening, fleet API, alerts, lab results, calibration, ISEF roadmap) — see `git log` | contributor |
| Claude (Anthropic) | AI assistant used for code, tests and documentation drafts — see `Docs/AI_USE_STATEMENT_TEMPLATE.md` | tool |
| Mentors, laboratory staff, PHED contacts | *add name, institution, what they advised vs what you did* | to add |

## Software libraries

| Library | Use | Licence |
|---|---|---|
| FastAPI, Starlette, Uvicorn | HTTP server | MIT / BSD |
| SQLAlchemy, Alembic | database and migrations | MIT |
| Pydantic | request validation | MIT |
| ReportLab | PDF certificates and the QR figure | BSD |
| NumPy | analysis scripts | BSD |
| pywebpush | browser push alerts | MPL-2.0 |
| requests, httpx, pyserial, python-dotenv, pypdf, pytest | bridge, tests, tooling | Apache-2.0 / BSD / MIT |
| google-genai | optional chatbot (off without a key) | Apache-2.0 |
| Leaflet 1.9.4 | dashboard map (`frontend/vendor/`) | BSD-2-Clause |
| OpenStreetMap tiles | map background | ODbL — attribution shown on the map |
| qrcode-generator 1.4.4 (Kazuhiko Arase) | QR stickers in the browser | MIT |
| Arduino-ESP32 core, LittleFS, Preferences, HTTPUpdate | firmware | LGPL-2.1 / Apache-2.0 |
| Playwright, axe-core | browser and accessibility tests | Apache-2.0 / MPL-2.0 |
| Lato (Google Fonts) | dashboard typeface | OFL |

## Methods and standards reused

- Square-wave anodic stripping voltammetry on gold for As(III): standard electroanalytical method; the peak-finding
  pipeline (`app/signal_processing.py`) uses Savitzky–Golay smoothing and a robust (MAD-clipped) linear baseline.
- Limits: IS 10500:2012 Amendment 1 (2015); WHO Guidelines for Drinking-water Quality (4th ed., arsenic 10 µg/L).
- LOD = 3.3·σ/slope and LOQ = 10·σ/slope (ICH / IUPAC convention).
- Deming regression, Bland–Altman limits of agreement, Wilson score interval, Western Electric control-chart rules,
  split-conformal prediction intervals, Mann–Kendall trend test with Sen's slope (standard references).
- Bullen et al. (2022), PLoS ONE — open-source potentiostat arsenic work, used as a comparison point only.

## Hardware design

- 3D models in `models_3d/` are the team's own; choose and state a hardware licence (CERN-OHL-P recommended, item 255).
- Electrode strips, ADC (ADS1115) and DAC (MCP4725) are commercial parts; part numbers in `Firmware/PINOUT.md`.

## Data

- Every dataset shipped in this repository is synthetic and labelled so (`Data/`, `Analysis/*.py --demo`).
- Field data belongs to the team and the source owners; deposit it with a DOI (Zenodo/OSF) before the fair (item 147).
