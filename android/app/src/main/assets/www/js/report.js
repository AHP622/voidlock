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
    '@page{size:A4;margin:12mm}@media print{.page{padding:0}h2{break-after:avoid}table,svg{break-inside:avoid}}@media(max-width:560px){.grid{grid-template-columns:1fr 1fr}}';

  function rangeDays(from, to) {
    var out = [], d = Core.parseDkey(from), end = Core.parseDkey(to), n = 0;
    while (d <= end && n++ < 800) { out.push(Core.dkey(d)); d = Core.addDays(d, 1); }
    return out;
  }
  function legendHtml(items) {
    return '<div class="leg">' + items.map(function (l) {
      return '<span>' + (l.dashed ? '<span style="display:inline-block;width:16px;border-top:2px dashed ' + l.color + ';margin-inline-end:6px;vertical-align:middle"></span>' : '<span class="dot" style="background:' + l.color + '"></span>') + esc(l.name) + '</span>';
    }).join('') + '</div>';
  }
  function cell(x) { return '<td class="num">' + x + '</td>'; }

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

  function build(db, from, to) {
    var fa = I18n.lang === 'fa', days = rangeDays(from, to), goalSec = (db.settings.goal_min || 120) * 60;
    var total = 0, best = { sec: 0, dk: null }, studied = 0, streak = 0, run = 0, subj = {}, testsBy = {}, wordsBy = {}, rows = [];
    days.forEach(function (dk) {
      var sec = Core.daySec(db, dk, false); total += sec; if (sec > best.sec) best = { sec: sec, dk: dk };
      if (sec > 0) studied++; if (sec >= 600) { run++; streak = Math.max(streak, run); } else run = 0;
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
    h.push('<h1>VOIDLOCK · ' + esc(title) + '</h1><div class="sub">' + esc(period) + ' · ' + esc(t('generated')) + ' ' + esc(I18n.dateStr(Core.dkey())) + '</div>');
    h.push('<div class="grid">' + [[I18n.dur(total), t('total')], [I18n.dur(total / Math.max(1, days.length)), t('avg_per_day')], [best.dk ? I18n.dur(best.sec) : '-', t('best_day') + (best.dk ? ' · ' + I18n.dateStr(best.dk) : '')],
      [I18n.digits(studied) + ' / ' + I18n.digits(days.length), t('study_days')], [I18n.digits(streak), t('streak')], [I18n.num(testsTotal), t('tests_solved')], [I18n.num(wordsTotal), t('words_learned')], [I18n.digits(names.length), t('subjects')]]
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
    var exs = Core.exams(db).filter(function (e) { return e.date >= from && e.date <= to; });
    var withRes = exs.filter(function (e) { return e.result; });
    if (exs.length) {
      h.push('<h2>' + esc(t('exams')) + '</h2><table><tr><th>' + esc(t('exam_name')) + '</th><th>' + esc(t('exam_date')) + '</th><th>' + esc(t('total_taraz')) + '</th><th>' + esc(t('overall_rank')) + '</th><th>' + esc(t('region_rank')) + '</th><th>' + esc(t('percent')) + '</th></tr>' +
        exs.map(function (e) {
          var r = e.result || {}, pcts = (r.subjects || []).filter(function (x) { return x.pct !== null && x.pct !== undefined; }).map(function (x) { return x.pct; });
          return '<tr><td>' + esc(e.name) + '</td>' + cell(esc(I18n.dateStr(e.date))) + cell(r.taraz != null ? I18n.num(r.taraz) : '-') + cell(r.rank != null ? I18n.num(r.rank) : '-') + cell(r.rank_region != null ? I18n.num(r.rank_region) : '-') +
            cell(pcts.length ? I18n.num(pcts.reduce(function (a, b) { return a + b; }, 0) / pcts.length, 1) : '-') + '</tr>';
        }).join('') + '</table>');
    }
    if (withRes.length) {
      var view = { exams: withRes, exam_subjects: db.exam_subjects }, ep = Core.examProgress(view), labels = ep.exams.map(function (e) { return e.name; });
      function lc(name, series, invert) {
        var c = Charts.lineChart({ t: t, fa: fa, labels: labels, series: series, invert: invert, width: 720, height: 220 });
        if (c.svg) h.push('<h2>' + esc(name) + (invert ? ' <small style="color:#7b8190;font-weight:400">(' + esc(t('rank_hint')) + ')</small>' : '') + '</h2>' + c.svg + legendHtml(c.legend));
      }
      lc(t('k_taraz'), [{ name: t('k_taraz'), color: '#0e9f8e', values: ep.exams.map(function (e) { return e.taraz; }) }]);
      lc(t('k_rank'), [{ name: t('k_rank'), color: '#2563eb', values: ep.exams.map(function (e) { return e.rank; }) }], true);
      lc(t('k_region'), [{ name: t('k_region'), color: '#7c3aed', values: ep.exams.map(function (e) { return e.rank_region; }) }], true);
      lc(t('k_subjects'), ep.subjects.map(function (s) { var v = ep.exams.map(function () { return null; }); s.points.forEach(function (p) { v[p[0]] = p[2]; }); return { name: s.name, color: s.color, values: v }; }));
    }
    h.push('<div class="foot">VOIDLOCK</div></div></body></html>');

    // ---- CSV (Excel opens it with the UTF-8 mark, Persian text included)
    var cols = names.map(function (k) { return subj[k].name; });
    function q(x) { x = String(x === null || x === undefined ? '' : x); return /[",\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x; }
    var csv = [[t('exam_date') + ' (Gregorian)', fa ? t('exam_date') + ' (Jalali)' : '', t('total') + ' (' + t('minutes') + ')'].concat(cols.map(function (c) { return c + ' (' + t('minutes') + ')'; })).concat([t('tests_solved'), t('words_learned')])];
    rows.forEach(function (r) {
      var tl = 0, wd = 0, m = db.tests[r.dk], w = db.words[r.dk]; if (m) Object.keys(m).forEach(function (k) { tl += m[k]; }); if (w) Object.keys(w).forEach(function (k) { wd += w[k]; });
      var d = Core.parseDkey(r.dk), j = Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate());
      csv.push([r.dk, fa ? j.jy + '/' + j.jm + '/' + j.jd : '', Math.round(r.sec / 60)].concat(cols.map(function (c) { return Math.round((r.parts[c] || 0) / 60); })).concat([tl, wd]));
    });
    if (exs.length) {
      csv.push([]); csv.push([t('exam_name'), t('exam_date'), t('total_taraz'), t('overall_rank'), t('region_rank'), t('subject'), t('percent'), t('taraz')]);
      exs.forEach(function (e) {
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
