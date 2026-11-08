# What is left before ISEF

Generated from `Docs/planning/isef_roadmap_status.csv` by `Analysis/roadmap_status.py` (edit the CSV, rerun; a test keeps this page in sync). Item numbers match `Docs/ISEF_ROADMAP.md`, where each item is explained.

**213 of 267 roadmap items are still open.** The software is finished except two items that wait for data; what remains is laboratory work (15), field work (4), running the ready-made tools on real measurements (50), finishing items the software started (38) and the team's own work (104: rules, writing, people, poster, interview).

Tick items here or copy the list into the logbook with the date you finish each one. The logbook is the evidence; this page is the plan. Do not let an AI write the research plan, abstract, poster or citations (item 1).

## Start here: the 53 must-do (P0) items

These decide whether the project is ISEF-level at all. The order is the roadmap's: rules first, then the science.

- [ ] **1** (P0) No generative AI for the research plan / abstract / poster / citations. *Rule. Everything in this repository was AI-assisted: use it as notes; write your own documents. Docs/AI_USE_STATEMENT_TEMPLATE.md lists what was AI-assisted so the disclosure is accurate.* `Team`
- [ ] **2** (P0) Disclose AI use (one-page statement). *Docs/AI_USE_STATEMENT_TEMPLATE.md: factual inventory of AI-assisted files, tools and versions; the 'what we checked / designed ourselves' sections are yours to write.* `Partial`
- [ ] **3** (P0) Be able to explain every file you show. *Docs/CODE_GUIDE.md walks the code; Docs/DEMO_SCRIPT.md names the 3 screens to show. Rewrite or drop anything you cannot explain.* `Team`
- [ ] **4** (P0) 12-month rule: research window from Jan 2026. *Write the start date in the logbook; Docs/planning/timeline.csv has the window; git history dates every software change.* `Team`
- [ ] **5** (P0) Continuation: Form 7 and 'previous work' labels. *Not software. CHANGELOG.md separates versions by date for the 'what is new this year' table.* `Team`
- [ ] **6** (P0) Research plan before experimenting; addenda. *Not software. Analysis/run_order.py and Data/field/README.md give the procedures section concrete steps.* `Team`
- [ ] **7** (P0) SRC review; Form 3 risk assessment; SDS for every chemical. *Not software. See section O.* `Team`
- [ ] **8** (P0) IRB approval before any survey or interview. *Not software.* `Team`
- [ ] **9** (P0) Team rules (up to 3; fixed for the year). *Not software. README 'Team' section to be completed (item 267).* `Team`
- [ ] **10** (P0) Booth must work without electricity or internet. *Poster figures are SVG/PDF from Analysis/make_poster_figures.py; QR code prints (project_figures.py qr). Print the figures; the dashboard is a bonus.* `Partial`
- [ ] **12** (P0) Confirm IRIS 2026-27 submission status. *Not software. Record the answer in the logbook.* `Team`
- [ ] **13** (P0) All real dates in one calendar. *Docs/planning/timeline.csv seeded with the published dates; Analysis/project_figures.py gantt draws it. Confirm the IRIS dates on iris.exstemplar.com.* `Partial`
- [ ] **22** (P0) One sentence of need with a number and source. *Write it yourself from JJM / CGWB; cite the year.* `Team`
- [ ] **23** (P0) State who the primary user is. *Not software. The platform supports district-lab, panchayat and household views; pick one for the story.* `Team`
- [ ] **24** (P0) Design criteria as measurable targets. *Docs/REQUIREMENTS_TRACEABILITY.md lists each criterion with the test that proves it and the current result/target.* `Partial`
- [ ] **25** (P0) Constraints written down. *Docs/REQUIREMENTS_TRACEABILITY.md 'Constraints' section (power, network, languages, hard water, iron/manganese, temperature) with what the software does about each.* `Partial`
- [ ] **26** (P0) Why current options fail the criteria (comparison table). *Data/field/landscape_template.csv + project_figures.py landscape give the figure once the numbers are filled from datasheets.* `Partial`
- [ ] **36** (P0) Literature review (20+ papers; table). *Not software. Keep the table as a CSV (method, LOD, interferents, cost, field-tested) next to Data/field/landscape_template.csv so the landscape figure draws from it.* `Team`
- [ ] **37** (P0) One sentence of what is new. *Not software; Docs/CLAIMS_REGISTER.md shows what is and is not demonstrated.* `Team`
- [ ] **48** (P0) Alternatives considered with decision matrices. *Not software. Docs/DECISION_LOG.md records the software choices and their alternatives.* `Team`
- [ ] **49** (P0) Weighted criteria and scores per matrix. *Not software.* `Team`
- [ ] **64** (P0) Get the LOD below 10 µg/L. *Not software. The platform reads LOD from the calibration record and never claims below the validated LOD (v5.8 floor).* `Lab`
- [ ] **65** (P0) Measure LOD and LOQ properly (>= 10 blanks). *POST /api/qc/runs (blank) stores every blank; the calibration endpoints compute 3.3 s/slope; Analysis/paired_validation.py reports it. Needs real blanks.* `Tooling ready`
- [ ] **66** (P0) As(III) vs As(V) pre-reduction and recovery. *arsenic_species on every reading; lab_species on results; spike_recovery QC runs (v5.9). Chemistry is lab work.* `Tooling ready`
- [ ] **67** (P0) Copper interference measured and mitigated. *Analysis/interference.py (recovery vs Cu with CI); robust baseline + secondary-peak flag in the pipeline (v5.8). Measurement is lab work.* `Tooling ready`
- [ ] **88** (P0) Certified reference material and recovery %. *check_standard and spike_recovery QC runs record recovery; the CRM itself must be bought.* `Tooling ready`
- [ ] **89** (P0) Blanks with every batch. *Software ready, not yet run on real samples or hardware. POST /api/qc/runs blank and field_blank (v5.7/v5.9); low readings are gated on recent blanks.* `Tooling ready`
- [ ] **90** (P0) 10 µg/L check standard start and end of each field day; reject if > 20 % drift. *Software ready, not yet run on real samples or hardware. v5.7 check-standard gate (80-120 %); Analysis/control_chart.py (v5.9) shows drift before it fails a day; run_order.py puts the opening and closing checks on every sheet.* `Tooling ready`
- [ ] **91** (P0) Spike recovery on real samples (80-120 %). *Software ready, not yet run on real samples or hardware. spike_recovery QC run type (v5.9) with baseline and recovery %.* `Tooling ready`
- [ ] **108** (P0) Replace simulated data with >= 40 real samples / 15 sources / 2 districts. *Data/field/README.md + paired_template.csv; /api/scans; bridge --file; GET /api/data/export/paired. Needs the field programme.* `Tooling ready`
- [ ] **109** (P0) Pre-register the analysis. *The analysis is fixed in code: paired_validation.py (end points, cutoffs, statistics). Write the pre-registration in the logbook citing the script version (git commit).* `Partial`
- [ ] **110** (P0) Confusion matrix at 10 and 50 µg/L with Wilson CIs; missed unsafe count. *Software ready, not yet run on real samples or hardware. paired_validation.py cutoffs 10 / 20 / 50 (v5.9) with Wilson intervals and missed-unsafe counts; /api/validation endpoint (v5.6).* `Tooling ready`
- [ ] **111** (P0) Proper sample collection; split; chain of custody. *Software ready, not yet run on real samples or hardware. SampleMeta (purge, bottle, preservation, custody note, split_for_lab, collected_at) stored with readings/scans and exported (v5.9). Procedure in Data/field/README.md.* `Tooling ready`
- [ ] **112** (P0) Record GPS / source type / depth / date-time per sample. *Software ready, not yet run on real samples or hardware. Device site (lat/long) + SampleMeta source_kind, depth_m, collected_at (v5.9).* `Tooling ready`
- [ ] **130** (P0) Scatter with 1:1 line and Bland-Altman. *Software ready, not yet run on real samples or hardware. paired_validation.py (v5.8).* `Tooling ready`
- [ ] **131** (P0) Regression slope/intercept with CIs (Deming). *Software ready, not yet run on real samples or hardware. paired_validation.py Deming with bootstrap CIs (v5.8).* `Tooling ready`
- [ ] **132** (P0) Justify the sample size (CI width). *Software ready, not yet run on real samples or hardware. paired_validation.py sample-size table (v5.9): Wilson CI width vs n unsafe.* `Tooling ready`
- [ ] **148** (P0) Be honest that V3 was trained on simulated readings; evaluate on real data. *Software ready, not yet run on real samples or hardware. Docs/CLAIMS_REGISTER.md N1; Analysis/aquanet_v3_field_eval.py (v5.9) evaluates the deployed network on paired rows.* `Tooling ready`
- [ ] **149** (P0) Baseline: threshold rule and logistic regression. *Software ready, not yet run on real samples or hardware. aquanet_v3_field_eval.py reports both baselines on the same rows.* `Tooling ready`
- [ ] **150** (P0) Confusion matrix on held-out real data. *aquanet_v3_field_eval.py; needs the paired dataset.* `Tooling ready`
- [ ] **164** (P0) Working robust prototype with a dummy cell at the fair. *Not software.* `Team`
- [ ] **165** (P0) Power consumption per mode; battery life. *Not software; firmware has the low-power build and deep-sleep strategy to measure.* `Lab`
- [ ] **210** (P0) Cost per test and per device from receipts. *Analysis/project_figures.py cost from bom_template.csv.* `Tooling ready`
- [ ] **220** (P0) Hazardous chemical list with SDS; SRC review. *Not software.* `Team`
- [ ] **221** (P0) All ISEF forms prepared. *Not software.* `Team`
- [ ] **222** (P0) Arsenic work in a proper lab; waste plan. *Not software.* `Team`
- [ ] **226** (P0) Dated logbook. *Not software (git history is the software logbook).* `Team`
- [ ] **227** (P0) 250-word abstract in your own words. *Not software.* `Team`
- [ ] **231** (P0) One clear story; title states the result. *Not software.* `Team`
- [ ] **232** (P0) Results panel largest: scatter / confusion / LOD. *make_poster_figures.py produces them from the paired CSV.* `Tooling ready`
- [ ] **241** (P0) 60-second and 3-minute pitch. *Not software.* `Team`
- [ ] **242** (P0) Every member explains chemistry / statistics / code. *Not software (Docs/CODE_GUIDE.md for the code).* `Team`
- [ ] **243** (P0) Top 40 hard questions rehearsed. *Not software; Docs/CLAIMS_REGISTER.md gives the honest answers to the first ten.* `Team`

