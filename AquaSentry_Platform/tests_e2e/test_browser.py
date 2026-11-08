"""Browser tests (Playwright + Chromium): what CI could not see before - the pages themselves.

Run:  pip install playwright && python -m playwright install chromium
      python -m pytest -q tests_e2e          (from AquaSentry_Platform/)
Set AXE_PATH to axe.min.js (npm i axe-core) to include the WCAG 2.2 AA audit.
Map tiles are answered locally (a blank tile), so the tests never hit OpenStreetMap's servers.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import pytest

pw = pytest.importorskip("playwright.sync_api")
PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLANK_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6360f8cf"
                          "f00f0004ff01fe9e1f8f6c0000000049454e44ae426082")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _post(base, path, body, method="POST"):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"null")


@pytest.fixture(scope="module")
def server():
    work = tempfile.mkdtemp()
    db = os.path.join(work, "e2e.db")
    shutil.copy(os.path.join(PLATFORM, "aquasentry.db"), db)
    port = _free_port()
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + db, "AQUASENTRY_DATA_DIR": work}
    py = os.environ.get("AQS_PYTHON", sys.executable)
    proc = subprocess.Popen([py, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=PLATFORM, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    # realistic field data: a rising handpump with a lab result, a clean tubewell, a hazardous one
    now = time.time()
    for i, v in enumerate([22, 26, 30, 34, 38, 42, 46, 50]):
        t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - (7 - i) * 5 * 86400))
        _post(base, "/api/readings", {"device_code": "E2E-HP-01", "arsenic_ppb": v, "source_type": "hardware", "qc_status": "pass",
                                      "recorded_at": t, "arsenic_species": "as3_only", "peak_current_ua": 0.03})
    _post(base, "/api/readings", {"device_code": "E2E-TW-02", "arsenic_ppb": 8, "source_type": "hardware", "qc_status": "pass", "arsenic_species": "total"})
    _post(base, "/api/readings", {"device_code": "E2E-HP-03", "arsenic_ppb": 185, "source_type": "hardware", "qc_status": "pass"})
    for code, lat, lon in (("E2E-HP-01", 25.55, 84.66), ("E2E-TW-02", 22.95, 88.57), ("E2E-HP-03", 25.76, 84.47)):
        _post(base, f"/api/admin/devices/{code}/site", {"name": code + " pump", "village": "Simri", "latitude": lat,
                                                        "longitude": lon, "source_kind": "handpump"}, method="PUT")
    _post(base, "/api/lab-results", {"device_code": "E2E-HP-01", "arsenic_ug_l": 61, "as3_ug_l": 24, "lab_method": "ICP-MS"})
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _page(browser, width=1440, height=900, bypass_csp=False):
    ctx = browser.new_context(viewport={"width": width, "height": height}, bypass_csp=bypass_csp)
    ctx.route("**/tile.openstreetmap.org/**", lambda r: r.fulfill(status=200, content_type="image/png", body=BLANK_PNG))
    pg = ctx.new_page()
    problems = []
    pg.on("pageerror", lambda e: problems.append("page error: " + str(e)))
    pg.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    pg.add_init_script("document.addEventListener('securitypolicyviolation', e => console.error('CSP ' + e.violatedDirective + ' ' + e.sourceFile + ':' + e.lineNumber));")
    return ctx, pg, problems


def _real(problems):
    return [p for p in problems if "favicon" not in p and "GL Driver" not in p and "WebGL" not in p]


@pytest.mark.parametrize("width", [1440, 390])
def test_dashboard_has_no_errors_or_csp_violations_and_fits(server, browser, width):
    ctx, pg, problems = _page(browser, width)
    pg.goto(server + "/index.html")
    pg.wait_for_timeout(1500)
    pg.locator("#fleet").scroll_into_view_if_needed()
    pg.wait_for_timeout(2000)
    pg.locator("[data-device='E2E-HP-01']").first.click()
    pg.wait_for_timeout(1500)
    assert pg.locator(".leaflet-interactive").count() == 3, "one map marker per placed node"
    assert pg.locator("#devTools").is_visible() and "device.html?code=E2E-HP-01" in pg.locator("#devPage").get_attribute("href")
    assert "caught" in pg.locator("#labSummary").inner_text()
    assert pg.evaluate("document.documentElement.scrollWidth") <= width, "no sideways scrolling"
    assert not _real(problems), _real(problems)
    ctx.close()


def test_languages_load_on_demand(server, browser):
    ctx, pg, problems = _page(browser)
    pg.goto(server + "/index.html")
    pg.wait_for_timeout(1200)
    for lang, word in (("bn", "যন্ত্র"), ("as", "যন্ত্ৰ"), ("pa", "ਯੰਤਰ"), ("hi", "उपकरण")):
        pg.select_option("#langSelect", lang)
        pg.wait_for_timeout(500)
        assert pg.evaluate("document.documentElement.lang") == lang
        assert word in pg.locator("#fleetHeading").inner_text(), lang
    pg.reload()
    pg.wait_for_timeout(1200)
    assert pg.evaluate("document.documentElement.lang") == "hi", "the choice is remembered"
    assert not _real(problems), _real(problems)
    ctx.close()


def test_public_page_and_sticker(server, browser):
    ctx, pg, problems = _page(browser, 390, 844)
    pg.goto(server + "/device.html?code=E2E-HP-01")
    pg.wait_for_timeout(1200)
    assert pg.locator("#pubVerdict").inner_text() == "Not safe to drink"
    assert pg.locator("#pubQc li").count() >= 1 and "As(III)" in pg.locator("#pubQc").inner_text()
    assert "61" in pg.locator("#pubLab").inner_text() and pg.locator("#pubSteps").is_visible()
    pg.goto(server + "/device.html?code=E2E-HP-01&sticker=1")
    pg.wait_for_timeout(800)
    assert pg.locator("#stickerQr svg").count() == 1
    assert not _real(problems), _real(problems)
    ctx.close()


def test_3d_model_loads_only_when_scrolled_to(server, browser):
    ctx, pg, problems = _page(browser)
    pg.goto(server + "/index.html")
    pg.wait_for_timeout(1200)
    assert pg.evaluate("!window.AQUASENTRY_MODEL"), "the 180 KB model is not loaded up front"
    pg.locator("#viewer3d").scroll_into_view_if_needed()
    pg.wait_for_timeout(2000)
    assert pg.evaluate("!!window.AQUASENTRY_MODEL")
    ctx.close()


@pytest.mark.skipif(not os.environ.get("AXE_PATH"), reason="set AXE_PATH to axe.min.js for the accessibility audit")
@pytest.mark.parametrize("path", ["/index.html", "/device.html?code=E2E-HP-01"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_wcag_22_aa(server, browser, path, theme):
    ctx, pg, _ = _page(browser, bypass_csp=True)      # only so axe itself can be injected; CSP is tested above
    ctx.add_init_script(f"try{{localStorage.setItem('aquasentry.theme','{theme}')}}catch(e){{}}")
    pg.goto(server + path)
    pg.wait_for_timeout(1500)
    if path.startswith("/index"):
        pg.locator("#fleet").scroll_into_view_if_needed()
        pg.wait_for_timeout(1500)
    pg.add_script_tag(path=os.environ["AXE_PATH"])
    v = pg.evaluate("axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}})"
                    ".then(r => r.violations.map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).slice(0, 3).join(', ')))")
    assert v == [], v
    ctx.close()
