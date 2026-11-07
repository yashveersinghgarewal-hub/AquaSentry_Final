# Changelog

## v4.1 — adaptive re-scanning on the ESP32
- The ESP32 takes 3 scans, then 3 more (up to 9) only while the arsenic reading is within 2 standard errors of 10 / 50 / 150 µg/L. Simulated overall accuracy 93.4% → 94.6%; dangerous samples missed 1,755 → 1,508 (out of 200,000); about 1.5× the average scan time instead of 3× for always doing 9 scans.
- 2 new tests check the firmware rule against the training code (110 tests).
- Training code can train and test with the same re-scan rule (`ADAPTIVE=1`, `eval_adaptive.py`). Eight more training runs did not beat the v4 network, so its weights are unchanged.

## v4 — AquaNet-V3, ESP32-ready, GitHub-ready
- **AquaNet-V3** is now the default model on the server, the dashboard and the ESP32. It reads arsenic on a log scale, was trained on readings with realistic sensor noise (3 scans averaged, like the firmware), and is weighted so it misses fewer Unsafe/Hazardous samples. Results: `Docs/AQUANET_V3_REPORT.md`. V1 is still available (`AQUANET_MODEL=v1`, or the V1 button on the dashboard).
- **ESP32:** the firmware runs V3 on the chip (`Firmware/esp32_firmware/aquanet_v3.c`, generated float32 C99, 352 weights = 1.4 KB, no `malloc`). Each reading now averages 3 voltammetry scans (`SCANS_PER_READING`).
- **Firmware moved to `Firmware/esp32_firmware/`** so the Arduino IDE opens it directly (a sketch must sit in a folder with the same name, and the `.c/.h` files must be beside it).
- New `scripts/install_aquanet_v3.py`: one command puts a trained model into the server, the dashboard and the firmware.
- New training code: `Neural_Network/v3_training/`.
- 7 new tests (108 in total at v4), including a C-vs-Python check of the ESP32 engine. CI also compiles the ESP32 engine.
- Repo hygiene: `.gitignore`, `.gitattributes`, no `.env` files, no API keys. `Docs/Canva.htm` (a saved Canva web page containing Canva's embedded Google API keys) is no longer included — GitHub would block the push.

## v3.1 — carbon black theme
- Dashboard defaults to a carbon-black dark theme; light mode still available from the moon button.

## v3 — error fixes
- All errors found in the original package fixed (firmware payload, voltammetry window, calibration, sensor stubs, OTA auth, PDF report, websocket, tests writing to the real database, and more). Full list with files and lines: `FIXES_v3.md`.

## v2 — new dashboard, Hindi, desktop app, AquaNet-V2
- Professional dashboard with English / हिन्दी switch, light and dark mode, offline fonts.
- Desktop app (`desktop_app.py`), VS Code launch settings, explainer video (`Docs/AquaSentry_Explained.mp4`).
- AquaNet-V2 trained on all five readings.
- Removed `.env` (it contained a live Gemini API key — revoke it).
