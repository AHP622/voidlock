/* The study report. A port of voidlock/report.py (collect, render_html, render_csv), so the report made on the phone has the same sections,
 * numbers, charts and look as the one made on the computer. Texts come from report_str.js (generated from report.py), charts from wincharts.js
 * (a port of charts.py). What counts as "study" is the Study Timer's own definition: subject timer + manual entries. Focus sessions are listed
 * in their own table and are NOT added to the total. (The computer's weekly class timetable is not on the phone, so that section is absent.) */
(function (root) {
  'use strict';
  var node = typeof module !== 'undefined' && module.exports;
  var WC = root.WinCharts || (node ? require('./wincharts.js') : null);
  var STRS = node ? require('./report_str.js') : null;
  var STR = root.REPORT_STR || STRS.STR, CSS = root.REPORT_CSS || STRS.CSS;
  var J = root.Jalali || (node ? require('./jalali.js') : null);
  var CoreRef = root.Core || (node ? require('./core.js') : null);
  var VERSION = function () { return (root.VOIDLOCK_CONFIG || {}).version || (root.Native && root.Native.appVersion && root.Native.appVersion()) || ''; };
  var MAX_DAILY_ROWS = 62, STREAK_MIN_SEC = 600;

  // ---------------------------------------------------------------- small helpers (report.py)
  function esc(s) { return WC.esc(s); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function dinfo(dk) {                                       // a day as {dk, y, m, d, wd}: wd 0 = Monday ... 6 = Sunday (Python's weekday())
    var p = dk.split('-'), y = +p[0], m = +p[1], d = +p[2], wd = (new Date(y, m - 1, d, 12).getDay() + 6) % 7;
    return { dk: dk, y: y, m: m, d: d, wd: wd };
  }
  function dkeyOf(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
  function addDk(dk, n) { var x = dinfo(dk); return dkeyOf(new Date(x.y, x.m - 1, x.d + n, 12)); }
  function jal(x) { return J.toJalali(x.y, x.m, x.d); }

  function helpers(lang) {
    var fa = lang === 'fa', t = STR[lang];
    function dg(s) { return WC.digits(s, fa); }
    return {
      STR: t, lang: lang, fa: fa, dg: dg,
      fmtDur: function (sec) {
        sec = Math.max(0, Math.trunc(sec));
        var mm = Math.floor(sec / 60), h = Math.floor(mm / 60), m = mm % 60;
        if (fa) {
          if (h && m) return dg(h + ' ' + t.h + ' ' + t.and + ' ' + m + ' ' + t.m);
          if (h) return dg(h + ' ' + t.h);
          return dg(m + ' ' + t.m);
        }
        return h ? h + 'h ' + pad2(m) + 'm' : m + ' min';
      },
      fmtDate: function (x, weekday, year) {
        if (year === undefined) year = true;
        if (fa) {
          var j = jal(x), s = j.jd + ' ' + WC.FA_MONTHS[j.jm - 1] + (year ? ' ' + j.jy : '');
          if (weekday) s = WC.FA_DAYS[x.wd] + ' ' + s;
          return dg(s);
        }
        var s2 = pad2(x.d) + ' ' + WC.EN_MONTHS[x.m - 1] + (year ? ' ' + x.y : '');
        return weekday ? WC.EN_DAYS[x.wd].slice(0, 3) + ' ' + s2 : s2;
      },
      jdateNumeric: function (x) { var j = jal(x); return ('000' + j.jy).slice(-4) + '-' + pad2(j.jm) + '-' + pad2(j.jd); },
      monthKey: function (x) { if (fa) { var j = jal(x); return [j.jy, j.jm]; } return [x.y, x.m]; },
      monthLabel: function (key) { return fa ? dg(WC.FA_MONTHS[key[1] - 1] + ' ' + key[0]) : WC.EN_MONTHS[key[1] - 1] + ' ' + key[0]; },
      status: function (st) { return t['st_' + st] || st || t.none; }
    };
  }

  // ---------------------------------------------------------------- data (report.collect)
  function dayEntrySec(db, dk, sid) {
    var tot = 0;
    db.entries.forEach(function (e) { if (e.date === dk && (sid === undefined || e.subject === sid)) tot += e.sec | 0; });
    return tot;
  }
  function runningFor(db, dk) {
    var a = db.active;
    return (a && dkeyOf(new Date(a.started * 1000)) === dk) ? Math.floor(CoreRef.elapsed(db)) : 0;
  }
  function collect(db, fromDk, toDk, opts) {
    opts = opts || {};
    var lang = opts.lang || (root.I18n ? root.I18n.lang : 'en'), H = helpers(lang), today = dkeyOf(new Date()), effEnd = toDk < today ? toDk : today;
    var goalMin = opts.goalMin !== undefined && opts.goalMin !== null ? opts.goalMin : (db.settings.goal_min || 120);
    var known = {}; db.subjects.forEach(function (s) { known[s.id] = s; });
    var subj = {}, days = [];
    function ghostOf(sid) { return CoreRef.subjectOrGhost(db, sid) || {}; }
    function recFor(sid) {
      var s = known[sid], g;
      if (s) g = { name: s.name, color: s.color || '#8A8F9C', ghost: false };
      else { var gh = ghostOf(sid); g = { name: gh.name || '?', color: gh.color || '#8A8F9C', ghost: true }; }
      var key = String(g.name).trim().toLowerCase();
      var r = subj[key] = subj[key] || { name: g.name, color: g.color, ghost: g.ghost, sec: 0, tests: 0, words: 0 };
      if (r.ghost && !g.ghost) r.ghost = false;                  // a living subject with the same name wins
      return r;
    }
    var examsBy = {}; CoreRef.exams(db).forEach(function (e) { (examsBy[e.date] = examsBy[e.date] || []).push(e.name); });
    for (var dk = fromDk, guard = 0; dk <= effEnd && guard < 4000; dk = addDk(dk, 1), guard++) {
      var running = runningFor(db, dk), total = dayEntrySec(db, dk) + running;
      // time per subject: every living subject, then the deleted ones grouped by name (as study.day_subject_times)
      var list = db.subjects.map(function (s) { return [s.id, dayEntrySec(db, dk, s.id) + (db.active && db.active.subject === s.id ? running : 0)]; }), ghosts = {}, gorder = [];
      db.entries.forEach(function (e) {
        if (e.date !== dk || known[e.subject] || !(e.sec > 0)) return;
        var key = String(ghostOf(e.subject).name || '?').trim().toLowerCase();
        if (!ghosts[key]) { ghosts[key] = [e.subject, 0]; gorder.push(key); }
        ghosts[key][1] += e.sec | 0;
      });
      gorder.forEach(function (k) { list.push(ghosts[k]); });
      list = list.filter(function (x) { return x[1] > 0; }).map(function (x, i) { return [x[0], x[1], i]; }).sort(function (a, b) { return (b[1] - a[1]) || (a[2] - b[2]); });
      var parts = [];
      list.forEach(function (x) { var r = recFor(x[0]); r.sec += x[1]; parts.push([r.name, x[1]]); });
      var dayTests = db.tests[dk] || {}, dayWords = db.words[dk] || {}, nt = 0, nw = 0;
      Object.keys(dayTests).forEach(function (sid) { var c = dayTests[sid] | 0; recFor(sid).tests += c; nt += c; });
      Object.keys(dayWords).forEach(function (sid) { var c = dayWords[sid] | 0; recFor(sid).words += c; nw += c; });
      var di = dinfo(dk); di.sec = total; di.tests = nt; di.words = nw; di.parts = parts; di.exam = examsBy[dk] || [];
      days.push(di);
    }
    var sessions = [];
    db.sessions.slice().sort(function (a, b) { return Number(a.start || 0) - Number(b.start || 0); }).forEach(function (r) {
      var st = Number(r.start); if (!isFinite(st)) return;
      var dt = new Date(st * 1000), sk = dkeyOf(dt);
      if (sk >= fromDk && sk <= effEnd) sessions.push({ start: dt, dk: sk, subject: String(r.subject || ''), planned_min: parseInt(r.planned_min, 10) || 0, focus_sec: parseInt(r.focus_sec, 10) || 0,
                                                       status: String(r.status || ''), blocked: parseInt(r.blocked_count, 10) || 0 });
    });
    var exams = [];
    CoreRef.exams(db).forEach(function (e) { if (e.date >= fromDk && e.date <= toDk) { var di = dinfo(e.date); di.name = e.name; exams.push(di); } });
    var total2 = 0, active = [], best = null, streak = 0, run = 0, goalDays = 0;
    days.forEach(function (x) {
      total2 += x.sec;
      if (x.sec > 0) { active.push(x); if (!best || x.sec > best.sec) best = x; }
      run = x.sec >= STREAK_MIN_SEC ? run + 1 : 0; streak = Math.max(streak, run);
      if (goalMin * 60 && x.sec >= goalMin * 60) goalDays++;
    });
    var subjects = Object.keys(subj).map(function (k) { return subj[k]; }).sort(function (a, b) { return (b.sec - a.sec) || (b.tests - a.tests) || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0); })
      .filter(function (r) { return r.sec || r.tests || r.words; });
    var monthly = [];
    if (days.length > MAX_DAILY_ROWS) {
      var by = {}, keys = [];
      days.forEach(function (x) {
        var k = H.monthKey(x), id = k.join('-');
        if (!by[id]) { by[id] = { key: k, sec: 0, tests: 0, words: 0, active: 0, days: 0 }; keys.push(k); }
        var m = by[id]; m.sec += x.sec; m.tests += x.tests; m.words += x.words; m.days += 1; m.active += x.sec > 0 ? 1 : 0;
      });
      keys.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
      monthly = keys.map(function (k) { return by[k.join('-')]; });
    }
    var sess = 0; sessions.forEach(function (s) { sess += s.focus_sec; });
    var ws = db.settings && db.settings.week_start !== undefined ? parseInt(db.settings.week_start, 10) : 5;
    return {
      lang: lang, name: String(opts.name || '').trim(), start: dinfo(fromDk), end: dinfo(toDk), eff_end: dinfo(effEnd), generated: new Date(), days: days, monthly: monthly, daily_rows: days.length <= MAX_DAILY_ROWS,
      subjects: subjects, sessions: sessions, exams: exams, goal_sec: goalMin * 60,
      summary: { total: total2, active_days: active.length, period_days: days.length, avg_active: active.length ? Math.floor(total2 / active.length) : 0, avg_cal: days.length ? Math.floor(total2 / days.length) : 0,
                 best: best, tests: days.reduce(function (a, x) { return a + x.tests; }, 0), words: days.reduce(function (a, x) { return a + x.words; }, 0), streak: streak, goal_days: goalDays,
                 sessions: sessions.length, sessions_sec: sess },
      version: opts.version || VERSION(), week_start: isFinite(ws) ? ws : 5, schedule: null,
      results: resultsData(db, toDk, lang, H), H: H
    };
  }

  function has(v) { return v !== null && v !== undefined; }
  function resultsData(db, endDk, lang, H) {
    H = H || helpers(lang);
    var view = { exams: CoreRef.exams(db).filter(function (e) { return e.result && e.date <= endDk; }), exam_subjects: db.exam_subjects };
    var P = CoreRef.examProgress(view), ex = P.exams;
    if (!ex.length) return null;
    var tz = [];
    function prevOf(i, key) { for (var k = i - 1; k >= 0; k--) if (has(ex[k][key])) return ex[k][key]; return null; }
    ex.forEach(function (e, i) {
      if (has(e.taraz)) tz.push([i, e.taraz]);
      var pt = prevOf(i, 'taraz'), pr = prevOf(i, 'rank'), pg = prevOf(i, 'rank_region');
      e.rank_region = has(e.rank_region) ? e.rank_region : null;
      e.delta = has(e.taraz) && pt !== null ? e.taraz - pt : null;
      e.delta_rank = has(e.rank) && pr !== null ? pr - e.rank : null;                      // + = better rank
      e.delta_region = has(e.rank_region) && pg !== null ? pg - e.rank_region : null;
      e.short = H.fmtDate(dinfo(e.date), false, false);
    });
    var subs = P.subjects.map(function (s) {
      var pts = s.points.filter(function (p) { return has(p[2]) || has(p[1]); }), tzp = s.points.filter(function (p) { return has(p[2]); }), latest = pts.length ? pts[pts.length - 1] : null;
      return { key: s.key, name: s.name, color: s.color, points: s.points, latest_pct: latest ? latest[1] : null, latest_taraz: tzp.length ? tzp[tzp.length - 1][2] : null,
               delta: tzp.length >= 2 ? tzp[tzp.length - 1][2] - tzp[tzp.length - 2][2] : null };
    });
    var ranked = subs.filter(function (s) { return has(s.latest_taraz); }).sort(function (a, b) { return b.latest_taraz - a.latest_taraz; });
    var moved = subs.filter(function (s) { return s.delta !== null; });
    function pick(list, key, better) { var b = null; list.forEach(function (e) { if (has(e[key]) && (b === null || better(e[key], b[key]))) b = e; }); return b; }
    var maxMoved = moved.length ? Math.max.apply(null, moved.map(function (s) { return s.delta; })) : 0, minMoved = moved.length ? Math.min.apply(null, moved.map(function (s) { return s.delta; })) : 0;
    return {
      exams: ex, subjects: subs, count: ex.length, latest: ex[ex.length - 1], prev: ex.length > 1 ? ex[ex.length - 2] : null,
      best_taraz: pick(ex, 'taraz', function (a, b) { return a > b; }),
      avg_taraz: tz.length ? tz.reduce(function (a, p) { return a + p[1]; }, 0) / tz.length : null,
      best_rank: pick(ex, 'rank', function (a, b) { return a < b; }), best_rank_region: pick(ex, 'rank_region', function (a, b) { return a < b; }),
      first_to_last: tz.length >= 2 ? tz[tz.length - 1][1] - tz[0][1] : null,
      strong: ranked.slice(0, 2), weak: ranked.length >= 4 ? ranked.slice(-2).reverse() : [],
      improved: moved.length && maxMoved > 0 ? moved.filter(function (s) { return s.delta === maxMoved; })[0] : null,
      declined: moved.length && minMoved < 0 ? moved.filter(function (s) { return s.delta === minMoved; })[0] : null
    };
  }

  // ---------------------------------------------------------------- charts of the exam progress (report.exam_chart / result_scenes)
  function examChart(res, kind, R, w, h) {
    var H = R.H, t = H.STR, fa = H.fa, ex = res ? res.exams : [];
    if (!ex.length) return new WC.Scene(w, 10);
    var labels = ex.map(function (e) { return e.short; }), tips = ex.map(function (e) { return e.name + ' · ' + H.fmtDate(dinfo(e.date)); }), fi = function (n) { return WC.fmtInt(n, fa); };
    if (kind === 'taraz' || kind === 'rank' || kind === 'region') {
      var key = { taraz: 'taraz', rank: 'rank', region: 'rank_region' }[kind], vals = ex.map(function (e) { return has(e[key]) ? e[key] : null; });
      if (!vals.some(function (v) { return v !== null; })) return new WC.Scene(w, 10);
      var name = { taraz: t.taraz_total, rank: t.rank, region: t.rank_region }[kind], color = { taraz: '#0e7490', rank: '#2563eb', region: '#7c9cd6' }[kind];
      return WC.lineChart({ labels: labels, invert: kind !== 'taraz', unit: name, series: [{ name: name, color: color, values: vals }],
        tips: vals.map(function (v, i) { return tips[i] + ': ' + (v !== null ? fi(v) : '-'); }) }, WC.LIGHT, w, h, fa);
    }
    var series = [];
    res.subjects.forEach(function (s) {
      var vals2 = ex.map(function () { return null; });
      s.points.forEach(function (p) { var v = kind === 'subjects' ? p[2] : p[1]; if (has(v)) vals2[p[0]] = v; });
      if (vals2.some(function (v) { return v !== null; })) series.push({ name: s.name, color: s.color, values: vals2, width: 2.2 });
    });
    if (!series.length || ex.length < 2) return new WC.Scene(w, 10);
    var spec = { labels: labels, series: series, unit: kind === 'subjects' ? t.taraz : '%' };
    if (kind === 'percent') spec.fmt = function (v) { return H.dg(v.toFixed(0)); };
    return WC.lineChart(spec, WC.LIGHT, w, h, fa);
  }
  function resultScenes(R, w) {
    var out = {}; if (!R.results) return out; w = w || 760;
    [['taraz', 250], ['rank', 230], ['region', 230], ['subjects', 270]].forEach(function (a) { var sc = examChart(R.results, a[0], R, w, a[1]); if (sc.items.length) out[a[0]] = sc; });
    return out;
  }

  // ---------------------------------------------------------------- HTML
  function stat(label, value) { return '<div class="stat"><b>' + esc(value) + '</b><span>' + esc(label) + '</span></div>'; }
  function barHtml(pct, color) { return '<div class="bar"><i style="width:' + Math.max(0, Math.min(100, pct)).toFixed(1) + '%;background:' + esc(color) + '"></i></div>'; }
  function deltaHtml(v, H) {
    if (!has(v) || v === 0) return '';
    return '<span class="' + (v > 0 ? 'pos' : 'neg') + '">' + esc(v > 0 ? H.STR.up : H.STR.down) + ' ' + esc(WC.fmtInt(Math.abs(v), H.fa)) + '</span>';
  }
  function periodTitle(R) {
    var H = R.H;
    return R.start.dk === R.end.dk ? H.fmtDate(R.start, true) : H.fmtDate(R.start) + '  -  ' + H.fmtDate(R.end);
  }

  function resultsHtml(R) {
    var res = R.results, H = R.H, t = H.STR, fa = H.fa;
    if (!res) return '';
    var ex = res.exams, fi = function (n) { return WC.fmtInt(n, fa); }, pc = function (p) { return H.dg(p.toFixed(1)) + (fa ? '٪' : '%'); }, latest = res.latest, best = res.best_taraz, bestr = res.best_rank;
    var stats = [stat(t.exams_taken, H.dg(res.count))];
    if (has(latest.taraz)) stats.push('<div class="stat"><b>' + esc(fi(latest.taraz)) + ' ' + deltaHtml(latest.delta, H) + '</b><span>' + esc(t.latest) + ' · ' + esc(t.taraz_total) + '</span></div>');
    if (has(latest.rank)) stats.push('<div class="stat"><b>' + esc(fi(latest.rank)) + ' ' + deltaHtml(latest.delta_rank, H) + '</b><span>' + esc(t.latest) + ' · ' + esc(t.rank) + '</span></div>');
    if (has(latest.rank_region)) stats.push('<div class="stat"><b>' + esc(fi(latest.rank_region)) + ' ' + deltaHtml(latest.delta_region, H) + '</b><span>' + esc(t.latest) + ' · ' + esc(t.rank_region) + '</span></div>');
    if (best) stats.push(stat(t.best_taraz + ' (' + best.short + ')', fi(best.taraz)));
    if (has(res.avg_taraz)) stats.push(stat(t.avg_taraz, fi(res.avg_taraz)));
    if (bestr) stats.push(stat(t.best_rank + ' (' + bestr.short + ')', fi(bestr.rank)));
    if (res.best_rank_region) stats.push(stat(t.best_rank_region + ' (' + res.best_rank_region.short + ')', fi(res.best_rank_region.rank_region)));
    if (has(res.first_to_last)) stats.push('<div class="stat"><b>' + (deltaHtml(res.first_to_last, H) || esc(t.same)) + '</b><span>' + esc(t.first_to_last) + '</span></div>');
    var out = ['<div class="card"><h2>' + esc(t.results_title) + '</h2><div class="grid">' + stats.join('') + '</div><div class="note">' + esc(t.results_upto) + '</div></div>\n'];
    var scenes = resultScenes(R);
    [['taraz', 'chart_taraz'], ['rank', 'chart_rank'], ['region', 'chart_region'], ['subjects', 'chart_subj']].forEach(function (a) {
      if (scenes[a[0]]) out.push('<div class="card"><h2>' + esc(t[a[1]]) + '</h2><div class="chart">' + scenes[a[0]].toSvg(t[a[1]]) + '</div></div>\n');
    });
    var none = '<span class=muted>' + esc(t.none) + '</span>', rows = [];
    ex.slice().reverse().forEach(function (e) {
      rows.push('<tr><td class="num">' + esc(H.fmtDate(dinfo(e.date))) + '</td><td>' + esc(e.name) + '</td><td class="num">' + (has(e.taraz) ? esc(fi(e.taraz)) : none) + '</td><td class="num">' + deltaHtml(e.delta, H) + '</td>' +
        '<td class="num">' + (has(e.rank) ? esc(fi(e.rank)) : none) + '</td><td class="num">' + deltaHtml(e.delta_rank, H) + '</td>' +
        '<td class="num">' + (has(e.rank_region) ? esc(fi(e.rank_region)) + ' ' + deltaHtml(e.delta_region, H) : none) + '</td>' +
        '<td class="num">' + (has(e.pct_avg) ? esc(pc(e.pct_avg)) : '') + '</td><td>' + esc(e.note) + '</td></tr>');
    });
    out.push('<div class="card tall"><h2>' + esc(t.exam_name) + '</h2><table><thead><tr><th>' + esc(t.date) + '</th><th>' + esc(t.exam_name) + '</th><th class="num">' + esc(t.taraz_total) + '</th><th class="num">' + esc(t.delta_taraz) + '</th>' +
      '<th class="num">' + esc(t.rank) + '</th><th class="num">' + esc(t.delta_rank) + '</th><th class="num">' + esc(t.rank_region) + '</th><th class="num">' + esc(t.pct_avg) + '</th><th>' + esc(t.note_l) + '</th></tr></thead><tbody>' + rows.join('') + '</tbody></table></div>\n');
    var subs = res.subjects.filter(function (s) { return s.points.some(function (p) { return has(p[1]) || has(p[2]); }); });
    if (subs.length) {
      var cols = []; for (var i = Math.max(0, ex.length - 8); i < ex.length; i++) cols.push(i);
      var head = cols.map(function (i2) { return '<th class="num">' + esc(ex[i2].short) + '</th>'; }).join(''), rows2 = [];
      subs.forEach(function (s) {
        var cells = {}; s.points.forEach(function (p) { cells[p[0]] = [p[1], p[2]]; });
        var tds = cols.map(function (i2) {
          var c = cells[i2] || [null, null], pct = c[0], tz = c[1];
          return '<td class="num">' + (has(tz) ? '<b>' + esc(fi(tz)) + '</b>' : '') + (has(pct) ? '<br><span class="muted">' + esc(pc(pct)) + '</span>' : '') + ((has(tz) || has(pct)) ? '' : '<span class="muted">' + esc(t.none) + '</span>') + '</td>';
        });
        rows2.push('<tr><td class="name"><span class="dot" style="background:' + esc(s.color) + '"></span>' + esc(s.name) + '</td>' + tds.join('') + '<td class="num">' + deltaHtml(s.delta, H) + '</td></tr>');
      });
      out.push('<div class="card tall"><h2>' + esc(t.subject_matrix) + '</h2><table><thead><tr><th>' + esc(t.subject) + '</th>' + head + '<th class="num">' + esc(t.latest_vs_prev) + '</th></tr></thead><tbody>' + rows2.join('') + '</tbody></table>' +
        '<div class="note">' + esc(t.taraz) + ' / ' + esc(t.pct) + '</div></div>\n');
    }
    var ins = [], sep = '، ';
    function nm(s) { return esc(s.name + ' (' + fi(s.latest_taraz) + ')'); }
    if (res.strong.length) ins.push('<li><b>' + esc(t.strong) + ':</b> ' + res.strong.map(nm).join(sep) + '</li>');
    if (res.weak.length) ins.push('<li><b>' + esc(t.weak) + ':</b> ' + res.weak.map(nm).join(sep) + '</li>');
    if (res.improved) ins.push('<li><b>' + esc(t.improved) + ':</b> ' + esc(res.improved.name) + ' ' + deltaHtml(res.improved.delta, H) + '</li>');
    if (res.declined) ins.push('<li><b>' + esc(t.declined) + ':</b> ' + esc(res.declined.name) + ' ' + deltaHtml(res.declined.delta, H) + '</li>');
    if (ins.length) out.push('<div class="card"><ul class="ins">' + ins.join('') + '</ul></div>\n');
    return out.join('');
  }

  function renderHtml(R, interactive) {
    if (interactive === undefined) interactive = true;
    var H = R.H, t = H.STR, lang = R.lang, rtl = lang === 'fa', s = R.summary, total = s.total, out = [], dash = '<span class="muted">' + esc(t.none) + '</span>';
    out.push('<!DOCTYPE html>\n<html lang="' + lang + '" dir="' + (rtl ? 'rtl' : 'ltr') + '">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>' + esc(t.title) +
      (R.name ? ' - ' + esc(R.name) : '') + '</title>\n<style>' + CSS + '</style>\n</head>\n<body>\n<div class="page">\n');
    if (interactive) out.push('<button class="noprint" onclick="window.print()">' + esc(t.print) + '</button>\n');
    var meta = ['<span>' + esc(t.period) + ': <b>' + esc(periodTitle(R)) + '</b></span>'];
    if (R.name) meta.unshift('<span>' + esc(t.student) + ': <b>' + esc(R.name) + '</b></span>');
    meta.push('<span>' + esc(t.generated) + ': ' + esc(H.fmtDate(dinfo(dkeyOf(R.generated)))) + '</span>');
    out.push('<div class="head"><h1>' + esc(t.title) + '</h1><div class="meta">' + meta.join('') + '</div></div>\n');
    if (!R.days.length || (!total && !R.sessions.length && !R.subjects.length)) out.push('<div class="card"><div class="empty">' + esc(t.no_data) + '</div></div>\n');
    var best = s.best, stats = [
      stat(t.total, H.fmtDur(total)), stat(t.active_days, H.dg(s.active_days + ' ' + t.of_days.replace('{n}', s.period_days))), stat(t.avg_active, H.fmtDur(s.avg_active)), stat(t.avg_cal, H.fmtDur(s.avg_cal)),
      stat(t.best + (best ? ' (' + H.fmtDate(best, false, false) + ')' : ''), best ? H.fmtDur(best.sec) : t.none), stat(t.tests, H.dg(s.tests))];
    if (s.words) stats.push(stat(t.words, H.dg(s.words)));
    stats.push(stat(t.streak, H.dg(s.streak)));
    if (R.goal_sec) stats.push(stat(t.goal_days, H.dg(s.goal_days + ' ' + t.of + ' ' + s.period_days)));
    stats.push(stat(t.sessions, H.dg(s.sessions)));
    stats.push(stat(t.sessions_time, H.fmtDur(s.sessions_sec)));
    out.push('<div class="card"><h2>' + esc(t.summary) + '</h2><div class="grid">' + stats.join('') + '</div><div class="note">' + esc(t.note) + '</div></div>\n');
    if (R.subjects.length) {
      var rows = R.subjects.map(function (r) {
        var pct = total ? r.sec / total * 100 : 0, nm = esc(r.name) + (r.ghost ? ' <span class="muted">(' + esc(t.deleted) + ')</span>' : '');
        return '<tr><td class="name"><span class="dot" style="background:' + esc(r.color) + '"></span>' + nm + '</td><td class="num">' + esc(H.fmtDur(r.sec)) + '</td><td class="num">' + H.dg(pct.toFixed(0) + '%') + '</td>' +
          '<td style="width:28%">' + barHtml(pct, r.color) + '</td><td class="num">' + (r.tests ? H.dg(r.tests) : dash) + '</td><td class="num">' + (r.words ? H.dg(r.words) : dash) + '</td></tr>';
      });
      out.push('<div class="card"><h2>' + esc(t.subjects) + '</h2><table><thead><tr><th>' + esc(t.subject) + '</th><th class="num">' + esc(t.time) + '</th><th class="num">' + esc(t.share) + '</th><th></th>' +
        '<th class="num">' + esc(t.tests_short) + '</th><th class="num">' + esc(t.words_short) + '</th></tr></thead><tbody>' + rows.join('') + '</tbody></table></div>\n');
    }
    var scStudy = WC.studyChart(R);
    if (scStudy.items.length && R.days.length > 1) {
      var mode = R.daily_rows ? 'day' : 'month', wk = R.days.length >= 7 ? WC.weekdayChart(R) : null;
      out.push('<div class="card"><h2>' + esc(mode === 'day' ? t.chart_daily : t.chart_monthly) + '</h2><div class="chart">' + scStudy.toSvg(t.chart_daily) + '</div></div>\n');
      if (wk) out.push('<div class="card"><h2>' + esc(t.weekday_chart) + '</h2><div class="chart" style="max-width:520px;margin:0 auto">' + wk.toSvg(t.weekday_chart) + '</div></div>\n');
    }
    out.push(resultsHtml(R));
    if (R.daily_rows && R.days.length) {
      var mx = Math.max.apply(null, R.days.map(function (x) { return x.sec; }).concat([1])), anyExam = R.days.some(function (x) { return x.exam.length; });
      var rws = R.days.map(function (x) {
        var ex = x.exam.length ? '<td><span class="exam">' + esc(x.exam.join(', ')) + '</span></td>' : (anyExam ? '<td></td>' : '');
        return '<tr><td class="num">' + esc(H.fmtDate(x)) + '</td><td class="num">' + esc(rtl ? WC.FA_DAYS[x.wd] : WC.EN_DAYS[x.wd].slice(0, 3)) + '</td><td class="num">' + (x.sec ? esc(H.fmtDur(x.sec)) : '<span class=muted>' + esc(t.none) + '</span>') + '</td>' +
          '<td style="width:26%">' + barHtml(x.sec / mx * 100, '#0e7490') + '</td><td class="num">' + H.dg(x.tests || '') + '</td><td class="num">' + H.dg(x.words || '') + '</td>' + ex + '</tr>';
      });
      out.push('<div class="card tall"><h2>' + esc(t.daily) + '</h2><table><thead><tr><th>' + esc(t.date) + '</th><th class="num">' + esc(t.weekday) + '</th><th class="num">' + esc(t.time) + '</th><th></th><th class="num">' + esc(t.tests_short) + '</th><th class="num">' +
        esc(t.words_short) + '</th>' + (anyExam ? '<th>' + esc(t.exam) + '</th>' : '') + '</tr></thead><tbody>' + rws.join('') + '</tbody></table></div>\n');
    } else if (R.monthly.length) {
      var mx2 = Math.max.apply(null, R.monthly.map(function (m) { return m.sec; }).concat([1]));
      var rws2 = R.monthly.map(function (m) {
        return '<tr><td>' + esc(H.monthLabel(m.key)) + '</td><td class="num">' + (m.sec ? esc(H.fmtDur(m.sec)) : dash) + '</td><td style="width:28%">' + barHtml(m.sec / mx2 * 100, '#0e7490') + '</td>' +
          '<td class="num">' + H.dg(m.active + ' ' + t.of + ' ' + m.days) + '</td><td class="num">' + (m.tests ? H.dg(m.tests) : dash) + '</td><td class="num">' + (m.words ? H.dg(m.words) : dash) + '</td></tr>';
      });
      out.push('<div class="card tall"><h2>' + esc(t.monthly) + '</h2><table><thead><tr><th>' + esc(t.month) + '</th><th class="num">' + esc(t.time) + '</th><th></th><th class="num">' + esc(t.active_days) + '</th><th class="num">' + esc(t.tests_short) +
        '</th><th class="num">' + esc(t.words_short) + '</th></tr></thead><tbody>' + rws2.join('') + '</tbody></table></div>\n');
    }
    if (R.sessions.length) {
      var rws3 = R.sessions.map(function (x) {
        return '<tr><td class="num">' + esc(H.fmtDate(dinfo(x.dk))) + ' · ' + H.dg(pad2(x.start.getHours()) + ':' + pad2(x.start.getMinutes())) + '</td><td>' + esc(x.subject || t.none) + '</td><td class="num">' + esc(H.fmtDur(x.planned_min * 60)) + '</td>' +
          '<td class="num">' + esc(H.fmtDur(x.focus_sec)) + '</td><td>' + esc(H.status(x.status)) + '</td><td class="num">' + H.dg(x.blocked) + '</td></tr>';
      });
      out.push('<div class="card tall"><h2>' + esc(t.sessions_title) + '</h2><table><thead><tr><th>' + esc(t.when) + '</th><th>' + esc(t.subject) + '</th><th class="num">' + esc(t.planned) + '</th><th class="num">' + esc(t.focused) + '</th><th>' + esc(t.status) +
        '</th><th class="num">' + esc(t.blocked) + '</th></tr></thead><tbody>' + rws3.join('') + '</tbody></table></div>\n');
    }
    if (R.exams.length) out.push('<div class="card"><h2>' + esc(t.exams) + '</h2><table><tbody>' + R.exams.map(function (e) { return '<tr><td class="num">' + esc(H.fmtDate(e, true)) + '</td><td>' + esc(e.name) + '</td></tr>'; }).join('') + '</tbody></table></div>\n');
    out.push('<div class="foot">' + esc(t.app) + ' · v' + esc(R.version) + '</div>\n</div>\n</body>\n</html>\n');
    return out.join('').split('<table>').join('<div class="tw"><table>').split('</table>').join('</table></div>');
  }

  // ---------------------------------------------------------------- CSV (render_csv)
  function csvQuote(x) { x = x === null || x === undefined ? '' : String(x); return /[",\r\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; }
  function renderCsv(R) {
    var H = R.H, t = H.STR, s = R.summary, rows = [], lang = R.lang;
    function pf(v) { return Number.isInteger(v) ? v.toFixed(1) : String(v); }                 // a Python float prints 2218.0
    function mins(sec) { return pf(WC.pyRound(sec / 60 * 10) / 10); }                       // round(sec / 60, 1)
    function w(r) { rows.push(r); }
    var gen = R.generated;
    w([t.title, 'VOIDLOCK ' + R.version]);
    if (R.name) w([t.student, R.name]);
    w([t.start_gdate, R.start.dk, H.jdateNumeric(R.start)]); w([t.end_gdate, R.end.dk, H.jdateNumeric(R.end)]);
    w([t.generated, dkeyOf(gen) + ' ' + pad2(gen.getHours()) + ':' + pad2(gen.getMinutes())]); w([]);
    w([t.summary]); w([t.key, t.value]);
    [[t.total_min, mins(s.total)], [t.active_days, s.active_days], [t.of_days.replace('{n}', '').trim(), s.period_days], [t.avg_active + ' (' + t.csv_minutes + ')', mins(s.avg_active)],
     [t.avg_cal + ' (' + t.csv_minutes + ')', mins(s.avg_cal)], [t.tests, s.tests], [t.words, s.words], [t.streak, s.streak], [t.goal_days, s.goal_days], [t.sessions, s.sessions],
     [t.sessions_time + ' (' + t.csv_minutes + ')', mins(s.sessions_sec)]].forEach(w);
    if (s.best) w([t.best, s.best.dk, mins(s.best.sec)]);
    w([]); w([t.subjects]); w([t.subject, t.total_min, t.share + ' %', t.tests, t.words]);
    R.subjects.forEach(function (r) { w([r.name + (r.ghost ? ' (' + t.deleted + ')' : ''), mins(r.sec), s.total ? pf(WC.pyRound(r.sec / s.total * 1000) / 10) : 0, r.tests, r.words]); });
    w([]);
    var cols = R.subjects.filter(function (r) { return r.sec; }).map(function (r) { return r.name; });
    if (R.daily_rows) {
      w([t.daily]); w([t.gdate, t.jdate, t.weekday, t.total_min, t.tests, t.words].concat(cols));
      R.days.forEach(function (x) {
        var per = {}; x.parts.forEach(function (p) { per[p[0]] = p[1]; });
        w([x.dk, H.jdateNumeric(x), lang === 'fa' ? WC.FA_DAYS[x.wd] : WC.EN_DAYS[x.wd].slice(0, 3), mins(x.sec), x.tests, x.words].concat(cols.map(function (c) { return per[c] ? mins(per[c]) : ''; })));
      });
    } else {
      w([t.monthly]); w([t.month, t.total_min, t.active_days, t.days, t.tests, t.words]);
      R.monthly.forEach(function (m) { w([H.monthLabel(m.key), mins(m.sec), m.active, m.days, m.tests, m.words]); });
    }
    w([]); w([t.sessions_title]); w([t.gdate, 'HH:MM', t.subject, t.planned_min, t.focus_min, t.status, t.blocked]);
    R.sessions.forEach(function (x) { w([x.dk, pad2(x.start.getHours()) + ':' + pad2(x.start.getMinutes()), x.subject, x.planned_min, mins(x.focus_sec), H.status(x.status), x.blocked]); });
    if (R.exams.length) { w([]); w([t.exams]); R.exams.forEach(function (e) { w([e.dk, H.jdateNumeric(e), e.name]); }); }
    var res = R.results;
    if (res) {
      w([]); w([t.results_title]);
      var subs = res.subjects.filter(function (x) { return x.points.length; }), head = [t.gdate, t.jdate, t.exam_name, t.taraz_total, t.rank, t.rank_region, t.pct_avg, t.note_l];
      subs.forEach(function (x) { head.push(x.name + ' - ' + t.pct, x.name + ' - ' + t.taraz); });
      w(head);
      res.exams.forEach(function (e, i) {
        function v(x) { return has(x) ? x : ''; }
        var row = [e.date, H.jdateNumeric(dinfo(e.date)), e.name, v(e.taraz), v(e.rank), v(e.rank_region), has(e.pct_avg) ? pf(WC.pyRound(e.pct_avg * 100) / 100) : '', e.note];
        subs.forEach(function (x) { var pt = x.points.filter(function (p) { return p[0] === i; })[0]; row.push(!pt || !has(pt[1]) ? '' : pt[1], !pt || !has(pt[2]) ? '' : pt[2]); });
        w(row);
      });
    }
    return rows.map(function (r) { return r.map(csvQuote).join(','); }).join('\r\n') + '\r\n';
  }

  // ---------------------------------------------------------------- the phone's entry point
  function build(db, from, to, opts) {
    opts = opts || {};
    var R = collect(db, from, to, opts), html = renderHtml(R, opts.interactive !== false), t = R.H.STR;
    return { html: html, csv: '\uFEFF' + renderCsv(R), title: t.title + (R.name ? ' - ' + R.name : ''), base: 'voidlock-report-' + from.replace(/-/g, '') + '-' + to.replace(/-/g, ''), R: R };
  }
  var Report = { build: build, collect: collect, renderHtml: renderHtml, renderCsv: renderCsv, resultScenes: resultScenes, helpers: helpers, dinfo: dinfo, MAX_DAILY_ROWS: MAX_DAILY_ROWS };
  if (node) module.exports = Report; else root.Report = Report;
})(typeof window !== 'undefined' ? window : globalThis);
