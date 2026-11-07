"""Round 2: continue training the best V2 weights with fresh data and a low, decaying learning rate."""
import json, math, sys, os, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_v2 as T

def run(weights_path, out_path, epochs=150, seed=99):
    d = json.load(open(weights_path))
    sizes = d["topology"]
    rng = np.random.default_rng(seed)
    net = T.MLP(sizes, rng)
    L = len(sizes) - 1
    net.W = [np.array(d["weights"][f"W{i+1}"]) for i in range(L)]
    net.B = [np.array(d["weights"][f"B{i+1}"]) for i in range(L)]
    net.m = [np.zeros_like(p) for p in net.W + net.B]; net.v = [np.zeros_like(p) for p in net.W + net.B]
    Xtr = T.sample(400_000, rng); ytr = T.label(Xtr); Xtr = T.norm(Xtr)
    Xva = T.sample(60_000, np.random.default_rng(seed + 1)); yva = T.label(Xva); Xva = T.norm(Xva)
    start = T.metrics(net.predict(Xva), yva)
    best = (start["accuracy_pct"] - 0.5 * start["dangerous_called_safe"], [w.copy() for w in net.W], [b.copy() for b in net.B], start, 0)
    print("start", sizes, start, flush=True)
    for ep in range(1, epochs + 1):
        lr = 1e-5 + 0.5 * (1e-3 - 1e-5) * (1 + math.cos(math.pi * ep / epochs))
        perm = rng.permutation(len(Xtr))
        for i in range(0, len(Xtr), 512):
            b = perm[i:i + 512]; net.step(Xtr[b], ytr[b], lr)
        if ep % 10 == 0:
            m = T.metrics(net.predict(Xva), yva); s = m["accuracy_pct"] - 0.5 * m["dangerous_called_safe"]
            print(f"  {sizes} ep {ep} val {m['accuracy_pct']} dangerous->safe {m['dangerous_called_safe']}", flush=True)
            if s > best[0]: best = (s, [w.copy() for w in net.W], [b.copy() for b in net.B], m, ep)
    net.W, net.B = best[1], best[2]
    tests = {}
    for tag, X in [("field_like", T.sample(100_000, np.random.default_rng(11), boundary_frac=0.0)), ("boundary_dense", T.sample(100_000, np.random.default_rng(7), boundary_frac=1.0))]:
        tests[tag] = T.metrics(net.predict(T.norm(X)), T.label(X))
    d["weights"] = {f"W{i+1}": np.round(w, 6).tolist() for i, w in enumerate(net.W)} | {f"B{i+1}": np.round(b, 6).tolist() for i, b in enumerate(net.B)}
    d["training"]["round2"] = {"epochs": epochs, "fresh_samples": 400000, "lr": "1e-3 to 1e-5 cosine", "best_epoch": best[4]}
    d["validation"] = best[3]; d["test"] = tests
    json.dump(d, open(out_path, "w"), indent=1)
    print("final", sizes, json.dumps(tests), flush=True)

if __name__ == "__main__":
    o = sys.argv[1]
    run(f"{o}/aquanet_v2_5x8x6x4_weights.json", f"{o}/aquanet_v2_5x8x6x4_round2.json")
    run(f"{o}/aquanet_v2_5x16x12x4_weights.json", f"{o}/aquanet_v2_5x16x12x4_round2.json")