## In the lab (chemistry and bench) (13)

Needs chemicals, a supervisor and the instrument. Do these under the approved research plan.


**D Design**

- [ ] **56** (P1) Design rationale for sample well and pump volumes. *Not software.*
- [ ] **57** (P1) Justify electrode choice with own measurements. *Not software.*

**E Sensor**

- [ ] **79** (P1) Dissolved oxygen effect. *Not software (the reading schema has dissolved_oxygen_mg_l).*
- [ ] **80** (P2) Cheaper electrode comparison. *Not software; electrode_lot distinguishes them in the data.*
- [ ] **81** (P2) Electrode surface characterisation. *Not software.*
- [ ] **85** (P2) Speciation as an extension. *Not software.*

**J Hardware**

- [ ] **166** (P1) Characterise the potentiostat. *Not software; noise_sigma_ua per scan is logged for the comparison.*
- [ ] **167** (P1) Pump and fluidics tests; carry-over. *Not software; field_blank QC runs record carry-over.*
- [ ] **168** (P1) Enclosure IP / UV / heat tests. *Not software.*
- [ ] **169** (P1) Drop / vibration test. *Not software.*

**K Firmware**

- [ ] **182** (P1) 14-day soak test. *Not software; /api/metrics and the firmware's reset counter record it.*
- [ ] **187** (P2) Flash and test on two boards. *Not software; CI compiles for ESP32 / S3 / C3.*
- [ ] **190** (P2) Deep-sleep strategy with numbers. *Strategy documented in Firmware/README.md; the numbers need a power meter.*

