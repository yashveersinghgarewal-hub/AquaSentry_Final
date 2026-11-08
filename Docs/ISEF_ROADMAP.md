# AquaSentry → Regeneron ISEF: 267 changes that move the needle

Written 8 November 2026. Regeneron ISEF 2027 is **8–14 May 2027 in Los Angeles**; Team India is picked through the **IRIS National Fair**. This is a to-do list for the student team, not text to submit. Read the first section before anything else.

**How to use this list**

- Every item has a priority. **P0** = do it or the project is weak at ISEF level (or at risk under the rules). **P1** = clearly raises the score. **P2** = polish, do it if there is time.
- Items are grouped by the five ISEF engineering judging criteria (Research Problem 10 pts, Design & Methodology 15, Execution 20, Creativity & Impact 20, Presentation 35 = poster 10 + interview 25), then rules and safety, then the booth and the interview.
- The single biggest gap today: **almost every number in this project comes from simulated data**, and the sensor's detection limit (**20 µg/L**) is **twice the legal limit (10 µg/L)**. Items marked ★ attack those two problems. A judge will find both within two minutes, so fix them first.
- Tick items off in your logbook with the date, not here. The logbook is evidence; this file is a plan.

---

## 0. Rules that can disqualify you (read first)

1. **P0** ★ **Do not let generative AI write the research plan, abstract, poster or citations.** ISEF rules forbid it, and everything submitted must be in your own words. This list, the code comments and the docs in this repo were written with an AI assistant: use them as notes, then write your own documents from scratch.
2. **P0** **Disclose AI use.** ISEF allows AI as a resource if it is cited and acknowledged. Write a one-page "AI use statement": which parts of the code and docs were AI-assisted, which tools and versions, what you checked yourself, and what you designed yourself. Keep it in the logbook and at the booth.
3. **P0** Be able to explain **every file you show**, line by line if asked. If you can't explain a part of the code, rewrite it yourself or leave it out of the presentation. Judges score "degree of independence".
4. **P0** **12-month rule:** ISEF 2027 judges only up to 12 months of continuous research, and nothing done before **January 2026**. Write down the date your current research year started and keep everything you present inside that window.
5. **P0** If any of this builds on an earlier year's project, it is a **continuation**: fill in **Form 7**, show what is new this year (a new variable or line of inquiry, not just more samples) and label older material "previous work" at the booth.
6. **P0** Write the **research plan before experimenting** (rationale, question/goal, materials, procedures, risk and safety, data analysis, bibliography). Any change after approval needs an **addendum** and re-approval before you collect more data.
7. **P0** Arsenic standards are **hazardous chemicals**: you need **SRC review**, a **Risk Assessment (Form 3)** signed by a **Designated Supervisor or Qualified Scientist**, and the SDS for every chemical. See section O.
8. **P0** If you survey or interview villagers, ASHA workers or households, that is **human-participant research**: IRB approval and informed consent **before** you start. Water samples alone are not, but questionnaires are.
9. **P0** **Team rules:** up to 3 members, every member eligible, membership fixed for the research year, full names on the abstract and forms. A project that competed as individual can't become a team project (or the reverse).
10. **P0** The booth must work **without electricity or internet**. The live dashboard can be a bonus, never the only way to see your results.
11. **P0** Credit every contribution: labs that ran samples, mentors, open-source libraries (Leaflet, ReportLab, FastAPI…), any published method you copied. Unpublished data from others needs written permission.

## A. Pathway and timeline

12. **P0** Confirm whether the team submitted to **IRIS 2026–27** (the window was 1 Aug – 13 Oct 2026). If yes, watch for the November shortlist; if not, decide now between another ISEF-affiliated fair you are eligible for (check the Society for Science "Find an Affiliated Fair" list) and planning for the 2027–28 cycle as a continuation.
13. **P0** Put the real dates in one calendar: IRIS shortlist (Nov 2026), IRIS National Fair (Nov 2026 or Jan–Feb 2027; the IRIS site lists both, so confirm), mentoring camps (Jan–Apr 2027), ISEF (8–14 May 2027), form deadlines.
14. **P1** Also enter the **Stockholm Junior Water Prize India** (run by IIT Madras; applications have closed around 30 April). It is a water-only competition, so arsenic monitoring fits it better than almost any other.
15. **P1** Pick the ISEF **category** on purpose. Best fit: **Environmental Engineering (ENEV)**, where the problem is drinking-water safety and the solution is an engineered system. Alternatives: Chemistry (analytical electrochemistry) if the electrode work becomes the headline; Embedded Systems if the firmware and on-device AI are the headline. Judges in each category look for different things, so write the 1-sentence pitch for each and pick the one that sounds strongest.
16. **P1** Work backwards from the fair date: field data finished 8 weeks before, poster draft 6 weeks before, three mock judging rounds in the last 4 weeks.
17. **P1** Freeze the scope by a fixed date (suggest 15 March 2027). After that only analysis, writing and practice.
18. **P2** Plan travel documents early (passport, US visa appointment wait times in India can be long).
19. **P2** Book time with a statistics teacher or university mentor for two reviews: one of the study design (now), one of the analysis (March).
20. **P2** Keep a "decision log" page: each time you change direction, write date, what, why. Judges love seeing reasoning.
21. **P2** Make a one-page Gantt chart for the poster or the logbook showing the year's work.

