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
  const LIMITS = { asWho: 0.010, asBis: 0.010, asDetect: 0.020, asHaz: 0.150, lod: 0.020, phMin: 6.5, phMax: 8.5, turb: 5, ec: 1500 };

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
  const V3_MODEL = /*__V3_MODEL__*/{"id":"v3","sizes":[5,16,12,4],"logAs":true,"mean":[-1.68909001,7.41104344,847.35161309,4.86824623,24.97882183],"std":[0.7652232,0.96131817,566.86157266,4.83761623,5.52333305],"W":[[[-0.391879,-1.673074,1.367837,-0.227389,0.005492],[-0.370435,0.333997,0.471096,-0.938196,0.020226],[0.117853,-1.36443,0.662452,-0.105412,0.017853],[-0.1351,0.105022,-0.306746,-0.140637,0.036015],[2.992769,0.012532,0.119634,-0.25648,-0.007771],[1.926714,-0.040864,-0.022146,-0.976478,0.022329],[-0.1511,1.864218,1.47712,-0.23232,0.014832],[2.118491,0.153227,-0.10066,0.219629,0.051031],[-0.298381,1.031445,-0.832517,-0.219848,0.005578],[0.201559,1.221021,0.280387,0.297793,0.003121],[1.482024,0.022889,0.034944,-0.951729,-0.014981],[-0.315174,-0.036855,-0.030504,2.880545,0.007158],[-0.039577,-0.418885,-0.876515,-0.189246,0.044793],[0.210627,0.301508,0.711433,0.432683,-0.045125],[2.309022,-0.023066,0.261066,0.298445,-0.022935],[-0.262326,0.147545,0.767721,0.455167,0.106628]],[[0.0,0.0,0.0,-0.0,0.0,-0.0,0.0,-0.0,-0.0,0.0,0.0,0.0,-0.0,0.0,0.0,-0.0],[-0.437251,1.603574,0.048801,0.524407,-2.355649,-0.352033,-0.41293,-0.0,0.243216,-0.445248,-0.000435,-0.353733,-0.054963,1.000945,1e-06,0.143167],[-0.421598,0.459455,-0.045675,0.551257,-1.481856,-1.681521,-0.09901,-0.0,0.209759,-0.90402,-0.0,-0.730844,-0.116129,0.251086,-0.0,0.324324],[-1.019157,-0.023473,-0.068074,0.928546,1.1378,0.260114,-0.577477,-0.663238,-0.074225,-0.555833,-0.311927,-0.989393,-0.816892,0.704057,-0.498942,0.395111],[1.301759,-0.504286,1.207868,0.058671,-1.751397,-1.067675,2.173775,0.241424,1.147319,0.433484,0.1242,-0.54847,0.768129,-1.115385,1.064204,-0.884961],[-0.423623,-0.454897,0.015915,-0.234095,-0.254853,1.216714,-0.15687,-1.940184,-0.073587,0.035485,-0.493374,1.621294,0.114197,0.774796,-2.453158,0.318531],[0.264545,-0.555868,0.151565,-0.490003,1.888452,0.786566,-0.163402,-0.327729,0.326764,0.779353,-0.426168,0.4656,0.600964,0.433397,-0.235667,0.496999],[0.021734,-0.657818,-0.126832,-1.339151,0.870253,0.743255,-0.099513,1.260286,-0.040763,0.275123,1.088988,0.383705,0.181761,-0.795257,2.824923,-0.316074],[0.302116,-0.486934,0.180523,0.029748,0.278411,0.547645,-0.002214,-1.766906,0.091624,0.352517,-1.070984,0.389542,-0.015406,0.423571,-2.463403,-0.288322],[0.155107,-0.244288,0.077355,0.466333,-0.598195,0.404088,0.173906,-1.037949,-0.431281,0.029037,-0.488946,0.149716,-0.033819,1.072596,-2.005836,0.101671],[-0.959125,-0.132473,1.511985,0.441687,0.096598,-0.411231,0.378786,2.039418,0.574083,0.750874,0.748558,0.019501,-1.678289,-1.05349,1.720007,-0.212912],[-0.577163,-0.381556,-0.251125,-0.718522,-2.392536,0.33532,-0.22951,-0.958752,0.042829,-0.382682,0.0,1.350213,-0.722761,-0.184988,-1.403123,0.834665]],[[0.0,1.291856,0.381872,0.1486,-4.956909,-1.636858,-0.909066,-3e-06,-0.028457,0.090254,0.190439,-0.002146],[-0.0,0.39138,0.396023,-0.508709,-1.511328,0.910253,-0.388868,-0.471973,0.582909,0.151539,-0.803319,-1.614797],[-0.0,-0.892831,-0.520757,0.43392,1.01894,0.856651,0.632277,-1.388697,0.83002,0.075597,0.509377,-0.011091],[-0.0,-1.68348,-0.409439,0.374203,1.464457,-0.487082,0.734275,1.112466,-0.450324,-1.308766,0.771918,0.245175]]],"B":[[-0.317766,1.874818,0.804623,1.349707,0.828685,1.027461,-0.255444,-1.701525,-0.533429,1.210372,-1.534914,0.060399,1.043719,1.692233,-1.996204,1.11478],[-0.31555,1.677568,1.049823,0.800722,-1.662575,1.153284,-0.759143,-1.901693,0.955778,1.849504,-0.256652,-0.621176],[-0.028107,0.747985,0.295847,-1.705639]],"info":{"testAccuracy":98.6,"missReduction":16.6}}/*__END_V3__*/;

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
    else if (asMgL >= LIMITS.asDetect) { raise('Unsafe'); reasons.push({ code: 'AS_BIS' }); }  // detected => above IS 10500 (10 µg/L)
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
