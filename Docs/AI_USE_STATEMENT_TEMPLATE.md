# AI use statement — template and factual inventory

ISEF items 1–2: generative AI may be used as a resource if it is cited and acknowledged, and it may not write the
research plan, abstract, poster or citations. This page gives the **facts** about AI assistance in this repository
so that the statement you write is accurate. The sections marked *(write yourself)* must be in your own words.

## 1. What in this repository was AI-assisted (factual)

| Area | AI-assisted? | Tool | Human work |
|---|---|---|---|
| Server code (`AquaSentry_Platform/app`, tests) | Yes — drafted and revised with Claude (Anthropic) in Claude Code sessions, Nov 2026 | Claude Sonnet / Opus / Fable 5.1 | Reviewed, run and merged by Yashveer Singh Garewal and Nalin Aggarwal; Nalin Aggarwal authored the v5.2–v5.7 branches |
| Dashboard (`frontend/`) | Yes, same sessions | same | same |
| Firmware (`Firmware/esp32_firmware`) | Yes, same sessions; compiled in CI for three chips | same | Hardware wiring and bench runs are the team's |
| Analysis scripts (`Analysis/`) | Yes | same | The statistics methods are standard (Deming, Bland–Altman, Wilson, conformal); the team must be able to explain each one |
| Documentation (`Docs/`, `README.md`, `CHANGELOG.md`) | Yes | same | Must not be submitted as the research plan, paper or poster text |
| AquaNet-V3 weights (`app/aquanet_v3_weights.json`) | Trained by `scripts/train_aquanet_v2.py` on simulated readings (AI-assisted script) | same | No real data was used in training |
| The ISEF roadmap and the 60-item review | Written with an AI assistant as planning notes | same | Plans, not submissions |

Open-source libraries used are listed in `Docs/CREDITS.md`; they are not AI output.

## 2. What we checked ourselves *(write yourself)*

For each area above: what you ran, what you measured, which test or bench result you looked at with your own eyes,
and what you changed because of it. Dates and logbook page numbers.

## 3. What we designed ourselves *(write yourself)*

The research question, the choice of chemistry and electrode, the field protocol, the decision criteria, the
hardware, and any algorithm or rule you specified before it was coded. Be specific; judges score independence.

## 4. What the AI did not do *(write yourself, and keep it true)*

Research plan, abstract, poster text, citations, laboratory work, field sampling, data entry, the interpretation of
results.

## 5. Where this statement lives

One printed page at the booth and in the logbook; the tools and model names from the table above; the date range.
