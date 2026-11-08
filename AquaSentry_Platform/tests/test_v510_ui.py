"""v5.10 UI pass: one version label everywhere, practice controls apart from the real result, readable lab
summary and trend projections, and the demo programme naming the calibration behind every reading."""
import os
import re
from datetime import datetime, timedelta, timezone

from app import trends

FRONT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(name):
    return open(os.path.join(FRONT, name), encoding="utf-8").read()


def test_every_page_shows_the_same_release_as_the_changelog():
    labels = set()
    for name in os.listdir(FRONT):
        if name.endswith(".html"):
            labels |= set(re.findall(r"AquaSentry (v5\.\d+)", _read(name)))
    assert len(labels) == 1, labels
    # the service-worker cache is renamed with each release, or phones keep serving the old pages
    sw = re.search(r"const VERSION = 'aquasentry-(v5\.\d+)'", _read("sw.js")).group(1)
    assert {sw} == labels, (sw, labels)
    changelog = os.path.join(ROOT, "CHANGELOG.md")
    if os.path.exists(changelog):          # not in the Docker image
        latest = re.search(r"^## (v5\.\d+)\b", open(changelog, encoding="utf-8").read(), re.M).group(1)
        assert labels == {latest}, (labels, latest)


def test_practice_controls_are_grouped_and_not_the_primary_action():
    html = _read("index.html")
    group = re.search(r'<div class="practice" role="group" aria-labelledby="practiceLabel">(.*?)\n            </div>', html, re.S)
    assert group, "practice group missing"
    body = group.group(1)
    assert 'id="demoBtn"' in body and "data-quick=" in body
    demo_btn = re.search(r'<button[^>]*id="demoBtn"[^>]*>', html).group(0)
    assert "btn-primary" not in demo_btn


def test_lab_bias_is_described_in_words():
    js = _read("field-ui.js")
    assert "lab.bias.low" in js and "lab.bias.high" in js and "toFixed(1)" in js
    i18n = _read("i18n-v5.js")
    for key in ("lab.bias.low", "lab.bias.high", "lab.bias.none", "ov.practice", "ov.practice.note"):
        assert i18n.count(f"'{key}'") == 2, key        # English and Hindi


def test_public_page_puts_uncertainty_next_to_the_value():
    js = _read("device.js")
    assert "' ± ' + Math.round(r.uncertainty_ug_l)" in js
    assert "t('ov.unc'" not in js


def _series(slope_per_day, start=40.0, days=30):
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return [(t0 + timedelta(hours=6 * i), start + slope_per_day * i / 4) for i in range(days * 4)]


def test_slow_rise_is_not_projected_years_ahead():
    out = trends.analyse(_series(0.03), lod=20.0)
    assert out["direction"] == "rising"
    assert "within two years" in out["message"] and "days" not in out["message"]
    assert out["projection"]["days"] > trends.PROJECTION_HORIZON_DAYS     # the number is still in the API


def test_medium_rise_is_given_in_months_and_fast_rise_in_days():
    months = trends.analyse(_series(0.5), lod=20.0)["message"]
    assert "months" in months
    days = trends.analyse(_series(3.0), lod=20.0)["message"]
    assert re.search(r"in about \d+ days", days)
