# What is left before ISEF

Generated from `Docs/planning/isef_roadmap_status.csv` by `Analysis/roadmap_status.py` (edit the CSV, rerun; a test keeps this page in sync). Item numbers match `Docs/ISEF_ROADMAP.md`, where each item is explained, and `Docs/TEAM_WORKBOOK.md`, where each open item has its steps, template and place to record.

**210 of 267 roadmap items are still open.** None is unaddressed: every one has a worksheet, a template or a ready script. What remains is laboratory work (12), field work (4), running the ready-made tools on real measurements (67), finishing items the software started (29) and the team's own work (98: rules, writing, people, poster, interview).

Tick items here or copy the list into the logbook with the date you finish each one. The logbook is the evidence; this page is the plan. Do not let an AI write the research plan, abstract, poster or citations (item 1).

## Start here: the 53 must-do (P0) items

These decide whether the project is ISEF-level at all. The order is the roadmap's: rules first, then the science.

- [ ] **1** (P0) No generative AI for the research plan / abstract / poster / citations. *Rule. Everything in this repository was AI-assisted: use it as notes; write your own documents. Docs/AI_USE_STATEMENT_TEMPLATE.md lists what was AI-assisted so the disclosure is accurate. Workbook §1: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **2** (P0) Disclose AI use (one-page statement). *Docs/AI_USE_STATEMENT_TEMPLATE.md: factual inventory of AI-assisted files, tools and versions; the 'what we checked / designed ourselves' sections are yours to write. Workbook §2.* `Partial`
- [ ] **3** (P0) Be able to explain every file you show. *Docs/CODE_GUIDE.md walks the code; Docs/DEMO_SCRIPT.md names the 3 screens to show. Rewrite or drop anything you cannot explain. Workbook §3: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **4** (P0) 12-month rule: research window from Jan 2026. *Write the start date in the logbook; Docs/planning/timeline.csv has the window; git history dates every software change. Workbook §4: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **5** (P0) Continuation: Form 7 and 'previous work' labels. *Not software. CHANGELOG.md separates versions by date for the 'what is new this year' table. Workbook §5: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **6** (P0) Research plan before experimenting; addenda. *Not software. Analysis/run_order.py and Data/field/README.md give the procedures section concrete steps. Workbook §6: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **7** (P0) SRC review; Form 3 risk assessment; SDS for every chemical. *Not software. See section O. Workbook §7: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **8** (P0) IRB approval before any survey or interview. *Workbook §8: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **9** (P0) Team rules (up to 3; fixed for the year). *Not software. README 'Team' section to be completed (item 267). Workbook §9: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **10** (P0) Booth must work without electricity or internet. *Poster figures are SVG/PDF from Analysis/make_poster_figures.py; QR code prints (project_figures.py qr). Print the figures; the dashboard is a bonus. Workbook §10.* `Partial`
- [ ] **12** (P0) Confirm IRIS 2026-27 submission status. *Not software. Record the answer in the logbook. Workbook §12: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **13** (P0) All real dates in one calendar. *Docs/planning/timeline.csv seeded with the published dates; Analysis/project_figures.py gantt draws it. Confirm the IRIS dates on iris.exstemplar.com. Workbook §13.* `Partial`
- [ ] **22** (P0) One sentence of need with a number and source. *Write it yourself from JJM / CGWB; cite the year. Workbook §22: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **23** (P0) State who the primary user is. *Not software. The platform supports district-lab, panchayat and household views; pick one for the story. Workbook §23: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **24** (P0) Design criteria as measurable targets. *Docs/REQUIREMENTS_TRACEABILITY.md lists each criterion with the test that proves it and the current result/target. Workbook §24.* `Partial`
- [ ] **25** (P0) Constraints written down. *Docs/REQUIREMENTS_TRACEABILITY.md 'Constraints' section (power, network, languages, hard water, iron/manganese, temperature) with what the software does about each. Workbook §25.* `Partial`
- [ ] **26** (P0) Why current options fail the criteria (comparison table). *Data/field/landscape_template.csv + project_figures.py landscape give the figure once the numbers are filled from datasheets. Workbook §26.* `Partial`
- [ ] **36** (P0) Literature review (20+ papers; table). *Not software. Keep the table as a CSV (method, LOD, interferents, cost, field-tested) next to Data/field/landscape_template.csv so the landscape figure draws from it. Workbook §36: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **37** (P0) One sentence of what is new. *Not software; Docs/CLAIMS_REGISTER.md shows what is and is not demonstrated. Workbook §37: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **48** (P0) Alternatives considered with decision matrices. *Analysis/decision_matrix.py (weighted scores + ±30 % weight-sensitivity) from Docs/templates/decision_matrix_template.csv; reasons in Docs/DECISION_LOG.md. Workbook §48.* `Tooling ready`
- [ ] **49** (P0) Weighted criteria and scores per matrix. *Same script: normalised weights, ranking, robustness of the winner. Workbook §49.* `Tooling ready`
- [ ] **64** (P0) Get the LOD below 10 µg/L. *Not software. The platform reads LOD from the calibration record and never claims below the validated LOD (v5.8 floor). Workbook §64: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **65** (P0) Measure LOD and LOQ properly (>= 10 blanks). *Docs/templates/standards_template.csv (>= 10 blanks, 6 standards) -> Analysis/linearity.py: LOD 3.3 s/slope from residual and blank SD, LOQ, lack-of-fit. Workbook §65.* `Tooling ready`
- [ ] **66** (P0) As(III) vs As(V) pre-reduction and recovery. *spike_recovery QC runs for As(V) recovery with/without pre-reduction; arsenic_species per reading. Chemistry with the supervisor. Workbook §66.* `Tooling ready`
- [ ] **67** (P0) Copper interference measured and mitigated. *Analysis/interference.py (recovery vs Cu with CI); robust baseline + secondary-peak flag in the pipeline (v5.8). Measurement is lab work.* `Tooling ready`
- [ ] **88** (P0) Certified reference material and recovery %. *check_standard QC runs with a CRM; recovery in the QC log and control chart. Workbook §88.* `Tooling ready`
- [ ] **89** (P0) Blanks with every batch. *POST /api/qc/runs blank and field_blank (v5.7/v5.9); low readings are gated on recent blanks. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **90** (P0) 10 µg/L check standard start and end of each field day; reject if > 20 % drift. *v5.7 check-standard gate (80-120 %); Analysis/control_chart.py (v5.9) shows drift before it fails a day; run_order.py puts the opening and closing checks on every sheet. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **91** (P0) Spike recovery on real samples (80-120 %). *spike_recovery QC run type (v5.9) with baseline and recovery %. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **108** (P0) Replace simulated data with >= 40 real samples / 15 sources / 2 districts. *Data/field/README.md + paired_template.csv; /api/scans; bridge --file; GET /api/data/export/paired. Needs the field programme.* `Tooling ready`
- [ ] **109** (P0) Pre-register the analysis. *The analysis is fixed in code: paired_validation.py (end points, cutoffs, statistics). Write the pre-registration in the logbook citing the script version (git commit). Workbook §109.* `Partial`
- [ ] **110** (P0) Confusion matrix at 10 and 50 µg/L with Wilson CIs; missed unsafe count. *paired_validation.py cutoffs 10 / 20 / 50 (v5.9) with Wilson intervals and missed-unsafe counts; /api/validation endpoint (v5.6). Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **111** (P0) Proper sample collection; split; chain of custody. *SampleMeta (purge, bottle, preservation, custody note, split_for_lab, collected_at) stored with readings/scans and exported (v5.9). Procedure in Data/field/README.md. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **112** (P0) Record GPS / source type / depth / date-time per sample. *Device site (lat/long) + SampleMeta source_kind, depth_m, collected_at (v5.9). Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **130** (P0) Scatter with 1:1 line and Bland-Altman. *paired_validation.py (v5.8). Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **131** (P0) Regression slope/intercept with CIs (Deming). *paired_validation.py Deming with bootstrap CIs (v5.8). Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **132** (P0) Justify the sample size (CI width). *paired_validation.py sample-size table (v5.9): Wilson CI width vs n unsafe. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **148** (P0) Be honest that V3 was trained on simulated readings; evaluate on real data. *Docs/CLAIMS_REGISTER.md N1; Analysis/aquanet_v3_field_eval.py (v5.9) evaluates the deployed network on paired rows. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **149** (P0) Baseline: threshold rule and logistic regression. *aquanet_v3_field_eval.py reports both baselines on the same rows. Counts as done only once real samples or hardware have gone through it.* `Tooling ready`
- [ ] **150** (P0) Confusion matrix on held-out real data. *aquanet_v3_field_eval.py; needs the paired dataset.* `Tooling ready`
- [ ] **164** (P0) Working robust prototype with a dummy cell at the fair. *Workbook §164: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **165** (P0) Power consumption per mode; battery life. *Docs/templates/power_log_template.csv -> Analysis/power_budget.py: mAh/day, battery life, share by mode. Workbook §165.* `Tooling ready`
- [ ] **210** (P0) Cost per test and per device from receipts. *bom_template.csv -> project_figures.py cost. Workbook §210.* `Tooling ready`
- [ ] **220** (P0) Hazardous chemical list with SDS; SRC review. *Workbook §220: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **221** (P0) All ISEF forms prepared. *Workbook §221: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **222** (P0) Arsenic work in a proper lab; waste plan. *Workbook §222: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **226** (P0) Dated logbook. *Not software (git history is the software logbook). Workbook §226: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **227** (P0) 250-word abstract in your own words. *Workbook §227: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **231** (P0) One clear story; title states the result. *Workbook §231: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **232** (P0) Results panel largest: scatter / confusion / LOD. *make_poster_figures.py produces them from the paired CSV.* `Tooling ready`
- [ ] **241** (P0) 60-second and 3-minute pitch. *Workbook §241: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **242** (P0) Every member explains chemistry / statistics / code. *Not software (Docs/CODE_GUIDE.md for the code). Workbook §242: Docs/TEAM_WORKBOOK.md.* `Worksheet`
- [ ] **243** (P0) Top 40 hard questions rehearsed. *Not software; Docs/CLAIMS_REGISTER.md gives the honest answers to the first ten. Workbook §243: Docs/TEAM_WORKBOOK.md.* `Worksheet`

