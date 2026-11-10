"""v5.11: the repository matches the SBI Youth Ideathon video pitch (script v3).

Slide 5A: firmware builds for four ESP32 chips, checks the reference electrode before every test and says so at
boot. Slide 5B: the device simulator sends scans to the dashboard through the real pipeline; the dashboard can be
opened on one device. Slide 6: the last software items of the 60-point review (16 input ablation, 19 inputs
outside the training data) are closed."""
import os
import re
import sys

from app import aquanet_v3

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PLATFORM)
FRONT = os.path.join(PLATFORM, "frontend")


def _read(*parts):
    return open(os.path.join(*parts), encoding="utf-8").read()


def test_firmware_builds_for_four_chips_in_ci():
    ci = _read(ROOT, ".github", "workflows", "ci.yml")
    chips = set(re.findall(r"fqbn: (esp32:esp32:\w+)", ci))
    assert chips == {"esp32:esp32:esp32", "esp32:esp32:esp32s3", "esp32:esp32:esp32c3", "esp32:esp32:esp32c6"}, chips
    ino = _read(ROOT, "Firmware", "esp32_firmware", "esp32_firmware.ino")
    assert '#elif defined(CONFIG_IDF_TARGET_ESP32C6)' in ino and '"esp32c6"' in ino


def test_boot_self_test_mentions_the_reference_electrode_check():
    ino = _read(ROOT, "Firmware", "esp32_firmware", "esp32_firmware.ino")
    assert '[SELFTEST] Reference electrode: checked before every test' in ino
    assert "QC_REF_UNSTABLE" in ino


def test_simulator_uses_the_shared_pipeline_and_sends_simulated_scans():
    html = _read(FRONT, "mas-g1-display.html")
    assert '<script src="asv.js"></script>' in html
    assert "fetch('api/scans'" in html and "source_type: 'simulated'" in html
    assert "SIM-MASG1-01" in html and 'href="index.html?device=SIM-MASG1-01"' in html
    # the meter shows the same four outcomes as the server
    for word in ("SCREEN POSITIVE", "RETEST", "NOT DETECTED", "TEST FAILED"):
        assert word in html, word
    # imported files are never sent (they could be anyone's data)
    assert "if(data.asv) sendToServer(data);" in html


def test_dashboard_opens_on_a_device_from_the_address():
    js = _read(FRONT, "app.js")
    assert "function urlDevice()" in js and "loadLatestFromServer(urlDevice() || undefined)" in js
    # the device on screen is followed live whatever its source; only hardware raises a toast
    assert "if (state.reading && state.reading.device === d.device_code) loadLatestFromServer(d.device_code);" in js


def test_aquanet_flags_inputs_outside_its_training_data():
    normal = aquanet_v3.predict(0.005, 7.3, 450, 1.5, 25)
    assert normal["outside_training_range"] == []
    muddy = aquanet_v3.predict(0.005, 7.3, 450, 30.0, 25)       # turbidity 30 NTU: > 3 SD from the training data
    assert muddy["outside_training_range"] == ["turbidity"]
    assert muddy["predicted_class"] in ("Unsafe", "Hazardous")    # the fixed rules still decide
    js = _read(FRONT, "neural.js")
    assert "const OOD_Z = 3;" in js and "notMeasured, ood," in js


def test_input_ablation_in_the_research_pipeline():
    sys.path.insert(0, os.path.join(ROOT, "Analysis"))
    import aquanet_v2_pipeline as p
    X, y, cens, sites, _ = p.demo(n_sites=4, per_site=15)
    out = p.ablation(X, y, cens, sites)
    assert set(out) == {"waveform only", "context only", "all inputs"}
    assert all(v["n_evaluated"] > 0 and v["mae_ug_l"] >= 0 for v in out.values())