## B. Research problem and need (judging I, 10 pts)

22. **P0** Write one sentence for the need with a number and a source: how many people in India drink water above 10 µg/L arsenic (use the latest Jal Jeevan Mission / CGWB numbers, with year).
23. **P0** State **who** the user is (district lab? panchayat? household? ASHA worker?) and pick one primary user. The design follows from that choice.
24. **P0** Write the **design criteria** as measurable targets, e.g. LOD ≤ 5 µg/L, result in ≤ 15 min, ≤ ₹X per test, ≤ ₹Y per device, works 30 days unattended, runs on a 5 V solar supply. Judges score "definition of criteria".
25. **P0** Write the **constraints**: no lab skills, no fridge, unreliable power and network, local languages, hard water, iron and manganese in the groundwater, monsoon temperature range.
26. **P0** ★ Show why the current options fail the criteria: field test kits (Gutzeit/mercuric bromide, semi-quantitative, arsine gas risk), lab ICP-MS (accurate, slow, expensive, far away), existing electrochemical devices. A comparison table is enough.
27. **P1** Quantify the gap: average time from sample to lab result in a real district; how often a source is retested. Ask a PHED district lab directly and cite the conversation (with permission).
28. **P1** Explain why **continuous** monitoring matters: arsenic in tubewells can change seasonally; one test a year can miss it. Find a published seasonal-variation study and cite it.
29. **P1** Explain the health end point in plain words: chronic exposure → skin lesions, cancers, cardiovascular disease. Use WHO fact sheet numbers, not dramatic claims.
30. **P1** State the legal limits correctly: IS 10500:2012 with Amendment 1 (2015), 10 µg/L with no relaxation; WHO guideline 10 µg/L (provisional, set by measurement limits).
31. **P1** Turn the need into **one research question or engineering goal** sentence that is testable, e.g. "Can a ₹___ unattended gold-electrode SWASV node flag tubewells above 10 µg/L with ≥ 90 % sensitivity against ICP-MS?"
32. **P2** Map where the problem is: a district-level map of affected habitations (cite the source) next to where you tested.
33. **P2** One quote from a real stakeholder (district chemist, panchayat member) on what they need, with permission.
34. **P2** Avoid "AI-powered" as the problem statement; the problem is unsafe water, AI is one tool.
35. **P2** Explain why arsenic and not fluoride/nitrate/iron first (all exist in the same belts), and where the design could extend.

## C. Prior art and novelty

36. **P0** ★ Do a proper literature review: at least 20 peer-reviewed papers on electrochemical arsenic detection (gold, gold-nanoparticle, Mn/Au, carbon electrodes; SWASV vs DPASV), low-cost potentiostats, and arsenic field kits. Keep a table: method, LOD, interferents, cost, field-tested or not.
37. **P0** State exactly what is **new** in AquaSentry versus that table, in one sentence. If the honest answer is "integration and field deployment", say so and prove the integration works in the field.
38. **P1** Compare against the open-source potentiostat work (e.g. Bullen et al., PLoS ONE 2022) and commercial instruments (Metrohm, PalmSens) with numbers.
39. **P1** Look at past ISEF projects on arsenic or water sensing (Society for Science project abstracts database) and say how yours differs.
40. **P1** Patent search (Google Patents, InPASS): "arsenic voltammetry portable", "arsenic sensor IoT". Note the closest 5 patents.
41. **P1** Cite the Indian field-testing ecosystem (JJM field test kits, WQMIS, NABL labs) so judges see you know the system you plug into.
42. **P2** Cite earlier Indian student and startup efforts on arsenic sensing and state what you learned from them.
43. **P2** Keep a BibTeX/Zotero library; cite in one consistent style (APA or ACS) on the poster and in the paper.
44. **P2** Read and cite the WHO and BIS documents directly, not secondary blogs.
45. **P2** Note where other people's code or designs were reused (e.g. electrode cell design) and the licence.
46. **P2** List what you deliberately did **not** do (e.g. no mercury electrodes) and why.
47. **P2** Prepare a one-slide "landscape" figure: cost vs LOD for each method, your device marked.

