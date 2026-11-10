"""
AquaNet-V3 inference (pure Python, no NumPy). Identical maths and safety rules to the C engine
Firmware/esp32_firmware/aquanet_v3.c that runs on the ESP32, and to the dashboard (frontend/neural.js).

V3 = trained from random weights on all five readings, with arsenic fed in as log10(As + 0.001)
so the 10 / 20 / 150 ug/L rule edges are easy to separate. Training code: Neural_Network/v3_training/.

    from aquanet_v3 import predict
    predict(arsenic_mg_l=0.005, ph=5.8, conductivity_us_cm=400, turbidity_ntu=2, temperature_c=24)

After the network votes, fixed WHO / IS 10500 (as amended 2015: 10 ug/L, no relaxation) rules run; a rule can only make the verdict stricter.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from typing import Dict, List, Optional

CLASSES = ["Safe", "Caution", "Unsafe", "Hazardous"]
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WEIGHTS = "aquanet_v3_weights.json"
BOUNDS = [(0.0, 2.0), (4.5, 10.5), (50.0, 5000.0), (0.0, 100.0), (5.0, 45.0)]


@lru_cache(maxsize=8)
def load(weights_path: str) -> Dict:
    with open(weights_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve(weights_path: Optional[str]) -> str:
    path = weights_path or DEFAULT_WEIGHTS
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def network(raw: List[Optional[float]], model: Dict) -> Dict[str, List[float]]:
    """Forward pass. Returns every layer so the dashboard / tests can inspect activations.
    A None input means "not measured": it enters the network at its training mean (z = 0, a neutral value)."""
    mean = model["normalization_moments"]["mean"]
    std = model["normalization_moments"]["std"]
    missing = [v is None for v in raw]
    vals = [0.0 if v is None else (v if math.isfinite(v) else 0.0) for v in raw]
    if model.get("input_transform", {}).get("arsenic", "").startswith("log10"):
        vals[0] = math.log10(max(vals[0], 0.0) + 0.001)
    h = [0.0 if miss else (v - m) / s for v, m, s, miss in zip(vals, mean, std, missing)]
    layers = [h]
    n = len(model["topology"]) - 1
    for i in range(n):
        W = model["weights"][f"W{i + 1}"]
        B = model["weights"][f"B{i + 1}"]
        z = [sum(w * x for w, x in zip(row, h)) + b for row, b in zip(W, B)]
        h = [max(0.0, v) for v in z] if i < n - 1 else z
        layers.append(h)
    mx = max(h)
    ex = [math.exp(v - mx) for v in h]
    tot = sum(ex)
    return {"layers": layers, "logits": h, "probs": [e / tot for e in ex]}


def apply_rules(vote: str, raw: List[Optional[float]], entropy: float):
    """The fixed safety rules (same order and thresholds as the C engine). Returns (final, reasons).
    A None reading was not measured: its rule is skipped (and reported), never assumed to pass."""
    arsenic, ph, ec, turb, _ = raw
    final = vote
    reasons: List[str] = []

    def at_least(c: str, why: str):
        nonlocal final
        if CLASSES.index(c) > CLASSES.index(final):
            final = c
            reasons.append(why)

    oob = any(v is not None and (not math.isfinite(v) or not (lo <= v <= hi)) for v, (lo, hi) in zip(raw, BOUNDS))
    if oob:
        at_least("Unsafe", "SAFETY_OVERRIDE_OUT_OF_BOUNDS")
    if arsenic > 0.150:
        at_least("Hazardous", "SAFETY_OVERRIDE_ARSENIC_ACUTE_HAZARD")
    elif arsenic >= 0.020:
        # Detected (>= the 20 ug/L sensor LOD) means above the 10 ug/L IS 10500 / WHO limit.
        at_least("Unsafe", "SAFETY_OVERRIDE_ARSENIC_EXCEEDS_BIS")
    elif arsenic > 0.010:
        # Above 10 ug/L but below the LOD: not confirmed, so Caution + lab test.
        at_least("Caution", "POTABILITY_ADVISORY_ARSENIC_ABOVE_WHO")
    if not oob:
        if ph is not None:
            if ph < 6.0 or ph > 9.0:
                at_least("Unsafe", "SAFETY_OVERRIDE_SEVERE_PH_VIOLATION")
            elif ph < 6.5 or ph > 8.5:
                at_least("Caution", "POTABILITY_ADVISORY_PH_EXCEEDANCE")
        if turb is not None:
            if turb > 10.0:
                at_least("Unsafe", "SAFETY_OVERRIDE_HIGH_TURBIDITY")
            elif turb > 5.0:
                at_least("Caution", "POTABILITY_ADVISORY_TURBIDITY")
        if ec is not None:
            if ec > 2000.0:
                at_least("Unsafe", "SAFETY_OVERRIDE_HIGH_SALINITY")
            elif ec > 1500.0:
                at_least("Caution", "POTABILITY_ADVISORY_CONDUCTIVITY")
    if entropy > 0.65 and final == "Safe":
        final = "Caution"
        reasons.append("ADVISORY_HIGH_UNCERTAINTY")
    return final, reasons, oob


NAMES = ["arsenic", "ph", "conductivity", "turbidity", "temperature"]
OOD_Z = 3.0   # |z| above this = outside the training data (review item 19)


def predict(arsenic_mg_l: float, ph: Optional[float] = 7.2, conductivity_us_cm: Optional[float] = 400.0,
            turbidity_ntu: Optional[float] = 2.0, temperature_c: Optional[float] = 24.0,
            weights_path: Optional[str] = None) -> Dict:
    """pH / conductivity / turbidity / temperature may be None = sensor not fitted (see network())."""
    if arsenic_mg_l is None:
        raise ValueError("arsenic_mg_l is required")
    model = load(_resolve(weights_path))
    raw = [arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c]
    out = network(raw, model)
    probs = out["probs"]
    best = max(range(4), key=lambda i: probs[i])
    vote = CLASSES[best]
    entropy = max(0.0, min(1.0, -sum(p * math.log(p) for p in probs if p > 1e-12) / math.log(4)))
    final, reasons, oob = apply_rules(vote, raw, entropy)
    if arsenic_mg_l < 0.020:
        reasons.append("BELOW_METHOD_LOD_LAB_CONFIRMATION_ADVISED")
    not_measured = [n for n, v in zip(NAMES, raw) if v is None]
    # Review item 19 (v5.11): measured inputs more than OOD_Z standard deviations from the training data. The
    # vote is less reliable there; the fixed rules above already decided the final class, so nothing else changes.
    outside = [n for n, z, v in zip(NAMES, out["layers"][0], raw) if v is not None and abs(z) > OOD_Z]
    reasons += ["NOT_MEASURED_" + n.upper() for n in not_measured]
    return {
        "model": "AquaNet-V3 " + "-".join(map(str, model["topology"])),
        "network_vote": vote,
        "raw_model_class": vote,
        "predicted_class": final,
        "override_applied": final != vote,
        "is_out_of_bounds": oob,
        "confidence_pct": round(probs[best] * 100, 1),
        "probabilities_pct": {c: round(p * 100, 2) for c, p in zip(CLASSES, probs)},
        "entropy": round(entropy, 4),
        "high_uncertainty": entropy > 0.65,
        "reasons": reasons,
        "not_measured": not_measured,
        "outside_training_range": outside,
        "activations": {"input": out["layers"][0], "hidden_1": out["layers"][1], "hidden_2": out["layers"][2],
                        "output_logits": out["logits"]},
    }


if __name__ == "__main__":
    examples = [
        ("Clean well", 0.005, 7.4, 300, 1.0, 22),
        ("Just above WHO limit", 0.012, 7.3, 420, 2.5, 25),
        ("Borderline arsenic", 0.045, 7.3, 420, 2.5, 25),
        ("Acidic water, low arsenic", 0.005, 5.8, 400, 2.0, 24),
        ("Muddy water", 0.005, 7.2, 400, 15.0, 24),
        ("Salty water", 0.005, 7.2, 2500, 2.0, 24),
        ("Industrial runoff", 0.22, 5.8, 1250, 18.0, 31),
    ]
    for name, *vals in examples:
        r = predict(*vals)
        print(f"{name:28s} vote={r['network_vote']:9s} final={r['predicted_class']:9s} conf={r['confidence_pct']}%")
