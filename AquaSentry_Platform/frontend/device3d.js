/**
 * Interactive 3D view of the real AquaSentry enclosure (from models_3d/*.stl, embedded by device3d-data.js).
 * Plain WebGL, no libraries. Drag to rotate, scroll / pinch to zoom, "Explode" button separates the parts.
 *   AquaDevice3D.mount(containerElement, { labels: {lid, base, well, strainer} })
 */
(function () {
  'use strict';
  const reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- tiny mat4 helpers (column-major) ----
  const M = {
    persp(f, a, n, fa) { const t = 1 / Math.tan(f / 2), nf = 1 / (n - fa); return [t / a, 0, 0, 0, 0, t, 0, 0, 0, 0, (fa + n) * nf, -1, 0, 0, 2 * fa * n * nf, 0]; },
    mul(a, b) { const o = new Array(16); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k]; o[i * 4 + j] = s; } return o; },
    lookAt(e, c, u) {
      let zx = e[0] - c[0], zy = e[1] - c[1], zz = e[2] - c[2]; let l = Math.hypot(zx, zy, zz); zx /= l; zy /= l; zz /= l;
      let xx = u[1] * zz - u[2] * zy, xy = u[2] * zx - u[0] * zz, xz = u[0] * zy - u[1] * zx; l = Math.hypot(xx, xy, xz); xx /= l; xy /= l; xz /= l;
      const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
      return [xx, yx, zx, 0, xy, yy, zy, 0, xz, yz, zz, 0, -(xx * e[0] + xy * e[1] + xz * e[2]), -(yx * e[0] + yy * e[1] + yz * e[2]), -(zx * e[0] + zy * e[1] + zz * e[2]), 1];
    },
    trans(x, y, z) { return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]; },
  };

  const VS = `attribute vec3 p; attribute vec3 n; uniform mat4 mvp; uniform mat4 model; varying vec3 vn; varying vec3 vp;
void main(){ vec4 w = model * vec4(p, 1.0); vp = w.xyz; vn = n; gl_Position = mvp * w; gl_PointSize = 2.0; }`;
  const FS = `precision mediump float; varying vec3 vn; varying vec3 vp; uniform vec3 eye; uniform vec3 base; uniform vec3 rim; uniform float alpha;
void main(){
  vec3 N = normalize(vn); vec3 V = normalize(eye - vp);
  if (dot(N, V) < 0.0) N = -N;
  vec3 L = normalize(vec3(0.5, 0.9, 0.35));
  float diff = max(dot(N, L), 0.0);
  float hemi = 0.5 + 0.5 * N.y;
  vec3 H = normalize(L + V); float spec = pow(max(dot(N, H), 0.0), 48.0);
  float fres = pow(1.0 - max(dot(N, V), 0.0), 2.5);
  vec3 col = base * (0.28 + 0.32 * hemi + 0.55 * diff) + vec3(1.0) * spec * 0.35 + rim * fres * 0.9;
  gl_FragColor = vec4(col, alpha + fres * (1.0 - alpha) * 0.6);
}`;
  // animated "water surface" of dots under the model: ripples spread out from the centre
  const PVS = `attribute vec3 p; uniform mat4 mvp; uniform float t; varying float h; varying float f;
void main(){ float r = length(p.xz); float w = sin(r * 0.075 - t * 2.2) * 3.2 * exp(-r * 0.006) + sin(p.x * 0.05 + t * 1.3) * 1.2;
  h = w; f = 1.0 - smoothstep(60.0, 175.0, r); gl_Position = mvp * vec4(p.x, p.y + w, p.z, 1.0); gl_PointSize = 1.4 + max(w, 0.0) * 0.45; }`;
  const PFS = `precision mediump float; uniform vec3 rim; varying float h; varying float f;
void main(){ vec2 c = gl_PointCoord - 0.5; if (dot(c, c) > 0.25) discard; gl_FragColor = vec4(rim * (0.75 + h * 0.08) + vec3(0.15, 0.25, 0.45) * max(h, 0.0) * 0.12, (0.18 + max(h, 0.0) * 0.09) * f); }`;

  // Where each part sits (mm, STL z-up). explode: extra offset when the view is "exploded".
  const LAYOUT = {
    base: { pos: [0, 0, 0], explode: [0, 0, 0], color: [0.09, 0.15, 0.30], alpha: 0.42 },
    lid: { pos: [0, 0, 86], explode: [0, 0, 70], color: [0.13, 0.21, 0.40], alpha: 0.9 },
    well: { pos: [0, 0, 12], explode: [0, 0, 42], color: [0.23, 0.51, 0.96], alpha: 1.0 },
    strainer: { pos: [0, -40, -44], explode: [0, -30, -40], color: [0.51, 0.55, 0.97], alpha: 1.0 },
  };

  function decode(b64) {
    const bin = atob(b64), buf = new ArrayBuffer(bin.length), u8 = new Uint8Array(buf);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return new Int16Array(buf);
  }
  function compile(gl, vs, fs) {
    const s = (t, src) => { const o = gl.createShader(t); gl.shaderSource(o, src); gl.compileShader(o); return o; };
    const p = gl.createProgram(); gl.attachShader(p, s(gl.VERTEX_SHADER, vs)); gl.attachShader(p, s(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
    return gl.getProgramParameter(p, gl.LINK_STATUS) ? p : null;
  }

  function mount(box, opts) {
    opts = opts || {};
    const data = window.AQUASENTRY_MODEL;
    const canvas = document.createElement('canvas');
    box.prepend(canvas);
    const gl = data && canvas.getContext('webgl', { antialias: true, alpha: true, premultipliedAlpha: false });
    const prog = gl && compile(gl, VS, FS);
    const pprog = gl && compile(gl, PVS, PFS);
    if (!prog || !pprog) { canvas.remove(); const f = document.createElement('div'); f.className = 'viewer-fallback'; f.textContent = opts.fallback || '3D view needs WebGL.'; box.appendChild(f); return null; }

    // build buffers (STL z-up -> GL y-up: (x, z, -y)), flat normals per triangle
    const parts = data.parts.map((pt) => {
      const q = decode(pt.data), n = q.length / 3, pos = new Float32Array(q.length), nor = new Float32Array(q.length);
      for (let i = 0; i < n; i++) { pos[i * 3] = q[i * 3] * data.scale; pos[i * 3 + 1] = q[i * 3 + 2] * data.scale; pos[i * 3 + 2] = -q[i * 3 + 1] * data.scale; }
      for (let t = 0; t < n / 3; t++) {
        const a = t * 9;
        const ux = pos[a + 3] - pos[a], uy = pos[a + 4] - pos[a + 1], uz = pos[a + 5] - pos[a + 2];
        const vx = pos[a + 6] - pos[a], vy = pos[a + 7] - pos[a + 1], vz = pos[a + 8] - pos[a + 2];
        let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx; const l = Math.hypot(nx, ny, nz) || 1; nx /= l; ny /= l; nz /= l;
        for (let k = 0; k < 3; k++) { nor[a + k * 3] = nx; nor[a + k * 3 + 1] = ny; nor[a + k * 3 + 2] = nz; }
      }
      const pb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, pb); gl.bufferData(gl.ARRAY_BUFFER, pos, gl.STATIC_DRAW);
      const nb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, nb); gl.bufferData(gl.ARRAY_BUFFER, nor, gl.STATIC_DRAW);
      return { name: pt.name, count: n, pb, nb, L: LAYOUT[pt.name] || LAYOUT.base };
    });
    // dotted floor
    const fl = [];
    for (let x = -180; x <= 180; x += 7) for (let z = -180; z <= 180; z += 7) if (x * x + z * z < 180 * 180) fl.push(x, -50, z);
    const fb = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, fb); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(fl), gl.STATIC_DRAW);
    const floorN = fl.length / 3;

    const U = {}; ['mvp', 'model', 'eye', 'base', 'rim', 'alpha'].forEach((k) => { U[k] = gl.getUniformLocation(prog, k); });
    const PU = { mvp: gl.getUniformLocation(pprog, 'mvp'), rim: gl.getUniformLocation(pprog, 'rim'), t: gl.getUniformLocation(pprog, 't') };
    const t0 = performance.now();
    const aP = gl.getAttribLocation(prog, 'p'), aN = gl.getAttribLocation(prog, 'n'), aPP = gl.getAttribLocation(pprog, 'p');

    // label overlay
    const labelBox = document.createElement('div'); labelBox.className = 'viewer-labels'; box.appendChild(labelBox);
    const labels = {};
    Object.keys(opts.labels || {}).forEach((k) => { const d = document.createElement('div'); d.className = 'viewer-label'; d.textContent = opts.labels[k]; labelBox.appendChild(d); labels[k] = d; });

    const st = { yaw: 0.7, pitch: 0.38, dist: 330, explode: 0, target: 0, drag: null, idle: 0, visible: true, running: false };
    let rimColor = [0.31, 0.55, 1.0];

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(box.clientWidth * dpr), h = Math.round(box.clientHeight * dpr);
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    }
    function ease(x) { return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }

    function render() {
      resize();
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.enable(gl.DEPTH_TEST); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      const e = ease(st.explode);
      const cy = 38 + e * 22, dist = st.dist * (1 + 0.42 * e);
      const eye = [Math.cos(st.pitch) * Math.sin(st.yaw) * dist, cy + Math.sin(st.pitch) * dist, Math.cos(st.pitch) * Math.cos(st.yaw) * dist];
      const proj = M.persp(0.62, canvas.width / canvas.height, 10, 2000);
      const view = M.lookAt(eye, [0, cy, 0], [0, 1, 0]);
      const vp = M.mul(proj, view);

      gl.useProgram(pprog); gl.uniformMatrix4fv(PU.mvp, false, vp); gl.uniform3fv(PU.rim, rimColor); gl.uniform1f(PU.t, reduce ? 0 : (performance.now() - t0) / 1000);
      gl.bindBuffer(gl.ARRAY_BUFFER, fb); gl.enableVertexAttribArray(aPP); gl.vertexAttribPointer(aPP, 3, gl.FLOAT, false, 0, 0);
      gl.drawArrays(gl.POINTS, 0, floorN);

      gl.useProgram(prog); gl.uniform3fv(U.eye, eye); gl.uniform3fv(U.rim, rimColor);
      // opaque first, translucent shell last without depth write
      const order = parts.slice().sort((a, b) => b.L.alpha - a.L.alpha);
      const rect = canvas.getBoundingClientRect();
      order.forEach((pt) => {
        const L = pt.L, off = [L.pos[0] + L.explode[0] * e, L.pos[2] + L.explode[2] * e, -(L.pos[1] + L.explode[1] * e)];
        const model = M.trans(off[0], off[1], off[2]);
        gl.uniformMatrix4fv(U.mvp, false, vp); gl.uniformMatrix4fv(U.model, false, model);
        gl.uniform3fv(U.base, L.color); gl.uniform1f(U.alpha, L.alpha);
        gl.depthMask(L.alpha > 0.95);
        gl.bindBuffer(gl.ARRAY_BUFFER, pt.pb); gl.enableVertexAttribArray(aP); gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, pt.nb); gl.enableVertexAttribArray(aN); gl.vertexAttribPointer(aN, 3, gl.FLOAT, false, 0, 0);
        gl.drawArrays(gl.TRIANGLES, 0, pt.count);
        // label position (top-centre of part)
        const lab = labels[pt.name];
        if (lab) {
          const top = { base: 60, lid: 14, well: 44, strainer: -6 }[pt.name] || 0;
          const side = { base: 70, lid: 0, well: 0, strainer: 0 }[pt.name] || 0;
          const w = [off[0] + side, off[1] + top, off[2]];
          const c = [0, 1, 2, 3].map((r) => vp[r] * w[0] + vp[4 + r] * w[1] + vp[8 + r] * w[2] + vp[12 + r]);
          if (c[3] > 0) {
            lab.style.left = ((c[0] / c[3] * 0.5 + 0.5) * rect.width) + 'px';
            lab.style.top = ((-c[1] / c[3] * 0.5 + 0.5) * rect.height) + 'px';
          }
          lab.style.opacity = pt.name === 'base' || pt.name === 'lid' ? '1' : String(Math.min(1, 0.15 + e));
        }
      });
      gl.depthMask(true);
    }

    function loop() {
      if (st.running) return;
      st.running = true;
      const tick = () => {
        if (!st.visible || document.hidden) { st.running = false; return; }
        const d = st.target - st.explode;
        st.explode += Math.sign(d) * Math.min(Math.abs(d), 0.018);
        if (!st.drag && !reduce) { st.idle++; if (st.idle > 90) st.yaw += 0.0035; }
        render();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }

    canvas.addEventListener('pointerdown', (e) => { st.drag = { x: e.clientX, y: e.clientY }; st.idle = 0; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', (e) => {
      if (!st.drag) return;
      st.yaw -= (e.clientX - st.drag.x) * 0.008; st.pitch = Math.max(-0.2, Math.min(1.25, st.pitch + (e.clientY - st.drag.y) * 0.006));
      st.drag = { x: e.clientX, y: e.clientY }; if (reduce) render();
    });
    const end = () => { st.drag = null; st.idle = 0; };
    canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
    canvas.addEventListener('wheel', (e) => { e.preventDefault(); st.dist = Math.max(200, Math.min(520, st.dist + e.deltaY * 0.3)); if (reduce) render(); }, { passive: false });
    new IntersectionObserver((en) => { st.visible = en[0].isIntersecting; if (st.visible) loop(); }).observe(box);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) loop(); });
    window.addEventListener('resize', () => render());

    const api = {
      explode(on) { st.target = on ? 1 : 0; if (reduce) { st.explode = st.target; render(); } else loop(); },
      get exploded() { return st.target === 1; },
      setRim(hex) { const n = parseInt(hex.replace('#', ''), 16); if (!isNaN(n)) rimColor = [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; render(); },
      setLabels(map) { Object.keys(map).forEach((k) => { if (labels[k]) labels[k].textContent = map[k]; }); },
    };
    render(); loop();
    return api;
  }

  window.AquaDevice3D = { mount };
})();