## D. Engineering design process (judging II, 15 pts)

48. **P0** Show **alternatives you considered** for each major choice with a decision matrix: electrode (bare gold, gold nanoparticle on screen-printed carbon, bismuth film, Mn-Au), technique (SWASV, DPASV, LSV), power (mains, solar + Li-ion, primary cells), comms (Wi-Fi, LoRa, GSM/SMS), form factor (catamaran, tank sentry, bench unit).
49. **P0** For each matrix, weight the criteria from section B and show the scores. One matrix on the poster, the rest in the logbook.
50. **P0** Document **iterations**: v1 → v5.6 already exist in the changelog; turn them into a design-history figure (what failed, what you changed, what you measured).
51. **P1** Separate the three things being engineered: the **sensor chemistry**, the **instrument** (potentiostat + fluidics + enclosure) and the **system** (network, dashboard, alerts). Judges get lost otherwise.
52. **P1** Draw one clear block diagram of the instrument (sample in → pump → cell → potentiostat → ESP32 → result) with part numbers.
53. **P1** Add a failure-mode table (FMEA): electrode fouling, bubble in cell, pump failure, low battery, wrong calibration, Wi-Fi loss; for each, how the device detects and reports it.
54. **P1** Show a **requirements traceability** table: each criterion → which test proves it → result.
55. **P1** Choose **one** prototype as the competition device (the bench MAS-G1 unit or the tank sentry). Present the catamaran as future work unless it has field data.
56. **P1** Write the design rationale for the 15 mL sample well and pump volumes (dead volume, rinse volume, cross-contamination).
57. **P1** Justify electrode choice with your own measurements, not just literature.
58. **P2** Make a bill of materials with prices and suppliers in India, and the cost per test (electrode, reagents, power).
59. **P2** Design for manufacture: which parts are 3D printed, which are bought, how long assembly takes (time it).
60. **P2** Show what you'd change for a version 2 production unit.
61. **P2** Write down every safety-by-design choice (no arsenic waste dumped, low-voltage, sealed electronics).
62. **P2** Include an exploded view of the enclosure from the STL files.
63. **P2** Keep the old prototypes; physical iteration history is convincing at a booth.

## E. Sensor science and chemistry ★

64. **P0** ★ **Get the limit of detection below 10 µg/L**, and ideally ≤ 5 µg/L, or the device cannot say "safe". Options to test: longer deposition time (60 → 180 → 300 s), more negative deposition potential, stirring during deposition, gold-nanoparticle-modified screen-printed electrodes, higher-surface-area gold, background subtraction. Plot LOD vs each variable.
65. **P0** ★ Measure LOD and LOQ properly: ≥ 10 blank replicates, LOD = 3.3·σ_blank/slope, LOQ = 10·σ/slope, with the calibration range stated. Report both in µg/L with uncertainty.
66. **P0** ★ Handle **As(III) vs As(V)**: gold SWASV mainly sees As(III); groundwater has both. Test a pre-reduction step (e.g. a published reducing reagent and acid conditions) and show recovery of As(V) spikes before and after. Without this, total arsenic is under-reported.
67. **P0** ★ Measure **copper interference** (Cu stripping peak overlaps As on gold): spike 0–200 µg/L Cu into a fixed As sample and plot the bias. Then test a mitigation (peak deconvolution, EDTA/masking, potential window shift).
68. **P1** Test the other common interferents in the arsenic belt: iron (Fe²⁺/Fe³⁺, often mg/L levels), manganese, phosphate, silicate, humic acid, chloride, hardness. One plot per interferent: As recovery vs interferent concentration.
69. **P1** Measure the effect of **pH** (5–9) and **temperature** (15–40 °C) on peak current and correct for them (the device already logs both).
70. **P1** Measure **electrode lifetime**: number of scans before slope drops 10 %; effect of cleaning/conditioning cycles. Plot slope vs scan number.
71. **P1** Measure **electrode-to-electrode variability** (≥ 5 electrodes from one lot, ≥ 2 lots): slope CV %. This decides whether one factory calibration is enough.
72. **P1** Measure **repeatability** (same sample, 10 scans) and **intermediate precision** (different days, electrodes, operators).
73. **P1** Show linearity range: at least 6 standards from 0 to 300 µg/L, residual plot, not only R².
74. **P1** Explain the electrochemistry on one poster panel: deposition As³⁺ + 3e⁻ → As⁰ on gold, then oxidative stripping; why square wave improves signal-to-noise.
75. **P1** Show raw voltammograms (current vs potential) for blank, 10, 50, 100 µg/L on one plot. Judges trust raw data.
76. **P1** Validate the baseline-subtraction/peak-finding algorithm against hand-measured peaks on ≥ 50 scans.
77. **P1** Test **matrix effects** in real well water vs deionised water: compare calibration slopes; this is why standard addition exists.
78. **P1** Compare **external calibration vs standard addition** on the same real samples against ICP-MS. Show which is more accurate and at what cost in time.
79. **P1** Test the effect of **dissolved oxygen** and whether purging or a reducing agent is needed.
80. **P2** Try a cheaper electrode (screen-printed gold or carbon + gold film) and compare cost per test vs performance.
81. **P2** Characterise the electrode surface (cyclic voltammetry in sulfuric acid for gold area; optical microscope images before/after use).
82. **P2** Measure sample stability: how long a collected sample keeps its As(III)/As(V) ratio; whether acidifying is needed.
83. **P2** Measure reagent consumption and waste per test and show safe waste handling.
84. **P2** Report the potentiostat's own noise floor (current noise with dummy cell) and compare with the signal at 10 µg/L.
85. **P2** If time permits, demonstrate speciation (As(III) and total As separately) as an extension; it is rare in low-cost devices.
86. **P2** Compare SWASV parameters (frequency, amplitude, step) in a small design-of-experiments (2³ factorial) rather than one-at-a-time.
87. **P2** Show a Randles–Sevcik or peak-current vs deposition-time plot to show the physics behaves as expected.