## In the laboratory (chemistry and bench) (11)

Needs chemicals, a supervisor and the instrument, under the approved research plan. Each row names its template in Docs/templates/ and the script that turns the measurement into the figure.


**D Design**

- [ ] **56** (P1) Design rationale for sample well and pump volumes. *Measure dead volume, fill and rinse volumes; Docs/templates/carryover_holdtime_sheet.csv. Workbook §56.*

**E Sensor**

- [ ] **79** (P1) Dissolved oxygen effect. *interference_template.csv with dissolved oxygen as the interferent; dissolved_oxygen_mg_l field. Workbook §79.*
- [ ] **81** (P2) Electrode surface characterisation. *Microscope photos before/after N scans; photo_log.csv; HARDWARE_CHANGELOG. Workbook §81.*
- [ ] **83** (P2) Reagent consumption and waste per test. *Measured volumes into bom_template.csv reagent rows and the safety panel. Workbook §83.*
- [ ] **84** (P2) Potentiostat noise floor with a dummy cell. *Dummy-cell scan through /api/scans; noise_sigma_ua recorded per scan. Workbook §84.*

**J Hardware**

- [ ] **166** (P1) Characterise the potentiostat. *Dummy-cell noise, linearity vs resistors, step response; tune QC_REF_* thresholds. Workbook §166.*
- [ ] **167** (P1) Pump and fluidics tests; carry-over. *carryover_holdtime_sheet.csv carryover rows; field_blank QC runs. Workbook §167.*
- [ ] **168** (P1) Enclosure IP / UV / heat tests. *Docs/templates/enclosure_test_log.csv. Workbook §168.*
- [ ] **169** (P1) Drop / vibration test. *enclosure_test_log.csv drop/vibration rows. Workbook §169.*

