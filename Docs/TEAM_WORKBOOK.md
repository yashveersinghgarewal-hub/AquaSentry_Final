# Team workbook — every roadmap item that is not pure software, with its worksheet

For each item of `Docs/ISEF_ROADMAP.md` that code alone cannot close, this page gives: **Do** (the concrete steps),
**Use** (the template, script or endpoint in this repository), **Record** (where the evidence goes). Items the software
has fully closed are not repeated here; they are in `Docs/ISEF_ROADMAP_STATUS.md` with their tests. Templates live in
`Docs/templates/`; scripts in `Analysis/`; every script has `--demo` so you can see its output before you have data.

Nothing here is written for you to submit: the research plan, abstract, poster text and paper must be your own words
(items 1–2). The templates are structures and checklists; the scripts are calculators.

---

## 0 Rules

**1 — No generative AI for the research plan, abstract, poster or citations.**
Do: write those four documents from your logbook; use this repository as notes only. Use: `Docs/templates/abstract_structure.md`, `paper_outline.md` (structures, no text). Record: a line in the AI-use statement saying which documents were written without AI.

**2 — Disclose AI use.** Do: fill sections 2–4 of the statement in your words. Use: `Docs/AI_USE_STATEMENT_TEMPLATE.md` (section 1 is a factual inventory). Record: one printed page at the booth; copy in the logbook.

**3 — Explain every file you show.** Do: pick the files you will show (`Docs/DEMO_SCRIPT.md`), read `Docs/CODE_GUIDE.md`, and practise explaining `app/signal_processing.py`, `app/classification.py`, `frontend/asv.js` and one analysis script. Remove from the demo anything you cannot explain. Record: list of shown files in the logbook.

**4 — 12-month rule.** Do: write the date of your first data collection on the first logbook page; keep everything before it labelled "preparatory". Use: `Docs/planning/timeline.csv` row "Forms…". Record: logbook page 1.

**5 — Continuation rules.** Do: if any part was done before the research window, fill Form 7 and label earlier work "previous work" on the poster. Use: `CHANGELOG.md` dates. Record: Form 7.

**6 — Research plan before experimenting.** Do: write hypothesis, procedures (cite `Docs/SOP_MEASUREMENT.md`, `Data/field/README.md`), risk assessment, data analysis (cite `Analysis/paired_validation.py` by commit), bibliography; get signatures before the first arsenic standard is opened. Use: `Docs/templates/isef_forms_checklist.csv`. Record: signed plan + dated addenda.

**7 — SRC review, Form 3, SDS.** Do: list every chemical, attach its SDS, have the Qualified Scientist sign. Use: `Docs/templates/chemical_inventory.csv`. Record: Form 3 with the inventory attached.

**8 — IRB before surveys/interviews.** Do: submit the interview guide and consent form to the IRB before any interview or usability trial. Use: `Docs/templates/stakeholder_interview_guide.md`, `usability_trial_sheet.md`. Record: Form 4 + approval date.

**9 — Team rules.** Do: fix the team (≤ 3) and roles for the year. Use: README "Team" table. Record: README + Form 1A.

**10 — Booth without power or internet.** Do: print every figure (`Analysis/make_poster_figures.py`), the QR, the SOP and the claims register; bring the device with a dummy cell and a charged power bank; the dashboard is a bonus. Record: packing list in the logbook.

**12 — IRIS status.** Do: check the IRIS site and your submission account; note the date. Record: logbook + `Docs/planning/timeline.csv`.

**13 — One calendar.** Do: confirm the IRIS and ISEF dates and edit `Docs/planning/timeline.csv`; run `python Analysis/project_figures.py gantt`. Record: the Gantt on the wall.

**14 — Stockholm Junior Water Prize India.** Do: check eligibility and date; add a row to the timeline. Record: timeline.

**15 — Category.** Do: choose (ENEV recommended) and write one sentence why. Record: `Docs/DECISION_LOG.md`.

**16 — Work backwards from the fair.** Use: the milestone rows already in `timeline.csv` (field data −8 weeks, poster −6 weeks, three mocks). Record: Gantt.

