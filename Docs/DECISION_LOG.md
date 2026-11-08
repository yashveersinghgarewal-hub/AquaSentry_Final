# Decision log

ISEF item 20: each change of direction with its date, what and why. The software decisions below come from the
changelog and the two reviews; add the team's chemistry, hardware and study decisions underneath in the same form.

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-11-07 | Keep the rule-based classifier primary; the network can tighten but never relax a verdict | Network-only verdicts | A model trained on simulated data must not be able to call unsafe water safe (v4.1, tests) |
| 2026-11-07 | Drop the 50 µg/L "relaxation" tier | Keep both tiers | IS 10500 Amendment 1 (2015) removed it; WHO is 10 µg/L (v5.2) |
| 2026-11-07 | Show "below sensor LOD" instead of a number under 20 µg/L | Print the estimate anyway | The strip cannot quantify there; a number would imply precision (v5.2) |
| 2026-11-08 | Per-device calibration records with IDs; standard addition supported | One factory curve | Matrix effects differ per source; traceability (v5.6) |
| 2026-11-08 | Store UTC; display local; mark unknown sample times | Trust device clocks | Field clocks drift and reset (v5.6–v5.7) |
| 2026-11-08 | A scan with a fault is a failed test, never a number | Report with a warning | Harm review: a wrong low number is worse than no number (v5.7) |
| 2026-11-08 | Check standard every 7 days and calibration ≤ 90 days or low readings are not trusted | No gating | Low readings are the dangerous failure mode (v5.7) |
| 2026-11-08 | Writes locked to this computer or a device with its key | Open API | Field pilot exposure (v5.7) |
| 2026-11-08 | One screening outcome with a measured guard band | Four tier labels | Review item 04: 10.1 µg/L was "Caution" and "Safe" at once (v5.8) |
| 2026-11-08 | Native scans stored with checksums; reprocessing creates a new linked reading | Overwrite on reprocess | Evidence must be immutable (v5.8) |
| 2026-11-08 | The browser runs a checked port of the server pipeline and prefers the server's answer | Separate JS maths | Browser and server disagreed on the same trace (v5.8) |
| 2026-11-08 | Factory calibration labelled a synthetic example | Present R² 0.9967 as accuracy | It was fitted on four simulated standards (v5.8) |
| 2026-11-08 | A fitted calibration's LOD is floored at the validated method LOD | Trust the fit | A perfect fit claimed 1e-14 µg/L and then failed every scan (v5.8) |
| 2026-11-08 | Analysis scripts are numpy-only with SVG output | matplotlib / notebooks | Runs anywhere, figures print cleanly, no hidden state (v5.8–v5.9) |
| 2026-11-08 | Grouped (by site) evaluation; refuse to run below 4 sites / 40 pairs | Random row splits | Random splits leak the site matrix; tiny studies produce noise "wins" (v5.8) |
| 2026-11-08 | Judging mode hides market, sales and the assistant | Remove those pages | Roadmap items 195/258/262: keep them as backup, out of the science story (v5.9) |
| 2026-11-08 | Stop adding product features after v5.9 | Keep building | Roadmap item 257: every further hour goes to real measurements |
| *(date)* | *Electrode choice …* | | |
| *(date)* | *Deposition time / potential …* | | |
| *(date)* | *Primary user and deployment model …* | | |
| *(date)* | *Competition prototype …* | | |

## Things deliberately not done (item 46)

- No mercury electrodes; no mercuric-bromide (Gutzeit) chemistry in the device.
- No invented coordinates for demo data; no simulated readings in reports or alerts.
- No accuracy claim for the network beyond its synthetic benchmark until the paired dataset exists.
