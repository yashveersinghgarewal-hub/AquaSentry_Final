"""Compare V1, V2 and V3 models.
  A) Rule fidelity on exact readings (same test sets as the V2 report): network alone.
  B) End-to-end with noisy sensors: final verdict (network vote + safety rules on the *measured* values)
     against the class of the *true* water.
Usage: python3 eval_v3.py <v1.json> <v2.json> <model.json> [<model.json> ...]
"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_v3 as T3

V1_PATH, V2_PATH, *MODELS = sys.argv[1:]


def load(path):
    d = json.load(open(path))
    sizes = d["topology"]
    if isinstance(sizes, dict):  # V1 json format
        sizes = [5, 8, 6, 4]
    L = len(sizes) - 1
    W = [np.array(d["weights"][f"W{i + 1}"]) for i in range(L)]
    B = [np.array(d["weights"][f"B{i + 1}"]) for i in range(L)]
    log_as = d.get("input_transform", {}).get("arsenic", "").startswith("log10")
    return {"name": os.path.basename(path).replace("_best.json", "").replace("aquanet_", "").replace("_weights.json", ""),
            "W": W, "B": B, "mean": np.array(d["normalization_moments"]["mean"]),
            "std": np.array(d["normalization_moments"]["std"]), "log": log_as}


def probs(m, X):
    T = X.astype(np.float64).copy()
    if m["log"]:
        T[:, 0] = np.log10(np.clip(T[:, 0], 0, None) + 0.001)
    h = (T - m["mean"]) / m["std"]
    for i, (W, B) in enumerate(zip(m["W"], m["B"])):
        z = h @ W.T + B
        h = np.maximum(0, z) if i < len(m["W"]) - 1 else z
    z = h - h.max(1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(1, keepdims=True)


def final_verdict(m, Xmeas):
    p = probs(m, Xmeas)
    vote = p.argmax(1)
    final = np.maximum(vote, T3.label(Xmeas))           # safety rules on measured values
    H = -(p * np.log(np.clip(p, 1e-12, 1))).sum(1) / np.log(4)
    final = np.where((final == 0) & (H > 0.65), 1, final)
    return vote, final


def m_(pred, y):
    return {"accuracy_pct": round(float((pred == y).mean() * 100), 3),
            "dangerous_missed": int(((y >= 2) & (pred <= 1)).sum()),
            "dangerous_called_safe": int(((y >= 2) & (pred == 0)).sum()),
            "false_alarms": int((pred > y).sum()), "n": int(len(y))}


models = [load(V1_PATH), load(V2_PATH)] + [load(p) for p in MODELS]
res = {"A_exact_network_only": {}, "B_noisy_end_to_end": {}}
field = T3.sample(100_000, np.random.default_rng(11), boundary_frac=0.0)
bound = T3.sample(100_000, np.random.default_rng(7), boundary_frac=1.0)
for m in models:
    res["A_exact_network_only"][m["name"]] = {
        "field_like": m_(probs(m, field).argmax(1), T3.label(field)),
        "near_limits": m_(probs(m, bound).argmax(1), T3.label(bound))}
for tag, frac in [("realistic_water", 0.0), ("near_limits", 1.0)]:
    rng = np.random.default_rng(2027)
    truth = T3.sample(200_000, rng, boundary_frac=frac)
    meas = T3.measure(truth, rng)
    y = T3.label(truth)
    key = f"B_noisy_end_to_end_{tag}_scans{T3.SCANS}"
    res[key] = {"rules only": m_(T3.label(meas), y)}
    for m in models:
        _, final = final_verdict(m, meas)
        res[key][m["name"]] = m_(final, y)
res.pop("B_noisy_end_to_end")
print(json.dumps(res, indent=1))
