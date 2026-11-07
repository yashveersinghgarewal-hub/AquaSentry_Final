/**
 * AquaSentry motion layer (v5.1) — loaded on every page after shell.js.
 *  - animated 3D dotted-wave background that ripples around the cursor (canvas 2D, pauses when hidden)
 *  - soft blue cursor light, top scroll-progress bar, sweeping light beam
 *  - word-by-word heading reveal, text "decode" effect, magnetic buttons, hero parallax
 * Everything is skipped or frozen when the user prefers reduced motion.
 */
(function () {
  'use strict';
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = window.matchMedia && matchMedia('(hover: hover) and (pointer: fine)').matches;
  const pointer = { x: -9999, y: -9999, tx: -9999, ty: -9999, active: false };

  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

  // ---------------- dotted wave background ----------------
  function initWave() {
    const c = document.createElement('canvas');
    c.className = 'bg-wave'; c.setAttribute('aria-hidden', 'true');
    document.body.prepend(c);
    const ctx = c.getContext('2d');
    let W = 0, H = 0, dpr = 1, rgb = '120,170,255', running = false, visible = true, last = 0;
    const COLS = 64, ROWS = 26;
    function size() {
      dpr = Math.min(window.devicePixelRatio || 1, 1.25);
      W = c.width = Math.round(innerWidth * dpr); H = c.height = Math.round(innerHeight * dpr);
      rgb = cssVar('--fx-dot') || rgb;
    }
    function draw(time) {
      ctx.clearRect(0, 0, W, H);
      const t = reduce ? 0 : time / 1000;
      const horizon = H * 0.50, fov = H * 0.9, camY = 1.15;
      const px = pointer.x * dpr, py = pointer.y * dpr;
      for (let r = 0; r < ROWS; r++) {
        const z = 1.2 + r * 0.42;                                   // depth (near -> far)
        for (let i = 0; i < COLS; i++) {
          const x = (i / (COLS - 1) - 0.5) * 14;
          let y = Math.sin(x * 0.55 + t * 0.9) * 0.22 + Math.cos(z * 0.7 - t * 1.1) * 0.24 + Math.sin((x + z) * 0.35 + t * 0.6) * 0.12;
          let sx = W / 2 + (x / z) * fov, sy = horizon + ((camY - y) / z) * fov * 0.55;
          if (fine && pointer.active) {                              // ripple lift near the cursor
            const dx = sx - px, dy = sy - py, d2 = dx * dx + dy * dy, R = 160 * dpr;
            if (d2 < R * R) { const k = 1 - Math.sqrt(d2) / R; sy -= k * k * 26 * dpr; }
          }
          if (sx < -10 || sx > W + 10 || sy > H + 10) continue;
          const depth = 1 - r / ROWS, crest = Math.max(0, y) * 1.6, fade = Math.min(1, Math.max(0, (sy / H - 0.42) / 0.2));
          const a = (0.06 + 0.42 * depth * depth) * (0.65 + crest) * fade;
          if (a < 0.01) continue;
          const s = (0.9 + 1.9 * depth) * dpr;
          ctx.fillStyle = `rgba(${rgb},${Math.min(0.75, a).toFixed(3)})`;
          ctx.fillRect(sx - s / 2, sy - s / 2, s, s);
        }
      }
    }
    function loop() {
      if (running || reduce) return;
      running = true;
      const tick = (time) => {
        if (!visible || document.hidden) { running = false; return; }
        if (time - last > 33) { draw(time); last = time; }        // ~30 fps is plenty for a background
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
    size(); draw(0);
    window.addEventListener('resize', () => { size(); draw(performance.now()); });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) loop(); });
    document.addEventListener('aquasentry:theme', () => { rgb = cssVar('--fx-dot') || rgb; draw(performance.now()); });
    loop();
  }

  // ---------------- cursor light + progress bar + beam ----------------
  function initChrome() {
    const bar = document.createElement('div'); bar.className = 'scroll-progress'; bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    const beam = document.createElement('div'); beam.className = 'top-beam'; beam.setAttribute('aria-hidden', 'true');
    document.body.prepend(beam);
    const onScroll = () => {
      const h = document.documentElement.scrollHeight - innerHeight;
      bar.style.transform = `scaleX(${h > 0 ? Math.min(1, scrollY / h) : 0})`;
    };
    addEventListener('scroll', onScroll, { passive: true }); onScroll();

    if (!fine || reduce) return;
    const light = document.createElement('div'); light.className = 'cursor-light'; light.setAttribute('aria-hidden', 'true');
    document.body.appendChild(light);
    addEventListener('pointermove', (e) => { pointer.tx = e.clientX; pointer.ty = e.clientY; pointer.active = true; }, { passive: true });
    document.addEventListener('pointerleave', () => { pointer.active = false; });
    const follow = () => {
      if (pointer.x < -9000) { pointer.x = pointer.tx; pointer.y = pointer.ty; }
      pointer.x += (pointer.tx - pointer.x) * 0.14; pointer.y += (pointer.ty - pointer.y) * 0.14;
      light.style.transform = `translate3d(${pointer.x - 300}px, ${pointer.y - 300}px, 0)`;
      light.style.opacity = pointer.active ? '1' : '0';
      requestAnimationFrame(follow);
    };
    requestAnimationFrame(follow);
  }

  // ---------------- headings: word-by-word reveal ----------------
  function splitWords(el) {
    if (!el) return;
    const walk = (node) => {
      Array.from(node.childNodes).forEach((n) => {
        if (n.nodeType === 3 && n.textContent.trim()) {
          const frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach((part) => {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
            const w = document.createElement('span'); w.className = 'w';
            const inner = document.createElement('span'); inner.textContent = part; w.appendChild(inner);
            frag.appendChild(w);
          });
          n.replaceWith(frag);
        } else if (n.nodeType === 1 && !n.classList.contains('w')) walk(n);
      });
    };
    walk(el);
    el.querySelectorAll('.w > span').forEach((s, i) => { s.style.transitionDelay = (60 + i * 55) + 'ms'; });
    el.classList.add('wsplit');
  }
  function splitAll() {
    document.querySelectorAll('.section-head h1, .section-head h2, .page-hero h1').forEach(splitWords);
  }

  // ---------------- text decode effect (used for the verdict title) ----------------
  const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&*+=?';
  function decode(el, text, ms) {
    if (!el) return;
    if (reduce || /[^\x00-\x7F]/.test(text)) { el.textContent = text; return; }    // Hindi etc: no scramble
    ms = ms || 700;
    const t0 = performance.now();
    cancelAnimationFrame(el._dec);
    const step = (now) => {
      const p = Math.min(1, (now - t0) / ms), n = Math.floor(text.length * p);
      let out = text.slice(0, n);
      for (let i = n; i < text.length; i++) out += text[i] === ' ' ? ' ' : GLYPHS[(Math.random() * GLYPHS.length) | 0];
      el.textContent = out;
      if (p < 1) el._dec = requestAnimationFrame(step); else el.textContent = text;
    };
    el._dec = requestAnimationFrame(step);
  }

  // ---------------- magnetic buttons + hero parallax ----------------
  function initMagnetic() {
    if (!fine || reduce) return;
    const sel = '.btn-primary, .btn-danger, .chat-fab, .icon-btn, .chip';
    document.addEventListener('pointermove', (e) => {
      const b = e.target.closest && e.target.closest(sel);
      document.querySelectorAll('[data-mag]').forEach((x) => { if (x !== b) { x.style.translate = ''; delete x.dataset.mag; } });
      if (!b) return;
      const r = b.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / r.width, dy = (e.clientY - (r.top + r.height / 2)) / r.height;
      b.dataset.mag = '1';
      b.style.translate = `${(dx * 8).toFixed(1)}px ${(dy * 6).toFixed(1)}px`;
    }, { passive: true });
  }
  function initParallax() {
    if (!fine || reduce) return;
    const layers = document.querySelectorAll('[data-depth]');
    if (!layers.length) return;
    addEventListener('pointermove', (e) => {
      const x = e.clientX / innerWidth - 0.5, y = e.clientY / innerHeight - 0.5;
      layers.forEach((l) => { const d = parseFloat(l.dataset.depth); l.style.translate = `${(-x * d).toFixed(1)}px ${(-y * d).toFixed(1)}px`; });
    }, { passive: true });
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.documentElement.classList.add('motion-ready');
    initWave(); initChrome(); splitAll(); initMagnetic(); initParallax();
    if (window.AquaUI && window.AquaUI.reveal) window.AquaUI.reveal();
  });
  document.addEventListener('aquasentry:lang', () => setTimeout(splitAll, 0));

  window.AquaMotion = { decode, splitWords };
})();
