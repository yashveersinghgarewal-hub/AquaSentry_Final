#!/usr/bin/env python3
"""Install a trained AquaNet-V3 model everywhere it is used, in one step.

    python AquaSentry_Platform/scripts/install_aquanet_v3.py Neural_Network/v3_training/models/<model>.json

It writes:
  Neural_Network/aquanet_v3_weights.json           (Python / standalone toolkit)
  AquaSentry_Platform/app/aquanet_v3_weights.json  (server verdicts)
  Firmware/esp32_firmware/aquanet_v3.h, Firmware/esp32_firmware/aquanet_v3.c     (ESP32, generated C99 float32 code)
  AquaSentry_Platform/frontend/neural.js           (dashboard, between the __V3_MODEL__ markers)
Then run the tests:  python main.py --test
"""
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM = os.path.dirname(HERE)
ROOT = os.path.dirname(PLATFORM)


def main(path: str) -> None:
    d = json.load(open(path, encoding="utf-8"))
    assert d.get("model_name") == "AquaNet-V3" and len(d["topology"]) == 4, "expects an AquaNet-V3 weights file"
    for dst in (os.path.join(ROOT, "Neural_Network", "aquanet_v3_weights.json"),
                os.path.join(PLATFORM, "app", "aquanet_v3_weights.json")):
        shutil.copyfile(path, dst)
        print("[+] wrote", os.path.relpath(dst, ROOT))

    subprocess.run([sys.executable, os.path.join(HERE, "gen_c_v3.py"), path, os.path.join(ROOT, "Firmware", "esp32_firmware")], check=True)
    print("[+] wrote Firmware/esp32_firmware/aquanet_v3.h and Firmware/esp32_firmware/aquanet_v3.c")

    L = len(d["topology"]) - 1
    test = d.get("test", {})
    js_model = {
        "id": "v3", "sizes": d["topology"], "logAs": True,
        "mean": d["normalization_moments"]["mean"], "std": d["normalization_moments"]["std"],
        "W": [d["weights"][f"W{i + 1}"] for i in range(L)], "B": [d["weights"][f"B{i + 1}"] for i in range(L)],
        "info": {"testAccuracy": test.get("exact_accuracy_pct", "?"), "missReduction": test.get("missed_dangerous_reduction_pct", "?")},
    }
    js_path = os.path.join(PLATFORM, "frontend", "neural.js")
    s = open(js_path, encoding="utf-8").read()
    s, n = re.subn(r"/\*__V3_MODEL__\*/.*?/\*__END_V3__\*/",
                   lambda _: "/*__V3_MODEL__*/" + json.dumps(js_model, separators=(",", ":")) + "/*__END_V3__*/", s, flags=re.S)
    assert n == 1, "V3 markers not found in frontend/neural.js"
    open(js_path, "w", encoding="utf-8").write(s)
    print("[+] updated AquaSentry_Platform/frontend/neural.js")
    print("[*] Done. Now run: python main.py --test")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
