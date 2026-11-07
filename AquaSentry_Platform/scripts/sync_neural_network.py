#!/usr/bin/env python3
"""Keep the copies of AquaNet-V1 in step across the AquaSentry_Universal package.

Canonical (edit these):
    AquaSentry_Platform/app/neural_classifier.py   -> copied to Neural_Network/aquanet_classifier.py
    AquaSentry_Platform/app/asv_extractor.py       -> copied to Neural_Network/asv_extractor.py
    Neural_Network/aquanet_v1.c / aquanet_v1.h     -> copied to Firmware/esp32_firmware/ (Arduino needs them next to the .ino)
Also writes aquanet_v1_weights.json to Neural_Network/ and AquaSentry_Platform/app/.

Deliberately NOT synced (they are different files on purpose):
    - tests: Neural_Network/test_aquanet_parity.py (22 tests) and tests/test_neural_parity.py (18 tests)
    - JavaScript: frontend/neural.js (dashboard, V1 + V2) and Neural_Network/aquanet_neural.js (standalone V1)

Usage:  python scripts/sync_neural_network.py
"""

import json
import os
import shutil
import sys
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SCRIPTS_DIR)                     # AquaSentry_Platform
PROJECT_ROOT = os.path.dirname(APP_DIR)                    # AquaSentry_Universal
NN_DIR = os.path.join(PROJECT_ROOT, "Neural_Network")
FW_DIR = os.path.join(PROJECT_ROOT, "Firmware", "esp32_firmware")


def copy(src: str, dst: str) -> None:
    if not os.path.exists(src):
        print(f"[!] Missing, skipped: {os.path.relpath(src, PROJECT_ROOT)}")
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"[+] {os.path.relpath(src, PROJECT_ROOT)} -> {os.path.relpath(dst, PROJECT_ROOT)}")


def sync() -> bool:
    print("=" * 70)
    print("AquaNet-V1 synchronisation")
    print("=" * 70)
    sys.path.insert(0, APP_DIR)
    try:
        from app import neural_classifier as nc
    except Exception as e:  # pragma: no cover
        print(f"[!] Could not import app.neural_classifier: {e}")
        return False

    weights = {
        "model_name": "AquaNet-V1",
        "version": "1.3.0",
        "topology": {
            "input_features": 5, "hidden_layer_1": 8, "hidden_layer_2": 6, "output_classes": 4,
            "total_nodes": nc.NODES_COUNT, "total_synapses": nc.SYNAPSES_COUNT, "classes": nc.CLASSES,
        },
        "normalization_moments": {"mean": nc.INPUT_MEAN, "std": nc.INPUT_STD},
        "geochemical_bounds": nc.FEATURE_BOUNDS,
        "potability_limits": nc.POTABILITY_LIMITS,
        "weights": {"W1": nc.W1, "B1": nc.B1, "W2": nc.W2, "B2": nc.B2, "W3": nc.W3, "B3": nc.B3},
        "metadata": {
            "how_made": "Hand-constructed from the WHO/BIS arsenic thresholds (10, 50, 150 ug/L); not trained on data",
            "inputs_used": "arsenic only (20 of 112 weights non-zero); pH, conductivity, turbidity handled by safety rules",
            "trained_successor": "aquanet_v2_weights.json (AquaNet-V2)",
            "last_synced_at": datetime.now().isoformat(),
        },
    }
    for d in (NN_DIR, os.path.join(APP_DIR, "app")):
        path = os.path.join(d, "aquanet_v1_weights.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(weights, f, indent=2)
        print(f"[+] Wrote {os.path.relpath(path, PROJECT_ROOT)}")

    copy(os.path.join(APP_DIR, "app", "neural_classifier.py"), os.path.join(NN_DIR, "aquanet_classifier.py"))
    copy(os.path.join(APP_DIR, "app", "asv_extractor.py"), os.path.join(NN_DIR, "asv_extractor.py"))
    for c_file in ("aquanet_v1.h", "aquanet_v1.c"):
        copy(os.path.join(NN_DIR, c_file), os.path.join(FW_DIR, c_file))
    print("[*] Done. Tests and JavaScript files are intentionally left alone (see the top of this file).")
    return True


if __name__ == "__main__":
    sys.exit(0 if sync() else 1)
