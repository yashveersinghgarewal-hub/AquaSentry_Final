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
TYPES = open(os.path.join(FW_DIR, "esp32_firmware", "aquasentry_types.h"), encoding="utf-8").read()
GXX = shutil.which("g++")
GCC = shutil.which("gcc") or shutil.which("cc")

TARGETS = {
    "esp32": [],
    "esp32s3": ["-DCONFIG_IDF_TARGET_ESP32S3=1"],
    "esp32c3": ["-DCONFIG_IDF_TARGET_ESP32C3=1", "-DCONFIG_FREERTOS_UNICORE=1"],
    "esp32c6": ["-DCONFIG_IDF_TARGET_ESP32C6=1", "-DCONFIG_FREERTOS_UNICORE=1"],   # v5.11
}


@pytest.mark.skipif(GXX is None, reason="no C++ compiler")
@pytest.mark.parametrize("target", sorted(TARGETS))
def test_sketch_type_checks(target):
    cmd = [GXX, "-std=gnu++20", "-Wall", "-Wextra", "-Wformat=2", "-Wvolatile", "-Werror", "-fsyntax-only", "-x", "c++",
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
    c3 = SRC[SRC.index("#elif defined(CONFIG_IDF_TARGET_ESP32C3)"):SRC.index("#elif defined(CONFIG_IDF_TARGET_ESP32C6)")]
    c6 = SRC[SRC.index("#elif defined(CONFIG_IDF_TARGET_ESP32C6)"):SRC.index("#else   /* original ESP32")]
    esp = SRC[SRC.index("#else   /* original ESP32"):SRC.index("#define SENSOR_CORE 1")]
    rules = {
        # strapping pins, flash/PSRAM pins, ADC1 pins usable for the bubble sensor (ADC2 fails with Wi-Fi on)
        "esp32": ({0, 5, 12, 15}, set(range(6, 12)) | {16, 17}, set(range(32, 40))),
        "esp32s3": ({0, 3, 45, 46}, set(range(26, 38)), set(range(1, 11))),
        "esp32c3": ({2, 8, 9}, set(range(12, 18)), set(range(0, 5))),
        # ESP32-C6: strapping 4, 5, 8, 9, 15; SPI flash 24-30; USB 12-13 and UART0 16-17 kept free; ADC1 on GPIO0-6
        "esp32c6": ({4, 5, 8, 9, 15}, set(range(24, 31)) | {12, 13, 16, 17}, set(range(0, 7))),
    }
    for name, block in (("esp32", esp), ("esp32s3", s3), ("esp32c3", c3), ("esp32c6", c6)):
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


@pytest.mark.skipif(GXX is None, reason="no C++ compiler")
@pytest.mark.parametrize("target", sorted(TARGETS))
def test_sketch_type_checks_with_optional_features_on(target):
    """HTTPS-without-CA, battery monitor and low-power deep sleep, all switched on as build flags."""
    flags = ["-DLOW_POWER_MODE=1", "-DPIN_BATTERY_ADC=35", "-DALLOW_INSECURE_TLS=1", "-DPULL_OTA=1", "-DPIN_REAGENT_PUMP=4",
             "-DPIN_TEMP_NTC=1", "-DPIN_PH_ADC=2", "-DPIN_EC_ADC=3", "-DPIN_TURBIDITY_ADC=5", "-DCOPPER_CHECK=0"]
    cmd = [GXX, "-std=gnu++20", "-Wall", "-Wextra", "-Wformat=2", "-Wvolatile", "-Werror", "-fsyntax-only", "-x", "c++",
           *TARGETS[target], *flags, "-I", os.path.join(FW_DIR, "host_check"), "-I", os.path.join(FW_DIR, "esp32_firmware"), SKETCH]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-3000:]