**17 — Scope freeze.** Do: on 15 March 2027 stop changing method, settings and analysis; tag the code (`git tag -a isef-2027`). Record: `Docs/DECISION_LOG.md` entry "frozen".

**18 — Travel documents.** Do: passport validity ≥ 6 months after May 2027; US visa appointment early. Record: timeline row.

**19 — Statistics mentor.** Do: two meetings; bring `Analysis/out/*/report.md`. Record: meeting notes in the logbook.

**22 — The need in one sentence with a number.** Do: take the figure from the JJM/IMIS dashboard or a CGWB report with its date. Use: `Docs/templates/literature_table.csv` row for the source. Record: poster panel 1.

**23 — Primary user.** Do: decide (district lab chemist / panchayat / household) from the interviews. Record: `DECISION_LOG.md`.

**24 — Measurable design criteria.** Do: set your own numbers in the "target" column. Use: `Docs/REQUIREMENTS_TRACEABILITY.md`. Record: that file + poster criteria panel.

**25 — Constraints.** Do: confirm or edit the constraints table. Use: `REQUIREMENTS_TRACEABILITY.md` §Constraints. Record: same.

**26 — Why current options fail.** Do: fill `Data/field/landscape_template.csv` from datasheets/quotes; run `project_figures.py landscape`. Record: figure + the literature table rows it came from.

**27 — Quantify the gap.** Do: ask the laboratory how long a result takes (days) and how often sources are retested; add to the need panel. Record: interview notes.

**28 — Why continuous monitoring.** Do: cite one study of seasonal arsenic change in your state; later show your own trend (`/api/devices/{code}/trend`). Record: literature table.

**29 — Health end point.** Do: one plain sentence (chronic exposure → skin lesions, cancers) with a WHO citation. Record: poster.

**31 — One testable question.** Do: "Can the node detect arsenic above 10 µg/L with sensitivity ≥ 90 % (lower CI ≥ 80 %) against ICP-MS across ≥ 15 sources?" — or your own. Record: research plan.

**32 — Map of affected habitations.** Do: obtain the habitation list from JJM/IMIS; plot with your sites (dashboard map or a GIS tool). Record: poster.

**33 — Stakeholder quote.** Use: interview guide question 7; permission to quote. Record: interview notes.

**35 — Why arsenic first.** Do: one paragraph: burden, existing kit limits, extension to fluoride/uranium (item 218). Record: paper introduction.

## C Prior art

**36 — Literature table.** Do: ≥ 20 papers; read the full text; fill every column. Use: `Docs/templates/literature_table.csv` (three documents pre-listed — verify them). Record: the CSV + Zotero library (item 43).

**37 — What is new.** Do: one sentence that follows from the table. Record: poster + abstract.

**38 — Compare with open-source and commercial potentiostats.** Use: `landscape_template.csv` rows (Bullen 2022, commercial instrument). Record: landscape figure.

**39 — Past ISEF arsenic/water projects.** Do: search the ISEF abstracts database; add rows to the literature table with "what we do differently". Record: literature table.

**40 — Patent search.** Do: Google Patents / Espacenet: "arsenic anodic stripping voltammetry portable"; list 5 with one line each. Record: `Docs/DECISION_LOG.md` "things not done" if a patent changed your design.

**41 — Indian field-testing ecosystem.** Do: cite the JJM FTK guidelines, WQMIS and NABL; the JJM export (`GET /api/data/export/jjm`) shows you understand the format. Record: literature table.

**42 — Earlier Indian efforts.** Do: two or three examples with what happened to them. Record: literature table.

**43 — Reference manager.** Do: Zotero library; one style; export BibTeX into the paper. Record: `Docs/references.bib` (yours).

**44 — Cite WHO and BIS directly.** Use: rows already in the literature table. Record: paper.

**46 — What you deliberately did not do.** Do: extend the list in `Docs/DECISION_LOG.md` §"Things deliberately not done". Record: same.

## D Design

**48 — Alternatives and decision matrices.** Do: one matrix each for electrode, potentiostat front end, pump, enclosure, deployment model. Use: `Docs/templates/decision_matrix_template.csv` → `python Analysis/decision_matrix.py <csv>`. Record: `Analysis/out/decisions/*/report.md` + reasons in `DECISION_LOG.md`.

