/**
 * Public page for one water source (opened from the QR sticker on a handpump or tap).
 * Shows the latest verdict in plain words, what to do, any caveat and the latest lab confirmation.
 * ?sticker=1 shows a printable QR sticker for the same page. Reads /api/public/devices/<code> only.
 */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const t = (k, v) => window.I18N.t(k, v);
  const params = new URLSearchParams(location.search);
  const code = params.get('code') || '';
  const API = window.AQUASENTRY_API_URL || (location.port === '8001' ? 'http://127.0.0.1:8000' : location.origin);
  const VCLS = { Safe: 'Safe', 'Below Sensor LOD': 'Clear', Caution: 'Caution', Unsafe: 'Unsafe', Hazardous: 'Hazardous', 'Test Failed': 'Failed' };
  let data = null;

  try { const th = localStorage.getItem('aquasentry.theme'); if (th) document.documentElement.setAttribute('data-theme', th); } catch (e) { /* default */ }

  function locale() { return ({ hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', pa: 'pa-IN' })[window.I18N.lang] || 'en-IN'; }
  function when(iso) {
    const d = new Date(iso);
    try { return d.toLocaleString(locale(), { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch (e) { return d.toISOString(); }
  }
  function ageDays(iso) { return (Date.now() - new Date(iso).getTime()) / 86400e3; }

  function render() {
    const card = $('pubCard');
    if (!data) return;
    const place = [data.name, data.village, data.district].filter(Boolean).join(', ') || data.device_code;
    $('pubPlace').textContent = place;
    document.title = `AquaSentry — ${place}`;
    const r = data.latest;
    if (!r) {
      $('pubVerdict').textContent = t('verdict.none.title');
      card.className = 'pub-card none';
      return;
    }
    const v = VCLS[r.classification] || 'Caution';
    card.className = 'pub-card v-' + v;
    $('pubVerdict').textContent = t('verdict.' + v + '.title');
    // v5.7: below the 20 µg/L detection limit the number is noise, so it is not shown as "x µg/L (limit 10)";
    // a failed test has no valid number at all
    $('pubValue').textContent = v === 'Failed' ? t('pub.failed')
      : r.arsenic_ug_l < 20 ? t('pub.valueLow')
        : t('pub.value', { v: Math.round(r.arsenic_ug_l) });
    const old = ageDays(r.recorded_at);
    $('pubWhen').textContent = t('pub.when', { d: when(r.recorded_at) }) + (old > 3 ? ' ' + t('pub.old', { n: Math.round(old) }) : '');
    $('pubWhen').classList.toggle('stale', old > 3);
    $('pubDo').textContent = t('verdict.' + v + '.action');
    $('pubSteps').hidden = !(v === 'Unsafe' || v === 'Hazardous');
    $('pubDemo').hidden = !r.is_demo;
    const qc = $('pubQc');
    // translated on the page from the flags (the server's caveat sentences are English only)
    const QCK = { FLAT_SIGNAL: 'qc.FLAT_SIGNAL', NOISE_ABOVE_LOD: 'qc.NOISE', BASELINE_UNSTABLE: 'qc.NOISE', PEAK_AT_WINDOW_EDGE: 'qc.PEAK_EDGE',
      QC_NOT_REPORTED: 'qc.NO_QC', CHECK_STANDARD_MISSING: 'qc.UNVERIFIED', CHECK_STANDARD_FAILED: 'qc.UNVERIFIED',
      CHECK_STANDARD_OVERDUE: 'qc.UNVERIFIED', CALIBRATION_MISSING: 'qc.UNVERIFIED', CALIBRATION_EXPIRED: 'qc.UNVERIFIED' };
    const keys = [];
    (r.qc_flags || []).forEach((f) => {
      const k = ['as3_only', 'copper_interference', 'uncalibrated'].includes(f) ? 'qc.' + f : QCK[f];
      if (k && !keys.includes(k)) keys.push(k);
    });
    qc.hidden = !keys.length;
    qc.innerHTML = '';
    keys.forEach((k) => { const li = document.createElement('li'); li.textContent = t(k); qc.appendChild(li); });
    const lab = $('pubLab');
    lab.hidden = !data.lab;
    if (data.lab) {
      lab.textContent = t(data.lab.above_limit ? 'pub.labBad' : 'pub.labOk',
        { v: data.lab.arsenic_ug_l, m: data.lab.lab_method, d: new Date(data.lab.sampled_at).toLocaleDateString(locale()) });
      lab.className = 'pub-lab ' + (data.lab.above_limit ? 'bad' : 'ok');
    }
  }

  function sticker() {
    const box = $('sticker');
    box.hidden = false;
    document.body.classList.add('sticker-mode');
    const url = `${location.origin}${location.pathname}?code=${encodeURIComponent(code)}`;
    const qr = window.qrcode(0, 'M');              // error correction M: survives some dirt and scratches
    qr.addData(url);
    qr.make();
    $('stickerQr').innerHTML = qr.createSvgTag({ cellSize: 6, margin: 2, scalable: true });
    $('stickerName').textContent = data ? [data.name, data.village].filter(Boolean).join(', ') || code : code;
    $('stickerUrl').textContent = url.replace(/^https?:\/\//, '');
    $('stickerPrint').addEventListener('click', () => window.print());
  }

  async function load() {
    if (!code) { $('pubVerdict').textContent = t('pub.nocode'); return; }
    try {
      const res = await fetch(`${API}/api/public/devices/${encodeURIComponent(code)}`);
      if (!res.ok) throw new Error(String(res.status));
      data = await res.json();
      render();
    } catch (e) {
      $('pubVerdict').textContent = t('pub.error');
    }
    if (params.get('sticker')) sticker();
  }

  document.addEventListener('aquasentry:lang', () => { render(); if (!$('sticker').hidden && data) $('stickerName').textContent = [data.name, data.village].filter(Boolean).join(', ') || code; });
  document.addEventListener('DOMContentLoaded', load);
})();
