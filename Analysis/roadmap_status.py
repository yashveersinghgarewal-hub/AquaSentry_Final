#!/usr/bin/env python3
"""
Render the ISEF roadmap status register (all 267 items) from Docs/planning/isef_roadmap_status.csv into
Docs/ISEF_ROADMAP_STATUS.md, with a summary table by section and a bar figure.

Statuses:
  Done            the software part is implemented and tested (where column says where)
  Tooling ready   the software exists; the item closes when the team's data or measurements go through it
  Partial         software did part; the rest is the team's
  Open            software work that should wait for data (deliberately not done yet)
  Team / Lab / Field   no software share: logbook, writing, people, chemistry, bench or field work

Usage: python Analysis/roadmap_status.py          (rewrites Docs/ISEF_ROADMAP_STATUS.md, Docs/REMAINING_WORK.md
                                                   and Docs/planning/roadmap_status.svg)
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV = os.path.join(ROOT, "Docs", "planning", "isef_roadmap_status.csv")
MD = os.path.join(ROOT, "Docs", "ISEF_ROADMAP_STATUS.md")
SVG = os.path.join(ROOT, "Docs", "planning", "roadmap_status.svg")
REMAINING = os.path.join(ROOT, "Docs", "REMAINING_WORK.md")
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402

ORDER = ["Done", "Tooling ready", "Partial", "Open", "Team", "Lab", "Field"]
COLOUR = {"Done": sp.GREEN, "Tooling ready": sp.BLUE, "Partial": sp.AMBER, "Open": sp.VIOLET, "Team": sp.MUTED, "Lab": sp.RED, "Field": sp.RED}


def load():
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["item"] = int(r["item"])
    rows.sort(key=lambda r: r["item"])
    return rows


def render(rows):
    by_section = OrderedDict()
    for r in rows:
        by_section.setdefault(r["section"], []).append(r)
    total = Counter(r["status"] for r in rows)
    software_share = sum(total[s] for s in ("Done", "Tooling ready", "Partial", "Open"))
    L = ["# ISEF roadmap — status of all 267 items", "",
         "Generated from `Docs/planning/isef_roadmap_status.csv` by `Analysis/roadmap_status.py`; edit the CSV, rerun. "
         "The roadmap (`Docs/ISEF_ROADMAP.md`) is the plan; this page says, item by item, what the software has done, "
         "what is ready and waiting for the team's data, and what no code can do.", "",
         "| status | meaning | items |", "|---|---|---|",
         f"| **Done** | software implemented and tested; nothing left to measure for this item | {total['Done']} |",
         f"| **Tooling ready** | software exists but has not been run on real samples or hardware; closes when the team's data go through it | {total['Tooling ready']} |",
         f"| **Partial** | software did its part; the rest is the team's | {total['Partial']} |",
         f"| **Open** | software work deliberately waiting for data | {total['Open']} |",
         f"| **Team** | logbook, writing, forms, people — no software share | {total['Team']} |",
         f"| **Lab / Field** | chemistry, bench or field work | {total['Lab'] + total['Field']} |",
         f"| | **total** | **{len(rows)}** ({software_share} with a software share) |", "",
         "![status by section](planning/roadmap_status.svg)", "",
         "## By section", "", "| section | items | Done | Tooling ready | Partial | Open | Team | Lab/Field |", "|---|---|---|---|---|---|---|---|"]
    for sec, items in by_section.items():
        c = Counter(r["status"] for r in items)
        L.append(f"| {sec} | {len(items)} | {c['Done']} | {c['Tooling ready']} | {c['Partial']} | {c['Open']} | {c['Team']} | {c['Lab'] + c['Field']} |")
    L += ["", "## Every item", ""]
    for sec, items in by_section.items():
        L += [f"### {sec}", "", "| # | P | item | owner | status | where / next step |", "|---|---|---|---|---|---|"]
        for r in items:
            where = r["where_or_next_step"].replace("|", "\\|")
            L.append(f"| {r['item']} | {r['priority']} | {r['title']} | {r['owner']} | **{r['status']}** | {where} |")
        L.append("")
    L += ["## Reading the register honestly", "",
          "- *Done* never means the sensor works. It means the code path and its test exist. Every accuracy claim still waits for `Data/field/`.",
          "- The 15 items the roadmap says to do first (1, 2, 4, 6, 7, 12, 24, 36, 64–67, 88, 108, 109) are team, lab and field work; the software's share of them (templates, QC runs, traceability, analysis) is ready.",
          "- Item 257 is in force: after v5.9 the software only changes to fix a defect or to process real data.", ""]
    return "\n".join(L), by_section, total


# Who does what is left, in the order the team should work through it.
GROUPS = [
    ("Lab", "In the lab (chemistry and bench)", "Needs chemicals, a supervisor and the instrument. Do these under the approved research plan."),
    ("Field", "In the field", "Needs real sources, sample bottles and a laboratory partner."),
    ("Tooling ready", "Run the ready-made tools on real data",
     "The software for these exists and is tested, but nothing real has gone through it yet. Each closes when the "
     "measurements are made and the script or endpoint named in the row is run on them."),
    ("Partial", "Finish what the software started", "The software did its share; the rest is writing, drawing, measuring or choosing."),
    ("Team", "Team work: rules, writing, people, poster and interview", "No software share. These are logbook, forms, writing and practice."),
    ("Open", "Software work that should wait for data", "Deliberately not done yet."),
]

# Not roadmap items, but still open outside the code (kept here so nothing is lost between versions).
OUTSIDE = [
    "Write sections 2-4 of `Docs/AI_USE_STATEMENT_TEMPLATE.md` (what you checked, what you designed, what the AI did not do) in your own words, and print it for the booth.",
    "Have native speakers check the Hindi, Bengali, Assamese and Punjabi screens (`AquaSentry_Platform/frontend/i18n-*.js`); they were machine-assisted.",
    "Complete the Team section of `README.md` with every member's name and role once the team is final (ISEF allows at most three).",
    "Confirm in writing whether the team entered IRIS 2026-27 (submissions closed 13 October 2026) and record the answer and the next fair in `Docs/planning/timeline.csv`.",
    "Review GitHub's automatic dependency pull requests (Dependabot) as they arrive; CI must pass before merging.",
]


def _line(r):
    step = r["where_or_next_step"].replace("\n", " ").strip()
    return f"- [ ] **{r['item']}** ({r['priority']}) {r['title']}. *{step}*"


def render_remaining(rows):
    open_rows = [r for r in rows if r["status"] != "Done"]
    p0 = [r for r in open_rows if r["priority"] == "P0"]
    c = Counter(r["status"] for r in open_rows)
    L = ["# What is left before ISEF", "",
         "Generated from `Docs/planning/isef_roadmap_status.csv` by `Analysis/roadmap_status.py` (edit the CSV, rerun; a test "
         "keeps this page in sync). Item numbers match `Docs/ISEF_ROADMAP.md`, where each item is explained.", "",
         f"**{len(open_rows)} of {len(rows)} roadmap items are still open.** The software is finished except two items that wait "
         f"for data; what remains is laboratory work ({c['Lab']}), field work ({c['Field']}), running the ready-made tools on real "
         f"measurements ({c['Tooling ready']}), finishing items the software started ({c['Partial']}) and the team's own work "
         f"({c['Team']}: rules, writing, people, poster, interview).", "",
         "Tick items here or copy the list into the logbook with the date you finish each one. The logbook is the evidence; "
         "this page is the plan. Do not let an AI write the research plan, abstract, poster or citations (item 1).", "",
         f"## Start here: the {len(p0)} must-do (P0) items", "",
         "These decide whether the project is ISEF-level at all. The order is the roadmap's: rules first, then the science.", ""]
    L += [_line(r) + f" `{r['status']}`" for r in p0]
    for status, title, blurb in GROUPS:
        items = [r for r in open_rows if r["status"] == status and r["priority"] != "P0"]
        if not items:
            continue
        L += ["", f"## {title} ({len(items)})", "", blurb, ""]
        sec = None
        for r in items:
            if r["section"] != sec:
                sec = r["section"]
                L += ["", f"**{sec}**", ""]
            L.append(_line(r))
    L += ["", "## Outside the roadmap", ""] + [f"- [ ] {t}" for t in OUTSIDE]
    L += ["", "## Already done in software", "",
          f"{sum(1 for r in rows if r['status'] == 'Done')} items need nothing more from the code; they are listed with their "
          "file and test in `Docs/ISEF_ROADMAP_STATUS.md`. *Done* there never means the sensor works: every accuracy claim "
          "still waits for real paired samples in `Data/field/`.", ""]
    return "\n".join(L)


def figure(by_section):
    secs = list(by_section)
    H = 60 + 22 * len(secs) + 40
    W = 820
    g = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' {sp.FONT}>",
         f"<rect width='{W}' height='{H}' fill='white'/>",
         f"<text x='16' y='24' font-size='15' font-weight='700' fill='{sp.INK}'>ISEF roadmap: 267 items by section and status</text>"]
    x0, xmax = 250, W - 20
    scale = (xmax - x0) / max(len(v) for v in by_section.values())
    for i, sec in enumerate(secs):
        y = 50 + i * 22
        g.append(f"<text x='{x0 - 8}' y='{y + 12}' font-size='11' text-anchor='end' fill='{sp.INK}'>{sp._esc(sec)}</text>")
        x = x0
        c = Counter(r["status"] for r in by_section[sec])
        for st in ORDER:
            n = c[st]
            if n:
                w = n * scale
                g.append(f"<rect x='{x:.1f}' y='{y}' width='{w:.1f}' height='16' fill='{COLOUR[st]}' fill-opacity='{0.95 if st in ('Done', 'Tooling ready') else 0.7}'/>")
                if w > 14:
                    g.append(f"<text x='{x + w / 2:.1f}' y='{y + 12}' font-size='10' text-anchor='middle' fill='white'>{n}</text>")
                x += w
    ly = 50 + len(secs) * 22 + 14
    x = x0
    for st in ORDER:
        g.append(f"<rect x='{x}' y='{ly}' width='12' height='12' fill='{COLOUR[st]}'/>")
        g.append(f"<text x='{x + 16}' y='{ly + 10}' font-size='10.5' fill='{sp.INK}'>{st}</text>")
        x += 16 + 7 * len(st) + 18
    g.append("</svg>")
    return "\n".join(g)


def main() -> int:
    rows = load()
    md, by_section, total = render(rows)
    with open(MD, "w", encoding="utf-8") as f:
        f.write(md)
    with open(SVG, "w", encoding="utf-8") as f:
        f.write(figure(by_section))
    with open(REMAINING, "w", encoding="utf-8") as f:
        f.write(render_remaining(rows))
    print(f"{len(rows)} items: " + ", ".join(f"{k} {v}" for k, v in total.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
