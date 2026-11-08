# Field data: the paired dataset (v5.8)

This folder is where the **real** paired dataset lives: one node scan and one independent laboratory result on the
same water sample. Nothing in it is shipped by the project; the only file is a template. Until this folder holds
real rows, every accuracy figure in the repository is a software check or a manufacturer specification (see
`Docs/CLAIMS_REGISTER.md`).

## Minimum record (review items 21, 26, 30)

One row per **child scan**, linked to its **parent sample** by `parent_sample_id`. The template
`paired_template.csv` has every column; the groups are:

| Group | Columns | Notes |
|---|---|---|
| Collection | `parent_sample_id`, `source_code`, `site_name`, `village`, `district`, `state`, `latitude`, `longitude`, `source_kind`, `depth_m`, `collection_time_utc`, `preservation`, `collection_to_analysis_min` | The parent ID is given at the pump and never reused. Depth and preservation may be blank, never invented. |
| Instrument | `child_scan_id`, `raw_file_name`, `raw_file_sha256`, `potential_unit`, `current_unit`, `method`, `firmware_version`, `strip_lot`, `calibration_id`, `ph`, `conductivity_us_cm`, `temperature_c`, `turbidity_ntu`, `qc_status`, `qc_flags`, `device_ug_l`, `device_uncertainty_ug_l`, `screening_outcome` | The server fills these when the scan is uploaded (`POST /api/scans` with `sample_code = parent_sample_id`); the checksum is of the original instrument export, kept unchanged next to this table. |
| Reference | `lab_aliquot_id`, `lab_name`, `lab_method`, `lab_species`, `lab_value`, `lab_unit`, `lab_reporting_limit`, `lab_qualifier`, `lab_test_date`, `lab_report_link` | Keep the original value and unit. A result below the reporting limit keeps `lab_qualifier = <` and `lab_value = reporting limit`; it is never replaced by 0 or by half the limit in this file. |

Units are µg/L everywhere in the platform; convert once, at import, and record the original unit.

## Workflow

1. Collect the split sample, write `parent_sample_id` on both bottles and in the logbook.
2. Scan with the node (or import the instrument file): `python bridge/serial_bridge.py --file <export.csv> --device-code <node>`; the
   dashboard's **Replay a recorded scan** does the same for one file. Pass the parent ID as the sample code.
3. When the laboratory reports, enter the result: `POST /api/lab-results` with the same `sample_code`, `reporting_limit_ug_l`, `qualifier`
   and `species`; the server pairs it with the scan.
4. Export the paired table: `GET /api/data/export/paired` (CSV). Keep that export, this template filled in by hand for anything the
   server could not know (depth, preservation, lab report link), and the original instrument files together, under version control or a
   dated archive.
5. Analyse: `python Analysis/paired_validation.py paired.csv --out Analysis/out/validation` and
   `python Analysis/aquanet_v2_pipeline.py paired.csv --out Analysis/out/aquanet_pipeline`.

## Rules that keep the dataset honest

- **Blind the final comparison** (item 25): the laboratory results of the test set stay with the supervisor until the software version,
  calibration and decision settings are frozen and written down.
- **Group before you split** (item 24): all scans, spikes and repeats of one parent sample stay in the same fold; hold out whole sites.
  The analysis scripts do this; a random row split is not acceptable.
- **Count independent sources, visits and scans separately** (item 23). Thirty scans of three wells are three sources.
- **Never store household identifiers.** Coordinates of private wells are rounded or withheld in anything published (item 30).
- **Censored results are data** (item 26): report how many rows the "< reporting limit" policy affected.

Public datasets for checking the analysis code (not for validating the sensor): the Bullen et al. gold-electrode ASV workbook, the NIST
lead SWV sessions, the Warwick overlapping-SWV traces and the USGS speciation hold-time data (listed in the review, D01–D05). Keep their
instrument and preparation separate from AquaSentry data.
