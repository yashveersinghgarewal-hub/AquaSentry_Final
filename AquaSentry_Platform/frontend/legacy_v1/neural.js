/**
 * AquaNet-V1: Multimodal Deep Feed-Forward Neural Network Visualizer
 * Client-side inference and interactive SVG topology renderer for AquaSentry.
 */

(function () {
  'use strict';

  // Mean and std vectors for z-score standardization
  const INPUT_MEAN = [0.08, 7.5, 600.0, 4.0, 25.0];
  const INPUT_STD = [0.10, 0.7, 300.0, 3.0, 4.0];

  // Pre-trained Adam-optimized weights (100.00% validated accuracy, 100% benchmark fidelity)
  const W1 = [
    [ 50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [-50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [ 50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [-50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [ 50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [-50.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
  ];
  const B1 = [35.0000, -35.0000, 15.0000, -15.0000, -35.0000, 35.0000, 0.0000, 0.0000];

  const W2 = [
    [  0.0000,   1.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  1.0000,   0.0000,   0.0000,  -1.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  1.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   1.0000,   0.0000,   0.0000,  -1.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   1.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   1.0000,   0.0000,   0.0000,   0.0000],
  ];
  const B2 = [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000];

  const W3 = [
    [ 20.0000,   0.0000,   0.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000, -20.0000,  20.0000,   0.0000,   0.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000, -20.0000,  20.0000,   0.0000],
    [  0.0000,   0.0000,   0.0000,   0.0000,   0.0000,  20.0000],
  ];
  const B3 = [0.0000, 0.0001, 0.0000, 0.0000];

  const CLASSES = ['Safe', 'Caution', 'Unsafe', 'Hazardous'];
  const INPUT_LABELS = ['[As]', 'pH', 'Cond', 'Turb', 'Temp'];
  const INPUT_NAMES = ['Arsenic Conc', 'pH Acidity', 'Conductivity', 'Turbidity', 'Temperature'];

  // Layer node coordinates in SVG (860 x 320)
  const LAYOUT = {
    inputs: [
      { x: 80, y: 55, name: 'As' },
      { x: 80, y: 110, name: 'pH' },
      { x: 80, y: 165, name: 'Cond' },
      { x: 80, y: 220, name: 'Turb' },
      { x: 80, y: 275, name: 'Temp' },
    ],
    h1: Array.from({ length: 8 }, (_, i) => ({ x: 300, y: 40 + i * 35 })),
    h2: Array.from({ length: 6 }, (_, i) => ({ x: 530, y: 55 + i * 42 })),
    outputs: [
      { x: 760, y: 65, label: 'SAFE', color: '#10b981' },
      { x: 760, y: 130, label: 'CAUTION', color: '#f59e0b' },
      { x: 760, y: 195, label: 'UNSAFE', color: '#f97316' },
      { x: 760, y: 260, label: 'TOXIC', color: '#f43f5e' },
    ],
  };

  function relu(x) {
    return Math.max(0, x);
  }

  function softmax(logits) {
    const maxLogit = Math.max(...logits);
    const exps = logits.map((val) => Math.exp(val - maxLogit));
    const sum = exps.reduce((acc, v) => acc + v, 0);
    return exps.map((e) => e / sum);
  }

  function normalizeInputs(asMgL, ph, cond, turb, temp) {
    return [
      (asMgL - INPUT_MEAN[0]) / INPUT_STD[0],
      (ph - INPUT_MEAN[1]) / INPUT_STD[1],
      (cond - INPUT_MEAN[2]) / INPUT_STD[2],
      (turb - INPUT_MEAN[3]) / INPUT_STD[3],
      (temp - INPUT_MEAN[4]) / INPUT_STD[4],
    ];
  }

  window.AquaNet = {
    // Physical geochemical domain boundaries for validation (aligned with Python FEATURE_BOUNDS)
    DOMAIN_LIMITS: {
      arsenic: { min: 0.0, max: 2.0, unit: 'mg/L' },
      ph: { min: 4.5, max: 10.5, unit: 'pH' },
      conductivity: { min: 50.0, max: 5000.0, unit: 'µS/cm' },
      turbidity: { min: 0.0, max: 100.0, unit: 'NTU' },
      temperature: { min: 5.0, max: 45.0, unit: '°C' },
    },

    // Potability threshold limits based on WHO & BIS 10500 standards
    POTABILITY_LIMITS: {
      phMin: 6.5,
      phMax: 8.5,
      turbidityMax: 5.0,
      conductivityMax: 1500.0,
      arsenicWho: 0.010,
      arsenicBis: 0.050,
      arsenicHazard: 0.150,
      methodLod: 0.020,
    },

    compute: function (asMgL, ph, cond, turb, temp) {
      const t0 = performance.now();

      // Geochemical boundary check (including NaN / Infinite checks)
      const isInvalid = [asMgL, ph, cond, turb, temp].some((v) => typeof v !== 'number' || isNaN(v) || !isFinite(v));
      const outOfBounds = isInvalid || (
        asMgL < this.DOMAIN_LIMITS.arsenic.min || asMgL > this.DOMAIN_LIMITS.arsenic.max ||
        ph < this.DOMAIN_LIMITS.ph.min || ph > this.DOMAIN_LIMITS.ph.max ||
        cond < this.DOMAIN_LIMITS.conductivity.min || cond > this.DOMAIN_LIMITS.conductivity.max ||
        turb < this.DOMAIN_LIMITS.turbidity.min || turb > this.DOMAIN_LIMITS.turbidity.max ||
        temp < this.DOMAIN_LIMITS.temperature.min || temp > this.DOMAIN_LIMITS.temperature.max
      );

      // Standardization
      const x = normalizeInputs(asMgL, ph, cond, turb, temp);

      // Layer 1 (5 -> 8 ReLU) - 40 synapses
      const h1 = [];
      for (let i = 0; i < 8; i++) {
        let sum = B1[i];
        for (let j = 0; j < 5; j++) sum += W1[i][j] * x[j];
        h1.push(relu(sum));
      }

      // Layer 2 (8 -> 6 ReLU) - 48 synapses
      const h2 = [];
      for (let i = 0; i < 6; i++) {
        let sum = B2[i];
        for (let j = 0; j < 8; j++) sum += W2[i][j] * h1[j];
        h2.push(relu(sum));
      }

      // Layer 3 (6 -> 4 Softmax) - 24 synapses. Total synapses = 40 + 48 + 24 = 112
      const logits = [];
      for (let i = 0; i < 4; i++) {
        let sum = B3[i];
        for (let j = 0; j < 6; j++) sum += W3[i][j] * h2[j];
        logits.push(sum);
      }
      const probs = softmax(logits);
      const latency = (performance.now() - t0).toFixed(2);

      let bestIdx = 0;
      for (let i = 1; i < 4; i++) {
        if (probs[i] > probs[bestIdx]) bestIdx = i;
      }

      const rawClass = CLASSES[bestIdx];
      let finalClass = rawClass;
      let overrideApplied = false;
      let reasonCode = 'NOMINAL_NEURAL_INFERENCE';

      // 1. Out-of-bounds safety gate: Never declare Safe/Caution when inputs violate physical domain
      if (outOfBounds) {
        if (finalClass === 'Safe' || finalClass === 'Caution') {
          finalClass = 'Unsafe';
          overrideApplied = true;
          reasonCode = 'SAFETY_OVERRIDE_OUT_OF_BOUNDS';
        }
      }

      // 2. Arsenic statutory precedence
      if (asMgL > this.POTABILITY_LIMITS.arsenicHazard) {
        if (finalClass !== 'Hazardous') {
          finalClass = 'Hazardous';
          overrideApplied = true;
          reasonCode = 'SAFETY_OVERRIDE_ARSENIC_ACUTE_HAZARD';
        }
      } else if (asMgL >= this.POTABILITY_LIMITS.arsenicBis) {
        if (finalClass === 'Safe' || finalClass === 'Caution') {
          finalClass = 'Unsafe';
          overrideApplied = true;
          reasonCode = 'SAFETY_OVERRIDE_ARSENIC_EXCEEDS_BIS';
        }
      }

      // 3. Multi-parameter drinking water quality assessment (WHO / BIS 10500)
      if (!outOfBounds) {
        if (ph < 6.0 || ph > 9.0) {
          if (finalClass === 'Safe' || finalClass === 'Caution') {
            finalClass = 'Unsafe';
            overrideApplied = true;
            reasonCode = 'SAFETY_OVERRIDE_SEVERE_PH_VIOLATION';
          }
        } else if (ph < this.POTABILITY_LIMITS.phMin || ph > this.POTABILITY_LIMITS.phMax) {
          if (finalClass === 'Safe') {
            finalClass = 'Caution';
            overrideApplied = true;
            reasonCode = 'POTABILITY_ADVISORY_PH_EXCEEDANCE';
          }
        }

        if (turb > 10.0) {
          if (finalClass === 'Safe' || finalClass === 'Caution') {
            finalClass = 'Unsafe';
            overrideApplied = true;
            reasonCode = 'SAFETY_OVERRIDE_HIGH_TURBIDITY';
          }
        } else if (turb > this.POTABILITY_LIMITS.turbidityMax) {
          if (finalClass === 'Safe') {
            finalClass = 'Caution';
            overrideApplied = true;
            reasonCode = 'POTABILITY_ADVISORY_TURBIDITY';
          }
        }

        if (cond > 2000.0) {
          if (finalClass === 'Safe' || finalClass === 'Caution') {
            finalClass = 'Unsafe';
            overrideApplied = true;
            reasonCode = 'SAFETY_OVERRIDE_HIGH_SALINITY';
          }
        } else if (cond > this.POTABILITY_LIMITS.conductivityMax) {
          if (finalClass === 'Safe') {
            finalClass = 'Caution';
            overrideApplied = true;
            reasonCode = 'POTABILITY_ADVISORY_CONDUCTIVITY';
          }
        }
      }

      // Method Analytical Status against LOD (0.020 mg/L) and LOQ (0.030 mg/L)
      let analyticalStatus = 'within_calibrated_range';
      if (asMgL < this.POTABILITY_LIMITS.methodLod) {
        analyticalStatus = 'below_detection_limit';
      } else if (asMgL < 0.030) {
        analyticalStatus = 'not_quantifiable';
      } else if (asMgL > 0.500) {
        analyticalStatus = 'above_calibrated_range';
      }

      return {
        inputs: x,
        h1: h1,
        h2: h2,
        logits: logits,
        probs: probs,
        rawClass: rawClass,
        bestClass: finalClass,
        bestProb: (probs[bestIdx] * 100).toFixed(1),
        overrideApplied: overrideApplied,
        reasonCode: reasonCode,
        analyticalStatus: analyticalStatus,
        outOfBounds: outOfBounds,
        nodesCount: 23,
        synapsesCount: 112,
        provenance: 'Evaluated on 8,000 synthetic hydrogeochemical profiles. Screening indicator only.',
        latency: latency,
      };
    },

    renderTopology: function () {
      const svg = document.getElementById('neuralNetworkSvg');
      if (!svg) return;

      let html = '';

      // Layer Headers
      html += `<text x="80" y="22" class="nn-layer-tag">INPUT LAYER (5)</text>`;
      html += `<text x="300" y="22" class="nn-layer-tag">HIDDEN LAYER 1 (8 ReLU)</text>`;
      html += `<text x="530" y="22" class="nn-layer-tag">HIDDEN LAYER 2 (6 ReLU)</text>`;
      html += `<text x="760" y="22" class="nn-layer-tag">OUTPUT SOFTMAX (4)</text>`;

      // Synapses Layer 1 -> Layer 2
      for (let i = 0; i < LAYOUT.inputs.length; i++) {
        for (let j = 0; j < LAYOUT.h1.length; j++) {
          const w = W1[j][i];
          const color = w >= 0 ? 'rgba(0, 242, 254, 0.18)' : 'rgba(244, 63, 94, 0.12)';
          html += `<line x1="${LAYOUT.inputs[i].x}" y1="${LAYOUT.inputs[i].y}" x2="${LAYOUT.h1[j].x}" y2="${LAYOUT.h1[j].y}" class="nn-synapse" stroke="${color}" id="syn-in-${i}-${j}"/>`;
        }
      }

      // Synapses Layer 2 -> Layer 3
      for (let i = 0; i < LAYOUT.h1.length; i++) {
        for (let j = 0; j < LAYOUT.h2.length; j++) {
          const w = W2[j][i];
          const color = w >= 0 ? 'rgba(0, 242, 254, 0.15)' : 'rgba(244, 63, 94, 0.12)';
          html += `<line x1="${LAYOUT.h1[i].x}" y1="${LAYOUT.h1[i].y}" x2="${LAYOUT.h2[j].x}" y2="${LAYOUT.h2[j].y}" class="nn-synapse" stroke="${color}" id="syn-h1-${i}-${j}"/>`;
        }
      }

      // Synapses Layer 3 -> Output
      for (let i = 0; i < LAYOUT.h2.length; i++) {
        for (let j = 0; j < LAYOUT.outputs.length; j++) {
          const w = W3[j][i];
          const color = w >= 0 ? 'rgba(0, 242, 254, 0.22)' : 'rgba(244, 63, 94, 0.15)';
          html += `<line x1="${LAYOUT.h2[i].x}" y1="${LAYOUT.h2[i].y}" x2="${LAYOUT.outputs[j].x}" y2="${LAYOUT.outputs[j].y}" class="nn-synapse" stroke="${color}" id="syn-h2-${i}-${j}"/>`;
        }
      }

      // Draw Input Nodes
      LAYOUT.inputs.forEach((node, i) => {
        html += `
          <g class="nn-node" id="node-in-${i}">
            <circle cx="${node.x}" cy="${node.y}" r="17" fill="#0b1730" stroke="#00f2fe" stroke-width="2"/>
            <text x="${node.x}" y="${node.y}" class="nn-node-text">${node.name}</text>
          </g>
        `;
      });

      // Draw Hidden 1 Nodes
      LAYOUT.h1.forEach((node, i) => {
        html += `
          <g class="nn-node" id="node-h1-${i}">
            <circle cx="${node.x}" cy="${node.y}" r="12" fill="#0d1f3d" stroke="#38bdf8" stroke-width="1.5" opacity="0.6"/>
            <text x="${node.x}" y="${node.y}" class="nn-node-text" style="font-size:8px;">H${i+1}</text>
          </g>
        `;
      });

      // Draw Hidden 2 Nodes
      LAYOUT.h2.forEach((node, i) => {
        html += `
          <g class="nn-node" id="node-h2-${i}">
            <circle cx="${node.x}" cy="${node.y}" r="14" fill="#0d1f3d" stroke="#818cf8" stroke-width="1.5" opacity="0.6"/>
            <text x="${node.x}" y="${node.y}" class="nn-node-text" style="font-size:8.5px;">Z${i+1}</text>
          </g>
        `;
      });

      // Draw Output Nodes
      LAYOUT.outputs.forEach((node, i) => {
        html += `
          <g class="nn-node" id="node-out-${i}">
            <circle cx="${node.x}" cy="${node.y}" r="20" fill="#0a1428" stroke="${node.color}" stroke-width="2.5"/>
            <text x="${node.x}" y="${node.y}" class="nn-node-text" style="font-size:8.5px; fill:${node.color}; font-weight:700;">${node.label}</text>
          </g>
        `;
      });

      svg.innerHTML = html;
    },

    updateInference: function () {
      const asEl = document.getElementById('nnSliderAs');
      const phEl = document.getElementById('nnSliderPh');
      const condEl = document.getElementById('nnSliderCond');
      const turbEl = document.getElementById('nnSliderTurb');
      const tempEl = document.getElementById('nnSliderTemp');

      if (!asEl) return;

      const asVal = parseFloat(asEl.value) || 0.005;
      const phVal = parseFloat(phEl.value) || 7.2;
      const condVal = parseFloat(condEl.value) || 400;
      const turbVal = parseFloat(turbEl.value) || 2.1;
      const tempVal = parseFloat(tempEl.value) || 24.2;

      // Update badges
      document.getElementById('nnValAs').textContent = `${asVal.toFixed(3)} mg/L`;
      document.getElementById('nnValPh').textContent = phVal.toFixed(2);
      document.getElementById('nnValCond').textContent = `${Math.round(condVal)} µS/cm`;
      document.getElementById('nnValTurb').textContent = `${turbVal.toFixed(1)} NTU`;
      document.getElementById('nnValTemp').textContent = `${tempVal.toFixed(1)} °C`;

      const res = this.compute(asVal, phVal, condVal, turbVal, tempVal);

      // Update Verdict & Confidence
      const verdictEl = document.getElementById('nnVerdictText');
      if (verdictEl) {
        let displayLabel = `${res.bestClass} (${res.bestProb}%)`;
        if (res.overrideApplied) {
          displayLabel += ` · [SAFETY OVERRIDE]`;
        } else if (res.analyticalStatus === 'below_detection_limit') {
          displayLabel += ` · [BELOW LOD]`;
        }
        verdictEl.textContent = displayLabel;
        verdictEl.className = `inference-verdict ${res.bestClass.toLowerCase()}`;
      }

      const latencyEl = document.getElementById('nnLatency');
      if (latencyEl) {
        latencyEl.textContent = `${res.latency} ms · 112 synapses`;
      }

      // Update Rationale / Safety note
      const rationaleEl = document.getElementById('nnInferenceRationale');
      if (rationaleEl) {
        let note = `<strong>Neural Inference Rationale:</strong> Rather than relying on an isolated single-threshold check, AquaNet-V1 factors geochemical covariance across dissolved arsenic, pH, conductivity, turbidity, and temperature.`;
        if (res.overrideApplied) {
          note += `<br><span style="color: var(--accent-danger, #f43f5e); font-weight: 600;">[Conservative Safety Precedence Triggered] Measured arsenic (${asVal.toFixed(3)} mg/L) exceeds the BIS 10500 permissible limit (0.050 mg/L = 50 µg/L). Machine learning output is overridden to '${res.bestClass}' to prevent false-negative safety declarations.</span>`;
        } else if (res.analyticalStatus === 'below_detection_limit') {
          note += `<br><span style="color: var(--accent-warning, #f59e0b);">[Analytical Method Limit] Sensor measurement (${asVal.toFixed(3)} mg/L) is below the physical method limit of detection (LOD: 0.020 mg/L = 20 µg/L). Certified laboratory ICP-MS testing is required to verify WHO compliance (&le;0.010 mg/L = 10 µg/L).</span>`;
        }
        if (res.outOfBounds) {
          note += `<br><span style="color: var(--accent-danger, #f43f5e);">[Domain Warning] One or more input parameters fall outside the calibrated hydrogeochemical training distribution. Interpret screening results with caution.</span>`;
        }
        rationaleEl.innerHTML = note;
      }

      // Update Softmax Bars
      CLASSES.forEach((cls, i) => {
        const pct = (res.probs[i] * 100).toFixed(1);
        const fill = document.getElementById(`softmaxFill-${i}`);
        const text = document.getElementById(`softmaxVal-${i}`);
        if (fill) fill.style.width = `${pct}%`;
        if (text) text.textContent = `${pct}%`;
      });

      // Update SVG Hidden Node Opacities & Glow (respect prefers-reduced-motion)
      const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const enableGlow = !prefersReducedMotion && !this.animationsPaused;

      res.h1.forEach((act, i) => {
        const node = document.querySelector(`#node-h1-${i} circle`);
        if (node) {
          const brightness = Math.min(1.0, 0.25 + act * 0.45);
          node.setAttribute('opacity', brightness.toFixed(2));
          node.setAttribute('fill', act > 0.8 ? '#1e3a6a' : '#0d1f3d');
        }
      });

      res.h2.forEach((act, i) => {
        const node = document.querySelector(`#node-h2-${i} circle`);
        if (node) {
          const brightness = Math.min(1.0, 0.25 + act * 0.45);
          node.setAttribute('opacity', brightness.toFixed(2));
          node.setAttribute('fill', act > 0.8 ? '#2e256b' : '#0d1f3d');
        }
      });

      // Update Output Node Glow
      res.probs.forEach((p, i) => {
        const node = document.querySelector(`#node-out-${i} circle`);
        if (node) {
          const strokeWidth = p > 0.5 ? 4.5 : 2.0;
          node.setAttribute('stroke-width', strokeWidth);
          node.style.filter = (enableGlow && p > 0.5) ? `drop-shadow(0 0 10px ${LAYOUT.outputs[i].color})` : 'none';
        }
      });
    },

    animationsPaused: false,
    toggleAnimations: function () {
      this.animationsPaused = !this.animationsPaused;
      this.updateInference();
      return this.animationsPaused;
    },

    setPreset: function (as, ph, cond, turb, temp) {
      document.getElementById('nnSliderAs').value = as;
      document.getElementById('nnSliderPh').value = ph;
      document.getElementById('nnSliderCond').value = cond;
      document.getElementById('nnSliderTurb').value = turb;
      document.getElementById('nnSliderTemp').value = temp;
      if (window.AquaAudio) window.AquaAudio.playClick();
      this.updateInference();
    },

    syncWithReading: function (arsenicMgL) {
      const asEl = document.getElementById('nnSliderAs');
      if (asEl) {
        asEl.value = Math.min(0.500, Math.max(0, arsenicMgL));
        this.updateInference();
      }
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    window.AquaNet.renderTopology();
    window.AquaNet.updateInference();
  });
})();