**K Firmware**

- [ ] **185** (P1) Watchdog and brown-out tested. *Provoke a hang and a sag; reset counters in /status.json. Workbook §185.*
- [ ] **187** (P2) Flash and test on two boards. *Flash two boards; inter-device comparison (item 100). Workbook §187.*

## In the field (4)

Needs real sources, sample bottles and a laboratory partner.


**G Field**

- [ ] **113** (P1) Sample set covers the range. *Not software; paired_validation reports the distribution so gaps are visible. Workbook §113: Docs/TEAM_WORKBOOK.md.*
- [ ] **116** (P1) Multiple conditions (hot/cold, turbidity, iron, operators, rain). *Not software; SampleMeta.collector and the sensors record the conditions. Workbook §116: Docs/TEAM_WORKBOOK.md.*
- [ ] **117** (P1) Compare with the government field test kit. *Not software; add a kit_result column to the paired CSV for the comparison. Workbook §117: Docs/TEAM_WORKBOOK.md.*
- [ ] **118** (P1) Repeat sources in a second season. *Not software; readings are timestamped and the trend endpoint shows change. Workbook §118: Docs/TEAM_WORKBOOK.md.*

## Run the ready-made tools on real data (45)

The software for these exists and is tested, but nothing real has gone through it yet. Each closes when the measurements are made and the script or endpoint in the row is run on them.


**C Prior art**

- [ ] **47** (P2) Landscape figure: cost vs LOD. *Analysis/project_figures.py landscape from Data/field/landscape_template.csv (numbers to fill). Counts as done only once real samples or hardware have gone through it.*

**D Design**

- [ ] **57** (P1) Justify electrode choice with own measurements. *Analysis/electrode_study.py + decision_matrix.py on your electrode measurements. Workbook §57.*
- [ ] **58** (P2) Bill of materials with prices; cost per test. *Data/field/bom_template.csv -> Analysis/project_figures.py cost. Workbook §58.*

**E Sensor**