**49 — Weighted criteria and scores.** Use: same script; it also reports whether the winner survives ± 30 % weight noise. Record: same.

**51 — Chemistry / instrument / system separated.** Use: `REQUIREMENTS_TRACEABILITY.md` and `ROADMAP_COVERAGE.md` already use the three layers; mirror them on the poster. Record: poster layout.

**52 — Block diagram with part numbers.** Use: `Firmware/PINOUT.md` for every part and pin; draw the diagram (draw.io / Inkscape). Record: `Docs/hardware/block_diagram.svg` (yours).

**55 — One competition prototype.** Do: decide (handpump screening unit recommended, `CLAIMS_REGISTER` S6). Record: `DECISION_LOG.md`.

**56 — Sample well and pump volumes.** Do: measure dead volume, fill time and rinse volume; state why 15 mL. Use: `Docs/templates/carryover_holdtime_sheet.csv` (carry-over rows). Record: `HARDWARE_CHANGELOG.md`.

**57 — Electrode choice from own measurements.** Use: `Analysis/electrode_study.py` and the decision matrix. Record: `DECISION_LOG.md`.

**58 — BOM with prices.** Do: fill `Data/field/bom_template.csv` from receipts; run `project_figures.py cost`. Record: `Analysis/out/project/cost.md`.

**59 — Design for manufacture.** Do: time one full assembly with a stopwatch; list the steps that took longest. Record: `HARDWARE_CHANGELOG.md`.

**60 — Production changes.** Do: one list (PCB, injection-moulded well, sealed connectors). Record: paper discussion.

**61 — Safety by design.** Use: `Docs/FMEA.md` §Safety by design; add the chemistry lines with your supervisor. Record: `FMEA.md` + `Docs/templates/safety_poster_panel.md`.

**62 — Exploded view.** Do: export from your CAD (STL files in `models_3d/`). Record: `Docs/hardware/`.

**63 — Keep old prototypes.** Do: label each with version and date (item 179) and bring them. Record: `HARDWARE_CHANGELOG.md`.

## E Sensor

**64 — LOD below 10 µg/L.** Do: try longer deposition (DoE, item 86), electrode choice (item 57), cleaner blanks; measure after each change. Use: `Analysis/linearity.py`. Record: `CLAIMS_REGISTER` M1 with date.

**65 — LOD/LOQ properly.** Do: ≥ 10 blanks + 6 standards with replicates. Use: `Docs/templates/standards_template.csv` → `Analysis/linearity.py`. Record: report + `CLAIMS_REGISTER` M1/M2.

**66 — As(III) vs As(V).** Do: with the supervisor, choose a pre-reduction (e.g. thiosulfate or L-cysteine), measure recovery of As(V) spikes with and without it. Use: `POST /api/qc/runs run_type=spike_recovery`; `arsenic_species` on readings. Record: QC runs + `CLAIMS_REGISTER` M3.

**67 — Copper interference.** Do: Cu 0–500 µg/L at fixed As. Use: `Docs/templates/interference_template.csv` → `Analysis/interference.py`. Record: report; mitigation decision in `DECISION_LOG.md`.

**68 — Other interferents.** Do: Fe, Mn, phosphate, silicate, humics, chloride, hardness — one at a time, then a realistic mixture. Use: same template/script. Record: same.

**69 — pH and temperature.** Do: pH 5–9 and 15–40 °C at fixed As. Use: `interference.py` with pH / temperature as the interferent. Record: report; a correction, if any, goes into `app/signal_processing.py` as a documented function with its data.

**70 — Electrode lifetime.** Do: run a check standard every N scans per electrode until the response drops 10 %. Use: `Docs/templates/electrode_log_template.csv` → `Analysis/electrode_study.py`. Record: report + `tests_per_electrode` in the cost model.

**71 — Electrode-to-electrode variability.** Do: ≥ 5 electrodes from ≥ 2 lots, same standards. Use: same script (CV across electrodes, lot comparison). Record: report + `CLAIMS_REGISTER` M9.

**72 — Repeatability / intermediate precision.** Do: 10 repeats within a session; repeats across days and operators. Use: same script; `paired_validation.py` replicate CV for field samples. Record: report.

