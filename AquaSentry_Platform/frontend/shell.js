/**
 * AquaSentry shared page shell — used by every page (dashboard, market research, sales, device simulator).
 *  - theme (carbon black / light), mobile menu, "limelight" nav indicator + scroll spy
 *  - server connection pill (works offline; pages listen for the 'aquasentry:online' event)
 *  - water-quality assistant chat
 *  - effects: scroll reveal, cursor spotlight, 3D tilt, number tickers, range-slider fill, WebGL water caustics
 * Everything degrades gracefully: no WebGL -> CSS gradient, reduced motion -> no animation.
 */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const t = (k, v) => (window.I18N ? window.I18N.t(k, v) : k);
  const reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const API = window.AQUASENTRY_API_URL ||
    ((location.protocol === 'file:' || location.port === '8001') ? 'http://127.0.0.1:8000' : location.origin);

  const UI = { API, online: false, reduceMotion };

  async function api(path, opts, timeoutMs) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs || 4000);
    try {
      const res = await fetch(API + path, Object.assign({ signal: ctrl.signal, credentials: 'same-origin' }, opts || {}));
      if (res.status === 401 && (!opts || !opts.method || opts.method === 'GET')) document.dispatchEvent(new CustomEvent('aquasentry:signin'));
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return await res.json();
    } finally { clearTimeout(timer); }
  }
  UI.api = api;

  // ---------------- theme ----------------
  function toggleTheme() {
    const root = document.documentElement;
    const next = (root.getAttribute('data-theme') || 'dark') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('aquasentry.theme', next); } catch (e) { /* ignore */ }
    document.dispatchEvent(new CustomEvent('aquasentry:theme', { detail: { theme: next } }));
  }

  // ---------------- menu + limelight nav ----------------
  function setMenu(open) {
    const rail = $('rail'); if (!rail) return;
    rail.classList.toggle('open', open);
    if ($('railBackdrop')) $('railBackdrop').hidden = !open;
    if ($('menuBtn')) $('menuBtn').setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function moveLime() {
    document.querySelectorAll('.nav-group').forEach((g) => {
      const lime = g.querySelector('.nav-lime');
      const act = g.querySelector('.nav-link[aria-current="true"], .nav-link[aria-current="page"]');
      if (!lime) return;
      if (!act) { lime.style.opacity = '0'; return; }
      lime.style.opacity = '1';
      lime.style.height = act.offsetHeight + 'px';
      lime.style.transform = `translateY(${act.offsetTop}px)`;
    });
  }
  function initScrollSpy() {
    const links = Array.from(document.querySelectorAll('.nav-link[data-section]'));
    if (!links.length) { moveLime(); return; }
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        links.forEach((l) => l.setAttribute('aria-current', l.dataset.section === en.target.id ? 'true' : 'false'));
        moveLime();
      });
    }, { rootMargin: '-35% 0px -60% 0px' });
    links.forEach((l) => { const s = $(l.dataset.section); if (s) obs.observe(s); l.addEventListener('click', () => setMenu(false)); });
    links[0].setAttribute('aria-current', 'true');
    moveLime();
  }

  // ---------------- connection pill ----------------
  function renderConn() {
    const c = $('conn'); if (!c) return;
    c.dataset.state = UI.online ? 'online' : 'offline';
    if ($('connText')) $('connText').textContent = t(UI.online ? 'conn.online' : 'conn.offline');
  }
  async function checkServer() {
    const was = UI.online;
    try { await api('/api/health', null, 2500); UI.online = true; } catch (e) { UI.online = false; }
    renderConn();
    if (UI.online !== was || !UI._checked) document.dispatchEvent(new CustomEvent('aquasentry:online', { detail: { online: UI.online, first: !UI._checked } }));
    UI._checked = true;
    return UI.online;
  }
  UI.checkServer = checkServer;

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
    const p = $('chatPanel'); if (!p) return;
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
    if (!UI.online) { addMsg(t('chat.offline'), 'bot'); return; }
    const wait = addMsg(t('chat.thinking'), 'bot wait');
    try {
      const msg = window.I18N && window.I18N.lang === 'hi' ? `Please answer in simple Hindi. ${text}` : text;
      const d = await api('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) }, 30000);
      wait.remove(); addMsg(d.reply || '…', 'bot');
    } catch (err) { wait.remove(); addMsg(t('chat.offline'), 'bot'); }
  }

  // ---------------- effects ----------------
  function initReveal(root) {
    const els = (root || document).querySelectorAll('[data-reveal]:not(.is-in)');
    if (reduceMotion || !('IntersectionObserver' in window)) { els.forEach((e) => e.classList.add('is-in')); return; }
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('is-in'); obs.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    els.forEach((e) => obs.observe(e));
  }
  UI.reveal = initReveal;

  function initSpotlight() {
    document.addEventListener('pointermove', (e) => {
      const card = e.target.closest && e.target.closest('.spot');
      if (!card) return;
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }, { passive: true });
  }
  function initTilt() {
    if (reduceMotion || !matchMedia('(hover: hover)').matches) return;
    document.addEventListener('pointermove', (e) => {
      const card = e.target.closest && e.target.closest('.tilt');
      document.querySelectorAll('.tilt[data-tilting]').forEach((c) => { if (c !== card) { c.style.transform = ''; delete c.dataset.tilting; } });
      if (!card) return;
      const r = card.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      card.dataset.tilting = '1';
      card.style.transform = `perspective(900px) rotateX(${(-y * 5).toFixed(2)}deg) rotateY(${(x * 6).toFixed(2)}deg) translateY(-2px)`;
    }, { passive: true });
  }

  /** Animate a number into an element. fmt: function(value) -> string */
  function countTo(el, to, fmt, ms) {
    fmt = fmt || ((v) => Math.round(v).toLocaleString('en-IN'));
    if (reduceMotion || !isFinite(to)) { el.textContent = fmt(to); el._v = to; return; }
    const from = typeof el._v === 'number' ? el._v : 0;
    const dur = ms || 1100, t0 = performance.now();
    cancelAnimationFrame(el._raf);
    const step = (now) => {
      const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 4);
      el.textContent = fmt(from + (to - from) * e);
      if (p < 1) el._raf = requestAnimationFrame(step); else el._v = to;
    };
    el._raf = requestAnimationFrame(step);
  }
  UI.countTo = countTo;
  function initTickers(root) {
    const els = (root || document).querySelectorAll('[data-count]');
    const go = (el) => {
      const dec = parseInt(el.dataset.dec || '0', 10), pre = el.dataset.pre || '', suf = el.dataset.suf || '';
      countTo(el, parseFloat(el.dataset.count), (v) => pre + v.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf, 1600);
    };
    if (!('IntersectionObserver' in window)) { els.forEach(go); return; }
    const obs = new IntersectionObserver((entries) => entries.forEach((en) => { if (en.isIntersecting) { go(en.target); obs.unobserve(en.target); } }), { threshold: 0.4 });
    els.forEach((e) => obs.observe(e));
  }
  UI.tickers = initTickers;

  function fillRange(r) { const p = (r.value - r.min) / ((r.max - r.min) || 1) * 100; r.style.setProperty('--fill', p + '%'); }
  UI.fillRange = fillRange;
  function initRanges() {
    document.querySelectorAll('input[type="range"]').forEach(fillRange);
    document.addEventListener('input', (e) => { if (e.target.type === 'range') fillRange(e.target); });
  }

  // ---------------- WebGL water caustics (hero background) ----------------
  const FRAG = `precision mediump float;
uniform vec2 r; uniform float t; uniform vec3 c1; uniform vec3 c2;
void main(){
  vec2 uv = gl_FragCoord.xy / r;
  vec2 p = uv * vec2(r.x / r.y, 1.0) * 4.2 - vec2(250.0);
  float time = t * 0.22 + 23.0;
  vec2 i = p; float c = 1.0; float inten = 0.005;
  for (int n = 0; n < 4; n++) {
    float tt = time * (1.0 - (3.5 / float(n + 1)));
    i = p + vec2(cos(tt - i.x) + sin(tt + i.y), sin(tt - i.y) + cos(tt + i.x));
    c += 1.0 / length(vec2(p.x / (sin(i.x + tt) / inten), p.y / (cos(i.y + tt) / inten)));
  }
  c /= 4.0; c = 1.17 - pow(max(c, 0.0), 1.4);
  float v = clamp(pow(abs(c), 8.0), 0.0, 1.0);
  float glow = smoothstep(1.3, 0.0, length((uv - vec2(0.85, 0.85)) * vec2(1.0, 1.25)));
  vec3 col = c2 + c1 * (0.05 + 0.32 * glow) + c1 * v * (0.18 + 0.55 * glow);
  gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}`;
  const VERT = 'attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }';
  function hexToRgb(h) { h = h.trim().replace('#', ''); if (h.length === 3) h = h.split('').map((x) => x + x).join(''); const n = parseInt(h, 16); return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; }

  class WaterFX {
    constructor(canvas) {
      this.c = canvas; this.color = [0.23, 0.51, 0.96]; this.target = this.color.slice(); this.base = [0.008, 0.016, 0.04];
      const gl = canvas.getContext('webgl', { antialias: false, premultipliedAlpha: false, alpha: false, powerPreference: 'low-power' });
      if (!gl) { canvas.remove(); this.ok = false; return; }
      this.gl = gl; this.ok = true;
      const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
      const prog = gl.createProgram();
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG)); gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { canvas.remove(); this.ok = false; return; }
      gl.useProgram(prog);
      const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(prog, 'a'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      this.u = { r: gl.getUniformLocation(prog, 'r'), t: gl.getUniformLocation(prog, 't'), c1: gl.getUniformLocation(prog, 'c1'), c2: gl.getUniformLocation(prog, 'c2') };
      this.t0 = performance.now(); this.visible = true;
      new IntersectionObserver((en) => { this.visible = en[0].isIntersecting; if (this.visible) this.loop(); }).observe(canvas);
      document.addEventListener('visibilitychange', () => { if (!document.hidden) this.loop(); });
      window.addEventListener('resize', () => this.resize());
      this.resize(); this.loop();
    }
    setColor(hex) { this.target = hexToRgb(hex); if (reduceMotion) { this.color = this.target.slice(); this.frame(); } }
    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5) * 0.6;   // render at reduced resolution: it's a soft background
      const w = Math.max(1, Math.round(this.c.clientWidth * dpr)), h = Math.max(1, Math.round(this.c.clientHeight * dpr));
      if (this.c.width !== w || this.c.height !== h) { this.c.width = w; this.c.height = h; this.gl.viewport(0, 0, w, h); }
      if (reduceMotion) this.frame();
    }
    frame() {
      const gl = this.gl;
      for (let i = 0; i < 3; i++) this.color[i] += (this.target[i] - this.color[i]) * 0.06;
      gl.uniform2f(this.u.r, this.c.width, this.c.height);
      gl.uniform1f(this.u.t, reduceMotion ? 8.0 : (performance.now() - this.t0) / 1000);
      gl.uniform3fv(this.u.c1, this.color); gl.uniform3fv(this.u.c2, this.base);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    loop() {
      if (this.running || reduceMotion) { if (reduceMotion) this.frame(); return; }
      this.running = true;
      const tick = () => {
        if (!this.visible || document.hidden) { this.running = false; return; }
        this.frame(); requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
  }
  UI.WaterFX = WaterFX;
  UI.cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ---------------- init ----------------
  // Offline support: only on secure origins (localhost, the desktop app, HTTPS) - browsers do not allow it on plain LAN HTTP.
  if ('serviceWorker' in navigator && window.isSecureContext && location.protocol !== 'file:') {
    window.addEventListener('load', () => { navigator.serviceWorker.register('sw.js').catch(() => {}); });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if ($('menuBtn')) $('menuBtn').addEventListener('click', () => setMenu(!$('rail').classList.contains('open')));
    if ($('railBackdrop')) $('railBackdrop').addEventListener('click', () => setMenu(false));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { setMenu(false); toggleChat(false); } });
    if ($('themeBtn')) $('themeBtn').addEventListener('click', toggleTheme);
    if ($('chatFab')) {
      $('chatFab').addEventListener('click', () => toggleChat());
      $('chatClose').addEventListener('click', () => toggleChat(false));
      $('chatForm').addEventListener('submit', sendChat);
    }
    document.addEventListener('aquasentry:lang', () => { renderConn(); setTimeout(moveLime, 30); });
    window.addEventListener('resize', moveLime);
    initScrollSpy(); initReveal(); initSpotlight(); initTilt(); initTickers(); initRanges();
    renderConn();
    checkServer();
    setInterval(checkServer, 30000);
  });

  window.AquaUI = UI;
})();
