"""Train AquaNet-V2: same 5-input / 4-class MLP, but labels depend on all water-quality rules,
so the network itself must learn pH, conductivity and turbidity (not just arsenic).
Usage: python3 train_v2.py <v1_weights.json> <out_dir>
"""
import json, math, sys, time, os
import numpy as np

V1 = json.load(open(os.environ.get("V1_WEIGHTS", sys.argv[1] if len(sys.argv) > 1 else "")))
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
MEAN = np.array(V1["normalization_moments"]["mean"], dtype=np.float64)
STD = np.array(V1["normalization_moments"]["std"], dtype=np.float64)
CLASSES = ["Safe", "Caution", "Unsafe", "Hazardous"]


def label(X):
    a, ph, ec, tu = X[:, 0], X[:, 1], X[:, 2], X[:, 3]
    y = np.zeros(len(X), dtype=np.int64)
    y = np.maximum(y, np.where(a >= 0.010, 1, 0))
    y = np.maximum(y, np.where(a >= 0.050, 2, 0))
    y = np.maximum(y, np.where(a > 0.150, 3, 0))
    y = np.maximum(y, np.where((ph < 6.5) | (ph > 8.5), 1, 0))
    y = np.maximum(y, np.where((ph < 6.0) | (ph > 9.0), 2, 0))
    y = np.maximum(y, np.where(tu > 5.0, 1, 0))
    y = np.maximum(y, np.where(tu > 10.0, 2, 0))
    y = np.maximum(y, np.where(ec > 1500.0, 1, 0))
    y = np.maximum(y, np.where(ec > 2000.0, 2, 0))
    return y


def sample(n, rng, boundary_frac=0.5):
    """Realistic broad samples + samples concentrated near each regulatory threshold."""
    nb = int(n * (1 - boundary_frac))
    a = np.exp(rng.uniform(np.log(0.0005), np.log(0.5), n))
    ph = np.clip(rng.normal(7.4, 0.9, n), 4.6, 10.4)
    ec = np.clip(rng.lognormal(np.log(600), 0.6, n), 60, 4900)
    tu = np.clip(rng.lognormal(np.log(3.0), 0.9, n), 0.05, 95)
    te = np.clip(rng.normal(25, 5.5, n), 6, 44)
    X = np.column_stack([a, ph, ec, tu, te])
    # boundary cohort: pick one feature and place it near one of its thresholds
    idx = np.arange(nb, n)
    which = rng.integers(0, 4, len(idx))
    th = {0: [0.010, 0.050, 0.150], 1: [6.0, 6.5, 8.5, 9.0], 2: [1500.0, 2000.0], 3: [5.0, 10.0]}
    width = {0: 0.15, 1: 0.12, 2: 120.0, 3: 0.8}
    for f in range(4):
        sel = idx[which == f]
        t = rng.choice(th[f], len(sel))
        if f == 0:
            X[sel, 0] = t * np.exp(rng.uniform(-width[0], width[0], len(sel)))
        else:
            X[sel, f] = t + rng.uniform(-width[f], width[f], len(sel))
    return X


def norm(X):
    return (X - MEAN) / STD


class MLP:
    def __init__(self, sizes, rng):
        self.W, self.B = [], []
        for i in range(len(sizes) - 1):
            fan = sizes[i]
            s = math.sqrt(2.0 / fan) if i < len(sizes) - 2 else math.sqrt(2.0 / (fan + sizes[i + 1]))
            self.W.append(rng.normal(0, s, (sizes[i + 1], sizes[i])))
            self.B.append(np.zeros(sizes[i + 1]))
        self.m = [np.zeros_like(p) for p in self.W + self.B]
        self.v = [np.zeros_like(p) for p in self.W + self.B]
        self.t = 0

    def forward(self, X):
        acts, pre = [X], []
        h = X
        for i, (W, B) in enumerate(zip(self.W, self.B)):
            z = h @ W.T + B
            pre.append(z)
            h = np.maximum(0, z) if i < len(self.W) - 1 else z
            acts.append(h)
        z = acts[-1]
        z = z - z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        return p, acts, pre

    def step(self, X, y, lr, l2=1e-5):
        p, acts, pre = self.forward(X)
        n = len(X)
        Y = np.zeros_like(p)
        Y[np.arange(n), y] = 1
        w = np.ones(n)
        w[y >= 2] = 4.0           # dangerous water: big penalty for under-calling
        w[y == 1] = 2.0
        loss = -(w * np.log(p[np.arange(n), y] + 1e-12)).mean()
        d = (p - Y) * w[:, None] / n
        grads_W, grads_B = [None] * len(self.W), [None] * len(self.W)
        for i in reversed(range(len(self.W))):
            grads_W[i] = d.T @ acts[i] + l2 * self.W[i]
            grads_B[i] = d.sum(0)
            if i > 0:
                d = (d @ self.W[i]) * (pre[i - 1] > 0)
        self.t += 1
        params = self.W + self.B
        grads = grads_W + grads_B
        for k, (P, G) in enumerate(zip(params, grads)):
            self.m[k] = 0.9 * self.m[k] + 0.1 * G
            self.v[k] = 0.999 * self.v[k] + 0.001 * G * G
            mh = self.m[k] / (1 - 0.9 ** self.t)
            vh = self.v[k] / (1 - 0.999 ** self.t)
            P -= lr * mh / (np.sqrt(vh) + 1e-8)
        return loss

    def predict(self, X):
        return self.forward(X)[0].argmax(1)