- [ ] **68** (P1) Other interferents (Fe, Mn, phosphate, silicate, humics, chloride, hardness). *Analysis/interference.py takes any interferent.*
- [ ] **69** (P1) pH and temperature effects and corrections. *Analysis/interference.py with pH / temperature as the x variable (Docs/templates/interference_template.csv). Workbook §69.*
- [ ] **70** (P1) Electrode lifetime (scans until slope drops 10 %). *Docs/templates/electrode_log_template.csv -> Analysis/electrode_study.py: scans to -10 %, drift per 100 scans. Workbook §70.*
- [ ] **71** (P1) Electrode-to-electrode variability (>= 5 electrodes; 2 lots). *electrode_study.py: slope per electrode, CV across electrodes, lot comparison (F ratio); paired_validation by lot. Workbook §71.*
- [ ] **72** (P1) Repeatability and intermediate precision. *electrode_study.py repeatability (within session) and intermediate precision (across sessions/operators); paired_validation replicate CV. Workbook §72.*
- [ ] **73** (P1) Linearity with >= 6 standards and residual plot. *Analysis/linearity.py: >= 6 standards, residual plot, pure-error lack-of-fit test. Workbook §73.*
- [ ] **75** (P1) Raw voltammograms for blank / 10 / 50 / 100 on one plot. *Every scan is stored (v5.8) and GET /api/scans/{id} returns raw, smoothed and baseline arrays; the dashboard shows the trace. Real scans needed.*
- [ ] **76** (P1) Validate peak finding against >= 50 hand-measured scans. *Analysis/peak_check.py (v5.9): bias, limits of agreement, Deming slope, worst disagreements.*
- [ ] **77** (P1) Matrix effects: real water vs DI slopes. *Standard-addition endpoint per device; spike_recovery QC; paired_validation 'By site'.*
- [ ] **78** (P1) External calibration vs standard addition against ICP-MS. *Both calibration types are stored with IDs; reprocess any stored scan with either (v5.8) and compare in paired_validation.*
- [ ] **80** (P2) Cheaper electrode comparison. *electrode_log by electrode_lot -> electrode_study.py; decision_matrix.py. Workbook §80.*
- [ ] **82** (P2) Sample stability / hold time. *carryover_holdtime_sheet.csv hold_time rows; SampleMeta.collection_to_analysis_min stored. Workbook §82.*
- [ ] **86** (P2) SWASV parameter DoE (2^3 factorial). *Analysis/doe_factorial.py --plan (randomised 2^k plan) and analysis (effects, 95 % CIs, Pareto). Workbook §86.*
- [ ] **87** (P2) Peak current vs deposition time plot. *linearity.py deposition_s column -> peak vs deposition time per standard. Workbook §87.*

**F Metrology**

- [ ] **95** (P1) Blind samples. *Analysis/run_order.py: coded run sheet for the operator, sealed key for the supervisor (v5.9). Counts as done only once real samples or hardware have gone through it.*
- [ ] **96** (P1) Randomise run order. *run_order.py (seeded shuffle; opening and closing checks fixed). Counts as done only once real samples or hardware have gone through it.*
- [ ] **98** (P1) Calibrate pH / EC / temperature / turbidity sensors or drop them from claims. *QC run types ph_buffer, conductivity_standard, turbidity_standard, temperature_reference (v5.9); /api/qc/status reports sensor_checks.verified per sensor. Counts as done only once real samples or hardware have gone through it.*
- [ ] **99** (P2) Shewhart control charts for the check standard. *Analysis/control_chart.py (v5.9) with Western Electric rules. Counts as done only once real samples or hardware have gone through it.*
- [ ] **100** (P2) Inter-device comparison. *Same sample_code on readings from 2-3 devices; paired_validation groups by device via the site table.*

**G Field**

- [ ] **114** (P1) 30-day continuous deployment with weekly lab samples. *Firmware + Analysis/deployment_report.py on GET /api/data/export (uptime, gaps, late deliveries, QC, outcomes, battery). Workbook §114.*
- [ ] **122** (P2) Share results back with owners and the district lab. *QR public page per source (v5.6), PDF certificate, JJM export. Counts as done only once real samples or hardware have gone through it.*
- [ ] **126** (P2) Cost actually spent per sample. *scale_estimate.py rows field_samples_collected / field_total_spend_inr. Workbook §126.*
- [ ] **129** (P2) Map the field results and screenshot for the poster. *Dashboard map (v5.6); demo data has no coordinates so only real sites appear (v5.7).*

**H Statistics**

- [ ] **133** (P1) ROC curve and threshold choice. *paired_validation.py ROC/AUC at 10 / 20 / 50; aquanet_v2_pipeline referral curve. Counts as done only once real samples or hardware have gone through it.*
- [ ] **134** (P1) Precision as CV % at low / medium / high. *paired_validation.py replicate CV by band (v5.9). Counts as done only once real samples or hardware have gone through it.*
- [ ] **136** (P1) Uncertainty for every number on the poster. *Every metric in the analysis reports carries an interval and n. Counts as done only once real samples or hardware have gone through it.*
- [ ] **139** (P1) Interference by regression with CI. *Analysis/interference.py (v5.9). Counts as done only once real samples or hardware have gone through it.*
- [ ] **143** (P2) Trend detection on the 30-day deployment. *Mann-Kendall + Sen slope endpoint (v5.4) needs the real deployment.*

**I AquaNet**

- [ ] **152** (P1) Feature importance / ablation. *aquanet_v3_field_eval.py ablation table. Counts as done only once real samples or hardware have gone through it.*
- [ ] **153** (P1) Calibration / reliability diagram. *aquanet_v3_field_eval.py reliability.svg + ECE; aquanet_v2_pipeline reliability. Counts as done only once real samples or hardware have gone through it.*
- [ ] **160** (P2) Describe the failure cases. *aquanet_v3_field_eval.py lists the rows the network gets wrong. Counts as done only once real samples or hardware have gone through it.*

