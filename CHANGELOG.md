# Changelog

## v5.1 — black & blue, more motion
- New colour scheme: deep blue-black background with electric blue, cyan and indigo accents (light theme updated to match). Safety colours (green/amber/orange/red) unchanged.
- New `frontend/motion.js` on every page: animated 3D dotted-wave background that ripples around the cursor, soft cursor light, sweeping light beam, scroll progress bar, word-by-word heading reveals, "decode" animation on the verdict title, magnetic buttons, parallax on hero visuals.
- More movement: animated gradient text and buttons, shimmering labels, orbiting particles and pulse ring around the arsenic gauge, scrolling facts strip, floating icons, card lift and glow, self-drawing section dividers, staggered card entrances, page-to-page fade transitions, rippling water floor under the 3D device model.
- Performance: removed expensive blur filters from moving layers (about 3–4× higher frame rate in testing). Reduced-motion users get a still version.

## v5 — new UI across every page
- **One design system for every page** (`frontend/app.css` + `frontend/shell.js`): carbon-black glass UI with aqua gradients, light theme, English/Hindi on every page, same sidebar, top bar and assistant everywhere.
- **Brought back from the original UI:** "What to do if arsenic is high" (4-step public-health protocol, filter options, health note), **Contact local authorities** (auto-filled incident report you can email, copy, share or print; directory: Gram Panchayat/VWSC, district water department, Jal Jeevan Mission Citizen Corner, CPGRAMS, 108/112; local contacts saved on the device), catamaran robot knowledge base, scientific disclosure, impact numbers, **market research graphs**, **sales graphs**, **ROI calculator**, competitor comparison, roadmap and the **device simulator**.
- **Effects:** WebGL water-caustics hero that changes colour with the verdict, animated gauge, glowing nav highlight, cursor spotlight cards, 3D tilt, number counters, scroll reveal, drawn-in charts, rotating dotted globe, and an **interactive 3D model of the real enclosure** (from `models_3d/*.stl`) with an exploded view. All offline, and turned down for users who prefer reduced motion.
- `market-research.html` and `sales-expansion.html` were broken (their style files no longer existed); both rebuilt. Chart.js from the internet replaced by a small offline chart library (`charts.js`).
- The device simulator (`website`, a file with no extension that the server downloaded instead of showing) is now `device-simulator.html`.
- Fixed: "Load demo data" with the server running looked for the wrong device and fell back to local demo data.
- AquaNet, firmware, server API and tests unchanged (110 tests pass).

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
