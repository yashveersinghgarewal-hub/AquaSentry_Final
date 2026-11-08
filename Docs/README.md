# AquaSentry documentation

| Start here | |
| --- | --- |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | Every way to run it: desktop app, browser, Docker, ESP32, demo data, tests, troubleshooting |
| [ISEF_ROADMAP.md](ISEF_ROADMAP.md) | 267 prioritised changes for Regeneron ISEF / IRIS level judging, with the rules that can disqualify a project |
| [ISEF_ROADMAP_STATUS.md](ISEF_ROADMAP_STATUS.md) | Status of all 267 roadmap items: done in software / tooling ready / partial / team / lab / field, with where the code or next step is (from `planning/isef_roadmap_status.csv`) |
| [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) | Each design criterion → the test that proves it → result or target; constraints and the software's response |
| [FMEA.md](FMEA.md) | Failure modes, how each is detected and reported, which test proves it; safety by design |
| [DECISION_LOG.md](DECISION_LOG.md) | Dated decisions with alternatives and reasons |
| [SOP_MEASUREMENT.md](SOP_MEASUREMENT.md) | One measurement, step by step (chemistry steps for the supervisor to fill) |
| [AI_USE_STATEMENT_TEMPLATE.md](AI_USE_STATEMENT_TEMPLATE.md) | Factual inventory of AI assistance for the ISEF disclosure |
| [CREDITS.md](CREDITS.md) | People, libraries, methods, licences |
| [PRIVACY_AND_PERFORMANCE.md](PRIVACY_AND_PERFORMANCE.md) | What location data is stored and who sees it; measured page load on 3G |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 60-second click path for judging |
| [HARDWARE_CHANGELOG.md](HARDWARE_CHANGELOG.md) | Physical changes next to the software changelog |
| [planning/](planning/) | timeline.csv (Gantt), design_history.csv, isef_roadmap_status.csv |
| [ROADMAP_COVERAGE.md](ROADMAP_COVERAGE.md) | The 60-item Research and Engineering Review and the ISEF list mapped to code and tests, or to "needs the lab" |
| [CLAIMS_REGISTER.md](CLAIMS_REGISTER.md) | Every claim about limits, accuracy, cost, autonomy or power with its evidence or marked as a target |
| [CODE_GUIDE.md](CODE_GUIDE.md) | How the code fits together, and a neural-network primer using AquaNet |
| [IMPROVEMENT_LOG.md](IMPROVEMENT_LOG.md) | Every change since v5.1 with the reason and the source (design history) |
| [../CHANGELOG.md](../CHANGELOG.md) | Release notes, v2 → today |
| [../SECURITY.md](../SECURITY.md) | Reporting security problems; how keys and alerts are protected |

| Neural network (`neural/`) | |
| --- | --- |
| [AQUANET_V3_REPORT.md](neural/AQUANET_V3_REPORT.md) | AquaNet-V3, the model in use: method and results (simulated data) |
| [AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.md](neural/AQUANET_NEURAL_NETWORK_COMPREHENSIVE_GUIDE.md) | Long guide to AquaNet-V1 and the signal chain |
| [AQUANET_RETRAINING_REPORT.md](neural/AQUANET_RETRAINING_REPORT.md) | V2 retraining |
| [AQUANET_V1_STRESS_TEST_REPORT.md](neural/AQUANET_V1_STRESS_TEST_REPORT.md) | V1 stress test |

| Hardware (`hardware/`) | |
| --- | --- |
| [AQUASENTRY_HOME_ASSEMBLY_MANUAL.md](hardware/AQUASENTRY_HOME_ASSEMBLY_MANUAL.md) | Building the device |
| [PERSONAL_TANK_SENTRY_BLUEPRINT.md](hardware/PERSONAL_TANK_SENTRY_BLUEPRINT.md) | Household tank version |
| [CATAMARAN_PROTOTYPE_SPEC.md](hardware/CATAMARAN_PROTOTYPE_SPEC.md) | Floating (catamaran) version |
| [../Firmware/README.md](../Firmware/README.md) | ESP32 options, flashing, troubleshooting |
| [../Firmware/PINOUT.md](../Firmware/PINOUT.md) | Every pin, part and conditioning constant in one table; LED legend |
| [../models_3d/](../models_3d/) | Printable enclosure (STL / 3MF) |

| Media (`media/`) | |
| --- | --- |
| `media/AquaSentry_Explained.mp4` | 7-minute explainer video (how the code works, neural networks from scratch) |
| `media/screenshots/` | Dashboard screenshots used in the README |

[`archive/`](archive/) keeps older documents word for word; see its README for what replaced each one.

Folder names: this folder stays `Docs/` (capital D) because scripts and links already use it, and renaming only the letter case breaks Git on Windows and macOS.
