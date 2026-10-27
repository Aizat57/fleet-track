/* FleetTrack charts — dependency-free SVG line/area and donut.
   Line: 2.25px stroke, light grid, crosshair + tooltip, keyboard-steppable, last value direct-labelled.
   Donut: 2px surface gap between segments, legend kept in sync on hover. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const rm = (v, short) => {
    if (short) {
      if (Math.abs(v) >= 1e6) return 'RM ' + (v / 1e6).toFixed(1) + 'M';
      if (Math.abs(v) >= 1e3) return 'RM ' + (v / 1e3).toFixed(v >= 1e4 ? 0 : 1) + 'k';
      return 'RM ' + Math.round(v);
    }
    return 'RM ' + v.toLocaleString('en-MY', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  const el = (name, attrs, parent) => {
    const n = document.createElementNS(NS, name);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };

  function niceTicks(max, count) {
    if (max <= 0) return [0, 1];
    const raw = max / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw);
    const ticks = [];
    for (let v = 0; v <= max + step * 0.001; v += step) ticks.push(v);
    if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
    return ticks;
  }

  // Monotone cubic interpolation: smooth, but never overshoots below zero or above peaks.
  function monotonePath(pts) {
    const n = pts.length;
    if (n < 2) return '';
    if (n === 2) return `M${pts[0][0]},${pts[0][1]}L${pts[1][0]},${pts[1][1]}`;
    const dx = [], dy = [], m = [], t = [];
    for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; dy[i] = pts[i + 1][1] - pts[i][1]; m[i] = dy[i] / dx[i]; }
    t[0] = m[0]; t[n - 1] = m[n - 2];
    for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
    for (let i = 0; i < n - 1; i++) {
      if (m[i] === 0) { t[i] = t[i + 1] = 0; continue; }
      const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
      if (s > 9) { const k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
    }
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < n - 1; i++) {
      const h = dx[i] / 3;
      d += `C${pts[i][0] + h},${pts[i][1] + t[i] * h} ${pts[i + 1][0] - h},${pts[i + 1][1] - t[i + 1] * h} ${pts[i + 1][0]},${pts[i + 1][1]}`;
    }
    return d;
  }

  function lineChart(host) {
    const data = JSON.parse(document.getElementById(host.dataset.source).textContent);
    if (!data.length) return;
    const height = +host.dataset.height || 260;
    const tip = document.createElement('div');
    tip.className = 'tooltip';
    tip.setAttribute('role', 'status');
    let svg, active = -1, geo;

    function draw() {
      const W = host.clientWidth;
      if (!W) return;
      const pad = { t: 16, r: W < 480 ? 12 : 64, b: 30, l: 56 };
      const iw = W - pad.l - pad.r, ih = height - pad.t - pad.b;
      const max = Math.max(...data.map(d => d.value));
      const ticks = niceTicks(max, 4);
      const top = ticks[ticks.length - 1] || 1;
      const x = i => pad.l + (data.length === 1 ? iw / 2 : (i * iw) / (data.length - 1));
      const y = v => pad.t + ih - (v / top) * ih;
      host.innerHTML = '';
      svg = el('svg', { viewBox: `0 0 ${W} ${height}`, height, role: 'img', tabindex: '0',
        'aria-label': host.dataset.label || 'Line chart' });
      const defs = el('defs', {}, svg);
      const g = el('linearGradient', { id: 'ft-area', x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
      el('stop', { offset: '0%', 'stop-color': '#2563EB', 'stop-opacity': 0.18 }, g);
      el('stop', { offset: '100%', 'stop-color': '#2563EB', 'stop-opacity': 0 }, g);
      ticks.forEach(tv => {
        el('line', { class: 'grid-line', x1: pad.l, x2: W - pad.r, y1: y(tv), y2: y(tv) }, svg);
        const lab = el('text', { class: 'axis-label', x: pad.l - 10, y: y(tv) + 4, 'text-anchor': 'end' }, svg);
        lab.textContent = rm(tv, true);
      });
      const every = iw / data.length < 34 ? 2 : 1;
      data.forEach((d, i) => {
        if (i % every && i !== data.length - 1) return;
        const lab = el('text', { class: 'axis-label', x: x(i), y: height - 8, 'text-anchor': 'middle' }, svg);
        lab.textContent = d.label;
      });
      const pts = data.map((d, i) => [x(i), y(d.value)]);
      const line = monotonePath(pts);
      el('path', { class: 'area', d: `${line}L${pts[pts.length - 1][0]},${y(0)}L${pts[0][0]},${y(0)}Z` }, svg);
      const path = el('path', { class: 'line', d: line }, svg);
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches && path.getTotalLength) {
        const len = path.getTotalLength();
        path.style.strokeDasharray = len; path.style.strokeDashoffset = len;
        path.getBoundingClientRect();
        path.style.transition = 'stroke-dashoffset 700ms cubic-bezier(.2,.7,.2,1)';
        path.style.strokeDashoffset = 0;
        path.addEventListener('transitionend', () => { path.style.strokeDasharray = 'none'; }, { once: true });
      }
      // Selective direct label: only the latest month.
      const last = data[data.length - 1];
      el('circle', { cx: pts[pts.length - 1][0], cy: pts[pts.length - 1][1], r: 4, fill: '#2563EB', stroke: '#fff', 'stroke-width': 2 }, svg);
      if (W >= 480) {
        const endLab = el('text', { class: 'end-label', x: pts[pts.length - 1][0] + 10, y: pts[pts.length - 1][1] + 4 }, svg);
        endLab.textContent = rm(last.value, true);
      }
      const cross = el('line', { class: 'crosshair', y1: pad.t, y2: pad.t + ih, x1: -10, x2: -10 }, svg);
      const dot = el('circle', { class: 'hover-dot', r: 5, cx: -10, cy: -10 }, svg);
      const hit = el('rect', { x: pad.l - 10, y: 0, width: iw + 20, height, fill: 'transparent' }, svg);
      geo = { x, y, pts, cross, dot, iw, pad };
      hit.addEventListener('pointermove', e => {
        const r = svg.getBoundingClientRect();
        const px = (e.clientX - r.left) * (W / r.width);
        const i = Math.round(((px - pad.l) / iw) * (data.length - 1));
        show(Math.max(0, Math.min(data.length - 1, i)));
      });
      hit.addEventListener('pointerleave', hide);
      svg.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
          e.preventDefault();
          show(Math.max(0, Math.min(data.length - 1, (active < 0 ? data.length - 1 : active) + (e.key === 'ArrowRight' ? 1 : -1))));
        } else if (e.key === 'Escape') hide();
      });
      svg.addEventListener('focus', () => show(data.length - 1));
      svg.addEventListener('blur', hide);
      host.appendChild(svg);
      host.appendChild(tip);
    }

    function show(i) {
      active = i;
      const [px, py] = geo.pts[i];
      geo.cross.setAttribute('x1', px); geo.cross.setAttribute('x2', px);
      geo.dot.setAttribute('cx', px); geo.dot.setAttribute('cy', py); geo.dot.classList.add('on');
      const scale = host.clientWidth / svg.viewBox.baseVal.width;
      tip.innerHTML = `<div class="tt-label">${data[i].full}</div><div class="tt-value">${rm(data[i].value)}</div>`;
      tip.style.left = Math.min(Math.max(px * scale, 80), host.clientWidth - 80) + 'px';
      tip.style.top = py * scale + 'px';
      tip.classList.add('show');
    }
    function hide() {
      active = -1;
      tip.classList.remove('show');
      if (geo) { geo.cross.setAttribute('x1', -10); geo.cross.setAttribute('x2', -10); geo.dot.classList.remove('on'); }
    }

    draw();
    let w = host.clientWidth;
    new ResizeObserver(() => { if (host.clientWidth !== w) { w = host.clientWidth; draw(); } }).observe(host);
  }

  function donut(host) {
    const data = JSON.parse(document.getElementById(host.dataset.source).textContent);
    const total = data.reduce((s, d) => s + d.value, 0);
    const legend = document.getElementById(host.dataset.legend);
    const R = 70, C = 2 * Math.PI * R, GAP = total > 0 && data.filter(d => d.value).length > 1 ? 2 : 0;
    const svg = el('svg', { viewBox: '0 0 180 180', 'aria-hidden': 'true' });
    el('circle', { cx: 90, cy: 90, r: R, fill: 'none', stroke: '#EEF3FB', 'stroke-width': 22 }, svg);
    let offset = 0;
    data.forEach(d => {
      if (!d.value) return;
      const len = (d.value / total) * C;
      const seg = el('circle', { class: 'seg', cx: 90, cy: 90, r: R, stroke: d.color,
        'stroke-dasharray': `${Math.max(len - GAP, 0.5)} ${C}`, 'stroke-dashoffset': -offset, 'data-key': d.key }, svg);
      seg.addEventListener('click', () => { location.href = d.url; });
      seg.addEventListener('pointerenter', () => sync(d.key, true));
      seg.addEventListener('pointerleave', () => sync(d.key, false));
      offset += len;
    });
    host.prepend(svg);
    function sync(key, on) {
      svg.querySelectorAll('.seg').forEach(s => s.classList.toggle('hot', on && s.dataset.key === key));
      if (legend) legend.querySelectorAll('a').forEach(a => a.classList.toggle('hot', on && a.dataset.key === key));
    }
    if (legend) legend.querySelectorAll('a').forEach(a => {
      a.addEventListener('pointerenter', () => sync(a.dataset.key, true));
      a.addEventListener('pointerleave', () => sync(a.dataset.key, false));
      a.addEventListener('focus', () => sync(a.dataset.key, true));
      a.addEventListener('blur', () => sync(a.dataset.key, false));
    });
  }

  function init() {
    document.querySelectorAll('[data-chart="line"]').forEach(lineChart);
    document.querySelectorAll('[data-chart="donut"]').forEach(donut);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
