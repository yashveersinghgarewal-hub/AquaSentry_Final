/**
 * AquaSentry dashboard controller.
 * Works fully offline (simulated tests, AquaNet in the browser) and uses the FastAPI server when it is running.
 */
(function () {
  'use strict';

  const t = (k, v) => window.I18N.t(k, v);
  const $ = (id) => document.getElementById(id);
  const DEVICE = 'AQUA-001';
  const API = window.AQUASENTRY_API_URL ||
    ((location.protocol === 'file:' || location.port === '8001') ? 'http://127.0.0.1:8000' : location.origin);
  const CAL = { slope: 0.8563, intercept: 0.0096, peakMv: -800, windowMv: 60, excludeMv: 105 };

  const state = {
    online: false,
    reading: null,       // {asMgL, ph, ec, turb, temp, battery, lat, lon, time, source, savedOnServer}
    history: [],
    model: (window.AquaNet && window.AquaNet.hasV3) ? 'v3' : 'v1',
    lastTrace: null,
  };

  // ---------------- helpers ----------------
  async function api(path, opts, timeoutMs) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs || 4000);
    try {
      const res = await fetch(API + path, Object.assign({ signal: ctrl.signal }, opts || {}));
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return await res.json();
    } finally { clearTimeout(timer); }
  }
  function fmtTime(d) {
    const lang = window.I18N.lang === 'hi' ? 'hi-IN' : 'en-IN';
    try { return d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' }); } catch (e) { return d.toTimeString().slice(0, 5); }
  }
  function ugl(mgL) { return mgL * 1000; }
  function fmtUg(mgL) { const u = ugl(mgL); return u < 10 ? u.toFixed(1) : Math.round(u).toString(); }

  const ICONS = {
    none: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3"><path d="M28 7C21 17 15 24 15 31a13 13 0 0 0 26 0c0-7-6-14-13-24Z"/></svg>',
    Safe: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="28" cy="28" r="24"/><path d="M17 29l7 7 15-16"/></svg>',
    Caution: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M28 5L52 48H4Z"/><path d="M28 21v13M28 41v1"/></svg>',
    Unsafe: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"><circle cx="28" cy="28" r="24"/><path d="M19 19l18 18M37 19L19 37"/></svg>',
    Hazardous: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 4h20l14 14v20L38 52H18L4 38V18Z"/><path d="M28 16v16M28 40v1"/></svg>',
  };

  // ---------------- connection ----------------
  async function checkServer() {
    try { await api('/api/health', null, 2500); state.online = true; }
    catch (e) { state.online = false; }
    renderConn();
    renderReport();
    return state.online;
  }
  function renderConn() {
    const c = $('conn');
    c.dataset.state = state.online ? 'online' : 'offline';
    $('connText').textContent = t(state.online ? 'conn.online' : 'conn.offline');
  }

  // ---------------- readings ----------------
  function setReading(r, opts) {
    state.reading = r;
    const res = window.AquaNet.evaluate(r.asMgL, r.ph, r.ec, r.turb, r.temp, state.model);
    r.verdict = res.final;
    if (!opts || !opts.noHistory) {
      state.history.unshift({ time: r.time, asMgL: r.asMgL, verdict: res.final, source: r.source, ph: r.ph, ec: r.ec, turb: r.turb, temp: r.temp });
      state.history = state.history.slice(0, 50);
    }
    renderOverview();
    syncNetworkInputs(r);
    renderReport();
  }

  function stripPercent(u) {
    // piecewise scale: 0-10 -> 0-20%, 10-50 -> 20-45%, 50-150 -> 45-75%, 150-300 -> 75-100%
    const seg = [[0, 10, 0, 20], [10, 50, 20, 45], [50, 150, 45, 75], [150, 300, 75, 100]];
    const v = Math.max(0, Math.min(300, u));
    for (const [a, b, p, q] of seg) if (v <= b) return p + (v - a) / (b - a) * (q - p);
    return 100;
  }

  function renderOverview() {
    const r = state.reading;
    const v = $('verdict');
    if (!r) {
      v.dataset.tone = 'none';
      $('verdictIcon').innerHTML = ICONS.none;
      $('verdictTitle').textContent = t('verdict.none.title');
      $('verdictAction').textContent = t('verdict.none.action');
      $('asValue').textContent = '–';
      $('asMgl').textContent = '';
      $('stripPin').hidden = true;
      $('whyBox').hidden = true;
      $('ovMeta').textContent = t('ov.device', { code: DEVICE });
      renderReadingsGrid(null);
      return;
    }
    const res = window.AquaNet.evaluate(r.asMgL, r.ph, r.ec, r.turb, r.temp, state.model);
    v.dataset.tone = res.final;
    $('verdictIcon').innerHTML = ICONS[res.final];
    $('verdictTitle').textContent = t('verdict.' + res.final + '.title');
    $('verdictAction').textContent = t('verdict.' + res.final + '.action');
    $('asValue').textContent = fmtUg(r.asMgL);
    $('asMgl').textContent = t('ov.mgl', { v: r.asMgL.toFixed(4) });
    const pin = $('stripPin');
    pin.hidden = false;
    pin.style.left = stripPercent(ugl(r.asMgL)) + '%';
    $('stripPinLabel').textContent = fmtUg(r.asMgL) + ' µg/L';

    const why = $('whyList');
    why.innerHTML = '';
    res.reasons.filter((x) => x.code !== 'LOD').forEach((x) => {
      const li = document.createElement('li');
      li.textContent = t('reason.' + x.code, { v: x.v });
      why.appendChild(li);
    });
    $('labNote').hidden = !res.belowLod;
    $('labNote').textContent = t('ov.labNote');
    $('whyBox').hidden = false;

    const src = t('ov.source.' + r.source);
    $('ovMeta').textContent = `${t('ov.device', { code: DEVICE })}, ${t('ov.lastReading', { time: fmtTime(r.time) })} (${src})`;
    renderReadingsGrid(r);
  }

  const READ_DEFS = [
    { key: 'ph', label: 'read.ph', unit: '', min: 4.5, max: 10.5, ok: [6.5, 8.5], good: 'read.ph.good', fmt: (x) => x.toFixed(2) },
    { key: 'ec', label: 'read.ec', unit: 'µS/cm', min: 0, max: 3000, ok: [0, 1500], good: 'read.ec.good', fmt: (x) => Math.round(x) },
    { key: 'turb', label: 'read.turb', unit: 'NTU', min: 0, max: 20, ok: [0, 5], good: 'read.turb.good', fmt: (x) => x.toFixed(1) },
    { key: 'temp', label: 'read.temp', unit: '°C', min: 5, max: 45, ok: null, good: 'read.temp.good', fmt: (x) => x.toFixed(1) },
  ];
  function renderReadingsGrid(r) {
    const grid = $('readingsGrid');
    grid.innerHTML = READ_DEFS.map((d) => {
      const val = r ? r[d.key] : null;
      const pct = (x) => Math.max(0, Math.min(100, (x - d.min) / (d.max - d.min) * 100));
      const okBand = d.ok ? `<div class="gauge-ok" style="left:${pct(d.ok[0])}%;width:${pct(d.ok[1]) - pct(d.ok[0])}%"></div>` : '';
      const dot = val !== null ? `<div class="gauge-dot" style="left:${pct(val)}%"></div>` : '';
      const inRange = val === null || !d.ok || (val >= d.ok[0] && val <= d.ok[1]);
      const state = val === null || !d.ok ? '' : `<span class="reading-state ${inRange ? 'ok' : 'bad'}">${t(inRange ? 'read.ok' : 'read.bad')}</span>`;
      return `<div class="reading">
        <div class="reading-name">${t(d.label)}</div>
        <div class="reading-val">${val === null ? '–' : d.fmt(val)}${d.unit ? `<small>${d.unit}</small>` : ''}</div>
        <div class="gauge">${okBand}${dot}</div>
        <div class="reading-foot"><span>${t(d.good)}</span>${state}</div>
      </div>`;
    }).join('');
    const line = $('deviceLine');
    if (r && (r.battery != null || r.lat != null)) {
      const parts = [];
      if (r.battery != null) parts.push(`${t('read.battery')} ${Math.round(r.battery)}%`);
      if (r.lat != null) parts.push(`${t('read.location')} ${r.lat.toFixed(2)}°N, ${r.lon.toFixed(2)}°E`);
      line.textContent = parts.join('   |   ');
    } else line.textContent = '';
  }

  // ---------------- server data ----------------
  async function loadLatestFromServer() {
    try {
      const d = await api(`/api/readings/latest?device_code=${encodeURIComponent(DEVICE)}`);
      setReading({
        asMgL: (d.arsenic_ppb || 0) / 1000, ph: d.ph ?? 7.3, ec: d.conductivity_us_cm ?? 420, turb: d.turbidity_ntu ?? 2.0,
        temp: d.temperature_c ?? 25, battery: d.battery_pct, lat: d.latitude, lon: d.longitude,
        time: d.recorded_at ? new Date(d.recorded_at.endsWith('Z') || d.recorded_at.includes('+') ? d.recorded_at : d.recorded_at + 'Z') : new Date(),
        source: d.is_simulated === false || d.source_type === 'hardware' ? 'device' : 'demo', savedOnServer: true,
      });
      return true;
    } catch (e) { return false; }
  }

  async function loadDemo() {
    if (state.online) {
      try { await api('/api/demo/load', { method: 'POST' }, 6000); if (await loadLatestFromServer()) return; } catch (e) { /* fall through */ }
    }
    setReading({ asMgL: 0.045, ph: 7.35, ec: 412, turb: 2.1, temp: 24.2, battery: 71, lat: 25.61, lon: 85.14, time: new Date(), source: 'demo' });
  }

  // ---------------- voltammetry (same maths as app/signal_processing.py) ----------------
  function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let x = Math.imul(a ^ (a >>> 15), 1 | a); x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x; return ((x ^ (x >>> 14)) >>> 0) / 4294967296; }; }
  function synthTrace(asMgL) {
    const rand = rng(Math.round(asMgL * 1e5) + 17);
    const P = [], C = [];
    const peak = CAL.slope * asMgL + CAL.intercept;
    for (let i = 0; i < 121; i++) {
      const p = -1100 + i * 5;
      const base = -0.15 + 0.00015 * (p + 1100);
      const g = Math.exp(-0.5 * Math.pow((p - CAL.peakMv) / 35, 2));
      C.push(base + peak * g + (rand() - 0.5) * 2 * 0.004);
      P.push(p);
    }
    return { P, C };
  }
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
  function processTrace(P, C) {
    const S = savgol(C);
    const bx = [], by = [];
    P.forEach((p, i) => { if (Math.abs(p - CAL.peakMv) > CAL.excludeMv) { bx.push(p); by.push(S[i]); } });
    const mx = bx.reduce((a, b) => a + b, 0) / bx.length, my = by.reduce((a, b) => a + b, 0) / by.length;
    let sxx = 0, sxy = 0; bx.forEach((x, i) => { sxx += (x - mx) ** 2; sxy += (x - mx) * (by[i] - my); });
    const m = sxx ? sxy / sxx : 0, c = my - m * mx;
    const base = P.map((p) => m * p + c);
    let vr = 0; bx.forEach((x, i) => { vr += (by[i] - (m * x + c)) ** 2; }); vr /= Math.max(1, bx.length - 2);
    let bi = -1, best = -Infinity;
    P.forEach((p, i) => { if (Math.abs(p - CAL.peakMv) <= CAL.windowMv && S[i] - base[i] > best) { best = S[i] - base[i]; bi = i; } });
    const net = Math.max(0, best);
    const as = net <= CAL.intercept ? 0 : (net - CAL.intercept) / CAL.slope;
    return { S, base, peakIdx: bi, peakMv: P[bi], net, snr: net / Math.sqrt(Math.max(1e-9, vr)), asMgL: as };
  }

  async function runTest(asMgL, opts) {
    const quiet = opts && opts.quiet;
    const btn = $('runTestBtn');
    btn.disabled = true; btn.textContent = t('test.running');
    const { P, C } = synthTrace(asMgL);
    let out = processTrace(P, C);
    let saved = false;
    if (state.online) {
      try {
        const d = await api('/api/voltammetry/process', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ potentials_mv: P, currents_ua: C, filter_mode: 'savitzky_golay' }) });
        if (d && d.peak) {
          out = { S: d.smoothed_currents_ua, base: d.baseline_currents_ua, peakIdx: P.indexOf(d.peak.peak_potential_mv), peakMv: d.peak.peak_potential_mv, net: d.peak.net_peak_height_ua, snr: d.peak.snr, asMgL: d.estimated_arsenic_mg_l };
        }
      } catch (e) { /* keep local result */ }
    }
    state.lastTrace = { P, C, out };
    drawChart();
    $('trPeak').textContent = out.net.toFixed(4) + ' µA';
    $('trPos').textContent = Math.round(out.peakMv) + ' mV';
    $('trSnr').textContent = out.snr.toFixed(0);
    $('trAs').textContent = fmtUg(out.asMgL) + ' µg/L';

    const prev = state.reading || { ph: 7.3, ec: 420, turb: 2.5, temp: 25, battery: 71, lat: 25.61, lon: 85.14 };
    const reading = { asMgL: out.asMgL, ph: prev.ph, ec: prev.ec, turb: prev.turb, temp: prev.temp, battery: prev.battery, lat: prev.lat, lon: prev.lon, time: new Date(), source: 'sim' };
    if (state.online) {
      try {
        await api('/api/readings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
          device_code: DEVICE, arsenic_ppb: Math.round(ugl(out.asMgL) * 100) / 100, ph: reading.ph, conductivity_us_cm: reading.ec,
          turbidity_ntu: reading.turb, temperature_c: reading.temp, source_type: 'simulated', source_label: 'Dashboard test',
        }) });
        saved = true; reading.savedOnServer = true;
      } catch (e) { /* offline save failed: keep local */ }
    }
    setReading(reading);
    btn.disabled = false; btn.textContent = t('test.run');
    if (!quiet) $('testMsg').textContent = t(saved ? 'test.savedServer' : 'test.saved');
  }

  function drawChart() {
    const svg = $('vgChart');
    const NS = 'http://www.w3.org/2000/svg';
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    const add = (name, attrs, text) => { const e = document.createElementNS(NS, name); Object.keys(attrs).forEach((k) => e.setAttribute(k, attrs[k])); if (text !== undefined) e.textContent = text; svg.appendChild(e); return e; };
    const L = 64, R = 620, T = 20, B = 290;
    if (!state.lastTrace) { add('text', { x: 340, y: 160, 'text-anchor': 'middle', class: 'vg-empty' }, t('test.chart.empty')); return; }
    const { P, C, out } = state.lastTrace;
    const all = C.concat(out.S, out.base);
    let lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    const pad = (hi - lo) * 0.08 || 0.01; lo -= pad; hi += pad;
    const X = (p) => L + (p - P[0]) / (P[P.length - 1] - P[0]) * (R - L);
    const Y = (c) => B - (c - lo) / (hi - lo) * (B - T);
    const step = niceStep((hi - lo) / 5);
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
      add('line', { x1: L, x2: R, y1: Y(v), y2: Y(v), class: 'vg-grid' });
      add('text', { x: L - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'vg-tick' }, (Math.abs(v) < 1e-9 ? 0 : v).toFixed(step < 0.1 ? 2 : 1));
    }
    for (let p = -1100; p <= -500; p += 100) add('text', { x: X(p), y: B + 20, 'text-anchor': 'middle', class: 'vg-tick' }, String(p));
    add('line', { x1: L, x2: R, y1: B, y2: B, class: 'vg-axis' });
    add('text', { x: (L + R) / 2, y: B + 44, 'text-anchor': 'middle', class: 'vg-title' }, t('test.chart.x'));
    add('text', { x: 16, y: (T + B) / 2, 'text-anchor': 'middle', class: 'vg-title', transform: `rotate(-90 16 ${(T + B) / 2})` }, t('test.chart.y'));
    const path = (arr) => arr.map((c, i) => `${i ? 'L' : 'M'}${X(P[i]).toFixed(1)} ${Y(c).toFixed(1)}`).join(' ');
    add('path', { d: path(C), class: 'vg-raw' });
    add('path', { d: path(out.base), class: 'vg-base' });
    add('path', { d: path(out.S), class: 'vg-smooth' });
    if (out.peakIdx >= 0) {
      const px = X(out.peakMv);
      add('line', { x1: px, x2: px, y1: Y(out.base[out.peakIdx]), y2: Y(out.S[out.peakIdx]), class: 'vg-peak' });
      add('text', { x: px + 8, y: Y(out.S[out.peakIdx]) - 8, class: 'vg-peak-label' }, `${t('test.peak')} ${out.net.toFixed(3)} µA`);
    }
  }
  function niceStep(raw) { const p = Math.pow(10, Math.floor(Math.log10(raw))); const f = raw / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; }

  // ---------------- AquaNet panel ----------------
  const NN_IDS = [['nnAs', 'nnOutAs', (v) => `${(v * 1000).toFixed(0)} µg/L`], ['nnPh', 'nnOutPh', (v) => v.toFixed(2)], ['nnEc', 'nnOutEc', (v) => `${Math.round(v)} µS/cm`], ['nnTurb', 'nnOutTurb', (v) => `${v.toFixed(1)} NTU`], ['nnTemp', 'nnOutTemp', (v) => `${v.toFixed(1)} °C`]];
  function nnValues() { return NN_IDS.map(([id]) => parseFloat($(id).value)); }
  function syncNetworkInputs(r) {
    const vals = [Math.min(0.3, r.asMgL), r.ph, r.ec, Math.min(25, r.turb), r.temp];
    NN_IDS.forEach(([id], i) => { $(id).value = vals[i]; });
    updateNetwork();
  }
  function updateNetwork() {
    const v = nnValues();
    NN_IDS.forEach(([, out, f], i) => { $(out).textContent = f(v[i]); });
    const res = window.AquaNet.evaluate(v[0], v[1], v[2], v[3], v[4], state.model);
    window.AquaNet.draw($('nnSvg'), res);
    $('nnVote').innerHTML = `<span class="tone-${res.vote}">${t('class.' + res.vote)}</span>`;
    $('nnFinal').innerHTML = `<span class="tone-${res.final}">${t('class.' + res.final)}</span>`;
    $('nnConf').textContent = (res.confidence * 100).toFixed(1) + '%';
    $('nnEnt').textContent = res.entropy.toFixed(2);
    $('nnBars').innerHTML = window.AquaNet.CLASSES.map((c, i) => {
      const p = (res.probs[i] * 100);
      return `<div class="bar-row"><span>${t('class.' + c)}</span><div class="bar"><i style="width:${p.toFixed(1)}%;background:var(--${c === 'Safe' ? 'safe' : c === 'Caution' ? 'caution-fill' : c === 'Unsafe' ? 'unsafe' : 'haz'})"></i></div><span class="bar-pct">${p.toFixed(1)}%</span></div>`;
    }).join('');
    $('nnRuleMsg').textContent = t(res.final !== res.vote ? 'nn.override' : 'nn.agree');
    $('nnReasons').innerHTML = res.reasons.map((x) => `<li>${t('reason.' + x.code, { v: x.v })}</li>`).join('');
    const c = window.AquaNet.countWeights(state.model);
    $('nnStats').textContent = t('nn.stats', { nodes: c.nodes, weights: c.nz, total: c.total });
    renderModelNote();
  }
  function renderModelNote() {
    const info = window.AquaNet.v3Info;
    $('nnModelNote').textContent = state.model === 'v3' && info ? t('nn.v3.note', { acc: info.testAccuracy, miss: info.missReduction }) : t('nn.v1.note');
    document.querySelectorAll('[data-model]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.model === state.model ? 'true' : 'false'));
    const v3btn = document.querySelector('[data-model="v3"]');
    if (!window.AquaNet.hasV3) { v3btn.disabled = true; v3btn.title = t('nn.v3.missing'); }
  }

  // ---------------- contaminants ----------------
  const ANALYTES = [
    { id: 'arsenic', f: 'As(III) / As(V)', status: 'supported_screening', lod: '20 µg/L', bis: '10 µg/L (50 permissible)', method: 'Anodic stripping voltammetry (MAS-G1)' },
    { id: 'lead', f: 'Pb²⁺', status: 'planned', lod: '5 µg/L', bis: '10 µg/L', method: 'Differential pulse ASV at −450 mV' },
    { id: 'cadmium', f: 'Cd²⁺', status: 'planned', lod: '1 µg/L', bis: '3 µg/L', method: 'Differential pulse ASV at −600 mV' },
    { id: 'mercury', f: 'Hg²⁺', status: 'experimental', lod: '0.5 µg/L', bis: '1 µg/L', method: 'Square-wave ASV on gold electrode' },
    { id: 'chromium_total', f: 'Cr', status: 'lab_reference_only', lod: '0.2 µg/L', bis: '50 µg/L', method: 'ICP-MS (lab)' },
    { id: 'chromium_vi', f: 'Cr(VI)', status: 'planned', lod: '2 µg/L', bis: '50 µg/L (as total Cr)', method: 'Diphenylcarbazide colorimetry, 540 nm' },
    { id: 'fluoride', f: 'F⁻', status: 'planned', lod: '0.1 mg/L', bis: '1.0 mg/L (1.5 permissible)', method: 'Fluoride ion-selective electrode' },
    { id: 'nitrate', f: 'NO₃⁻', status: 'planned', lod: '0.5 mg/L', bis: '45 mg/L', method: 'UV absorbance at 220 nm' },
  ];
  function renderContaminants() {
    $('conTable').querySelector('tbody').innerHTML = ANALYTES.map((a) => `<tr>
      <td><div class="con-name">${t('con.name.' + a.id)}</div><div class="con-formula">${a.f}</div></td>
      <td><span class="tag ${a.status === 'supported_screening' ? 'active' : ''}">${t('con.status.' + a.status)}</span></td>
      <td class="num">${a.lod}</td><td class="num">${a.bis}</td><td>${a.method}</td></tr>`).join('');
  }

  // ---------------- report ----------------
  function renderReport() {
    const body = $('repTable').querySelector('tbody');
    body.innerHTML = state.history.length ? state.history.map((h) => `<tr>
      <td>${fmtTime(h.time)}</td><td class="num">${fmtUg(h.asMgL)}</td>
      <td><span class="tone-${h.verdict}" style="font-weight:700">${t('class.' + h.verdict)}</span></td><td>${t('ov.source.' + h.source)}</td></tr>`).join('')
      : `<tr class="empty-row"><td colspan="4">${t('rep.empty')}</td></tr>`;
    const pdf = $('pdfBtn');
    const canPdf = state.online && state.reading && state.reading.savedOnServer;
    pdf.setAttribute('aria-disabled', canPdf ? 'false' : 'true');
    pdf.textContent = t(canPdf ? 'rep.pdf' : 'rep.pdfOff');
    if (canPdf) pdf.href = API + '/api/reports/certificate/pdf'; else pdf.removeAttribute('href');
  }
  function downloadCsv() {
    const rows = [['time', 'arsenic_ug_l', 'arsenic_mg_l', 'ph', 'conductivity_us_cm', 'turbidity_ntu', 'temperature_c', 'verdict', 'source']];
    state.history.slice().reverse().forEach((h) => rows.push([h.time.toISOString(), ugl(h.asMgL).toFixed(1), h.asMgL.toFixed(4), h.ph, h.ec, h.turb, h.temp, h.verdict, h.source]));
    const blob = new Blob([rows.map((r) => r.join(',')).join('\n')], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `AquaSentry_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ---------------- chat ----------------
  function addMsg(text, cls) {
    const d = document.createElement('div');
    d.className = 'msg ' + cls;
    d.textContent = text.replace(/\*\*/g, '').replace(/^#+\s/gm, '');
    $('chatLog').appendChild(d);
    $('chatLog').scrollTop = 1e6;
    return d;
  }
  function toggleChat(open) {
    const p = $('chatPanel');
    const show = open === undefined ? p.hidden : open;
    p.hidden = !show;
    $('chatFab').setAttribute('aria-expanded', show ? 'true' : 'false');
    if (show) { if (!$('chatLog').children.length) addMsg(t('chat.hello'), 'bot'); $('chatInput').focus(); }
  }
  async function sendChat(e) {
    e.preventDefault();
    const text = $('chatInput').value.trim();
    if (!text) return;
    $('chatInput').value = '';
    addMsg(text, 'user');
    if (!state.online) { addMsg(t('chat.offline'), 'bot'); return; }
    const wait = addMsg(t('chat.thinking'), 'bot wait');
    try {
      const msg = window.I18N.lang === 'hi' ? `Please answer in simple Hindi. ${text}` : text;
      const d = await api('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) }, 30000);
      wait.remove(); addMsg(d.reply || '…', 'bot');
    } catch (err) { wait.remove(); addMsg(t('chat.offline'), 'bot'); }
  }

  // ---------------- layout: menu, scroll spy, theme ----------------
  function setMenu(open) {
    $('rail').classList.toggle('open', open);
    $('railBackdrop').hidden = !open;
    $('menuBtn').setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function initScrollSpy() {
    const links = Array.from(document.querySelectorAll('.nav-link'));
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) links.forEach((l) => l.setAttribute('aria-current', l.dataset.section === en.target.id ? 'true' : 'false'));
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    document.querySelectorAll('main .section').forEach((s) => obs.observe(s));
    links.forEach((l) => l.addEventListener('click', () => setMenu(false)));
  }
  function toggleTheme() {
    const root = document.documentElement;
    const cur = root.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('aquasentry.theme', next); } catch (e) { /* ignore */ }
  }

  function rerenderAll() {
    renderConn();
    renderOverview();
    updateNetwork();
    renderContaminants();
    renderReport();
    drawChart();
    $('testAsOut').textContent = $('testAs').value + ' µg/L';
    if (!$('runTestBtn').disabled) $('runTestBtn').textContent = t('test.run');
  }

  // ---------------- init ----------------
  document.addEventListener('DOMContentLoaded', async () => {
    $('menuBtn').addEventListener('click', () => setMenu(!$('rail').classList.contains('open')));
    $('railBackdrop').addEventListener('click', () => setMenu(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { setMenu(false); toggleChat(false); } });
    $('themeBtn').addEventListener('click', toggleTheme);
    $('demoBtn').addEventListener('click', loadDemo);
    document.querySelectorAll('[data-quick]').forEach((b) => b.addEventListener('click', () => runTest(parseFloat(b.dataset.quick), { quiet: true })));
    $('testAs').addEventListener('input', () => { $('testAsOut').textContent = $('testAs').value + ' µg/L'; });
    $('runTestBtn').addEventListener('click', () => runTest(parseFloat($('testAs').value) / 1000));
    NN_IDS.forEach(([id]) => $(id).addEventListener('input', updateNetwork));
    document.querySelectorAll('[data-preset]').forEach((b) => b.addEventListener('click', () => {
      b.dataset.preset.split(',').map(Number).forEach((v, i) => { $(NN_IDS[i][0]).value = v; });
      updateNetwork();
    }));
    document.querySelectorAll('[data-model]').forEach((b) => b.addEventListener('click', () => {
      if (b.disabled) return;
      state.model = b.dataset.model;
      updateNetwork();
      renderOverview();
    }));
    $('csvBtn').addEventListener('click', downloadCsv);
    $('printBtn').addEventListener('click', () => window.print());
    $('chatFab').addEventListener('click', () => toggleChat());
    $('chatClose').addEventListener('click', () => toggleChat(false));
    $('chatForm').addEventListener('submit', sendChat);
    document.addEventListener('aquasentry:lang', rerenderAll);

    initScrollSpy();
    rerenderAll();
    if (await checkServer()) await loadLatestFromServer();
    setInterval(async () => { const was = state.online; await checkServer(); if (!was && state.online) loadLatestFromServer(); }, 30000);
  });
})();