## F. Controls, calibration and metrology

88. **P0** ★ Use **certified reference material** (traceable arsenic standard, and if possible a certified natural-water reference) and report recovery %.
89. **P0** Run **blanks** (reagent blank and field blank) with every batch; report them.
90. **P0** Run a **known check standard** at 10 µg/L at the start and end of each field day; reject the day's data if it drifts > 20 %.
91. **P0** Use **spike recovery** on real samples (spike 10 and 50 µg/L into each matrix type); acceptable range e.g. 80–120 %.
92. **P1** Record every calibration in the platform (the standard-addition and external endpoints already exist) and print the calibration ID on each result.
93. **P1** Calculate **measurement uncertainty** for a single reading (calibration, repeatability, temperature, electrode variability) and show it as ± on the device and poster.
94. **P1** Define the **decision rule** with uncertainty: when does a reading near 10 µg/L count as "above"? (guard band).
95. **P1** Blind some samples: someone else prepares coded standards so you don't know the concentration while measuring. Record this; judges ask about bias.
96. **P1** Randomise run order of standards and samples to avoid drift being confused with concentration.
97. **P1** Keep glassware/plastic cleaning protocol written down (acid washing) and logged.
98. **P1** Calibrate the pH, conductivity, temperature and turbidity sensors against standards and show the results; otherwise drop them from claims.
99. **P2** Use control charts (Shewhart) for the daily check standard over the whole study.
100. **P2** Do an inter-device comparison: 2–3 devices measuring the same samples.
101. **P2** Store every raw scan file with its metadata (date, electrode ID, calibration ID, operator) so any number on the poster can be traced back.
102. **P2** Write a standard operating procedure (SOP) for a measurement and follow it.
103. **P2** Have an independent person repeat the SOP from the written instructions to prove reproducibility.
104. **P2** Track electrode lot numbers in the platform (field exists) and report results per lot.
105. **P2** Document balance and pipette calibration checks.
106. **P2** Show what happens without the controls (e.g. no temperature correction) to prove each control matters.
107. **P2** Report units consistently (µg/L everywhere; avoid mixing ppb and mg/L on the poster).

## G. Field validation study ★