**J Hardware**

- [ ] **171** (P1) Solar sizing with real insolation data. *power_budget.py --sun-hours (worst-month peak-sun hours) -> panel W and battery for autonomy. Workbook §171.*
- [ ] **177** (P2) Reduce the cost; cost curve across versions. *One BOM CSV per hardware version -> project_figures.py cost each. Workbook §177.*

**K Firmware**

- [ ] **182** (P1) 14-day soak test. *deployment_report.py on the 14-day export. Workbook §182.*
- [ ] **183** (P1) Offline buffering demo (3 days off, all readings arrive once). *Firmware ring buffer + idempotent uploads; bridge outbox tests; deployment_report.py counts late deliveries as the evidence. Run on a board and log it (Workbook §183). Counts as done only once real samples or hardware have gone through it.*
- [ ] **184** (P1) Safe OTA with rollback. *OTA with rollback and signed manifests (v5.5-v5.6); demonstrate on a board. Counts as done only once real samples or hardware have gone through it.*
- [ ] **190** (P2) Deep-sleep strategy with numbers. *power_log_template.csv deep_sleep row -> power_budget.py. Workbook §190.*

**L Software**

- [ ] **194** (P1) Lab-confirmation panel with real paired results. *Panel exists (v5.6); needs real pairs.*

**N Impact**

- [ ] **211** (P1) Scale estimate with assumptions. *Docs/templates/scale_assumptions_template.csv -> Analysis/scale_estimate.py (ranges, missing assumptions named). Workbook §211.*
- [ ] **214** (P1) Maintenance needs per month. *scale_estimate.py maintenance block from the QC rules (7-day check standard, 90-day calibration) + electrode life. Workbook §214.*

**Q Poster**

- [ ] **233** (P1) Every graph: units; n; error bars; source. *svg_plots subtitles carry n and the fit; axes carry units. Counts as done only once real samples or hardware have gone through it.*
- [ ] **236** (P1) Printed QR code to the repository / DOI. *Analysis/project_figures.py qr -> qr.svg / qr.pdf. Counts as done only once real samples or hardware have gone through it.*

## Finish what the software started (22)

The software did its share; the rest is writing, drawing, measuring or choosing.


**A Pathway**

- [ ] **16** (P1) Work backwards from the fair date. *Milestones (field data -8 weeks, poster -6 weeks, 3 mocks) are rows in Docs/planning/timeline.csv. Workbook §16.*
- [ ] **17** (P1) Scope freeze date (15 March 2027). *Row in timeline.csv. In software: tag the frozen version (git tag isef-2027, item 265). Workbook §17.*

**B Need**

- [ ] **32** (P2) Map of affected habitations next to test sites. *Dashboard map shows tested sites; the affected-habitation layer needs the government source (item 49). Workbook §32.*

**C Prior art**

- [ ] **38** (P1) Compare with open-source and commercial potentiostats. *Rows for Bullen et al. and commercial instruments in landscape_template.csv; fill the numbers. Workbook §38.*
- [ ] **41** (P1) Cite the Indian field-testing ecosystem (JJM kits; WQMIS; NABL). *JJM/WQMIS export exists (GET /api/data/export/jjm); cite the documents yourself. Workbook §41.*
- [ ] **44** (P2) Cite WHO and BIS documents directly. *Docs/IMPROVEMENT_LOG.md and app/standards.py cite the documents used by the code; cite them in your paper. Workbook §44.*

**D Design**

- [ ] **51** (P1) Separate chemistry / instrument / system. *Docs/REQUIREMENTS_TRACEABILITY.md and ROADMAP_COVERAGE.md are organised by those three layers; use the same split on the poster. Workbook §51.*
- [ ] **52** (P1) Block diagram of the instrument with part numbers. *Firmware/PINOUT.md gives every pin and part; draw the block diagram from it. Workbook §52.*

**F Metrology**

- [ ] **102** (P2) SOP for a measurement. *Docs/SOP_MEASUREMENT.md: instrument and software steps written; chemistry steps are placeholders for the supervisor. Workbook §102.*
- [ ] **106** (P2) Show what happens without the controls. *Reprocess stored scans with another calibration (v5.8) shows the calibration control; temperature correction needs item 69 first. Workbook §106.*

**G Field**

- [ ] **125** (P2) Time per test measured with a stopwatch. *Firmware prints time to first result (v5.9) and the scan duration is in scan settings; the hands-on part is a stopwatch. Workbook §125.*
- [ ] **127** (P2) Keep odd samples for retest. *The retest outcome flags them; sample_code links the retest to the original. Workbook §127.*

**H Statistics**

