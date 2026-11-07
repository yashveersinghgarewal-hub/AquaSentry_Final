# AquaSentry v5 — what's new and how to run it

This package replaces `AquaSentry.zip`, `AquaSentry_v2.zip`, `AquaSentry_v3.zip`, `AquaSentry_v3.1.zip`, `AquaSentry_v4.zip` and `AquaSentry_v4.1.zip`. Use this one. What changed in each version: **`CHANGELOG.md`**. The v3 error fixes, with file and line: **`FIXES_v3.md`**.

## How to run the desktop app (Windows)

1. Install **Python 3.10 or newer** from python.org. During setup, tick **"Add python.exe to PATH"**.
2. Unzip this folder, for example to `C:\Users\<you>\projects\AquaSentry`.
3. Double-click **`Start AquaSentry Desktop.bat`**.
   - First run: it creates a `.venv` folder and installs packages. This takes a few minutes and needs internet.
   - Later runs: it opens straight away.
4. AquaSentry opens in its own window. Close the window to stop it.

If the window doesn't open (for example, Microsoft Edge WebView2 is missing), run this in a terminal in the same folder:
`.venv\Scripts\python.exe desktop_app.py --browser` — it opens in your normal browser instead.

**Make a standalone .exe (optional):** after running the app once, double-click `build_desktop_exe.bat`. The app appears in `dist\AquaSentry\AquaSentry.exe`. Copy the whole `dist\AquaSentry` folder to share it with someone who doesn't have Python.

**macOS / Linux:** `chmod +x run_desktop.sh && ./run_desktop.sh`

## Running it from VS Code

1. **File → Open Folder** and choose the `AquaSentry` folder.
2. Accept the recommended Python extension if VS Code asks.
3. Run `Start AquaSentry Desktop.bat` once so `.venv` exists, then pick that interpreter: **Ctrl+Shift+P → Python: Select Interpreter → .venv**.
4. Open the **Run and Debug** panel (Ctrl+Shift+D). Choose one of the three launch options and press F5:
   - **AquaSentry: Desktop app** — its own window
   - **AquaSentry: Open in browser**
   - **AquaSentry: Server only (port 8000)** — then open http://localhost:8000

## What changed in v5 (compared with v4.1) — the new UI

| Page | What you get |
| --- | --- |
| Live dashboard (`index.html`) | Verdict card with a live water effect that changes colour, arsenic gauge, alert banner, **what to do if arsenic is high**, **contact local authorities** (ready-made incident report: email / copy / share / print, plus who to contact), test a sample, AquaNet, **3D model of the device** (drag to rotate, "Explode view"), contaminants, standards and methods, impact numbers, report. |
| Market research | Market-size globe, unit economics, Year-1 profit chart, competitor table (AquaSentry vs AccuSense vs lab vs field kits), market-size donut, trends, priority regions. |
| Sales & expansion | Revenue model, revenue and fleet charts, **ROI calculator**, go-to-market channels, technology moat, 3-phase roadmap, future hardware. |
| Device simulator | The MAS-G1 meter screen; import real CSV scans and calibration. |

Every page has the same sidebar, theme switch (carbon black / light), English–हिन्दी switch and assistant, and works offline. Your local water-department phone and email can be saved under *Contact authorities → Your local contacts*; they stay on that device only.

**Files:** new `shell.js`, `charts.js`, `device3d.js`, `device3d-data.js`, `globe.js`, `pages.js`, `i18n-v5.js`, `i18n-pages.js`, `device-simulator.html`, `mas-g1-display.html`, fonts Sora + JetBrains Mono; rewritten `index.html`, `app.js`, `app.css`, `market-research.html`, `sales-expansion.html`; small additions to `i18n.js` and `neural.js`; removed `website` (now `device-simulator.html`); new `scripts/stl_to_js.py`.
**Not changed:** AquaNet weights, firmware, server API, database, tests.

## What changed in v4.1 (compared with v4)

| Area | File | Change |
| --- | --- | --- |
| ESP32 | `Firmware/esp32_firmware/esp32_firmware.ino` | **Adaptive re-scanning.** New settings `MAX_SCANS_PER_READING` (9) and `RESCAN_Z` (2.0) next to `SCANS_PER_READING`, two small helper functions (`arsenic_ug_from_peak`, `arsenic_near_limit`), and the scan loop in step 5 now adds 3 more scans while the reading is close to 10 / 50 / 150 µg/L. Overall accuracy in simulation: 93.4% → **94.6%**. |
| Tests | `AquaSentry_Platform/tests/test_aquanet_v3.py` | 2 new tests: the firmware's re-scan settings match the training code, and its C re-scan rule matches Python on 3,000 readings. 110 tests in total. |
| Training | `Neural_Network/v3_training/train_v3.py`, new `eval_adaptive.py` | `ADAPTIVE=1` trains/tests with the firmware's re-scan rule. The "loss" note saved in model files now shows the real class weights. |
| Docs | `Docs/AQUANET_V3_REPORT.md` (new *Result 3*), `Firmware/README.md`, `CHANGELOG.md`, this file, test counts in `README.md`, `main.py`, `run_all_tests.*`, `START_HERE_OPERATIONS_GUIDE.md`, `AQUASENTRY_CODE_GUIDE.md`, `ci.yml` | Updated. |

