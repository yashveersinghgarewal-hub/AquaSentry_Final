# Video pitch check (SBI Youth Ideathon 2026, script v3)

Every sentence of the 1 min 50 s video-pitch script, checked against this repository (v5.11, 10 November 2026). **Backed** means the code and a test exist today; **wording** means a small change to the script keeps it exactly true. Nothing in the video should claim that a sensor has been built, calibrated in a lab or tested in the field: none of that has happened yet.

## Claim by claim

| Slide | What is said or shown | Status | Evidence in the repository |
| --- | --- | --- | --- |
| 2 | Arsenic has no colour, taste or smell | Backed (general science) | WHO arsenic fact sheet |
| 2 | "lab tests take weeks" | **Wording**: say "lab results can take weeks" | Not measured by the team; districts differ. Ask a PHED lab for a real figure (roadmap item 27) |
| 4 | Parts of 230 districts in 25 states | Backed | Government of India written reply in the Rajya Sabha, 4 Dec 2023 (Minister of State for Jal Shakti); show the source on screen |
| 4 | Limit 10 µg/L (IS 10500 · WHO) | Backed | `AquaSentry_Platform/app/standards.py`; IS 10500:2012 has no relaxation since Amendment 1 (2015) |
| 5A | ESP32 firmware runs the arsenic test on a gold electrode | Backed (code) | `Firmware/esp32_firmware/esp32_firmware.ino` (square-wave stripping on the gold working electrode) |
| 5A | "checks its own reference electrode first" | Backed | Step 0 of every test: rest-current settle check, `QC_REF_UNSTABLE` fault; the boot self-test prints the check and its limits (v5.11) |
| 5A | "stores readings when the network drops" | Backed | 1,000-reading offline buffer on LittleFS, idempotent uploads |
| 5A | AquaNet, 352 parameters, "can make a verdict stricter, never softer" | Backed | `aquanet_v3.c`: 5-16-12-4 network; the fixed rules run after it, so the final verdict is never softer than the rules; parity tests |
| 5A | On screen: "builds for 4 boards" | Backed (v5.11) | CI compiles ESP32, ESP32-S3, ESP32-C3 and ESP32-C6 (nine configurations); `tests/test_v511_pitch.py` |
| 5A | Serial self-test scrolling (`[SELFTEST] …`) | Backed, **needs a board** | Runs on any ESP32 on USB, even without the sensor (it then reports the ADC and DAC as not found). Without a board, show the green firmware job on GitHub Actions instead |
| 5A | AquaNet panel: network vote vs final verdict | Backed | Dashboard → *AquaNet model*: "Network's vote" and "Final verdict" side by side |
| 5B | "Every scan reaches our dashboard sealed with a digital fingerprint" | Backed | `POST /api/scans` stores the raw scan with its SHA-256 (`checksum_sha256`); the firmware uploads scans by default (`TRACE_UPLOAD 1`); the simulator prints the first 12 digits |
| 5B | One answer: not detected, retest, screen positive or invalid, with uncertainty | Backed | `classification.screening_outcome`; ± U (k = 2) on the dashboard, the QR page and the PDF |
| 5B | Live demo: simulator sends a scan, curve draws, result with ± appears | Backed (v5.11) | MAS-G1 simulator → SEND TO DASHBOARD → `index.html?device=SIM-MASG1-01`; browser test `test_simulator_sends_each_demo_scan_to_the_dashboard` |
| 5B | "It works offline" | Backed | Service worker caches the dashboard; the dashboard and simulator run without a network (the simulator then keeps its results on the meter) |
| 5B | "in five Indian languages" | **Wording**: say "in five languages" or "in English and four Indian languages" | English, Hindi, Bengali, Assamese, Punjabi. English is one of the five; the four Indian-language versions are machine-assisted and still need native-speaker checks |
| 5B | "327 automated tests" | **Wording**: say "more than 350 automated tests" | v5.11: 22 neural-toolkit + 335 server + 10 browser tests = 367, plus nine firmware builds on GitHub |
| 5B | Switch to Hindi; open the PDF | Backed | Language menu; *Report* → download (a simulated reading prints "SIMULATED / DEMO DATA: NOT A REAL WATER TEST" across the top, which is the honest thing to show) |
| 5B | GitHub Actions, all checks green | Backed | Check the latest run on `main` before recording |
| 6 | Sixty points of design-review feedback | Backed | `Docs/ROADMAP_COVERAGE.md` (Research and Engineering Review, 60 items) |
| 6 | "never call water safe on a guess" | Backed | Results never say "Safe": a clean reading is "Not detected" with ± and "not confirmation that the water is safe". The word survives only as one of AquaNet's four class names in the explorer panel, so avoid filming that panel with a clean sample if the slide says "never" |
| 6 | "We fixed every software point" | Backed (v5.11) | Every item software alone can close is closed; 20, 28 and 40 wait for data or a physical test. Safer to say: "We fixed every point software can fix" |
| 6 | On screen: before/after "Safe" → "Not detected ± µg/L" | Backed | Up to v5.6 a clean reading was labelled "Safe" (the change is in `CHANGELOG.md`, v5.7 and v5.8); today's dashboard shows "Not detected" with ± |
| 7 | 3 weeks / 3 months / 12 months | Team plan | Must be the team's real plan (`Docs/REMAINING_WORK.md`) |
| — | Reference build "commit 50b14fb" | **Update** | Use the commit of `main` after v5.11 is merged |

