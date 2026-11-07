"""
ESP32 firmware checks that run on a normal PC (no ESP32 toolchain needed).

- Type-checks esp32_firmware.ino against Firmware/host_check/ (stand-ins with the Arduino-ESP32
  core's function signatures) for ESP32, ESP32-S3 and ESP32-C3 pin/core profiles, with warnings as errors.
- Compiles the AquaNet C engines as C and calls them from C++, which fails if a header loses its
  extern "C" guard (the Arduino IDE builds .ino files as C++ and .c files as C).
- Checks the settings that the real chips care about: NVS key/namespace length (15 chars max),
  measurement task core on single-core chips, pins that are strapping / flash / input-only.
The real compile with Espressif's core runs in GitHub Actions (.github/workflows/ci.yml, job "firmware").
"""
import os
import re
import shutil
import subprocess
import tempfile

import pytest

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PLATFORM)
FW_DIR = os.path.join(ROOT, "Firmware")
SKETCH = os.path.join(FW_DIR, "esp32_firmware", "esp32_firmware.ino")
SRC = open(SKETCH, encoding="utf-8").read()
GXX = shutil.which("g++")
GCC = shutil.which("gcc") or shutil.which("cc")

TARGETS = {
    "esp32": [],
    "esp32s3": ["-DCONFIG_IDF_TARGET_ESP32S3=1"],
    "esp32c3": ["-DCONFIG_IDF_TARGET_ESP32C3=1", "-DCONFIG_FREERTOS_UNICORE=1"],
}


@pytest.mark.skipif(GXX is None, reason="no C++ compiler")
@pytest.mark.parametrize("target", sorted(TARGETS))
def test_sketch_type_checks(target):
    cmd = [GXX, "-std=gnu++17", "-Wall", "-Wextra", "-Wformat=2", "-Werror", "-fsyntax-only", "-x", "c++",
           *TARGETS[target], "-I", os.path.join(FW_DIR, "host_check"), "-I", os.path.join(FW_DIR, "esp32_firmware"), SKETCH]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-3000:]


@pytest.mark.skipif(GXX is None or GCC is None, reason="no C/C++ compiler")
def test_c_engines_link_from_cpp():
    work = tempfile.mkdtemp()
    inc = os.path.join(FW_DIR, "esp32_firmware")
    objs = []
    for name in ("aquanet_v3.c", "aquanet_v1.c"):
        o = os.path.join(work, name + ".o")
        subprocess.run([GCC, "-std=c99", "-Wall", "-Wextra", "-Werror", "-c", os.path.join(inc, name), "-I", inc, "-o", o], check=True)
        objs.append(o)
    cpp = os.path.join(work, "main.cpp")
    open(cpp, "w").write('#include "aquanet_v3.h"\nint main(){ aquanet_result_t a = aquanet_v3_predict(0.03f, 7.2f, 400, 2, 24);'
                         ' aquanet_result_t b = aquanet_v3_predict(0.004f, 7.2f, 400, 2, 24);'
                         ' return (a.predicted_class == AQUANET_CLASS_UNSAFE && b.predicted_class != AQUANET_CLASS_UNSAFE) ? 0 : 1; }\n')
    exe = os.path.join(work, "main")
    subprocess.run([GXX, "-std=c++17", "-I", inc, cpp, *objs, "-lm", "-o", exe], check=True)
    assert subprocess.run([exe]).returncode == 0


def test_nvs_names_fit():
    """NVS namespace and key names are limited to 15 characters on the ESP32."""
    names = re.findall(r'\.begin\("([^"]+)"', SRC) + re.findall(r'\.(?:get|put)(?:UInt|String|Bytes)\("([^"]+)"', SRC)
    assert names, "no NVS names found"
    assert all(len(n) <= 15 for n in names), [n for n in names if len(n) > 15]


def test_offline_buffer_not_in_nvs():
    """Large offline buffers do not fit the shared default NVS partition; they live on LittleFS."""
    assert "LittleFS.begin(" in SRC and "putBytes(" not in SRC


def test_single_core_chips_supported():
    assert re.search(r"CONFIG_FREERTOS_UNICORE[\s\S]{0,80}#define SENSOR_CORE 0", SRC)
    assert "xTaskCreatePinnedToCore(TaskSensors" in SRC and "SENSOR_CORE)" in SRC


def _pins(block):
    return {k: int(v) for k, v in re.findall(r"#define (I2C_SDA_PIN|I2C_SCL_PIN|PIN_\w+)\s+(\d+)", block)}


def test_pins_are_safe_on_each_chip():
    s3 = SRC[SRC.index("CONFIG_IDF_TARGET_ESP32S3"):SRC.index("#elif defined(CONFIG_IDF_TARGET_ESP32C3)")]
    c3 = SRC[SRC.index("#elif defined(CONFIG_IDF_TARGET_ESP32C3)"):SRC.index("#else   /* original ESP32")]
    esp = SRC[SRC.index("#else   /* original ESP32"):SRC.index("#define SENSOR_CORE 1")]
    rules = {
        # strapping pins, flash/PSRAM pins, ADC1 pins usable for the bubble sensor (ADC2 fails with Wi-Fi on)
        "esp32": ({0, 5, 12, 15}, set(range(6, 12)) | {16, 17}, set(range(32, 40))),
        "esp32s3": ({0, 3, 45, 46}, set(range(26, 38)), set(range(1, 11))),
        "esp32c3": ({2, 8, 9}, set(range(12, 18)), set(range(0, 5))),
    }
    for name, block in (("esp32", esp), ("esp32s3", s3), ("esp32c3", c3)):
        pins = _pins(block)
        strap, flash, adc1 = rules[name]
        assert len(pins) == 7, (name, pins)
        assert not (set(pins.values()) & flash), (name, "flash pin used")
        risky = {k: v for k, v in pins.items() if v in strap and k != "PIN_STATUS_LED"}
        assert not risky, (name, risky)
        assert pins["PIN_BUBBLE_SENSE"] in adc1, (name, "bubble sensor must be on ADC1")
        assert len(set(pins.values())) == len(pins), (name, "pin used twice")
        if name == "esp32":
            outs = [v for k, v in pins.items() if k != "PIN_BUBBLE_SENSE"]
            assert all(v < 34 for v in outs), "GPIO34-39 are input-only on the ESP32"