**Not changed in v4.1:** the installed neural network (same weights as v4 — 8 further training runs, including ones trained on adaptive-scan readings, did not beat it), the server, the dashboard, the database, the C engine `aquanet_v3.c/.h`, the voltammetry maths and calibration.

## What changed in v4 (and what didn't)

| Area | Files | Change |
| --- | --- | --- |
| Neural network | `Neural_Network/aquanet_v3.py`, `aquanet_v3_weights.json`, `v3_training/`; `AquaSentry_Platform/app/aquanet_v3.py`, `app/aquanet_v3_weights.json` | New **AquaNet-V3** (5-16-12-4), trained with realistic sensor noise. Now the default everywhere. Results: `Docs/AQUANET_V3_REPORT.md`. |
| Server | `app/classification.py`, `app/main.py` | Uses V3 by default (`AQUANET_MODEL=v1` switches back). New read-only route `GET /api/neural/v3`. Readings are stored with model version `AquaNet-V3`. All other routes unchanged. |
| Dashboard | `frontend/neural.js`, `app.js`, `index.html`, `i18n.js` | Model switch: **V3 (trained)** / V1 (hand-built). V3 note in English and Hindi with its test results. Carbon-black theme unchanged. |
| ESP32 | `Firmware/esp32_firmware/` (moved from `Firmware/`) | Runs V3 on the chip (`aquanet_v3.c/.h`, generated). Averages 3 scans per reading. Folder renamed so the Arduino IDE opens the sketch directly. |
| Installer | `AquaSentry_Platform/scripts/install_aquanet_v3.py`, `scripts/gen_c_v3.py` | One command installs a trained model into server, dashboard and ESP32 code. |
| Tests | `AquaSentry_Platform/tests/test_aquanet_v3.py`, `.github/workflows/ci.yml` | 7 new tests (108 total in v4). CI compiles the ESP32 engine. |
| GitHub | `.gitignore`, `.gitattributes`, `README.md` (new top section), `CHANGELOG.md` | Ready to push. `Docs/Canva.htm` removed (it holds Canva's Google API keys; GitHub would block the push). |

**Not changed:** the voltammetry maths and calibration, the database, the API routes (one added), the carbon theme and Hindi translations (one note added), the desktop app, the video, the 3D models and the data files.

## AquaNet-V3 results (short version)

| | Rules alone | V2 | **V3 (installed)** |
| --- | --- | --- | --- |
| Network correct on exact readings | — | 99.6% | **98.6%** |
| Whole system correct, noisy sensor, 3 scans | 93.6% | 93.6% | **93.5%** |
| Whole system correct, with v4.1 adaptive re-scanning | — | — | **94.6%** |
| Unsafe/Hazardous water missed (out of 200,000), 3 scans | 2,283 | 2,152 | **1,755** (−23%) |
| … with adaptive re-scanning | — | — | **1,508** (−34%) |
| Dangerous water called "Safe" | 0 | 0 | 0 |

With a fixed number of scans, about 93–94% is the ceiling for any model that is not allowed to soften the safety rules: a reading of 51 µg/L may really be 49. V3's gain is that it misses fewer dangerous samples at the same overall accuracy; v4.1's adaptive re-scanning then reduces the noise itself, only where it matters. A safety-first version that misses about 40% fewer is included in `Neural_Network/v3_training/models/` — the report explains how to switch.

## Putting it on GitHub

Easiest: install **GitHub Desktop**, choose **File → Add local repository** → pick the unzipped `AquaSentry` folder → *create a repository* → **Publish repository**. (Untick "Keep this code private" only if you want it public.)

Or with git in a terminal, inside the `AquaSentry` folder:
```
git init
git add .
git commit -m "AquaSentry v4"
git branch -M main
git remote add origin https://github.com/<your-username>/AquaSentry.git
git push -u origin main
```
Create the empty `AquaSentry` repository on github.com first (no README, no .gitignore — this folder already has them). Your friend then runs `git clone https://github.com/<your-username>/AquaSentry.git` and follows "How to run" above.

`.gitignore` keeps out `.venv`, caches, build output and any `.env` file, so API keys never get uploaded. There is no licence file yet — add one on GitHub (**Add file → Create new file → LICENSE**) if you want others to be allowed to reuse the code.

## Explainer video

`Docs/AquaSentry_Explained.mp4` (7 minutes) covers how the code works, then teaches neural networks from scratch using AquaNet. It has on-screen narration and no voice.

## Using the ESP32

1. In `Firmware/esp32_firmware/esp32_firmware.ino`, fill in the **CHANGE THESE BEFORE FLASHING** block (Wi-Fi name, password, server address).
2. Double-click **`Start AquaSentry for ESP32.bat`**. It prints the exact server address to put in the firmware.
3. Flash the ESP32 and watch the Serial Monitor at 115200 baud. `Firmware/README.md` has a troubleshooting table.

## Still to do

- Test the firmware on a real ESP32. It was checked here with a regular C++ compiler, stub ESP32 libraries and simulated scans, not on the board (the ESP32 toolchain could not be downloaded here). The neural-network part is plain C99 and was checked against Python on 100,000 inputs.
- Check AquaNet-V3 against real water samples tested by a lab. All training and test data so far is simulated.
- Calibrate with your own electrode and known arsenic standards, then update the calibration numbers in both `app/standards.py` and the firmware.
- Fit pH, conductivity, turbidity and temperature sensors if you want them measured: fill in `read_ph()` and the other `read_` functions in the firmware.
