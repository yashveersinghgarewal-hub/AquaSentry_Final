"""
AquaNet-V3 release checks.

Verifies:
- the model is small enough for an ESP32 (and the same weights are used by server, dashboard and firmware)
- the safety rules are never relaxed, and water that is truly Unsafe/Hazardous is never called Safe
- accuracy on a fixed exact-reading test set
- the generated C engine (Firmware/esp32_firmware/aquanet_v3.c, float32) gives the same answers as Python (skipped without gcc)
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile

import pytest

from app.aquanet_v3 import predict, load, CLASSES

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(PLATFORM)
APP_W = os.path.join(PLATFORM, "app", "aquanet_v3_weights.json")
NN_W = os.path.join(ROOT, "Neural_Network", "aquanet_v3_weights.json")
FW = os.path.join(ROOT, "Firmware", "esp32_firmware")


def rule_class(a, ph, ec, tu):
    c = 0
    if a > 0.010: c = max(c, 1)
    if a >= 0.020: c = max(c, 2)   # detected (>= LOD) = above IS 10500's 10 ug/L (no relaxation since 2015)
    if a > 0.150: c = max(c, 3)
    if ph < 6.5 or ph > 8.5: c = max(c, 1)
    if ph < 6.0 or ph > 9.0: c = max(c, 2)
    if tu > 5: c = max(c, 1)
    if tu > 10: c = max(c, 2)
    if ec > 1500: c = max(c, 1)
    if ec > 2000: c = max(c, 2)
    return c


def random_inputs(n, seed):
    rng = random.Random(seed)
    lims = {0: [0.010, 0.020, 0.150], 1: [6.0, 6.5, 8.5, 9.0], 2: [1500, 2000], 3: [5, 10]}
    rows = []
    for i in range(n):
        r = [math.exp(rng.uniform(math.log(0.0005), math.log(0.5))), rng.uniform(4.6, 10.4),
             math.exp(rng.uniform(math.log(60), math.log(4900))), math.exp(rng.uniform(math.log(0.05), math.log(90))),
             rng.uniform(6, 44)]
        if i % 2:
            f = rng.randrange(4)
            r[f] = rng.choice(lims[f]) * (1 + rng.uniform(-0.05, 0.05))
        rows.append(r)
    return rows


class TestAquaNetV3:
    def test_weights_identical_everywhere(self):
        assert json.load(open(APP_W)) == json.load(open(NN_W))
        js = open(os.path.join(PLATFORM, "frontend", "neural.js"), encoding="utf-8").read()
        m = re.search(r"/\*__V3_MODEL__\*/(.*?)/\*__END_V3__\*/", js, re.S)
        js_model = json.loads(m.group(1))
        d = json.load(open(APP_W))
        assert js_model["sizes"] == d["topology"]
        assert js_model["W"][0] == d["weights"]["W1"] and js_model["B"][-1] == d["weights"]["B3"]

    def test_small_enough_for_esp32(self):
        d = json.load(open(APP_W))
        sizes = d["topology"]
        params = sum(sizes[i] * sizes[i + 1] + sizes[i + 1] for i in range(len(sizes) - 1))
        assert sizes[0] == 5 and sizes[-1] == 4
        assert params <= 600, f"{params} parameters is more than the ESP32 budget used here"
        assert os.path.exists(os.path.join(FW, "aquanet_v3.c")) and os.path.exists(os.path.join(FW, "aquanet_v3.h"))
        assert "-".join(map(str, sizes)) in open(os.path.join(FW, "aquanet_v3.h")).read()

    def test_probabilities_sum_to_one(self):
        r = predict(0.03, 7.2, 400, 2, 24)
        assert abs(sum(r["probabilities_pct"].values()) - 100.0) < 0.05

    def test_rules_never_relaxed_and_danger_never_safe(self):
        for a, ph, ec, tu, te in random_inputs(4000, 11):
            r = predict(a, ph, ec, tu, te)
            final = CLASSES.index(r["predicted_class"])
            truth = rule_class(a, ph, ec, tu)
            assert final >= truth, (a, ph, ec, tu, r)
            if truth >= 2:
                assert r["predicted_class"] != "Safe"

    def test_network_accuracy_on_exact_readings(self):
        rows = random_inputs(4000, 23)
        correct = sum(CLASSES.index(predict(*r)["network_vote"]) == rule_class(*r[:4]) for r in rows)
        assert correct / len(rows) >= 0.93   # noise-aware model is deliberately cautious near limits

    def test_out_of_range_input_is_never_safe(self):
        for bad in ([0.005, 7.2, 400, 2, 60], [0.005, 12.0, 400, 2, 24], [float("nan"), 7.2, 400, 2, 24]):
            assert predict(*bad)["predicted_class"] in ("Unsafe", "Hazardous")

    @pytest.mark.skipif(shutil.which("gcc") is None and shutil.which("cc") is None, reason="no C compiler")
    def test_c_engine_matches_python(self):
        cc = shutil.which("gcc") or shutil.which("cc")
        work = tempfile.mkdtemp()
        harness = os.path.join(work, "h.c")
        open(harness, "w").write(r'''
#include <stdio.h>
#include "aquanet_v3.h"
int main(void){ double a,b,c,d,e; while(scanf("%lf %lf %lf %lf %lf",&a,&b,&c,&d,&e)==5){
 aquanet_result_t r=aquanet_v3_predict((float)a,(float)b,(float)c,(float)d,(float)e);
 printf("%d %d\n",(int)r.raw_model_class,(int)r.predicted_class);} return 0; }''')
        exe = os.path.join(work, "h")
        subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-I", FW, harness,
                        os.path.join(FW, "aquanet_v3.c"), os.path.join(FW, "aquanet_v1.c"), "-lm", "-o", exe], check=True)
        rows = random_inputs(3000, 37)
        out = subprocess.run([exe], input="\n".join(" ".join(repr(v) for v in r) for r in rows), capture_output=True,
                             text=True, check=True).stdout.split()
        for i, r in enumerate(rows):
            p = predict(*r)
            assert CLASSES[int(out[2 * i])] == p["network_vote"], r
            assert CLASSES[int(out[2 * i + 1])] == p["predicted_class"], r


class TestAdaptiveRescan:
    """The ESP32 re-scans readings close to a limit. The firmware rule must match the one the network was
    trained and tested with (Neural_Network/v3_training/train_v3.py, ADAPTIVE=1)."""

    INO = os.path.join(FW, "esp32_firmware.ino")

    def _defines(self):
        src = open(self.INO, encoding="utf-8").read()
        get = lambda name: float(re.search(rf"#define\s+{name}\s+([0-9.]+)", src).group(1))
        return src, get("SCANS_PER_READING"), get("MAX_SCANS_PER_READING"), get("RESCAN_Z")

    def test_firmware_settings_match_training(self):
        _, per, mx, z = self._defines()
        train = open(os.path.join(ROOT, "Neural_Network", "v3_training", "train_v3.py"), encoding="utf-8").read()
        assert (per, mx) == (3, 9)                       # 3 scans, then up to two more rounds of 3
        assert "for k in (6, 9)" in train and "scans[:, :3]" in train
        assert float(re.search(r"ADAPT_Z', ([0-9.]+)\)", train).group(1)) == z

    @pytest.mark.skipif(shutil.which("gcc") is None and shutil.which("cc") is None, reason="no C compiler")
    def test_firmware_near_limit_rule_matches_python(self):
        src, _, _, z = self._defines()
        fn = re.search(r"static bool arsenic_near_limit\(.*?\n}\n", src, re.S).group(0)
        work = tempfile.mkdtemp()
        c = os.path.join(work, "n.c")
        open(c, "w").write("#include <stdio.h>\n#include <stdbool.h>\n#include <math.h>\n"
                           f"#define RESCAN_Z {z}f\n{fn}\n"
                           "int main(void){float u; int n; while(scanf(\"%f %d\",&u,&n)==2) printf(\"%d\\n\",(int)arsenic_near_limit(u,n)); return 0;}\n")
        exe = os.path.join(work, "n")
        cc = shutil.which("gcc") or shutil.which("cc")
        subprocess.run([cc, "-std=c99", "-Wall", "-Werror", c, "-lm", "-o", exe], check=True)
        rng = random.Random(5)
        cases = [(round(rng.uniform(0, 250), 3), rng.choice([3, 6, 9])) for _ in range(3000)]
        out = subprocess.run([exe], input="\n".join(f"{u} {n}" for u, n in cases), capture_output=True,
                             text=True, check=True).stdout.split()
        for (u, n), got in zip(cases, out):
            sd = (5.0 if u < 50 else 7.5 if u <= 150 else 15.0) / math.sqrt(n)
            want = any(abs(u - L) < z * sd for L in (10.0, 20.0, 150.0))
            if abs(min(abs(u - L) for L in (10.0, 20.0, 150.0)) - z * sd) > 1e-3:   # skip float ties
                assert int(got) == int(want), (u, n)
