"""The ISEF roadmap status register must cover every one of the 267 items, use only the defined statuses, and
point at files that exist. Rendering it must be reproducible (the committed Markdown matches the CSV)."""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(ROOT, "Docs", "planning", "isef_roadmap_status.csv")
MD = os.path.join(ROOT, "Docs", "ISEF_ROADMAP_STATUS.md")
REMAINING = os.path.join(ROOT, "Docs", "REMAINING_WORK.md")
STATUSES = {"Done", "Tooling ready", "Partial", "Open", "Team", "Lab", "Field"}
OWNERS = {"team", "software", "lab", "field", "firmware", "external"}
PATH_RE = re.compile(r"(?<![\w/])((?:Docs|Analysis|Data|Firmware|AquaSentry_Platform|scripts|app|tests|bridge|frontend|models_3d)/[\w./-]+)")


def _rows():
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_every_roadmap_item_is_registered_once():
    rows = _rows()
    items = sorted(int(r["item"]) for r in rows)
    assert items == list(range(1, 268))
    assert all(r["status"] in STATUSES for r in rows), {r["item"]: r["status"] for r in rows if r["status"] not in STATUSES}
    assert all(r["owner"] in OWNERS for r in rows)
    assert all(r["where_or_next_step"].strip() for r in rows)
    # the roadmap's "first 30 days" items all have a next step that is not just "Not software."
    for n in (1, 2, 4, 6, 7, 12, 24, 36, 64, 65, 66, 67, 88, 108, 109):
        r = next(x for x in rows if int(x["item"]) == n)
        assert len(r["where_or_next_step"]) > 20, n


def test_register_paths_exist():
    missing = []
    for r in _rows():
        for path in PATH_RE.findall(r["where_or_next_step"]):
            p = path.rstrip(".,;:)")
            candidates = [os.path.join(ROOT, p), os.path.join(ROOT, "AquaSentry_Platform", p)]
            if p.startswith("Analysis/out") or p.endswith("/"):
                continue
            if not any(os.path.exists(c) for c in candidates):
                missing.append((r["item"], p))
    assert not missing, missing


def test_rendered_markdown_matches_csv(tmp_path):
    before = open(MD, encoding="utf-8").read()
    before_left = open(REMAINING, encoding="utf-8").read()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "Analysis", "roadmap_status.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    after = open(MD, encoding="utf-8").read()
    assert before == after, "Docs/ISEF_ROADMAP_STATUS.md is stale: run Analysis/roadmap_status.py and commit"
    assert "267" in after and after.count("| **Done** | software implemented") == 1
    assert before_left == open(REMAINING, encoding="utf-8").read(), "Docs/REMAINING_WORK.md is stale: run Analysis/roadmap_status.py"


def test_csv_rows_have_no_unquoted_commas():
    # a comma outside quotes splits the next-step text into an extra column that the renderer silently drops (v5.10 fix)
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        bad = [r["item"] for r in csv.DictReader(f) if None in r]
    assert bad == []


def test_remaining_work_lists_every_open_item_once():
    text = open(REMAINING, encoding="utf-8").read()
    open_items = [int(r["item"]) for r in _rows() if r["status"] != "Done"]
    listed = [int(n) for n in re.findall(r"^- \[ \] \*\*(\d+)\*\*", text, flags=re.M)]
    assert sorted(listed) == sorted(open_items)


def test_readme_counts_match_the_register():
    from collections import Counter
    c = Counter(r["status"] for r in _rows())
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert f"{c['Done']} done in software, {c['Tooling ready']} with the software ready" in readme
