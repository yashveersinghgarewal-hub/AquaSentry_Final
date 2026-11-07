/**
 * AquaNet — in-browser neural network (V1 hand-built, V3 trained) with the same safety rules
 * as app/neural_classifier.py, plus an SVG diagram of the network.
 *
 * window.AquaNet.evaluate(asMgL, ph, ec, turb, temp, modelId) -> result object
 * window.AquaNet.draw(svgElement, result)
 */
(function () {
  'use strict';

  const CLASSES = ['Safe', 'Caution', 'Unsafe', 'Hazardous'];
  const MEAN = [0.08, 7.5, 600.0, 4.0, 25.0];
  const STD = [0.10, 0.7, 300.0, 3.0, 4.0];
  const BOUNDS = [[0, 2], [4.5, 10.5], [50, 5000], [0, 100], [5, 45]];
  const LIMITS = { asWho: 0.010, asBis: 0.050, asHaz: 0.150, lod: 0.020, phMin: 6.5, phMax: 8.5, turb: 5, ec: 1500 };

  // V1: weights constructed by hand from the WHO / BIS thresholds (see docs). 23 neurons, 112 weights.
  const V1_MODEL = {
    id: 'v1', sizes: [5, 8, 6, 4],
    W: [
      [[50, 0, 0, 0, 0], [-50, 0, 0, 0, 0], [50, 0, 0, 0, 0], [-50, 0, 0, 0, 0], [50, 0, 0, 0, 0], [-50, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]],
      [[0, 1, 0, 0, 0, 0, 0, 0], [1, 0, 0, -1, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, -1, 0, 0], [0, 0, 1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0, 0, 0]],
      [[20, 0, 0, 0, 0, 0], [0, -20, 20, 0, 0, 0], [0, 0, 0, -20, 20, 0], [0, 0, 0, 0, 0, 20]],
    ],
    B: [[35, -35, 15, -15, -35, 35, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0.0001, 0, 0]],
  };

  // V3: trained on all five readings (arsenic fed in as log10(As + 0.001)), incl. realistic sensor noise.
  // Installed by AquaSentry_Platform/scripts/install_aquanet_v3.py - do not edit by hand.
  const V3_MODEL = /*__V3_MODEL__*/{"id":"v3","sizes":[5,16,12,4],"logAs":true,"mean":[-1.67223203,7.41169643,845.94288666,4.87214352,24.99316669],"std":[0.76826581,0.96145418,564.60775212,4.88366365,5.51649562],"W":[[[-0.354774,-1.355844,1.075415,-0.117376,0.021824],[-0.674392,0.121677,0.273318,-0.0027,0.003782],[-0.144756,-1.417103,1.11504,0.073584,0.004995],[-1.577645,-0.040943,-0.103048,0.202485,0.027378],[3.816441,-0.007769,0.033433,-0.155014,0.028732],[1.153322,0.06172,-0.02249,0.289649,0.032755],[-0.319741,1.827203,1.467404,-0.022578,-0.032801],[3.196162,0.006617,0.007209,-0.013693,-0.002806],[-0.248712,-1.924495,-1.227702,-0.070139,-0.018177],[-0.0,-0.0,0.0,0.0,0.0],[2.524205,0.008333,0.001711,-0.002281,0.002545],[-1.852383,0.007313,-0.007768,3.034071,-0.017944],[-0.239764,1.955227,-1.21847,0.004236,0.029574],[-0.478379,-0.018467,-0.088062,-0.113378,-0.036605],[3.197466,0.058783,-0.051744,0.193294,-0.058901],[-0.222396,0.003122,1.634071,-0.067956,0.008335]],[[0.0,-0.0,0.0,-0.0,-0.0,0.0,0.0,-0.0,-0.0,0.0,0.0,-0.0,-0.0,0.0,0.0,-0.0],[-0.669953,0.800342,-0.516767,1.554308,-2.786208,-0.85787,-0.969347,-0.0,-1.072203,-0.0,-0.0,-2.124911,-0.986053,0.895849,-0.834922,-0.118218],[-0.0,-0.0,-0.0,-0.0,-0.0,-0.0,0.0,-0.0,-0.0,-0.0,-0.0,-0.0,-0.0,0.0,0.0,0.0],[-0.114158,-0.119591,-1.01597,-0.306676,-0.44805,0.377481,-0.350877,0.552819,-0.219161,0.0,-0.18519,-1.221525,-0.546544,0.34338,-0.540778,-0.028157],[0.600341,0.161927,1.198769,0.721641,-0.887755,-0.717528,1.38082,-0.13162,1.715286,-0.0,0.028987,-1.341431,1.759039,-0.74898,0.403524,1.063323],[-0.265463,-0.010098,-0.044293,-0.518758,-0.422372,0.47812,-0.365464,-0.32842,-0.321485,-0.0,-0.02228,0.36313,-0.293587,0.010087,-0.642805,2.857641],[-0.33861,-0.106597,0.317431,-0.611418,0.024342,1.249574,-0.003841,-0.37672,0.051798,-0.0,-0.076818,1.546032,0.009471,-0.060697,-1.055847,-1.282724],[-0.771269,0.312939,-0.321046,-0.14586,1.942589,0.894098,-0.87075,1.467706,-0.972112,-0.0,1.018032,0.878326,-1.066612,0.218036,1.22303,0.057646],[0.001223,0.225766,-0.35849,-0.195119,-0.942708,-0.271892,-0.178663,-0.220053,-0.623406,-0.0,0.0,0.003282,-0.737426,0.231824,-0.017461,0.064645],[-0.045868,0.484001,-0.025637,0.213824,-0.939889,0.880602,-0.061874,-1.173602,-0.115464,0.0,-4.659665,0.047652,-0.092834,1.696143,-1.023687,0.017849],[0.582684,-0.160943,0.592322,0.678631,2.509586,-0.288704,0.869103,2.056904,0.988858,0.0,0.352406,-0.864621,1.05086,-0.195738,1.203303,-0.686869],[0.594386,-0.732693,0.33846,-1.231458,-2.283512,0.715951,0.773318,-0.775535,0.802249,-0.0,-0.010366,1.739267,0.754965,-0.699536,-2.756496,0.426447]],[[-0.0,1.608765,0.0,-0.540257,-2.92303,-0.880753,-1.866654,-2.286078,0.656418,0.428978,-0.121187,-0.165755],[-0.0,0.380019,0.0,-0.108535,-0.643463,0.579474,0.226048,-1.537273,0.701668,0.582707,-0.747489,-1.154323],[0.0,-0.858159,0.0,0.464303,0.47306,0.656762,0.578194,-0.110096,0.166186,-0.073946,0.659156,0.218492],[0.0,-0.0,-0.0,0.241509,0.554861,0.631044,0.505495,0.525287,0.0,-3.749831,0.899807,0.104395]]],"B":[[-0.453063,1.164734,0.02417,0.789642,-1.052159,2.00343,-0.585878,-1.600275,-0.536639,-0.157122,-2.778029,-0.736486,-0.930027,2.21526,-1.240446,-1.888889],[-0.184479,1.591705,-0.171586,0.187143,-2.581808,1.493987,-0.795992,-0.947227,1.771126,3.768137,-0.900932,-1.389121],[-0.342215,1.624753,0.375662,-3.497779]],"info":{"testAccuracy":98.6,"missReduction":23.1}}/*__END_V3__*/;

  const MODELS = { v1: V1_MODEL };
  if (V3_MODEL) MODELS.v3 = V3_MODEL;

  function relu(x) { return x > 0 ? x : 0; }
  function softmax(z) {
    const m = Math.max.apply(null, z);
    const e = z.map((v) => Math.exp(v - m));
    const s = e.reduce((a, b) => a + b, 0);
    return e.map((v) => v / s);
  }
  function entropy(p) {
    let h = 0;
    p.forEach((q) => { if (q > 1e-12) h -= q * Math.log(q); });
    return Math.max(0, Math.min(1, h / Math.log(4)));
  }

  function forward(model, raw) {
    const mean = model.mean || MEAN, std = model.std || STD;
    const x = raw.map((v, i) => {
      let u = isFinite(v) ? v : 0;
      if (i === 0 && model.logAs) u = Math.log10(Math.max(u, 0) + 0.001);
      return (u - mean[i]) / std[i];
    });
    const layers = [x];
    let h = x;
    model.W.forEach((W, li) => {
      const B = model.B[li];
      const last = li === model.W.length - 1;
      h = W.map((row, j) => {
        let s = B[j];
        for (let k = 0; k < row.length; k++) s += row[k] * h[k];
        return last ? s : relu(s);
      });
      layers.push(h);
    });
    return { x, layers, logits: h, probs: softmax(h) };
  }

  const RANK = { Safe: 0, Caution: 1, Unsafe: 2, Hazardous: 3 };

  function evaluate(asMgL, ph, ec, turb, temp, modelId) {
    const model = MODELS[modelId] || V1_MODEL;
    const raw = [asMgL, ph, ec, turb, temp];
    const f = forward(model, raw);
    let best = 0;
    for (let i = 1; i < 4; i++) if (f.probs[i] > f.probs[best]) best = i;
    const vote = CLASSES[best];
    let final = vote;
    const reasons = [];       // {code, v} explaining the verdict
    let override = false;
    const raise = (cls) => { if (RANK[cls] > RANK[final]) { final = cls; override = true; } };

    const finite = raw.every((v) => typeof v === 'number' && isFinite(v));
    const oob = !finite || raw.some((v, i) => v < BOUNDS[i][0] || v > BOUNDS[i][1]);
    if (oob) { raise('Unsafe'); reasons.push({ code: 'OOB' }); }

    if (asMgL > LIMITS.asHaz) { raise('Hazardous'); reasons.push({ code: 'AS_HAZ' }); }
    else if (asMgL >= LIMITS.asBis) { raise('Unsafe'); reasons.push({ code: 'AS_BIS' }); }
    else if (asMgL > LIMITS.asWho) { raise('Caution'); reasons.push({ code: 'AS_WHO' }); }
    else { reasons.push({ code: 'AS_OK' }); }

    if (!oob) {
      if (ph < 6.0 || ph > 9.0) { raise('Unsafe'); reasons.push({ code: 'PH_SEVERE', v: ph.toFixed(2) }); }
      else if (ph < LIMITS.phMin || ph > LIMITS.phMax) { raise('Caution'); reasons.push({ code: 'PH_ADV', v: ph.toFixed(2) }); }
      if (turb > 10) { raise('Unsafe'); reasons.push({ code: 'TURB_HIGH', v: turb.toFixed(1) }); }
      else if (turb > LIMITS.turb) { raise('Caution'); reasons.push({ code: 'TURB_ADV', v: turb.toFixed(1) }); }
      if (ec > 2000) { raise('Unsafe'); reasons.push({ code: 'EC_HIGH', v: Math.round(ec) }); }
      else if (ec > LIMITS.ec) { raise('Caution'); reasons.push({ code: 'EC_ADV', v: Math.round(ec) }); }
    }

    const H = entropy(f.probs);
    if (H > 0.65 && !override && final === 'Safe') { final = 'Caution'; override = true; reasons.push({ code: 'UNCERTAIN' }); }
    if (asMgL < LIMITS.lod) reasons.push({ code: 'LOD' });

    return {
      model: model.id, sizes: model.sizes, layers: f.layers, logits: f.logits, probs: f.probs,
      vote, final, override, confidence: f.probs[best], entropy: H, reasons, belowLod: asMgL < LIMITS.lod,
    };
  }

  function countWeights(model) {
    let nz = 0, total = 0;
    model.W.forEach((W) => W.forEach((row) => row.forEach((w) => { total++; if (Math.abs(w) > 1e-9) nz++; })));
    return { nz, total, nodes: model.sizes.reduce((a, b) => a + b, 0) };
  }

  // ---------- Diagram ----------
  const NS = 'http://www.w3.org/2000/svg';
  function el(name, attrs, text) {
    const e = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach((k) => e.setAttribute(k, attrs[k]));
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(svg, res) {
    if (!svg || !res) return;
    const t = (window.I18N && window.I18N.t) || ((k) => k);
    const model = MODELS[res.model] || V1_MODEL;
    const sizes = model.sizes;
    const W = 720, H = 420, top = 64, bottom = 396;
    const xs = sizes.map((_, i) => 132 + i * ((600 - 132) / (sizes.length - 1)));
    const pos = sizes.map((n, li) => {
      const gap = Math.min(40, (bottom - top) / Math.max(1, n - 1));
      const span = gap * (n - 1);
      const y0 = (top + bottom) / 2 - span / 2;
      return Array.from({ length: n }, (_, i) => ({ x: xs[li], y: y0 + i * gap }));
    });
    const r = (li) => (sizes[li] > 10 ? 8 : 12);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

    const heads = ['nn.layer.in', 'nn.layer.h1', 'nn.layer.h2', 'nn.layer.out'];
    sizes.forEach((n, li) => {
      const key = li === 0 ? heads[0] : li === sizes.length - 1 ? heads[3] : (li === 1 ? heads[1] : heads[2]);
      svg.appendChild(el('text', { x: xs[li], y: 26, 'text-anchor': 'middle', class: 'nn-head' }, `${t(key)} (${n})`));
    });

    const edges = el('g', { class: 'nn-edges' });
    model.W.forEach((Wl, li) => {
      let maxAbs = 0;
      Wl.forEach((row) => row.forEach((w) => { maxAbs = Math.max(maxAbs, Math.abs(w)); }));
      const src = res.layers[li];
      let srcMax = 0;
      src.forEach((a) => { srcMax = Math.max(srcMax, Math.abs(a)); });
      Wl.forEach((row, j) => row.forEach((w, k) => {
        if (Math.abs(w) < 1e-9) return;
        const strength = Math.abs(w) / (maxAbs || 1);
        const flow = srcMax ? Math.min(1, Math.abs(src[k]) / srcMax) : 0;
        const a = pos[li][k], b = pos[li + 1][j];
        edges.appendChild(el('line', {
          x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: w > 0 ? 'e-pos' : 'e-neg',
          'stroke-width': (0.6 + 1.8 * strength).toFixed(2), 'stroke-opacity': (0.12 + 0.7 * strength * (0.35 + 0.65 * flow)).toFixed(2),
        }));
      }));
    });
    svg.appendChild(edges);

    const inLabels = ['nn.as', 'nn.ph', 'nn.ec', 'nn.turb', 'nn.temp'];
    sizes.forEach((n, li) => {
      const acts = res.layers[li];
      const last = li === sizes.length - 1;
      let m = 0;
      acts.forEach((a) => { m = Math.max(m, Math.abs(a)); });
      pos[li].forEach((p, i) => {
        const g = el('g', {});
        let fillOp;
        let cls = 'n-node';
        if (last) { fillOp = res.probs[i]; cls += ' n-out n-' + CLASSES[i]; }
        else if (li === 0) { fillOp = 0.15 + 0.5 * Math.min(1, Math.abs(acts[i]) / 2); }
        else { fillOp = m ? Math.min(1, acts[i] / m) : 0; }
        g.appendChild(el('circle', { cx: p.x, cy: p.y, r: last ? 14 : r(li), class: 'n-bg' }));
        const c = el('circle', { cx: p.x, cy: p.y, r: last ? 14 : r(li), class: cls, 'fill-opacity': fillOp.toFixed(2) });
        const title = el('title', {}, last ? `${t('class.' + CLASSES[i])}: ${(res.probs[i] * 100).toFixed(1)}%` : `${acts[i].toFixed(3)}`);
        c.appendChild(title);
        g.appendChild(c);
        if (li === 0) g.appendChild(el('text', { x: p.x - 22, y: p.y + 5, 'text-anchor': 'end', class: 'nn-label' }, t(inLabels[i])));
        if (last) g.appendChild(el('text', { x: p.x + 24, y: p.y + 5, 'text-anchor': 'start', class: 'nn-label' + (CLASSES[i] === res.vote ? ' nn-label-strong' : '') }, t('class.' + CLASSES[i])));
        svg.appendChild(g);
      });
    });
  }

  window.AquaNet = {
    CLASSES, LIMITS, MODELS,
    hasV3: !!V3_MODEL,
    v3Info: V3_MODEL ? V3_MODEL.info : null,
    evaluate, draw, countWeights: (id) => countWeights(MODELS[id] || V1_MODEL),
  };
})();
