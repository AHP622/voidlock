/* Report of a period: a self-contained HTML page (also printed to PDF) and a CSV for spreadsheets. White paper style, same charts. */
(function (root) {
  'use strict';
  var t = function (k, v) { return I18n.t(k, v); };
  function esc(s) { return Charts.esc(s); }
  var CSS = ':root{--text:#1f2430;--text2:#4f5666;--text3:#7b8190;--border-hi:#cfd3dc;--panel:#fff;--amber:#c77700;--violet:#7c3aed;--accent:#2563eb;--panel2:#f3f4f7}' +
    '*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--text);font-family:"Vazirmatn","Noto Sans Arabic UI","Noto Sans Arabic","Segoe UI",system-ui,sans-serif;font-size:14px;line-height:1.6}' +
    '.page{max-width:780px;margin:0 auto;padding:22px}h1{margin:0;font-size:24px}h2{font-size:16px;margin:26px 0 10px;border-bottom:2px solid #e5e7ee;padding-bottom:4px}' +
    '.sub{color:var(--text2);margin:4px 0 16px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.stat{background:var(--panel2);border-radius:10px;padding:10px}' +
    '.stat b{display:block;font-size:18px}.stat span{font-size:12px;color:var(--text3)}table{width:100%;border-collapse:collapse;margin:6px 0}th,td{padding:7px 8px;border-bottom:1px solid #e5e7ee;text-align:start}' +
    'th{background:var(--panel2);font-size:12px;color:var(--text2)}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-inline-end:6px}.leg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:var(--text2);margin:6px 0 12px}' +
    '.foot{margin-top:30px;color:var(--text3);font-size:12px;text-align:center}svg.chart{width:100%;height:auto;display:block;direction:ltr}.num{font-variant-numeric:tabular-nums}' +
    'html,body{width:100%;max-width:100%;overflow-x:hidden}.page{width:100%;min-width:0}table{max-width:100%;table-layout:fixed}th,td{min-width:0;overflow-wrap:anywhere;word-break:break-word}' +
    '@page{size:A4;margin:12mm}@media print{html,body{overflow:visible}.page{padding:0}h2{break-after:avoid}table,svg{break-inside:avoid}}@media(max-width:560px){.page{padding:14px}h1{font-size:clamp(18px,5vw,24px);overflow-wrap:anywhere}.grid{grid-template-columns:1fr 1fr;gap:7px}.stat{padding:8px}.stat b{font-size:clamp(14px,4vw,18px)}table{font-size:10px}th,td{padding:5px 3px}}';

  function rangeDays(from, to) {
    var out = [], d = Core.parseDkey(from), end = Core.parseDkey(to), n = 0;
    while (d <= end && n++ < 5000) { out.push(Core.dkey(d)); d = Core.addDays(d, 1); }
    return out;
  }
  function legendHtml(items) {
    return '<div class="leg">' + items.map(function (l) {
      return '<span>' + (l.dashed ? '<span style="display:inline-block;width:16px;border-top:2px dashed ' + l.color + ';margin-inline-end:6px;vertical-align:middle"></span>' : '<span class="dot" style="background:' + l.color + '"></span>') + esc(l.name) + '</span>';
    }).join('') + '</div>';
  }
  function cell(x) { return '<td class="num">' + x + '</td>'; }
  function countOnDay(db, kind, dk) {
    var row = db[kind] && db[kind][dk];
    return row ? Object.keys(row).reduce(function (n, id) { return n + (Number(row[id]) || 0); }, 0) : 0;
  }
  function sessionRows(db, from, to) {
    return (db.sessions || []).filter(function (s) {
      if (!s || !isFinite(Number(s.start))) return false;
      var dk = Core.dkey(new Date(Number(s.start) * 1000)); return dk >= from && dk <= to;
    }).sort(function (a, b) { return Number(a.start) - Number(b.start); });
  }
  function tableRows(db, days, rows, fa) {
    var groups = {}, daily = days.length <= 62;
    rows.forEach(function (r) {
      var d = Core.parseDkey(r.dk), j = Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
      var key = daily ? r.dk : (fa ? j.jy + '-' + ('0' + j.jm).slice(-2) : d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2));
      var g = groups[key] || (groups[key] = { dk: r.dk, sec: 0, tests: 0, words: 0, parts: {} });
      g.sec += r.sec; g.tests += countOnDay(db, 'tests', r.dk); g.words += countOnDay(db, 'words', r.dk);
      Object.keys(r.parts).forEach(function (n) { g.parts[n] = (g.parts[n] || 0) + r.parts[n]; });
    });
    var headers = daily ? [t('exam_date'), t('weekday'), t('total'), t('tests_solved'), t('words_learned')] : [t('exam_date'), t('total'), t('tests_solved'), t('words_learned')];
    var out = ['<h2>' + esc(daily ? t('daily_table') : t('monthly_table')) + '</h2><table><thead><tr>' + headers.map(function (x) { return '<th>' + x + '</th>'; }).join('') + '</tr></thead><tbody>'];
    Object.keys(groups).sort().forEach(function (key) {
      var g = groups[key], d = Core.parseDkey(g.dk), j = Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
      var label = daily ? esc(I18n.dateStr(g.dk)) : esc(fa ? I18n.digits(j.jy + '/' + j.jm) : d.getFullYear() + '/' + (d.getMonth() + 1));
      var cells = ['<td>' + label + '</td>'];
      if (daily) cells.push('<td>' + esc(I18n.dayShort(g.dk)) + '</td>');
      cells.push(cell(esc(I18n.dur(g.sec))), cell(I18n.num(g.tests)), cell(I18n.num(g.words)));
      out.push('<tr>' + cells.join('') + '</tr>');
    });
    out.push('</tbody></table>');
    return out.join('');
  }
  function weekdayChart(rows, fa) {
    var names = fa ? ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    var sums = [0, 0, 0, 0, 0, 0, 0], counts = [0, 0, 0, 0, 0, 0, 0];
    rows.forEach(function (r) { var d = Core.parseDkey(r.dk), w = (d.getDay() + 6) % 7; sums[w] += r.sec; counts[w]++; });
    var avgs = sums.map(function (s, i) { return s / Math.max(1, counts[i]); }), max = Math.max.apply(null, avgs.concat([3600])), W = 720, H = 190, left = 28, base = 146, step = 96, bar = 42;
    var svg = '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" role="img"><line x1="' + left + '" x2="700" y1="' + base + '" y2="' + base + '" stroke="#cfd3dc"/>';
    avgs.forEach(function (v, i) { var bh = Math.max(2, (v / max) * 112), x = left + 12 + i * step;
      svg += '<rect x="' + x + '" y="' + (base - bh) + '" width="' + bar + '" height="' + bh + '" rx="6" fill="#0e9f8e"><title>' + esc(names[i]) + ': ' + esc(I18n.dur(v)) + '</title></rect>' +
        '<text x="' + (x + bar / 2) + '" y="166" text-anchor="middle" font-size="11" fill="#4f5666">' + esc(names[i]) + '</text>';
    });
    return '<h2>' + esc(t('weekday_chart')) + '</h2>' + svg + '</svg>';
  }

  function studyPart(db, days, goalSec, fa) {
    var weekly = days.length > 90, bars = [];
    var examDays = {}; db.exams.forEach(function (e) { examDays[e.date] = 1; });
    if (!weekly) {
      days.forEach(function (dk, i) {
        var d = Core.parseDkey(dk), first = (fa ? Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate()).jd : d.getDate()) === 1;
        bars.push({ dk: dk, label: I18n.dayShort(dk), month: first || i === 0 ? I18n.monthShort(dk) : '', exam: !!examDays[dk], sec: Core.daySec(db, dk, false), tip: I18n.dateStr(dk, true),
          parts: Core.daySubjectTimes(db, dk).map(function (x) { return { name: I18n.subjName(x.subject), color: x.subject.color, sec: x.sec }; }) });
      });
    } else {
      for (var i = 0; i < days.length; i += 7) {
        var chunk = days.slice(i, i + 7), by = {}, sec = 0, ex = false;
        chunk.forEach(function (dk) {
          sec += Core.daySec(db, dk, false); if (examDays[dk]) ex = true;
          Core.daySubjectTimes(db, dk).forEach(function (x) { var k = I18n.subjName(x.subject); by[k] = by[k] || { name: k, color: x.subject.color, sec: 0 }; by[k].sec += x.sec; });
        });
        bars.push({ dk: chunk[0], label: I18n.dayShort(chunk[0]), month: I18n.monthShort(chunk[0]), exam: ex, sec: sec, tip: I18n.dateStr(chunk[0]) + ' …',
          parts: Object.keys(by).map(function (k) { return by[k]; }) });
      }
    }
    var ch = Charts.studyChart({ t: t, fa: fa, days: bars, goalSec: weekly ? goalSec * 7 : goalSec, width: 720 });
    var legend = ch.legend.slice();
    return { html: ch.svg + legendHtml(legend), weekly: weekly };
  }

  function build(db, from, to, studentName) {
    var fa = I18n.lang === 'fa', days = rangeDays(from, to), goalSec = (db.settings.goal_min || 120) * 60;
    var sessions = sessionRows(db, from, to), sessionSec = sessions.reduce(function (n, s) { return n + (Number(s.focus_sec) || 0); }, 0);
    var total = 0, best = { sec: 0, dk: null }, studied = 0, streak = 0, run = 0, goalDays = 0, subj = {}, testsBy = {}, wordsBy = {}, rows = [];
    days.forEach(function (dk) {
      var sec = Core.daySec(db, dk, false); total += sec; if (sec > best.sec) best = { sec: sec, dk: dk };
      if (sec > 0) studied++; if (sec >= goalSec) goalDays++; if (sec >= 600) { run++; streak = Math.max(streak, run); } else run = 0;
      var parts = Core.daySubjectTimes(db, dk), row = { dk: dk, sec: sec, parts: {} };
      parts.forEach(function (x) {
        var nm = I18n.subjName(x.subject), k = nm.toLowerCase();                       // subjects of the same name (e.g. old deleted ones) are one line
        subj[k] = subj[k] || { name: nm, color: x.subject.color, sec: 0, days: {}, ids: {} }; subj[k].sec += x.sec; subj[k].days[dk] = 1; if (x.subject.id) subj[k].ids[x.subject.id] = 1;
        row.parts[nm] = (row.parts[nm] || 0) + x.sec;
      });
      ['tests', 'words'].forEach(function (kind) { var m = db[kind][dk]; if (m) Object.keys(m).forEach(function (sid) { var tgt = kind === 'tests' ? testsBy : wordsBy; tgt[sid] = (tgt[sid] || 0) + m[sid]; }); });
      rows.push(row);
    });
    var names = Object.keys(subj).sort(function (a, b) { return subj[b].sec - subj[a].sec; });
    var testsTotal = 0, wordsTotal = 0; Object.keys(testsBy).forEach(function (k) { testsTotal += testsBy[k]; }); Object.keys(wordsBy).forEach(function (k) { wordsTotal += wordsBy[k]; });
    var title = t('report_title'), period = I18n.dateStr(from) + ' — ' + I18n.dateStr(to);
    var h = [];
    h.push('<!doctype html><html lang="' + I18n.lang + '" dir="' + (fa ? 'rtl' : 'ltr') + '"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title><style>' + CSS + '</style></head><body><div class="page">');
    h.push('<h1>VOIDLOCK · ' + esc(title) + '</h1><div class="sub">' + esc(period) + (studentName ? ' · ' + esc(t('name')) + ': ' + esc(studentName) : '') + ' · ' + esc(t('generated')) + ' ' + esc(I18n.dateStr(Core.dkey())) + '</div><p class="sub">' + esc(t('report_note')) + '</p>');
    h.push('<div class="grid">' + [[I18n.dur(total), t('total')], [I18n.dur(total / Math.max(1, days.length)), t('avg_per_day')], [I18n.dur(total / Math.max(1, studied)), t('avg_active_day')], [best.dk ? I18n.dur(best.sec) : '-', t('best_day') + (best.dk ? ' · ' + I18n.dateStr(best.dk) : '')],
      [I18n.digits(studied) + ' / ' + I18n.digits(days.length), t('study_days')], [I18n.digits(streak), t('streak')], [I18n.digits(goalDays), t('goal_days')], [I18n.num(testsTotal), t('tests_solved')], [I18n.num(wordsTotal), t('words_learned')], [I18n.num(sessions.length), t('sessions_title')], [I18n.dur(sessionSec), t('sessions_time')], [I18n.digits(names.length), t('subjects')]]
      .map(function (s) { return '<div class="stat"><b class="num">' + esc(s[0]) + '</b><span>' + esc(s[1]) + '</span></div>'; }).join('') + '</div>');
    var sp = studyPart(db, days, goalSec, fa);
    h.push('<h2>' + esc(t('daily_study')) + (sp.weekly ? ' · ' + esc(t('weekly_bars')) : '') + '</h2>' + sp.html);
    if (names.length) {
      h.push('<h2>' + esc(t('subject_share')) + '</h2><table><tr><th>' + esc(t('subject')) + '</th><th>' + esc(t('col_time')) + '</th><th>' + esc(t('col_share')) + '</th><th>' + esc(t('col_avg_day')) + '</th><th>' + esc(t('tests_solved')) + '</th><th>' + esc(t('words_learned')) + '</th></tr>' +
        names.map(function (k) {
          var s = subj[k], tt = 0, ww = 0; Object.keys(s.ids).forEach(function (id) { tt += testsBy[id] || 0; ww += wordsBy[id] || 0; });
          return '<tr><td><span class="dot" style="background:' + s.color + '"></span>' + esc(s.name) + '</td>' + cell(esc(I18n.dur(s.sec))) + cell(I18n.digits(Math.round(s.sec / Math.max(1, total) * 100)) + (fa ? '٪' : '%')) +
            cell(esc(I18n.dur(s.sec / Math.max(1, Object.keys(s.days).length)))) + cell(I18n.num(tt)) + cell(I18n.num(ww)) + '</tr>';
        }).join('') + '</table>');
    }
    // exams inside the period (with a result)
    var allExams = Core.exams(db).filter(function (e) { return e.date <= to; });
    var exs = allExams.filter(function (e) { return e.date >= from; });
    var withRes = exs.filter(function (e) { return e.result; });
    var reportExams = allExams.filter(function (e) { return e.result; });
    var examRows = reportExams.concat(exs.filter(function (e) { return !e.result; })).sort(function (a, b) { return b.date.localeCompare(a.date); });
    if (examRows.length) {
      function examDelta(e, key, invert) {
        var list = allExams.filter(function (x) { return x.result; }), ix = list.indexOf(e), prev = null;
        for (var pi = ix - 1; pi >= 0; pi--) if (list[pi].result[key] != null) { prev = list[pi].result[key]; break; }
        if (e.result[key] == null || prev == null) return '';
        var d = invert ? prev - e.result[key] : e.result[key] - prev;
        return (d > 0 ? '▲ ' : d < 0 ? '▼ ' : '= ') + I18n.num(Math.abs(d));
      }
      h.push('<h2>' + esc(t('exams')) + '</h2><table><tr><th>' + esc(t('exam_name')) + '</th><th>' + esc(t('exam_date')) + '</th><th>' + esc(t('total_taraz')) + '</th><th>' + esc(t('delta_taraz')) + '</th><th>' + esc(t('overall_rank')) + '</th><th>' + esc(t('delta_rank')) + '</th><th>' + esc(t('region_rank')) + '</th><th>' + esc(t('delta_rank')) + '</th><th>' + esc(t('pct_avg')) + '</th><th>' + esc(t('note')) + '</th></tr>' +
        examRows.map(function (e) {
          var r = e.result || {}, pcts = (r.subjects || []).filter(function (x) { return x.pct !== null && x.pct !== undefined; }).map(function (x) { return x.pct; });
          return '<tr><td>' + esc(e.name) + '</td>' + cell(esc(I18n.dateStr(e.date))) + cell(r.taraz != null ? I18n.num(r.taraz) : '-') + cell(esc(examDelta(e, 'taraz', false))) + cell(r.rank != null ? I18n.num(r.rank) : '-') + cell(esc(examDelta(e, 'rank', true))) + cell(r.rank_region != null ? I18n.num(r.rank_region) : '-') + cell(esc(examDelta(e, 'rank_region', true))) +
            cell(pcts.length ? I18n.num(pcts.reduce(function (a, b) { return a + b; }, 0) / pcts.length, 1) : '-') + '<td>' + esc(r.note || '') + '</td></tr>';
        }).join('') + '</table>');
    }
    if (allExams.some(function (e) { return e.result; })) {
      var view = { exams: allExams.filter(function (e) { return e.result; }), exam_subjects: db.exam_subjects }, ep = Core.examProgress(view), labels = ep.exams.map(function (e) { return e.name; });
      var scored = ep.exams.filter(function (e) { return e.taraz !== null && e.taraz !== undefined; }), ranks = ep.exams.filter(function (e) { return e.rank !== null && e.rank !== undefined; });
      var bestTaraz = scored.reduce(function (a, e) { return !a || e.taraz > a.taraz ? e : a; }, null);
      var bestRank = ranks.reduce(function (a, e) { return !a || e.rank < a.rank ? e : a; }, null);
      var regionRanks = ep.exams.filter(function (e) { return e.rank_region !== null && e.rank_region !== undefined; });
      var bestRegion = regionRanks.reduce(function (a, e) { return !a || e.rank_region < a.rank_region ? e : a; }, null);
      var avgTaraz = scored.length ? scored.reduce(function (n, e) { return n + e.taraz; }, 0) / scored.length : null;
      var latestResult = ep.exams[ep.exams.length - 1];
      var firstTaraz = scored.length ? scored[0].taraz : null, lastTaraz = scored.length ? scored[scored.length - 1].taraz : null;
      h.push('<h2>' + esc(t('results_summary')) + '</h2><div class="grid">' + [
        [I18n.num(ep.exams.length), t('exams_taken')],
        [latestResult.taraz == null ? '-' : I18n.num(latestResult.taraz), t('latest') + ' · ' + t('total_taraz')],
        [latestResult.rank == null ? '-' : I18n.num(latestResult.rank), t('latest') + ' · ' + t('overall_rank')],
        [latestResult.rank_region == null ? '-' : I18n.num(latestResult.rank_region), t('latest') + ' · ' + t('region_rank')],
        [bestTaraz ? I18n.num(bestTaraz.taraz) : '-', t('best_taraz')],
        [avgTaraz == null ? '-' : I18n.num(avgTaraz, 1), t('avg_taraz')],
        [bestRank ? I18n.num(bestRank.rank) : '-', t('best_rank')],
        [bestRegion ? I18n.num(bestRegion.rank_region) : '-', t('best_rank_region')],
        [firstTaraz == null || lastTaraz == null ? '-' : I18n.num(lastTaraz - firstTaraz), t('first_to_last')]
      ].map(function (x) { return '<div class="stat"><b class="num">' + esc(x[0]) + '</b><span>' + esc(x[1]) + '</span></div>'; }).join('') + '</div>');
      function lc(name, series, invert) {
        var c = Charts.lineChart({ t: t, fa: fa, labels: labels, series: series, invert: invert, width: 720, height: 220 });
        if (c.svg) h.push('<h2>' + esc(name) + (invert ? ' <small style="color:#7b8190;font-weight:400">(' + esc(t('rank_hint')) + ')</small>' : '') + '</h2>' + c.svg + legendHtml(c.legend));
      }
      lc(t('k_taraz'), [{ name: t('k_taraz'), color: '#0e9f8e', values: ep.exams.map(function (e) { return e.taraz; }) }]);
      lc(t('k_rank'), [{ name: t('k_rank'), color: '#2563eb', values: ep.exams.map(function (e) { return e.rank; }) }], true);
      lc(t('k_region'), [{ name: t('k_region'), color: '#7c3aed', values: ep.exams.map(function (e) { return e.rank_region; }) }], true);
      lc(t('k_subjects'), ep.subjects.map(function (s) { var v = ep.exams.map(function () { return null; }); s.points.forEach(function (p) { v[p[0]] = p[2]; }); return { name: s.name, color: s.color, values: v }; }));
      lc(t('k_percent'), ep.subjects.map(function (s) { var v = ep.exams.map(function () { return null; }); s.points.forEach(function (p) { v[p[0]] = p[1]; }); return { name: s.name, color: s.color, values: v }; }));
      if (ep.subjects.length) {
        var matrixStart = Math.max(0, ep.exams.length - 8), matrixExams = ep.exams.slice(matrixStart);
        h.push('<h2>' + esc(t('subject_matrix')) + '</h2><div style="overflow-x:auto"><table><thead><tr><th>' + esc(t('subject')) + '</th>' + matrixExams.map(function (e) { return '<th>' + esc(e.name) + '<br>' + esc(I18n.dateStr(e.date)) + '</th>'; }).join('') + '<th>' + esc(t('latest_vs_prev')) + '</th></tr></thead><tbody>' + ep.subjects.map(function (s) {
          var points = s.points.filter(function (p) { return p[1] != null || p[2] != null; }), tarazPoints = points.filter(function (p) { return p[2] != null; });
          var delta = tarazPoints.length > 1 ? tarazPoints[tarazPoints.length - 1][2] - tarazPoints[tarazPoints.length - 2][2] : null;
          return '<tr><td>' + esc(s.name) + '</td>' + matrixExams.map(function (_e, i) { var p = s.points.find(function (x) { return x[0] === i + matrixStart; }); return '<td>' + (p ? esc(t('percent')) + ': ' + esc(I18n.num(p[1], 1)) + '<br>' + esc(t('taraz')) + ': ' + esc(I18n.num(p[2])) : '—') + '</td>'; }).join('') + '<td>' + (delta == null ? '' : esc((delta > 0 ? '▲ ' : delta < 0 ? '▼ ' : '= ') + I18n.num(Math.abs(delta)))) + '</td></tr>';
        }).join('') + '</tbody></table></div>');
        var latestBySubject = ep.subjects.map(function (s) { var ps = s.points.filter(function (p) { return p[2] != null; }); return { name: s.name, latest: ps.length ? ps[ps.length - 1][2] : null, delta: ps.length > 1 ? ps[ps.length - 1][2] - ps[ps.length - 2][2] : null }; }).filter(function (s) { return s.latest != null; }).sort(function (a, b) { return b.latest - a.latest; });
        var insights = [];
        if (latestBySubject.length >= 4) insights.push(t('strong') + ': ' + latestBySubject.slice(0, 2).map(function (s) { return s.name + ' (' + I18n.num(s.latest) + ')'; }).join(' · '), t('weak') + ': ' + latestBySubject.slice(-2).reverse().map(function (s) { return s.name + ' (' + I18n.num(s.latest) + ')'; }).join(' · '));
        var movers = latestBySubject.filter(function (s) { return s.delta != null; });
        var better = movers.slice().sort(function (a, b) { return b.delta - a.delta; }), worse = movers.slice().sort(function (a, b) { return a.delta - b.delta; });
        if (better.length && better[0].delta > 0) insights.push(t('improved') + ': ' + better[0].name + ' (+' + I18n.num(better[0].delta) + ')');
        if (worse.length && worse[0].delta < 0) insights.push(t('declined') + ': ' + worse[0].name + ' (' + I18n.num(worse[0].delta) + ')');
        if (insights.length) h.push('<p class="sub">' + insights.map(esc).join(' · ') + '</p>');
      }
    }
    if (days.length >= 7) h.push(weekdayChart(rows, fa));
    h.push(tableRows(db, days, rows, fa));
    if (sessions.length) {
      h.push('<h2>' + esc(t('sessions_title')) + '</h2><table><thead><tr><th>' + esc(t('when')) + '</th><th>' + esc(t('subject')) + '</th><th>' + esc(t('planned')) + '</th><th>' + esc(t('focused')) + '</th><th>' + esc(t('status')) + '</th><th>' + esc(t('blocked')) + '</th></tr></thead><tbody>' + sessions.map(function (s) {
        var started = new Date(Number(s.start) * 1000), planned = Number(s.planned_min) || 0, focused = Number(s.focus_sec) || 0;
        var status = { completed: t('st_completed'), ended: t('st_ended'), emergency: t('st_emergency'), recovered: t('st_recovered') }[s.status] || s.status || '-';
        return '<tr><td>' + esc(I18n.dateStr(Core.dkey(started), true)) + ' ' + esc(started.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })) + '</td><td>' + esc(s.subject || '-') + '</td>' + cell(I18n.digits(planned) + ' ' + esc(t('minutes'))) + cell(esc(I18n.dur(focused))) + '<td>' + esc(status) + '</td>' + cell(I18n.num(Number(s.blocked_count) || 0)) + '</tr>';
      }).join('') + '</tbody></table>');
    }
    var timetable = db.weekly_schedule || {}, classRows = timetable.classes || [], plannedRows = timetable.sessions || [];
    if (classRows.some(function (x) { return x.enabled !== false; }) || plannedRows.some(function (x) { return x.enabled !== false; })) {
      var dayNames = fa ? ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه'] : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
      var order = [], ws = Number(timetable.week_start); if ([0, 5, 6].indexOf(ws) < 0) ws = 5;
      for (var wi = 0; wi < 7; wi++) order.push((ws + wi) % 7);
      var classMin = classRows.filter(function (x) { return x.enabled !== false; }).reduce(function (n, x) { return n + Number(x.minutes || 0); }, 0);
      var plannedMin = plannedRows.filter(function (x) { return x.enabled !== false; }).reduce(function (n, x) { return n + Number(x.minutes || 0); }, 0);
      h.push('<h2>' + esc(t('schedule_title')) + '</h2><p class="sub">' + esc(t('week_class_h')) + ': ' + esc(I18n.dur(classMin * 60)) + ' · ' + esc(t('week_session_h')) + ': ' + esc(I18n.dur(plannedMin * 60)) + '</p><table><thead><tr><th>' + esc(t('weekday')) + '</th><th>' + esc(t('kind')) + '</th><th>' + esc(t('when')) + '</th><th>' + esc(t('planned')) + '</th><th>' + esc(t('subject')) + '</th><th>' + esc(t('place')) + '</th></tr></thead><tbody>');
      order.forEach(function (day) {
        classRows.concat(plannedRows).filter(function (x) { return x.enabled !== false && Number(x.day) === day; }).sort(function (a, b) { return String(a.time).localeCompare(String(b.time)); }).forEach(function (x) {
          var cls = classRows.indexOf(x) >= 0;
          h.push('<tr><td>' + esc(dayNames[day]) + '</td><td>' + esc(t(cls ? 'kind_class' : 'kind_session')) + '</td><td class="num">' + esc(x.time || '') + '</td>' + cell(I18n.num(Number(x.minutes) || 0) + ' ' + esc(t('minutes'))) + '<td>' + esc(cls ? x.name : (x.subject || '')) + '</td><td>' + esc(x.place || '') + '</td></tr>');
        });
      });
      h.push('</tbody></table>');
    }
    h.push('<div class="foot">VOIDLOCK · Novum · v' + esc(root.Native ? root.Native.appVersion() : ((root.VOIDLOCK_CONFIG || {}).version || '')) + '</div></div></body></html>');

    // ---- CSV (Excel opens it with the UTF-8 mark, Persian text included)
    var cols = names.map(function (k) { return subj[k].name; });
    function q(x) { x = String(x === null || x === undefined ? '' : x); return /[",\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; }
    var csv = [[t('exam_date') + ' (Gregorian)', fa ? t('exam_date') + ' (Jalali)' : '', t('weekday'), t('total') + ' (' + t('minutes') + ')'].concat(cols.map(function (c) { return c + ' (' + t('minutes') + ')'; })).concat([t('tests_solved'), t('words_learned')])];
    rows.forEach(function (r) {
      var tl = 0, wd = 0, m = db.tests[r.dk], w = db.words[r.dk]; if (m) Object.keys(m).forEach(function (k) { tl += m[k]; }); if (w) Object.keys(w).forEach(function (k) { wd += w[k]; });
      var d = Core.parseDkey(r.dk), j = Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
      csv.push([r.dk, fa ? j.jy + '/' + j.jm + '/' + j.jd : '', I18n.dateStr(r.dk, true), Math.round(r.sec / 60)].concat(cols.map(function (c) { return Math.round((r.parts[c] || 0) / 60); })).concat([tl, wd]));
    });
    csv.push([], [t('summary')], [t('total'), Math.round(total / 60)], [t('avg_per_day'), Math.round(total / Math.max(1, days.length) / 60)],
      [t('avg_active_day'), Math.round(total / Math.max(1, studied) / 60)], [t('study_days'), studied], [t('streak'), streak], [t('goal_days'), goalDays],
      [t('best_day'), best.dk || '', Math.round(best.sec / 60)], [t('tests_solved'), testsTotal], [t('words_learned'), wordsTotal], [t('sessions_title'), sessions.length], [t('sessions_time'), Math.round(sessionSec / 60)]);
    if (names.length) {
      csv.push([], [t('subjects')], [t('subject'), t('time'), t('share'), t('col_avg_day'), t('tests_solved'), t('words_learned')]);
      names.forEach(function (k) {
        var s = subj[k], tt = 0, ww = 0; Object.keys(s.ids).forEach(function (id) { tt += testsBy[id] || 0; ww += wordsBy[id] || 0; });
        csv.push([s.name, Math.round(s.sec / 60), Math.round(s.sec / Math.max(1, total) * 100), Math.round(s.sec / Math.max(1, Object.keys(s.days).length) / 60), tt, ww]);
      });
    }
    if (sessions.length) {
      csv.push([], [t('sessions_title')], [t('when'), t('subject'), t('planned'), t('focused'), t('status'), t('blocked')]);
      sessions.forEach(function (s) { csv.push([new Date(Number(s.start) * 1000).toISOString(), s.subject || '', s.planned_min || 0, Math.round((s.focus_sec || 0) / 60), s.status || '', s.blocked_count || 0]); });
    }
    if (classRows.some(function (x) { return x.enabled !== false; }) || plannedRows.some(function (x) { return x.enabled !== false; })) {
      var dayLabels = fa ? ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه'] : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
      csv.push([], [t('schedule_title')], [t('weekday'), t('kind'), t('when'), t('planned'), t('subject'), t('place')]);
      order.forEach(function (day) { classRows.concat(plannedRows).filter(function (x) { return x.enabled !== false && Number(x.day) === day; }).sort(function (a, b) { return String(a.time).localeCompare(String(b.time)); }).forEach(function (x) {
        var cls = classRows.indexOf(x) >= 0; csv.push([dayLabels[day], t(cls ? 'kind_class' : 'kind_session'), x.time, x.minutes, cls ? x.name : (x.subject || ''), x.place || '']);
      }); });
    }
    if (reportExams.length) {
      csv.push([]); csv.push([t('exam_name'), t('exam_date'), t('total_taraz'), t('overall_rank'), t('region_rank'), t('subject'), t('percent'), t('taraz')]);
      reportExams.forEach(function (e) {
        var r = e.result || {};
        if ((r.subjects || []).length) r.subjects.forEach(function (x, i) { csv.push([e.name, e.date, i ? '' : r.taraz, i ? '' : r.rank, i ? '' : r.rank_region, x.name, x.pct, x.taraz]); });
        else csv.push([e.name, e.date, r.taraz, r.rank, r.rank_region, '', '', '']);
      });
    }
    return { html: h.join(''), csv: '\uFEFF' + csv.map(function (r) { return r.map(q).join(','); }).join('\r\n'), title: title, base: 'voidlock-report-' + from.replace(/-/g, '') + '-' + to.replace(/-/g, '') };
  }
  root.Report = { build: build };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.Report;
})(typeof window !== 'undefined' ? window : globalThis);
