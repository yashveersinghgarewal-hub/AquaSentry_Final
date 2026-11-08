#!/usr/bin/env python3
"""
Project figures that are not data analysis (ISEF items 21, 47, 50, 58, 210, 236):

  gantt        Docs/planning/timeline.csv        -> gantt.svg            one-page plan of the research year (item 21)
  history      Docs/planning/design_history.csv  -> design_history.svg   v1 -> v5.9 design-history figure (item 50)
  landscape    Data/field/landscape_template.csv -> landscape.svg        cost vs LOD for each method, AquaSentry marked (item 47)
  cost         Data/field/bom_template.csv       -> cost.md + cost.json  cost per device and per test from the bill of materials (items 58, 210)
  qr           --url                             -> qr.svg / qr.pdf      printable QR code to the repository or data DOI (item 236)
  all          everything above

Every figure is drawn from a CSV the team edits; nothing is invented here. Rows with blank prices are listed as
"to fill" in the cost report, not guessed. Only numpy and (for the QR) reportlab are needed.

Usage:  python Analysis/project_figures.py all --out Analysis/out/project
        python Analysis/project_figures.py qr --url https://github.com/yashveersinghgarewal-hub/AquaSentry_Final --out Analysis/out/project
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import svg_plots as sp  # noqa: E402

TIMELINE = os.path.join(ROOT, "Docs", "planning", "timeline.csv")
HISTORY = os.path.join(ROOT, "Docs", "planning", "design_history.csv")
LANDSCAPE = os.path.join(ROOT, "Data", "field", "landscape_template.csv")
BOM = os.path.join(ROOT, "Data", "field", "bom_template.csv")
GROUP_COLOURS = {"Rules": sp.RED, "Prior art": sp.VIOLET, "Field study": sp.BLUE, "Sensor": sp.GREEN, "Milestone": sp.INK,
                 "Analysis": sp.AMBER, "Writing": sp.AMBER, "Interview": sp.VIOLET, "Logistics": sp.MUTED, "Pathway": sp.MUTED}


def _rows(path: str) -> List[Dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- gantt
def gantt(out_dir: str, path: str = TIMELINE) -> str:
    rows = _rows(path)
    for r in rows:
        r["s"] = dt.date.fromisoformat(r["start"])
        r["e"] = dt.date.fromisoformat(r["end"])
    rows.sort(key=lambda r: (r["s"], r["e"]))
    d0 = min(r["s"] for r in rows).replace(day=1)
    d1 = max(r["e"] for r in rows)
    span = (d1 - d0).days + 1
    W, left, top, rowh, right = 1000, 340, 76, 24, 20
    H = top + rowh * len(rows) + 40
    g = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' {sp.FONT}>",
         f"<rect width='{W}' height='{H}' fill='white'/>",
         f"<text x='{left}' y='24' font-size='16' font-weight='700' fill='{sp.INK}'>AquaSentry research year: plan</text>",
         f"<text x='{left}' y='40' font-size='11' fill='{sp.MUTED}'>from {path.replace(ROOT + os.sep, '')} - edit the CSV, rerun; dates are the team's to confirm</text>"]
    px = lambda d: left + (d - d0).days / span * (W - left - right)  # noqa: E731
    m = d0
    while m <= d1:
        x = px(m)
        g.append(f"<line x1='{x:.1f}' y1='{top - 8}' x2='{x:.1f}' y2='{H - 30}' stroke='{sp.GRID}'/>")
        g.append(f"<text x='{x + 3:.1f}' y='{top - 12}' font-size='10' fill='{sp.MUTED}'>{m.strftime('%b %y')}</text>")
        m = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    today = dt.date.today()
    if d0 <= today <= d1:
        g.append(f"<line x1='{px(today):.1f}' y1='{top - 8}' x2='{px(today):.1f}' y2='{H - 30}' stroke='{sp.RED}' stroke-dasharray='3 3'/>")
    for i, r in enumerate(rows):
        y = top + i * rowh
        col = GROUP_COLOURS.get(r.get("group", ""), sp.BLUE)
        g.append(f"<text x='{left - 8}' y='{y + 15}' font-size='11' text-anchor='end' fill='{sp.INK}'>{_esc(r['task'][:58])}</text>")
        if r["s"] == r["e"]:
            x = px(r["s"])
            g.append(f"<polygon points='{x:.1f},{y + 3} {x + 7:.1f},{y + 11} {x:.1f},{y + 19} {x - 7:.1f},{y + 11}' fill='{col}'/>")
        else:
            g.append(f"<rect x='{px(r['s']):.1f}' y='{y + 4}' width='{max(3, px(r['e']) - px(r['s'])):.1f}' height='14' rx='3' fill='{col}' fill-opacity='0.85'/>")
        g.append(f"<text x='{px(r['e']) + 6:.1f}' y='{y + 15}' font-size='9.5' fill='{sp.MUTED}'>{_esc(r.get('owner', ''))}</text>")
    g.append("</svg>")
    out = os.path.join(out_dir, "gantt.svg")
    sp.save(out, "\n".join(g))
    return out


# ---------------------------------------------------------------- design history
def history(out_dir: str, path: str = HISTORY) -> str:
    rows = _rows(path)
    W, left, rowh = 1000, 110, 78
    H = 70 + rowh * len(rows)
    g = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' {sp.FONT}>",
         f"<rect width='{W}' height='{H}' fill='white'/>",
         f"<text x='{left}' y='26' font-size='16' font-weight='700' fill='{sp.INK}'>Design history: what failed, what changed, what was measured</text>",
         f"<text x='{left}' y='42' font-size='11' fill='{sp.MUTED}'>from CHANGELOG.md and Docs/IMPROVEMENT_LOG.md (item 50)</text>",
         f"<line x1='{left - 40}' y1='60' x2='{left - 40}' y2='{H - 10}' stroke='{sp.GRID}' stroke-width='3'/>"]
    cols = [("what_failed_or_was_missing", "Failed / missing", sp.RED, left), ("what_changed", "Changed", sp.BLUE, left + 300),
            ("what_was_measured", "Measured", sp.GREEN, left + 600)]
    for i, r in enumerate(rows):
        y = 70 + i * rowh
        g.append(f"<circle cx='{left - 40}' cy='{y + 12}' r='6' fill='{sp.INK}'/>")
        g.append(f"<text x='{left - 52}' y='{y + 16}' font-size='11.5' font-weight='700' text-anchor='end' fill='{sp.INK}'>{_esc(r['version'])}</text>")
        g.append(f"<text x='{left - 52}' y='{y + 30}' font-size='9.5' text-anchor='end' fill='{sp.MUTED}'>{_esc(r['date'])}</text>")
        for key, head, col, x in cols:
            if i == 0:
                g.append(f"<text x='{x}' y='{y - 6}' font-size='10' font-weight='700' fill='{col}'>{head}</text>")
            text = r.get(key, "")
            lines, cur = [], ""
            for word in text.split():
                if len(cur) + len(word) + 1 > 52:
                    lines.append(cur)
                    cur = word
                else:
                    cur = (cur + " " + word).strip()
            lines.append(cur)
            for j, ln in enumerate(lines[:4]):
                g.append(f"<text x='{x}' y='{y + 12 + j * 13}' font-size='10' fill='{sp.INK}'>{_esc(ln)}</text>")
    g.append("</svg>")
    out = os.path.join(out_dir, "design_history.svg")
    sp.save(out, "\n".join(g))
    return out


# ---------------------------------------------------------------- landscape
def landscape(out_dir: str, path: str = LANDSCAPE) -> str:
    rows = _rows(path)
    pts = []
    missing = []
    for r in rows:
        try:
            lod = float(r["lod_ug_l"])
            cost = float(r["cost_per_test_inr"])
            pts.append((r["method"], lod, cost, r.get("field_capable", "")))
        except (ValueError, KeyError):
            missing.append(r.get("method", "?"))
    if not pts:
        ax = sp.Axes((0.1, 100), (1, 10000), "Method landscape: cost per test vs detection limit", "Detection limit (µg/L, log)", "Cost per test (₹, log)",
                     "No row of the landscape CSV has both a LOD and a cost yet - fill Data/field/landscape_template.csv")
    else:
        lods = [p[1] for p in pts]
        costs = [p[2] for p in pts]
        ax = sp.Axes((math.log10(min(lods) / 2), math.log10(max(lods) * 2)), (math.log10(max(1, min(costs) / 2)), math.log10(max(costs) * 2)),
                     "Method landscape: cost per test vs detection limit", "log10 detection limit (µg/L)", "log10 cost per test (₹)",
                     "Lower left is better; the 10 µg/L legal limit is the dashed line" + (f"; missing numbers: {', '.join(missing)}" if missing else ""))
        ax.vline(1.0, sp.RED, "5 4", "10 µg/L limit")
        for name, lod, cost, fc in pts:
            mine = "AquaSentry" in name
            ax.points([math.log10(lod)], [math.log10(cost)], sp.BLUE if mine else sp.MUTED, 7 if mine else 5, 0.95)
            ax.text(math.log10(lod) + 0.04, math.log10(cost), name[:34], sp.INK, 10)
    out = os.path.join(out_dir, "landscape.svg")
    sp.save(out, ax.render())
    return out


# ---------------------------------------------------------------- cost
def cost(out_dir: str, path: str = BOM) -> Dict:
    rows = _rows(path)
    device_total, per_test, to_fill, lines = 0.0, 0.0, [], []
    for r in rows:
        try:
            unit = float(r["unit_cost_inr"])
        except (ValueError, KeyError):
            to_fill.append(r["part"])
            continue
        consumable = (r.get("consumable_per_test") or "").lower() == "yes"
        if consumable:
            q = float(r.get("qty_per_test") or 1)
            per_test += unit * q
            lines.append((r["part"], "per test", q, unit, unit * q))
        else:
            q = float(r.get("qty_per_device") or 1)
            device_total += unit * q
            lines.append((r["part"], "per device", q, unit, unit * q))
    res = {"device_cost_inr": device_total, "consumables_per_test_inr": per_test, "parts_without_price": to_fill,
           "note": "Add electrode replacement amortised per test (price / tests per electrode, item 70) and the lab-confirmation share once measured."}
    with open(os.path.join(out_dir, "cost.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    L = ["# Cost model (items 58, 210)", "", f"Source: `{path.replace(ROOT + os.sep, '')}` - fill `unit_cost_inr` from receipts; nothing is estimated here.", "",
         "| part | basis | qty | unit ₹ | total ₹ |", "|---|---|---|---|---|"]
    for p, basis, q, u, t in lines:
        L += [f"| {p} | {basis} | {q:g} | {u:,.2f} | {t:,.2f} |"]
    L += ["", f"**Device: ₹ {device_total:,.2f}** (parts with a price) · **Consumables per test: ₹ {per_test:,.2f}**", ""]
    if to_fill:
        L += ["Parts still without a price (not counted): " + ", ".join(to_fill), ""]
    L += [res["note"], "", "Compare with: laboratory ICP-MS per sample (quote), field test kit per test (receipt) - put both in `Docs/CLAIMS_REGISTER.md` S5.", ""]
    with open(os.path.join(out_dir, "cost.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return res


# ---------------------------------------------------------------- qr
def qr(out_dir: str, url: str) -> List[str]:
    from reportlab.graphics import renderPDF, renderSVG
    from reportlab.graphics.barcode import qr as rlqr
    from reportlab.graphics.shapes import Drawing, String
    size = 360
    code = rlqr.QrCodeWidget(url, barLevel="M", barWidth=size, barHeight=size, y=30)
    d = Drawing(size, size + 30)
    d.add(code)
    d.add(String(size / 2, 10, url if len(url) < 60 else url[:57] + "...", textAnchor="middle", fontSize=9))
    svg_path, pdf_path = os.path.join(out_dir, "qr.svg"), os.path.join(out_dir, "qr.pdf")
    renderSVG.drawToFile(d, svg_path)
    renderPDF.drawToFile(d, pdf_path)
    return [svg_path, pdf_path]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gantt, design history, landscape, cost model and QR figures")
    ap.add_argument("what", choices=["gantt", "history", "landscape", "cost", "qr", "all"])
    ap.add_argument("--out", default=os.path.join(HERE, "out", "project"))
    ap.add_argument("--url", default="https://github.com/yashveersinghgarewal-hub/AquaSentry_Final")
    ap.add_argument("--timeline", default=TIMELINE)
    ap.add_argument("--history", default=HISTORY)
    ap.add_argument("--landscape", default=LANDSCAPE)
    ap.add_argument("--bom", default=BOM)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    made = []
    if a.what in ("gantt", "all"):
        made.append(gantt(a.out, a.timeline))
    if a.what in ("history", "all"):
        made.append(history(a.out, a.history))
    if a.what in ("landscape", "all"):
        made.append(landscape(a.out, a.landscape))
    if a.what in ("cost", "all"):
        c = cost(a.out, a.bom)
        made.append(os.path.join(a.out, "cost.md"))
        print(f"device ₹ {c['device_cost_inr']:,.0f}, per test ₹ {c['consumables_per_test_inr']:,.2f}, {len(c['parts_without_price'])} part(s) without a price")
    if a.what in ("qr", "all"):
        made += qr(a.out, a.url)
    print("\n".join(made))
    return 0


if __name__ == "__main__":
    sys.exit(main())