## Shot list: how to record each screen

Start everything from the repository folder on the laptop that records the video.

1. **Start the server with the demo field programme** (six labelled demo nodes, plus the simulator's own device):
   ```bash
   cd AquaSentry_Platform
   python scripts/seed_field_demo.py --db demo_field.db
   DATABASE_URL=sqlite:///demo_field.db python -m uvicorn app.main:app --port 8000
   ```
   Or just run `./run_desktop.sh` (macOS) / `Start AquaSentry Desktop.bat` (Windows) for an empty dashboard.
2. **Slide 5B, live demo.** Window 1: http://localhost:8000/device-simulator.html. Window 2: http://localhost:8000/?device=SIM-MASG1-01&mode=judging. Press **DEMO** once for "not detected", again for "screen positive" (contaminated). The meter shows the result with ± and `ON DASHBOARD: … SHA-256 …`; the dashboard window changes by itself. Press **View the recorded scan** on the dashboard to draw the curve.
3. **Hindi:** language menu in the top bar → हिन्दी.
4. **PDF:** *Report* in the left menu → download the screening report.
5. **AquaNet panel (slide 5A):** *AquaNet model* in the left menu: network vote and final verdict.
6. **Firmware (slide 5A):** Arduino IDE → open `Firmware/esp32_firmware/esp32_firmware.ino` → board *ESP32 Dev Module* (or ESP32-C6) → **Verify**. With a board on USB: **Upload**, then *Serial Monitor* at 115200 baud to film the `[SELFTEST]` lines.
7. **Wiring diagram:** `Firmware/PINOUT.md` (one table for all four chips).
8. **Green checks:** https://github.com/yashveersinghgarewal-hub/AquaSentry_Final/actions (latest run on `main`).

Judging mode (`?mode=judging` or the podium button) hides market, sales, impact and the assistant, as the script asks.

## Sources

- Rajya Sabha written reply, 4 December 2023 (arsenic in parts of 230 districts in 25 states): [ThePrint / PTI](https://theprint.in/india/arsenic-found-in-groundwater-in-25-states-fluoride-in-27-states-govt/1871766), [Deccan Herald](https://www.deccanherald.com/india/arsenic-found-in-groundwater-in-25-states-fluoride-in-27-states-govt-2796451), [Rajya Sabha debates record](https://rsdebate.nic.in/bitstream/123456789/745796/1/PQ_262_04122023_U95_p296_p297.pdf).