## In the field (4)

Needs real sources, sample bottles and a laboratory partner.


**G Field**

- [ ] **113** (P1) Sample set covers the range. *Not software; paired_validation reports the distribution so gaps are visible.*
- [ ] **116** (P1) Multiple conditions (hot/cold, turbidity, iron, operators, rain). *Not software; SampleMeta.collector and the sensors record the conditions.*
- [ ] **117** (P1) Compare with the government field test kit. *Not software; add a kit_result column to the paired CSV for the comparison.*
- [ ] **118** (P1) Repeat sources in a second season. *Not software; readings are timestamped and the trend endpoint shows change.*

## Run the ready-made tools on real data (31)

The software for these exists and is tested, but nothing real has gone through it yet. Each closes when the measurements are made and the script or endpoint named in the row is run on them.


**C Prior art**

- [ ] **47** (P2) Landscape figure: cost vs LOD. *Software ready, not yet run on real samples or hardware. Analysis/project_figures.py landscape from Data/field/landscape_template.csv (numbers to fill).*

**D Design**

- [ ] **58** (P2) Bill of materials with prices; cost per test. *Data/field/bom_template.csv + Analysis/project_figures.py cost -> cost.md; prices from receipts.*

**E Sensor**

- [ ] **68** (P1) Other interferents (Fe, Mn, phosphate, silicate, humics, chloride, hardness). *Analysis/interference.py takes any interferent.*
- [ ] **69** (P1) pH and temperature effects and corrections. *interference.py accepts pH / temperature as the x variable; the node logs both; a correction would go into app/signal_processing.py after measurement.*
- [ ] **70** (P1) Electrode lifetime (scans until slope drops 10 %). *Calibration records per device + electrode_lot on readings; Analysis/control_chart.py shows the fade. Measurement is lab work.*
- [ ] **71** (P1) Electrode-to-electrode variability (>= 5 electrodes; 2 lots). *paired_validation.py 'By electrode lot' table (v5.9). Measurement is lab work.*
- [ ] **72** (P1) Repeatability and intermediate precision. *paired_validation.py replicate CV % by band (v5.9) from repeated sample codes.*
- [ ] **75** (P1) Raw voltammograms for blank / 10 / 50 / 100 on one plot. *Every scan is stored (v5.8) and GET /api/scans/{id} returns raw, smoothed and baseline arrays; the dashboard shows the trace. Real scans needed.*
- [ ] **76** (P1) Validate peak finding against >= 50 hand-measured scans. *Analysis/peak_check.py (v5.9): bias, limits of agreement, Deming slope, worst disagreements.*
- [ ] **77** (P1) Matrix effects: real water vs DI slopes. *Standard-addition endpoint per device; spike_recovery QC; paired_validation 'By site'.*
- [ ] **78** (P1) External calibration vs standard addition against ICP-MS. *Both calibration types are stored with IDs; reprocess any stored scan with either (v5.8) and compare in paired_validation.*

