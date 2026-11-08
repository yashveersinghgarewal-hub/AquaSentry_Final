/**
 * AquaSentry v5.6 field features on the dashboard:
 *  - map of sensor nodes (Leaflet + OpenStreetMap, loaded only when the map scrolls into view)
 *  - lab checks: sensor-vs-lab summary, the latest lab results, and a form to add one
 *  - tools for the selected device: public page, printable QR sticker, Jal Jeevan Mission CSV
 *  - "Get alerts on this phone" (Web Push through the service worker)
 *  - sign-in dialog when the server keeps its data private (AQUASENTRY_READ_KEY)
 * Listens for 'aquasentry:fleet' (devices loaded) from app.js. Works without the server: it just hides.
 */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const t = (k, v) => window.I18N.t(k, v);
  const UI = () => window.AquaUI;
  const online = () => !!(UI() && UI().online);
  const esc = (x) => String(x == null ? '' : x).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (u) => (u < 10 ? Number(u).toFixed(1) : String(Math.round(u)));
  const VERDICT_CLASS = { Safe: 'safe', 'Below Sensor LOD': 'safe', Caution: 'caution', Unsafe: 'unsafe', Hazardous: 'haz' };
  const state = { devices: [], device: null, map: null, layer: null, leaflet: null };

  async function api(path, opts) {
    const res = await fetch(UI().API + path, Object.assign({ credentials: 'same-origin' }, opts || {}));
    if (res.status === 401) { document.dispatchEvent(new CustomEvent('aquasentry:signin')); throw new Error('401'); }
    if (!res.ok) {
      let detail = 'HTTP ' + res.status;
      try { const j = await res.json(); if (j.detail) detail = typeof j.detail === 'string' ? j.detail : j.detail[0].msg; } catch (e) { /* not JSON */ }
      throw new Error(detail);
    }
    return res.status === 204 ? null : res.json();
  }
  function loadScript(src) {
    return new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = fail; document.head.appendChild(s); });
  }
  function loadCss(href) {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l);
  }

  // ---------------------------------------------------------------- map
  function placed() { return state.devices.filter((d) => d.site && d.site.latitude != null && d.site.longitude != null); }

  function ensureMap() {
    if (state.leaflet) return state.leaflet;
    loadCss('vendor/leaflet.css');
    state.leaflet = loadScript('vendor/leaflet.js').then(() => {
      const L = window.L;
      state.map = L.map('nodeMap', { scrollWheelZoom: false, attributionControl: true }).setView([23.5, 85.5], 5);
      state.map.attributionControl.setPrefix('Leaflet');
      L.tileLayer((window.AQUASENTRY_TILES || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'), {
        maxZoom: 18, attribution: '&copy; OpenStreetMap contributors',
      }).addTo(state.map);
      state.layer = L.layerGroup().addTo(state.map);
    });
    return state.leaflet;
  }

  function drawMap() {
    const pts = placed();
    const card = $('mapCard');
    if (!card) return;
    $('mapNote').textContent = pts.length ? t('map.note', { n: pts.length }) : t('map.none');
    $('nodeMap').hidden = !pts.length;
    if (!pts.length) return;
    ensureMap().then(() => {
      const L = window.L;
      state.layer.clearLayers();
      const style = getComputedStyle(document.documentElement);
      const paint = (cls) => style.getPropertyValue({ safe: '--paint-safe', caution: '--paint-caution', unsafe: '--paint-unsafe', haz: '--paint-haz' }[cls] || '--ink-3').trim() || '#888';
      const bounds = [];
      pts.forEach((d) => {
        const cls = d.latest ? VERDICT_CLASS[d.latest.classification] || 'none' : 'none';
        const ll = [d.site.latitude, d.site.longitude];
        bounds.push(ll);
        const m = L.circleMarker(ll, { radius: 10, weight: 2, color: '#1b1b1b', fillColor: paint(cls), fillOpacity: 0.95 });
        const name = d.site.name || d.site.village || d.device_code;
        const val = d.latest ? `${num(d.latest.arsenic_ppb)} µg/L · ${esc(t('class.' + (d.latest.classification === 'Below Sensor LOD' ? 'Clear' : d.latest.classification)))}` : esc(t('verdict.none.title'));
        m.bindPopup(`<b>${esc(name)}</b><br>${val}<br><a href="device.html?code=${encodeURIComponent(d.device_code)}" target="_blank" rel="noopener">${esc(t('dev.page'))}</a>`);
        m.bindTooltip(`${esc(name)}: ${val}`);
        m.addTo(state.layer);
      });
      if (bounds.length === 1) state.map.setView(bounds[0], 12);
      else state.map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });
      setTimeout(() => state.map.invalidateSize(), 50);
    }).catch(() => { $('mapNote').textContent = t('map.offline', { n: pts.length }); });
  }

  function lazyMap() {
    const el = $('mapCard');
    if (!el || !('IntersectionObserver' in window)) { drawMap(); return; }
    let seen = false;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { seen = true; io.disconnect(); drawMap(); } }, { rootMargin: '300px' });
    io.observe(el);
    lazyMap.ready = () => seen;
  }

  // ---------------------------------------------------------------- device tools
  function renderTools() {
    const box = $('devTools');
    if (!box) return;
    const code = state.device;
    box.hidden = !code;
    if (!code) return;
    const c = encodeURIComponent(code);
    $('devPage').href = `device.html?code=${c}`;
    $('devSticker').href = `device.html?code=${c}&sticker=1`;
    $('devJjm').href = `${UI().API}/api/data/export/jjm?device_code=${c}`;
  }

  // ---------------------------------------------------------------- lab checks
  function fmtDate(iso) {
    const d = new Date(iso);
    const lang = { hi: 'hi-IN', bn: 'bn-IN', as: 'as-IN', pa: 'pa-IN' }[window.I18N.lang] || 'en-IN';
    try { return d.toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' }); } catch (e) { return d.toISOString().slice(0, 10); }
  }
  async function loadLab() {
    const card = $('labCard');
    if (!card) return;
    card.hidden = !online();
    if (!online()) return;
    const q = state.device ? `?device_code=${encodeURIComponent(state.device)}` : '';
    try {
      const [v, rows] = await Promise.all([api('/api/validation' + q), api('/api/lab-results' + (q ? q + '&' : '?') + 'limit=8')]);
      const sum = $('labSummary');
      if (!v.n_pairs) sum.textContent = rows.length ? t('lab.unpaired') : t('lab.none');
      else {
        const one = (key, n) => (n === 1 && ['en', 'hi'].includes(window.I18N.lang) ? key + '.one' : key);
        const parts = [t(one('lab.pairs', v.n_pairs), { n: v.n_pairs })];
        if (v.lab_above_limit) parts.push(v.missed_unsafe ? t('lab.missed', { m: v.missed_unsafe, n: v.lab_above_limit }) : t(one('lab.caught', v.lab_above_limit), { n: v.lab_above_limit }));
        if (v.mean_bias_ug_l != null) parts.push(t('lab.bias', { b: (v.mean_bias_ug_l > 0 ? '+' : '') + v.mean_bias_ug_l }));
        if (v.lab_as3_fraction != null) parts.push(t('lab.as3', { p: Math.round(v.lab_as3_fraction * 100) }));
        sum.textContent = parts.join(' ');
      }
      sum.className = 'lab-summary' + (v.missed_unsafe ? ' bad' : v.n_pairs ? ' ok' : '');
      const tb = $('labTable');
      tb.hidden = !rows.length;
      tb.querySelector('tbody').innerHTML = rows.map((r) => `<tr><td>${esc(fmtDate(r.sampled_at))}</td><td>${esc(r.device_code)}</td>` +
        `<td class="num">${r.node_arsenic_ug_l == null ? '–' : num(r.node_arsenic_ug_l)}</td><td class="num">${num(r.arsenic_ug_l)}</td>` +
        `<td>${esc(r.lab_method)}${r.nabl_accredited ? ' · NABL' : ''}</td></tr>`).join('');
    } catch (e) { /* lab panel stays as it was */ }
  }
  function fillLabDevices() {
    const sel = $('labDevice');
    if (!sel) return;
    const keep = sel.value || state.device;
    const hw = state.devices.filter((d) => d.is_hardware);
    const list = hw.length ? hw : state.devices;
    sel.innerHTML = list.map((d) => `<option value="${esc(d.device_code)}">${esc(d.device_code)}${d.site && d.site.name ? ' · ' + esc(d.site.name) : ''}</option>`).join('');
    if (keep && list.some((d) => d.device_code === keep)) sel.value = keep;
    if (!$('labDate').value) $('labDate').value = new Date().toISOString().slice(0, 10);
  }
  async function saveLab(ev) {
    ev.preventDefault();
    const msg = $('labMsg');
    const as3 = $('labAs3').value;
    const body = {
      device_code: $('labDevice').value, arsenic_ug_l: Number($('labAs').value), lab_method: $('labMethod').value,
      sampled_at: new Date($('labDate').value + 'T12:00:00').toISOString(), lab_name: $('labName').value || null,
      nabl_accredited: $('labNabl').checked, as3_ug_l: as3 === '' ? null : Number(as3),
    };
    msg.textContent = t('lab.saving');
    try {
      const r = await api('/api/lab-results', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      msg.textContent = r.node_arsenic_ug_l == null ? t('lab.savedNoPair') : t('lab.saved', { v: num(r.node_arsenic_ug_l) });
      $('labAs').value = ''; $('labAs3').value = '';
      loadLab();
    } catch (e) { msg.textContent = t('lab.error', { e: e.message }); }
  }

  // ---------------------------------------------------------------- push alerts
  function b64ToBytes(b64) {
    const pad = '='.repeat((4 - (b64.length % 4)) % 4);
    const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
  }
  const isIos = () => /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;

  async function pushState() {
    const box = $('pushBox');
    if (!box) return;
    if (!online() || !('serviceWorker' in navigator)) { box.hidden = true; return; }
    let ch;
    try { ch = await api('/api/alerts/channels'); } catch (e) { box.hidden = true; return; }
    if (!ch.webpush || !ch.webpush.available) { box.hidden = true; return; }
    box.hidden = false;
    state.vapid = ch.webpush.public_key;
    const note = $('pushNote'), btn = $('pushBtn');
    if (!('PushManager' in window)) {
      btn.disabled = true;
      note.textContent = isIos() && !standalone() ? t('push.ios') : t('push.unsupported');
      return;
    }
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    btn.disabled = false;
    btn.textContent = t(sub ? 'push.off' : 'push.on');
    btn.dataset.on = sub ? '1' : '';
    note.textContent = Notification.permission === 'denied' ? t('push.denied') : sub ? t('push.active') : t('push.why');
  }
  async function togglePush() {
    const btn = $('pushBtn'), note = $('pushNote');
    btn.disabled = true;
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await api('/api/alerts/unsubscribe/webpush', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ endpoint: sub.endpoint }) });
        await sub.unsubscribe();
      } else {
        const perm = await Notification.requestPermission();     // from the click, as iOS requires
        if (perm !== 'granted') { note.textContent = t('push.denied'); return; }
        const s = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(state.vapid) });
        const lang = ['en', 'hi', 'bn', 'as', 'pa'].includes(window.I18N.lang) ? window.I18N.lang : 'en';
        await api('/api/alerts/subscribe/webpush', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subscription: s.toJSON(), device_code: state.device || null, language: lang }) });
      }
    } catch (e) { note.textContent = t('push.error', { e: e.message }); } finally { btn.disabled = false; pushState(); }
  }

  // ---------------------------------------------------------------- sign in
  let asked = false;
  function askSignIn() {
    const dlg = $('signinDlg');
    if (!dlg || asked || dlg.open || typeof dlg.showModal !== 'function') return;
    asked = true;
    $('signinMsg').textContent = '';
    dlg.showModal();
    $('signinKey').focus();
  }
  async function signIn(ev) {
    ev.preventDefault();
    try {
      await api('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: $('signinKey').value }) });
      $('signinDlg').close();
      document.dispatchEvent(new CustomEvent('aquasentry:online', { detail: { online: true } }));
    } catch (e) { $('signinMsg').textContent = t('signin.wrong'); }
  }

  // ---------------------------------------------------------------- wiring
  document.addEventListener('aquasentry:fleet', (e) => {
    state.devices = e.detail.devices || [];
    state.device = e.detail.device || null;
    renderTools();
    fillLabDevices();
    loadLab();
    if (!lazyMap.ready || lazyMap.ready()) drawMap();
  });
  document.addEventListener('aquasentry:signin', askSignIn);
  document.addEventListener('aquasentry:online', () => { pushState(); });
  document.addEventListener('aquasentry:lang', () => { drawMap(); loadLab(); pushState(); });
  document.addEventListener('aquasentry:theme', drawMap);
  document.addEventListener('DOMContentLoaded', () => {
    lazyMap();
    if ($('labForm')) $('labForm').addEventListener('submit', saveLab);
    if ($('pushBtn')) $('pushBtn').addEventListener('click', togglePush);
    if ($('signinForm')) $('signinForm').addEventListener('submit', signIn);
    if ($('signinCancel')) $('signinCancel').addEventListener('click', () => $('signinDlg').close());
    fetch((UI() ? UI().API : '') + '/api/auth/status', { credentials: 'same-origin' }).then((r) => r.json())
      .then((s) => { if (s.map_tiles) window.AQUASENTRY_TILES = s.map_tiles; if (s.read_protected && !s.signed_in) askSignIn(); }).catch(() => {});
  });
})();
