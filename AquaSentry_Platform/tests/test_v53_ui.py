"""v5.3 dashboard checks (run with Node when available).

- every data-i18n key on the dashboard has an English and a Hindi string
- the colour chart puts the verdict edges (10, 20, 150 µg/L) on swatch centres and the bands agree
- dashboard scripts parse
"""
import json
import os
import re
import shutil
import subprocess

import pytest

FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
NODE = shutil.which("node")


def _keys(html):
    return set(re.findall(r'data-i18n(?:-html|-aria|-placeholder)?="([^"]+)"', html))


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_dashboard_strings_exist_in_english_and_hindi():
    html = open(os.path.join(FRONT, "index.html"), encoding="utf-8").read()
    keys = sorted(_keys(html) | {"chart.you", "verdict.Clear.title", "verdict.Clear.action", "class.Clear",
                                 "alert.Clear.t", "alert.Clear.d", "fleet.all", "fleet.demo", "fleet.count", "fleet.count.one",
                                 "fleet.st.online", "fleet.st.late", "fleet.st.offline", "fleet.st.demo", "hist.empty", "hist.desc", "hist.local"})
    script = (
        "global.window = {}; global.localStorage = {getItem(){return null}, setItem(){}};"
        "global.document = {documentElement: {lang: 'en', setAttribute(){}}, querySelectorAll(){return []}, addEventListener(){}, dispatchEvent(){}, readyState: 'loading'};"
        "global.CustomEvent = function(){}; global.navigator = {language: 'en'};"
        f"require({json.dumps(os.path.join(FRONT, 'i18n.js'))}); require({json.dumps(os.path.join(FRONT, 'i18n-v5.js'))});"
        f"const keys = {json.dumps(keys)}; const out = {{}};"
        "for (const lang of ['en', 'hi']) { window.I18N.setLang(lang); out[lang] = keys.filter(k => { const v = window.I18N.t(k); return !v || v === k; }); }"
        "console.log(JSON.stringify(out));"
    )
    res = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-2000:]
    missing = json.loads(res.stdout.strip().splitlines()[-1])
    # some data-i18n elements are filled in by script with HTML content; allow keys whose text is intentionally empty
    assert not missing["en"], f"missing English strings: {missing['en']}"
    assert not missing["hi"], f"missing Hindi strings: {missing['hi']}"


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_chart_edges_sit_on_swatch_centres():
    src = open(os.path.join(FRONT, "app.js"), encoding="utf-8").read()
    kit = re.search(r"const KIT = (\[[^\]]+\]);", src).group(1)
    fn = re.search(r"  function kitIndex\(u\) \{.*?\n  \}\n", src, re.S).group(0)
    pct = re.search(r"  function stripPercent\(u\) \{.*?\}\n", src).group(0)
    script = f"const KIT = {kit};\n{fn}{pct}console.log(JSON.stringify([0, 10, 20, 150, 300, 9999].map(stripPercent)));"
    out = json.loads(subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True).stdout)
    centre = lambda i: (i + 0.5) / 7 * 100
    assert out[:5] == pytest.approx([centre(0), centre(1), centre(2), centre(5), centre(6)])
    assert out[5] == pytest.approx(centre(6))
    css = open(os.path.join(FRONT, "field.css"), encoding="utf-8").read()
    b1, b2, b3 = (float(x) for x in re.search(r"--b1, ([\d.]+)%.*?--b2, ([\d.]+)%.*?--b3, ([\d.]+)%", css, re.S).groups())
    assert b1 == pytest.approx(centre(1), abs=0.05)              # "within limit" ends at 10 µg/L
    assert b1 + b2 == pytest.approx(centre(2), abs=0.05)         # "lab test" ends at 20 µg/L (sensor LOD)
    assert b1 + b2 + b3 == pytest.approx(centre(5), abs=0.05)    # "do not drink" ends at 150 µg/L


@pytest.mark.skipif(NODE is None, reason="node not installed")
@pytest.mark.parametrize("name", sorted(f for f in os.listdir(FRONT) if f.endswith(".js")))
def test_scripts_parse(name):
    res = subprocess.run([NODE, "--check", os.path.join(FRONT, name)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_every_page_uses_the_field_layer_without_the_motion_layer():
    for page in ("index.html", "market-research.html", "sales-expansion.html", "device-simulator.html"):
        html = open(os.path.join(FRONT, page), encoding="utf-8").read()
        assert 'href="field.css"' in html, page
        assert 'src="motion.js"' not in html, page