**F Metrology**

- [ ] **95** (P1) Blind samples. *Software ready, not yet run on real samples or hardware. Analysis/run_order.py: coded run sheet for the operator, sealed key for the supervisor (v5.9).*
- [ ] **96** (P1) Randomise run order. *Software ready, not yet run on real samples or hardware. run_order.py (seeded shuffle; opening and closing checks fixed).*
- [ ] **98** (P1) Calibrate pH / EC / temperature / turbidity sensors or drop them from claims. *Software ready, not yet run on real samples or hardware. QC run types ph_buffer, conductivity_standard, turbidity_standard, temperature_reference (v5.9); /api/qc/status reports sensor_checks.verified per sensor.*
- [ ] **99** (P2) Shewhart control charts for the check standard. *Software ready, not yet run on real samples or hardware. Analysis/control_chart.py (v5.9) with Western Electric rules.*
- [ ] **100** (P2) Inter-device comparison. *Same sample_code on readings from 2-3 devices; paired_validation groups by device via the site table.*

**G Field**

- [ ] **114** (P1) 30-day continuous deployment with weekly lab samples. *Firmware offline buffer, OTA, QC gates, trend detection; GET /api/metrics for uptime. Needs the deployment.*
- [ ] **129** (P2) Map the field results and screenshot for the poster. *Software ready, not yet run on real samples or hardware. Dashboard map (v5.6); demo data has no coordinates so only real sites appear (v5.7).*

**H Statistics**

