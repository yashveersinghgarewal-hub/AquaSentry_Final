"""AquaNet-V3 trainer.

Two changes from V2:
  1. Arsenic enters the network as log10(As_mg_L + 0.001), so the 10 / 50 / 150 ug/L limits are
     evenly spread instead of squeezed together near zero.
  2. Optional noise-aware mode: the network sees *measured* (noisy) readings but learns the class of the
     *true* water, using the sensor uncertainties stated in app/standards.py. It therefore learns how
     likely a reading near a limit is to really be over it.

Usage: python3 train_v3.py <mode: clean|noisy> <out_dir> <config list e.g. 5x8x6x4:0,1,2;5x16x12x4:0>
Writes <out_dir>/<mode>_<arch>_best.json after each architecture and progress to stdout.
"""
import json, math, os, sys, time
import numpy as np

CLASSES = ["Safe", "Caution", "Unsafe", "Hazardous"]
EPS_AS = 0.001
W_DANGER = float(os.environ.get('W_DANGER', 4.0))
W_CAUTION = float(os.environ.get('W_CAUTION', 2.0))
SCANS = int(os.environ.get('SCANS', 1))   # scans averaged per reading (noise / sqrt(SCANS))
# ADAPTIVE=1 copies the firmware: 3 scans, then +3 and +3 more only while the arsenic reading is within
# ADAPT_Z standard errors of a limit (10 / 50 / 150 ug/L). Overrides SCANS for arsenic.
ADAPTIVE = os.environ.get('ADAPTIVE', '0') == '1'
ADAPT_Z = float(os.environ.get('ADAPT_Z', 2.0))
LIMITS_UG = np.array([10.0, 50.0, 150.0])


def sd1(a_ug):
    """Single-scan arsenic noise (ug/L), from the uncertainty bands in app/standards.py."""
    return np.where(a_ug < 50, 5.0, np.where(a_ug <= 150, 7.5, 15.0))


def adaptive_arsenic(a_true_ug, rng):
    """Returns (measured arsenic ug/L, scans used) following the firmware's adaptive re-scan rule."""
    scans = rng.normal(0, 1, (len(a_true_ug), 9)) * sd1(a_true_ug)[:, None] + a_true_ug[:, None]
    used = np.full(len(a_true_ug), 3)
    est = scans[:, :3].mean(1)
    for k in (6, 9):
        near = (used == k - 3) & (np.abs(np.clip(est, 0, None)[:, None] - LIMITS_UG[None, :])
                                  < ADAPT_Z * sd1(np.clip(est, 0, None))[:, None] / np.sqrt(k - 3)).any(1)
        est = np.where(near, scans[:, :k].mean(1), est)
        used = np.where(near, k, used)
    return np.clip(est, 0, None), used


def label(X):
    a, ph, ec, tu = X[:, 0], X[:, 1], X[:, 2], X[:, 3]
    y = np.zeros(len(X), dtype=np.int64)
    y = np.maximum(y, np.where(a > 0.010, 1, 0))
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
    nb = int(n * (1 - boundary_frac))
    a = np.exp(rng.uniform(np.log(0.0005), np.log(0.5), n))
    ph = np.clip(rng.normal(7.4, 0.9, n), 4.6, 10.4)
    ec = np.clip(rng.lognormal(np.log(600), 0.6, n), 60, 4900)
    tu = np.clip(rng.lognormal(np.log(3.0), 0.9, n), 0.05, 95)
    te = np.clip(rng.normal(25, 5.5, n), 6, 44)
    X = np.column_stack([a, ph, ec, tu, te])
    idx = np.arange(nb, n)
    which = rng.integers(0, 4, len(idx))
    th = {0: [0.010, 0.050, 0.150], 1: [6.0, 6.5, 8.5, 9.0], 2: [1500.0, 2000.0], 3: [5.0, 10.0]}
    width = {0: 0.25, 1: 0.15, 2: 150.0, 3: 1.0}
    for f in range(4):
        sel = idx[which == f]
        t = rng.choice(th[f], len(sel))
        if f == 0:
            X[sel, 0] = t * np.exp(rng.uniform(-width[0], width[0], len(sel)))
        else:
            X[sel, f] = t + rng.uniform(-width[f], width[f], len(sel))
    return X


