#!/usr/bin/env python3
"""
AquaNet research pipeline (v5.8): can a model learn arsenic from scan features better than the calibration line,
and how sure can it be? Review items 23-29, 47-52.

This is the honest version of "we trained a neural network": every number comes from data the model never saw,
split BY SITE (grouped cross-validation), against simple baselines, with calibrated uncertainty.

Input: the paired CSV from GET /api/data/export/paired (rows with a laboratory value), or --demo for a clearly
labelled SYNTHETIC dataset with site-to-site matrix effects.

Features per reading: peak_height_ua, peak_potential_mv, snr, ph, conductivity_us_cm, turbidity_ntu, temperature_c
(missing values are imputed with the training-fold median and flagged). Target: lab_ug_l (censored lab values are
left out of training and of the regression metrics; they still count as "< cutoff" for the decision metrics).

Models, each fitted inside every fold:
  1. calibration line        As = (Ip - b) / a, a and b fitted on the training sites (the deployed method)
  2. ridge regression        on standardised features, lambda chosen by inner leave-one-site-out
  3. PLS regression          NIPALS, 1-3 components chosen the same way
  4. residual MLP            a small numpy MLP (one hidden layer, Adam, early stopping on an inner site split)
                             that learns the CORRECTION to the calibration line; falls back to the line when the
                             correction does not help on the inner split

For every model: MAE / RMSE on held-out sites, decision metrics at 10 and 20 µg/L, a split-conformal 90 %
interval (|residual| quantile from the training fold's own held-out part) and its empirical coverage, a reliability
table (predicted-vs-observed "≥ 10" rate by predicted bin) and a referral-vs-miss curve: as the action threshold
moves, what fraction of samples would be referred to a laboratory, and what fraction of truly unsafe samples
would be missed. Output: report.md, metrics.json, referral_curve.svg, reliability.svg in --out.

With fewer than 4 sites or 40 quantified pairs the script says so and stops: nothing learned from less can be
trusted, and a model that "wins" on such a set is noise.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import svg_plots as sp  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "AquaSentry_Platform"))
from app.signal_processing import generate_synthetic_asv_trace  # noqa: E402

FEATURES = ["peak_height_ua", "peak_potential_mv", "snr", "ph", "conductivity_us_cm", "turbidity_ntu", "temperature_c"]
N_FEAT = len(FEATURES)
# v5.10 (ISEF item 157): raw voltammograms, resampled to the standard sweep grid, travel in X[:, N_FEAT:] when available
TRACE_GRID = np.arange(-1100.0, -499.9, 5.0)          # 121 points, the node's own grid
N_TRACE = len(TRACE_GRID)
CUTOFFS = (10.0, 20.0)
MIN_SITES, MIN_PAIRS = 4, 40
CONF_LEVEL = 0.90


# ---------------------------------------------------------------- data
def _f(v) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def resample_trace(P, C) -> np.ndarray:
    """A stored scan on the node's 121-point grid (linear interpolation; NaN outside the scan's own range)."""
    P, C = np.asarray(P, float), np.asarray(C, float)
    order = np.argsort(P)
    P, C = P[order], C[order]
    out = np.interp(TRACE_GRID, P, C, left=np.nan, right=np.nan)
    return out


def load_scans(path: str) -> Dict[int, np.ndarray]:
    """GET /api/scans/export saved as JSON -> {reading_id: resampled trace}."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for sc in data.get("scans", data if isinstance(data, list) else []):
        tr = resample_trace(sc["potentials_mv"], sc["currents_ua"])
        for rid in sc.get("reading_ids") or []:
            out[int(rid)] = tr
    return out


