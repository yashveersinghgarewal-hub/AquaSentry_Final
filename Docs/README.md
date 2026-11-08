# AquaSentry documentation

| Start here | |
| --- | --- |
| [HOW_TO_RUN.md](HOW_TO_RUN.md) | Every way to run it: desktop app, browser, Docker, ESP32, demo data, tests, troubleshooting |
| [ISEF_ROADMAP.md](ISEF_ROADMAP.md) | 267 prioritised changes for Regeneron ISEF / IRIS level judging, with the rules that can disqualify a project |
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
| [../Firmware/README.md](../Firmware/README.md) | ESP32 pins, options, flashing, troubleshooting |
| [../models_3d/](../models_3d/) | Printable enclosure (STL / 3MF) |

| Media (`media/`) | |
| --- | --- |
| `media/AquaSentry_Explained.mp4` | 7-minute explainer video (how the code works, neural networks from scratch) |
| `media/screenshots/` | Dashboard screenshots used in the README |

[`archive/`](archive/) keeps older documents word for word; see its README for what replaced each one.

Folder names: this folder stays `Docs/` (capital D) because scripts and links already use it, and renaming only the letter case breaks Git on Windows and macOS.
