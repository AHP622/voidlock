/* Exams: countdown, progress charts (total taraz / rank / region rank / per subject), results form and the exam subjects. */
(function (root) {
  'use strict';
  var h = UI.h, t = function (k, v) { return I18n.t(k, v); };
  var Views = root.Views = root.Views || {};

  function parseNum(s) {
    s = String(s === undefined || s === null ? '' : s).trim();
    if (!s) return null;
    s = s.replace(/[۰-۹]/g, function (d) { return d.charCodeAt(0) - 1776; }).replace(/[٠-٩]/g, function (d) { return d.charCodeAt(0) - 1632; })
      .replace(/[٬,\s']/g, '').replace(/٫/g, '.').replace(/−/g, '-');
    var n = Number(s); return isFinite(n) ? n : NaN;
  }
  Views.parseNum = parseNum;
  function numInput(value, ph) {
    return h('input', { type: 'text', inputmode: 'decimal', placeholder: ph, value: value === null || value === undefined ? '' : String(value), style: { textAlign: 'center' } });
  }
  function daysFrom(dk) { return Math.round((Core.parseDkey(dk) - Core.parseDkey(Core.dkey())) / 86400000); }
  function dueText(dk) { var d = daysFrom(dk); return d === 0 ? t('today_exam') : (d > 0 ? t('days_left', { n: I18n.digits(d) }) : t('days_ago', { n: I18n.digits(-d) })); }

  function examSheet(App, ex) {
    var db = App.db, name = h('input', { type: 'text', maxlength: 40, placeholder: t('exam_name'), value: ex ? ex.name : '' });
    var df = UI.dateField(ex ? ex.date : Core.dkey()), tm = h('input', { type: 'time', value: ex && ex.time ? ex.time : '' });
    var acts = [];
    if (ex) acts.push(h('button', { class: 'btn danger', onclick: function () {
      UI.confirm(t('delete_exam'), ex.name, t('delete'), true).then(function (ok) { if (ok) { Core.removeExam(db, ex.id); App.changed(); s.close(); } });
    } }, t('delete')));
    acts.push(h('button', { class: 'btn primary', onclick: function () {
      var nm = name.value.trim(); if (!nm) return UI.toast(t('enter_name'), 'warn');
      if (ex) Core.updateExam(db, ex.id, { name: nm, date: df.get(), time: tm.value || '' }); else Core.addExam(db, nm, df.get(), tm.value || '');
      App.changed(); s.close();
    } }, t('save')));
    var s = UI.sheet({ title: ex ? t('edit_exam') : t('add_exam'), body: [UI.field(t('exam_name'), name), UI.field(t('exam_date'), df.el), UI.field(t('exam_time'), tm)], actions: acts });
    if (!ex) setTimeout(function () { name.focus(); }, 300);
  }

  function resultSheet(App, ex) {
    var db = App.db, old = ex.result || {}, rows = {};
    var oldBy = {}; (old.subjects || []).forEach(function (r) { oldBy[Core.examSubject(db, r.sid) ? r.sid : 'n:' + String(r.name || '').toLowerCase()] = r; });
    var total = numInput(old.taraz, t('total_taraz')), rank = numInput(old.rank, t('overall_rank')), region = numInput(old.rank_region, t('region_rank'));
    var note = h('input', { type: 'text', maxlength: 120, placeholder: t('note_optional'), value: old.note || '' });
    var list = h('div', { class: 'col', style: { gap: '8px' } }), err = h('div', { class: 'small', style: { color: 'var(--red)', minHeight: '18px' } });
    function addRow(s) {
      var r = oldBy[s.id] || {}, pct = numInput(r.pct, '%'), tz = numInput(r.taraz, t('taraz'));
      rows[s.id] = { pct: pct, tz: tz };
      list.appendChild(h('div', { class: 'row' }, h('div', { class: 'row grow', style: { gap: '8px' } }, h('span', { class: 'dot', style: { '--c': s.color } }), h('b', null, s.name)),
        h('div', { style: { width: '92px' } }, pct), h('div', { style: { width: '104px' } }, tz)));
    }
    function build() { list.innerHTML = ''; rows = {}; if (!db.exam_subjects.length) list.appendChild(h('div', { class: 'small dim' }, t('no_exam_subjects'))); db.exam_subjects.forEach(addRow); }
    build();
    var newName = h('input', { type: 'text', maxlength: 24, placeholder: t('new_subject') });
    function addSubj() {
      var v = newName.value.trim(); if (!v) return;
      var keep = snapshot(); Core.addExamSubject(db, v); newName.value = ''; App.save(); build(); restore(keep);
    }
    function snapshot() { var o = {}; Object.keys(rows).forEach(function (k) { o[k] = [rows[k].pct.value, rows[k].tz.value]; }); return o; }
    function restore(o) { Object.keys(o).forEach(function (k) { if (rows[k]) { rows[k].pct.value = o[k][0]; rows[k].tz.value = o[k][1]; } }); }
    newName.addEventListener('keydown', function (e) { if (e.key === 'Enter') addSubj(); });
    var top = h('div', { class: 'row', style: { gap: '8px', alignItems: 'flex-end' } },
      [[t('total_taraz'), total], [t('overall_rank'), rank], [t('region_rank'), region]].map(function (p) { return h('div', { class: 'grow' }, h('label', { class: 'field', style: { marginTop: 0 } }, p[0]), p[1]); }));
    var acts = [];
    if (ex.result) acts.push(h('button', { class: 'btn danger', onclick: function () { Core.clearExamResult(db, ex.id); App.changed(); s.close(); } }, t('remove_result')));
    acts.push(h('button', { class: 'btn primary', onclick: function () {
      var bad = false, vals = {};
      function chk(inp, lo, hi) { var v = parseNum(inp.value); if (v !== null && (isNaN(v) || v < lo || v > hi)) bad = true; return v; }
      vals.taraz = chk(total, 0, 20000); vals.rank = chk(rank, 1, 5000000); vals.rank_region = chk(region, 1, 5000000);
      var subs = db.exam_subjects.map(function (sj) { var r = rows[sj.id]; return r ? { sid: sj.id, pct: chk(r.pct, -33.4, 100), taraz: chk(r.tz, 0, 20000) } : null; }).filter(Boolean);
      if (bad) { err.textContent = t('check_numbers'); return; }
      var extra = (old.subjects || []).filter(function (r) { return !Core.examSubject(db, r.sid); });          // rows of deleted exam subjects stay as they are
      vals.subjects = subs.concat(extra); vals.note = note.value;
      Core.setExamResult(db, ex.id, vals); App.changed(); s.close(); UI.toast(t('saved'), 'success');
    } }, t('save')));
    var s = UI.sheet({ title: t('results_title') + ' · ' + ex.name, message: t('results_hint'),
      body: [top, h('div', { style: { height: '12px' } }), list, h('div', { class: 'row', style: { marginTop: '10px' } }, h('div', { class: 'grow' }, newName),
        h('button', { class: 'btn soft', onclick: addSubj }, UI.ic('plus'), t('add'))), UI.field('', note), err], actions: acts });
  }

  function examSubjectSheet(App, sj) {
    var db = App.db, name = h('input', { type: 'text', maxlength: 24, value: sj ? sj.name : '', placeholder: t('new_subject') });
    var cf = UI.colorField(sj ? sj.color : Core.SUBJECT_COLORS[db.exam_subjects.length % Core.SUBJECT_COLORS.length]), acts = [];
    if (sj) acts.push(h('button', { class: 'btn danger', onclick: function () {
      UI.confirm(t('delete_subject'), t('delete_subject_msg', { name: sj.name }), t('delete'), true).then(function (ok) { if (ok) { Core.removeExamSubject(db, sj.id); App.changed(); s.close(); } });
    } }, t('delete')));
    acts.push(h('button', { class: 'btn primary', onclick: function () {
      var v = name.value.trim(); if (!v) return UI.toast(t('enter_name'), 'warn');
      var dup = db.exam_subjects.find(function (x) { return x.name.trim().toLowerCase() === v.toLowerCase() && (!sj || x.id !== sj.id); });
      if (dup) return UI.toast(t('name_taken'), 'warn');
      if (sj) Core.editExamSubject(db, sj.id, { name: v, color: cf.get() }); else Core.addExamSubject(db, v, cf.get());
      App.changed(); s.close();
    } }, t('save')));
    var s = UI.sheet({ title: sj ? t('edit_subject') : t('add_subject'), body: [UI.field(t('name'), name), UI.field(t('color'), cf.el)], actions: acts });
    if (!sj) setTimeout(function () { name.focus(); }, 300);
  }

  var KINDS = [['taraz', 'k_taraz'], ['rank', 'k_rank'], ['region', 'k_region'], ['subjects', 'k_subjects'], ['percent', 'k_percent']];
  function progressCard(App) {
    var db = App.db, ep = Core.examProgress(db), kind = App.examKind || 'taraz', fa = I18n.lang === 'fa';
    var seg = h('div', { class: 'seg' }, KINDS.map(function (k) { return h('button', { class: k[0] === kind ? 'on' : '', onclick: function () { App.examKind = k[0]; App.render(); } }, t(k[1])); }));
    var body = h('div'), W = Math.max(300, Math.min(root.innerWidth || 360, 720) - 34);
    if (!ep.exams.length) body.appendChild(h('div', { class: 'empty' }, t('no_results_yet')));
    else {
      var labels = ep.exams.map(function (e) { return e.name; }), series, opts = { t: t, fa: fa, labels: labels, width: W };
      if (kind === 'taraz') series = [{ name: t('k_taraz'), color: '#2DD4BF', values: ep.exams.map(function (e) { return e.taraz; }) }];
      else if (kind === 'rank') { series = [{ name: t('k_rank'), color: '#60A5FA', values: ep.exams.map(function (e) { return e.rank; }) }]; opts.invert = true; }
      else if (kind === 'region') { series = [{ name: t('k_region'), color: '#A78BFA', values: ep.exams.map(function (e) { return e.rank_region; }) }]; opts.invert = true; }
      else {
        var idx = kind === 'percent' ? 1 : 2;
        series = ep.subjects.map(function (s) { var v = ep.exams.map(function () { return null; }); s.points.forEach(function (p) { v[p[0]] = p[idx]; }); return { name: s.name, color: s.color, values: v }; });
        if (kind === 'percent') opts.dec = 1;
      }
      opts.series = series;
      var ch = Charts.lineChart(opts);
      if (!ch.svg) body.appendChild(h('div', { class: 'empty' }, t('no_results_yet')));
      else {
        body.appendChild(h('div', { html: ch.svg }));
        if (opts.invert) body.appendChild(h('div', { class: 'small dim', style: { textAlign: 'center' } }, t('rank_hint')));
        if (ch.legend.length) body.appendChild(h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '8px 14px', marginTop: '8px' } }, ch.legend.map(function (l) { return h('span', { class: 'row small muted', style: { gap: '6px' } }, h('span', { class: 'dot', style: { '--c': l.color } }), l.name); })));
      }
    }
    return h('section', { class: 'card' }, h('h3', null, t('progress')), seg, h('div', { style: { height: '10px' } }), body);
  }

  Views.exams = function (host, App) {
    var db = App.db, nx = Core.nextExam(db), list = Core.exams(db), fa = I18n.lang === 'fa';
    if (nx) host.appendChild(h('section', { class: 'card', style: { background: 'linear-gradient(135deg,color-mix(in srgb,var(--accent) 16%,var(--panel)),var(--panel))' } },
      h('h3', null, t('next_exam')), h('div', { class: 'row sb' }, h('div', null, h('b', { style: { fontSize: '18px' } }, nx.exam.name), h('div', { class: 'small muted' }, I18n.dateStr(nx.exam.date, true) + (nx.exam.time ? ' · ' + I18n.digits(nx.exam.time) : ''))),
        h('div', { class: 'pill', style: { '--c': nx.days <= 3 ? 'var(--amber)' : 'var(--accent)', fontSize: '14px', padding: '6px 14px' } }, dueText(nx.exam.date)))));
    host.appendChild(progressCard(App));
    var items = list.map(function (e) {
      var r = e.result, pills = [];
      if (r) {
        if (r.taraz !== null && r.taraz !== undefined) pills.push(h('span', { class: 'pill', style: { '--c': '#2DD4BF' } }, t('taraz') + ' ' + I18n.num(r.taraz)));
        if (r.rank !== null && r.rank !== undefined) pills.push(h('span', { class: 'pill', style: { '--c': '#60A5FA' } }, t('rank_word') + ' ' + I18n.num(r.rank)));
        if (r.rank_region !== null && r.rank_region !== undefined) pills.push(h('span', { class: 'pill', style: { '--c': '#4ADE80' } }, t('region_word') + ' ' + I18n.num(r.rank_region)));
      }
      var past = daysFrom(e.date) < 0;
      return h('div', { class: 'item', style: { alignItems: 'flex-start' } },
        h('div', { class: 'grow' }, h('div', { class: 'row sb' }, h('b', null, e.name), h('span', { class: 'small', style: { color: daysFrom(e.date) >= 0 && daysFrom(e.date) <= 3 ? 'var(--amber)' : 'var(--text3)' } }, dueText(e.date))),
          h('div', { class: 'small muted' }, I18n.dateStr(e.date, true) + (e.time ? ' · ' + I18n.digits(e.time) : '')),
          pills.length ? h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '6px', marginTop: '6px' } }, pills) : null,
          h('div', { class: 'row', style: { marginTop: '10px', gap: '8px' } },
            h('button', { class: 'btn sm ' + (r ? '' : 'primary'), onclick: function () { resultSheet(App, e); } }, UI.ic('check'), r ? t('edit_results') : t('enter_results')),
            h('button', { class: 'btn sm', onclick: function () { examSheet(App, e); } }, UI.ic('edit'), t('edit')))));
    });
    host.appendChild(h('section', { class: 'card' }, h('h3', null, t('exams')), items.length ? h('div', { class: 'list' }, items) : h('div', { class: 'empty' }, t('no_exams'))));
    var chips = h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '8px' } }, db.exam_subjects.map(function (s) {
      return h('button', { class: 'chip', style: { '--c': s.color }, onclick: function () { examSubjectSheet(App, s); } }, h('span', { class: 'dot', style: { '--c': s.color } }), s.name);
    }).concat([h('button', { class: 'chip', onclick: function () { examSubjectSheet(App, null); } }, UI.ic('plus'), t('add'))]));
    host.appendChild(h('section', { class: 'card' }, h('h3', null, t('exam_subjects')), h('div', { class: 'small dim', style: { marginBottom: '10px' } }, t('exam_subjects_hint')), chips));
    host.appendChild(h('button', { class: 'fab', 'aria-label': t('add_exam'), html: UI.icon('plus'), onclick: function () { examSheet(App, null); } }));
  };
})(typeof window !== 'undefined' ? window : globalThis);
