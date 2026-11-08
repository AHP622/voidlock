/* SVG charts as strings. Same design as the computer's report: a few light gridlines, one slice per main subject (the small ones
 * merged into "other"), the day's total above each column, one dashed goal line, a soft band on exam days. */
(function (root) {
  'use strict';
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function niceTicks(max, n) {
    max = Math.max(max, 1e-9); var raw = max / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
    var step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag, out = [];
    for (var v = 0; v <= max + step * 0.999; v += step) { out.push(+v.toFixed(6)); if (out.length > 8) break; }
    if (out[out.length - 1] < max) out.push(+(out[out.length - 1] + step).toFixed(6));
    return out;
  }
  var OTHER = '#8d99ab';

  function groupParts(days, keep) {
    var tot = {}, color = {};
    days.forEach(function (d) { d.parts.forEach(function (p) { tot[p.name] = (tot[p.name] || 0) + p.sec; if (!color[p.name]) color[p.name] = p.color; }); });
    var ranked = Object.keys(tot).sort(function (a, b) { return tot[b] - tot[a]; });
    var top = ranked.length > keep + 1 ? ranked.slice(0, keep) : ranked, rank = {}; top.forEach(function (n, i) { rank[n] = i; });
    days.forEach(function (d) {
      var parts = [], other = 0;
      d.parts.forEach(function (p) { if (p.name in rank) parts.push(p); else other += p.sec; });
      parts.sort(function (a, b) { return rank[a.name] - rank[b.name]; });
      if (other) parts.push({ name: null, color: OTHER, sec: other });
      d.parts = parts;
    });
    return { legend: top.map(function (n) { return { name: n, color: color[n] }; }), hasOther: ranked.length > keep + 1 };
  }

  /* days: [{dk, label, month(optional), parts:[{name,color,sec}], sec, exam}] oldest first */
  function studyChart(o) {
    var T = o.t, fa = o.fa, days = JSON.parse(JSON.stringify(o.days)), W = o.width || 340, H = 240;
    var g = groupParts(days, 5);
    var ml = 34, mr = 8, mt = 28, mb = 26,                 // always left to right (also in Persian): oldest day at the left, axis on the left
         pw = W - ml - mr, ph = H - mt - mb, base = mt + ph;
    var goal = o.goalSec || 0, maxSec = Math.max(3600, goal, Math.max.apply(null, days.map(function (d) { return d.sec; })));
    var ticks = niceTicks(maxSec * 1.06 / 3600, 4), ymax = ticks[ticks.length - 1] * 3600, n = days.length, slot = pw / n;
    var bw = Math.max(4, Math.min(30, slot * 0.64)), s = '';
    function cx(i) { return ml + (i + 0.5) * slot; }
    var axisX = ml - 6, anchor = 'end';
    ticks.forEach(function (tv) {
      var y = base - ph * (tv * 3600 / ymax);
      s += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + y + '" y2="' + y + '" style="stroke:var(--border-hi)" stroke-width="' + (tv ? 1 : 1.4) + '"' + (tv ? ' stroke-dasharray="2 4"' : '') + ' opacity="' + (tv ? 0.7 : 1) + '"/>';
      s += '<text x="' + axisX + '" y="' + (y + 3.5) + '" font-size="10.5" text-anchor="' + anchor + '" style="fill:var(--text3)">' + I18n.digits(+tv.toFixed(2)) + '</text>';
    });
    s += '<text x="' + axisX + '" y="' + (mt - 14) + '" font-size="10" text-anchor="' + anchor + '" style="fill:var(--text3)">' + esc(T('hours_axis')) + '</text>';
    var step = 1; while (slot * step < 30) step++;
    var showTot = slot >= 19;
    days.forEach(function (d, i) {
      var x0 = cx(i) - bw / 2;
      if (d.exam) {
        s += '<rect x="' + (cx(i) - slot / 2 + 1) + '" y="' + (mt - 4) + '" width="' + (slot - 2) + '" height="' + (ph + 4) + '" rx="4" style="fill:var(--amber)" opacity="0.16"/>';
        s += '<polygon points="' + (cx(i) - 5) + ',' + (mt - 11) + ' ' + (cx(i) + 5) + ',' + (mt - 11) + ' ' + cx(i) + ',' + (mt - 3) + '" style="fill:var(--amber)"/>';
      }
      if (d.sec > 0) {
        var used = 0;
        d.parts.forEach(function (p, k) {
          var hh = Math.max(ph * p.sec / ymax, 0.8), last = k === d.parts.length - 1;
          s += '<rect x="' + x0 + '" y="' + (base - used - hh) + '" width="' + bw + '" height="' + hh + '" rx="' + (last ? 3 : 0) + '" fill="' + p.color + '" style="stroke:var(--panel)" stroke-width="1"><title>' + esc(d.tip || '') + ' · ' + esc(p.name || T('other_subjects')) + ': ' + esc(I18n.dur(p.sec)) + '</title></rect>';
          used += hh;
        });
        if (showTot) s += '<text x="' + cx(i) + '" y="' + (base - used - 6) + '" font-size="9.5" text-anchor="middle" style="fill:var(--text2)">' + I18n.digits(+(d.sec / 3600).toFixed(1)) + '</text>';
      } else {
        s += '<rect x="' + x0 + '" y="' + (base - 2) + '" width="' + bw + '" height="2" rx="1" style="fill:var(--border-hi)"/>';
      }
      if (i % step === 0 || d.month) s += '<text x="' + cx(i) + '" y="' + (H - 8) + '" font-size="10" text-anchor="middle" style="fill:var(--text3)">' + esc(d.month ? d.month + ' ' + d.label : d.label) + '</text>';
    });
    if (goal) {
      var gy = base - ph * goal / ymax;
      s += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + gy + '" y2="' + gy + '" style="stroke:var(--violet)" stroke-width="1.5" stroke-dasharray="6 4"/>';
    }
    var legend = g.legend.slice(); if (g.hasOther) legend.push({ name: T('other_subjects'), color: OTHER });
    if (goal) legend.push({ name: T('daily_goal_line') + ' ' + I18n.digits(+(goal / 3600).toFixed(1)) + ' ' + T('hours_axis'), color: 'var(--violet)', dashed: true });
    return { svg: '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" role="img">' + s + '</svg>', legend: legend };
  }

  /* series: [{name,color,values:[number|null]}], labels: [string]; invert = lower is better (drawn upwards) */
  function lineChart(o) {
    var T = o.t, fa = o.fa, W = o.width || 340, H = o.height || 230, ml = 40, mr = 8, mt = 22, mb = 34, pw = W - ml - mr, ph = H - mt - mb;
    var vals = []; o.series.forEach(function (s) { s.values.forEach(function (v) { if (v !== null && v !== undefined) vals.push(v); }); });
    if (!vals.length) return { svg: '', legend: [] };
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.18 || Math.max(1, Math.abs(hi) * 0.1);
    lo = o.zero ? 0 : lo - pad; hi = hi + pad; if (o.min !== undefined) lo = Math.max(o.min, lo);
    var ticks = niceTicks(hi - lo, 4).map(function (v) { return lo + v; }), top = ticks[ticks.length - 1]; if (top < hi) top = hi;
    function y(v) { var f = (v - lo) / (top - lo || 1); return o.invert ? mt + ph * f : mt + ph * (1 - f); }
    var n = o.labels.length, step = n > 1 ? pw / (n - 1) : 0;
    function x(i) { var xx = n > 1 ? i * step : pw / 2; return ml + xx; }
    var s = '', axisX = ml - 6, anchor = 'end';
    ticks.forEach(function (tv) {
      var yy = y(tv); if (yy < mt - 1 || yy > mt + ph + 1) return;
      s += '<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + yy + '" y2="' + yy + '" style="stroke:var(--border-hi)" stroke-dasharray="2 4" opacity=".7"/>';
      s += '<text x="' + axisX + '" y="' + (yy + 3.5) + '" font-size="10" text-anchor="' + anchor + '" style="fill:var(--text3)">' + I18n.num(tv) + '</text>';
    });
    o.labels.forEach(function (lb, i) {
      var skip = n > 7 ? Math.ceil(n / 7) : 1; if (i % skip && i !== n - 1) return;
      s += '<text x="' + x(i) + '" y="' + (H - 12) + '" font-size="10" text-anchor="middle" style="fill:var(--text3)">' + esc(lb.length > (n <= 3 ? 16 : 10) ? lb.slice(0, n <= 3 ? 15 : 9) + '…' : lb) + '</text>';
    });
    o.series.forEach(function (se) {
      var pts = [], seg = [];
      se.values.forEach(function (v, i) { if (v === null || v === undefined) { if (seg.length) pts.push(seg); seg = []; } else seg.push([x(i), y(v), v]); });
      if (seg.length) pts.push(seg);
      pts.forEach(function (sg) {
        if (sg.length > 1) s += '<polyline points="' + sg.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ') + '" fill="none" stroke="' + se.color + '" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>';
        sg.forEach(function (p) {
          s += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="4" fill="' + se.color + '" style="stroke:var(--panel)" stroke-width="1.5"/>';
          if (o.series.length === 1 && n <= 8) s += '<text x="' + p[0].toFixed(1) + '" y="' + (p[1] - 9).toFixed(1) + '" font-size="10" text-anchor="middle" style="fill:var(--text2)">' + I18n.num(p[2], o.dec || 0) + '</text>';
        });
      });
    });
    return { svg: '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" role="img">' + s + '</svg>', legend: o.series.length > 1 ? o.series.map(function (s2) { return { name: s2.name, color: s2.color }; }) : [] };
  }

  function ring(frac, size, text, sub) {
    var r = size / 2 - 11, c = 2 * Math.PI * r, f = Math.max(0, Math.min(1, frac)), id = 'rg' + Math.floor(Math.random() * 1e6);
    return '<svg class="ring" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '"><defs><linearGradient id="' + id + '" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style="stop-color:var(--accent)"/><stop offset="1" style="stop-color:var(--accent2)"/></linearGradient></defs>' +
      '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" style="stroke:var(--panel2)" stroke-width="12"/>' +
      (f > 0.004 ? '<circle cx="' + size / 2 + '" cy="' + size / 2 + '" r="' + r + '" fill="none" stroke="url(#' + id + ')" stroke-width="12" stroke-linecap="round" stroke-dasharray="' + (c * f).toFixed(1) + ' ' + c.toFixed(1) + '" transform="rotate(-90 ' + size / 2 + ' ' + size / 2 + ')"/>' : '') +
      '<text x="50%" y="' + (sub ? '47%' : '53%') + '" text-anchor="middle" font-size="22" font-weight="700" style="fill:var(--text)">' + esc(text) + '</text>' +
      (sub ? '<text x="50%" y="63%" text-anchor="middle" font-size="11.5" style="fill:var(--text3)">' + esc(sub) + '</text>' : '') + '</svg>';
  }
  var Charts = { studyChart: studyChart, lineChart: lineChart, ring: ring, niceTicks: niceTicks, esc: esc };
  if (typeof module !== 'undefined' && module.exports) module.exports = Charts; else root.Charts = Charts;
})(typeof window !== 'undefined' ? window : globalThis);
