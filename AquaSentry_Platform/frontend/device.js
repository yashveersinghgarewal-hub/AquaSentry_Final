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
  const VCLS = { Safe: 'Safe', 'Below Sensor LOD': 'Clear', Caution: 'Caution', Unsafe: 'Unsafe', Hazardous: 'Hazardous' };
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
    $('pubValue').textContent = t('pub.value', { v: r.arsenic_ug_l < 10 ? r.arsenic_ug_l.toFixed(1) : Math.round(r.arsenic_ug_l) });
    const old = ageDays(r.recorded_at);
    $('pubWhen').textContent = t('pub.when', { d: when(r.recorded_at) }) + (old > 3 ? ' ' + t('pub.old', { n: Math.round(old) }) : '');
    $('pubWhen').classList.toggle('stale', old > 3);
    $('pubDo').textContent = t('verdict.' + v + '.action');
    $('pubSteps').hidden = !(v === 'Unsafe' || v === 'Hazardous');
    $('pubDemo').hidden = !r.is_demo;
    const qc = $('pubQc');
    // translated on the page from the flags (the server's caveat sentences are English only)
    const flags = (r.qc_flags || []).filter((f) => ['as3_only', 'copper_interference', 'uncalibrated'].includes(f));
    qc.hidden = !flags.length;
    qc.innerHTML = '';
    flags.forEach((f) => { const li = document.createElement('li'); li.textContent = t('qc.' + f); qc.appendChild(li); });
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
