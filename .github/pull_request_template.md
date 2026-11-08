## What changed and why

## Checks
- [ ] `python main.py --test` passes (or `pytest` in `AquaSentry_Platform/`)
- [ ] `ruff check .` is clean
- [ ] If the arsenic rules changed: all four copies agree (Python app, Neural_Network, `frontend/neural.js`, firmware C) and the parity tests pass
- [ ] If the firmware changed: it builds for ESP32, ESP32-S3 and ESP32-C3 (CI does this), and `FIRMWARE_VERSION` is bumped
- [ ] User-facing text added in English **and** Hindi (`frontend/i18n-v5.js`)
- [ ] `CHANGELOG.md` updated
