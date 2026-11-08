# Judge question bank (ISEF items 243, 245, 246) — answers in YOUR words; the pointer says where the honest fact lives

| # | Question | Where the fact is |
|---|---|---|
| 1 | What is your detection limit and how did you measure it? | `Analysis/linearity.py` report; CLAIMS_REGISTER M1 (currently a specification, 20 µg/L) |
| 2 | The legal limit is 10 µg/L and you detect from 20. So what is the device for? | screening outcome logic; REQUIREMENTS_TRACEABILITY C1–C3 |
| 3 | How many real water samples have you compared with a laboratory? | `paired_validation.py` report, n and sites |
| 4 | What is your sensitivity at 10 µg/L and its confidence interval? | same report (Wilson intervals) |
| 5 | Why Deming regression and not ordinary least squares? | both methods carry error (paired_validation.py docstring) |
| 6 | What does the neural network add over a threshold rule? | `aquanet_v3_field_eval.py` baselines + ablation |
| 7 | What was the network trained on? | simulated readings — CLAIMS_REGISTER N1 |
| 8 | Can the network ever call unsafe water safe? | no: hard rules; `test_aquanet_v3.py`, item 154 |
| 9 | What happens when copper is present? | `interference.py` report; robust baseline; secondary-peak flag |
| 10 | As(III) or total arsenic? | arsenic_species field; pre-reduction step [supervisor] |
| 11 | How do you know the electrode is still good? | check standards, control chart, REF_UNSTABLE, calibration age |
| 12 | What is the uncertainty of one reading and where does the number come from? | ± U (k = 2) from scan noise + 5 % calibration term |
| 13 | How is a result tied to its raw data? | checksum, analysis version, calibration ID on the certificate |
| 14 | What did you do when a scan was malformed? | rejected with a reason, never a number |
| 15 | How many electrodes did you test and how different were they? | `electrode_study.py` |
| 16 | How long does an electrode last? | same |
| 17 | What is the cost per test, from receipts? | `project_figures.py cost` |
| 18 | How long does the battery last; how did you measure it? | `power_budget.py` with a measured log |
| 19 | What breaks in the field? | FMEA; deployment report gaps |
| 20 | Who is the user and what do they do with a positive result? | interview themes; communication protocol |
| 21 | Which parts did you build, which did you buy, which did AI help with? | CREDITS; AI_USE_STATEMENT |
| 22 | What would you do with another six months? | three experiments in your future-work section |
| 23 | What is the biggest weakness of this project? | CLAIMS_REGISTER targets (say them yourself first) |
| 24 | How did you randomise and blind your measurements? | `run_order.py` sheets and sealed keys |
| 25 | Why did your calibration R² look so good? | it was four synthetic standards — say so |
| 26 | How did you choose 20 µg/L and the retest band? | guard band = expanded uncertainty |
| 27 | What was your sample size calculation? | paired_validation sample-size table |
| 28 | How do you handle lab results below the reporting limit? | censored; qualifier "<" |
| 29 | What is the false-alarm rate? | deployment report: positives not repeated; needs lab |
| 30 | What did the government field kit say on the same samples? | kit_result column (item 117) |
| 31 | Show me one raw voltammogram and explain every feature. | stored scans; trace viewer |
| 32 | How did you validate the peak-finding? | `peak_check.py` vs hand measurements |
| 33 | Where does the sample go after the test; is anything hazardous? | SOP waste steps; safety panel |
| 34 | What is the pH / temperature effect? | interference.py with pH / temperature as x |
| 35 | How do you know the clock on the device is right? | time_source; server receipt fallback |
| 36 | Can someone fake a reading? | write lock, device keys, checksums |
| 37 | What is in the firmware self-test? | boot self-test output |
| 38 | What is new compared with Bullen et al. / commercial kits? | landscape figure; literature table |
| 39 | What would it cost a district to run this for a year? | `scale_estimate.py` with stated assumptions |
| 40 | If you had to drop the neural network, would the project still work? | yes: rules + pipeline; say why you kept it |

Rehearse "I don't know, but here is how I would find out" for anything not in the table (item 246).