def load(path: str, scans_path: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    X, y, cens, sites, rids = [], [], [], [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("qc_status") or "").lower() == "fail":
                continue
            lab = _f(r.get("lab_ug_l"))
            if not math.isfinite(lab):
                continue
            X.append([_f(r.get(k)) for k in FEATURES])
            y.append(lab)
            cens.append((r.get("lab_qualifier") or "").strip() == "<")
            sites.append(r.get("site_name") or r.get("village") or r.get("device_code") or "unknown")
            try:
                rids.append(int(r.get("reading_id") or -1))
            except ValueError:
                rids.append(-1)
    X = np.array(X, float)
    if scans_path:
        traces = load_scans(scans_path)
        T = np.array([traces.get(rid, np.full(N_TRACE, np.nan)) for rid in rids]) if len(rids) else np.zeros((0, N_TRACE))
        X = np.hstack([X, T]) if len(X) else X
    return X, np.array(y, float), np.array(cens, bool), np.array(sites), FEATURES


def demo(n_sites: int = 8, per_site: int = 30, seed: int = 11):
    """SYNTHETIC: each site has its own matrix (slope factor 0.75-1.1, offset), copper that shifts the peak, pH
    and conductivity that correlate with the matrix, and 8 % proportional + 0.004 µA floor noise on the peak."""
    rng = np.random.default_rng(seed)
    X, y, cens, sites, traces = [], [], [], [], []
    for s in range(n_sites):
        slope_f = rng.uniform(0.75, 1.1)
        offset = rng.uniform(-0.004, 0.006)
        ph0 = rng.uniform(6.6, 7.8)
        ec0 = rng.uniform(250, 1400)
        for _ in range(per_site):
            truth = float(np.exp(rng.uniform(np.log(1.0), np.log(250.0))))
            ip = 0.0096 + 0.8563 * truth / 1000 * slope_f + offset
            ip = ip * (1 + rng.normal(0, 0.08)) + rng.normal(0, 0.004)
            ph = ph0 + rng.normal(0, 0.15)
            ec = ec0 * (1 + rng.normal(0, 0.1))
            X.append([max(ip, 0.0), -800 + 12 * (1.0 - slope_f) * 10 + rng.normal(0, 6), max(ip, 1e-4) / 0.004,
                      ph, ec, abs(rng.normal(2.5, 1.5)), rng.normal(26, 3)])
            lab = truth * (1 + rng.normal(0, 0.05))
            c = lab < 2.0
            y.append(2.0 if c else lab)
            cens.append(c)
            sites.append(f"Site-{s + 1}")
            # the raw voltammogram the same site matrix would give (for the trace CNN, item 157)
            eff_ppb = max(0.0, (ip - 0.0096) / 0.8563 * 1000.0)
            P, C = generate_synthetic_asv_trace(eff_ppb, seed=int(rng.integers(0, 10 ** 6)))
            traces.append(resample_trace(P, C))
    X = np.hstack([np.array(X), np.array(traces)])
    return X, np.array(y), np.array(cens, bool), np.array(sites), FEATURES


# ---------------------------------------------------------------- models (numpy only)
class Standardiser:
    def fit(self, X):
        X = X[:, :N_FEAT]
        self.med = np.nanmedian(X, axis=0)
        self.med = np.where(np.isfinite(self.med), self.med, 0.0)
        Xi = self._impute(X)
        self.mu, self.sd = Xi.mean(0), Xi.std(0) + 1e-9
        return self

    def _impute(self, X):
        return np.where(np.isfinite(X), X, self.med)

    def transform(self, X):
        X = X[:, :N_FEAT]
        Xi = self._impute(X)
        miss = (~np.isfinite(X)).astype(float)
        return np.hstack([(Xi - self.mu) / self.sd, miss])


class CalLine:
    name = "calibration line"

    def fit(self, X, y, sites=None):
        ip = X[:, 0]
        ok = np.isfinite(ip)
        A = np.vstack([y[ok] / 1000.0, np.ones(ok.sum())]).T
        (a, b), *_ = np.linalg.lstsq(A, ip[ok], rcond=None)
        self.a, self.b = (a, b) if a > 0 else (0.8563, 0.0096)
        return self

    def predict(self, X):
        ip = X[:, 0]
        return np.clip((ip - self.b) / self.a * 1000.0, 0, None)


class Ridge:
    name = "ridge"

    def __init__(self, lam=1.0):
        self.lam = lam

    def fit(self, X, y, sites=None):
        self.st = Standardiser().fit(X)
        Z = self.st.transform(X)
        self.ym = y.mean()
        n_f = Z.shape[1]
        self.w = np.linalg.solve(Z.T @ Z + self.lam * np.eye(n_f), Z.T @ (y - self.ym))
        return self

    def predict(self, X):
        return np.clip(self.st.transform(X) @ self.w + self.ym, 0, None)


class PLS:
    name = "PLS"

    def __init__(self, k=2):
        self.k = k

    def fit(self, X, y, sites=None):
        self.st = Standardiser().fit(X)
        Z = self.st.transform(X)
        self.ym = y.mean()
        Zc, yc = Z.copy(), (y - self.ym).copy()
        W, P, Q = [], [], []
        for _ in range(self.k):
            w = Zc.T @ yc
            if np.linalg.norm(w) < 1e-12:
                break
            w /= np.linalg.norm(w)
            t = Zc @ w
            tt = t @ t
            if tt < 1e-12:
                break
            p = Zc.T @ t / tt
            q = yc @ t / tt
            Zc -= np.outer(t, p)
            yc -= q * t
            W.append(w); P.append(p); Q.append(q)
        if not W:
            self.beta = np.zeros(Z.shape[1])
            return self
        W, P, Q = np.array(W).T, np.array(P).T, np.array(Q)
        self.beta = W @ np.linalg.pinv(P.T @ W) @ Q
        return self

    def predict(self, X):
        return np.clip(self.st.transform(X) @ self.beta + self.ym, 0, None)


class ResidualMLP:
    """Learns y - calibration(X) with one hidden layer; early stopping on an inner site split."""
    name = "residual MLP"

    def __init__(self, hidden=16, lr=0.01, epochs=600, l2=1e-3, seed=0):
        self.h, self.lr, self.epochs, self.l2, self.seed = hidden, lr, epochs, l2, seed

    def fit(self, X, y, sites=None):
        self.base = CalLine().fit(X, y)
        self.st = Standardiser().fit(X)
        Z = self.st.transform(X)
        r = y - self.base.predict(X)
        self.rs = r.std() + 1e-9
        rn = r / self.rs
        rng = np.random.default_rng(self.seed)
        if sites is not None and len(np.unique(sites)) >= 3:
            hold = np.unique(sites)[rng.integers(0, len(np.unique(sites)))]
            tr, va = sites != hold, sites == hold
        else:
            idx = rng.permutation(len(y)); cut = int(0.8 * len(y))
            tr = np.zeros(len(y), bool); tr[idx[:cut]] = True; va = ~tr
        d = Z.shape[1]
        W1 = rng.normal(0, 1 / math.sqrt(d), (d, self.h)); b1 = np.zeros(self.h)
        W2 = rng.normal(0, 1 / math.sqrt(self.h), self.h); b2 = np.zeros(1)
        params = [W1, b1, W2, b2]
        m = [np.zeros_like(p) for p in params]; v = [np.zeros_like(p) for p in params]
        best, best_params, bad = float("inf"), [p.copy() for p in params], 0

        def forward(Zb, P):
            W1, b1, W2, b2 = P
            Hh = np.tanh(Zb @ W1 + b1)
            return Hh, Hh @ W2 + b2[0]

        for ep in range(1, self.epochs + 1):
            Hh, out = forward(Z[tr], params)
            err = out - rn[tr]
            g2 = Hh.T @ err / tr.sum() + self.l2 * params[2]
            gb2 = np.array([err.mean()])
            dh = np.outer(err, params[2]) * (1 - Hh ** 2)
            g1 = Z[tr].T @ dh / tr.sum() + self.l2 * params[0]
            gb1 = dh.mean(0)
            grads = [g1, gb1, g2, gb2]
            for i in range(4):
                m[i] = 0.9 * m[i] + 0.1 * grads[i]
                v[i] = 0.999 * v[i] + 0.001 * np.square(grads[i])
                params[i] = params[i] - self.lr * (m[i] / (1 - 0.9 ** ep)) / (np.sqrt(v[i] / (1 - 0.999 ** ep)) + 1e-8)
            if ep % 10 == 0:
                _, ov = forward(Z[va], params)
                loss = float(np.mean((ov - rn[va]) ** 2))
                if loss < best - 1e-6:
                    best, best_params, bad = loss, [p.copy() for p in params], 0
                else:
                    bad += 1
                    if bad >= 15:
                        break
        self.params = best_params
        # keep the correction only if it beats "no correction" on the inner held-out site
        _, ov = forward(Z[va], self.params)
        self.use = float(np.mean((ov - rn[va]) ** 2)) < float(np.mean(rn[va] ** 2)) * 0.98
        return self

    def predict(self, X):
        base = self.base.predict(X)
        if not self.use:
            return base
        Z = self.st.transform(X)
        W1, b1, W2, b2 = self.params
        corr = (np.tanh(Z @ W1 + b1) @ W2 + b2[0]) * self.rs
        return np.clip(base + corr, 0, None)


class TraceCNN:
    """A tiny 1-D convolutional network on the raw voltammogram (ISEF item 157), numpy only.

    conv(kernel 9, F filters) -> ReLU -> global average + max pool -> linear -> log1p(As). Each trace is centred and
    scaled by the training set's spread; the network has F*(9+1) + 2F + 1 parameters (F = 8: 97). Early stopping on an
    inner site split; falls back to the calibration line for rows without a stored trace, and is kept only when it
    beats the line on the inner split - the same rule as the residual MLP."""
    name = "trace CNN"

    def __init__(self, filters=8, kernel=9, lr=0.01, epochs=400, l2=1e-4, seed=0):
        self.F, self.K, self.lr, self.epochs, self.l2, self.seed = filters, kernel, lr, epochs, l2, seed

    @staticmethod
    def _windows(T, K):
        n, L = T.shape
        idx = np.arange(K)[None, :] + np.arange(L - K + 1)[:, None]          # (L-K+1, K)
        return T[:, idx]                                                      # (n, L-K+1, K)

    def _prep(self, X):
        T = X[:, N_FEAT:N_FEAT + N_TRACE]
        has = np.isfinite(T).all(1)
        T = np.where(np.isfinite(T), T, 0.0)
        T = T - T.mean(1, keepdims=True)
        return T / self.scale, has

    def fit(self, X, y, sites=None):
        self.base = CalLine().fit(X, y)
        T = X[:, N_FEAT:N_FEAT + N_TRACE] if X.shape[1] >= N_FEAT + N_TRACE else np.full((len(y), N_TRACE), np.nan)
        has = np.isfinite(T).all(1)
        self.use = False
        if has.sum() < 20:
            return self
        Tc = T[has] - T[has].mean(1, keepdims=True)
        self.scale = Tc.std() + 1e-9
        T = Tc / self.scale
        yl = np.log1p(np.clip(y[has], 0, None))
        self.ym, self.ys = yl.mean(), yl.std() + 1e-9
        yn = (yl - self.ym) / self.ys
        rng = np.random.default_rng(self.seed)
        s_has = sites[has] if sites is not None else None
        if s_has is not None and len(np.unique(s_has)) >= 3:
            hold = np.unique(s_has)[rng.integers(0, len(np.unique(s_has)))]
            tr, va = s_has != hold, s_has == hold
        else:
            idx = rng.permutation(len(yn)); cut = int(0.8 * len(yn))
            tr = np.zeros(len(yn), bool); tr[idx[:cut]] = True; va = ~tr
        W = rng.normal(0, 1 / math.sqrt(self.K), (self.K, self.F)); b = np.zeros(self.F)
        V = rng.normal(0, 1 / math.sqrt(2 * self.F), 2 * self.F); c = np.zeros(1)
        params = [W, b, V, c]
        m = [np.zeros_like(p) for p in params]; v = [np.zeros_like(p) for p in params]
        Wn = self._windows(T, self.K)                                  # (n, P, K)

        def forward(Wn_b, P):
            W, b, V, c = P
            Z = Wn_b @ W + b                                           # (n, P, F)
            H = np.maximum(Z, 0)
            feat = np.concatenate([H.mean(1), H.max(1)], axis=1)       # (n, 2F)
            return Z, H, feat, feat @ V + c[0]

        best, best_params, bad = float("inf"), [p.copy() for p in params], 0
        for ep in range(1, self.epochs + 1):
            Z, H, feat, out = forward(Wn[tr], params)
            err = (out - yn[tr]) / tr.sum()                            # dL/dout for mean squared error (x 1/2)
            gV = feat.T @ err + self.l2 * params[2]
            gc = np.array([err.sum()])
            dfeat = np.outer(err, params[2])                           # (n, 2F)
            n_, Pn, F = H.shape
            dH = np.repeat(dfeat[:, None, :F], Pn, axis=1) / Pn
            amax = H.argmax(1)                                         # (n, F)
            dmax = np.zeros_like(H)
            np.put_along_axis(dmax, amax[:, None, :], dfeat[:, None, F:], axis=1)
            dZ = (dH + dmax) * (Z > 0)
            gW = np.einsum("npk,npf->kf", Wn[tr], dZ) + self.l2 * params[0]
            gb = dZ.sum((0, 1))
            grads = [gW, gb, gV, gc]
            for i in range(4):
                m[i] = 0.9 * m[i] + 0.1 * grads[i]
                v[i] = 0.999 * v[i] + 0.001 * np.square(grads[i])
                params[i] = params[i] - self.lr * (m[i] / (1 - 0.9 ** ep)) / (np.sqrt(v[i] / (1 - 0.999 ** ep)) + 1e-8)
            if ep % 10 == 0:
                _, _, _, ov = forward(Wn[va], params)
                loss = float(np.mean((ov - yn[va]) ** 2))
                if loss < best - 1e-6:
                    best, best_params, bad = loss, [p.copy() for p in params], 0
                else:
                    bad += 1
                    if bad >= 12:
                        break
        self.params = best_params
        _, _, _, ov = forward(Wn[va], self.params)
        pred_va = np.expm1(ov * self.ys + self.ym)
        base_va = self.base.predict(X[has][va])
        self.use = np.abs(pred_va - y[has][va]).mean() < np.abs(base_va - y[has][va]).mean() * 0.98
        self._forward = forward
        return self

    def predict(self, X):
        base = self.base.predict(X)
        if not self.use or X.shape[1] < N_FEAT + N_TRACE:
            return base
        T, has = self._prep(X)
        out = base.copy()
        if has.any():
            _, _, _, o = self._forward(self._windows(T[has], self.K), self.params)
            out[has] = np.clip(np.expm1(o * self.ys + self.ym), 0, None)
        return out


def choose(model_cls, grid: List, X, y, sites) -> object:
    """Inner leave-one-site-out to pick a hyper-parameter; falls back to the first value with < 3 sites."""
    us = np.unique(sites)
    if len(us) < 3 or len(grid) == 1:
        return model_cls(grid[0])
    best, best_v = None, float("inf")
    for g in grid:
        err = []
        for s in us:
            tr = sites != s
            if tr.sum() < 5:
                continue
            p = model_cls(g).fit(X[tr], y[tr], sites[tr]).predict(X[~tr])
            err.append(np.abs(p - y[~tr]).mean())
        v = float(np.mean(err)) if err else float("inf")
        if v < best_v:
            best, best_v = g, v
    return model_cls(best if best is not None else grid[0])


# ---------------------------------------------------------------- evaluation
def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, c - h), min(1.0, c + h)