- [ ] **133** (P1) ROC curve and threshold choice. *Software ready, not yet run on real samples or hardware. paired_validation.py ROC/AUC at 10 / 20 / 50; aquanet_v2_pipeline referral curve.*
- [ ] **134** (P1) Precision as CV % at low / medium / high. *Software ready, not yet run on real samples or hardware. paired_validation.py replicate CV by band (v5.9).*
- [ ] **136** (P1) Uncertainty for every number on the poster. *Software ready, not yet run on real samples or hardware. Every metric in the analysis reports carries an interval and n.*
- [ ] **139** (P1) Interference by regression with CI. *Software ready, not yet run on real samples or hardware. Analysis/interference.py (v5.9).*
- [ ] **143** (P2) Trend detection on the 30-day deployment. *Mann-Kendall + Sen slope endpoint (v5.4) needs the real deployment.*

**I AquaNet**

- [ ] **152** (P1) Feature importance / ablation. *Software ready, not yet run on real samples or hardware. aquanet_v3_field_eval.py ablation table.*
- [ ] **153** (P1) Calibration / reliability diagram. *Software ready, not yet run on real samples or hardware. aquanet_v3_field_eval.py reliability.svg + ECE; aquanet_v2_pipeline reliability.*
- [ ] **160** (P2) Describe the failure cases. *Software ready, not yet run on real samples or hardware. aquanet_v3_field_eval.py lists the rows the network gets wrong.*

**K Firmware**

- [ ] **183** (P1) Offline buffering demo (3 days off, all readings arrive once). *Software ready, not yet run on real samples or hardware. Firmware ring buffer + idempotency keys (v5.3-v5.5); bridge outbox tests (v5.8). Run it on the real board and log it.*
- [ ] **184** (P1) Safe OTA with rollback. *Software ready, not yet run on real samples or hardware. OTA with rollback and signed manifests (v5.5-v5.6); demonstrate on a board.*

**L Software**

- [ ] **194** (P1) Lab-confirmation panel with real paired results. *Panel exists (v5.6); needs real pairs.*

**Q Poster**

- [ ] **233** (P1) Every graph: units; n; error bars; source. *Software ready, not yet run on real samples or hardware. svg_plots subtitles carry n and the fit; axes carry units.*
- [ ] **236** (P1) Printed QR code to the repository / DOI. *Software ready, not yet run on real samples or hardware. Analysis/project_figures.py qr -> qr.svg / qr.pdf.*

## Finish what the software started (31)

The software did its share; the rest is writing, drawing, measuring or choosing.


**A Pathway**

- [ ] **16** (P1) Work backwards from the fair date. *Milestones (field data -8 weeks, poster -6 weeks, 3 mocks) are rows in Docs/planning/timeline.csv.*
- [ ] **17** (P1) Scope freeze date (15 March 2027). *Row in timeline.csv. In software: tag the frozen version (git tag isef-2027, item 265).*

**B Need**

- [ ] **32** (P2) Map of affected habitations next to test sites. *Dashboard map shows tested sites; the affected-habitation layer needs the government source (item 49).*

**C Prior art**

- [ ] **38** (P1) Compare with open-source and commercial potentiostats. *Rows for Bullen et al. and commercial instruments in landscape_template.csv; fill the numbers.*
- [ ] **41** (P1) Cite the Indian field-testing ecosystem (JJM kits; WQMIS; NABL). *JJM/WQMIS export exists (GET /api/data/export/jjm); cite the documents yourself.*
- [ ] **44** (P2) Cite WHO and BIS documents directly. *Docs/IMPROVEMENT_LOG.md and app/standards.py cite the documents used by the code; cite them in your paper.*

**D Design**

- [ ] **51** (P1) Separate chemistry / instrument / system. *Docs/REQUIREMENTS_TRACEABILITY.md and ROADMAP_COVERAGE.md are organised by those three layers; use the same split on the poster.*
- [ ] **52** (P1) Block diagram of the instrument with part numbers. *Firmware/PINOUT.md gives every pin and part; draw the block diagram from it.*

**E Sensor**

- [ ] **73** (P1) Linearity with >= 6 standards and residual plot. *External calibration endpoint accepts any number of standards and returns residuals; add the residual plot once real standards exist.*
- [ ] **82** (P2) Sample stability / hold time. *SampleMeta.collection_to_analysis_min and preservation are stored (v5.9) so the effect can be analysed.*
- [ ] **83** (P2) Reagent consumption and waste per test. *bom_template.csv has per-test reagent rows.*
- [ ] **84** (P2) Potentiostat noise floor with a dummy cell. *The pipeline reports noise_sigma_ua per scan; run a dummy-cell scan through /api/scans to record it.*
- [ ] **86** (P2) SWASV parameter DoE (2^3 factorial). *Scan settings are stored with every scan (scan_settings_json), so a factorial run is analysable; run_order.py randomises it.*
- [ ] **87** (P2) Peak current vs deposition time plot. *Deposition time is stored per scan; plot from the paired/scan export.*