**73 — Linearity with ≥ 6 standards + residual plot.** Use: `linearity.py` (lack-of-fit test). Record: report.

**74 — Electrochemistry panel.** Do: one figure (deposition → stripping) in your own drawing + one paragraph. Record: poster.

**75 — Raw voltammograms on one plot.** Do: run blank, 10, 50, 100 µg/L; the scans are stored; plot via `GET /api/scans/{id}` arrays (or screenshot the trace viewer). Record: poster figure.

**76 — Peak finding vs hand measurement.** Do: ≥ 50 printed scans measured by hand. Use: `Docs/templates/hand_peaks_template.csv` → `Analysis/peak_check.py`. Record: report.

**77 — Matrix effects.** Do: real water vs DI slopes by standard addition. Use: `/api/admin/calibrations/standard-addition`; spike-recovery QC runs. Record: `paired_validation.py` by-site table.

**78 — External calibration vs standard addition vs ICP-MS.** Use: reprocess stored scans with each calibration (`POST /api/scans/{id}/reprocess`) and compare in `paired_validation.py`. Record: report.

**79 — Dissolved oxygen.** Do: purge with N₂ vs not, same standard. Use: `dissolved_oxygen_mg_l` field; interference template with DO as x. Record: report.

**80 — Cheaper electrode.** Use: electrode log with a different `electrode_lot`; decision matrix. Record: `DECISION_LOG.md`.

**81 — Surface characterisation.** Do: optical microscope photos before/after N scans (SEM if available). Record: `HARDWARE_CHANGELOG.md` + photo log.

**82 — Hold time.** Do: same sample at 0, 30 min, 2 h, 24 h. Use: `carryover_holdtime_sheet.csv`; `SampleMeta.collection_to_analysis_min`. Record: result; a rule in the SOP.

**83 — Reagent and waste per test.** Do: measure volumes. Use: BOM reagent rows. Record: safety panel + cost model.

**84 — Noise floor with a dummy cell.** Do: scan a resistor dummy cell; the pipeline reports `noise_sigma_ua`. Record: `CLAIMS_REGISTER` (new row S7).

**85 — Speciation extension.** Do: one paragraph of future work. Use: `Docs/templates/future_work_template.md`. Record: paper.

**86 — SWASV parameter DoE.** Use: `python Analysis/doe_factorial.py --plan …` → run in that order → `doe_factorial.py plan.csv`. Record: report; chosen settings into the firmware defines with the date.

**87 — Peak current vs deposition time.** Use: `linearity.py` with the `deposition_s` column. Record: report figure.

## F Metrology

**88 — Certified reference material.** Do: buy a CRM (e.g. NIST SRM or an ISO 17034 producer); run as a check standard. Use: QC runs `check_standard`. Record: recovery in the QC log; `CLAIMS_REGISTER`.

**97 — Cleaning protocol.** Do: write it with the supervisor (acid, rinse, dry). Record: `Docs/SOP_MEASUREMENT.md` step 5.

**100 — Inter-device comparison.** Do: same samples on 2–3 nodes with the same `sample_code`. Use: paired export; `paired_validation.py` by device. Record: report.

**102 — SOP.** Do: fill every **[supervisor]** line. Use: `Docs/SOP_MEASUREMENT.md`. Record: same.

**103 — Independent repeat of the SOP.** Do: give the SOP to someone new; time; note questions. Record: SOP §Reproducibility check.

**105 — Balance and pipette checks.** Do: weigh a check mass / pipette water onto a balance weekly. Record: logbook table.

**106 — Show what happens without the controls.** Do: reprocess a day's scans with a stale calibration (`reprocess?calibration_id=`); compare. Record: one poster sentence.

## G Field

**108 — ≥ 40 real samples / 15 sources / 2 districts.** Do: plan sites across the range; run `Data/field/README.md` workflow. Use: `Docs/templates/field_day_sheet.csv`, `run_order.py`, `/api/scans`, `/api/lab-results`, paired export. Record: `Data/field/` (deposited with a DOI later).

**109 — Pre-register the analysis.** Do: write end points, cutoffs, statistics and the script commit hash before the first field day; sign and date. Use: `paired_validation.py` docstring as the method text. Record: logbook + a dated PDF.