def run(X, y, cens, sites, out_dir: str, label: str) -> Dict:
    os.makedirs(out_dir, exist_ok=True)
    us = np.unique(sites)
    quant = ~cens
    res: Dict = {"label": label, "n_rows": int(len(y)), "n_quantified": int(quant.sum()), "n_sites": int(len(us)),
                 "features": FEATURES, "split": "leave-one-site-out (grouped)", "conformal_level": CONF_LEVEL}
    if len(us) < MIN_SITES or quant.sum() < MIN_PAIRS:
        res["stopped"] = (f"Need at least {MIN_SITES} sites and {MIN_PAIRS} quantified pairs for a grouped evaluation; "
                          f"got {len(us)} sites and {int(quant.sum())} pairs. Collect more before training anything.")
        _write(out_dir, res, {})
        return res

    specs = [("calibration line", lambda Xt, yt, st: CalLine().fit(Xt, yt)),
             ("ridge", lambda Xt, yt, st: choose(Ridge, [0.1, 1.0, 10.0, 100.0], Xt, yt, st).fit(Xt, yt, st)),
             ("PLS", lambda Xt, yt, st: choose(PLS, [1, 2, 3], Xt, yt, st).fit(Xt, yt, st)),
             ("residual MLP", lambda Xt, yt, st: ResidualMLP().fit(Xt, yt, st))]
    has_traces = X.shape[1] >= N_FEAT + N_TRACE and np.isfinite(X[:, N_FEAT:N_FEAT + N_TRACE]).all(1).sum() >= 20
    if has_traces:
        specs.append(("trace CNN", lambda Xt, yt, st: TraceCNN().fit(Xt, yt, st)))
    res["trace_cnn"] = ("included (raw voltammograms available for %d rows)" % int(np.isfinite(X[:, N_FEAT:N_FEAT + N_TRACE]).all(1).sum())
                        if has_traces else "skipped: fewer than 20 rows with a stored scan (pass --scans scans.json from GET /api/scans/export)")
    preds = {name: np.full(len(y), np.nan) for name, _ in specs}
    lo = {name: np.full(len(y), np.nan) for name, _ in specs}
    hi = {name: np.full(len(y), np.nan) for name, _ in specs}
    rng = np.random.default_rng(0)
    for s in us:
        te = sites == s
        tr = ~te & quant
        if tr.sum() < 10:
            continue
        # split-conformal: fit on most training sites, take residual quantile on one held-out training site
        tr_sites = np.unique(sites[tr])
        cal_site = tr_sites[rng.integers(0, len(tr_sites))] if len(tr_sites) >= 3 else None
        fit_mask = tr & (sites != cal_site) if cal_site is not None else tr
        cal_mask = tr & (sites == cal_site) if cal_site is not None else tr
        for name, make in specs:
            m = make(X[fit_mask], y[fit_mask], sites[fit_mask])
            p = m.predict(X[te])
            preds[name][te] = p
            rc = np.abs(m.predict(X[cal_mask]) - y[cal_mask])
            k = min(len(rc) - 1, int(math.ceil((len(rc) + 1) * CONF_LEVEL)) - 1) if len(rc) else 0
            q = float(np.sort(rc)[max(0, k)]) if len(rc) else float("nan")
            lo[name][te], hi[name][te] = np.clip(p - q, 0, None), p + q

    res["models"] = {}
    curve_ax = sp.Axes((0, 1), (0, 1), "Referral vs missed-unsafe (held-out sites)" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                       "Fraction of samples referred to a laboratory", "Fraction of truly unsafe (lab ≥ 10 µg/L) missed")
    rel_ax = sp.Axes((0, 1), (0, 1), "Reliability: predicted vs observed ≥ 10 µg/L" + (" (SYNTHETIC)" if "SYNTHETIC" in label else ""),
                     "Predicted probability of lab ≥ 10 µg/L (bin centre)", "Observed fraction with lab ≥ 10 µg/L")
    rel_ax.line([0, 1], [0, 1], sp.MUTED, 1.0, "5 4", "perfect")
    colors = [sp.MUTED, sp.BLUE, sp.GREEN, sp.RED, sp.VIOLET]
    unsafe = (y >= 10) & quant
    for (name, _), col in zip(specs, colors):
        p = preds[name]
        ok = np.isfinite(p)
        d: Dict = {}
        e = p[ok & quant] - y[ok & quant]
        d["mae_ug_l"], d["rmse_ug_l"] = float(np.abs(e).mean()), float(math.sqrt((e ** 2).mean()))
        d["n_evaluated"] = int((ok & quant).sum())
        for c in CUTOFFS:
            pos = (y >= c) & quant & ok
            pred = p >= c
            tp = int((pred & pos).sum()); fn = int((~pred & pos).sum())
            fp = int((pred & ~pos & ok).sum()); tn = int((~pred & ~pos & ok).sum())
            se = wilson(tp, tp + fn); spc = wilson(tn, tn + fp)
            d[f"at_{c:.0f}"] = {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "sensitivity": se[0], "sensitivity_ci95": [se[1], se[2]],
                                "specificity": spc[0], "specificity_ci95": [spc[1], spc[2]]}
        cover = ((y >= lo[name]) & (y <= hi[name]))[ok & quant]
        width = (hi[name] - lo[name])[ok & quant]
        d["conformal"] = {"target_coverage": CONF_LEVEL, "empirical_coverage": float(cover.mean()), "median_width_ug_l": float(np.median(width))}
        # referral-vs-miss curve: refer when prediction >= t
        ts = np.linspace(0, 60, 121)
        ref, miss = [], []
        for t in ts:
            referred = p[ok] >= t
            ref.append(float(referred.mean()))
            miss.append(float((~referred & unsafe[ok]).sum() / max(1, unsafe[ok].sum())))
        d["referral_curve"] = {"threshold_ug_l": ts.tolist(), "referred": ref, "missed_unsafe": miss}
        curve_ax.line(ref, miss, col, 1.8, None, name)
        # reliability: P(lab >= 10) from the conformal interval: fraction of the interval above 10
        w = np.maximum(hi[name] - lo[name], 1e-6)
        prob = np.clip((hi[name] - 10) / w, 0, 1)
        bins = np.linspace(0, 1, 6)
        rel = []
        for b0, b1 in zip(bins[:-1], bins[1:]):
            inb = ok & quant & (prob >= b0) & (prob < b1 if b1 < 1 else prob <= b1)
            if inb.sum() >= 5:
                rel.append({"bin": [float(b0), float(b1)], "n": int(inb.sum()), "predicted": float(prob[inb].mean()),
                            "observed": float(unsafe[inb].mean())})
        d["reliability"] = rel
        if rel:
            rel_ax.line([r_["predicted"] for r_ in rel], [r_["observed"] for r_ in rel], col, 1.6, None, name)
            rel_ax.points([r_["predicted"] for r_ in rel], [r_["observed"] for r_ in rel], col, 3.5)
        res["models"][name] = d
    sp.save(os.path.join(out_dir, "referral_curve.svg"), curve_ax.render())
    sp.save(os.path.join(out_dir, "reliability.svg"), rel_ax.render())
    base = res["models"]["calibration line"]["mae_ug_l"]
    best = min(res["models"].items(), key=lambda kv: kv[1]["mae_ug_l"])
    res["verdict"] = (f"Best held-out MAE: {best[0]} ({best[1]['mae_ug_l']:.1f} µg/L vs {base:.1f} µg/L for the calibration line). "
                      + ("A learned model is not clearly better than the calibration line on unseen sites (less than 20 % lower MAE); keep the line."
                         if best[1]["mae_ug_l"] > 0.8 * base else
                         "A learned model is clearly better on unseen sites; it still needs a prospective check on new sites and electrode lots before it may change a verdict."))
    _write(out_dir, res, preds)
    return res


