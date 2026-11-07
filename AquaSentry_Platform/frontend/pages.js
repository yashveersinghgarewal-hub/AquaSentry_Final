/**
 * Page logic for the project pages: market research (charts + globe), sales & expansion (charts + ROI calculator)
 * and the device simulator (auto-sizing frame). Each block only runs if its elements are on the page.
 */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const t = (k, v) => window.I18N.t(k, v);
  const crore = (v) => '₹' + (Math.round(v * 100) / 100).toLocaleString('en-IN') + ' Cr';

  function fmtInr(val) {
    if (val >= 1e7) return '₹' + (val / 1e7).toFixed(2) + ' Cr';
    return '₹' + (val / 1e5).toFixed(1) + ' L';
  }

  // ---------------- market research ----------------
  function initMarket() {
    if (!$('chartProfit')) return;
    const C = window.AquaCharts;
    C.draw('bar', $('chartProfit'), () => ({
      labels: [t('pg.q1'), t('pg.q2'), t('pg.q3'), t('pg.q4')], stacked: true, totals: true, left: 70,
      series: [{ name: t('mk.s.hw'), color: 'var(--primary)', data: [1.5, 3.2, 6.8, 9.5] },
        { name: t('mk.s.saas'), color: 'var(--violet)', data: [0.1, 0.5, 1.4, 2.82] }],
      yFmt: (v) => '₹' + (Math.round(v * 10) / 10) + ' Cr', tipFmt: crore,
    }));
    C.draw('donut', $('chartTam'), () => ({
      items: [{ name: t('mk.s.niche'), value: 1.2, color: 'var(--primary)' }, { name: t('mk.s.general'), value: 6.3, color: 'var(--violet)' }],
      center: { big: '$7.5B', small: t('mk.s.total') }, tipFmt: (v) => '$' + v + 'B',
    }));
    if ($('globe') && window.AquaGlobe) {
      const spots = () => [
        { lat: 19.0, lon: 75.5, label: t('mk.g.mh'), primary: true, dx: -10, dy: 14 },
        { lat: 25.6, lon: 85.1, label: t('mk.g.ig'), primary: true, dx: -10, dy: -10 },
        { lat: 23.7, lon: 90.4, label: t('mk.g.bd'), primary: true, dx: 10, dy: -12 },
        { lat: 10.5, lon: 105.5, label: t('mk.g.mk'), dx: 10, dy: 14 },
        { lat: 17.0, lon: 95.5, label: t('mk.g.ir'), dx: 10, dy: 4 },
        { lat: 36.5, lon: -117.0, label: t('mk.g.us') },
      ];
      const g = window.AquaGlobe.mount($('globe'), { hotspots: spots(), origin: 0 });
      document.addEventListener('aquasentry:lang', () => g.setLabels(spots().map((s) => s.label)));
    }
  }

  // ---------------- sales & expansion ----------------
  let freq = 12;
  function calcRoi() {
    const src = parseInt($('roiSrc').value, 10), fee = parseInt($('roiLab').value, 10);
    $('roiSrcOut').textContent = src.toLocaleString('en-IN');
    $('roiLabOut').textContent = '₹' + fee.toLocaleString('en-IN');
    // same model as the original dashboard calculator
    const trad = src * freq * fee;
    const nodes = Math.max(1, Math.ceil(src / 5));
    const capex = nodes * 6500, consumables = src * freq * 5, saas = nodes * 1188;
    const fleet = capex + consumables + saas;
    const save = Math.max(0, trad - fleet);
    const monthlySave = Math.max(1, trad / 12 - (consumables + saas) / 12);
    const payback = capex / monthlySave;
    const UI = window.AquaUI;
    UI.countTo($('roiSave'), save, fmtInr, 900);
    $('roiPct').textContent = t('sl.roi.pct', { p: Math.round(save / trad * 100) });
    UI.countTo($('roiTrad'), trad, fmtInr, 900);
    UI.countTo($('roiFleet'), fleet, fmtInr, 900);
    $('roiNodes').textContent = t('sl.roi.nodes', { n: nodes.toLocaleString('en-IN') });
    UI.countTo($('roiPay'), payback, (v) => t('sl.roi.months', { m: v.toFixed(1) }), 900);
    UI.countTo($('roiPeople'), src * 500, (v) => Math.round(v).toLocaleString('en-IN'), 900);
    const a = Math.min(92, Math.max(8, Math.round(fleet / trad * 100)));
    $('roiBarA').style.width = a + '%'; $('roiBarB').style.width = (100 - a) + '%';
    $('roiLegA').textContent = t('sl.roi.barA', { v: fmtInr(fleet) });
    $('roiLegB').textContent = t('sl.roi.barB', { v: fmtInr(save) });
  }
  function initSales() {
    if (!$('chartRevenue')) return;
    const C = window.AquaCharts;
    C.draw('bar', $('chartRevenue'), () => ({
      labels: [t('sl.y1'), t('sl.y2'), t('sl.y3')], stacked: true, totals: true, left: 70,
      series: [{ name: t('sl.s.hw'), color: 'var(--primary)', data: [1.8, 14.5, 28.5] },
        { name: t('sl.s.saas'), color: 'var(--violet)', data: [0.3, 3.2, 8.4] },
        { name: t('sl.s.cons'), color: 'var(--caution-fill)', data: [0.1, 1.4, 4.2] }],
      yFmt: (v) => '₹' + Math.round(v) + ' Cr', tipFmt: crore,
    }));
    C.draw('line', $('chartFleet'), () => ({
      labels: ['Q1', 'Q2', 'Q3', 'Q4', 'Q6', 'Q8', 'Q10', 'Q12'], left: 64,
      series: [{ name: t('sl.s.rural'), color: 'var(--primary)', data: [25, 75, 250, 800, 3500, 10000, 16000, 22500] },
        { name: t('sl.s.urban'), color: 'var(--violet)', data: [10, 40, 150, 500, 2500, 8000, 16000, 25000] }],
      yFmt: (v) => v >= 1000 ? Math.round(v / 1000) + 'k' : String(Math.round(v)), tipFmt: (v) => v.toLocaleString('en-IN') + ' ' + t('sl.units'),
    }));
    ['roiSrc', 'roiLab'].forEach((id) => $(id).addEventListener('input', calcRoi));
    document.querySelectorAll('[data-freq]').forEach((b) => b.addEventListener('click', () => {
      freq = parseInt(b.dataset.freq, 10);
      document.querySelectorAll('[data-freq]').forEach((x) => x.setAttribute('aria-pressed', x === b ? 'true' : 'false'));
      calcRoi();
    }));
    document.addEventListener('aquasentry:lang', calcRoi);
    calcRoi();
  }

  // ---------------- device simulator ----------------
  function initSim() {
    const f = $('simFrame'); if (!f) return;
    window.addEventListener('message', (e) => {
      const h = e.data && e.data.aquasentryFrameHeight;
      if (e.source === f.contentWindow && h > 200 && h < 4000) f.style.height = (h + 8) + 'px';
    });
  }

  document.addEventListener('DOMContentLoaded', () => { initMarket(); initSales(); initSim(); });
})();
