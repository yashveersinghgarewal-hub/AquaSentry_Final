/**
 * AquaCharts — tiny dependency-free SVG charts for AquaSentry (works offline, follows the light/dark theme).
 *   AquaCharts.bar(el, { labels, series: [{ name, color, data }], stacked, yFmt, tipFmt, totals })
 *   AquaCharts.line(el, { labels, series: [...], area, yFmt })
 *   AquaCharts.donut(el, { items: [{ name, value, color }], center: {big, small}, tipFmt })
 * Colors may be CSS variables ('var(--primary)') or hex. Charts redraw on theme / language change if you pass a
 * function instead of an options object.
 */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  let uid = 0;
  function mk(name, attrs, parent, text) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function col(c) { if (!c || c.indexOf('var(') !== 0) return c; return getComputedStyle(document.documentElement).getPropertyValue(c.slice(4, -1).trim()).trim() || '#2DD4BF'; }
  function niceStep(v) { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const f = v / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p; }
  /** Axis scale with 3-5 round ticks: returns { max, n } */
  function scale(dataMax) { const step = niceStep(dataMax * 1.08 / 4); const n = Math.max(2, Math.ceil(dataMax * 1.08 / step)); return { max: step * n, n }; }

  let tip;
  function showTip(e, html) {
    if (!tip) { tip = document.createElement('div'); tip.className = 'chart-tip'; document.body.appendChild(tip); }
    tip.innerHTML = html; tip.style.opacity = '1';
    const x = Math.min(window.innerWidth - tip.offsetWidth - 10, e.clientX + 14), y = Math.max(10, e.clientY - tip.offsetHeight - 12);
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hideTip() { if (tip) tip.style.opacity = '0'; }

  function frame(el, h) {
    el.innerHTML = '';
    const W = Math.max(320, el.clientWidth || 600), H = h || 280;
    const svg = mk('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart-svg', role: 'img' }, el);
    return { svg, W, H, defs: mk('defs', {}, svg) };
  }
  function legend(el, series) {
    const d = document.createElement('div'); d.className = 'chart-legend';
    d.innerHTML = series.map((s) => `<span><i style="background:${col(s.color)}"></i>${s.name}</span>`).join('');
    el.appendChild(d);
  }
  function gradient(defs, color, vertical, a1, a2) {
    const id = 'cg' + (++uid);
    const g = mk('linearGradient', vertical ? { id, x1: 0, y1: 0, x2: 0, y2: 1 } : { id, x1: 0, y1: 0, x2: 1, y2: 0 }, defs);
    mk('stop', { offset: '0%', 'stop-color': color, 'stop-opacity': a1 }, g);
    mk('stop', { offset: '100%', 'stop-color': color, 'stop-opacity': a2 }, g);
    return `url(#${id})`;
  }
  function yAxis(svg, L, R, T, B, max, fmt, n) {
    n = n || 4;
    for (let i = 0; i <= n; i++) {
      const v = max * i / n, y = B - (B - T) * i / n;
      mk('line', { x1: L, x2: R, y1: y, y2: y, class: 'c-grid', 'stroke-dasharray': i ? '3 5' : '' }, svg);
      mk('text', { x: L - 10, y: y + 4, 'text-anchor': 'end', class: 'c-tick' }, svg, fmt(v));
    }
  }

  function bar(el, o) {
    const { svg, W, H, defs } = frame(el, o.height);
    const fmt = o.yFmt || ((v) => v);
    const L = o.left || 64, R = W - 12, T = 22, B = H - 34;
    const totals = o.labels.map((_, i) => o.stacked ? o.series.reduce((a, s) => a + s.data[i], 0) : Math.max(...o.series.map((s) => s.data[i])));
    const sc = scale(Math.max(...totals)), max = sc.max;
    yAxis(svg, L, R, T, B, max, fmt, sc.n);
    const n = o.labels.length, slot = (R - L) / n, groupW = Math.min(slot * 0.62, 90);
    o.labels.forEach((lab, i) => {
      const cx = L + slot * (i + 0.5);
      mk('text', { x: cx, y: B + 22, 'text-anchor': 'middle', class: 'c-xl' }, svg, lab);
      let acc = 0;
      o.series.forEach((s, si) => {
        const v = s.data[i], c = col(s.color);
        const bw = o.stacked ? groupW : groupW / o.series.length;
        const x = o.stacked ? cx - groupW / 2 : cx - groupW / 2 + si * bw;
        const y0 = o.stacked ? acc : 0;
        const y = B - (y0 + v) / max * (B - T), h = v / max * (B - T);
        const top = !o.stacked || si === o.series.length - 1;
        const r = mk('rect', { x: x + 1, y, width: Math.max(1, bw - 2), height: Math.max(0, h), rx: top ? 6 : 1.5, fill: gradient(defs, c, true, 1, 0.55), class: 'c-bar', style: `animation-delay:${(i * 90 + si * 60)}ms` }, svg);
        r.addEventListener('pointermove', (e) => showTip(e, `${lab} · ${s.name}<br><b>${(o.tipFmt || fmt)(v)}</b>`));
        r.addEventListener('pointerleave', hideTip);
        if (o.stacked) acc += v;
      });
      if (o.totals) mk('text', { x: cx, y: B - totals[i] / max * (B - T) - 8, 'text-anchor': 'middle', class: 'c-total' }, svg, fmt(totals[i]));
    });
    legend(el, o.series);
  }

  function line(el, o) {
    const { svg, W, H, defs } = frame(el, o.height);
    const fmt = o.yFmt || ((v) => v);
    const L = o.left || 64, R = W - 16, T = 22, B = H - 34;
    const sc = scale(Math.max(...o.series.flatMap((s) => s.data))), max = sc.max;
    yAxis(svg, L, R, T, B, max, fmt, sc.n);
    const n = o.labels.length, X = (i) => L + (R - L) * (n === 1 ? 0.5 : i / (n - 1)), Y = (v) => B - v / max * (B - T);
    o.labels.forEach((lab, i) => mk('text', { x: X(i), y: B + 22, 'text-anchor': i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle', class: 'c-xl' }, svg, lab));
    o.series.forEach((s, si) => {
      const c = col(s.color);
      const pts = s.data.map((v, i) => [X(i), Y(v)]);
      // smooth path (Catmull-Rom -> Bezier)
      let d = `M${pts[0][0]},${pts[0][1]}`;
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
        d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
      }
      if (o.area !== false) mk('path', { d: `${d} L${pts[pts.length - 1][0]},${B} L${pts[0][0]},${B} Z`, fill: gradient(defs, c, true, 0.35, 0), class: 'c-area' }, svg);
      const p = mk('path', { d, stroke: c, class: 'c-line', style: `animation-delay:${si * 200}ms;filter:drop-shadow(0 0 6px ${c}66)` }, svg);
      try { p.style.setProperty('--len', Math.ceil(p.getTotalLength())); } catch (e) { /* ignore */ }
      pts.forEach(([x, y], i) => {
        const dot = mk('circle', { cx: x, cy: y, r: 4.5, fill: c, class: 'c-dot' }, svg);
        dot.addEventListener('pointermove', (e) => showTip(e, `${o.labels[i]} · ${s.name}<br><b>${(o.tipFmt || fmt)(s.data[i])}</b>`));
        dot.addEventListener('pointerleave', hideTip);
      });
    });
    legend(el, o.series);
  }

  function donut(el, o) {
    el.innerHTML = '';
    const S = 260, cx = S / 2, cy = S / 2, R = 108, w = 26;
    const svg = mk('svg', { viewBox: `0 0 ${S} ${S}`, class: 'chart-svg', role: 'img', style: 'max-width:300px;margin:0 auto' }, el);
    const total = o.items.reduce((a, b) => a + b.value, 0);
    mk('circle', { cx, cy, r: R, fill: 'none', stroke: col('var(--surface-3)'), 'stroke-width': w }, svg);
    let a0 = -Math.PI / 2;
    const C = 2 * Math.PI * R;
    o.items.forEach((it, i) => {
      const frac = it.value / total, len = C * frac;
      const c = mk('circle', {
        cx, cy, r: R, fill: 'none', stroke: col(it.color), 'stroke-width': w, 'stroke-dasharray': `${len - 3} ${C}`,
        'stroke-dashoffset': -(a0 + Math.PI / 2) / (2 * Math.PI) * C, transform: `rotate(-90 ${cx} ${cy})`, 'stroke-linecap': 'round',
        style: `filter:drop-shadow(0 0 8px ${col(it.color)}55);transition:stroke-width .3s`,
      }, svg);
      c.addEventListener('pointermove', (e) => { c.setAttribute('stroke-width', w + 6); showTip(e, `${it.name}<br><b>${(o.tipFmt || ((v) => v))(it.value)}</b> · ${(frac * 100).toFixed(0)}%`); });
      c.addEventListener('pointerleave', () => { c.setAttribute('stroke-width', w); hideTip(); });
      a0 += frac * 2 * Math.PI;
    });
    if (o.center) {
      mk('text', { x: cx, y: cy + 4, 'text-anchor': 'middle', style: `font-family:var(--font-display);font-weight:700;font-size:34px;fill:${col('var(--ink)')}` }, svg, o.center.big);
      mk('text', { x: cx, y: cy + 28, 'text-anchor': 'middle', style: `font-size:13px;fill:${col('var(--ink-3)')}` }, svg, o.center.small);
    }
    legend(el, o.items.map((i) => ({ name: i.name, color: i.color })));
  }

  function spark(el, data, color) {
    el.innerHTML = '';
    const W = 240, H = 70, max = Math.max(...data) * 1.1;
    const svg = mk('svg', { viewBox: `0 0 ${W} ${H}`, class: 'chart-svg', preserveAspectRatio: 'none', style: 'width:100%;height:70px' }, el);
    const defs = mk('defs', {}, svg);
    const pts = data.map((v, i) => [i / (data.length - 1) * W, H - 4 - v / max * (H - 10)]);
    const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
    const c = col(color || 'var(--primary)');
    mk('path', { d: `${d} L${W},${H} L0,${H} Z`, fill: gradient(defs, c, true, 0.35, 0), class: 'c-area' }, svg);
    const p = mk('path', { d, stroke: c, class: 'c-line', 'vector-effect': 'non-scaling-stroke' }, svg);
    try { p.style.setProperty('--len', Math.ceil(p.getTotalLength())); } catch (e) { /* ignore */ }
  }

  // Charts drawn with a builder function are redrawn on theme/language/resize changes.
  const registry = [];
  function draw(kind, el, builder) {
    if (!el) return;
    const run = () => { const o = typeof builder === 'function' ? builder() : builder; ({ bar, line, donut })[kind](el, o); };
    registry.push(run);
    if ('IntersectionObserver' in window) {
      const obs = new IntersectionObserver((en) => { if (en[0].isIntersecting) { run(); obs.disconnect(); } }, { threshold: 0.2 });
      obs.observe(el);
    } else run();
  }
  let rt;
  const redraw = () => { clearTimeout(rt); rt = setTimeout(() => registry.forEach((f) => f()), 120); };
  document.addEventListener('aquasentry:theme', redraw);
  document.addEventListener('aquasentry:lang', redraw);
  window.addEventListener('resize', redraw);

  window.AquaCharts = { bar, line, donut, spark, draw: draw };
})();
