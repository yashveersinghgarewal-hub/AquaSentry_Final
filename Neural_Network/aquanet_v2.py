"""
AquaNet-V2 inference (pure Python, no NumPy needed).

V2 is a 5-8-6-4 network (same size as V1) trained from random weights on 300,000 synthetic samples whose labels
follow ALL the drinking-water rules (arsenic tiers + pH + turbidity + conductivity), so unlike V1
it actually uses every input. Training code: v2_training/train_v2.py and finetune_v2.py.

    from aquanet_v2 import predict
    predict(arsenic_mg_l=0.005, ph=5.8, conductivity_us_cm=400, turbidity_ntu=2, temperature_c=24)

The same conservative safety rules as V1 are applied after the network, so a rule can only
make the verdict stricter. For the larger, slightly more accurate 5-16-12-4 version:
    predict(..., weights_path="aquanet_v2_large_weights.json")
"""

from __future__ import annotations
import json
import math
import os
from functools import lru_cache
from typing import Dict, List, Optional

CLASSES = ["Safe", "Caution", "Unsafe", "Hazardous"]
HERE = os.path.dirname(os.path.abspath(__file__))
BOUNDS = [(0.0, 2.0), (4.5, 10.5), (50.0, 5000.0), (0.0, 100.0), (5.0, 45.0)]


@lru_cache(maxsize=4)
def load(weights_path: str) -> Dict:
    with open(weights_path, "r", encoding="utf-8") as f:
        return json.load(f)


def network(raw: List[float], model: Dict) -> List[float]:
    mean = model["normalization_moments"]["mean"]
    std = model["normalization_moments"]["std"]
    h = [(v - m) / s for v, m, s in zip(raw, mean, std)]
    layers = len(model["topology"]) - 1
    for i in range(layers):
        W = model["weights"][f"W{i + 1}"]
        B = model["weights"][f"B{i + 1}"]
        z = [sum(w * x for w, x in zip(row, h)) + b for row, b in zip(W, B)]
        h = [max(0.0, v) for v in z] if i < layers - 1 else z
    mx = max(h)
    ex = [math.exp(v - mx) for v in h]
    tot = sum(ex)
    return [e / tot for e in ex]


def predict(arsenic_mg_l: float, ph: float = 7.2, conductivity_us_cm: float = 400.0,
            turbidity_ntu: float = 2.0, temperature_c: float = 24.0,
            weights_path: Optional[str] = None) -> Dict:
    path = weights_path or "aquanet_v2_weights.json"
    model = load(path if os.path.isabs(path) else os.path.join(HERE, path))
    raw = [arsenic_mg_l, ph, conductivity_us_cm, turbidity_ntu, temperature_c]
    probs = network(raw, model)
    best = max(range(4), key=lambda i: probs[i])
    vote = CLASSES[best]
    final = vote
    reasons: List[str] = []

    def at_least(c: str):
        nonlocal final
        if CLASSES.index(c) > CLASSES.index(final):
            final = c

    oob = any(not math.isfinite(v) or not (lo <= v <= hi) for v, (lo, hi) in zip(raw, BOUNDS))
    if oob:
        at_least("Unsafe"); reasons.append("SAFETY_OVERRIDE_OUT_OF_BOUNDS")
    if arsenic_mg_l > 0.150:
        at_least("Hazardous"); reasons.append("ARSENIC_ACUTE_HAZARD")
    elif arsenic_mg_l >= 0.050:
        at_least("Unsafe"); reasons.append("ARSENIC_EXCEEDS_BIS")
    elif arsenic_mg_l > 0.010:
        at_least("Caution"); reasons.append("ARSENIC_ABOVE_WHO")
    if not oob:
        if ph < 6.0 or ph > 9.0: at_least("Unsafe"); reasons.append("SEVERE_PH")
        elif ph < 6.5 or ph > 8.5: at_least("Caution"); reasons.append("PH_ADVISORY")
        if turbidity_ntu > 10: at_least("Unsafe"); reasons.append("HIGH_TURBIDITY")
        elif turbidity_ntu > 5: at_least("Caution"); reasons.append("TURBIDITY_ADVISORY")
        if conductivity_us_cm > 2000: at_least("Unsafe"); reasons.append("HIGH_SALINITY")
        elif conductivity_us_cm > 1500: at_least("Caution"); reasons.append("CONDUCTIVITY_ADVISORY")

    entropy = -sum(p * math.log(p) for p in probs if p > 1e-12) / math.log(4)
    if entropy > 0.65 and final == "Safe":
        final = "Caution"; reasons.append("ADVISORY_HIGH_UNCERTAINTY")
    if arsenic_mg_l < 0.020:
        reasons.append("BELOW_METHOD_LOD_LAB_CONFIRMATION_ADVISED")

    return {
        "model": "AquaNet-V2 " + "-".join(map(str, model["topology"])),
        "network_vote": vote,
        "predicted_class": final,
        "override_applied": final != vote,
        "confidence_pct": round(probs[best] * 100, 1),
        "probabilities_pct": {c: round(p * 100, 2) for c, p in zip(CLASSES, probs)},
        "entropy": round(entropy, 4),
        "reasons": reasons,
    }


if __name__ == "__main__":
    examples = [
        ("Clean well", 0.005, 7.4, 300, 1.0, 22),
        ("Borderline arsenic", 0.035, 7.3, 420, 2.5, 25),
        ("Acidic water, low arsenic", 0.005, 5.8, 400, 2.0, 24),
        ("Muddy water", 0.005, 7.2, 400, 15.0, 24),
        ("Salty water", 0.005, 7.2, 2500, 2.0, 24),
        ("Industrial runoff", 0.22, 5.8, 1250, 18.0, 31),
    ]
    for name, *vals in examples:
        r = predict(*vals)
        print(f"{name:28s} vote={r['network_vote']:9s} final={r['predicted_class']:9s} conf={r['confidence_pct']}%")