@pytest.mark.skipif(GXX is None, reason="no C++ compiler")
def test_offline_record_v55_size_and_migration():
    """5.6 records grew from 52 to 60 bytes; buffered 5.5 readings are converted, not thrown away."""
    body = re.search(r"typedef struct \{\n(\s+float arsenic_mg_l;[\s\S]*?)\} sensor_reading_t;", TYPES).group(1)
    new_fields = ("arsenic_species", "cal_tag", "cu_peak_ua",
                  # v5.7 fields live in former padding, so the record stays 60 bytes (checked below)
                  "qc_result", "good_scans", "qc_reserved", "qc_bits")
    old = "\n".join(l for l in body.splitlines() if not any(f in l for f in new_fields)) + "\n"
    src = ("#include <cstdint>\ntypedef struct {\n%s} new_t;\ntypedef struct {\n%s} old_t;\n"
           "static_assert(sizeof(old_t) == 52, \"v5.5 record\");\nstatic_assert(sizeof(new_t) == 60, \"v5.6 record\");\n"
           "int main(){return 0;}\n") % (body, old)
    work = tempfile.mkdtemp()
    cpp = os.path.join(work, "size.cpp")
    open(cpp, "w").write(src)
    out = subprocess.run([GXX, "-std=c++17", "-fsyntax-only", cpp], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "#define RECORD_SIZE_V55 52" in TYPES
    mig = re.search(r"static bool obuf_migrate_from_v55\(\)[\s\S]*?\n\}", SRC).group(0)
    assert "memcpy(&r, buf, RECORD_SIZE_V55)" in mig and "rename(\"/offline.tmp\", OFFLINE_FILE)" in mig
    assert SRC.index("obuf_migrate_from_v55();") < SRC.index('File f = LittleFS.open(OFFLINE_FILE, "r");\n    bool valid')


def test_battery_curve_is_monotonic_and_https_is_checked():
    mv = [int(x) for x in re.search(r"MV\[12\]\s*=\s*\{([^}]*)\}", SRC).group(1).split(",")]
    pct = [int(x) for x in re.search(r"PCT\[12\]\s*=\s*\{([^}]*)\}", SRC).group(1).split(",")]
    assert mv == sorted(mv) and pct == sorted(pct) and pct[0] == 0 and pct[-1] == 100 and mv[-1] == 4200
    # https never silently skips certificate checks
    assert "setCACert(ROOT_CA_PEM)" in SRC and re.search(r"else if \(ALLOW_INSECURE_TLS\)\s*\{\s*secure\.setInsecure\(\)", SRC)
    assert re.search(r"#ifndef ALLOW_INSECURE_TLS\n#define ALLOW_INSECURE_TLS 0", SRC)
    # deep sleep keeps the stepper driver off
    sleep_fn = re.search(r"void enter_deep_sleep[\s\S]*?\n\}", SRC).group(0)
    assert "digitalWrite(PIN_STEPPER_ENABLE, HIGH)" in sleep_fn and "gpio_hold_en" in sleep_fn


def test_structs_are_declared_before_arduino_prototypes():
    """arduino-cli inserts function prototypes above the first function in the .ino, so every struct
    used in a function signature must come from a header (CI caught this on the real ESP32 core)."""
    assert not re.search(r"^typedef struct", SRC, re.M), "move structs to aquasentry_types.h"
    assert SRC.index('#include "aquasentry_types.h"') < SRC.index("static float arsenic_ug_from_peak")


_FUNC_DEF = re.compile(r"^((?:static\s+)?(?:unsigned\s+)?[A-Za-z_][\w:]*[\s\*&]+)([A-Za-z_]\w*)\s*\(([^;{}()]*)\)\s*\{", re.M)


def _with_arduino_prototypes(src: str) -> str:
    """Mimic arduino-cli's .ino preprocessing: a prototype for every top-level function, inserted just
    above the first function definition (defaults dropped, as in a declaration that precedes them)."""
    defs = [m for m in _FUNC_DEF.finditer(src) if m.group(2) not in ("if", "for", "while", "switch", "setup", "loop")]
    protos = []
    for m in defs:
        args = re.sub(r"\s*=\s*[^,]+", "", m.group(3))
        protos.append(f"{m.group(1).strip()} {m.group(2)}({args});")
    first = defs[0].start()
    return src[:first] + "\n".join(protos) + "\n#line %d\n" % (src[:first].count("\n") + 1) + src[first:]


@pytest.mark.skipif(GXX is None, reason="no C++ compiler")
def test_sketch_compiles_after_arduino_prototype_insertion():
    work = tempfile.mkdtemp()
    out_path = os.path.join(work, "esp32_firmware.cpp")
    open(out_path, "w", encoding="utf-8").write(_with_arduino_prototypes(SRC))
    cmd = [GXX, "-std=gnu++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-fsyntax-only", "-x", "c++",
           *TARGETS["esp32"], "-I", os.path.join(FW_DIR, "host_check"), "-I", os.path.join(FW_DIR, "esp32_firmware"), out_path]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-3000:]


def test_v56_firmware_features_are_wired():
    # quality fields reach the server
    for key in ("arsenic_species", "peak_current_ua", "cu_peak_ua", "calibration_ref"):
        assert f'\\"{key}\\"' in SRC, key
    # the reagent is dosed after the other sensors are read (it changes pH and conductivity)
    assert SRC.index("float ec = read_conductivity(temp);") < SRC.index("digitalWrite((uint8_t)reagent_pin, HIGH);")
    # copper extension never feeds the arsenic background fit
    asv = re.search(r"asv_result_t execute_asv_cycle\(\)[\s\S]*?\n\}", SRC).group(0)
    # background fit (2 loops) and, since v5.7, the arsenic peak search stop at the arsenic sweep
    assert asv.count("for (int i = 0; i < n_as; i++)") == 3
    # calibration from the server is sanity-checked and used for the arsenic value
    assert "sl > 0.05f && sl < 50.0f" in SRC and "arsenic_ug_from_peak(peak_current_ua) / 1000.0f" in SRC
    # server updates: never mid-test, and the new build confirms itself after a successful upload
    assert "if (is_measuring) return;" in SRC and "esp_ota_mark_app_valid_cancel_rollback();" in SRC