- [ ] **140** (P1) Explain outliers individually. *paired_validation and peak_check list the largest disagreements; the explanation goes in the logbook. Workbook §140.*
- [ ] **142** (P2) Mixed model for repeated readings per source. *Grouped-by-site evaluation in aquanet_v2_pipeline avoids the independence error; a mixed model is future work once there are repeated visits. Workbook §142.*

**I AquaNet**

- [ ] **151** (P1) Why a network at all. *The ablation in aquanet_v3_field_eval.py answers it with data; the argument is yours to write. Workbook §151.*
- [ ] **156** (P1) Document the training-data generation. *Docs/neural/AQUANET_V3_REPORT.md and scripts/train_aquanet_v2.py describe the distributions and noise; the 'why realistic' citation is yours. Workbook §156.*

**J Hardware**

- [ ] **170** (P1) PCB or neat perfboard; wiring diagram; labelled photo. *Firmware/PINOUT.md gives the wiring table to draw from. Workbook §170.*
- [ ] **175** (P2) Device UI usable without a phone (LED/buzzer legend). *Firmware drives status LED patterns; print the legend on the lid. Workbook §175.*

**L Software**

- [ ] **197** (P2) Page load on a cheap Android phone on 3G. *Docs/PRIVACY_AND_PERFORMANCE.md records a throttled headless measurement; measure on a real phone too. Workbook §197.*

**P Logbook**

- [ ] **229** (P1) Limitations section. *Docs/CLAIMS_REGISTER.md lists every limit (LOD, species, Cu, sample size, simulated training) as targets; write the prose yourself. Workbook §229.*

**S Credibility**

- [ ] **255** (P2) Open-source the hardware with a licence. *Docs/CREDITS.md lists the licence slot; choose CERN-OHL or similar. Workbook §255.*

**U Repository**

- [ ] **267** (P2) Names and roles in the README. *README 'Team' section added with the contributors visible in git history; complete it when the team is final. Workbook §267.*

## Team work: rules, writing, people, poster and interview (75)

No software share. Logbook, forms, writing and practice; the worksheet in Docs/TEAM_WORKBOOK.md gives the steps.


**A Pathway**