108. **P0** ★ **Replace simulated data with real samples.** Target ≥ 40 real groundwater samples from ≥ 15 sources across ≥ 2 districts, each measured by AquaSentry and by an accredited lab (ICP-MS or HG-AAS at a NABL lab).
109. **P0** ★ Pre-register the analysis in the logbook before the lab results come back: the primary end point (sensitivity and specificity at 10 µg/L), the sample size and the statistics.
110. **P0** ★ Report the full **confusion matrix** at 10 µg/L and 50 µg/L with Wilson 95 % confidence intervals (the validation endpoint already computes this) and say clearly how many unsafe samples were missed.
111. **P0** Use proper **sample collection**: clean bottles, purge the tubewell for a fixed time, split each sample (half for lab, half for device), chain-of-custody sheet, preservation as the lab requires.
112. **P0** Record GPS, source type, depth if known, date and time for each sample.
113. **P1** Make the sample set cover the range: some < 5, some 5–10, some 10–50, some > 50 µg/L; otherwise sensitivity is meaningless. Ask district PHED staff which sources are known high.
114. **P1** Do a **continuous deployment**: at least one node running ≥ 30 days unattended at a real source, with weekly lab grab samples to compare.
115. **P1** Report uptime, missed readings, battery behaviour, false alarms and maintenance visits for that deployment.
116. **P1** Test the device in **multiple conditions** (judging III asks for this): hot/cold, high turbidity, high iron, different operators, rain.
117. **P1** Compare with the government **field test kit** on the same samples; shows where your device adds value.
118. **P1** Repeat a subset of sources in a second season (post-monsoon vs pre-monsoon) to show temporal change, if the timeline allows.
119. **P1** Photograph every field site and setup (no faces without consent).
120. **P1** Get a letter from the lab confirming they ran the samples (judges sometimes ask for proof).
121. **P1** Budget the lab costs now (ICP-MS per sample) and ask the lab/PHED/IIT for support; many labs discount for students.
122. **P2** Share results back with the source owners and the district lab (ethics and impact).
123. **P2** If a sample is above the limit, have a plan to tell the community responsibly through the authority (agree it with your mentor before testing).
124. **P2** Use the platform's JJM export to show your data fits the government format.
125. **P2** Report the time per test in the field, measured with a stopwatch, including setup.
126. **P2** Record cost actually spent per sample.
127. **P2** Keep any samples that gave odd results for a re-test.
128. **P2** Run a small usability trial (with IRB approval) where a non-expert performs the test from your instructions.
129. **P2** Map the field results on the platform and screenshot it for the poster.

## H. Statistics and data analysis

