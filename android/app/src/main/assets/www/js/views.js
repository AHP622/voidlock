/* Views: Today, Stats, Tasks. Each view builds DOM into `host`; App (app.js) owns the data and re-renders after changes. */
(function (root) {
  'use strict';
  var h = UI.h, t = function (k, v) { return I18n.t(k, v); };
  var Views = root.Views = root.Views || {};

  function subjectDot(color) { return h('span', { class: 'dot', style: { '--c': color } }); }
  function card(title, kids, cls) { return h('section', { class: 'card ' + (cls || '') }, title ? h('h3', null, title) : null, kids); }

  // ------------------------------------------------------------------ sheets used by Today
  function manualSheet(App, preset) {
    var db = App.db;
    if (!db.subjects.length) return subjectSheet(App, null);
    var sid = preset || db.settings.last_subject || db.subjects[0].id;
    var sel = h('select', null, db.subjects.map(function (s) { return h('option', { value: s.id }, s.name); }));
    sel.value = db.subject ? sid : sid;
    if (!Core.subject(db, sid)) sel.value = db.subjects[0].id; else sel.value = sid;
    var mins = h('input', { type: 'number', inputmode: 'numeric', min: 1, max: 1440, placeholder: '60', value: '60' });
    var dayf = UI.dateField(Core.dkey());
    var quick = h('div', { class: 'row', style: { marginTop: '8px', flexWrap: 'wrap' } }, [15, 30, 45, 60, 90, 120].map(function (m) {
      return h('button', { class: 'btn sm', type: 'button', onclick: function () { mins.value = m; } }, I18n.digits(m));
    }));
    var s = UI.sheet({ title: t('manual_title'),
      body: [UI.field(t('subject'), sel), UI.field(t('how_long'), mins), quick, UI.field(t('which_day'), dayf.el)],
      actions: [h('button', { class: 'btn', onclick: function () { s.close(); } }, t('cancel')),
        h('button', { class: 'btn primary', onclick: function () {
          var m = parseFloat(String(mins.value).replace(/[٠-٩]/g, function (d) { return d.charCodeAt(0) - 1632; }));
          if (!(m > 0) || m > 1440) return UI.toast(t('check_numbers'), 'warn');
          Core.addManual(db, Core.parseDkey(dayf.get()), sel.value, m);
          db.settings.last_subject = sel.value; App.changed(); s.close(); UI.toast(t('saved'), 'success');
        } }, t('save'))] });
  }

  function subjectSheet(App, subj) {
    var db = App.db, nameIn = h('input', { type: 'text', maxlength: 24, placeholder: t('subject_name'), value: subj ? subj.name : '' });
    var cf = UI.colorField(subj ? subj.color : Core.SUBJECT_COLORS[db.subjects.length % Core.SUBJECT_COLORS.length]);
    var tests = h('input', { type: 'checkbox' }), words = h('input', { type: 'checkbox' });
    tests.checked = subj ? subj.tests !== false : true; words.checked = subj ? !!subj.words : false;
    function toggleRow(label, cb) { return h('label', { class: 'row sb', style: { padding: '10px 0' } }, h('span', null, label), cb); }
    var body = [UI.field(t('name'), nameIn), UI.field(t('color'), cf.el), h('div', { style: { marginTop: '10px' } },
      toggleRow(t('tests_solved'), tests), toggleRow(t('words_learned'), words))];
    var acts = [];
    if (subj) acts.push(h('button', { class: 'btn danger', onclick: function () {
      UI.confirm(t('delete_subject'), t('delete_subject_msg', { name: subj.name }), t('delete'), true).then(function (ok) {
        if (ok) { Core.removeSubject(db, subj.id); App.changed(); s.close(); }
      });
    } }, t('delete')));
    acts.push(h('button', { class: 'btn primary', onclick: function () {
      var name = nameIn.value.trim(); if (!name) return UI.toast(t('enter_name'), 'warn');
      var dup = db.subjects.find(function (x) { return x.name.trim().toLowerCase() === name.toLowerCase() && (!subj || x.id !== subj.id); });
      if (dup) return UI.toast(t('name_taken'), 'warn');
      if (subj) Core.editSubject(db, subj.id, { name: name, color: cf.get(), tests: tests.checked, words: words.checked });
      else { var n = Core.addSubject(db, name, cf.get(), { tests: tests.checked, words: words.checked }); db.settings.last_subject = n.id; }
      App.changed(); s.close();
    } }, t('save')));
    var s = UI.sheet({ title: subj ? t('edit_subject') : t('add_subject'), body: body, actions: acts });
    setTimeout(function () { if (!subj) nameIn.focus(); }, 300);
  }
  Views.subjectSheet = subjectSheet; Views.manualSheet = manualSheet;

  // ------------------------------------------------------------------ Today
  Views.today = function (host, App) {
    var db = App.db, today = Core.dkey(), goal = (db.settings.goal_min || 120) * 60;
    var sel = db.settings.last_subject; if (!Core.subject(db, sel)) sel = db.subjects[0] ? db.subjects[0].id : null;
    var running = db.active && Core.subject(db, db.active.subject) ? db.active : null;
    if (running) sel = running.subject;
    var total = Core.daySec(db, today), el = {};
    el.ring = h('div', { class: 'grow', style: { textAlign: 'center' } });
    function drawRing() { var tot = Core.daySec(db, today); el.ring.innerHTML = Charts.ring(goal ? tot / goal : 0, 170, I18n.dur(tot), t('of_goal', { goal: I18n.dur(goal) })); }
    drawRing(); el.drawRing = drawRing;
    host.appendChild(card(null, [el.ring]));

    if (!db.subjects.length) {
      host.appendChild(card(null, [h('div', { class: 'empty' }, t('no_subjects')), h('button', { class: 'btn primary block', onclick: function () { subjectSheet(App, null); } }, t('add_subject'))]));
    } else {
      var chips = h('div', { class: 'chips' }, db.subjects.map(function (s) {
        return h('button', { class: 'chip' + (s.id === sel ? ' on' : ''), style: { '--c': s.color }, disabled: running && s.id !== sel, onclick: function () {
          if (running) return; db.settings.last_subject = s.id; App.refresh(); } }, subjectDot(s.color), s.name);
      }));
      el.clock = h('div', { class: 'timer num' }, I18n.clock(running ? Core.elapsed(db) : 0));
      el.hint = h('div', { class: 'small dim', style: { textAlign: 'center' } }, running ? t('running') + ' · ' + Core.subjectOrGhost(db, running.subject).name : t('timer_hint'));
      var go = h('button', { class: 'btn primary block', style: { minHeight: '56px', fontSize: '17px' }, onclick: function () {
        if (running) { Core.stopTimer(db); App.changed(); }
        else if (sel) { Core.startTimer(db, sel); db.settings.last_subject = sel; App.changed(); }
        else UI.toast(t('pick_subject'), 'warn');
      } }, UI.ic(running ? 'stop' : 'play'), running ? t('stop') : t('start'));
      host.appendChild(card(null, [chips, el.clock, el.hint, h('div', { style: { height: '12px' } }), go,
        h('div', { style: { height: '10px' } }), h('button', { class: 'btn block', onclick: function () { manualSheet(App, sel); } }, UI.ic('plus'), t('add_time'))]));

      var times = Core.daySubjectTimes(db, today), by = {}; times.forEach(function (x) { by[x.subject.id] = x.sec; });
      function subjectRow(s) {
        var sec = by[s.id] || 0;
        return h('div', { class: 'item' },
          h('div', { class: 'grow', onclick: function () { if (!running) { db.settings.last_subject = s.id; App.refresh(); } } },
            h('div', { class: 'row' }, subjectDot(s.color), h('b', null, s.name), h('span', { class: 'muted small num', style: { marginInlineStart: 'auto' } }, I18n.dur(sec))),
            h('div', { class: 'bar', style: { '--c': s.color, marginTop: '6px' } }, h('i', { style: { width: Math.min(100, goal ? sec / goal * 100 * Math.max(1, db.subjects.length / 2) : 0) + '%' } }))),
          stepper(db, App, 'tests', s, today, s.tests !== false), stepper(db, App, 'words', s, today, !!s.words));
      }
      // subjects with a tests counter and subjects with a words counter are two separate groups, so they do not get mixed up
      var testSubjects = db.subjects.filter(function (s) { return !s.words; }), wordSubjects = db.subjects.filter(function (s) { return !!s.words; });
      var groups = [];
      if (testSubjects.length) groups.push(h('div', { class: 'group' }, wordSubjects.length ? h('div', { class: 'group-title' }, t('group_tests')) : null, h('div', { class: 'list' }, testSubjects.map(subjectRow))));
      if (wordSubjects.length) groups.push(h('div', { class: 'group' }, h('div', { class: 'group-title' }, t('group_words')), h('div', { class: 'list' }, wordSubjects.map(subjectRow))));
      host.appendChild(card(t('by_subject'), groups));
      var ents = db.entries.filter(function (e) { return e.date === today; }).sort(function (a, b) { return (b.t || 0) - (a.t || 0); });
      host.appendChild(card(t('entries_today'), ents.length ? h('div', { class: 'list' }, ents.map(function (e) {
        var s = Core.subjectOrGhost(db, e.subject);
        return h('div', { class: 'item' }, subjectDot(s.color), h('div', { class: 'grow' }, h('b', null, I18n.subjName(s)), h('div', { class: 'small dim' }, I18n.dur(e.sec) + (e.source === 'manual' ? ' · ✎' : ''))),
          h('button', { class: 'icon-btn', 'aria-label': t('delete'), html: UI.icon('trash'), onclick: function () { Core.removeEntry(db, e.id); App.changed(); } }));
      })) : h('div', { class: 'empty' }, t('no_entries'))));
      if (db.sessions.some(function (r) { return Core.dkey(new Date(r.start * 1000)) === today; })) host.appendChild(h('div', { class: 'small dim', style: { textAlign: 'center', marginBottom: '10px' } }, t('sessions_note')));
    }
    App.tick = function () {
      var r = db.active && Core.subject(db, db.active.subject);
      if (el.clock && r) el.clock.textContent = I18n.clock(Core.elapsed(db));
      if (el.drawRing) el.drawRing();
    };
  };
  function stepper(db, App, kind, s, day, show) {
    if (!show) return null;
    var n = Core.counter(db, kind, day, s.id);
    return h('div', { class: 'col', style: { alignItems: 'center', gap: '2px' } }, h('span', { class: 'dim', style: { fontSize: '10.5px' } }, t(kind === 'tests' ? 'tests_solved' : 'words_learned')),
      h('div', { class: 'stepper' }, h('button', { 'aria-label': '-', onclick: function () { Core.setCounter(db, kind, day, s.id, Core.counter(db, kind, day, s.id) - 1); App.changed(); } }, '−'),
        h('b', { class: 'num' }, I18n.digits(n)), h('button', { 'aria-label': '+', onclick: function () { Core.setCounter(db, kind, day, s.id, Core.counter(db, kind, day, s.id) + 1); App.changed(); } }, '+')));
  }

  // ------------------------------------------------------------------ Stats
  Views.stats = function (host, App) {
    var db = App.db, fa = I18n.lang === 'fa', n = App.range || 14, today = new Date();
    var seg = h('div', { class: 'seg' }, [7, 14, 30, 60].map(function (r) {
      return h('button', { class: r === n ? 'on' : '', onclick: function () { App.range = r; App.render(); } }, t('last_days', { n: I18n.digits(r) }));
    }));
    host.appendChild(h('div', { style: { margin: '4px 0 14px' } }, seg));
    var examDays = {}; db.exams.forEach(function (e) { examDays[e.date] = e.name; });
    var days = [], sum = 0, best = { sec: 0, dk: null }, active = 0, subjTot = {};
    for (var i = n - 1; i >= 0; i--) {
      var d = Core.addDays(today, -i), dk = Core.dkey(d), parts = Core.daySubjectTimes(db, dk), sec = Core.daySec(db, dk);
      var first = (fa ? Jalali.toJalali(d.getFullYear(), d.getMonth() + 1, d.getDate()).jd : d.getDate()) === 1;
      days.push({ dk: dk, label: I18n.dayShort(dk), month: first || i === n - 1 ? I18n.monthShort(dk) : '', exam: !!examDays[dk], sec: sec, tip: I18n.dateStr(dk, true),
        parts: parts.map(function (x) { return { name: I18n.subjName(x.subject), color: x.subject.color, sec: x.sec }; }) });
      sum += sec; if (sec > best.sec) best = { sec: sec, dk: dk }; if (sec > 0) active++;
      parts.forEach(function (x) { var k = I18n.subjName(x.subject); subjTot[k] = subjTot[k] || { color: x.subject.color, sec: 0 }; subjTot[k].sec += x.sec; });
    }
    // a month label only on the first bar of a month (the first bar always carries one)
    var W = Math.min(host.clientWidth || 340, 720) - 34;
    var ch = Charts.studyChart({ t: t, fa: fa, days: days, goalSec: (db.settings.goal_min || 120) * 60, width: Math.max(300, W) });
    host.appendChild(card(t('daily_study'), [h('div', { html: ch.svg }), h('div', { class: 'row', style: { flexWrap: 'wrap', gap: '8px 14px', marginTop: '8px' } }, ch.legend.map(function (l) {
      return h('span', { class: 'row small muted', style: { gap: '6px' } }, l.dashed ? h('span', { style: { width: '16px', borderTop: '2px dashed ' + l.color, display: 'inline-block' } }) : subjectDot(l.color), l.name); }).concat(examDaysAny(days) ? [h('span', { class: 'row small muted', style: { gap: '6px' } },
      h('span', { style: { color: 'var(--amber)' } }, '▼'), t('exam_day'))] : []))]));
    var streak = 0; for (var k = days.length - 1; k >= 0 && days[k].sec >= 600; k--) streak++;
    host.appendChild(card(null, h('div', { class: 'stat-grid' },
      stat(I18n.dur(sum), t('total')), stat(I18n.dur(sum / Math.max(1, n)), t('avg_per_day')),
      stat(best.dk ? I18n.dur(best.sec) : '-', t('best_day') + (best.dk ? ' · ' + I18n.dateStr(best.dk) : '')), stat(I18n.digits(streak) + ' / ' + I18n.digits(active), t('streak') + ' / ' + t('study_days')))));
    var names = Object.keys(subjTot).sort(function (a, b) { return subjTot[b].sec - subjTot[a].sec; });
    if (names.length) host.appendChild(card(t('subject_share'), h('div', { class: 'list' }, names.map(function (nm) {
      var v = subjTot[nm];
      return h('div', { class: 'item' }, h('div', { class: 'grow' }, h('div', { class: 'row' }, subjectDot(v.color), h('b', null, nm), h('span', { class: 'muted small num', style: { marginInlineStart: 'auto', display: 'flex', gap: '10px' } }, h('span', null, I18n.dur(v.sec)), h('b', null, I18n.digits(Math.round(v.sec / Math.max(1, sum) * 100)) + (I18n.lang === 'fa' ? '٪' : '%')))),
        h('div', { class: 'bar', style: { '--c': v.color, marginTop: '6px' } }, h('i', { style: { width: (v.sec / Math.max(1, sum) * 100) + '%' } }))));
    }))));
  };
  function examDaysAny(days) { return days.some(function (d) { return d.exam; }); }
  function stat(v, label) { return h('div', { class: 'stat' }, h('b', { class: 'num' }, v), h('span', null, label)); }

  // ------------------------------------------------------------------ Tasks
  Views.tasks = function (host, App) {
    var db = App.db, today = Core.dkey(), day = App.taskDay || today, fa = I18n.lang === 'fa';
    var seg = h('div', { class: 'seg' },
      h('button', { class: day === today ? 'on' : '', onclick: function () { App.taskDay = today; App.render(); } }, t('today')),
      h('button', { class: day === dayAfter(today, 1) ? 'on' : '', onclick: function () { App.taskDay = dayAfter(today, 1); App.render(); } }, t('tomorrow')),
      h('button', { class: day !== today && day !== dayAfter(today, 1) ? 'on' : '', onclick: function () {
        var df = UI.dateField(day); var s = UI.sheet({ title: t('pick_date'), body: df.el, actions: [h('button', { class: 'btn primary', onclick: function () { App.taskDay = df.get(); s.close(); App.render(); } }, t('select'))] });
      } }, t('pick_date')));
    host.appendChild(h('div', { style: { margin: '4px 0 6px' } }, seg));
    host.appendChild(h('div', { class: 'small dim', style: { margin: '0 4px 12px' } }, I18n.dateStr(day, true)));
    var inp = h('input', { type: 'text', placeholder: t('add_task'), maxlength: 160 });
    function add() { var v = inp.value.trim(); if (!v) return; Core.addTodo(db, Core.parseDkey(day), v); App.changed(); }
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') add(); });
    host.appendChild(card(null, h('div', { class: 'row' }, h('div', { class: 'grow' }, inp), h('button', { class: 'btn primary', 'aria-label': t('add'), onclick: add }, UI.ic('plus')))));
    var todays = db.todos.filter(function (x) { return x.date === day; });
    host.appendChild(card(null, todays.length ? h('div', { class: 'list' }, todays.map(function (x) { return todoRow(App, x); })) : h('div', { class: 'empty' }, t('no_tasks'))));
    if (day === today) {
      var old = db.todos.filter(function (x) { return x.date < today && !x.done; }).sort(function (a, b) { return a.date < b.date ? 1 : -1; }).slice(0, 30);
      if (old.length) host.appendChild(card(t('open_before'), h('div', { class: 'list' }, old.map(function (x) { return todoRow(App, x, true); }))));
    }
  };
  function dayAfter(dk, n) { return Core.dkey(Core.addDays(Core.parseDkey(dk), n)); }
  function todoRow(App, x, showDate) {
    return h('div', { class: 'item' },
      h('button', { class: 'check' + (x.done ? ' on' : ''), 'aria-label': 'toggle', html: x.done ? UI.icon('check') : '', onclick: function () { Core.toggleTodo(App.db, x.id); App.changed(); } }),
      h('div', { class: 'grow' }, h('div', { class: x.done ? 'done' : '' }, x.text), showDate ? h('div', { class: 'small dim' }, I18n.dateStr(x.date)) : null),
      h('button', { class: 'icon-btn', 'aria-label': t('delete'), html: UI.icon('trash'), onclick: function () { Core.removeTodo(App.db, x.id); App.changed(); } }));
  }
})(typeof window !== 'undefined' ? window : globalThis);