**113 — Range coverage.** Do: include known high and low sources; the `paired_validation` report shows the distribution. Record: report.

**114 — 30-day deployment.** Do: install one node; weekly lab split. Use: firmware, `Analysis/deployment_report.py` on the export. Record: report.

**115 — Uptime / missed / battery / false alarms.** Use: `deployment_report.py`. Record: report + poster.

**116 — Multiple conditions.** Do: hot/cold days, turbid sources, iron-rich sources, two operators, rain. Use: field-day sheet columns; `SampleMeta.collector`. Record: paired export analysed by condition.

**117 — Government field test kit comparison.** Do: run the FTK on the same bottle; write `kit_result_if_any` on the field-day sheet; add a `kit_result` column to the paired CSV. Record: paired_validation (add a kit row manually) + poster.

**118 — Second season.** Do: repeat the same sources after the monsoon. Record: trend endpoint + paired export.

**119 — Site photographs.** Use: `Docs/templates/photo_log.csv` (consent column). Record: photo log.

**120 — Letter from the lab.** Use: `Docs/templates/letter_templates.md`. Record: signed letter.

**121 — Lab budget.** Use: `Docs/templates/budget_template.csv`. Record: budget.

**123 — Communication plan for a high result.** Use: `Docs/templates/communication_protocol.md`. Record: names/phones in the logbook.

**125 — Time per test.** Do: stopwatch from bottle to outcome; the firmware prints time to first result. Record: SOP + poster.

**126 — Cost actually spent per sample.** Use: `scale_estimate.py` rows `field_samples_collected`, `field_total_spend_inr`. Record: report.

**127 — Retest odd samples.** Do: keep the bottle; repeat with the same `sample_code`. Record: paired export.

**128 — Usability trial.** Use: `Docs/templates/usability_trial_sheet.md` (IRB). Record: sheets.

## H Statistics

**140 — Explain outliers individually.** Use: "largest disagreements" tables in `paired_validation.py` and `peak_check.py`. Record: one line per outlier in the logbook.

**142 — Mixed model.** Do: after repeated visits exist, fit a random-intercept model (statsmodels) or report per-source means; note the limitation. Record: paper methods.

**143 — Trend detection.** Use: `GET /api/devices/{code}/trend` on the 30-day data. Record: poster figure.

**144 — Statistics teacher check.** Do: bring `Analysis/out/*/report.md`. Record: notes.

**147 — Raw data with a DOI.** Do: deposit `Data/field/` (paired CSV, instrument files, data dictionary) on Zenodo/OSF; cite the DOI on the poster QR. Record: DOI in README.

## I AquaNet

**150 — Confusion matrix on real data.** Use: `Analysis/aquanet_v3_field_eval.py paired.csv`. Record: report.

**151 — Why a network.** Use: the ablation table from the same script; write the argument from it. Record: paper.

**156 — Training-data generation.** Do: add one paragraph on why the distributions are realistic, with a citation. Use: `scripts/train_aquanet_v2.py`, `Docs/neural/AQUANET_V3_REPORT.md`. Record: report.

## J Hardware

**164 — Robust prototype with a dummy cell.** Do: build a resistor/capacitor dummy cell that gives a stable scan; test the whole demo twice. Record: `HARDWARE_CHANGELOG.md`.

**165 — Power per mode; battery life.** Use: `Docs/templates/power_log_template.csv` → `Analysis/power_budget.py`. Record: report + `CLAIMS_REGISTER` S4.

**166 — Potentiostat characterisation.** Do: dummy-cell scans: noise floor, linearity vs known resistors, step response. Record: `HARDWARE_CHANGELOG.md`; thresholds for `QC_REF_*` tuned from it.

**167 — Fluidics and carry-over.** Use: `carryover_holdtime_sheet.csv`; `field_blank` QC runs. Record: report; rinse rule in the SOP.

**168 — Enclosure IP/UV/heat.** Use: `Docs/templates/enclosure_test_log.csv`. Record: log + photos.

**169 — Drop/vibration.** Use: same log. Record: same.

**170 — Wiring diagram and labelled photo.** Use: `Firmware/PINOUT.md`. Record: `Docs/hardware/`.