def measure(X, rng):
    """Simulated sensor readings. Arsenic noise follows the uncertainty bands in app/standards.py."""
    M = X.copy()
    a_ug = X[:, 0] * 1000
    if ADAPTIVE:
        M[:, 0] = adaptive_arsenic(a_ug, rng)[0] / 1000
    else:
        sd = sd1(a_ug) / np.sqrt(SCANS)
        M[:, 0] = np.clip(a_ug + rng.normal(0, sd), 0, None) / 1000
    M[:, 1] = X[:, 1] + rng.normal(0, 0.10, len(X))                    # pH probe +/-0.1
    M[:, 2] = X[:, 2] * (1 + rng.normal(0, 0.03, len(X)))              # conductivity +/-3%
    M[:, 3] = np.clip(X[:, 3] + rng.normal(0, 0.3, len(X)) + X[:, 3] * rng.normal(0, 0.05, len(X)), 0, None)
    M[:, 4] = X[:, 4] + rng.normal(0, 0.5, len(X))
    return M


def transform(X):
    T = X.copy().astype(np.float64)
    T[:, 0] = np.log10(X[:, 0] + EPS_AS)
    return T


class MLP:
    def __init__(self, sizes, rng):
        self.sizes = sizes
        self.W, self.B = [], []
        for i in range(len(sizes) - 1):
            s = math.sqrt(2.0 / sizes[i]) if i < len(sizes) - 2 else math.sqrt(2.0 / (sizes[i] + sizes[i + 1]))
            self.W.append(rng.normal(0, s, (sizes[i + 1], sizes[i])))
            self.B.append(np.zeros(sizes[i + 1]))
        self.m = [np.zeros_like(p) for p in self.W + self.B]
        self.v = [np.zeros_like(p) for p in self.W + self.B]
        self.t = 0

    def forward(self, X):
        acts, pre, h = [X], [], X
        for i, (W, B) in enumerate(zip(self.W, self.B)):
            z = h @ W.T + B
            pre.append(z)
            h = np.maximum(0, z) if i < len(self.W) - 1 else z
            acts.append(h)
        z = acts[-1] - acts[-1].max(1, keepdims=True)
        p = np.exp(z); p /= p.sum(1, keepdims=True)
        return p, acts, pre

    def step(self, X, y, lr, l2=1e-5):
        p, acts, pre = self.forward(X)
        n = len(X)
        Y = np.zeros_like(p); Y[np.arange(n), y] = 1
        w = np.ones(n); w[y >= 2] = W_DANGER; w[y == 1] = W_CAUTION
        d = (p - Y) * w[:, None] / n
        gW, gB = [None] * len(self.W), [None] * len(self.W)
        for i in reversed(range(len(self.W))):
            gW[i] = d.T @ acts[i] + l2 * self.W[i]
            gB[i] = d.sum(0)
            if i > 0:
                d = (d @ self.W[i]) * (pre[i - 1] > 0)
        self.t += 1
        for k, (P, G) in enumerate(zip(self.W + self.B, gW + gB)):
            self.m[k] = 0.9 * self.m[k] + 0.1 * G
            self.v[k] = 0.999 * self.v[k] + 0.001 * G * G
            P -= lr * (self.m[k] / (1 - 0.9 ** self.t)) / (np.sqrt(self.v[k] / (1 - 0.999 ** self.t)) + 1e-8)

    def predict(self, X):
        return self.forward(X)[0].argmax(1)


