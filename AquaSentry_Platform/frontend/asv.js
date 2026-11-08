/**
 * AquaSentry ASV trace maths (v5.8) — a port of app/signal_processing.py, kept in one file so the browser
 * (offline practice tests, replay preview, the device simulator) and the server give the same answer.
 * tests/test_v58_pipeline.py runs both on the same traces and fails if they drift apart.
 * When the server is reachable its result is used; this file is the offline fallback and the chart maths.
 *
 *   window.AquaASV.process(P, C, opts) -> { S, base, sub, peakIdx, peakMv, net, snr, noise, asMgL, asUgL,
 *                                          flags, status, failed, uncertaintyUg, secondary, outliers, reversed }
 *   window.AquaASV.synth(asMgL, seed)  -> { P, C }   simulated clean trace (same model as the server's generator)
 *   window.AquaASV.fault()             -> { P, C }   flat trace of a dead / dry electrode
 */
(function () {
  'use strict';
  const CAL = { slope: 0.8563, intercept: 0.0096, peakMv: -800, expectMv: 60, searchMv: 100, excludeMv: 105, lodUg: 20, calMaxUg: 500 };
  const QC = { flatUa: 0.005, maxNoiseUa: 0.05, snr: 3, minPoints: 10, minShoulder: 4 };
  const FAULTS = ['ADC_SATURATION_HIGH', 'ADC_SATURATION_LOW', 'FLAT_SIGNAL', 'BASELINE_UNSTABLE', 'NOISE_ABOVE_LOD',
    'PEAK_AT_WINDOW_EDGE', 'NO_POINTS_IN_WINDOW', 'MALFORMED_TRACE', 'TOO_FEW_POINTS', 'NON_FINITE', 'INVALID_CALIBRATION',
    'NONMONOTONIC_SWEEP', 'INSUFFICIENT_BASELINE', 'PARTIAL_WINDOW'];
  const ANALYSIS_VERSION = 'asv-1.2.0';

  function savgol(y) {
    const n = y.length; if (n < 5) return y.slice();
    const s = new Array(n);
    s[0] = (31 * y[0] + 9 * y[1] - 3 * y[2] - 5 * y[3] + 3 * y[4]) / 35;
    s[1] = (9 * y[0] + 13 * y[1] + 12 * y[2] + 6 * y[3] - 5 * y[4]) / 35;
    for (let i = 2; i < n - 2; i++) s[i] = (-3 * y[i - 2] + 12 * y[i - 1] + 17 * y[i] + 12 * y[i + 1] - 3 * y[i + 2]) / 35;
    s[n - 2] = (-5 * y[n - 5] + 6 * y[n - 4] + 12 * y[n - 3] + 13 * y[n - 2] + 9 * y[n - 1]) / 35;
    s[n - 1] = (3 * y[n - 5] - 5 * y[n - 4] - 3 * y[n - 3] + 9 * y[n - 2] + 31 * y[n - 1]) / 35;
    return s;
  }
  function fit(xs, ys) {
    const n = xs.length, mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
    let sxx = 0, sxy = 0;
    for (let i = 0; i < n; i++) { sxx += (xs[i] - mx) ** 2; sxy += (xs[i] - mx) * (ys[i] - my); }
    const sl = sxx ? sxy / sxx : 0, ic = my - sl * mx;
    const res = xs.map((x, i) => ys[i] - (sl * x + ic));
    return { sl, ic, res, v: res.reduce((a, r) => a + r * r, 0) / Math.max(1, n - 2) };
  }
  const median = (a) => { const b = a.slice().sort((x, y) => x - y); return b[Math.floor(b.length / 2)]; };
  /** Robust background line: points outside ±excludeMv, with spikes / other peaks clipped (3 × MAD, 3 passes). */
  function baseline(P, S, peakMv) {
    let bx = [], by = [];
    P.forEach((p, i) => { if (Math.abs(p - peakMv) > CAL.excludeMv) { bx.push(p); by.push(S[i]); } });
    if (bx.length < 4) {
      const sl = (S[S.length - 1] - S[0]) / (P[P.length - 1] - P[0] || 1), ic = S[0] - sl * P[0];
      return { base: P.map((p) => sl * p + ic), v: 0.01, outliers: 0, sl };
    }
    const n0 = bx.length;
    let f = fit(bx, by);
    for (let k = 0; k < 3; k++) {
      const med = median(f.res), mad = median(f.res.map((r) => Math.abs(r - med))), sd = Math.max(1.4826 * mad, 1e-6);
      const kx = [], ky = [];
      f.res.forEach((r, i) => { if (Math.abs(r - med) <= 3 * sd) { kx.push(bx[i]); ky.push(by[i]); } });
      if (kx.length < 4 || kx.length === bx.length) break;
      bx = kx; by = ky; f = fit(bx, by);
    }
    return { base: P.map((p) => f.sl * p + f.ic), v: f.v, outliers: n0 - bx.length, sl: f.sl };
  }
  function uncertainty(ug, noise, slope, calRelSd, nScans) {
    const uN = noise / slope * 1000 / Math.sqrt(Math.max(1, nScans || 1)), uC = (calRelSd == null ? 0.05 : calRelSd) * Math.max(0, ug);
    return Math.round(2 * Math.sqrt(uN * uN + uC * uC) * 100) / 100;
  }

  function reject(P, C, flag, msg) {
    return { P, C, S: C.slice(), base: C.map(() => 0), sub: C.slice(), peakIdx: -1, peakMv: NaN, net: 0, snr: 0, noise: 0,
      asMgL: 0, asUgL: 0, flags: [flag], messages: [msg], status: 'REJECTED', failed: true, uncertaintyUg: null,
      secondary: 0, outliers: 0, reversed: false, version: ANALYSIS_VERSION };
  }

  function process(Pin, Cin, opts) {
    opts = opts || {};
    const slope = opts.slope == null ? CAL.slope : opts.slope, icpt = opts.intercept == null ? CAL.intercept : opts.intercept;
    const lod = opts.lodUg == null ? CAL.lodUg : opts.lodUg, target = CAL.peakMv;
    let P = (Pin || []).map(Number), C = (Cin || []).map(Number);
    if (P.length !== C.length) return reject(P, C, 'MALFORMED_TRACE', 'Potentials and currents arrays must have identical length.');
    if (P.length < QC.minPoints) return reject(P, C, 'TOO_FEW_POINTS', `Insufficient points (minimum ${QC.minPoints} required).`);
    if (!P.concat(C).every(Number.isFinite)) return reject(P, C, 'NON_FINITE', 'Trace contains non-finite numbers.');
    if (!(Number.isFinite(slope) && slope > 0 && Number.isFinite(icpt))) return reject(P, C, 'INVALID_CALIBRATION', 'Calibration slope must be a positive number.');
    let reversed = false;
    const d = P.slice(1).map((p, i) => p - P[i]);
    if (d.every((x) => x < 0)) { P = P.slice().reverse(); C = C.slice().reverse(); reversed = true; }
    else if (!d.every((x) => x > 0)) return reject(P, C, 'NONMONOTONIC_SWEEP', 'Potentials must increase (or decrease) steadily through the sweep.');

    const flags = [], messages = [];
    const maxC = Math.max.apply(null, C), minC = Math.min.apply(null, C);
    const nMax = C.filter((c) => c === maxC).length, nMin = C.filter((c) => c === minC).length;
    if (C.some((c) => c >= 10) || nMax > 3) flags.push('ADC_SATURATION_HIGH');
    if (C.some((c) => c <= -10) || nMin > 3) flags.push('ADC_SATURATION_LOW');
    if (maxC - minC < QC.flatUa) flags.push('FLAT_SIGNAL');
    const S = savgol(C);
    const leftSh = P.filter((p) => p < target - CAL.excludeMv).length, rightSh = P.filter((p) => p > target + CAL.excludeMv).length;
    if (leftSh < QC.minShoulder || rightSh < QC.minShoulder) {
      const r = reject(P, C, 'INSUFFICIENT_BASELINE', `Too few points outside the peak region (${leftSh} before, ${rightSh} after).`);
      r.S = S; r.reversed = reversed; return r;
    }
    if (!(P[0] <= target - CAL.expectMv && P[P.length - 1] >= target + CAL.expectMv)) flags.push('PARTIAL_WINDOW');
    const bl = baseline(P, S, target);
    const base = bl.base, sub = S.map((s, i) => s - base[i]);
    if (bl.outliers > Math.max(2, 0.05 * P.length)) flags.push('BASELINE_OUTLIERS');
    const noise = Math.sqrt(Math.max(1e-9, bl.v));
    if (noise > QC.maxNoiseUa) flags.push('BASELINE_UNSTABLE');
    else if (QC.snr * noise / slope * 1000 > lod) flags.push('NOISE_ABOVE_LOD');

    const win = [];
    P.forEach((p, i) => { if (Math.abs(p - target) <= CAL.searchMv) win.push(i); });
    if (!win.length) { const r = reject(P, C, 'NO_POINTS_IN_WINDOW', 'No sweep data points within the search window.'); r.S = S; r.base = base; r.sub = sub; r.flags = flags.concat(r.flags); return r; }
    let bi = win[0], best = sub[bi];
    win.forEach((i) => { if (sub[i] > best) { best = sub[i]; bi = i; } });
    let atEdge = false;
    if (bi === win[0] || bi === win[win.length - 1]) { const nb = bi === win[0] ? bi - 1 : bi + 1; atEdge = nb >= 0 && nb < sub.length && sub[nb] >= best; }
    const peakMv = P[bi], net = Math.max(0, best), snr = noise > 0 ? net / noise : 0;
    // half-height width (same walk as the server)
    let lp = peakMv, rp = peakMv;
    for (let i = bi; i >= 0; i--) if (sub[i] <= net / 2) { lp = P[i]; break; }
    for (let i = bi; i < P.length; i++) if (sub[i] <= net / 2) { rp = P[i]; break; }
    const fwhm = Math.abs(rp - lp);
    let asMgL, asUgL;
    if (net <= icpt) { asMgL = 0; asUgL = 0; flags.push('BELOW_METHOD_LOD'); }
    else { asMgL = Math.max(0, (net - icpt) / slope); asUgL = Math.round(asMgL * 1000 * 1e6) / 1e6; if (snr < QC.snr) flags.push('LOW_SNR'); }
    if (atEdge && net > icpt) flags.push('PEAK_AT_WINDOW_EDGE');
    else if (Math.abs(peakMv - target) > CAL.expectMv && net > icpt) flags.push('PEAK_SHIFTED');
    // secondary peaks outside the main peak's own region
    const thr = QC.snr * noise;
    let lo = bi, hi = bi;
    while (lo > 0 && sub[lo - 1] > thr / 2) lo--;
    while (hi < sub.length - 1 && sub[hi + 1] > thr / 2) hi++;
    let secondary = 0;
    for (let i = 1; i < sub.length - 1; i++) {
      if (i >= lo - 1 && i <= hi + 1) continue;
      if (sub[i] > thr && sub[i] >= sub[i - 1] && sub[i] > sub[i + 1]) secondary++;
    }
    if (asUgL > CAL.calMaxUg) flags.push('ABOVE_CALIBRATION_RANGE');
    const failed = flags.some((f) => FAULTS.includes(f));
    return { P, C, S, base, sub, peakIdx: bi, peakMv, net, snr, noise, fwhm, asMgL, asUgL: Math.round(asUgL * 100) / 100,
      flags, messages, status: failed ? 'REJECTED' : (flags.length ? 'WARNING' : 'PASS'), failed,
      uncertaintyUg: uncertainty(asUgL, noise, slope, opts.calRelSd, opts.nScans), secondary, outliers: bl.outliers,
      baselineSlope: bl.sl, reversed, version: ANALYSIS_VERSION };
  }

  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let x = Math.imul(a ^ (a >>> 15), 1 | a); x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x; return ((x ^ (x >>> 14)) >>> 0) / 4294967296; }; }
  function synth(asMgL, seed) {
    const rand = rng(seed == null ? Math.round(asMgL * 1e5) + 17 : seed), P = [], C = [];
    const peak = CAL.slope * asMgL + CAL.intercept;
    for (let i = 0; i < 121; i++) {
      const p = -1100 + i * 5;
      C.push(-0.15 + 0.00015 * (p + 1100) + peak * Math.exp(-0.5 * Math.pow((p - CAL.peakMv) / 35, 2)) + (rand() - 0.5) * 2 * 0.004);
      P.push(p);
    }
    return { P, C };
  }
  function fault() {
    const rand = rng(99), P = [], C = [];
    for (let i = 0; i < 121; i++) { P.push(-1100 + i * 5); C.push(Math.round((rand() - 0.5) * 2) * 0.000625); }
    return { P, C };
  }
  /** Parse a recorded instrument file: CSV / TSV with potential and current columns (header optional), or JSON. */
  function parseTraceFile(text, name) {
    text = String(text || '').replace(/^﻿/, '').trim();
    if (!text) return { error: 'empty' };
    if (text[0] === '{' || text[0] === '[') {
      try {
        const j = JSON.parse(text);
        const P = j.potentials_mv || j.potential_mV || j.potentials || j.P, C = j.currents_ua || j.current_uA || j.currents || j.C;
        if (Array.isArray(P) && Array.isArray(C)) return { P: P.map(Number), C: C.map(Number), meta: j };
        if (Array.isArray(j) && j.length && typeof j[0] === 'object') return { P: j.map((r) => Number(r.potential_mV ?? r.potentials_mv ?? r.p)), C: j.map((r) => Number(r.current_uA ?? r.currents_ua ?? r.c)), meta: {} };
      } catch (e) { return { error: 'json' }; }
      return { error: 'json' };
    }
    const lines = text.split(/\r?\n/).filter((l) => l.trim() && !l.trim().startsWith('#'));
    const sep = lines[0].includes('\t') ? '\t' : lines[0].includes(';') ? ';' : ',';
    let pi = 0, ci = 1, start = 0;
    const head = lines[0].split(sep).map((h) => h.trim().toLowerCase());
    if (head.some((h) => /[a-z]/.test(h))) {
      start = 1;
      const fp = head.findIndex((h) => /potential|volt|\bmv\b|\be\b/.test(h)), fc = head.findIndex((h) => /current|\bua\b|µa|amp|\bi\b/.test(h));
      if (fp >= 0) pi = fp; if (fc >= 0) ci = fc;
    }
    const P = [], C = [];
    for (let i = start; i < lines.length; i++) {
      const cells = lines[i].split(sep);
      const p = parseFloat(cells[pi]), c = parseFloat(cells[ci]);
      if (Number.isFinite(p) && Number.isFinite(c)) { P.push(p); C.push(c); }
    }
    // volts instead of millivolts, or amps / nanoamps instead of microamps: convert when the range makes it obvious
    const span = Math.max.apply(null, P) - Math.min.apply(null, P);
    const scaledP = span > 0 && span < 5 ? P.map((p) => p * 1000) : P;
    const maxAbsC = Math.max.apply(null, C.map(Math.abs));
    const scaledC = maxAbsC < 1e-3 ? C.map((c) => c * 1e6) : maxAbsC > 1e4 ? C.map((c) => c / 1000) : C;
    return { P: scaledP, C: scaledC, meta: { file: name || null, rows: P.length, converted: scaledP !== P || scaledC !== C } };
  }

  window.AquaASV = { CAL, QC, FAULTS, ANALYSIS_VERSION, process, synth, fault, savgol, parseTraceFile, uncertainty };
})();