**171 — Solar sizing.** Do: get peak-sun hours for the worst month (NASA POWER / NREL); run `power_budget.py --sun-hours`. Record: report.

**172 — Tool-free electrode replacement.** Do: design a slot/clip; time a replacement. Record: `HARDWARE_CHANGELOG.md`.

**173 — Custom PCB.** Do: KiCad schematic from the pinout; one revision. Record: `Docs/hardware/`, changelog.

**174 — Reference-electrode self-test.** Done in firmware 5.10 (`REF_UNSTABLE` settle test); Do: tune `QC_REF_MAX_ABS_UA` / `QC_REF_MAX_DRIFT_UA` from item 166 measurements. Record: changelog.

**175 — LED/buzzer legend.** Use: `Firmware/PINOUT.md` §LED legend; print on the lid. Record: photo.

**177 — Cost curve across versions.** Do: one BOM CSV per hardware version → `project_figures.py cost` each → plot. Record: poster.

**178 — Spares.** Do: list (electrodes, tubing, cell, cable, power bank). Record: packing list.

**179 — Label printed parts.** Do: version + date embossed or marked. Record: changelog.

**180 — Fit tests for printed parts.** Use: `enclosure_test_log.csv` row "print fit". Record: log.

## K Firmware

**182 — 14-day soak.** Do: run a node on the bench 14 days; export; `deployment_report.py`. Record: report.

**183 — Offline buffering demo.** Do: unplug Wi-Fi 3 days; reconnect; the report's "late deliveries" shows them. Record: report.

**184 — OTA with rollback.** Do: flash a deliberately broken build via OTA; confirm rollback; log it. Record: logbook.

**185 — Watchdog and brown-out.** Do: provoke a hang (debug define) and a sag (lab supply); confirm reset counters in `/status.json`. Record: logbook.

**187 — Two boards.** Do: flash two; compare check-standard readings. Record: inter-device comparison (item 100).

**190 — Deep-sleep numbers.** Use: `power_log_template.csv` deep_sleep row with everything fitted. Record: power report.

## L Software

**193 — Alert to a real phone (video).** Do: configure one channel; trigger with a hardware reading; record the phone. Record: video file name in the logbook.

**194 — Lab-confirmation panel with real pairs.** Do: enter the first lab results; screenshot. Record: poster.

**196 — Native-speaker check of translations.** Do: have a native speaker read the safety strings in `frontend/i18n-*.js`; correct them. Record: commit.

**197 — Load on a cheap phone.** Do: open the dashboard on a real phone on mobile data; time it; replace the headless figure. Use: `Docs/PRIVACY_AND_PERFORMANCE.md`. Record: same.

## M Users

**202 — Interviews.** Use: `stakeholder_interview_guide.md` (IRB first). Record: notes + themes.

**203 — Comprehension test.** Use: `usability_trial_sheet.md` §Comprehension. Record: sheet.

**204 — Protocol for an unsafe reading.** Use: `communication_protocol.md`. Record: logbook roles.

**206 — Equity.** Do: one paragraph: who pays, who maintains, who owns the data (from interviews). Record: paper discussion.

**207 — Letter of support.** Use: `letter_templates.md`. Record: letter.

**208 — Consent.** Use: photo log consent column; media consent in the forms checklist. Record: signed forms.

**209 — After the project.** Do: decide (donate to the PHED lab, keep for a second season). Record: `DECISION_LOG.md`.

## N Impact

**210 — Cost per test and device.** Use: BOM → `project_figures.py cost`. Record: report.

**211 — Scale estimate.** Use: `Docs/templates/scale_assumptions_template.csv` → `Analysis/scale_estimate.py`. Record: report (ranges).

**212 — Health impact plainly.** Do: one sentence with a citation; no invented lives-saved number. Record: poster.

**213 — Deployment model.** Do: choose (handpump screening by the district lab recommended). Record: `DECISION_LOG.md`.

**214 — Maintenance per month.** Use: `scale_estimate.py` maintenance block (from the QC rules + electrode life). Record: report.

**215 — Partner conversation.** Do: one meeting (PHED / NGO); minutes. Record: logbook.