def _write(out_dir: str, res: Dict, preds: Dict) -> None:
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, default=float)
    L = [f"# AquaNet research pipeline — {res['label']}", ""]
    if "SYNTHETIC" in res["label"]:
        L += ["> **SYNTHETIC demonstration data.** The numbers describe the generator, not the sensor or any trained model.", ""]
    L += [f"- Rows: {res['n_rows']} (quantified lab values: {res['n_quantified']}); sites: {res['n_sites']}; split: {res['split']}", ""]
    if res.get("stopped"):
        L += [f"**Stopped:** {res['stopped']}", ""]
    else:
        L += ["| model | MAE µg/L | RMSE µg/L | sens @10 | spec @10 | sens @20 | spec @20 | 90 % interval coverage | median width µg/L |",
              "|---|---|---|---|---|---|---|---|---|"]
        for name, d in res["models"].items():
            a, b, c = d["at_10"], d["at_20"], d["conformal"]
            L += [f"| {name} | {d['mae_ug_l']:.1f} | {d['rmse_ug_l']:.1f} | {100 * a['sensitivity']:.0f} % | {100 * a['specificity']:.0f} % | "
                  f"{100 * b['sensitivity']:.0f} % | {100 * b['specificity']:.0f} % | {100 * c['empirical_coverage']:.0f} % | {c['median_width_ug_l']:.0f} |"]
        L += ["", f"**{res['verdict']}**", "", f"Trace CNN (item 157): {res.get('trace_cnn', 'n/a')}.", "",
              "![referral](referral_curve.svg)", "", "![reliability](reliability.svg)", "",
              "## Reading the results", "",
              "- Every model is fitted without the site it is scored on. Random row splits would leak the site's matrix into training and flatter every model.",
              "- The 90 % interval is split-conformal: the |residual| quantile on a training site the model did not fit. Coverage far below 90 % on new sites means the interval is too narrow there.",
              "- The referral curve is the operating choice: a lower action threshold refers more water to the laboratory and misses fewer unsafe sources. The deployed node uses 20 µg/L with a retest band.",
              "- Any model that beats the calibration line here still needs a prospective check (new sites, new electrode lots) before it may change a verdict.", ""]
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Grouped-by-site evaluation of learned arsenic models against the calibration line")
    ap.add_argument("csv", nargs="?", help="paired CSV from GET /api/data/export/paired")
    ap.add_argument("--demo", action="store_true", help="run on a SYNTHETIC multi-site dataset")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "aquanet_pipeline"))
    ap.add_argument("--label", default=None)
    ap.add_argument("--scans", default=None, help="JSON from GET /api/scans/export: enables the trace CNN (item 157)")
    a = ap.parse_args(argv)
    if a.demo:
        X, y, cens, sites, _ = demo()
        label = a.label or "SYNTHETIC multi-site demo"
    elif a.csv:
        X, y, cens, sites, _ = load(a.csv, a.scans)
        label = a.label or os.path.basename(a.csv)
    else:
        ap.error("give a paired CSV or --demo")
    res = run(X, y, cens, sites, a.out, label)
    print(res.get("stopped") or res["verdict"])
    print(f"-> {a.out}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
