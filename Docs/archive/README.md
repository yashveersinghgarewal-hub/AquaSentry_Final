# Archive

Older documents, kept word for word so no information is lost when the repository was reorganised (v5.7, November 2026). They describe earlier versions; some numbers and limits in them are out of date (for example the withdrawn 50 µg/L IS 10500 "permissible" value, test counts, and the claim that AquaNet-V1 was trained). For current information use [`../README.md`](../README.md) (the documentation index) and [`../../CHANGELOG.md`](../../CHANGELOG.md).

| File | What it was | Replaced by |
| --- | --- | --- |
| `FIXES_v3.md` | Every v3 fix with file and line | `CHANGELOG.md` (v3 entry) keeps the summary; this file keeps the detail |
| `WHATS_NEW_v5.1.md` | v5.1 "what's new and how to run" (was `WHATS_NEW_AND_HOW_TO_RUN.md`), including the v4–v5.1 change tables, the AquaNet-V3 results table and the GitHub how-to | `Docs/HOW_TO_RUN.md`, `CHANGELOG.md` |
| `START_HERE_OPERATIONS_GUIDE_v1.md` | The first all-in-one operations guide | `Docs/HOW_TO_RUN.md` |
| `README_sections_pre_v5.7.md` | The v5.2–v5.5 release notes and the old folder tree from the top-level README | `CHANGELOG.md`, `README.md` |
| `PLATFORM_README_v1.md`, `PLATFORM_QUICK_START_v1.txt` | First description of `AquaSentry_Platform/` (catamaran-first, ports 8000/8001) | `AquaSentry_Platform/README.md` |
| `README_universal_2026-10.pdf` | PDF of the October 2026 "Universal" README | `README.md` |
| `AquaSentry-Explanation_template.md` | Unfinished text template for the bot explanation (was in `frontend/`, not used by any page) | — |
| `OTHER_MATERIALS_NOTES.txt` | Short note: materials (ammeter, glass rod, magnets, baking soda) and two feature ideas (connect to own sensor; find location and connect to nearest sensor) | Partly done: each node has its own page and QR code, and the sensor map shows all nodes (v5.6). "Find my location and show the nearest sensor" is not built yet |

Removed in v5.7 because an identical copy exists elsewhere (checked byte for byte): `Neural_Network/AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.md` (same as `Docs/neural/`), `Docs/AquaSentry_Logo.jpg` (same as `AquaSentry_Platform/frontend/aquasentry-logo.jpg`), `frontend/chat.js` and `frontend/audio.js` (same as `frontend/legacy_v1/`, the only pages that load them), `frontend/data.json` (same as `Data/example_calibration.json`) and the second copy of the materials note. PDF renders of Markdown files were removed too: every word in them is in the Markdown source, and `AquaSentry_Platform/scripts/convert_all_md_to_pdf.py` regenerates them. Everything removed is still in the Git history (commit `c803547`, the head of the `aquasentry-v5.6` branch, is the last one before the clean-up).