def metrics(pred, y):
    return {"accuracy_pct": round(float((pred == y).mean() * 100), 3),
            "dangerous_called_safe": int(((y >= 2) & (pred == 0)).sum()),
            "under_calls": int((pred < y).sum()), "over_calls": int((pred > y).sum()), "n": int(len(y))}


def main():
    mode, out, cfg = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(31 if mode == "clean" else 47)
    Xtr_true = sample(int(os.environ.get('NTRAIN', 260000)), rng); Xva_true = sample(60_000, rng)
    Xtr = measure(Xtr_true, rng) if mode == "noisy" else Xtr_true
    Xva = measure(Xva_true, rng) if mode == "noisy" else Xva_true
    ytr, yva = label(Xtr_true), label(Xva_true)
    Ttr, Tva = transform(Xtr), transform(Xva)
    mean, std = Ttr.mean(0), Ttr.std(0)
    Ntr, Nva = (Ttr - mean) / std, (Tva - mean) / std
    t0 = time.time()
    for part in cfg.split(";"):
        arch, seeds = part.split(":")
        sizes = [int(v) for v in arch.split("x")]
        best = None
        for seed in [int(s) for s in seeds.split(",")]:
            r2 = np.random.default_rng(1000 + seed)
            net = MLP(sizes, r2)
            epochs = int(os.environ.get('EPOCHS', 160 if sizes[1] <= 16 else 120))
            for ep in range(1, epochs + 1):
                lr = 5e-5 + 0.5 * (5e-3 - 5e-5) * (1 + math.cos(math.pi * ep / epochs))
                perm = r2.permutation(len(Ntr))
                for i in range(0, len(Ntr), 512):
                    b = perm[i:i + 512]
                    net.step(Ntr[b], ytr[b], lr)
                if ep % 20 == 0 or ep == epochs:
                    m = metrics(net.predict(Nva), yva)
                    score = m["accuracy_pct"] - 1.0 * m["dangerous_called_safe"] / 10
                    if best is None or score > best["score"]:
                        best = {"score": score, "seed": seed, "epoch": ep, "val": m,
                                "W": [w.copy() for w in net.W], "B": [b_.copy() for b_ in net.B]}
                    print(f"[{mode}] {arch} seed {seed} ep {ep} val {m['accuracy_pct']}% dangerous->safe {m['dangerous_called_safe']} ({time.time() - t0:.0f}s)", flush=True)
        doc = {"model_name": "AquaNet-V3", "mode": mode, "topology": sizes, "classes": CLASSES,
               "input_transform": {"arsenic": "log10(arsenic_mg_l + 0.001)", "others": "none"},
               "normalization_moments": {"mean": mean.round(8).tolist(), "std": std.round(8).tolist()},
               "weights": {f"W{i + 1}": np.round(w, 6).tolist() for i, w in enumerate(best["W"])}
                          | {f"B{i + 1}": np.round(b, 6).tolist() for i, b in enumerate(best["B"])},
               "training": {"seed": best["seed"], "best_epoch": best["epoch"], "train_samples": len(Ntr),
                            "optimizer": "Adam, cosine learning rate 5e-3 -> 5e-5, batch 512",
                            "loss": f"cross-entropy, x{W_DANGER:g} weight on Unsafe/Hazardous, x{W_CAUTION:g} on Caution",
                            "inputs": "noisy measured readings, true-water labels" if mode == "noisy" else "exact readings"},
               "validation": best["val"]}
        doc["training"]["class_weights"] = {"dangerous": W_DANGER, "caution": W_CAUTION}
        doc["training"]["scans_averaged"] = f"adaptive 3/6/9 (z={ADAPT_Z:g})" if ADAPTIVE else SCANS
        tag = os.environ.get("TAG", "")
        json.dump(doc, open(os.path.join(out, f"{mode}{tag}_{arch}_best.json"), "w"), indent=1)
        print(f"==> [{mode}] {arch} best seed {best['seed']} ep {best['epoch']} {best['val']}", flush=True)


if __name__ == "__main__":
    main()
