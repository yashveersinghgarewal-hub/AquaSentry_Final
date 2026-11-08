"""v5.6 frontend: extra languages, strict style policy, offline cache list, vendored libraries."""
import json
import os
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.main import app

FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
NODE = shutil.which("node")
SAFETY_PREFIXES = ("verdict.", "class.", "alert.", "act.", "reason.", "qc.", "pub.", "warn.", "ov.")


def _tables():
    """{lang: {key: text}} for every language, loaded the way the browser does."""
    script = r"""
      global.window = {}; global.document = {addEventListener(){}, querySelectorAll(){return []}, documentElement:{}};
      global.localStorage = {getItem(){return null}, setItem(){}};
      const tables = {};
      const fs = require('fs');
      require(process.argv[1] + '/i18n.js');
      const realExtend = window.I18N.extend;
      window.I18N.extend = (l, d) => { tables[l] = Object.assign(tables[l] || {}, d); realExtend(l, d); };
      // the base tables live inside i18n.js; read them back through t() for every key we know
      for (const f of ['i18n-v5.js', 'i18n-bn.js', 'i18n-as.js', 'i18n-pa.js']) require(process.argv[1] + '/' + f);
      const src = fs.readFileSync(process.argv[1] + '/i18n.js', 'utf8');
      const en = {}, hi = {};
      const enBlock = src.slice(src.indexOf('en: {'), src.indexOf('\n    hi: {'));
      for (const m of enBlock.matchAll(/^\s*'([\w.-]+)':/gm)) en[m[1]] = window.I18N.t(m[1]);
      tables.en = Object.assign(en, tables.en);
      console.log(JSON.stringify(tables));
    """
    out = subprocess.run([NODE, "-e", script, FRONT], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_new_languages_cover_safety_text_with_matching_placeholders():
    t = _tables()
    en = t["en"]
    for lang in ("bn", "as", "pa"):
        d = t[lang]
        missing = [k for k in en if k.startswith(SAFETY_PREFIXES) and k not in d
                   and not k.startswith(("ov.source", "act.health"))]
        assert len(d) >= 200 and not missing, (lang, missing[:10])
        for k, v in d.items():
            ph_en = sorted(re.findall(r"\{\w+\}", en.get(k, v)))
            assert sorted(re.findall(r"\{\w+\}", v)) == ph_en, (lang, k)
        assert all("µg/L" in d[k] for k in ("pub.value", "pub.limit")), lang


def test_language_menu_lists_all_and_files_exist():
    html = open(os.path.join(FRONT, "index.html"), encoding="utf-8").read()
    for code in ("en", "hi", "bn", "as", "pa"):
        assert f'<option value="{code}"' in html
    for f in ("i18n-bn.js", "i18n-as.js", "i18n-pa.js"):
        assert os.path.exists(os.path.join(FRONT, f))


def test_dashboard_and_public_page_use_a_strict_style_policy():
    for page in ("index.html", "device.html"):
        assert 'style="' not in open(os.path.join(FRONT, page), encoding="utf-8").read(), page
    with TestClient(app) as c:
        for path in ("/index.html", "/device.html"):
            csp = c.get(path).headers["content-security-policy"]
            assert "style-src 'self';" in csp + ";" and "'unsafe-inline'" not in csp.split("style-src")[1].split(";")[0]
            assert "https://tile.openstreetmap.org" in csp
        # the older project pages keep their inline styles allowed
        assert "'unsafe-inline'" in c.get("/market-research.html").headers["content-security-policy"].split("style-src")[1].split(";")[0]


def test_service_worker_caches_only_files_that_exist_and_handles_push():
    sw = open(os.path.join(FRONT, "sw.js"), encoding="utf-8").read()
    files = re.findall(r"'([\w./-]+\.(?:html|css|js|svg|json|woff2))'", sw.split("const PRECACHE")[1].split("];")[0])
    assert "device.html" in files and "field-ui.js" in files and "device3d-data.js" not in files
    for f in files:
        assert os.path.exists(os.path.join(FRONT, f)), f
    assert "addEventListener('push'" in sw and "showNotification" in sw and "notificationclick" in sw


def test_vendored_libraries_are_local_with_licences():
    for f in ("vendor/leaflet.js", "vendor/leaflet.css", "vendor/qrcode.js", "vendor/LICENSE-leaflet.txt"):
        assert os.path.getsize(os.path.join(FRONT, f)) > 1000, f
    assert "cdn" not in open(os.path.join(FRONT, "field-ui.js"), encoding="utf-8").read().lower()
