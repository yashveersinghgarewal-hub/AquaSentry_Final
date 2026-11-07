"""Adaptive re-scanning: the ESP32 takes 3 scans, and only if the averaged arsenic reading is close to a
limit (10 / 50 / 150 ug/L) does it take extra scans before deciding. Compares fixed 3 / 6 / 9 scans with
adaptive schemes on the same simulated water, using a given model + the safety rules.
Usage: python3 eval_adaptive.py <model.json> [<model.json> ...]"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_v3 as T3

LIMITS_UG = np.array([10.0, 50.0, 150.0])


def load(path):
    d = json.load(open(path))
    L = len(d["topology"]) - 1
    return {"name": os.path.basename(path).replace(".json", ""),
            "W": [np.array(d["weights"][f"W{i + 1}"]) for i in range(L)],
            "B": [np.array(d["weights"][f"B{i + 1}"]) for i in range(L)],
            "mean": np.array(d["normalization_moments"]["mean"]), "std": np.array(d["normalization_moments"]["std"])}


def final_verdict(m, X):
    T = X.astype(np.float64).copy()
    T[:, 0] = np.log10(np.clip(T[:, 0], 0, None) + 0.001)
    h = (T - m["mean"]) / m["std"]
    for i, (W, B) in enumerate(zip(m["W"], m["B"])):
        z = h @ W.T + B
        h = np.maximum(0, z) if i < len(m["W"]) - 1 else z
    z = h - h.max(1, keepdims=True); p = np.exp(z); p /= p.sum(1, keepdims=True)
    final = np.maximum(p.argmax(1), T3.label(X))
    H = -(p * np.log(np.clip(p, 1e-12, 1))).sum(1) / np.log(4)
    return np.where((final == 0) & (H > 0.65), 1, final)


def sd1(a_ug):  # single-scan arsenic noise, from app/standards.py
    return np.where(a_ug < 50, 5.0, np.where(a_ug <= 150, 7.5, 15.0))


def stats(pred, y, scans):
    return {"accuracy_pct": round(float((pred == y).mean() * 100), 3),
            "dangerous_missed": int(((y >= 2) & (pred <= 1)).sum()),
            "dangerous_called_safe": int(((y >= 2) & (pred == 0)).sum()),
            "false_alarms": int((pred > y).sum()),
            "avg_scans": round(float(scans.mean()), 3),
            "pct_readings_rescanned": round(float((scans > 3).mean() * 100), 2)}


def run(models, frac, n=200_000, seed=2027):
    rng = np.random.default_rng(seed)
    truth = T3.sample(n, rng, boundary_frac=frac)
    y = T3.label(truth)
    T3.SCANS = 1
    base = T3.measure(truth, rng)                          # pH / EC / turbidity / temperature read once
    a_true = truth[:, 0] * 1000
    scans = rng.normal(0, 1, (n, 9)) * sd1(a_true)[:, None] + a_true[:, None]   # 9 independent scans (ug/L)

    def with_scans(k):
        X = base.copy(); X[:, 0] = np.clip(scans[:, :k].mean(1), 0, None) / 1000
        return X

    out = {}
    for m in models:
        res = {}
        for k in (3, 6, 9):
            res[f"fixed_{k}_scans"] = stats(final_verdict(m, with_scans(k)), y, np.full(n, k))
        for z in (1.0, 1.5, 2.0, 2.5):
            X3 = with_scans(3); a3 = X3[:, 0] * 1000
            near = (np.abs(a3[:, None] - LIMITS_UG[None, :]) < z * sd1(a3)[:, None] / np.sqrt(3)).any(1)
            X = X3.copy(); X[near, 0] = with_scans(6)[near, 0]
            k = np.where(near, 6, 3)
            res[f"adaptive_3to6_z{z}"] = stats(final_verdict(m, X), y, k)
            a6 = X[:, 0] * 1000
            near2 = near & (np.abs(a6[:, None] - LIMITS_UG[None, :]) < z * sd1(a6)[:, None] / np.sqrt(6)).any(1)
            X2 = X.copy(); X2[near2, 0] = with_scans(9)[near2, 0]
            res[f"adaptive_3to9_z{z}"] = stats(final_verdict(m, X2), y, np.where(near2, 9, k))
        out[m["name"]] = res
    return out


if __name__ == "__main__":
    models = [load(p) for p in sys.argv[1:]]
    print(json.dumps({"realistic_water": run(models, 0.0), "near_limits": run(models, 1.0)}, indent=1))
