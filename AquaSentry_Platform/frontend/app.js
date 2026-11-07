/**
 * AquaSentry dashboard controller (v5).
 * Works fully offline (simulated tests, AquaNet in the browser) and uses the FastAPI server when it is running.
 * Page chrome (theme, menu, connection pill, chat, effects) lives in shell.js.
 */
(function () {
  'use strict';

  const t = (k, v) => window.I18N.t(k, v);
  const $ = (id) => document.getElementById(id);
  const UI = () => window.AquaUI;
  const DEVICE = 'AQUA-001';
  const CAL = { slope: 0.8563, intercept: 0.0096, peakMv: -800, windowMv: 60, excludeMv: 105 };
  const TONE_HEX = { none: '#3B82F6', Safe: '#34D399', Caution: '#F59E0B', Unsafe: '#FB923C', Hazardous: '#F43F5E' };
  const CONTACT_KEY = 'aquasentry.contacts';

  const state = {
    reading: null,       // {asMgL, ph, ec, turb, temp, battery, lat, lon, time, source, savedOnServer}
    history: [],
    model: (window.AquaNet && window.AquaNet.hasV3) ? 'v3' : 'v1',
    lastTrace: null,
    fx: null,
    device: null,
  };
  const online = () => !!(UI() && UI().online);
  const api = (...a) => UI().api(...a);

  function fmtTime(d) {
    const lang = window.I18N.lang === 'hi' ? 'hi-IN' : 'en-IN';
    try { return d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' }); } catch (e) { return d.toTimeString().slice(0, 5); }
  }
  function fmtDateTime(d) {
    const lang = window.I18N.lang === 'hi' ? 'hi-IN' : 'en-IN';
    try { return d.toLocaleString(lang, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch (e) { return d.toISOString(); }
  }
  function ugl(mgL) { return mgL * 1000; }
  function fmtUgNum(u) { return u < 10 ? u.toFixed(1) : Math.round(u).toString(); }
  function fmtUg(mgL) { return fmtUgNum(ugl(mgL)); }

  const ICONS = {
    none: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3"><path d="M28 7C21 17 15 24 15 31a13 13 0 0 0 26 0c0-7-6-14-13-24Z"/></svg>',
    Safe: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="28" cy="28" r="24"/><path d="M17 29l7 7 15-16"/></svg>',
    Caution: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M28 5L52 48H4Z"/><path d="M28 21v13M28 41v1"/></svg>',
    Unsafe: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round"><circle cx="28" cy="28" r="24"/><path d="M19 19l18 18M37 19L19 37"/></svg>',
    Hazardous: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 4h20l14 14v20L38 52H18L4 38V18Z"/><path d="M28 16v16M28 40v1"/></svg>',
  };

  // ---------------- readings ----------------
  // Sensors that are not fitted stay null (shown as "not measured"); the model still needs a number,
  // so typical values are used for the vote only, exactly like the ESP32 firmware does.
  const TYPICAL = { ph: 7.2, ec: 400, turb: 2.0, temp: 24 };
  const val = (r, k) => (r[k] == null ? TYPICAL[k] : r[k]);
  function evaluate(r) { return window.AquaNet.evaluate(r.asMgL, val(r, 'ph'), val(r, 'ec'), val(r, 'turb'), val(r, 'temp'), state.model); }
  // A "Safe" vote with arsenic below the 20 µg/L LOD is shown as "No arsenic detected", never "Safe to drink":
  // the sensor cannot see the 10 µg/L limit.
  function verdictKey(res) { return res.final === 'Safe' && res.belowLod ? 'Clear' : res.final; }
  function setReading(r, opts) {
    state.reading = r;
    const res = evaluate(r);
    r.verdict = res.final;
    if (!opts || !opts.noHistory) {
      state.history.unshift({ time: r.time, asMgL: r.asMgL, verdict: res.final, source: r.source, ph: r.ph, ec: r.ec, turb: r.turb, temp: r.temp });
      state.history = state.history.slice(0, 50);
    }
    renderOverview();
    syncNetworkInputs(r);
    renderReport();
    renderDispatch();
  }

  function stripPercent(u) {
    // piecewise scale matching the verdict edges: 0-10 -> 0-20%, 10-20 (below LOD) -> 20-35%,
    // 20-150 (detected = above IS 10500) -> 35-75%, 150-300 -> 75-100%
    const seg = [[0, 10, 0, 20], [10, 20, 20, 35], [20, 150, 35, 75], [150, 300, 75, 100]];
    const v = Math.max(0, Math.min(300, u));
    for (const [a, b, p, q] of seg) if (v <= b) return p + (v - a) / (b - a) * (q - p);
    return 100;
  }

  // ---------------- ring gauge ----------------
  const RING = { cx: 120, cy: 120, r: 92, start: -135, sweep: 270 };
  function polar(deg, r) { const rad = deg * Math.PI / 180; return [RING.cx + r * Math.sin(rad), RING.cy - r * Math.cos(rad)]; }
  function arcPath(f0, f1, r) {
    r = r || RING.r;
    const a = RING.start + RING.sweep * f0, b = RING.start + RING.sweep * f1;
    const [x0, y0] = polar(a, r), [x1, y1] = polar(b, r);
    return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${r} ${r} 0 ${(b - a) > 180 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
  }
  function initRing() {
    const NS = 'http://www.w3.org/2000/svg';
    $('ringTrack').setAttribute('d', arcPath(0, 1));
    $('ringVal').setAttribute('d', arcPath(0, 1));
    $('ringBands').innerHTML = '';
    [[0, 0.2, '#34D399'], [0.2, 0.35, '#FBBF24'], [0.35, 0.75, '#FB923C'], [0.75, 1, '#F43F5E']].forEach(([a, b, c]) => {
      const p = document.createElementNS(NS, 'path');
      p.setAttribute('d', arcPath(a + 0.004, b - 0.004, RING.r + 17)); p.setAttribute('class', 'ring-band'); p.setAttribute('stroke', c);
      p.style.strokeWidth = '4'; p.style.opacity = '.85'; p.style.strokeLinecap = 'round';
      $('ringBands').appendChild(p);
    });
    $('ringTicks').innerHTML = '';
    [[0, '0'], [0.2, '10'], [0.35, '20'], [0.75, '150'], [1, '300']].forEach(([f, lab]) => {
      const [tx, ty] = polar(RING.start + RING.sweep * f, RING.r - 24);
      const text = document.createElementNS(NS, 'text');
      text.setAttribute('x', tx.toFixed(1)); text.setAttribute('y', (ty + 4).toFixed(1)); text.setAttribute('text-anchor', 'middle'); text.setAttribute('class', 'ring-tick-l');
      text.textContent = lab; $('ringTicks').appendChild(text);
    });
    const len = $('ringVal').getTotalLength();
    $('ringVal').style.strokeDasharray = len; $('ringVal').style.strokeDashoffset = len;
    state.ringLen = len;
  }
  function setRing(u) {
    if (!state.ringLen) return;
    const f = u == null ? 0 : stripPercent(u) / 100;
    $('ringVal').style.strokeDashoffset = state.ringLen * (1 - Math.max(0.004, f));
    const el = $('ringNum');
    if (u == null) { el.textContent = '–'; el._v = 0; return; }
    UI().countTo(el, u, fmtUgNum, 1300);
  }

  function renderOverview() {
    const r = state.reading;
    const v = $('verdict');
    if (!r) {
      v.dataset.tone = 'none';
      $('verdictIcon').innerHTML = ICONS.none;
      $('verdictBadge').textContent = t('verdict.badge.none');
      $('verdictTitle').textContent = t('verdict.none.title');
      $('verdictAction').textContent = t('verdict.none.action');
      $('verdictTime').textContent = '';
      $('asValue').textContent = '–';
      $('asMgl').textContent = '';
      $('stripPin').hidden = true;
      $('labNote').hidden = true;
      $('alertBanner').hidden = true;
      $('ovMeta').textContent = t('ov.device', { code: DEVICE });
      setRing(null);
      if (state.fx) state.fx.setColor(TONE_HEX.none);
      renderReadingsGrid(null);
      return;
    }
    const res = evaluate(r);
    const vk = verdictKey(res);
    v.dataset.tone = res.final;
    $('verdictIcon').innerHTML = vk === 'Clear' ? ICONS.none : ICONS[res.final];
    $('verdictBadge').textContent = t('class.' + vk);
    const vt = t('verdict.' + vk + '.title');
    if ($('verdictTitle').textContent !== vt) { if (window.AquaMotion) window.AquaMotion.decode($('verdictTitle'), vt, 650); else $('verdictTitle').textContent = vt; }
    $('verdictAction').textContent = t('verdict.' + vk + '.action');
    $('verdictTime').textContent = fmtTime(r.time);
    UI().countTo($('asValue'), ugl(r.asMgL), fmtUgNum, 1200);
    $('asMgl').textContent = t('ov.mgl', { v: r.asMgL.toFixed(4) });
    const pin = $('stripPin');
    pin.hidden = false;
    pin.style.left = stripPercent(ugl(r.asMgL)) + '%';
    $('stripPinLabel').textContent = fmtUg(r.asMgL) + ' µg/L';
    setRing(ugl(r.asMgL));
    if (state.fx) state.fx.setColor(TONE_HEX[res.final]);
    if (state.device) state.device.setRim(TONE_HEX[res.final]);

    const why = $('whyList');
    why.innerHTML = '';
    res.reasons.filter((x) => x.code !== 'LOD').forEach((x) => {
      const li = document.createElement('li');
      li.textContent = t('reason.' + x.code, { v: x.v });
      why.appendChild(li);
    });
    $('labNote').hidden = !res.belowLod;
    $('labNote').textContent = t('ov.labNote');

    // alert banner
    const b = $('alertBanner');
    b.hidden = false;
    b.className = 'alert-banner' + (res.final === 'Safe' ? ' ok' : res.final === 'Caution' ? ' warn' : '');
    $('alertTitle').textContent = t('alert.' + vk + '.t');
    $('alertText').textContent = t('alert.' + vk + '.d');
    $('alertBtn1').hidden = res.final === 'Safe';
    $('alertBtn2').hidden = res.final === 'Safe' || res.final === 'Caution';

    const src = t('ov.source.' + r.source);
    $('ovMeta').textContent = `${t('ov.device', { code: r.device || DEVICE })}, ${t('ov.lastReading', { time: fmtTime(r.time) })} (${src})`;
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
      const val = r ? (r[d.key] ?? null) : null;
      const pct = (x) => Math.max(0, Math.min(100, (x - d.min) / (d.max - d.min) * 100));
      const okBand = d.ok ? `<div class="gauge-ok" style="left:${pct(d.ok[0])}%;width:${pct(d.ok[1]) - pct(d.ok[0])}%"></div>` : '';
      const dot = val !== null ? `<div class="gauge-dot" style="left:${pct(val)}%"></div>` : '';
      const inRange = val === null || !d.ok || (val >= d.ok[0] && val <= d.ok[1]);
      const st = val === null || !d.ok ? '' : `<span class="reading-state ${inRange ? 'ok' : 'bad'}">${t(inRange ? 'read.ok' : 'read.bad')}</span>`;
      return `<div class="card reading spot">
        <div class="reading-name">${t(d.label)}</div>
        <div class="reading-val">${val === null ? '–' : d.fmt(val)}${d.unit ? `<small>${d.unit}</small>` : ''}</div>
        <div class="gauge">${okBand}${dot}</div>
        <div class="reading-foot"><span>${t(d.good)}</span>${st}</div>
      </div>`;
    }).join('');
    const line = $('deviceLine');
    if (r && (r.battery != null || r.lat != null)) {
      const parts = [];
      if (r.battery != null) parts.push(`${t('read.battery')} ${Math.round(r.battery)}%`);
      if (r.lat != null) parts.push(`${t('read.location')} ${r.lat.toFixed(2)}°N, ${r.lon.toFixed(2)}°E`);
      line.textContent = parts.join('   ·   ');
    } else line.textContent = '';
  }

  // ---------------- server data ----------------
  async function loadLatestFromServer(code) {
    code = code || DEVICE;
    try {
      const d = await api(`/api/readings/latest?device_code=${encodeURIComponent(code)}`);
      setReading({
        device: code,
        asMgL: (d.arsenic_ppb || 0) / 1000, ph: d.ph ?? null, ec: d.conductivity_us_cm ?? null, turb: d.turbidity_ntu ?? null,
        temp: d.temperature_c ?? null, battery: d.battery_pct, lat: d.latitude, lon: d.longitude,
        time: d.recorded_at ? new Date(d.recorded_at.endsWith('Z') || d.recorded_at.includes('+') ? d.recorded_at : d.recorded_at + 'Z') : new Date(),
        source: d.is_simulated === false || d.source_type === 'hardware' ? 'device' : 'demo', savedOnServer: true,
      });
      return true;
    } catch (e) { return false; }
  }
  async function loadDemo() {
    if (online()) {
      try { await api('/api/demo/load', { method: 'POST' }, 6000); if (await loadLatestFromServer('DEMO-BOT-01')) return; } catch (e) { /* fall through */ }
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
    if (online()) {
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
    if (online()) {
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
    const add = (name, attrs, text, parent) => { const e = document.createElementNS(NS, name); Object.keys(attrs).forEach((k) => e.setAttribute(k, attrs[k])); if (text !== undefined) e.textContent = text; (parent || svg).appendChild(e); return e; };
    const prim = UI().cssVar('--primary') || '#2DD4BF', vio = UI().cssVar('--violet') || '#818CF8';
    const defs = add('defs', {});
    const lg = add('linearGradient', { id: 'vgGrad', x1: 0, y1: 0, x2: 1, y2: 0 }, undefined, defs);
    add('stop', { offset: '0%', 'stop-color': prim }, undefined, lg); add('stop', { offset: '100%', 'stop-color': vio }, undefined, lg);
    const ag = add('linearGradient', { id: 'vgArea', x1: 0, y1: 0, x2: 0, y2: 1 }, undefined, defs);
    add('stop', { offset: '0%', 'stop-color': prim, 'stop-opacity': 0.28 }, undefined, ag); add('stop', { offset: '100%', 'stop-color': prim, 'stop-opacity': 0 }, undefined, ag);
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
      add('line', { x1: L, x2: R, y1: Y(v), y2: Y(v), class: 'vg-grid', 'stroke-dasharray': '3 5' });
      add('text', { x: L - 8, y: Y(v) + 4, 'text-anchor': 'end', class: 'vg-tick' }, (Math.abs(v) < 1e-9 ? 0 : v).toFixed(step < 0.1 ? 2 : 1));
    }
    for (let p = -1100; p <= -500; p += 100) add('text', { x: X(p), y: B + 20, 'text-anchor': 'middle', class: 'vg-tick' }, String(p));
    add('line', { x1: L, x2: R, y1: B, y2: B, class: 'vg-axis' });
    add('text', { x: (L + R) / 2, y: B + 44, 'text-anchor': 'middle', class: 'vg-title' }, t('test.chart.x'));
    add('text', { x: 16, y: (T + B) / 2, 'text-anchor': 'middle', class: 'vg-title', transform: `rotate(-90 16 ${(T + B) / 2})` }, t('test.chart.y'));
    const path = (arr) => arr.map((c, i) => `${i ? 'L' : 'M'}${X(P[i]).toFixed(1)} ${Y(c).toFixed(1)}`).join(' ');
    add('path', { d: `${path(out.S)} L${X(P[P.length - 1]).toFixed(1)} ${B} L${X(P[0]).toFixed(1)} ${B} Z`, class: 'vg-area' });
    add('path', { d: path(C), class: 'vg-raw' });
    add('path', { d: path(out.base), class: 'vg-base' });
    const sm = add('path', { d: path(out.S), class: 'vg-smooth' });
    try { sm.style.setProperty('--len', Math.ceil(sm.getTotalLength())); } catch (e) { /* ignore */ }
    if (out.peakIdx >= 0) {
      const px = X(out.peakMv);
      add('line', { x1: px, x2: px, y1: Y(out.base[out.peakIdx]), y2: Y(out.S[out.peakIdx]), class: 'vg-peak', 'stroke-dasharray': '2 3' });
      add('circle', { cx: px, cy: Y(out.S[out.peakIdx]), r: 6, class: 'vg-peak-dot' });
      add('text', { x: px + 10, y: Y(out.S[out.peakIdx]) - 10, class: 'vg-peak-label' }, `${t('test.peak')} ${out.net.toFixed(3)} µA`);
    }
  }
  function niceStep(raw) { const p = Math.pow(10, Math.floor(Math.log10(raw))); const f = raw / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; }

  // ---------------- AquaNet panel ----------------
  const NN_IDS = [['nnAs', 'nnOutAs', (v) => `${(v * 1000).toFixed(0)} µg/L`], ['nnPh', 'nnOutPh', (v) => v.toFixed(2)], ['nnEc', 'nnOutEc', (v) => `${Math.round(v)} µS/cm`], ['nnTurb', 'nnOutTurb', (v) => `${v.toFixed(1)} NTU`], ['nnTemp', 'nnOutTemp', (v) => `${v.toFixed(1)} °C`]];
  function nnValues() { return NN_IDS.map(([id]) => parseFloat($(id).value)); }
  function syncNetworkInputs(r) {
    const vals = [Math.min(0.3, r.asMgL), val(r, 'ph'), val(r, 'ec'), Math.min(25, val(r, 'turb')), val(r, 'temp')];
    NN_IDS.forEach(([id], i) => { $(id).value = vals[i]; UI().fillRange($(id)); });
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
    const colors = { Safe: 'var(--safe)', Caution: 'var(--caution-fill)', Unsafe: 'var(--unsafe)', Hazardous: 'var(--haz)' };
    $('nnBars').innerHTML = window.AquaNet.CLASSES.map((c, i) => {
      const p = (res.probs[i] * 100);
      return `<div class="bar-row"><span>${t('class.' + c)}</span><div class="bar"><i style="width:${p.toFixed(1)}%;background:${colors[c]};color:${colors[c]}"></i></div><span class="bar-pct">${p.toFixed(1)}%</span></div>`;
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
    { id: 'arsenic', f: 'As(III) / As(V)', status: 'supported_screening', lod: '20 µg/L', bis: '10 µg/L (no relaxation)', method: 'Anodic stripping voltammetry (MAS-G1)' },
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

  // ---------------- authorities: incident report + contacts ----------------
  function loadContacts() { try { return JSON.parse(localStorage.getItem(CONTACT_KEY) || '{}'); } catch (e) { return {}; } }
  function saveContacts() {
    const c = { office: $('cOffice').value.trim(), phone: $('cPhone').value.trim(), email: $('cEmail').value.trim() };
    try { localStorage.setItem(CONTACT_KEY, JSON.stringify(c)); $('cSaved').textContent = t('auth.mine.saved'); } catch (e) { $('cSaved').textContent = t('auth.mine.nosave'); }
    renderDispatch();
  }
  function reportRows() {
    const r = state.reading;
    if (!r) return null;
    const res = evaluate(r);
    return [
      ['auth.f.station', `${r.device || DEVICE} (${t('auth.f.stationType')})`],
      ['auth.f.contaminant', t('auth.f.arsenicTotal')],
      ['auth.f.reading', `${r.asMgL.toFixed(4)} mg/L (${fmtUg(r.asMgL)} µg/L)`],
      ['auth.f.limits', 'WHO 10 µg/L · IS 10500: 10 µg/L (no relaxation since 2015)'],
      ['auth.f.tier', `${t('class.' + verdictKey(res))} — ${t('verdict.' + verdictKey(res) + '.title')}`],
      ['auth.f.other', [
        r.ph == null ? null : `pH ${r.ph.toFixed(2)}`, r.ec == null ? null : `${Math.round(r.ec)} µS/cm`,
        r.turb == null ? null : `${r.turb.toFixed(1)} NTU`, r.temp == null ? null : `${r.temp.toFixed(1)} °C`,
      ].filter(Boolean).join(' · ') || t('auth.f.notMeasured')],
      ['auth.f.method', t('auth.f.methodVal')],
      ['auth.f.geotag', r.lat != null ? `${r.lat.toFixed(4)}°N, ${r.lon.toFixed(4)}°E` : t('auth.f.noGps')],
      ['auth.f.time', fmtDateTime(r.time)],
    ];
  }
  function reportText() {
    const rows = reportRows();
    if (!rows) return '';
    return `${t('auth.mail.subject', { code: (state.reading && state.reading.device) || DEVICE })}\n\n${t('auth.mail.intro')}\n\n` +
      rows.map(([k, v]) => `${t(k)}: ${v}`).join('\n') + `\n\n${t('auth.mail.ask')}\n\n${t('auth.mail.note')}`;
  }
  function renderDispatch() {
    const rows = reportRows();
    const st = $('dispatchStatus');
    const c = loadContacts();
    if (!rows) {
      $('dispatchBody').innerHTML = `<dt>—</dt><dd>${t('auth.empty')}</dd>`;
      st.className = 'tag'; st.textContent = t('auth.status.none');
      ['dEmail', 'dCopy', 'dShare', 'dPrint'].forEach((id) => $(id).setAttribute('aria-disabled', 'true'));
    } else {
      $('dispatchBody').innerHTML = rows.map(([k, v]) => `<dt>${t(k)}</dt><dd>${v.replace(/</g, '&lt;')}</dd>`).join('');
      const res = evaluate(state.reading);
      const urgent = res.final === 'Unsafe' || res.final === 'Hazardous';
      st.className = 'tag ' + (urgent ? 'tone-haz' : res.final === 'Caution' ? 'tone-caution' : 'active');
      st.textContent = t(urgent ? 'auth.status.urgent' : res.final === 'Caution' ? 'auth.status.watch' : 'auth.status.ok');
      ['dEmail', 'dCopy', 'dShare', 'dPrint'].forEach((id) => $(id).removeAttribute('aria-disabled'));
      const subject = encodeURIComponent(t('auth.mail.subject', { code: (state.reading && state.reading.device) || DEVICE }) + ' — ' + t('class.' + res.final));
      $('dEmail').href = `mailto:${encodeURIComponent(c.email || '')}?subject=${subject}&body=${encodeURIComponent(reportText())}`;
    }
    // directory buttons that use saved contacts
    const call = $('dirCallLocal'), mail = $('dirEmailLocal');
    if (c.phone) { call.href = 'tel:' + c.phone.replace(/[^\d+]/g, ''); call.textContent = t('dir.call') + ' ' + c.phone; } else { call.href = '#contactsBox'; call.textContent = t('dir.addNumber'); }
    if (c.email) { mail.href = $('dEmail').getAttribute('href') || ('mailto:' + c.email); mail.textContent = t('dir.email'); } else { mail.href = '#contactsBox'; mail.textContent = t('dir.addEmail'); }
    $('dShare').hidden = !navigator.share;
  }
  function flash(msg) { const m = $('dispatchMsg'); m.textContent = msg; clearTimeout(m._t); m._t = setTimeout(() => { m.textContent = ''; }, 4000); }
  async function copyReport() {
    const text = reportText(); if (!text) return;
    try { await navigator.clipboard.writeText(text); flash(t('auth.copied')); }
    catch (e) {
      const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); flash(t('auth.copied')); } catch (err) { flash(t('auth.copyFail')); }
      ta.remove();
    }
  }
  function printReport() {
    const rows = reportRows(); if (!rows) return;
    const w = window.open('', '_blank', 'width=760,height=900');
    if (!w) { window.print(); return; }
    const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
    w.document.write(`<!doctype html><html lang="${window.I18N.lang}"><head><meta charset="utf-8"><title>${esc(t('auth.report.t'))}</title>
      <style>body{font-family:system-ui,'Segoe UI',sans-serif;margin:40px;color:#111}h1{font-size:22px;margin:0 0 4px}p{color:#444}
      table{border-collapse:collapse;width:100%;margin-top:20px}td{border:1px solid #ccc;padding:10px;vertical-align:top}td:first-child{width:34%;font-weight:600;background:#f4f6f8}
      .foot{margin-top:24px;font-size:13px;color:#555}</style></head><body>
      <h1>AquaSentry — ${esc(t('auth.report.t'))}</h1><p>${esc(t('auth.mail.intro'))}</p>
      <table>${rows.map(([k, v]) => `<tr><td>${esc(t(k))}</td><td>${esc(v)}</td></tr>`).join('')}</table>
      <p class="foot">${esc(t('auth.mail.ask'))}<br><br>${esc(t('auth.mail.note'))}</p></body></html>`);
    w.document.close(); w.focus(); setTimeout(() => w.print(), 300);
  }

  // ---------------- report ----------------
  function renderReport() {
    const body = $('repTable').querySelector('tbody');
    body.innerHTML = state.history.length ? state.history.map((h) => `<tr>
      <td>${fmtTime(h.time)}</td><td class="num">${fmtUg(h.asMgL)}</td>
      <td><span class="tone-${h.verdict}" style="font-weight:700">${t('class.' + h.verdict)}</span></td><td>${t('ov.source.' + h.source)}</td></tr>`).join('')
      : `<tr class="empty-row"><td colspan="4">${t('rep.empty')}</td></tr>`;
    const pdf = $('pdfBtn');
    const canPdf = online() && state.reading && state.reading.savedOnServer;
    pdf.setAttribute('aria-disabled', canPdf ? 'false' : 'true');
    pdf.textContent = t(canPdf ? 'rep.pdf' : 'rep.pdfOff');
    if (canPdf) pdf.href = UI().API + '/api/reports/certificate/pdf'; else pdf.removeAttribute('href');
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

  // ---------------- device 3D + sparklines ----------------
  function deviceLabels() { return { lid: t('dev.p.lid'), base: t('dev.p.base'), well: t('dev.p.well'), strainer: t('dev.p.strainer') }; }
  function initDevice() {
    if (!window.AquaDevice3D || state.device !== null) return;
    state.device = window.AquaDevice3D.mount($('viewer3d'), { labels: deviceLabels(), fallback: t('dev.noWebgl') }) || false;
    $('explodeBtn').addEventListener('click', () => {
      if (!state.device) return;
      state.device.explode(!state.device.exploded);
      $('explodeBtn').textContent = t(state.device.exploded ? 'dev.assemble' : 'dev.explode');
    });
  }
  function drawSparks() {
    if (!window.AquaCharts) return;
    window.AquaCharts.spark($('sparkMarket'), [2.1, 2.6, 3.4, 4.2, 5.1, 5.9, 6.6, 7.5], 'var(--primary)');
    window.AquaCharts.spark($('sparkSales'), [2.2, 6, 11, 19.1, 26, 33, 38, 41.1], 'var(--violet)');
    const tr = synthTrace(0.06); window.AquaCharts.spark($('sparkDevice'), tr.C.map((c) => c + 0.2), 'var(--primary-2)');
  }

  function rerenderAll() {
    renderOverview();
    updateNetwork();
    renderContaminants();
    renderReport();
    renderDispatch();
    drawChart();
    drawSparks();
    $('testAsOut').textContent = $('testAs').value + ' µg/L';
    if (!$('runTestBtn').disabled) $('runTestBtn').textContent = t('test.run');
    if (state.device) { state.device.setLabels(deviceLabels()); $('explodeBtn').textContent = t(state.device.exploded ? 'dev.assemble' : 'dev.explode'); }
  }

  // ---------------- init ----------------
  document.addEventListener('DOMContentLoaded', () => {
    $('demoBtn').addEventListener('click', loadDemo);
    document.querySelectorAll('[data-quick]').forEach((b) => b.addEventListener('click', () => runTest(parseFloat(b.dataset.quick), { quiet: true })));
    $('testAs').addEventListener('input', () => { $('testAsOut').textContent = $('testAs').value + ' µg/L'; });
    $('runTestBtn').addEventListener('click', () => runTest(parseFloat($('testAs').value) / 1000));
    NN_IDS.forEach(([id]) => $(id).addEventListener('input', updateNetwork));
    document.querySelectorAll('[data-preset]').forEach((b) => b.addEventListener('click', () => {
      b.dataset.preset.split(',').map(Number).forEach((v, i) => { $(NN_IDS[i][0]).value = v; UI().fillRange($(NN_IDS[i][0])); });
      updateNetwork();
    }));
    document.querySelectorAll('[data-model]').forEach((b) => b.addEventListener('click', () => {
      if (b.disabled) return;
      state.model = b.dataset.model;
      updateNetwork(); renderOverview(); renderDispatch();
    }));
    $('csvBtn').addEventListener('click', downloadCsv);
    $('printBtn').addEventListener('click', () => window.print());
    $('dCopy').addEventListener('click', copyReport);
    $('dPrint').addEventListener('click', printReport);
    $('dShare').addEventListener('click', () => { const text = reportText(); if (text && navigator.share) navigator.share({ title: t('auth.report.t'), text }).catch(() => {}); });
    $('dEmail').addEventListener('click', (e) => { if ($('dEmail').getAttribute('aria-disabled') === 'true') e.preventDefault(); });
    const c = loadContacts();
    $('cOffice').value = c.office || ''; $('cPhone').value = c.phone || ''; $('cEmail').value = c.email || '';
    $('cSave').addEventListener('click', saveContacts);
    document.querySelectorAll('a[href="#contactsBox"]').forEach((a) => a.addEventListener('click', () => { $('contactsBox').open = true; }));
    $('dirCallLocal').addEventListener('click', () => { if ($('dirCallLocal').getAttribute('href') === '#contactsBox') $('contactsBox').open = true; });
    $('dirEmailLocal').addEventListener('click', () => { if ($('dirEmailLocal').getAttribute('href') === '#contactsBox') $('contactsBox').open = true; });
    document.addEventListener('aquasentry:lang', rerenderAll);
    document.addEventListener('aquasentry:theme', () => { drawChart(); drawSparks(); });
    document.addEventListener('aquasentry:online', (e) => { renderReport(); if (e.detail.online) loadLatestFromServer(); });

    const canvas = $('heroFx');
    if (canvas && UI().WaterFX) { state.fx = new (UI().WaterFX)(canvas); if (!state.fx.ok) state.fx = null; }
    initRing();
    rerenderAll();
    initDevice();
  });
})();