def v1_predict(X):
    W = V1["weights"]
    h = np.maximum(0, X @ np.array(W["W1"]).T + np.array(W["B1"]))
    h = np.maximum(0, h @ np.array(W["W2"]).T + np.array(W["B2"]))
    return (h @ np.array(W["W3"]).T + np.array(W["B3"])).argmax(1)


def metrics(pred, y):
    acc = (pred == y).mean() * 100
    rec = [float(((pred == c) & (y == c)).sum() / max(1, (y == c).sum()) * 100) for c in range(4)]
    danger_called_safe = int(((y >= 2) & (pred == 0)).sum())
    under = int((pred < y).sum())
    return {"accuracy_pct": round(float(acc), 3), "recall_pct": [round(r, 2) for r in rec],
            "dangerous_called_safe": danger_called_safe, "under_calls": under, "n": int(len(y))}


def train(sizes, seed, Xtr, ytr, Xva, yva, epochs, bs=512, lr0=4e-3):
    rng = np.random.default_rng(seed)
    net = MLP(sizes, rng)
    best = (-1, None, None)
    n = len(Xtr)
    for ep in range(1, epochs + 1):
        lr = 1e-4 + 0.5 * (lr0 - 1e-4) * (1 + math.cos(math.pi * ep / epochs))
        perm = rng.permutation(n)
        tot = 0
        for i in range(0, n, bs):
            b = perm[i:i + bs]
            tot += net.step(Xtr[b], ytr[b], lr)
        if ep % 5 == 0 or ep == epochs:
            m = metrics(net.predict(Xva), yva)
            score = m["accuracy_pct"] - 0.5 * m["dangerous_called_safe"]
            if score > best[0]:
                best = (score, [w.copy() for w in net.W], [b_.copy() for b_ in net.B], m, ep)
            print(f"  {sizes} seed {seed} ep {ep:3d} loss {tot / (n // bs + 1):.4f} val {m['accuracy_pct']:.2f}% dangerous->safe {m['dangerous_called_safe']}", flush=True)
    return best


if __name__ == "__main__":
    t0 = time.time()
    rng = np.random.default_rng(2026)
    Xtr_raw = sample(300_000, rng)
    Xva_raw = sample(60_000, rng)
    Xte_boundary = sample(100_000, np.random.default_rng(7), boundary_frac=1.0)
    Xte_field = sample(100_000, np.random.default_rng(11), boundary_frac=0.0)
    ytr, yva = label(Xtr_raw), label(Xva_raw)
    print("class mix (train):", np.bincount(ytr, minlength=4) / len(ytr))
    Xtr, Xva = norm(Xtr_raw), norm(Xva_raw)

    configs = [([5, 8, 6, 4], s) for s in range(8)] + [([5, 16, 12, 4], s) for s in range(4)]
    results = []
    for sizes, seed in configs:
        score, W, B, m, ep = train(sizes, seed, Xtr, ytr, Xva, yva, epochs=120)
        results.append({"sizes": sizes, "seed": seed, "score": score, "W": W, "B": B, "val": m, "epoch": ep})
        print(f"==> {sizes} seed {seed}: best val {m} at epoch {ep}  [{time.time() - t0:.0f}s]", flush=True)

    summary = {"elapsed_s": round(time.time() - t0)}
    for tag, X in [("field_like", Xte_field), ("boundary_dense", Xte_boundary)]:
        y = label(X)
        summary[f"v1_network_only_{tag}"] = metrics(v1_predict(norm(X)), y)
    for sizes in ([5, 8, 6, 4], [5, 16, 12, 4]):
        best = max((r for r in results if r["sizes"] == sizes), key=lambda r: r["score"])
        net = MLP(sizes, np.random.default_rng(0))
        net.W, net.B = best["W"], best["B"]
        key = "x".join(map(str, sizes))
        for tag, X in [("field_like", Xte_field), ("boundary_dense", Xte_boundary)]:
            summary[f"v2_{key}_{tag}"] = metrics(net.predict(norm(X)), label(X))
        json.dump({
            "model_name": "AquaNet-V2", "topology": sizes, "classes": CLASSES,
            "normalization_moments": {"mean": MEAN.tolist(), "std": STD.tolist()},
            "weights": {f"W{i + 1}": np.round(w, 6).tolist() for i, w in enumerate(best["W"])}
                       | {f"B{i + 1}": np.round(b, 6).tolist() for i, b in enumerate(best["B"])},
            "training": {"seed": best["seed"], "best_epoch": best["epoch"], "train_samples": 300000,
                         "val_samples": 60000, "optimizer": "Adam + cosine LR", "loss": "class-weighted cross-entropy",
                         "labels": "WHO/BIS arsenic tiers + pH, turbidity, conductivity potability rules (synthetic)"},
            "validation": best["val"],
        }, open(os.path.join(OUT, f"aquanet_v2_{key}_weights.json"), "w"), indent=1)
    json.dump(summary, open(os.path.join(OUT, "training_summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
