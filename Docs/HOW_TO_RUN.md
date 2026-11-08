# How to run AquaSentry

This guide replaces `WHATS_NEW_AND_HOW_TO_RUN.md` (v5.1) and `START_HERE_OPERATIONS_GUIDE.md` (v1). Both originals are kept in [`archive/`](archive/). Paths are from the repository root.

## What you need

- **Python 3.10 or newer** (python.org; on Windows tick **"Add python.exe to PATH"** while installing).
- Internet for the first run only (it installs packages into a local `.venv` folder).
- Optional: Docker; an ESP32 board and the Arduino IDE; a Gemini API key for the assistant.

## 1. Desktop app (simplest)

| System | Do this |
| --- | --- |
| Windows | Double-click **`Start AquaSentry Desktop.bat`** |
| macOS / Linux | `chmod +x run_desktop.sh && ./run_desktop.sh` |

The first run creates `.venv` and installs `requirements.txt` + `requirements-desktop.txt` (a few minutes). Later runs open straight away. Close the window to stop it.

If the window does not open (for example Microsoft Edge WebView2 is missing), run `.venv\Scripts\python.exe desktop_app.py --browser` (Windows) or `.venv/bin/python desktop_app.py --browser` to use your normal browser instead.

**Standalone .exe (Windows, optional):** after one normal run, double-click `scripts\build_desktop_exe.bat`. The app appears in `dist\AquaSentry\AquaSentry.exe`; copy the whole `dist\AquaSentry` folder to share it with someone who has no Python.

## 2. In the browser

| System | Do this |
| --- | --- |
| Windows | Double-click `scripts\setup_and_run.bat` |
| macOS / Linux | `./scripts/setup_and_run.sh` |
| Any, by hand | `python -m venv .venv`, activate it (`source .venv/bin/activate`, or `.venv\Scripts\activate.bat`), `pip install -r requirements.txt`, then `python main.py --serve` |

Then open http://localhost:8000. The API documentation is at http://localhost:8000/docs. Stop the server with **Ctrl+C**.

Port already in use: `python main.py --serve --port 8080`.

## 3. Docker

```bash
docker compose up -d        # then open http://localhost:8000
```

The database lives in the `aquasentry-data` volume, so it survives updates. Put settings (`AQUASENTRY_API_KEY` and the others from `AquaSentry_Platform/.env.example`) in a `.env` file next to `docker-compose.yml`. The container runs as a non-root user with a read-only file system and a health check.

## 4. With an ESP32 on your Wi-Fi

1. Start the server so other devices can reach it: **`Start AquaSentry for ESP32.bat`** (Windows) or `python main.py --serve --host 0.0.0.0 --port 8000`. The Windows launcher prints the address to use.
2. Open `Firmware/esp32_firmware/esp32_firmware.ino` in the Arduino IDE, fill in the **CHANGE THESE BEFORE FLASHING** block (Wi-Fi, server address, optional API key) and upload. Or flash it, join the node's setup hotspot and enter the settings there.
3. Watch the Serial Monitor at 115200 baud. Pins, options (low power, HTTPS, copper scan, dosing pump, OTA) and a troubleshooting table: [`Firmware/README.md`](../Firmware/README.md).

## 5. Demo data for presentations

The demo writes to a **separate** database and refuses to touch `aquasentry.db`:

```bash
cd AquaSentry_Platform
python scripts/seed_field_demo.py --db demo_field.db
DATABASE_URL=sqlite:///demo_field.db python -m uvicorn app.main:app --port 8000
```

Windows (PowerShell): `$env:DATABASE_URL="sqlite:///demo_field.db"; python -m uvicorn app.main:app --port 8000`.

It creates six nodes in the arsenic belt with 30 days of readings, lab confirmations (one sample the sensor missed, so the validation panel shows the honest picture), a standard-addition calibration, a low battery and a silent node. Every code starts with `DEMO-` and every reading is labelled *SIMULATED FIELD DEMO*. Never show it as real data.

## 6. Command line

| Command | What it does |
| --- | --- |
| `python main.py --serve [--host 0.0.0.0] [--port 8000] [--reload]` | Web platform and API |
| `python main.py --test` | Every test (neural toolkit + platform) |
| `python main.py --csv Data/example_data.csv [--cal Data/calibration.json]` | Process one voltammetry scan and classify it |
| `python main.py --csv Data/example_data.csv --ph 7.8 --ec 500 --turb 3.0 --temp 24` | Same, with field sensor values |
| `python main.py --neural` | Neural-network toolkit demo scenarios |
| `python main.py --version` | Versions and model sizes |

## 7. Tests and checks

| What | Command |
| --- | --- |
| All unit/API tests | `python main.py --test`, or `./scripts/run_all_tests.sh` / `scripts\run_all_tests.bat` |
| Platform only | `cd AquaSentry_Platform && python run_tests.py` |
| Browser tests | `cd AquaSentry_Platform && pip install playwright && python -m playwright install chromium && python -m pytest tests_e2e` |
| + WCAG 2.2 AA audit | `npm i axe-core`, then set `AXE_PATH` to `node_modules/axe-core/axe.min.js` before running the browser tests |
| Lint | `ruff check .` |
| Firmware compile (host stubs) | part of the platform tests (`tests/test_firmware_host_build.py`); real ESP32 builds run in GitHub Actions |

## 8. VS Code

1. **File → Open Folder** and pick the repository folder; accept the recommended Python extension.
2. Run the desktop launcher once so `.venv` exists, then **Ctrl+Shift+P → Python: Select Interpreter → .venv**.
3. **Run and Debug** (Ctrl+Shift+D) has three launch options: *Desktop app*, *Open in browser*, *Server only (port 8000)*.

## 9. Optional settings

- **Assistant:** copy `AquaSentry_Platform/.env.example` to `AquaSentry_Platform/.env` and add your own Gemini key. Without a key it answers from your own readings (offline mode).
- **Write protection:** set `AQUASENTRY_API_KEY`; devices send it as `X-API-Key`. Per-device keys are under `/api/admin/devices/{code}/key`.
- **Alerts to phones:** Web Push works out of the box; WhatsApp and SMS need provider keys (see `.env.example`).
- `.env` is in `.gitignore`. Never commit API keys.

## 10. Troubleshooting

| Problem | Fix |
| --- | --- |
| `python` / `python3` not found | Install Python 3.10+ and tick *Add to PATH* (Windows), then open a new terminal. |
| `permission denied: ./scripts/setup_and_run.sh` | `chmod +x scripts/*.sh run_desktop.sh` |
| Port 8000 in use | `python main.py --serve --port 8080` |
| Package install fails | Check the internet connection, then delete `.venv` and run the launcher again. |
| ESP32 cannot reach the server | Use the PC's LAN address (not `localhost`), start with `--host 0.0.0.0`, allow Python through the firewall. More in `Firmware/README.md`. |
| Desktop window blank | Use `--browser` (section 1). |
