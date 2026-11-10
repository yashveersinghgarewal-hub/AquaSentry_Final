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
  const SIM_DEVICE = 'SIM-DASHBOARD';   // v5.7: dashboard practice tests never share a code with a real device
  const REPLAY_DEVICE = 'REPLAY-FILE';  // v5.8: recorded instrument files replayed through the server pipeline
  // windowMv: where the peak is expected; searchMv: how far it is searched (v5.7, same as app/standards.py)
  // v5.8: the trace maths lives in asv.js (a checked port of app/signal_processing.py); the server's answer wins online
  const ASV = window.AquaASV;
  const CAL = ASV.CAL;
  const STALE_MIN = 120;                // a node reports hourly; older than 2 h = possibly offline
  const TONE_HEX = { none: '#3B82F6', Safe: '#34D399', Caution: '#F59E0B', Unsafe: '#FB923C', Hazardous: '#F43F5E', Clear: '#3B82F6', Failed: '#F43F5E', Retest: '#F59E0B' };
  const CONTACT_KEY = 'aquasentry.contacts';

  const state = {
    reading: null,       // {asMgL, ph, ec, turb, temp, battery, lat, lon, time, source, savedOnServer}
    histHours: 720,
    histDevice: null,    // null = all devices
    history: [],
    model: (window.AquaNet && window.AquaNet.hasV3) ? 'v3' : 'v1',
    lastTrace: null,
    fx: null,
    device: null,
  };
  const online = () => !!(UI() && UI().online);
  /** Apply data-left / data-width (percent) and data-color set in HTML templates, through the CSSOM. */
  function applyGeometry(root) {
    (root || document).querySelectorAll('[data-left],[data-width],[data-color]').forEach((e) => {
      if (e.dataset.left != null) e.style.left = e.dataset.left + '%';
      if (e.dataset.width != null) e.style.width = e.dataset.width + '%';
      if (e.dataset.color != null) { e.style.background = e.dataset.color; e.style.color = e.dataset.color; }
    });
  }
  const api = (...a) => UI().api(...a);

  function fmtTime(d) {
    const lang = ({ hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', pa: 'pa-IN' })[window.I18N.lang] || 'en-IN';
    try { return d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' }); } catch (e) { return d.toTimeString().slice(0, 5); }
  }
  function fmtDateTime(d) {
    const lang = ({ hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', pa: 'pa-IN' })[window.I18N.lang] || 'en-IN';
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
    Failed: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="44" height="44" rx="6"/><path d="M19 19l18 18M37 19L19 37"/></svg>',
    Retest: '<svg viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M46 28a18 18 0 1 1-5.3-12.7"/><path d="M46 8v10H36"/></svg>',
  };

  // ---------------- readings ----------------
  // v5.7: sensors that are not fitted stay null all the way through: the model gets a neutral input and their
  // rule is skipped (neural.js), and nothing is assumed or shown for them (was: typical values for the vote).
  const nn = (v) => (v === undefined ? null : v);
  function evaluate(r) { return window.AquaNet.evaluate(r.asMgL, nn(r.ph), nn(r.ec), nn(r.turb), nn(r.temp), state.model); }
  const SERVER_KEY = { 'Below Sensor LOD': 'Clear', 'Test Failed': 'Failed' };
  // What the screen shows. A failed test is "Test failed" (never a clean result). Below the 20 µg/L LOD a "Safe"
  // vote is "Not detected: not confirmed safe", never "Safe to drink". A verdict stored by the server wins,
  // because it includes the scan QC, check-standard and calibration checks the browser cannot see.
  // Is the verdict driven by something other than arsenic (pH, turbidity, conductivity, out-of-range input)?
  const nonArsenicIssue = (res) => res.reasons.some((x) => /^(PH_|TURB_|EC_|OOB)/.test(x.code));
  /** v5.8 (review item 04): the ONE screening outcome. From the server when it stored the reading (it includes
   *  the scan QC, check-standard and calibration checks); otherwise from the local value and its uncertainty. */
  function outcomeOf(r) {
    if (!r) return null;
    if (r.failed) return 'invalid';
    if (r.outcome) return r.outcome;
    const ug = ugl(r.asMgL), u = r.uncertaintyUg != null && r.uncertaintyUg > 0 ? r.uncertaintyUg : 10;
    return ug >= CAL.lodUg ? 'screen_positive' : ug >= CAL.lodUg - u ? 'retest' : 'not_detected';
  }
  function verdictKey(res, r) {
    r = r || state.reading;
    if (r && r.failed) return 'Failed';
    const oc = outcomeOf(r);
    if (r && r.serverLabel && (SERVER_KEY[r.serverLabel] || res.final !== r.serverLabel)) {
      const k = SERVER_KEY[r.serverLabel] || r.serverLabel;
      if (k === 'Failed') return k;
      // the stored class says Caution / Below LOD for arsenic alone: show the outcome instead
      if (!nonArsenicIssue(res) && (k === 'Clear' || k === 'Caution' || k === 'Safe')) return oc === 'retest' ? 'Retest' : oc === 'not_detected' ? 'Clear' : k;
      if (ICONS[k] || k === 'Clear') return k;
    }
    if (!nonArsenicIssue(res) && (res.final === 'Safe' || res.final === 'Caution')) {
      if (oc === 'retest') return 'Retest';
      if (oc === 'not_detected') return 'Clear';
    }
    return res.final === 'Safe' && res.belowLod ? 'Clear' : res.final;
  }
  const paintKey = (vk) => vk;
  function belowLod(r) { return ugl(r.asMgL) < CAL.lodUg; }
  function setReading(r, opts) {
    state.reading = r;
    const res = evaluate(r);
    const vk = verdictKey(res, r);
    r.verdict = vk === 'Failed' ? 'Test Failed' : vk === 'Clear' ? 'Below Sensor LOD' : vk === 'Retest' ? 'Caution' : res.final;
    if (!opts || !opts.noHistory) {
      state.history.unshift({ time: r.time, asMgL: r.asMgL, verdict: r.verdict, source: r.source, ph: r.ph, ec: r.ec, turb: r.turb, temp: r.temp });
      state.history = state.history.slice(0, 50);
    }
    renderOverview();
    syncNetworkInputs(r);
    renderReport();
    renderDispatch();
    loadFleet();
  }

  // The colour chart: seven printed swatches like a field test kit. A value sits on the centre of its swatch
  // and in between it moves linearly, so 10 / 20 / 150 µg/L (the verdict edges) line up with swatch centres.
  const KIT = [0, 10, 20, 50, 100, 150, 300];
  const KIT_RGB = [[250, 246, 228], [243, 227, 155], [230, 197, 90], [208, 154, 53], [172, 106, 40], [134, 70, 32], [87, 48, 26]];
  function kitIndex(u) {   // fractional swatch index 0..6
    const v = Math.max(0, Math.min(300, u));
    for (let i = 1; i < KIT.length; i++) if (v <= KIT[i]) return i - 1 + (v - KIT[i - 1]) / (KIT[i] - KIT[i - 1]);
    return KIT.length - 1;
  }
  function stripPercent(u) { return (kitIndex(u) + 0.5) / KIT.length * 100; }
  function kitColour(u) {   // the colour a test strip would turn, interpolated between swatches
    const f = kitIndex(u), i = Math.min(KIT.length - 2, Math.floor(f)), w = f - i;
    const c = KIT_RGB[i].map((x, k) => Math.round(x + (KIT_RGB[i + 1][k] - x) * w));
    return `rgb(${c.join(',')})`;
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
    if (!$('ringTrack')) return;   // v5.3 layout has no ring gauge
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
    const vk = verdictKey(res, r);
    v.dataset.tone = paintKey(vk);   // "not detected" gets its own paint, never the "safe" green; failed is red
    $('verdictIcon').innerHTML = vk === 'Clear' ? ICONS.none : (ICONS[vk] || ICONS[res.final]);
    $('verdictBadge').textContent = t('class.' + vk);
    renderOutcome(r, vk);
    const vt = t('verdict.' + vk + '.title');
    if ($('verdictTitle').textContent !== vt) { if (window.AquaMotion) window.AquaMotion.decode($('verdictTitle'), vt, 650); else $('verdictTitle').textContent = vt; }
    $('verdictAction').textContent = t('verdict.' + vk + '.action');
    $('verdictTime').textContent = fmtTime(r.time);
    // v5.7: below the detection limit the number is noise, so it is shown as "< 20"; a failed test shows no number
    const failed = vk === 'Failed', low = !failed && belowLod(r);
    const shownUg = failed ? null : low ? CAL.lodUg : ugl(r.asMgL);
    if (failed) { $('asValue').textContent = '–'; $('asValue')._v = 0; }
    else if (low) { $('asValue').textContent = '<' + CAL.lodUg; $('asValue')._v = 0; }
    else UI().countTo($('asValue'), ugl(r.asMgL), fmtUgNum, 1200);
    $('asMgl').textContent = failed ? t('auth.f.notValid') : low ? t('auth.f.notDetected')
      : t('ov.mgl', { v: r.asMgL.toFixed(4) });   // v5.10: the ± is stated once, in the uncertainty line below
    const pin = $('stripPin');
    if (failed) pin.hidden = true;
    else {
      if (pin.hidden) { pin.style.left = stripPercent(0) + '%'; pin.hidden = false; void pin.offsetWidth; }   // first reading slides in from 0
      pin.style.left = stripPercent(shownUg) + '%';
      pin.style.setProperty('--sample', kitColour(shownUg));
      $('stripPinLabel').textContent = t('chart.you', { v: (low ? '< ' + CAL.lodUg : fmtUg(r.asMgL)) + ' µg/L' });
      // keep the label inside the chart near the ends (the marker itself stays exact)
      const lab = $('stripPinLabel'), bodyW = pin.parentElement.clientWidth, x = stripPercent(shownUg) / 100 * bodyW, half = lab.offsetWidth / 2;
      pin.style.setProperty('--shift', (x - half < 0 ? half - x : x + half > bodyW ? bodyW - half - x : 0) + 'px');
    }
    setRing(failed ? null : shownUg);
    if (low && $('ringNum')) $('ringNum').textContent = '<' + CAL.lodUg;
    if (state.fx) state.fx.setColor(TONE_HEX[vk] || TONE_HEX[res.final]);
    if (state.device) state.device.setRim(TONE_HEX[vk] || TONE_HEX[res.final]);

    const why = $('whyList');
    why.innerHTML = '';
    if (!failed) {
      res.reasons.filter((x) => x.code !== 'LOD').forEach((x) => {
        const li = document.createElement('li');
        li.textContent = x.code === 'NM' ? t('reason.NM', { v: t(NM_LABEL[x.v] || 'read.' + x.v) }) : t('reason.' + x.code, { v: x.v });
        why.appendChild(li);
      });
    }
    $('labNote').hidden = failed || !res.belowLod;
    $('labNote').textContent = t('ov.labNote');
    renderQc(r.qc, r.failNotes);

    // alert banner
    const b = $('alertBanner');
    b.hidden = false;
    b.className = 'alert-banner' + (vk === 'Safe' ? ' ok' : vk === 'Caution' || vk === 'Clear' ? ' warn' : '');
    $('alertTitle').textContent = t('alert.' + vk + '.t');
    $('alertText').textContent = t('alert.' + vk + '.d');
    $('alertBtn1').hidden = vk === 'Safe';
    $('alertBtn2').hidden = vk === 'Safe' || vk === 'Caution' || vk === 'Clear' || vk === 'Failed';

    renderMeta();
    renderReadingsGrid(r);
  }

  const NM_LABEL = { ph: 'read.ph', ec: 'read.ec', turb: 'read.turb', temp: 'read.temp' };
  const MODE_OF = { device: 'live', replay: 'replay', sim: 'sim', demo: 'demo', import: 'import' };
  /** v5.8: the outcome chip, the ± uncertainty and the data mode (live / replay / simulation) beside the verdict. */
  function renderOutcome(r, vk) {
    const oc = outcomeOf(r), chip = $('outcomeChip'), mode = $('modeBadge'), unc = $('uncLine'), view = $('viewScanBtn');
    if (chip) { chip.hidden = !oc; chip.dataset.outcome = oc || ''; chip.textContent = oc ? t('outcome.' + oc) : ''; }
    if (mode) { const m = MODE_OF[r.source] || 'sim'; mode.dataset.mode = m; mode.textContent = t('mode.' + m); mode.title = t('mode.' + m + '.hint'); }
    if (unc) {
      const has = r.uncertaintyUg != null && !r.failed;
      unc.hidden = !has;
      if (has) unc.textContent = t(r.scanId || r.uncertaintySource === 'measured_from_scan' ? 'ov.uncMeasured' : 'ov.uncTypical', { u: r.uncertaintyUg < 10 ? r.uncertaintyUg.toFixed(1) : Math.round(r.uncertaintyUg) });
    }
    if (view) view.hidden = !(r.scanId && online());
  }
  /** Device line under the verdict, with a warning when a real device's last reading is old (v5.7). */
  function ageText(min) {
    if (min < 120) return Math.round(min) + ' min';
    if (min < 48 * 60) return Math.round(min / 60) + ' h';
    return Math.round(min / 1440) + ' d';
  }
  function renderMeta() {
    const r = state.reading;
    if (!r) return;
    const src = t('ov.source.' + r.source);
    let meta = `${t('ov.device', { code: r.device || DEVICE })}, ${t('ov.lastReading', { time: fmtTime(r.time) })} (${src})`;
    const ageMin = (Date.now() - r.time.getTime()) / 60000;
    const stale = r.source === 'device' && ageMin > STALE_MIN;
    if (stale) meta += ' · ' + t('ov.stale', { age: ageText(ageMin) });
    if (r.timeUnknown) meta += ' · ' + t('qc.TIME_UNKNOWN');
    $('ovMeta').textContent = meta;
    $('ovMeta').classList.toggle('meta-warn', stale || !!r.timeUnknown);
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
      const okBand = d.ok ? `<div class="gauge-ok" data-left="${pct(d.ok[0])}" data-width="${pct(d.ok[1]) - pct(d.ok[0])}"></div>` : '';
      const dot = val !== null ? `<div class="gauge-dot" data-left="${pct(val)}"></div>` : '';
      const inRange = val === null || !d.ok || (val >= d.ok[0] && val <= d.ok[1]);
      const st = val === null || !d.ok ? '' : `<span class="reading-state ${inRange ? 'ok' : 'bad'}">${t(inRange ? 'read.ok' : 'read.bad')}</span>`;
      return `<div class="card reading spot">
        <div class="reading-name">${t(d.label)}</div>
        <div class="reading-val">${val === null ? `<span class="reading-nm">${t('read.nm')}</span>` : d.fmt(val) + (d.unit ? `<small>${d.unit}</small>` : '')}</div>
        <div class="gauge">${okBand}${dot}</div>
        <div class="reading-foot"><span>${t(d.good)}</span>${st}</div>
      </div>`;
    }).join('');
    applyGeometry(grid);
    const line = $('deviceLine');
    if (r && (r.battery != null || r.lat != null)) {
      const parts = [];
      if (r.battery != null) parts.push(`${t('read.battery')} ${Math.round(r.battery)}%`);
      if (r.lat != null) parts.push(`${t('read.location')} ${r.lat.toFixed(2)}°N, ${r.lon.toFixed(2)}°E`);
      line.textContent = parts.join('   ·   ');
    } else line.textContent = '';
  }

  // ---------------- server data ----------------
  const SOURCE_KEY = { hardware: 'device', manual_import: 'import', simulated: 'sim', synthetic_demo: 'demo', synthetic_fixture: 'demo', recorded_replay: 'replay' };
  /** A stored reading as the dashboard keeps it. Nothing is invented: missing values stay null. */
  function fromServer(d, code) {
    const qc = (d.qc_flags || '').split(',').filter(Boolean);
    return {
      id: d.id, device: d.device_code || code,
      asMgL: (d.arsenic_ppb || 0) / 1000, ph: d.ph ?? null, ec: d.conductivity_us_cm ?? null, turb: d.turbidity_ntu ?? null,
      temp: d.temperature_c ?? null, battery: d.battery_pct ?? null, lat: d.latitude ?? null, lon: d.longitude ?? null,
      time: d.recorded_at ? new Date(d.recorded_at.endsWith('Z') || d.recorded_at.includes('+') ? d.recorded_at : d.recorded_at + 'Z') : new Date(),
      source: SOURCE_KEY[d.source_type] || (d.is_simulated === false ? 'device' : 'demo'), savedOnServer: true,
      qc, species: d.arsenic_species || null, serverLabel: d.classification, failed: d.classification === 'Test Failed',
      timeUnknown: d.time_source === 'unknown',
      outcome: d.screening_outcome || null, uncertaintyUg: d.uncertainty_ppb ?? null, scanId: d.trace_id || null,
      uncertaintySource: d.trace_id ? 'measured_from_scan' : 'method_typical', calibrationId: d.calibration_ref || null,
    };
  }
  /** v5.11: ?device=CODE in the address opens the dashboard on that device (the MAS-G1 simulator links here). */
  function urlDevice() {
    try { const c = new URLSearchParams(location.search).get('device'); return c && /^[A-Za-z0-9._-]{1,64}$/.test(c) ? c : null; }
    catch (e) { return null; }
  }
  /** v5.7: with no device code, show the newest REAL device reading; fall back to the newest of any kind. */
  async function loadLatestFromServer(code) {
    try {
      let d;
      if (code) d = await api(`/api/readings/latest?device_code=${encodeURIComponent(code)}`);
      else {
        try { d = await api('/api/readings/latest?source_type=hardware'); } catch (e) { d = await api('/api/readings/latest'); }
      }
      setReading(fromServer(d, code));
      return true;
    } catch (e) { return false; }
  }
  async function loadDemo() {
    if (online()) {
      try { await api('/api/demo/load', { method: 'POST' }, 6000); if (await loadLatestFromServer('DEMO-BOT-01')) return; } catch (e) { /* fall through */ }
    }
    // offline demo: clearly "demo", and no invented battery level or location (v5.7)
    setReading({ asMgL: 0.045, ph: 7.35, ec: 412, turb: 2.1, temp: 24.2, battery: null, lat: null, lon: null, time: new Date(), source: 'demo' });
  }

  // ---------------- voltammetry: asv.js (one pipeline; the server is authoritative when online) ----------------
  const synthTrace = (asMgL) => ASV.synth(asMgL);
  const faultTrace = () => ASV.fault();
  const processTrace = (P, C) => ASV.process(P, C);
  const FAULT_KEY = { FLAT_SIGNAL: 'qc.FLAT_SIGNAL', NOISE_ABOVE_LOD: 'qc.NOISE', BASELINE_UNSTABLE: 'qc.NOISE', PEAK_AT_WINDOW_EDGE: 'qc.PEAK_EDGE',
    ADC_SATURATION_HIGH: 'qc.SATURATED', ADC_SATURATION_LOW: 'qc.SATURATED', NONMONOTONIC_SWEEP: 'qc.BADSWEEP', INSUFFICIENT_BASELINE: 'qc.BADSWEEP',
    TOO_FEW_POINTS: 'qc.BADSWEEP', NON_FINITE: 'qc.BADSWEEP', MALFORMED_TRACE: 'qc.BADSWEEP', NO_POINTS_IN_WINDOW: 'qc.BADSWEEP', PARTIAL_WINDOW: 'qc.BADSWEEP', INVALID_CALIBRATION: 'qc.BADCAL', REF_UNSTABLE: 'qc.REF' };
  /** Send a trace through the server's pipeline (POST /api/scans). Returns null when offline or refused. */
  async function postScan(P, C, extra) {
    try {
      return await api('/api/scans', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({ potentials_mv: P, currents_ua: C }, extra)) }, 12000);
    } catch (e) { return { error: e && e.message ? e.message : 'offline' }; }
  }
  function showTraceNumbers(out, caption) {
    $('trPeak').textContent = out.net.toFixed(4) + ' µA';
    $('trPos').textContent = Number.isFinite(out.peakMv) ? Math.round(out.peakMv) + ' mV' : '–';
    $('trSnr').textContent = out.snr.toFixed(0);
    $('trAs').textContent = out.failed ? t('class.Failed') : (out.asUgL < CAL.lodUg ? '< ' + CAL.lodUg : fmtUgNum(out.asUgL)) + ' µg/L'
      + (out.uncertaintyUg != null && !out.failed && out.asUgL >= CAL.lodUg ? ' ± ' + (out.uncertaintyUg < 10 ? out.uncertaintyUg.toFixed(1) : Math.round(out.uncertaintyUg)) : '');
    const cap = $('traceCaption'); if (cap) cap.textContent = caption || '';
  }
  /** A practice test (simulated trace), an electrode fault, or a recorded instrument file (replay). */
  async function runTest(asMgL, opts) {
    opts = opts || {};
    const quiet = opts.quiet;
    const btn = $('runTestBtn');
    btn.disabled = true; btn.textContent = t('test.running');
    const replay = !!opts.trace;
    const { P, C } = replay ? opts.trace : opts.fault ? faultTrace() : synthTrace(asMgL);
    let out = processTrace(P, C);
    let saved = false, refused = null, server = null;
    if (online()) {
      const d = await postScan(P, C, { device_code: replay ? (opts.device || REPLAY_DEVICE) : SIM_DEVICE,
        source_type: replay ? 'recorded_replay' : 'simulated', raw_file_name: replay ? opts.fileName : undefined,
        source_label: replay ? t('mode.replay') : 'Dashboard practice test', recorded_at: opts.recordedAt || undefined });
      if (d && !d.error) {
        server = d;
        const pl = d.pipeline || {};
        out = Object.assign({}, out, { asUgL: pl.estimated_ug_l == null ? 0 : pl.estimated_ug_l, asMgL: (pl.estimated_ug_l || 0) / 1000,
          flags: pl.qc_flags || out.flags, failed: pl.qc_status === 'REJECTED', uncertaintyUg: pl.uncertainty_ug_l ?? out.uncertaintyUg, status: pl.qc_status || out.status });
        saved = true;
      } else if (d && d.error) refused = d.error;
    }
    state.lastTrace = { P, C, out, caption: replay ? t('test.traceOf', { what: opts.fileName || t('mode.replay') }) : t(server ? 'test.pipelineServer' : 'test.pipelineLocal') };
    drawChart();
    showTraceNumbers(out, state.lastTrace.caption);

    // a practice test only measures arsenic: pH / conductivity / turbidity / temperature are "not measured"
    const failNotes = Array.from(new Set((out.flags || []).map((f) => FAULT_KEY[f]).filter(Boolean)));
    const reading = { asMgL: out.asMgL, ph: null, ec: null, turb: null, temp: null, battery: null, lat: null, lon: null,
      time: opts.recordedAt ? new Date(opts.recordedAt) : new Date(), source: replay ? 'replay' : 'sim',
      device: replay ? (opts.device || REPLAY_DEVICE) : SIM_DEVICE, failed: !!out.failed, failNotes, qc: [],
      uncertaintyUg: out.failed ? null : out.uncertaintyUg, uncertaintySource: 'measured_from_scan', fileName: opts.fileName || null };
    if (server && server.result) {
      const d = server.result;
      reading.savedOnServer = true; reading.id = d.reading.id; reading.serverLabel = d.label;
      reading.qc = (d.reading.qc_flags || '').split(',').filter(Boolean); reading.outcome = d.screening_outcome || null;
      reading.scanId = server.scan && server.scan.id; reading.calibrationId = server.scan && server.scan.calibration_id;
    }
    setReading(reading);
    btn.disabled = false; btn.textContent = t('test.run');
    if (out.failed) $('testMsg').textContent = t('test.failed', { why: failNotes.map((k) => t(k)).join(' ') });
    else if (replay) $('testMsg').textContent = t(saved ? 'test.replaySaved' : 'test.replayLocal', { n: P.length });
    else if (!quiet) $('testMsg').textContent = refused && online() ? t('test.refused', { why: refused }) : t(saved ? 'test.savedServer' : 'test.saved');
  }
  /** v5.8: show the stored native trace of the reading on screen (GET /api/scans/{id}), with the server's processing. */
  async function viewScan(scanId) {
    if (!scanId) return;
    try {
      const d = await api(`/api/scans/${scanId}`, null, 8000);
      const pr = d.processed || {};
      const out = { P: d.potentials_mv, C: d.currents_ua, S: pr.smoothed_currents_ua || d.currents_ua, base: pr.baseline_currents_ua || d.currents_ua.map(() => 0),
        peakIdx: pr.peak && pr.peak.peak_potential_mv != null ? d.potentials_mv.indexOf(pr.peak.peak_potential_mv) : -1,
        peakMv: pr.peak ? pr.peak.peak_potential_mv : NaN, net: pr.peak ? pr.peak.net_peak_height_ua || 0 : 0, snr: pr.peak ? pr.peak.snr || 0 : 0,
        asUgL: pr.estimated_ug_l || 0, asMgL: (pr.estimated_ug_l || 0) / 1000, failed: pr.qc_status === 'REJECTED', flags: d.qc_flags || [],
        uncertaintyUg: d.uncertainty_ug_l };
      state.lastTrace = { P: out.P, C: out.C, out, caption: t('test.storedTrace', { id: scanId, sum: (d.checksum_sha256 || '').slice(0, 10), ok: pr.checksum_matches === false ? t('test.checksumBad') : t('test.checksumOk') }) };
      drawChart();
      showTraceNumbers(out, state.lastTrace.caption);
      document.getElementById('test').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) { flash(t('test.traceMissing')); }
  }
  function onReplayFile(file) {
    if (!file) return;
    const rd = new FileReader();
    rd.onload = () => {
      const parsed = ASV.parseTraceFile(rd.result, file.name);
      if (parsed.error || !parsed.P || parsed.P.length < 2) { $('testMsg').textContent = t('test.replayBad'); return; }
      runTest(0, { trace: { P: parsed.P, C: parsed.C }, fileName: file.name, recordedAt: parsed.meta && parsed.meta.recorded_at,
        device: parsed.meta && parsed.meta.device_code });
    };
    rd.readAsText(file);
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
    if (out.peakIdx >= 0 && Number.isFinite(out.peakMv)) {
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
    // The explorer is a what-if tool with sliders; a sensor that was not measured leaves its slider where it is
    // (v5.7: nothing is filled in for it, and the verdict above never uses the slider values).
    const vals = [Math.min(0.3, r.asMgL), r.ph, r.ec, r.turb == null ? null : Math.min(25, r.turb), r.temp];
    NN_IDS.forEach(([id], i) => { if (vals[i] != null) { $(id).value = vals[i]; UI().fillRange($(id)); } });
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
      return `<div class="bar-row"><span>${t('class.' + c)}</span><div class="bar"><i data-width="${p.toFixed(1)}" data-color="${colors[c]}"></i></div><span class="bar-pct">${p.toFixed(1)}%</span></div>`;
    }).join('');
    applyGeometry($('nnBars'));
    $('nnRuleMsg').textContent = t(res.final !== res.vote ? 'nn.override' : 'nn.agree');
    $('nnOod').hidden = !(res.ood && res.ood.length);
    $('nnOod').textContent = res.ood && res.ood.length ? t('nn.ood', { list: res.ood.join(', ') }) : '';
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
    const vk = verdictKey(res, r);
    const srcKey = { device: 'auth.src.device', import: 'auth.src.import', sim: 'auth.src.sim', demo: 'auth.src.demo', replay: 'auth.src.replay' }[r.source] || 'auth.src.demo';
    return [
      ['auth.f.source', t(srcKey)],
      ['auth.f.station', `${r.device || DEVICE} (${t('auth.f.stationType')})`],
      // v5.7: the device measures As(III) unless total-arsenic pre-treatment is fitted (was "total dissolved")
      ['auth.f.contaminant', t(r.species === 'total' ? 'auth.f.arsenicTotal' : 'auth.f.arsenicAs3')],
      ['auth.f.reading', vk === 'Failed' ? t('auth.f.notValid') : belowLod(r) ? t('auth.f.notDetected') : `${r.asMgL.toFixed(4)} mg/L (${fmtUg(r.asMgL)} µg/L)`],
      ['auth.f.limits', 'WHO 10 µg/L · IS 10500: 10 µg/L (no relaxation since 2015)'],
      ['auth.f.tier', `${t('class.' + vk)} — ${t('verdict.' + vk + '.title')}`],
      ['auth.f.outcome', `${t('outcome.' + (outcomeOf(r) || 'invalid'))}${r.uncertaintyUg != null && vk !== 'Failed' && !belowLod(r) ? ' · ± ' + (r.uncertaintyUg < 10 ? r.uncertaintyUg.toFixed(1) : Math.round(r.uncertaintyUg)) + ' µg/L' : ''}${r.calibrationId ? ' · ' + t('auth.f.cal', { id: r.calibrationId }) : ''}`],
      ['auth.f.other', [
        r.ph == null ? null : `pH ${r.ph.toFixed(2)}`, r.ec == null ? null : `${Math.round(r.ec)} µS/cm`,
        r.turb == null ? null : `${r.turb.toFixed(1)} NTU`, r.temp == null ? null : `${r.temp.toFixed(1)} °C`,
      ].filter(Boolean).join(' · ') || t('auth.f.notMeasured')],
      ['auth.f.method', t('auth.f.methodVal')],
      ['auth.f.geotag', r.lat != null ? `${r.lat.toFixed(4)}°N, ${r.lon.toFixed(4)}°E` : t('auth.f.noGps')],
      ['auth.f.time', r.timeUnknown ? t('auth.f.timeUnknown', { d: fmtDateTime(r.time) }) : fmtDateTime(r.time)],
    ];
  }
  /** v5.7: only real readings with a valid result can be sent to authorities (was: anything, incl. practice tests). */
  function reportBlocked(r) {
    if (!r) return null;
    if (r.source !== 'device' && r.source !== 'import' && r.source !== 'replay') return 'auth.blockedSim';
    if (verdictKey(evaluate(r), r) === 'Failed') return 'auth.blockedFailed';
    return null;
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
      const blocked = reportBlocked(state.reading);
      $('dispatchBody').innerHTML = (blocked ? `<dt>!</dt><dd class="dispatch-blocked">${esc(t(blocked))}</dd>` : '') +
        rows.map(([k, v]) => `<dt>${t(k)}</dt><dd>${v.replace(/</g, '&lt;')}</dd>`).join('');
      const res = evaluate(state.reading);
      const vk = verdictKey(res, state.reading);
      const urgent = vk === 'Unsafe' || vk === 'Hazardous';
      if (blocked) {
        st.className = 'tag'; st.textContent = t(blocked === 'auth.blockedSim' ? 'auth.status.practice' : 'auth.status.failed');
        ['dEmail', 'dCopy', 'dShare', 'dPrint'].forEach((id) => $(id).setAttribute('aria-disabled', 'true'));
        $('dEmail').removeAttribute('href');
      } else {
        st.className = 'tag ' + (urgent ? 'tone-haz' : vk === 'Caution' ? 'tone-caution' : 'active');
        st.textContent = t(urgent ? 'auth.status.urgent' : vk === 'Caution' ? 'auth.status.watch' : 'auth.status.ok');
        ['dEmail', 'dCopy', 'dShare', 'dPrint'].forEach((id) => $(id).removeAttribute('aria-disabled'));
        const subject = encodeURIComponent(t('auth.mail.subject', { code: (state.reading && state.reading.device) || DEVICE }) + ' — ' + t('class.' + vk));
        $('dEmail').href = `mailto:${encodeURIComponent(c.email || '')}?subject=${subject}&body=${encodeURIComponent(reportText())}`;
      }
    }
    // directory buttons that use saved contacts
    const call = $('dirCallLocal'), mail = $('dirEmailLocal');
    if (c.phone) { call.href = 'tel:' + c.phone.replace(/[^\d+]/g, ''); call.textContent = t('dir.call') + ' ' + c.phone; } else { call.href = '#contactsBox'; call.textContent = t('dir.addNumber'); }
    if (c.email) { mail.href = $('dEmail').getAttribute('href') || ('mailto:' + c.email); mail.textContent = t('dir.email'); } else { mail.href = '#contactsBox'; mail.textContent = t('dir.addEmail'); }
    $('dShare').hidden = !navigator.share;
  }
  function flash(msg) { const m = $('dispatchMsg'); m.textContent = msg; clearTimeout(m._t); m._t = setTimeout(() => { m.textContent = ''; }, 4000); }
  async function copyReport() {
    if (reportBlocked(state.reading)) { flash(t(reportBlocked(state.reading))); return; }
    const text = reportText(); if (!text) return;
    try { await navigator.clipboard.writeText(text); flash(t('auth.copied')); }
    catch (e) {
      const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); flash(t('auth.copied')); } catch (err) { flash(t('auth.copyFail')); }
      ta.remove();
    }
  }
  function printReport() {
    if (reportBlocked(state.reading)) { flash(t(reportBlocked(state.reading))); return; }
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
      <td>${vchip(h.verdict, h.asMgL)}</td><td>${t('ov.source.' + h.source)}</td></tr>`).join('')
      : `<tr class="empty-row"><td colspan="4">${t('rep.empty')}</td></tr>`;
    const pdf = $('pdfBtn');
    const canPdf = online() && state.reading && state.reading.savedOnServer;
    pdf.setAttribute('aria-disabled', canPdf ? 'false' : 'true');
    pdf.textContent = t(canPdf ? 'rep.pdf' : 'rep.pdfOff');
    // v5.7: the report is for the reading on screen (was: the newest reading of any device)
    if (canPdf) pdf.href = UI().API + '/api/reports/certificate/pdf' + (state.reading.id ? '?reading_id=' + state.reading.id : '?device_code=' + encodeURIComponent(state.reading.device || DEVICE));
    else pdf.removeAttribute('href');
  }
  // verdict as paint + words (never colour alone)
  function vchip(cls, asMgL) {
    const key = cls === 'Test Failed' ? 'Failed' : cls === 'Below Sensor LOD' || (cls === 'Safe' && asMgL != null && ugl(asMgL) < 20) ? 'Clear' : cls;
    return `<span class="vchip c-${esc(String(cls).replace(/\s+/g, ''))}">${esc(t('class.' + key))}</span>`;
  }
  function downloadCsv() {
    if (online()) { window.location.href = UI().API + '/api/data/export?format=csv'; return; }   // every device, from the server
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
  /** Measurement-quality caveats from the node (As(III) only, copper, factory calibration). */
  // v5.7: device QC codes shown in plain words (scan faults, unverified sensor)
  const QC_NOTE = { FLAT_SIGNAL: 'qc.FLAT_SIGNAL', NOISE_ABOVE_LOD: 'qc.NOISE', BASELINE_UNSTABLE: 'qc.NOISE', PEAK_AT_WINDOW_EDGE: 'qc.PEAK_EDGE',
    QC_NOT_REPORTED: 'qc.NO_QC', CHECK_STANDARD_MISSING: 'qc.UNVERIFIED', CHECK_STANDARD_FAILED: 'qc.UNVERIFIED',
    CHECK_STANDARD_OVERDUE: 'qc.UNVERIFIED', CALIBRATION_MISSING: 'qc.UNVERIFIED', CALIBRATION_EXPIRED: 'qc.UNVERIFIED' };
  function renderQc(flags, extraKeys) {
    const ul = $('qcNotes');
    if (!ul) return;
    const keys = [];
    (extraKeys || []).forEach((k) => { if (!keys.includes(k)) keys.push(k); });
    (flags || []).forEach((f) => {
      const k = ['as3_only', 'copper_interference', 'uncalibrated'].includes(f) ? 'qc.' + f : QC_NOTE[f];
      if (k && !keys.includes(k)) keys.push(k);
    });
    ul.hidden = !keys.length;
    ul.innerHTML = keys.map((k) => `<li class="qc-${k.replace(/\W/g, '_')}">${esc(t(k))}</li>`).join('');
  }
  function loadScript(src) {
    return new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = fail; document.head.appendChild(s); });
  }
  /** The 3D model (about 180 KB) loads only when its section comes near the screen. */
  function lazyDevice() {
    const el = $('viewer3d');
    if (!el) return;
    const go = () => loadScript('device3d-data.js').then(() => loadScript('device3d.js')).then(initDevice).catch(() => {});
    if (!('IntersectionObserver' in window)) { go(); return; }
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); go(); } }, { rootMargin: '600px' });
    io.observe(el);
  }
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


  // ---------------- devices & history ----------------
  const NS_SVG = 'http://www.w3.org/2000/svg';
  const PAINT = { Safe: '--paint-safe', 'Below Sensor LOD': '--paint-clear', Caution: '--paint-caution', Unsafe: '--paint-unsafe', Hazardous: '--paint-haz', 'Test Failed': '--paint-haz' };
  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function seenText(mins) {
    if (mins == null) return '';
    if (mins < 90) return t('fleet.seen.min', { n: Math.max(0, Math.round(mins)) });
    if (mins < 48 * 60) return t('fleet.seen.h', { n: Math.round(mins / 60) });
    return t('fleet.seen.d', { n: Math.round(mins / 1440) });
  }
  const ICON_UP = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 11l5-6 5 6"/></svg>';
  const ICON_DOWN = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 5l5 6 5-6"/></svg>';
  const WARN_ICON = {
    trend: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/></svg>',
    offline: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 8.5a15 15 0 0 1 20 0M5 12a10 10 0 0 1 14 0M8.5 15.5a5 5 0 0 1 7 0"/><path d="M3 3l18 18"/></svg>',
    reading: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.5 20h19Z"/><path d="M12 10v4M12 17v.5"/></svg>',
    battery: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="7" width="17" height="10" rx="2"/><path d="M22 10.5v3M6 10.5v3"/></svg>',
  };
  function renderWarnings(list) {
    const ul = $('warnList');
    if (!ul) return;
    if (list === null) { ul.innerHTML = `<li class="empty">${esc(t('fleet.empty'))}</li>`; return; }
    // field data first: hide demo/simulated alerts whenever a real node has something to say
    const real = list.filter((a) => a.type === 'trend' || a.type === 'offline' || a.type === 'battery' || a.source_type === 'hardware');
    // one line per device and kind (newest wins); trends and silent devices before single readings
    const seen = new Set(), pick = [];
    (real.length ? real : list).slice().sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || '')).forEach((a) => {
      const k = (a.type || 'reading') + '|' + (a.device_code || a.id);
      if (!seen.has(k)) { seen.add(k); pick.push(a); }
    });
    const rank = { trend: 0, offline: 1, battery: 3 };   // single unsafe readings rank 2
    const items = pick.sort((a, b) => (rank[a.type] ?? 2) - (rank[b.type] ?? 2)).slice(0, 6);
    if (!items.length) { ul.innerHTML = `<li class="empty">${esc(t('warn.none'))}</li>`; return; }
    ul.innerHTML = items.map((a) => {
      const type = a.type || 'reading';
      const level = a.level === 'CRITICAL' ? 'crit' : a.level === 'WARNING' ? 'warn' : 'note';
      const when = a.timestamp ? fmtDateTime(new Date(a.timestamp)) : '';
      const label = t('warn.type.' + type);
      return `<li class="wl ${level}"><span class="wl-ico">${WARN_ICON[type] || WARN_ICON.reading}</span>` +
        `<span class="wl-body"><b>${esc(label)}${a.device_code ? ': ' + esc(a.device_code) : ''}</b><span>${esc(String(a.message || '').replace(a.device_code + ': ', ''))}</span>` +
        `<small>${esc(when)}</small></span></li>`;
    }).join('');
  }
  function renderTrendNote(devs) {
    const p = $('trendNote');
    if (!p) return;
    const d = devs && state.histDevice ? devs.find((x) => x.device_code === state.histDevice) : null;
    if (!d || !d.trend || !d.trend.message) { p.hidden = true; return; }
    p.hidden = false;
    p.className = 'trend-note ' + (d.trend.direction === 'rising' ? 'up' : d.trend.direction === 'falling' ? 'down' : '');
    p.textContent = `${d.device_code}: ${d.trend.message}`;
    if (d.trend.p_value != null) p.title = `Mann-Kendall p = ${d.trend.p_value}`;
  }
  function fillHistTable(points) {
    const tb = $('histTable') && $('histTable').querySelector('tbody');
    if (!tb) return;
    tb.innerHTML = points.length ? points.slice().reverse().slice(0, 200).map((p) =>
      `<tr><td>${esc(fmtDateTime(p.t))}</td><td>${esc(p.device_code || '–')}</td><td class="num">${fmtUgNum(p.ppb)}</td><td>${vchip(p.cls, p.ppb / 1000)}</td></tr>`).join('')
      : `<tr class="empty-row"><td colspan="4">${esc(t('hist.empty'))}</td></tr>`;
  }
  function deviceRow(d) {
    // v5.7: a failed test shows no number, and a value below the 20 µg/L detection limit is shown as "< 20"
    const lv = !d.latest ? '' : d.latest.classification === 'Test Failed' ? t('class.Failed')
      : d.latest.arsenic_ppb < CAL.lodUg ? '&lt; ' + CAL.lodUg + ' µg/L' : fmtUgNum(d.latest.arsenic_ppb) + ' µg/L';
    const latest = d.latest ? `<span class="dv-latest c-${esc(d.latest.classification.replace(/\s+/g, ''))}">${lv}</span>` : '<span></span>';
    const count = d.reading_count === 1 ? t('fleet.count.one', { u: d.unsafe_count }) : t('fleet.count', { n: d.reading_count, u: d.unsafe_count });
    const batt = d.latest && d.latest.battery_pct != null ? t('fleet.batt', { n: Math.round(d.latest.battery_pct) }) : '';
    const lab = d.lab ? t('fleet.lab', { v: fmtUgNum(d.lab.arsenic_ug_l) }) : '';
    const place = d.site && (d.site.name || d.site.village) ? (d.site.name || d.site.village) : '';
    // v5.10: two short lines instead of one long comma run: where and when, then the numbers
    // "last reading" is the age of the newest MEASUREMENT, not of the last upload: a node that only re-sends old
    // buffered readings is in contact ("Online") but has no new data, and the list must not say "0 min ago"
    const readAt = d.latest && d.latest.recorded_at ? Date.parse(d.latest.recorded_at) : NaN;
    const readMins = Number.isFinite(readAt) ? (Date.now() - readAt) / 60000 : d.minutes_since_seen;
    const where = [place, t('fleet.st.' + d.status), seenText(readMins)].filter(Boolean).join(' · ');
    const facts = [count, batt, lab, d.firmware_version ? t('fleet.fw', { v: d.firmware_version }) : ''].filter(Boolean).join(' · ');
    const sel = state.histDevice === d.device_code;
    const tr = d.trend && d.trend.direction === 'rising' ? `<span class="dv-trend up">${ICON_UP}${esc(t('trend.rising'))}</span>`
      : d.trend && d.trend.direction === 'falling' ? `<span class="dv-trend down">${ICON_DOWN}${esc(t('trend.falling'))}</span>` : '';
    return `<li><button type="button" class="dv-row" data-device="${esc(d.device_code)}" aria-pressed="${sel}">` +
      `<span class="dv-dot ${esc(d.status)}" aria-hidden="true"></span><span class="dv-name">${esc(d.device_code)}</span>${latest}` +
      `<span class="dv-meta"><span class="dv-where">${tr}${esc(where)}</span><span class="dv-facts">${esc(facts)}</span></span></button></li>`;
  }
  function renderDevices(list) {
    const ul = $('deviceList');
    if (!ul) return;
    if (list === null) { ul.innerHTML = `<li class="empty">${esc(t('fleet.empty'))}</li>`; return; }
    if (!list.length) { ul.innerHTML = `<li class="empty">${esc(t('fleet.none'))}</li>`; return; }
    const hw = list.filter((d) => d.is_hardware), demo = list.filter((d) => !d.is_hardware);
    let html = `<li><button type="button" class="dv-row all" data-device="" aria-pressed="${!state.histDevice}"><span class="dv-name">${esc(t('fleet.all'))}</span></button></li>`;
    html += hw.map(deviceRow).join('');
    if (!hw.length) html += `<li class="empty">${esc(t('fleet.nohw'))}</li>`;
    if (demo.length) {
      const open = demo.some((d) => d.device_code === state.histDevice) ? ' open' : '';
      html += `<li class="dv-demo"><details${open}><summary>${esc(t('fleet.demo', { n: demo.length }))}</summary><ul>${demo.map(deviceRow).join('')}</ul></details></li>`;
    }
    ul.innerHTML = html;
    ul.querySelectorAll('[data-device]').forEach((btn) => btn.addEventListener('click', () => {
      state.histDevice = btn.dataset.device || null;
      loadFleet();
    }));
  }
  function drawHistory(points, local) {
    const svg = $('historyChart');
    if (!svg) return;
    const W = 720, H = 300, L = 62, R = 12, T = 12, B = 30;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.innerHTML = '';
    const add = (tag, attrs, text) => { const e = document.createElementNS(NS_SVG, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; svg.appendChild(e); return e; };
    // y uses the same scale as the colour chart: swatch centres from bottom (0) to top (300)
    const Y = (u) => T + (H - T - B) * (1 - kitIndex(u) / (KIT.length - 1));
    [[0, 10, '--paint-safe'], [10, 20, '--paint-caution'], [20, 150, '--paint-unsafe'], [150, 300, '--paint-haz']].forEach(([a, b, v]) => {
      add('rect', { class: 'h-band', x: L, y: Y(b), width: W - L - R, height: Y(a) - Y(b), fill: cssVar(v) });
    });
    KIT.forEach((u, i) => {   // the chart's own swatches down the left edge
      add('rect', { class: 'h-swatch', x: 1, y: Y(u) - 9, width: 14, height: 18, rx: 2, fill: `rgb(${KIT_RGB[i].join(',')})` });
      add('text', { class: 'h-tick', x: 54, y: Y(u) + 4, 'text-anchor': 'end' }, u === 300 ? '300+' : String(u));
    });
    [[10, ''], [20, ' lod'], [150, '']].forEach(([u, c]) => add('line', { class: 'h-edge' + c, x1: L, x2: W - R, y1: Y(u), y2: Y(u) }));
    if (!points.length) {
      fillHistTable([]);
      add('text', { class: 'h-empty', x: (L + W - R) / 2, y: H / 2, 'text-anchor': 'middle' }, t('hist.empty'));
      $('histDesc').textContent = local ? t('hist.local') : '';
      return;
    }
    const ts = points.map((p) => p.t.getTime());
    let t0 = Math.min(...ts), t1 = Math.max(...ts);
    if (t1 - t0 < 3600e3) { t0 -= 1800e3; t1 += 1800e3; }
    const X = (x) => L + 8 + (W - L - R - 16) * (x - t0) / (t1 - t0);
    const lang = ({ hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', pa: 'pa-IN' })[window.I18N.lang] || 'en-IN';
    const span = t1 - t0;
    const fmt = (d) => span > 2 * 86400e3 ? d.toLocaleDateString(lang, { day: 'numeric', month: 'short' }) : d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' });
    for (let i = 0; i <= 4; i++) {
      const x = t0 + span * i / 4;
      add('text', { class: 'h-tick', x: X(x), y: H - 8, 'text-anchor': i === 0 ? 'start' : i === 4 ? 'end' : 'middle' }, fmt(new Date(x)));
    }
    const byDevice = {};
    points.forEach((p) => { (byDevice[p.device_code || ''] = byDevice[p.device_code || ''] || []).push(p); });
    const DASH = ['', '6 4', '2 3', '10 3 2 3'];   // series differ by line style too, not by colour alone
    const series = Object.entries(byDevice);
    if (series.length > 4) {
      // Many sources: joining each one's points makes a tangle. Show one line, the highest reading per day.
      const days = {};
      points.forEach((p) => { const k = p.t.toISOString().slice(0, 10); if (!days[k] || p.ppb > days[k].ppb) days[k] = p; });
      const top = Object.keys(days).sort().map((k) => days[k]);
      if (top.length > 1) add('polyline', { class: 'h-line h-max', points: top.map((p) => `${X(p.t.getTime()).toFixed(1)},${Y(p.ppb).toFixed(1)}`).join(' ') });
    }
    series.forEach(([code, pts], k) => {
      if (series.length <= 4 && pts.length > 1) add('polyline', { class: 'h-line', 'stroke-dasharray': DASH[k % DASH.length], points: pts.map((p) => `${X(p.t.getTime()).toFixed(1)},${Y(p.ppb).toFixed(1)}`).join(' ') });
      if (code && series.length > 1 && series.length <= 4) {
        const last = pts[pts.length - 1];
        add('text', { class: 'h-label', x: Math.min(W - R - 2, X(last.t.getTime()) + 6), y: Y(last.ppb) - 8, 'text-anchor': 'end' }, code);
      }
    });
    points.forEach((p) => {
      const c = add('circle', { class: 'h-pt', cx: X(p.t.getTime()), cy: Y(p.ppb), r: points.length > 120 ? 3 : 5, fill: cssVar(PAINT[p.cls] || '--ink-3') });
      const tt = document.createElementNS(NS_SVG, 'title');
      tt.textContent = `${fmtUgNum(p.ppb)} µg/L, ${t('class.' + (SERVER_KEY[p.cls] || p.cls))}, ${fmtDateTime(p.t)}${p.device_code ? ', ' + p.device_code : ''}`;
      c.appendChild(tt);
    });
    fillHistTable(points);
    const max = Math.max(...points.map((p) => p.ppb));
    $('histDesc').textContent = (local ? t('hist.local') + ' ' : '') +
      t('hist.desc', { n: points.length, a: fmtDateTime(new Date(t0)), b: fmtDateTime(new Date(t1)), max: fmtUgNum(max) }) +
      (series.length > 4 ? ' ' + t('hist.dailyMax') : '');
  }
  async function loadFleet() {
    if (!online()) {
      renderDevices(null);
      renderWarnings(null);
      renderTrendNote(null);
      const since = Date.now() - state.histHours * 3600e3;
      const pts = state.history.filter((h) => h.time.getTime() >= since).map((h) => ({ t: h.time, ppb: ugl(h.asMgL), cls: h.verdict })).reverse();
      drawHistory(pts, true);
      return;
    }
    try {
      const dev = state.histDevice ? `&device_code=${encodeURIComponent(state.histDevice)}` : '';
      $('deviceList').setAttribute('aria-busy', 'true');
      const [devs, hist, alerts] = await Promise.all([api('/api/devices'), api(`/api/readings/history?hours=${state.histHours}&limit=1000${dev}`),
        api('/api/alerts/recent?limit=20').catch(() => ({ alerts: [] }))]);
      $('deviceList').removeAttribute('aria-busy');
      renderDevices(devs);
      document.dispatchEvent(new CustomEvent('aquasentry:fleet', { detail: { devices: devs, device: state.histDevice } }));
      renderWarnings(alerts.alerts || []);
      renderTrendNote(devs);
      drawHistory(hist.map((p) => ({ t: new Date(p.t), ppb: p.ppb, cls: p.cls, device_code: p.device_code })), false);
    } catch (e) { renderDevices(null); }
  }

  // ---------------- live updates (Server-Sent Events) ----------------
  let live = null, fleetTimer = null, toastTimer = null;
  function toast(text, urgent) {
    const el = $('toast');
    if (!el) return;
    el.textContent = text;
    el.className = 'toast' + (urgent ? ' urgent' : '');
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, urgent ? 9000 : 5000);
  }
  function startLive() {
    if (live || !window.EventSource || !online()) return;
    live = new EventSource(UI().API + '/api/events');
    live.addEventListener('open', () => { $('livePill').hidden = false; });
    live.addEventListener('error', () => { $('livePill').hidden = true; });   // EventSource reconnects by itself
    live.addEventListener('reading', (e) => {
      let d; try { d = JSON.parse(e.data); } catch (err) { return; }
      clearTimeout(fleetTimer);
      fleetTimer = setTimeout(loadFleet, 700);
      // follow the device on screen whatever its source (v5.11: also the simulator opened with ?device=);
      // only a real device announces itself with a toast or replaces another reading
      if (state.reading && state.reading.device === d.device_code) loadLatestFromServer(d.device_code);
      else if (d.source_type === 'hardware' && (!state.reading || state.reading.source === 'device')) loadLatestFromServer(d.device_code);
      if (d.source_type === 'hardware') {
        toast(t('live.reading', { code: d.device_code, v: fmtUgNum(d.arsenic_ppb), cls: t('class.' + (SERVER_KEY[d.classification] || d.classification)) }), false);
      }
    });
    live.addEventListener('alert', (e) => {
      let a; try { a = JSON.parse(e.data); } catch (err) { return; }
      if (a.source_type === 'hardware') toast(a.message, true);
    });
  }
  function stopLive() { if (live) { live.close(); live = null; } if ($('livePill')) $('livePill').hidden = true; }

  function rerenderAll() {
    renderOverview();
    updateNetwork();
    renderContaminants();
    renderReport();
    renderDispatch();
    drawChart();
    drawSparks();
    loadFleet();
    $('testAsOut').textContent = $('testAs').value + ' µg/L';
    if (!$('runTestBtn').disabled) $('runTestBtn').textContent = t('test.run');
    if (state.device) { state.device.setLabels(deviceLabels()); $('explodeBtn').textContent = t(state.device.exploded ? 'dev.assemble' : 'dev.explode'); }
  }

  // ---------------- init ----------------
  document.addEventListener('DOMContentLoaded', () => {
    $('demoBtn').addEventListener('click', loadDemo);
    document.querySelectorAll('[data-quick]').forEach((b) => b.addEventListener('click', () => (
      b.dataset.quick === 'fault' ? runTest(0, { fault: true }) : runTest(parseFloat(b.dataset.quick), { quiet: true }))));
    $('testAs').addEventListener('input', () => { $('testAsOut').textContent = $('testAs').value + ' µg/L'; });
    $('runTestBtn').addEventListener('click', () => runTest(parseFloat($('testAs').value) / 1000));
    if ($('replayBtn')) $('replayBtn').addEventListener('click', () => $('replayFile').click());
    if ($('replayFile')) $('replayFile').addEventListener('change', (e) => { onReplayFile(e.target.files && e.target.files[0]); e.target.value = ''; });
    if ($('viewScanBtn')) $('viewScanBtn').addEventListener('click', () => viewScan(state.reading && state.reading.scanId));
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
    document.addEventListener('aquasentry:theme', () => { drawChart(); drawSparks(); loadFleet(); });
    document.addEventListener('aquasentry:online', (e) => {
      renderReport(); loadFleet();
      if (e.detail.online) { loadLatestFromServer(urlDevice() || undefined); startLive(); } else stopLive();
    });
    document.querySelectorAll('[data-hist]').forEach((b) => b.addEventListener('click', () => {
      state.histHours = Number(b.dataset.hist);
      document.querySelectorAll('[data-hist]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      loadFleet();
    }));
    setInterval(() => { if (online() && !document.hidden) loadFleet(); }, 60000);
    setInterval(() => { if (!document.hidden) renderMeta(); }, 60000);   // v5.7: the "reading is old" warning keeps up

    const canvas = $('heroFx');
    if (canvas && UI().WaterFX) { state.fx = new (UI().WaterFX)(canvas); if (!state.fx.ok) state.fx = null; }
    initRing();
    rerenderAll();
    lazyDevice();
  });
})();