**F Metrology**

- [ ] **102** (P2) SOP for a measurement. *Docs/SOP_MEASUREMENT.md: instrument and software steps written; chemistry steps are placeholders for the supervisor.*
- [ ] **106** (P2) Show what happens without the controls. *Reprocess stored scans with another calibration (v5.8) shows the calibration control; temperature correction needs item 69 first.*

**G Field**

- [ ] **115** (P1) Report uptime / missed readings / battery / false alarms. */api/metrics and /api/devices give uptime, battery and alert counts; a 30-day summary script is a small addition once data exist.*
- [ ] **125** (P2) Time per test measured with a stopwatch. *Firmware prints time to first result (v5.9) and the scan duration is in scan settings; the hands-on part is a stopwatch.*
- [ ] **127** (P2) Keep odd samples for retest. *The retest outcome flags them; sample_code links the retest to the original.*

**H Statistics**

- [ ] **140** (P1) Explain outliers individually. *paired_validation and peak_check list the largest disagreements; the explanation goes in the logbook.*
- [ ] **142** (P2) Mixed model for repeated readings per source. *Grouped-by-site evaluation in aquanet_v2_pipeline avoids the independence error; a mixed model is future work once there are repeated visits.*

**I AquaNet**

- [ ] **151** (P1) Why a network at all. *The ablation in aquanet_v3_field_eval.py answers it with data; the argument is yours to write.*
- [ ] **156** (P1) Document the training-data generation. *Docs/neural/AQUANET_V3_REPORT.md and scripts/train_aquanet_v2.py describe the distributions and noise; the 'why realistic' citation is yours.*

**J Hardware**

- [ ] **170** (P1) PCB or neat perfboard; wiring diagram; labelled photo. *Firmware/PINOUT.md gives the wiring table to draw from.*
- [ ] **175** (P2) Device UI usable without a phone (LED/buzzer legend). *Firmware drives status LED patterns; print the legend on the lid.*

**K Firmware**

- [ ] **185** (P1) Watchdog and brown-out tested. *Watchdog in firmware (v5.3); brown-out behaviour must be provoked on a real board.*

**L Software**

- [ ] **197** (P2) Page load on a cheap Android phone on 3G. *Docs/PRIVACY_AND_PERFORMANCE.md records a throttled headless measurement; measure on a real phone too.*

**N Impact**

- [ ] **214** (P1) Maintenance needs per month. *Calibration age (90 d) and check-standard (7 d) rules define the minimum schedule; electrode life needs item 70.*

**P Logbook**

- [ ] **229** (P1) Limitations section. *Docs/CLAIMS_REGISTER.md lists every limit (LOD, species, Cu, sample size, simulated training) as targets; write the prose yourself.*

**S Credibility**

- [ ] **255** (P2) Open-source the hardware with a licence. *Docs/CREDITS.md lists the licence slot; choose CERN-OHL or similar.*

**U Repository**

- [ ] **267** (P2) Names and roles in the README. *README 'Team' section added with the contributors visible in git history; complete it when the team is final.*

## Team work: rules, writing, people, poster and interview (79)

No software share. These are logbook, forms, writing and practice.


**A Pathway**