- [ ] **14** (P1) Enter Stockholm Junior Water Prize India. *Workbook §14: Docs/TEAM_WORKBOOK.md.*
- [ ] **15** (P1) Pick the ISEF category on purpose. *Not software (ENEV recommended by the roadmap). Workbook §15: Docs/TEAM_WORKBOOK.md.*
- [ ] **18** (P2) Travel documents early. *Row in timeline.csv. Workbook §18: Docs/TEAM_WORKBOOK.md.*
- [ ] **19** (P2) Two reviews with a statistics mentor. *Row in timeline.csv; Analysis/*/report.md are what to review. Workbook §19: Docs/TEAM_WORKBOOK.md.*

**B Need**

- [ ] **27** (P1) Quantify the gap (time to lab result; retest frequency). *Not software. The paired export's pair_gap_hours measures it for your own samples. Workbook §27: Docs/TEAM_WORKBOOK.md.*
- [ ] **28** (P1) Why continuous monitoring matters (seasonal change). *Not software; the trend endpoint (Mann-Kendall) shows it on real data later. Workbook §28: Docs/TEAM_WORKBOOK.md.*
- [ ] **29** (P1) Health end point in plain words. *Workbook §29: Docs/TEAM_WORKBOOK.md.*
- [ ] **31** (P1) One testable research question. *Not software. Analysis/paired_validation.py computes the sensitivity it asks about. Workbook §31: Docs/TEAM_WORKBOOK.md.*
- [ ] **33** (P2) One stakeholder quote. *Workbook §33: Docs/TEAM_WORKBOOK.md.*
- [ ] **35** (P2) Why arsenic first and where the design extends. *Workbook §35: Docs/TEAM_WORKBOOK.md.*

**C Prior art**

- [ ] **39** (P1) Past ISEF projects on arsenic / water sensing. *Workbook §39: Docs/TEAM_WORKBOOK.md.*
- [ ] **40** (P1) Patent search. *Workbook §40: Docs/TEAM_WORKBOOK.md.*
- [ ] **42** (P2) Earlier Indian student / startup efforts. *Workbook §42: Docs/TEAM_WORKBOOK.md.*
- [ ] **43** (P2) BibTeX/Zotero library; one citation style. *Workbook §43: Docs/TEAM_WORKBOOK.md.*
- [ ] **46** (P2) List what you deliberately did not do. *Not software (Docs/DECISION_LOG.md has a place for it). Workbook §46: Docs/TEAM_WORKBOOK.md.*

**D Design**

- [ ] **55** (P1) Choose one competition prototype. *Not software (recommendation recorded in CLAIMS_REGISTER S6). Workbook §55: Docs/TEAM_WORKBOOK.md.*
- [ ] **59** (P2) Design for manufacture; assembly time. *Workbook §59: Docs/TEAM_WORKBOOK.md.*
- [ ] **60** (P2) What you'd change for a production unit. *Workbook §60: Docs/TEAM_WORKBOOK.md.*
- [ ] **62** (P2) Exploded view of the enclosure. *Not software (STL files in models_3d/). Workbook §62: Docs/TEAM_WORKBOOK.md.*
- [ ] **63** (P2) Keep the old prototypes. *Workbook §63: Docs/TEAM_WORKBOOK.md.*

**E Sensor**

- [ ] **74** (P1) Explain the electrochemistry on a poster panel. *Not software (Docs/IMPROVEMENT_LOG.md §4 has the method text to start from). Workbook §74: Docs/TEAM_WORKBOOK.md.*
- [ ] **85** (P2) Speciation as an extension. *Docs/templates/future_work_template.md. Workbook §85.*

**F Metrology**

- [ ] **97** (P1) Written cleaning protocol. *Not software; Docs/SOP_MEASUREMENT.md has the slot. Workbook §97: Docs/TEAM_WORKBOOK.md.*
- [ ] **103** (P2) Independent person repeats the SOP. *Workbook §103: Docs/TEAM_WORKBOOK.md.*
- [ ] **105** (P2) Balance and pipette calibration checks. *Not software (logbook). Workbook §105: Docs/TEAM_WORKBOOK.md.*

**G Field**

- [ ] **119** (P1) Photograph every site. *Workbook §119: Docs/TEAM_WORKBOOK.md.*
- [ ] **120** (P1) Letter from the lab. *Workbook §120: Docs/TEAM_WORKBOOK.md.*
- [ ] **121** (P1) Budget the lab costs. *Workbook §121: Docs/TEAM_WORKBOOK.md.*
- [ ] **123** (P2) Responsible communication plan for a high result. *Not software; alert channels exist and are off by default for practice data. Workbook §123: Docs/TEAM_WORKBOOK.md.*
- [ ] **128** (P2) Usability trial with a non-expert. *Not software (IRB). Workbook §128: Docs/TEAM_WORKBOOK.md.*

**H Statistics**

- [ ] **144** (P2) Check the analysis with a statistics teacher. *Workbook §144: Docs/TEAM_WORKBOOK.md.*
- [ ] **147** (P2) Raw data in a public repository with a DOI. *Not software; Data/field/README.md says what to deposit. Workbook §147: Docs/TEAM_WORKBOOK.md.*

**J Hardware**

- [ ] **172** (P1) Tool-free electrode replacement. *Workbook §172: Docs/TEAM_WORKBOOK.md.*
- [ ] **173** (P2) Custom PCB (KiCad). *Workbook §173: Docs/TEAM_WORKBOOK.md.*
- [ ] **178** (P2) Spares at the fair. *Workbook §178: Docs/TEAM_WORKBOOK.md.*
- [ ] **179** (P2) Label 3D-printed parts with versions. *Workbook §179: Docs/TEAM_WORKBOOK.md.*
- [ ] **180** (P2) Tolerance / fit tests for printed parts. *Workbook §180: Docs/TEAM_WORKBOOK.md.*

**L Software**

- [ ] **193** (P1) One alert reaching a real phone (video). *Alert channels exist (v5.6); record the video yourself. Workbook §193: Docs/TEAM_WORKBOOK.md.*
- [ ] **196** (P2) Translate alert text with a native speaker. *Not software; the HI/BN/AS/PA strings are machine-assisted and must be checked (i18n-*.js). Workbook §196: Docs/TEAM_WORKBOOK.md.*

**M Users**

- [ ] **202** (P1) Interview >= 5 stakeholders (IRB). *Workbook §202: Docs/TEAM_WORKBOOK.md.*
- [ ] **203** (P1) Comprehension test of the result screen. *Not software (the public QR page is the screen to test). Workbook §203: Docs/TEAM_WORKBOOK.md.*
- [ ] **204** (P1) Communication protocol for an unsafe reading. *Not software; alert routing is configurable. Workbook §204: Docs/TEAM_WORKBOOK.md.*
- [ ] **206** (P2) Equity: who pays / maintains / owns the data. *Workbook §206: Docs/TEAM_WORKBOOK.md.*
- [ ] **207** (P2) Letter of support. *Workbook §207: Docs/TEAM_WORKBOOK.md.*
- [ ] **208** (P2) Consent for photos and names. *Not software; SampleMeta.collector takes initials only. Workbook §208: Docs/TEAM_WORKBOOK.md.*
- [ ] **209** (P2) What happens to devices after the project. *Workbook §209: Docs/TEAM_WORKBOOK.md.*

**N Impact**

- [ ] **212** (P1) Health impact plainly. *Workbook §212: Docs/TEAM_WORKBOOK.md.*
- [ ] **213** (P1) Deployment model chosen. *Workbook §213: Docs/TEAM_WORKBOOK.md.*
- [ ] **215** (P2) Talk to a partner. *Workbook §215: Docs/TEAM_WORKBOOK.md.*
- [ ] **216** (P2) Provisional patent only if warranted. *Workbook §216: Docs/TEAM_WORKBOOK.md.*
- [ ] **217** (P2) Environmental impact of the device. *Workbook §217: Docs/TEAM_WORKBOOK.md.*
- [ ] **218** (P2) Extension to fluoride / nitrate / uranium / lead. *Workbook §218: Docs/TEAM_WORKBOOK.md.*

**O Safety**

- [ ] **223** (P1) Lab safety log per session. *Workbook §223: Docs/TEAM_WORKBOOK.md.*
- [ ] **224** (P1) Most dilute stock that works. *Workbook §224: Docs/TEAM_WORKBOOK.md.*
- [ ] **225** (P2) Safety on the poster. *Workbook §225: Docs/TEAM_WORKBOOK.md.*

**P Logbook**

- [ ] **228** (P1) Full IMRaD paper. *Workbook §228: Docs/TEAM_WORKBOOK.md.*
- [ ] **230** (P1) Future work: 3 concrete experiments. *Workbook §230: Docs/TEAM_WORKBOOK.md.*

**Q Poster**

- [ ] **234** (P1) Supporting documents on the table. *Workbook §234: Docs/TEAM_WORKBOOK.md.*
- [ ] **235** (P1) Prototype opened on the table + used electrode. *Workbook §235: Docs/TEAM_WORKBOOK.md.*
- [ ] **237** (P2) Check display and safety rules. *Workbook §237: Docs/TEAM_WORKBOOK.md.*
- [ ] **240** (P2) Three strangers read the poster. *Workbook §240: Docs/TEAM_WORKBOOK.md.*

**R Interview**

- [ ] **244** (P1) 3 mock judging sessions. *Row in timeline.csv. Workbook §244: Docs/TEAM_WORKBOOK.md.*
- [ ] **245** (P1) Know the numbers by heart. *Numbers come from the analysis reports once real data exist. Workbook §245: Docs/TEAM_WORKBOOK.md.*
- [ ] **246** (P1) Practise 'I don't know but here is how I'd find out'. *Workbook §246: Docs/TEAM_WORKBOOK.md.*
- [ ] **247** (P1) Prepare for special-award judges. *Workbook §247: Docs/TEAM_WORKBOOK.md.*
- [ ] **248** (P2) Practise with interruptions. *Workbook §248: Docs/TEAM_WORKBOOK.md.*
- [ ] **249** (P2) One true field story. *Workbook §249: Docs/TEAM_WORKBOOK.md.*
- [ ] **250** (P2) Record a practice interview. *Workbook §250: Docs/TEAM_WORKBOOK.md.*

**S Credibility**

- [ ] **251** (P1) Find a mentor; log meetings. *Workbook §251: Docs/TEAM_WORKBOOK.md.*
- [ ] **252** (P1) Present at a school fair first. *Workbook §252: Docs/TEAM_WORKBOOK.md.*
- [ ] **253** (P2) Submit the paper to a student journal. *Workbook §253: Docs/TEAM_WORKBOOK.md.*
- [ ] **254** (P2) Publish the dataset with a DOI. *Workbook §254: Docs/TEAM_WORKBOOK.md.*
- [ ] **256** (P2) Youth innovation programmes only with real data. *Workbook §256: Docs/TEAM_WORKBOOK.md.*

**T Cut**

- [ ] **260** (P2) Catamaran and tank prototypes as future work. *Not software (docs in Docs/hardware/ are labelled as concepts). Workbook §260: Docs/TEAM_WORKBOOK.md.*

**U Repository**

- [ ] **265** (P2) Tag the fair version (git tag isef-2027). *Run at the scope freeze: git tag -a isef-2027 -m 'version shown at ISEF 2027' && git push origin isef-2027. Workbook §265: Docs/TEAM_WORKBOOK.md.*

## Outside the roadmap

- [ ] Write sections 2-4 of `Docs/AI_USE_STATEMENT_TEMPLATE.md` (what you checked, what you designed, what the AI did not do) in your own words, and print it for the booth.
- [ ] Have native speakers check the Hindi, Bengali, Assamese and Punjabi screens (`AquaSentry_Platform/frontend/i18n-*.js`); they were machine-assisted.
- [ ] Complete the Team section of `README.md` with every member's name and role once the team is final (ISEF allows at most three).
- [ ] Confirm in writing whether the team entered IRIS 2026-27 and record the answer and the next fair in `Docs/planning/timeline.csv`.
- [ ] Review GitHub's automatic dependency pull requests (Dependabot) as they arrive; CI must pass before merging.
- [ ] Tune the firmware's reference-electrode thresholds (`QC_REF_MAX_ABS_UA`, `QC_REF_MAX_DRIFT_UA`) from the dummy-cell characterisation (item 166) before the first field day.

## Already done in software

57 items need nothing more from the code; they are listed with their file and test in `Docs/ISEF_ROADMAP_STATUS.md`. *Done* there never means the sensor works: every accuracy claim still waits for real paired samples in `Data/field/`.
