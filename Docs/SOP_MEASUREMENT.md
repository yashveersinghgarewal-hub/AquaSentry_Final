# Standard operating procedure — one AquaSentry measurement

ISEF items 102–103: a written procedure that an independent person can follow. The instrument and software steps
below are complete; every chemistry step marked **[supervisor]** must be written by the Designated Supervisor /
Qualified Scientist after the Form 3 risk assessment (section O) and must not be improvised.

## Before the day

1. Charge the node; confirm the firmware version on `/status.json` and that the boot self-test shows ADC and DAC found.
2. Calibration: check `/api/qc/status?device_code=…` — calibration age ≤ 90 days, otherwise run an external calibration
   or standard addition first (`/api/admin/calibrations/*`).
3. Auxiliary sensors: pH buffer, conductivity standard, turbidity standard and reference thermometer checks
   (`POST /api/qc/runs` with `run_type` = `ph_buffer` …). Unchecked sensors are shown as unverified.
4. Print the day's blinded run sheet: `python Analysis/run_order.py --samples … --day YYYY-MM-DD`; the supervisor keeps the key.
5. Glassware and cell cleaning protocol **[supervisor]** (acid wash, rinse, drying; logged).

## At each source (field)

6. Write the parent sample ID on both bottles and the logbook; purge the source for the agreed time; record time, GPS,
   source type, depth if known (`SampleMeta`: purge_minutes, bottle_id, collected_at, source_kind, depth_m).
7. Split the sample: one bottle for the laboratory with its preservation **[supervisor]**, one for the node.
8. Field blank once per day (deionised water carried through the same steps) → `run_type` = `field_blank`.

## At the instrument

9. Opening check standard (10 µg/L) **[supervisor prepares]** → `run_type` = `check_standard`. If recovery is outside
   80–120 %, stop: recalibrate or change the electrode; do not measure samples.
10. For each run on the sheet, in order: rinse volume, fill the 15 mL well, supporting electrolyte / pre-reduction step
    **[supervisor]**, start the test (button, dashboard "Test a sample", or `bridge --port`). Enter the coded sample ID
    as `sample_code`.
11. Read the outcome: *invalid* → repeat once after the suggested action; *retest* → repeat and send to the lab;
    *not detected* / *screen positive* → record. Never override a failed test by hand.
12. Spike recovery on at least one real sample per matrix per day **[supervisor prepares the spike]** →
    `run_type` = `spike_recovery` with `baseline_ug_l` and `expected_ug_l`.
13. Closing check standard → `check_standard`. If it fails, the day's data are flagged by the server; write why in the logbook.

## After the day

14. Confirm every scan reached the server (`GET /api/scans?device_code=…`) and that the bridge outbox is empty.
15. Enter laboratory results when they arrive: `POST /api/lab-results` with the same `sample_code`, `reporting_limit_ug_l`,
    `qualifier` and `species`.
16. Export and analyse: `GET /api/data/export/paired` → `python Analysis/make_poster_figures.py --paired paired.csv`.
17. Waste: collect, label, hand to the licensed route **[supervisor]**; log it.

## Reproducibility check (item 103)

Give this page and the run sheet to someone who has not done it before; time them; note every question they ask;
change the page, not the person.