130. **P0** Plot device vs lab on a scatter plot with the 1:1 line, plus a **Bland–Altman** plot (bias and limits of agreement).
131. **P0** Report regression slope/intercept with confidence intervals (Deming or Passing–Bablok regression is more correct than ordinary least squares here, because both methods have error).
132. **P0** Justify the sample size: with n unsafe samples, what is the width of the sensitivity confidence interval? Show the calculation.
133. **P1** Plot a **ROC curve** for the device reading as a classifier of "> 10 µg/L by lab", and choose the alarm threshold from it.
134. **P1** Report precision as CV % at low, medium and high concentration.
135. **P1** Handle values below LOD correctly (censored data; don't put zeros); the platform's Mann-Kendall code already censors at LOD, explain that.
136. **P1** Report uncertainty for every number on the poster (± or CI), and the n.
137. **P1** Use a significance test only where there is a hypothesis; otherwise report effect sizes and intervals.
138. **P1** Show the analysis is reproducible: one Python notebook or script in `Analysis/` that regenerates every figure from the raw files.
139. **P1** Use the right test for interference: a regression of recovery on interferent concentration with CI, not just "looked fine".
140. **P1** Look at outliers individually and explain them; never delete data without writing why in the logbook.
141. **P2** Run a power/sample-size estimate for a future larger study (e.g. 200 sources) as "future work".
142. **P2** Use a mixed model if many readings come from the same source (readings are not independent).
143. **P2** Show the trend detection (Mann-Kendall + Sen slope) on the 30-day deployment with real data.
144. **P2** Check the analysis with a statistics teacher; note it in the acknowledgements.
145. **P2** Avoid 3D charts, pie charts and dual axes on the poster.
146. **P2** Make figures colour-blind safe and readable from 1.5 m.
147. **P2** Keep the raw data in a public repository (Zenodo/OSF) with a DOI by the fair.

## I. AquaNet (the neural network) – make it defensible

148. **P0** ★ Be honest that AquaNet-V3 was **trained on simulated readings**. Retrain or at least **evaluate on the real field dataset** and report its accuracy vs the simple rule-based classification.
149. **P0** Show a **baseline**: does the neural network beat a threshold rule or logistic regression? If not, say so and keep the rules as primary (the platform already wraps it in hard safety rules).
150. **P0** Report its confusion matrix on held-out real data, not training data.
151. **P1** Explain why a network is needed at all (combining pH, temperature, conductivity, turbidity and peak shape) and what it adds beyond the arsenic number.
152. **P1** Show feature importance or ablation (remove each input, measure the effect).
153. **P1** Show its calibration (does 90 % confidence mean right 90 % of the time?) with a reliability diagram.
154. **P1** Make sure the hard safety rule can never be overridden to "safe" by the network, and show the test that proves it.
155. **P1** State parameter count (352), memory (1.4 KB) and inference time on the ESP32, measured.
156. **P1** Document the training data generation: what distributions, what noise model, and why they're realistic (cite).
157. **P2** Try a tiny model trained on raw voltammograms (1D CNN) vs extracted features, only if you have enough real scans.
158. **P2** Show quantised (INT8) vs float accuracy (parity tests exist).
159. **P2** Use cross-validation, not one split.
160. **P2** Describe the failure cases the model gets wrong.
161. **P2** Version the model and record which version produced each result (the platform stores firmware version; add model version to the poster tables).
162. **P2** Drop "AI" wording from the title unless the network is shown to matter.
163. **P2** Keep the chatbot out of the main pitch; it distracts from the science.

## J. Prototype hardware (judging III, 20 pts)

164. **P0** Bring a **working, robust prototype** to the fair (with a dummy cell for safe demonstration; no arsenic at the booth).
165. **P0** Measure and report **power consumption** in each mode (deep sleep, measuring, transmitting) and battery life calculated and measured.
166. **P1** Characterise the **potentiostat**: current range, resolution, noise, accuracy against a reference resistor network and against a commercial potentiostat on the same cell.
167. **P1** Test the **pump and fluidics**: volume delivered vs set volume, carry-over between samples (measure a blank after a high sample).
168. **P1** Make the enclosure field-worthy: IP rating test (spray/immersion), UV exposure, heat (inside temperature in sun).
169. **P1** Drop/vibration test for transport on village roads.
170. **P1** Show the PCB (or neat perfboard), wiring diagram and labelled photo; messy wiring costs "engineering skill" points.
171. **P1** Solar sizing calculation for the field node with real insolation data for the district.
172. **P1** Make electrode replacement a 1-minute, tool-free job and demonstrate it.
173. **P2** Design a custom PCB (KiCad) for the analog front end and get it fabricated.
174. **P2** Add a reference electrode check (open-circuit potential) as an automatic self-test.
175. **P2** Make the user interface on the device usable without a phone (LED/buzzer meaning printed on the lid).
176. **P2** Document all pin assignments and wiring in one table (firmware already defines them).
177. **P2** Reduce the cost of the bench unit; show the cost curve across versions.
178. **P2** Have a spare of every critical part at the fair.
179. **P2** Label the 3D-printed parts with version numbers.
180. **P2** Show tolerance/fit tests for printed parts.
181. **P2** Keep a hardware changelog alongside the software one.

## K. Firmware and reliability

182. **P1** Run a **long soak test** (≥ 14 days continuous on the bench) and report crashes, resets, memory, and data loss.
183. **P1** Demonstrate offline buffering: unplug Wi-Fi for 3 days, reconnect, show all readings arrive once (idempotency keys already exist).
184. **P1** Demonstrate safe OTA update with rollback on a real board.
185. **P1** Watchdog and brown-out behaviour tested and logged.
186. **P2** Measure time to first result after power-on.
187. **P2** Flash and test the firmware on two different ESP32 boards.
188. **P2** Keep the firmware build reproducible (CI already compiles 8 configurations; show the badge).
189. **P2** Add a self-test report printed on boot (sensors found, electrode OK, calibration age).
190. **P2** Explain the deep-sleep strategy and its effect on battery life with numbers.
191. **P2** Make the firmware version visible on every reading and on the poster.

## L. Software platform

192. **P1** Prepare an **offline demo** (the seeded demo database and the hosted read-only demo) that works without internet; replace "SIMULATED" data with your real field data when you have it.
193. **P1** Show one alert reaching a real phone (push/WhatsApp/SMS) in a recorded video.
194. **P1** Show the lab-confirmation panel with real paired results; it is the most convincing screen.
195. **P2** Keep the dashboard to the 3 screens you'll show; hide extras (market, sales pages) during judging.
196. **P2** Translate the alert text with a native speaker, not machine translation only.
197. **P2** Measure page load on a cheap Android phone on 3G.
198. **P2** Keep the test suite green and show the count (≈ 245 tests) as evidence of engineering discipline, briefly.
199. **P2** Explain data privacy: what location data is stored and who can see it.
200. **P2** Prepare the 60-second software demo script.
201. **P2** Have the JJM/WQMIS export ready to show compatibility with government systems.

## M. Users, community and ethics

202. **P1** Interview (with IRB approval) at least 5 stakeholders: district chemist, PHED engineer, ASHA worker, panchayat head, household. Write down what changed in the design because of them.
203. **P1** Show the result screen to non-expert users and measure if they understand it (comprehension test).
204. **P1** Decide the communication protocol for an unsafe reading (who is told first, what advice) with the district authority, so the device never causes panic or false reassurance.
205. **P1** Keep the "screening, not a certified lab test" message everywhere (already in the reports).
206. **P2** Think about equity: who pays, who maintains, who owns the data.
207. **P2** Get a letter of support from a panchayat, NGO or PHED office if they want to pilot it.
208. **P2** Respect consent for photos and names.
209. **P2** Plan what happens to deployed devices after the project ends.

## N. Impact, cost and scale (judging IV, 20 pts)

210. **P0** Compute **cost per test** and **cost per device** from real receipts, and compare with lab tests and field kits per test, with sources.
211. **P1** Estimate the scale: how many habitations could be covered for the cost of X lab tests; be conservative and show assumptions.
212. **P1** Estimate the health impact plainly (people served by monitored sources), without exaggerated claims.
213. **P1** Describe the deployment model (district lab-owned network vs household device) and pick one.
214. **P1** Describe maintenance needs per month (electrode change, calibration check) and who does them.
215. **P2** Talk to one potential partner (an NGO, a startup incubator, or IIT Madras/IIT Kharagpur arsenic groups) and record the outcome.
216. **P2** Consider a provisional patent only if there is a truly new mechanism; discuss with a mentor first (publication before filing can block a patent).
217. **P2** Show environmental impact of the device itself (e-waste, reagent waste) and the mitigation.
218. **P2** Explain how the approach extends to fluoride, nitrate, uranium or lead (and what changes).
219. **P2** Keep the business/market pages as backup material, not the main story.

## O. Safety, approvals and forms

220. **P0** List every hazardous chemical (arsenic standards, acids, reducing reagents, any mercury-free alternatives used) with its SDS; get the SRC to review before experimentation.
221. **P0** Prepare all forms the project needs (typically: Checklist for Adult Sponsor (1), Student Checklist (1A), Research Plan, Approval Form (1B), Regulated Research Institution form (1C) if work was done in a university or industry lab, Qualified Scientist (2) and Risk Assessment (3) for the hazardous chemicals, Human Participants (4) and consent forms if you survey people, Continuation (7) if applicable). Check each against the current ISEF rules, as the list changes yearly.
222. **P0** Do all arsenic work in a proper lab with gloves, eye protection and a supervisor; never at home. Write a waste-disposal plan (collect, label, give to a licensed disposal route).
223. **P1** Keep a lab safety log page per session (who supervised, what chemicals, what was disposed).
224. **P1** Use the most dilute stock that works; prepare standards by the supervisor if required.
225. **P2** Show safety on the poster briefly (judges and display & safety inspectors check it).

## P. Logbook, paper and abstract

226. **P0** Keep a **dated, handwritten (or timestamped digital) logbook**: plans, raw observations, failures, decisions, sketches. It is the strongest proof of independence.
227. **P0** Write a **250-word abstract** yourself: purpose, procedure, data, conclusions, current year only.
228. **P1** Write a full research paper (IMRaD, 10–15 pages) and have it reviewed by a mentor; submit to a student journal or the IRIS paper requirement.
229. **P1** Write a "limitations" section that names the LOD, As(III)/As(V), Cu interference, sample size and simulated training data honestly.
230. **P1** Write a "future work" section with 3 concrete next experiments; judges score "quality of ideas for further research".

## Q. Poster and booth (judging V-a, 10 pts)

231. **P0** One clear story on the poster: Need → Criteria → Design → Testing → Results → Impact → Limitations. Big title that says the result, e.g. "A ₹___ unattended sensor that flagged __ of __ unsafe tubewells against ICP-MS".
232. **P0** The **results panel is the largest**: device-vs-lab scatter, confusion matrix, LOD figure.
233. **P1** Every graph: axis labels with units, n, error bars, source of data, readable at 1.5 m.
234. **P1** Display the logbook, the paper, the forms and the AI-use statement on the table ("supporting documentation displayed").
235. **P1** The physical prototype on the table, opened so judges can see inside, plus a used electrode.
236. **P1** A printed QR code to the code repository and data DOI (works offline as print; no internet required to understand the poster).
237. **P2** Check the current ISEF display & safety rules (size limits, prohibited items: no chemicals, no arsenic-containing samples, photos with credits).
238. **P2** Use at most 3 colours plus neutrals and one typeface family.
239. **P2** Short labels in English; Hindi copy of the alert screen as an example only.
240. **P2** Get three people who don't know the project to read the poster for 60 s and say what it's about; fix what they miss.

## R. Interview preparation (judging V-b, 25 pts — the largest single block)

241. **P0** Prepare a 60-second and a 3-minute pitch; each team member must be able to give both.
242. **P0** Every member must explain the electrochemistry, the statistics and the code they wrote; judges check "contributions and understanding by all members".
243. **P0** Rehearse the top 40 hard questions with answers in your own words. Start with: Why is your LOD above the legal limit (or how did you fix it)? How do you handle As(V)? What about copper and iron? How many real samples? What did the lab say? Why a neural network? What did you do yourself vs the AI assistant vs your mentor? What would you do with one more year? How much does a test cost? Who will maintain it?
244. **P1** Do at least 3 mock judging sessions with scientists or engineers (an IIT/IISER professor, an environmental engineer, a chemist), and log the questions you couldn't answer.
245. **P1** Know the numbers by heart: LOD, sensitivity/specificity with CI, n, cost per test, battery life, price.
246. **P1** Practise saying "I don't know, but here is how I'd find out."
247. **P1** Prepare for special-award judges (water, environment, engineering societies) who visit separately with different questions.
248. **P2** Practise with someone interrupting you; real judges do.
249. **P2** Prepare one memorable, true field story (a specific well, a specific result).
250. **P2** Record a practice interview and watch it once.

## S. Credibility and recognition

251. **P1** Find a **mentor** with electrochemistry or environmental-engineering credentials and log the meetings; mention them correctly (what they advised vs what you did).
252. **P1** Present at a school/city science fair first for practice and feedback.
253. **P2** Submit the paper to a peer-reviewed student journal (e.g. Journal of Emerging Investigators) or a conference student session.
254. **P2** Publish the dataset with a DOI.
255. **P2** Open-source the hardware design with a licence (CERN-OHL or similar) and say so.
256. **P2** Apply to youth innovation programmes in India (e.g. those run by DST/INSPIRE, Atal Innovation Mission) only with real data; do not spread effort thin before ISEF.

## T. Stop doing / cut

257. **P1** Stop adding software features; the platform already exceeds what judges score. Every hour now goes to real measurements.
258. **P1** Remove or clearly separate marketing claims (market research, sales pages, ROI calculator) from the scientific story.
259. **P1** Remove any number that comes from simulation from the results panel, or label it "simulation" in the same font size.
260. **P2** Drop the catamaran and personal-tank prototypes from the main poster unless field-tested; show them as future work.
261. **P2** Avoid buzzwords ("revolutionary", "AI-powered", "100 % accurate").
262. **P2** Cut the chatbot from the demo.

## U. This repository

263. **P1** Put the real field dataset under `Data/field/` with a README (columns, units, how collected) and keep the simulated data clearly separate.
264. **P1** Add an `Analysis/` script that recreates every poster figure from `Data/field/`.
265. **P2** Tag the exact repository version used at the fair (`git tag isef-2027`).
266. **P2** Keep `CHANGELOG.md` and `Docs/IMPROVEMENT_LOG.md` as the design-history evidence.
267. **P2** Add your names and roles in the README once the team is final.

---

## The first 30 days (start here)

If only fifteen things get done, do these, in this order: 1, 2, 4, 6, 7 (forms and supervisor), 12, 24, 36, 64, 65, 66, 67, 88, 108, 109. They are the difference between "impressive software project" and "ISEF-level engineering with real evidence".

## Sources

- Society for Science, [ISEF Grand Award judging criteria](https://www.societyforscience.org/isef/grand-award/criteria/) (engineering: research problem 10, design & methodology 15, execution 20, creativity & impact 20, presentation 35).
- Society for Science, [Rules for all projects](https://www.societyforscience.org/isef/international-rules/rules-for-all-projects/) (12-month limit, January 2026 start for ISEF 2027, continuation/Form 7, teams, abstract, display without electricity or internet, generative-AI rule, attribution).
- Society for Science, [Affiliated fair network](https://societyforscience.org/isef/affiliated-fair-network/) and [Find an affiliated fair](https://findafair.societyforscience.org/).
- IRIS National Fair, [timeline and process](https://iris.exstemplar.com/) (2026–27 submissions 1 Aug – 13 Oct 2026, ISEF 8–14 May 2027, Los Angeles).
- Example ISEF Form 3 Risk Assessment guidance: [Colorado State Science & Engineering Fair risk-assessment guidelines](https://csef.natsci.colostate.edu/wp-content/uploads/2023/08/Risk-Assessment-Guidelines.pdf).
- IIT Madras, [Stockholm Junior Water Prize India](https://aquamap.iitm.ac.in/sjwp-india.html).
- Bullen et al. (2022), low-cost electrochemical arsenic detection with an open-source potentiostat, PLoS ONE (PMC8769315); other technical sources are listed in `Docs/IMPROVEMENT_LOG.md`.
