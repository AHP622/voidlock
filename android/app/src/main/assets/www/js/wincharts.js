/* The computer's report charts, ported 1:1 from voidlock/charts.py (Scene -> SVG, study chart, weekday chart, line chart), so the report made
 * on the phone looks exactly like the one made on the computer. Keep it in step with charts.py (android/tests/report_parity_test.py compares them).
 *
 * Data shape (R, like report.collect in Python):
 *   R.lang, R.daily_rows, R.goal_sec, R.week_start, R.subjects:[{name,color,ghost,sec}],
 *   R.days:[{wd (Mon=0..Sun=6), y, m, d, sec, parts:[[name,sec]], exam:[names]}], R.monthly:[{key:[y,m], sec}], R.H: helpers (see report.js) */
(function (root) {
  'use strict';
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  function jalali() { return root.Jalali || require('./jalali.js'); }
  var FA_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  var FA_DAYS = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه'];          // Mon..Sun
  var EN_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  var EN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var LIGHT = { text: '#334155', muted: '#64748b', grid: '#e2e8f0', axis: '#94a3b8', goal: '#a855f7', avg: '#0e7490', ma: '#6d28d9', accent: '#0e7490',
                accent2: '#7c9cd6', exam: '#d97706', good: '#16a34a', bad: '#dc2626', area: '#0e749022', panel: '#ffffff' };

  function pyRound(x) {                                    // Python's round(): halves go to the even number
    var f = Math.floor(x), d = x - f;
    if (d < 0.5) return f;
    if (d > 0.5) return f + 1;
    return f % 2 === 0 ? f : f + 1;
  }
  function digits(s, fa) { s = String(s); return fa ? s.replace(/[0-9]/g, function (c) { return FA[+c]; }) : s; }
  function fmtInt(n, fa) {
    var v = pyRound(n), neg = v < 0, s = String(Math.abs(v)).replace(/\B(?=(\d{3})+(?!\d))/g, fa ? '\u066c' : ',');
    return digits((neg ? '-' : '') + s, fa);
  }
  function g(x) { return String(+Number(x).toPrecision(6)); }          // Python's {:g}
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;'); }
  function f1(x) { return Number(x).toFixed(1); }

  function niceTicks(lo, hi, n) {
    n = n || 5;
    if (hi <= lo) hi = lo + 1;
    var raw = (hi - lo) / Math.max(1, n - 1), mag = Math.pow(10, Math.floor(Math.log10(raw))), step = null, ms = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < ms.length; i++) if (ms[i] * mag >= raw) { step = ms[i] * mag; break; }
    var start = Math.floor(lo / step) * step, ticks = [], v = start;
    while (v < hi + step * 0.999) { ticks.push(+v.toFixed(6)); v += step; if (ticks.length > 12) break; }
    return ticks;
  }

  function Scene(w, h) { this.w = w; this.h = h; this.items = []; }
  Scene.prototype.rect = function (x, y, w, h, fill, rx, title, stroke) { this.items.push(['rect', x, y, w, h, fill, rx || 0, title || null, stroke || null]); };
  Scene.prototype.line = function (x1, y1, x2, y2, stroke, width, dash) { this.items.push(['line', x1, y1, x2, y2, stroke, width === undefined ? 1.0 : width, dash || null]); };
  Scene.prototype.poly = function (pts, stroke, width, dash) { this.items.push(['poly', pts.slice(), stroke, width === undefined ? 2.0 : width, dash || null]); };
  Scene.prototype.polygon = function (pts, fill, title) { this.items.push(['polygon', pts.slice(), fill, title || null]); };
  Scene.prototype.circle = function (cx, cy, r, fill, stroke, title) { this.items.push(['circle', cx, cy, r, fill, stroke || null, title || null]); };
  Scene.prototype.text = function (x, y, s, size, fill, anchor, bold) { this.items.push(['text', x, y, String(s), size === undefined ? 11 : size, fill || '#334155', anchor || 'middle', !!bold]); };
  Scene.prototype.add = function (other, dx, dy) {
    dx = dx || 0; dy = dy || 0;
    other.items.forEach(function (it) {
      var k = it[0], c = it.slice();
      if (k === 'rect' || k === 'circle' || k === 'text') { c[1] += dx; c[2] += dy; }
      else if (k === 'line') { c[1] += dx; c[2] += dy; c[3] += dx; c[4] += dy; }
      else if (k === 'poly' || k === 'polygon') c[1] = it[1].map(function (p) { return [p[0] + dx, p[1] + dy]; });
      this.items.push(c);
    }, this);
  };
  Scene.prototype.toSvg = function (label) {
    var o = ['<svg viewBox="0 0 ' + this.w.toFixed(0) + ' ' + this.h.toFixed(0) + '" direction="ltr" style="direction:ltr" role="img" aria-label="' + esc(label || '') + '">'];
    this.items.forEach(function (it) {
      var k = it[0];
      if (k === 'rect') {
        var st = it[8] ? ' stroke="' + it[8] + '"' : '', body = it[7] ? '<title>' + esc(it[7]) + '</title>' : '';
        o.push('<rect x="' + f1(it[1]) + '" y="' + f1(it[2]) + '" width="' + f1(Math.max(it[3], 0)) + '" height="' + f1(Math.max(it[4], 0)) + '" rx="' + it[6] + '" fill="' + it[5] + '"' + st + '>' + body + '</rect>');
      } else if (k === 'line') {
        o.push('<line x1="' + f1(it[1]) + '" y1="' + f1(it[2]) + '" x2="' + f1(it[3]) + '" y2="' + f1(it[4]) + '" stroke="' + it[5] + '" stroke-width="' + it[6] + '"' + (it[7] ? ' stroke-dasharray="' + it[7] + '"' : '') + '/>');
      } else if (k === 'poly') {
        o.push('<polyline fill="none" stroke="' + it[2] + '" stroke-width="' + it[3] + '" stroke-linejoin="round" stroke-linecap="round"' + (it[4] ? ' stroke-dasharray="' + it[4] + '"' : '') +
               ' points="' + it[1].map(function (p) { return f1(p[0]) + ',' + f1(p[1]); }).join(' ') + '"/>');
      } else if (k === 'polygon') {
        o.push('<polygon fill="' + it[2] + '" points="' + it[1].map(function (p) { return f1(p[0]) + ',' + f1(p[1]); }).join(' ') + '">' + (it[3] ? '<title>' + esc(it[3]) + '</title>' : '') + '</polygon>');
      } else if (k === 'circle') {
        o.push('<circle cx="' + f1(it[1]) + '" cy="' + f1(it[2]) + '" r="' + it[3] + '" fill="' + it[4] + '"' + (it[5] ? ' stroke="' + it[5] + '" stroke-width="2"' : '') + '>' + (it[6] ? '<title>' + esc(it[6]) + '</title>' : '') + '</circle>');
      } else if (k === 'text') {
        o.push('<text x="' + f1(it[1]) + '" y="' + f1(it[2]) + '" font-size="' + it[4] + '" fill="' + it[5] + '" text-anchor="' + it[6] + '"' + (it[7] ? ' font-weight="700"' : '') + '>' + esc(it[3]) + '</text>');
      }
    });
    o.push('</svg>');
    return o.join('');
  };

  function legend(sc, entries, y, w, rtl, pal, size) {
    size = size || 11;
    var x = rtl ? w - 8 : 8, rowH = 18, curY = y;
    entries.forEach(function (e) {
      var kind = e[0], color = e[1], text = e[2], tw = text.length * size * 0.7 + 38;
      if ((rtl && x - tw < 8) || (!rtl && x + tw > w - 8)) { x = rtl ? w - 8 : 8; curY += rowH; }
      var s = rtl ? -1 : 1, ix = x + (rtl ? -6 : 6);
      if (kind === 'dot') sc.circle(ix, curY + 7, 5, color);
      else if (kind === 'line' || kind === 'dash') sc.line(ix - 8, curY + 7, ix + 8, curY + 7, color, 2.4, kind === 'dash' ? '4 3' : null);
      else if (kind === 'tri') sc.polygon([[ix - 5, curY + 11], [ix + 5, curY + 11], [ix, curY + 2]], color);
      sc.text(ix + (rtl ? -14 : 14), curY + 11, text, size, pal.text, rtl ? 'end' : 'start');
      x += s * tw;
    });
    return curY - y + rowH;
  }

  function titled(scene, title, fa, pal, size) {
    var head = 28, sc = new Scene(scene.w, scene.h + head);
    sc.text(fa ? scene.w - 4 : 4, 18, title, size || 14, '#0e5a72', fa ? 'end' : 'start', true);
    sc.add(scene, 0, head);
    return sc;
  }

  // ---------------------------------------------------------------- study charts
  function bars(R) {
    var H = R.H, fa = R.lang === 'fa', colors = {}, order = {}, out = [];
    R.subjects.forEach(function (r, i) { var k = r.name.trim().toLowerCase(); colors[k] = r.color; order[k] = i; });
    function part(n, v) { return [n, colors[n.trim().toLowerCase()] || '#8A8F9C', v]; }
    function ord(p) { var k = p[0].trim().toLowerCase(); return k in order ? order[k] : 99; }
    if (R.daily_rows) {
      R.days.forEach(function (x) {
        var jd = fa ? jalali().toJalali(x.y, x.m, x.d) : { jy: x.y, jm: x.m, jd: x.d };
        var parts = x.parts.map(function (p) { return part(p[0], p[1]); }).sort(function (a, b) { return ord(a) - ord(b); });
        var first = jd.jd === 1;
        out.push({ label: digits(jd.jd, fa) + ((fa && first) ? ' ' + FA_MONTHS[jd.jm - 1] : ''), sec: x.sec, parts: parts, exam: x.exam, tip: H.fmtDate(x, true) });
      });
      return ['day', out];
    }
    var by = {};
    R.days.forEach(function (x) {
      var k = H.monthKey(x).join('-'), m = by[k] = by[k] || {};
      x.parts.forEach(function (p) { m[p[0]] = (m[p[0]] || 0) + p[1]; });
    });
    R.monthly.forEach(function (m) {
      var parts = Object.keys(by[m.key.join('-')] || {}).map(function (n) { return part(n, by[m.key.join('-')][n]); }).sort(function (a, b) { return ord(a) - ord(b); });
      out.push({ label: fa ? FA_MONTHS[m.key[1] - 1] : EN_MONTHS[m.key[1] - 1], sec: m.sec, parts: parts, exam: [], tip: H.monthLabel(m.key) });
    });
    return ['month', out];
  }

  function groupParts(bs, R, deleted, keep) {
    keep = keep || 5;
    var tot = {}, color = {};
    bs.forEach(function (b) { b.parts.forEach(function (p) { tot[p[0]] = (tot[p[0]] || 0) + p[2]; }); });
    var ranked = Object.keys(tot).sort(function (a, b) { return tot[b] - tot[a]; });
    var top = ranked.length > keep + 1 ? ranked.slice(0, keep) : ranked, rank = {};
    top.forEach(function (n, i) { rank[n] = i; });
    bs.forEach(function (b) { b.parts.forEach(function (p) { if (!(p[0] in color)) color[p[0]] = p[1]; }); });
    bs.forEach(function (b) {
      var parts = [], other = 0;
      b.parts.forEach(function (p) { if (p[0] in rank) parts.push(p); else other += p[2]; });
      parts.sort(function (a, b2) { return rank[a[0]] - rank[b2[0]]; });
      if (other) parts.push([null, '#b6bfcc', other]);
      b.parts = parts;
    });
    var ghosts = {}; R.subjects.forEach(function (r) { if (r.ghost) ghosts[r.name] = 1; });
    return { legend: top.map(function (n) { return [color[n], n + (ghosts[n] ? ' (' + deleted + ')' : '')]; }), hasOther: ranked.length > keep + 1 };
  }

  function studyChart(R, pal, w) {
    pal = pal || LIGHT; w = w || 760;
    var H = R.H, t = H.STR, fa = R.lang === 'fa', mb_ = bars(R), mode = mb_[0], bs = mb_[1];
    if (!bs.length) return new Scene(w, 10);
    var gp = groupParts(bs, R, t.deleted);
    var ml = 40, mr = 14, mt = 30, mb = 30, hPlot = 270, pw = w - ml - mr, ph = hPlot - mt - mb;
    var goal = mode === 'day' ? R.goal_sec : 0;
    var ymaxSec = Math.max(Math.max.apply(null, bs.map(function (b) { return b.sec; })), goal || 0, 3600);
    var ticks = niceTicks(0, ymaxSec * 1.06 / 3600, 4), ymax = ticks[ticks.length - 1] * 3600, n = bs.length, slot = pw / n;
    var bw = Math.max(4.0, Math.min(mode === 'day' ? 30.0 : 64.0, slot * 0.64)), sc = new Scene(w, hPlot), axisX = ml - 8, base = mt + ph;
    ticks.forEach(function (tv) {
      var y = base - ph * (tv * 3600 / ymax);
      sc.line(ml, y, w - mr, y, pal.grid, tv ? 1 : 1.4, tv === 0 ? null : '2 4');
      sc.text(axisX, y + 3.5, digits(g(tv), fa), 10.5, pal.muted, 'end');
    });
    sc.text(axisX, mt - 14, t.h, 10, pal.muted, 'end');
    function cx(i) { return ml + (i + 0.5) * slot; }
    var step = 1; while (slot * step < (mode === 'day' ? 30 : 40)) step++;
    var showTot = slot >= 19 || mode === 'month';
    bs.forEach(function (b, i) {
      var x0 = cx(i) - bw / 2;
      if (b.exam.length) {
        sc.rect(cx(i) - slot / 2 + 1, mt - 4, slot - 2, ph + 4, pal.exam + '1f', 4);
        sc.polygon([[cx(i) - 5, mt - 11], [cx(i) + 5, mt - 11], [cx(i), mt - 3]], pal.exam, t.exam + ': ' + b.exam.join(', '));
      }
      if (b.sec > 0) {
        var tip = b.tip + ' · ' + H.fmtDur(b.sec), used = 0.0, parts = b.parts.length ? b.parts : [[null, pal.accent, b.sec]];
        parts.forEach(function (p, k) {
          var hh = Math.max(ph * p[2] / ymax, 0.8), label = p[0] !== null ? p[0] : t.other_subjects;
          sc.rect(x0, base - used - hh, bw, hh, p[1], k === parts.length - 1 ? 3 : 0, tip + '\n' + label + ': ' + H.fmtDur(p[2]), '#ffffff');
          used += hh;
        });
        if (showTot) sc.text(cx(i), base - used - 6, digits(f1(b.sec / 3600).replace('.0', ''), fa), 9.5, pal.text);
      } else sc.rect(x0, base - 2, bw, 2, pal.grid, 1);
      if (i % step === 0 || b.label.indexOf(' ') >= 0) sc.text(cx(i), hPlot - 10, b.label, 10, pal.muted);
    });
    if (goal) {
      var gy = base - ph * goal / ymax;
      sc.line(ml, gy, w - mr, gy, pal.goal, 1.5, '6 4');
      sc.text(w - mr - 2, gy - 5, t.goal + ' ' + digits(g(goal / 3600), fa) + ' ' + t.h, 10, pal.goal, 'end', true);
    }
    var ent = gp.legend.map(function (e) { return ['dot', e[0], e[1]]; });
    if (gp.hasOther) ent.push(['dot', '#b6bfcc', t.other_subjects]);
    if (bs.some(function (b) { return b.exam.length; })) ent.push(['tri', pal.exam, t.legend_exam]);
    var used2 = legend(sc, ent, hPlot + 2, w, false, pal);
    sc.h = hPlot + 2 + used2;
    return sc;
  }

  function weekdayChart(R, pal, w, h) {
    pal = pal || LIGHT; w = w || 380; h = h || 200;
    var H = R.H, fa = R.lang === 'fa', ws = R.week_start === undefined ? 5 : R.week_start, order = [], tot = [0, 0, 0, 0, 0, 0, 0], cnt = [0, 0, 0, 0, 0, 0, 0], k;
    for (k = 0; k < 7; k++) order.push((ws + k) % 7);
    R.days.forEach(function (x) { tot[x.wd] += x.sec; cnt[x.wd] += 1; });
    var avg = order.map(function (o) { return cnt[o] ? tot[o] / cnt[o] : 0; });
    var sc = new Scene(w, h), mt = 22, mb = 28, ph = h - mt - mb, mx = Math.max.apply(null, avg.concat([1])), slot = (w - 16) / 7, bw = Math.min(34, slot * 0.7), best = -1;
    if (avg.some(function (v) { return v; })) avg.forEach(function (v, i) { if (best < 0 || v > avg[best]) best = i; });
    avg.forEach(function (v, i) {
      var cx = 8 + (i + 0.5) * slot, hh = ph * v / mx;
      sc.rect(cx - bw / 2, mt + ph - hh, bw, hh, i === best ? pal.accent : pal.accent2, 3, (fa ? FA_DAYS[order[i]] : EN_DAYS[order[i]]) + ': ' + H.fmtDur(v));
      if (v > 0) sc.text(cx, mt + ph - hh - 5, digits(f1(v / 3600), fa), 10, pal.text);
      sc.text(cx, h - 9, fa ? FA_DAYS[order[i]] : EN_DAYS[order[i]].slice(0, 3), 10, pal.muted);
    });
    sc.line(8, mt + ph, w - 8, mt + ph, pal.axis, 1);
    return sc;
  }

  function lineChart(spec, pal, w, h, fa) {
    pal = pal || LIGHT; w = w || 760; h = h || 260;
    var labels = spec.labels, series = spec.series, invert = !!spec.invert, vals = [];
    series.forEach(function (s) { s.values.forEach(function (v) { if (v !== null && v !== undefined) vals.push(v); }); });
    var ml = 58, mr = 30, mt = 24, mb = 34, sc = new Scene(w, h);
    if (!vals.length) return sc;
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals), pad = (hi - lo) * 0.12 || Math.max(1.0, Math.abs(hi) * 0.05);
    var ticks = niceTicks(lo - pad, hi + pad, 5), ylo = ticks[0], yhi = ticks[ticks.length - 1], pw = w - ml - mr, ph = h - mt - mb, n = labels.length, axisX = ml - 6;
    function py(v) { var f = (v - ylo) / ((yhi - ylo) || 1); return mt + (invert ? ph * f : ph * (1 - f)); }
    function px(i) { return n === 1 ? ml + pw / 2 : ml + i / (n - 1) * pw; }
    var fmt = spec.fmt || function (v) { return fmtInt(v, fa); };
    ticks.forEach(function (tv) { sc.line(ml, py(tv), w - mr, py(tv), pal.grid, 1); sc.text(axisX, py(tv) + 3.5, fmt(tv), 10.5, pal.muted, 'end'); });
    if (spec.unit) sc.text(axisX, mt - 8, spec.unit, 10.5, pal.muted, 'end');
    var step = n <= 7 ? 1 : Math.ceil(n / 7);
    labels.forEach(function (lab, i) { if (i % step === 0) sc.text(px(i), h - 12, lab, 10, pal.muted); });
    var single = series.length === 1;
    series.forEach(function (s) {
      var pts = [], real = [];
      s.values.forEach(function (v, i) { if (v !== null && v !== undefined) { pts.push([px(i), py(v)]); real.push([i, v]); } });
      if (!pts.length) return;
      if (single && pts.length > 1 && !spec.no_area) {
        var base = !invert ? py(ylo) : py(yhi);
        sc.polygon([[pts[0][0], base]].concat(pts).concat([[pts[pts.length - 1][0], base]]), pal.area);
      }
      if (pts.length > 1) sc.poly(pts, s.color, s.width || 2.6);
      if (single && spec.trend !== false && real.length >= 3) {
        var xs = real.map(function (p) { return p[0]; }), ys = real.map(function (p) { return p[1]; });
        var mx_ = xs.reduce(function (a, b) { return a + b; }, 0) / xs.length, my_ = ys.reduce(function (a, b) { return a + b; }, 0) / ys.length;
        var den = xs.reduce(function (a, x) { return a + (x - mx_) * (x - mx_); }, 0) || 1, sl = 0;
        xs.forEach(function (x, i) { sl += (x - mx_) * (ys[i] - my_); });
        sl /= den;
        sc.poly([[px(xs[0]), py(my_ + sl * (xs[0] - mx_))], [px(xs[xs.length - 1]), py(my_ + sl * (xs[xs.length - 1] - mx_))]], pal.goal, 1.6, '6 4');
      }
      var bestI = null;
      if (single && real.length) {
        var b = real[0];
        real.forEach(function (p) { if (invert ? p[1] < b[1] : p[1] > b[1]) b = p; });
        bestI = b[0];
      }
      s.values.forEach(function (v, i) {
        if (v === null || v === undefined) return;
        var tip = spec.tips ? spec.tips[i] : labels[i] + ': ' + fmt(v);
        sc.circle(px(i), py(v), i === bestI ? 5.5 : 4, s.color, '#ffffff', tip);
        if (single && s.value_labels !== false && n <= 14) sc.text(px(i), py(v) - 9, fmt(v), 10, pal.text, 'middle', i === bestI);
      });
    });
    if (!single) {
      var used = legend(sc, series.map(function (s) { return ['line', s.color, s.name]; }), h + 2, w, false, pal);
      sc.h = h + 2 + used;
    }
    return sc;
  }

  var WinCharts = { LIGHT: LIGHT, Scene: Scene, digits: digits, fmtInt: fmtInt, niceTicks: niceTicks, esc: esc, titled: titled, legend: legend, pyRound: pyRound,
                    studyChart: studyChart, weekdayChart: weekdayChart, lineChart: lineChart, FA_MONTHS: FA_MONTHS, FA_DAYS: FA_DAYS, EN_DAYS: EN_DAYS, EN_MONTHS: EN_MONTHS };
  if (typeof module !== 'undefined' && module.exports) module.exports = WinCharts; else root.WinCharts = WinCharts;
})(typeof window !== 'undefined' ? window : globalThis);