**216 — Patent only if warranted.** Do: decide after the patent search (item 40). Record: `DECISION_LOG.md`.

**217 — Environmental impact.** Do: waste per test (item 83), electrode disposal, device end of life. Record: paper.

**218 — Extension to other analytes.** Do: one paragraph. Use: `future_work_template.md`. Record: paper.

## O Safety

**220 — Chemical list with SDS; SRC review.** Use: `chemical_inventory.csv`. Record: Form 3 attachment.

**221 — All forms.** Use: `isef_forms_checklist.csv`. Record: forms folder.

**222 — Arsenic in a proper lab; waste plan.** Do: with the supervisor; write the waste route in the SOP. Record: SOP + safety log.

**223 — Lab safety log.** Use: `lab_safety_log.csv`. Record: every session.

**224 — Most dilute stock.** Do: calculate the lowest stock that still gives your standards; buy that. Record: chemical inventory.

**225 — Safety on the poster.** Use: `safety_poster_panel.md`. Record: poster.

## P Logbook

**226 — Dated logbook.** Use: `logbook_page_template.md`. Record: the logbook.

**227 — Abstract.** Use: `abstract_structure.md` (structure only). Record: registration.

**228 — IMRaD paper.** Use: `paper_outline.md`. Record: paper.

**229 — Limitations.** Use: `limitations_template.md` + `CLAIMS_REGISTER.md`. Record: paper + poster.

**230 — Future work.** Use: `future_work_template.md`. Record: paper.

## Q Poster

**231 — One story; result in the title.** Use: `poster_checklist.md`. Record: poster.

**232 — Results panel largest.** Use: `make_poster_figures.py`. Record: poster.

**234 — Supporting documents on the table.** Do: logbook, SOP, forms, claims register, data dictionary, printed reports. Record: packing list.

**235 — Prototype opened + used electrode.** Do: bring a used electrode in a labelled bag. Record: packing list.

**237 — Display and safety rules.** Use: `poster_checklist.md` last items. Record: checklist.

**240 — Three strangers read the poster.** Do: ask what they understood; fix. Record: logbook.

## R Interview

**241 — 60 s and 3 min pitches.** Do: write and time them. Record: logbook.

**242 — Every member explains chemistry, statistics, code.** Use: `CODE_GUIDE.md`, analysis reports, `judge_questions.md`. Record: mock sessions.

**243 — 40 hard questions.** Use: `Docs/templates/judge_questions.md` (pointers to the honest facts). Record: your answers in the logbook.

**244 — Three mock sessions.** Use: `mock_judging_scoresheet.md`. Record: scoresheets.

**245 — Know the numbers.** Do: make a one-page "numbers card" from the analysis reports. Record: card.

**246 — "I don't know, but…".** Do: practise with the question bank. Record: mock notes.

**247 — Special-award judges.** Do: list the awards relevant to water/environment and their criteria. Record: logbook.

**248 — Interruptions.** Use: mock scoresheet rule. Record: scoresheets.

**249 — One true field story.** Do: pick it from the field-day sheets. Record: logbook.

**250 — Record a practice interview.** Do: phone video; watch it. Record: file name.

## S Credibility

**251 — Mentor.** Do: ask a chemistry teacher / local scientist; log meetings. Record: logbook.

**252 — School fair first.** Do: present; collect questions. Record: logbook.

**253 — Student journal.** Do: submit the paper after the fair. Record: paper.

**254 — Dataset DOI.** See 147. Record: README.

**255 — Hardware licence.** Do: choose (CERN-OHL-P recommended); add a LICENSE file in `models_3d/`. Record: `CREDITS.md`.

**256 — Youth programmes.** Do: only with real data. Record: timeline.

## T Cut

**260 — Catamaran and tank as future work.** Do: label the two concept documents as such on the poster (they are already in `HARDWARE_CHANGELOG.md` as concepts). Record: poster.

## U Repository

**265 — Tag the fair version.** Do: at the freeze, `git tag -a isef-2027 -m "version shown at ISEF 2027" && git push origin isef-2027`. Record: `DECISION_LOG.md`.

**267 — Names and roles in the README.** Do: complete the Team table. Record: README.

---

## Ready-made software that still has to meet real data