- [ ] **14** (P1) Enter Stockholm Junior Water Prize India. *Not software.*
- [ ] **15** (P1) Pick the ISEF category on purpose. *Not software (ENEV recommended by the roadmap).*
- [ ] **18** (P2) Travel documents early. *Row in timeline.csv.*
- [ ] **19** (P2) Two reviews with a statistics mentor. *Row in timeline.csv; Analysis/*/report.md are what to review.*

**B Need**

- [ ] **27** (P1) Quantify the gap (time to lab result; retest frequency). *Not software. The paired export's pair_gap_hours measures it for your own samples.*
- [ ] **28** (P1) Why continuous monitoring matters (seasonal change). *Not software; the trend endpoint (Mann-Kendall) shows it on real data later.*
- [ ] **29** (P1) Health end point in plain words. *Not software.*
- [ ] **31** (P1) One testable research question. *Not software. Analysis/paired_validation.py computes the sensitivity it asks about.*
- [ ] **33** (P2) One stakeholder quote. *Not software.*
- [ ] **35** (P2) Why arsenic first and where the design extends. *Not software.*

**C Prior art**

- [ ] **39** (P1) Past ISEF projects on arsenic / water sensing. *Not software.*
- [ ] **40** (P1) Patent search. *Not software.*
- [ ] **42** (P2) Earlier Indian student / startup efforts. *Not software.*
- [ ] **43** (P2) BibTeX/Zotero library; one citation style. *Not software.*
- [ ] **46** (P2) List what you deliberately did not do. *Not software (Docs/DECISION_LOG.md has a place for it).*

**D Design**

- [ ] **55** (P1) Choose one competition prototype. *Not software (recommendation recorded in CLAIMS_REGISTER S6).*
- [ ] **59** (P2) Design for manufacture; assembly time. *Not software.*
- [ ] **60** (P2) What you'd change for a production unit. *Not software.*
- [ ] **62** (P2) Exploded view of the enclosure. *Not software (STL files in models_3d/).*
- [ ] **63** (P2) Keep the old prototypes. *Not software.*

**E Sensor**

- [ ] **74** (P1) Explain the electrochemistry on a poster panel. *Not software (Docs/IMPROVEMENT_LOG.md §4 has the method text to start from).*

**F Metrology**

- [ ] **97** (P1) Written cleaning protocol. *Not software; Docs/SOP_MEASUREMENT.md has the slot.*
- [ ] **103** (P2) Independent person repeats the SOP. *Not software.*
- [ ] **105** (P2) Balance and pipette calibration checks. *Not software (logbook).*

**G Field**

- [ ] **119** (P1) Photograph every site. *Not software.*
- [ ] **120** (P1) Letter from the lab. *Not software.*
- [ ] **121** (P1) Budget the lab costs. *Not software.*
- [ ] **122** (P2) Share results back with owners and the district lab. *Needs real results first. QR public page per source (v5.6), PDF certificate, JJM export.*
- [ ] **123** (P2) Responsible communication plan for a high result. *Not software; alert channels exist and are off by default for practice data.*
- [ ] **126** (P2) Cost actually spent per sample. *Not software (cost model takes receipts).*
- [ ] **128** (P2) Usability trial with a non-expert. *Not software (IRB).*

**H Statistics**

- [ ] **144** (P2) Check the analysis with a statistics teacher. *Not software.*
- [ ] **147** (P2) Raw data in a public repository with a DOI. *Not software; Data/field/README.md says what to deposit.*

**J Hardware**

- [ ] **171** (P1) Solar sizing with real insolation data. *Not software.*
- [ ] **172** (P1) Tool-free electrode replacement. *Not software.*
- [ ] **173** (P2) Custom PCB (KiCad). *Not software.*
- [ ] **177** (P2) Reduce the cost; cost curve across versions. *Not software (cost model per BOM version).*
- [ ] **178** (P2) Spares at the fair. *Not software.*
- [ ] **179** (P2) Label 3D-printed parts with versions. *Not software.*
- [ ] **180** (P2) Tolerance / fit tests for printed parts. *Not software.*

**L Software**

- [ ] **193** (P1) One alert reaching a real phone (video). *Alert channels exist (v5.6); record the video yourself.*
- [ ] **196** (P2) Translate alert text with a native speaker. *Not software; the HI/BN/AS/PA strings are machine-assisted and must be checked (i18n-*.js).*

**M Users**

- [ ] **202** (P1) Interview >= 5 stakeholders (IRB). *Not software.*
- [ ] **203** (P1) Comprehension test of the result screen. *Not software (the public QR page is the screen to test).*
- [ ] **204** (P1) Communication protocol for an unsafe reading. *Not software; alert routing is configurable.*
- [ ] **206** (P2) Equity: who pays / maintains / owns the data. *Not software.*
- [ ] **207** (P2) Letter of support. *Not software.*
- [ ] **208** (P2) Consent for photos and names. *Not software; SampleMeta.collector takes initials only.*
- [ ] **209** (P2) What happens to devices after the project. *Not software.*

**N Impact**

- [ ] **211** (P1) Scale estimate with assumptions. *Not software.*
- [ ] **212** (P1) Health impact plainly. *Not software.*
- [ ] **213** (P1) Deployment model chosen. *Not software.*
- [ ] **215** (P2) Talk to a partner. *Not software.*
- [ ] **216** (P2) Provisional patent only if warranted. *Not software.*
- [ ] **217** (P2) Environmental impact of the device. *Not software.*
- [ ] **218** (P2) Extension to fluoride / nitrate / uranium / lead. *Not software.*

**O Safety**

- [ ] **223** (P1) Lab safety log per session. *Not software.*
- [ ] **224** (P1) Most dilute stock that works. *Not software.*
- [ ] **225** (P2) Safety on the poster. *Not software.*

**P Logbook**

- [ ] **228** (P1) Full IMRaD paper. *Not software.*
- [ ] **230** (P1) Future work: 3 concrete experiments. *Not software.*

**Q Poster**

- [ ] **234** (P1) Supporting documents on the table. *Not software.*
- [ ] **235** (P1) Prototype opened on the table + used electrode. *Not software.*
- [ ] **237** (P2) Check display and safety rules. *Not software.*
- [ ] **240** (P2) Three strangers read the poster. *Not software.*

**R Interview**

- [ ] **244** (P1) 3 mock judging sessions. *Row in timeline.csv.*
- [ ] **245** (P1) Know the numbers by heart. *Numbers come from the analysis reports once real data exist.*
- [ ] **246** (P1) Practise 'I don't know but here is how I'd find out'. *Not software.*
- [ ] **247** (P1) Prepare for special-award judges. *Not software.*
- [ ] **248** (P2) Practise with interruptions. *Not software.*
- [ ] **249** (P2) One true field story. *Not software.*
- [ ] **250** (P2) Record a practice interview. *Not software.*

**S Credibility**

- [ ] **251** (P1) Find a mentor; log meetings. *Not software.*
- [ ] **252** (P1) Present at a school fair first. *Not software.*
- [ ] **253** (P2) Submit the paper to a student journal. *Not software.*
- [ ] **254** (P2) Publish the dataset with a DOI. *Not software.*
- [ ] **256** (P2) Youth innovation programmes only with real data. *Not software.*

**T Cut**

- [ ] **260** (P2) Catamaran and tank prototypes as future work. *Not software (docs in Docs/hardware/ are labelled as concepts).*

**U Repository**

- [ ] **265** (P2) Tag the fair version (git tag isef-2027). *Run at the scope freeze: git tag -a isef-2027 -m 'version shown at ISEF 2027' && git push origin isef-2027.*

## Software work that should wait for data (2)

Deliberately not done yet.


**I AquaNet**

- [ ] **157** (P2) Tiny CNN on raw voltammograms. *Only after enough real scans exist; aquanet_v2_pipeline.py is the harness to add it to.*

**J Hardware**

- [ ] **174** (P2) Reference-electrode open-circuit self-test. *Boot self-test (v5.8) covers ADC/DAC/storage/calibration; an OCP check needs the analog path to be measured first - add after item 166.*

## Outside the roadmap

- [ ] Write sections 2-4 of `Docs/AI_USE_STATEMENT_TEMPLATE.md` (what you checked, what you designed, what the AI did not do) in your own words, and print it for the booth.
- [ ] Have native speakers check the Hindi, Bengali, Assamese and Punjabi screens (`AquaSentry_Platform/frontend/i18n-*.js`); they were machine-assisted.
- [ ] Complete the Team section of `README.md` with every member's name and role once the team is final (ISEF allows at most three).
- [ ] Confirm in writing whether the team entered IRIS 2026-27 (submissions closed 13 October 2026) and record the answer and the next fair in `Docs/planning/timeline.csv`.
- [ ] Review GitHub's automatic dependency pull requests (Dependabot) as they arrive; CI must pass before merging.

## Already done in software

54 items need nothing more from the code; they are listed with their file and test in `Docs/ISEF_ROADMAP_STATUS.md`. *Done* there never means the sensor works: every accuracy claim still waits for real paired samples in `Data/field/`.
