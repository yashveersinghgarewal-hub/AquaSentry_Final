# Hardware changelog

ISEF item 181: physical changes kept next to the software changelog. Seeded from what the repository documents;
add a row for every printed part, wiring change or electrode change with the date and what was measured.

| Date | Version | Change | Why | Measured |
|---|---|---|---|---|
| 2026 (pre-Nov) | MAS-G1 bench unit | ESP32 + ADS1115 + MCP4725 potentiostat; 15 mL printed sample well; stepper pump; IR bubble sensor | First working ASV chain | synthetic scans only |
| 2026 (pre-Nov) | Shell v1 (`models_3d/aquasentry_shell_base.stl`, `_lid.stl`) | Printed enclosure | | fit not yet logged (item 180) |
| 2026 (pre-Nov) | Shell 120 mm (`*_full_120mm.stl`, slicer plates) | Larger enclosure for battery and probes | | |
| 2026 (pre-Nov) | Tank bracket, suction strainer (`aquasentry_tank_bracket.stl`, `aquasentry_suction_strainer.stl`) | In-tank sentry concept (`Docs/hardware/PERSONAL_TANK_SENTRY_BLUEPRINT.md`) | | concept — no field data (item 260) |
| 2026 (pre-Nov) | Catamaran concept (`Docs/hardware/CATAMARAN_PROTOTYPE_SPEC.md`) | Surface-water sampling platform | | concept — future work (item 260) |
| 2026-11-08 | firmware 5.6–5.9 pin profiles | Pins fixed per chip (ESP32 / S3 / C3), ADC1 only, optional sensors as `#define`s | Wi-Fi kills ADC2; strapping pins | host-build test per profile |
| *(date)* | | *electrode lot / strip type change* | | *slope, LOD* |
| *(date)* | | *PCB v1 (KiCad)* | item 173 | *noise floor* |
| *(date)* | | *enclosure IP / UV / heat test* | item 168 | |

Licence for the hardware files: to be chosen (CERN-OHL-P recommended) and stated in `Docs/CREDITS.md`.