These items were marked "done" in v5.9 because their code and tests exist; Nalin Aggarwal's v5.10 review moved them to
*Tooling ready*: they count as done only once real samples or hardware have gone through them. For each, Do = the real
run; Use = the tool; Record = where the result goes.

**47 — Landscape figure (cost vs LOD).** Do: fill `Data/field/landscape_template.csv` with datasheet/quote numbers. Use: `project_figures.py landscape`. Record: figure + literature rows.

**89 — Blanks with every batch.** Do: run a reagent blank at the start of every batch of real samples. Use: `POST /api/qc/runs` `run_type=blank`. Record: QC log; the server gates low readings on it.

**90 — Check standard start and end of each field day.** Do: a real 10 µg/L standard, opening and closing. Use: `run_order.py` sheet rows; `control_chart.py` weekly. Record: QC log + chart.

**91 — Spike recovery on real samples.** Do: spike one real sample per matrix per day. Use: `run_type=spike_recovery` with `baseline_ug_l`. Record: QC log.

**95 — Blind samples.** Do: run a real day from a sealed-key sheet. Use: `run_order.py`. Record: sheet + key in the logbook.

**96 — Randomised run order.** Do: same sheet; note the seed. Record: logbook.

**98 — Auxiliary-sensor calibration.** Do: pH buffers, conductivity standard, turbidity standard, reference thermometer on the real node. Use: QC run types `ph_buffer` … Record: `/api/qc/status sensor_checks`.

**99 — Control chart.** Do: ≥ 10 real check-standard runs, then weekly. Use: `control_chart.py`. Record: chart in the logbook.

**110 — Confusion matrices at 10 / 20 / 50 with CIs.** Do: run on the real paired export. Use: `paired_validation.py`. Record: report + poster.

**111 — Chain of custody.** Do: fill `SampleMeta` for every real bottle. Use: `/api/scans` or `/api/readings` `sample` object; `field_day_sheet.csv`. Record: paired export.

**112 — GPS / source type / depth / time per sample.** Do: same, at the pump. Record: same.

**122 — Share results back.** Do: hand the QR sticker and the PDF certificate to the owner and the district lab for real sources. Use: public page, `/api/reports/certificate/pdf`. Record: communication log.

**129 — Map of field results.** Do: set real site coordinates (`PUT /api/admin/devices/{code}/site`); screenshot the dashboard map. Record: poster.

**130 — Scatter with 1:1 line and Bland–Altman.** Do: real paired export. Use: `paired_validation.py`. Record: report figures.

**131 — Deming slope and intercept with CIs.** Do: same run. Record: report.

**132 — Sample-size justification.** Do: read the sample-size table of the real report; state the CI width. Record: paper methods.

**133 — ROC and threshold.** Do: real report. Record: poster.

**134 — CV % at low / medium / high.** Do: repeat real samples under the same `sample_code`. Use: `paired_validation.py` replicate table; `electrode_study.py`. Record: report.

**136 — Uncertainty for every poster number.** Do: take every figure from the real reports with its interval. Record: poster.

**139 — Interference by regression.** Do: real interferent series. Use: `interference.py`. Record: report.

**148 — AquaNet evaluated on real data.** Do: `aquanet_v3_field_eval.py paired.csv`. Record: report; `CLAIMS_REGISTER` N1.

**149 — Baselines (threshold rule, logistic regression).** Do: same run; compare the three tables. Record: report + poster.

**152 — Ablation.** Do: same run; read the ablation table. Record: report.

**153 — Reliability diagram.** Do: same run; `reliability.svg` and the ECE. Record: poster.

**160 — Failure cases.** Do: read the "rows the network got wrong" table; explain each. Record: logbook.

**183 — Offline buffering demo.** Do: 3 days unplugged on a real node; `deployment_report.py` late deliveries. Record: report.

**184 — OTA with rollback.** Do: push a deliberately broken build; confirm rollback on a real board. Record: logbook.

**233 — Figure standards.** Do: check every poster figure has units, n, intervals, source. Use: `poster_checklist.md`. Record: checklist.

**236 — Printed QR.** Do: `project_figures.py qr --url <repository or DOI>`; print. Record: poster.
