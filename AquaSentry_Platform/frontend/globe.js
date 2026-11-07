/**
 * Rotating dotted globe (canvas 2D) with glowing hotspots and arcs — used on the Market research page.
 * Land mask: 2° grid (lat -55..77, lon -179..179), from the public-domain global-land-mask dataset, packed as bits.
 *   AquaGlobe.mount(canvas, { hotspots: [{ lat, lon, label, primary }], origin: index })
 */
(function () {
  'use strict';
  const MASK = 'AAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAABwAAAAAAAAAAAAAAAAAAAAAAAAAAAADgAAAAAAAAAAAAAAAAAAAAAAAAAAAABwAAAAAAAAAACAAAAAAAAAAAAAAAAAB4AAAAAAAAAAAAAAAAAAAAAAAAAAAAB4AAAAAAAAAAAAAAAAAAAwAAAAAAAAA8AAAAAAAAAAAAAAAAAQAYAAAAAAAAB6AAAAAAAAAAAAAAAAAwAMAAAAAAAAB+AAAAAAAAAAAAAAAAAAAGAAAAAAAAB/wAAAAAAAAAAAAAAAD4AEAAAAAAAAA/gAAAAAAAAAAAAACAP4AAAAAAAAAAA/8AAAAAHwAAAAAADwf8AAAAAAAAAAA/8AAAAAH4AAAAAAD//+AAAAAAAAAAA/+AAAAAP8AAAAAAH//+AAAAAAAAAAAf/AAAAAP8AAAAAAH//+AAAAAAAAAAAf/AAAAAf+DAAAAAH//8AAAAAAAAAAAf/wAAAAf/DAAAAAH//4AAAAAAAAAAAf/8AAAAf/DAAAAAD//4CAAAAAAAAAAf/8AAAA//DgAAAAAf/gAAAAAAAAAAA//8AAAA//zgAAAAAf/gAAAAAAAAAAD//8AAAA//wgAAAAAHxgBAAAAAAAAAD//+AAAA//wgAAAAABxAAAAAAAAAAAH//+AAAAf/wAAAAAAAAAAAAAAAAAAAH///AAAAf/wAAAAACIDQIAAAAAAAAAP///gAAA//wAAAAB4AHggAAAAAAAAAf///AAAA//wAAAACAAHgAAAAAAAAAAP//8AAAB//wAAAAGdCuAAAAAAAAAAAP//gAAAD//4AAAAMeBgAAAAAAAAAAAP/+AAAAB//8AAAAc+gAAAAAAAAAAAAH/+AAAAB//+AAAAUOAAAAAAAAAAAAAH/8AAAYH///AAAAsGAAAAAAAAAAAAAH/gAAA/////gACAAAIAAAAAAAAAAAAr/AAAB/////gAIASAAAAAAAAAAAAABBwAAAD////8wAMATAIAAAAAAAAAAADAAAAAD////6AAcAfgwAAAAAAAAAAAPAAAAAH////3gAcAfAgAAAAAAAAAAD8AAAAAD////34AeBfAgAAAAAAAAAAPMAwAAAD////n+AfB+gAAAAAAAAAAAeGEAAAAD////v+B/j/AAAAAAAAAAAAeAwAAAAD////f/D///8gAAAAAAAAAC+AAAAAAB///+fwH///+AAAAAAAAAAF+AQAAAAB///+/n/////AAAAAAAAAAD/AQAAAAAf//9/f/////gAAAAAAAAAP//gAAAAAf/73///////gAAAAAAAAAf//wAAAAAP/AA///////BgAAAAAAAA///8AAAAAH+Ai///////E8AAAAAAAB///8AAAAAGDRf///////mMAAAAAAAD///8AAAAAfCJf//////+ECAAAAAAAD///+AAAAAPCb3///////+AAAAAAAAD////gAAAAfxnwP///////jgAAAAAAD////+AAAAB/f5f///////wAAAAAAAD////8EAAAB///v///////5AAAAAAAF////0YAAAB///////////8AAAAAAAP/////gAAADf//////////9AAAAAAAf///3/wAAAbH//////////9AgAAAAB////n/gAAAOCR/////////4A4AABAC///4D+AAAAGCx/////////4A4AAHgD///gH0AAAAAG4/////////+AMAAf1////gHgA4AAAP5///////////LwAP/////4A0B4AAAD5/////////////Mf/////9H4D4A+AA+ev///////////8H//////g8H/gAAAf/6//f////////AP/7/nbdrwD/+AAAH/Ag7H////////gBgAAfw3/gB/+gAAAgAMHe///+/9gBAAAADsj38AH/+gAAAAAEAH///OAAAAAAAAALivwAf//wAAAAADAAP/wAHIAAAAAAAwADw////4AAIAAAAAAHAAAAAAA=';
  const ROWS = 67, COLS = 180, LAT0 = -55, LON0 = -179, STEP = 2;
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function landPoints() {
    const bin = atob(MASK), pts = [];
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      const i = r * COLS + c;
      if ((bin.charCodeAt(i >> 3) >> (7 - (i & 7))) & 1) {
        const lat = (LAT0 + r * STEP) * Math.PI / 180, lon = (LON0 + c * STEP) * Math.PI / 180;
        pts.push([Math.cos(lat) * Math.sin(lon), Math.sin(lat), Math.cos(lat) * Math.cos(lon)]);
      }
    }
    return pts;
  }
  function v3(lat, lon) { lat *= Math.PI / 180; lon *= Math.PI / 180; return [Math.cos(lat) * Math.sin(lon), Math.sin(lat), Math.cos(lat) * Math.cos(lon)]; }
  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

  function mount(canvas, opts) {
    const ctx = canvas.getContext('2d');
    const land = landPoints();
    const spots = (opts.hotspots || []).map((h) => Object.assign({ v: v3(h.lat, h.lon) }, h));
    const origin = spots[opts.origin || 0];
    let rot = 1.2, tilt = 0.38, visible = true, running = false, drag = null;
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = canvas.clientWidth * dpr; canvas.height = canvas.clientHeight * dpr;
    }
    function project(p, R, cx, cy) {
      const cr = Math.cos(rot), sr = Math.sin(rot), ct = Math.cos(tilt), stt = Math.sin(tilt);
      const x = p[0] * cr - p[2] * sr, z0 = p[0] * sr + p[2] * cr;
      const y = p[1] * ct - z0 * stt, z = p[1] * stt + z0 * ct;
      return [cx + x * R, cy - y * R, z];
    }
    function slerp(a, b, t) {
      const d = Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])));
      if (d < 1e-6) return a; const s = Math.sin(d), wa = Math.sin((1 - t) * d) / s, wb = Math.sin(t * d) / s;
      return [a[0] * wa + b[0] * wb, a[1] * wa + b[1] * wb, a[2] * wa + b[2] * wb];
    }
    function draw(time) {
      const W = canvas.width, H = canvas.height, R = Math.min(W, H) * 0.42, cx = W / 2, cy = H / 2;
      const prim = cssVar('--primary') || '#2DD4BF', vio = cssVar('--violet') || '#818CF8', ink3 = cssVar('--ink-3') || '#6E7A83';
      ctx.clearRect(0, 0, W, H);
      // atmosphere
      const g = ctx.createRadialGradient(cx, cy, R * 0.85, cx, cy, R * 1.25);
      g.addColorStop(0, prim + '33'); g.addColorStop(1, prim + '00');
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.25, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = prim + '40'; ctx.lineWidth = 1 * (W / canvas.clientWidth); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();
      // land dots
      const dot = Math.max(1.2, R / 150);
      for (const p of land) {
        const q = project(p, R, cx, cy);
        if (q[2] < -0.05) continue;
        ctx.globalAlpha = 0.18 + 0.7 * Math.max(0, q[2]);
        ctx.fillStyle = ink3;
        ctx.fillRect(q[0] - dot / 2, q[1] - dot / 2, dot, dot);
      }
      ctx.globalAlpha = 1;
      // arcs from origin
      const tt = (time / 1000) % 3 / 3;
      spots.forEach((s) => {
        if (s === origin || !origin) return;
        if (origin.v[0] * s.v[0] + origin.v[1] * s.v[1] + origin.v[2] * s.v[2] < -0.2) return;   // skip arcs to the far side of the planet
        ctx.beginPath(); let first = true;
        for (let i = 0; i <= 40; i++) {
          const v = slerp(origin.v, s.v, i / 40), lift = 1 + 0.18 * Math.sin(Math.PI * i / 40);
          const q = project([v[0] * lift, v[1] * lift, v[2] * lift], R, cx, cy);
          if (q[2] < -0.1) { first = true; continue; }
          if (first) { ctx.moveTo(q[0], q[1]); first = false; } else ctx.lineTo(q[0], q[1]);
        }
        const lg = ctx.createLinearGradient(0, 0, W, H); lg.addColorStop(0, prim); lg.addColorStop(1, vio);
        ctx.strokeStyle = lg; ctx.globalAlpha = 0.75; ctx.lineWidth = 1.6 * (W / canvas.clientWidth); ctx.stroke(); ctx.globalAlpha = 1;
        // travelling pulse
        const v = slerp(origin.v, s.v, tt), lift = 1 + 0.18 * Math.sin(Math.PI * tt), q = project([v[0] * lift, v[1] * lift, v[2] * lift], R, cx, cy);
        if (q[2] > 0) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(q[0], q[1], 2.2 * (W / canvas.clientWidth), 0, Math.PI * 2); ctx.fill(); }
      });
      // hotspots
      spots.forEach((s, i) => {
        const q = project(s.v, R, cx, cy);
        if (q[2] < 0) return;
        const k = W / canvas.clientWidth, pulse = ((time / 1400 + i * 0.3) % 1);
        const c = s.primary ? prim : vio;
        ctx.strokeStyle = c; ctx.globalAlpha = (1 - pulse) * 0.8; ctx.lineWidth = 2 * k;
        ctx.beginPath(); ctx.arc(q[0], q[1], (6 + pulse * 18) * k, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1;
        ctx.fillStyle = c; ctx.shadowColor = c; ctx.shadowBlur = 14 * k; ctx.beginPath(); ctx.arc(q[0], q[1], 4.5 * k, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
        if (s.label) {
          ctx.font = `600 ${12 * k}px Mukta, system-ui, sans-serif`; ctx.fillStyle = cssVar('--ink') || '#fff';
          ctx.globalAlpha = Math.min(1, q[2] * 2.5); const dx = s.dx == null ? 10 : s.dx, dy = s.dy == null ? -8 : s.dy;
          ctx.textAlign = dx < 0 ? 'right' : 'left'; ctx.fillText(s.label, q[0] + dx * k, q[1] + dy * k); ctx.textAlign = 'left'; ctx.globalAlpha = 1;
        }
      });
    }
    function loop() {
      if (running) return; running = true;
      const tick = (time) => {
        if (!visible || document.hidden) { running = false; return; }
        if (!drag && !reduce) rot += 0.0009;
        draw(time); requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
    canvas.addEventListener('pointerdown', (e) => { drag = e.clientX; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', (e) => { if (drag === null) return; rot += (e.clientX - drag) * 0.006; drag = e.clientX; if (reduce) draw(0); });
    canvas.addEventListener('pointerup', () => { drag = null; });
    window.addEventListener('resize', () => { resize(); draw(performance.now()); });
    new IntersectionObserver((en) => { visible = en[0].isIntersecting; if (visible) loop(); }).observe(canvas);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) loop(); });
    document.addEventListener('aquasentry:theme', () => draw(performance.now()));
    resize(); draw(0); loop();
    return { setLabels(labels) { labels.forEach((l, i) => { if (spots[i]) spots[i].label = l; }); draw(performance.now()); } };
  }
  window.AquaGlobe = { mount };
})();
