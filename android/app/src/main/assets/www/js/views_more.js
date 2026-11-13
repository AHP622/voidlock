/* More: sync with the computer (Wi-Fi + file), study subjects, settings, about / updates. */
(function (root) {
  'use strict';
  var h = UI.h, t = function (k, v) { return I18n.t(k, v); };
  var Views = root.Views = root.Views || {};
  var ERR = { 'That file is not a VOIDLOCK sync file.': 'err_not_sync', 'This file was made by this same device.': 'err_same', 'That sync file has no device id.': 'err_nodev',
              'The file has no data.': 'err_nodata' };
  function syncErr(e) {
    var m = String(e && e.message || e);
    if (ERR[m]) return t(ERR[m]);
    if (m.indexOf('different version') >= 0) return t('err_version');
    return m;
  }
  function card(title, kids) { return h('section', { class: 'card' }, title ? h('h3', null, title) : null, kids); }
  function seg(items, cur, on) { return h('div', { class: 'seg' }, items.map(function (i) { return h('button', { class: i[0] === cur ? 'on' : '', onclick: function () { on(i[0]); } }, i[1]); })); }

  // ------------------------------------------------------------------ summaries of an import
  function planLines(plan) {
    var names = { entries: 'k_entries', subjects: 'k_subjects_n', exams: 'k_exams_n', exam_subjects: 'k_exam_subjects_n', todos: 'k_todos_n', sessions: 'k_sessions_n', classes: 'k_classes_n' }, lines = [];
    [['new_here', 'added'], ['changed', 'updated'], ['removed_here', 'removed']].forEach(function (p) {
      var items = Object.keys(names).filter(function (k) { return plan.stats[k][p[1]]; }).map(function (k) { return I18n.num(plan.stats[k][p[1]]) + ' ' + t(names[k]); });
      var c = plan.stats.tests[p[1]] + plan.stats.words[p[1]]; if (c) items.push(I18n.num(c) + ' ' + t('k_counts'));
      if (items.length) lines.push(t(p[0]) + ': ' + items.join(I18n.lang === 'fa' ? '، ' : ', '));
    });
    return lines;
  }
  function importText(App, text) {
    var db = App.db, plan;
    try { plan = Core.prepare(db, text); } catch (e) { return UI.toast(syncErr(e), 'error'); }
    App.save();
    if (plan.changes() === 0) return UI.toast(t('up_to_date'), 'info');
    var body = h('div', { class: 'col' }, h('div', { class: 'muted small' }, t('from') + ': ' + plan.peer.name),
      planLines(plan).map(function (l) { return h('div', null, l); }), plan.warn.length ? h('div', { class: 'banner' }, t('big_remove')) : null);
    var s = UI.sheet({ title: t('import_q'), body: body, actions: [h('button', { class: 'btn', onclick: function () { s.close(); } }, t('cancel')),
      h('button', { class: 'btn ' + (plan.warn.length ? 'danger' : 'primary'), onclick: function () { Core.commit(db, plan); App.changed(); s.close(); UI.toast(t('synced_ok'), 'success'); } }, t('import_btn'))] });
  }
  Views.importText = importText;

  // ------------------------------------------------------------------ pairing with the computer
  function pairFlow(App) {
    var db = App.db, body = h('div'), s, scanning = false, found = [], cancelled = false;
    function listStep() {
      body.innerHTML = '';
      var status = h('div', { class: 'small muted', style: { margin: '6px 0 10px' } }, scanning ? t('finding') : '');
      var res = h('div', { class: 'col' });
      var addr = h('input', { type: 'text', class: 'hex', placeholder: t('address_ph'), inputmode: 'url', autocapitalize: 'none', spellcheck: 'false' });
      function drawFound() {
        res.innerHTML = '';
        found.forEach(function (f) { res.appendChild(h('button', { class: 'btn block', style: { justifyContent: 'space-between' }, onclick: function () { if ((f.proto || 1) < 2) return UI.toast(t('proto_old'), 'error'); codeStep(f.addr, f.device.name); } }, h('span', null, f.device.name), h('span', { class: 'dim small hex' }, f.addr))); });
        if (!scanning && !found.length) res.appendChild(h('div', { class: 'banner' }, t('none_found'), h('div', { style: { marginTop: '6px' } }, t('vpn_hint'))));
      }
      body.append(h('div', { class: 'small dim' }, t('wifi_hint')), status, res, h('label', { class: 'field' }, t('enter_address')),
        h('div', { class: 'row' }, h('div', { class: 'grow' }, addr), h('button', { class: 'btn soft', onclick: function () {
          var v = addr.value.trim(); if (!v) return; if (v.indexOf(':') < 0) v += ':' + Net.PORTS[0];
          status.textContent = t('working'); Net.ping(v, 4000).then(function (r) { if (r && (r.proto || 1) < 2) { status.textContent = ''; UI.toast(t('proto_old'), 'error'); } else if (r) codeStep(r.addr, r.device.name); else { status.textContent = ''; UI.toast(t('network_error'), 'error'); } });
        } }, t('connect'))));
      if (!scanning && !found.length) { scanning = true; found = []; drawFound(); status.textContent = t('finding');
        Net.scan(function (f) { found.push(f); drawFound(); }, null).then(function () { scanning = false; status.textContent = ''; drawFound(); }); }
      drawFound();
    }
    function codeStep(addr, name) {
      body.innerHTML = '';
      var code = h('input', { type: 'text', class: 'code', inputmode: 'numeric', maxlength: 7, placeholder: '------', autocomplete: 'one-time-code' });
      var err = h('div', { class: 'small', style: { color: 'var(--red)', minHeight: '20px', marginTop: '8px' } });
      var btn = h('button', { class: 'btn primary block', style: { marginTop: '10px' }, onclick: function () {
        var digitsOnly = String(code.value).replace(/[۰-۹]/g, function (d) { return d.charCodeAt(0) - 1776; }).replace(/\D/g, '');
        if (digitsOnly.length < 6) { err.textContent = t('wrong_code'); return; }
        btn.disabled = true; err.textContent = t('working');
        Net.pairStart(addr, digitsOnly, { id: db.sync.device_id, name: db.sync.device_name || Native.deviceName() }).then(function (r) {
          btn.disabled = false;
          if (r.ok) return confirmStep(r);
          err.textContent = r.error === 'wrong' ? t('wrong_code') : r.error === 'no_code' ? t('no_code') : r.error === 'locked' ? t('locked') : t('network_error');
        }).catch(function (e) { btn.disabled = false; err.textContent = String(e && e.message || e); });
      } }, t('pair'));
      body.append(h('div', { class: 'row sb' }, h('b', null, name), h('span', { class: 'dim small hex' }, addr)), h('label', { class: 'field' }, t('enter_code')), code, err, btn);
      setTimeout(function () { code.focus(); }, 200);
    }
    // both devices show the same number; the person allows the pairing on the computer (a man in the middle would get another number)
    function confirmStep(st) {
      body.innerHTML = ''; cancelled = false;
      var big = h('div', { class: 'timer num', style: { fontSize: '44px', letterSpacing: '.12em' } }, I18n.digits(st.sas.slice(0, 3) + ' ' + st.sas.slice(3)));
      var msg = h('div', { class: 'small muted', style: { textAlign: 'center', margin: '4px 0 10px' } }, t('pair_confirm_msg'));
      var status = h('div', { class: 'small dim', style: { textAlign: 'center' } }, t('waiting_allow'));
      body.append(h('div', { class: 'dim small', style: { textAlign: 'center' } }, t('sas_number')), big, msg, status);
      Net.pairFinish(st, function () { return cancelled || s.closed; }).then(function (r) {
        if (s.closed) return;
        if (r.ok) { db.sync.laptop = r.lap; Native.setBackgroundSync(db.settings.bg_sync !== false); App.changed(); s.close(); UI.toast(t('pair_ok'), 'success'); App.syncNow(true); return; }
        status.style.color = 'var(--red)';
        status.textContent = r.error === 'denied' ? t('pair_denied') : r.error === 'expired' ? t('pair_expired') : r.error === 'key' ? t('pair_key') : t('network_error');
      });
    }
    s = UI.sheet({ title: t('find_computer'), body: body, actions: [h('button', { class: 'btn', onclick: function () { s.close(); } }, t('close'))] });
    listStep();
  }
  Views.pairFlow = pairFlow;

  function syncCard(App) {
    var db = App.db, lap = db.sync.laptop, kids = [];
    kids.push(h('div', { class: 'small muted', style: { marginBottom: '10px' } }, t('sync_intro')));
    if (lap) {
      var st = App.syncState || 'ok', stText = { ok: t('st_ok'), busy: t('st_busy'), err: t('st_err'), off: t('st_off') }[st];
      kids.push(h('div', { class: 'row', style: { marginBottom: '6px' } }, h('span', { class: 'status-dot ' + st }), h('b', null, t('paired_with', { name: lap.name || '?' })), h('span', { class: 'small dim', style: { marginInlineStart: 'auto' } }, stText)));
      var last = lap.last ? I18n.dateTimeStr(lap.last / 1000) : t('never');
      kids.push(h('div', { class: 'small dim' }, t('last_sync') + ': ' + last + (App.syncMsg ? ' · ' + App.syncMsg : '')));
      kids.push(h('div', { class: 'row', style: { marginTop: '12px', gap: '8px', flexWrap: 'wrap' } },
        h('button', { class: 'btn primary', disabled: st === 'busy', onclick: function () { App.syncNow(true); } }, UI.ic('sync'), t('sync_now')),
        h('button', { class: 'btn danger', onclick: function () { UI.confirm(t('unpair'), lap.name, t('unpair'), true).then(function (ok) { if (ok) { db.sync.laptop = null; App.syncState = 'off'; Native.setBackgroundSync(false); App.changed(); } }); } }, t('unpair'))));
      var auto = h('input', { type: 'checkbox' }); auto.checked = db.settings.auto_sync !== false;
      auto.addEventListener('change', function () { db.settings.auto_sync = auto.checked; App.save(); });
      kids.push(h('label', { class: 'row sb', style: { padding: '12px 0 0' } }, h('span', null, t('auto_sync')), auto));
      if (Native.available) {
        var bg = h('input', { type: 'checkbox' }); bg.checked = db.settings.bg_sync !== false;
        bg.addEventListener('change', function () { db.settings.bg_sync = bg.checked; App.save(); Native.setBackgroundSync(bg.checked && !!db.sync.laptop); });
        kids.push(h('label', { class: 'row sb', style: { padding: '12px 0 0' } }, h('span', null, t('bg_sync')), bg), h('div', { class: 'small dim', style: { marginTop: '4px' } }, t('bg_hint')));
      }
    } else {
      kids.push(h('div', { class: 'row', style: { marginBottom: '4px' } }, h('span', { class: 'status-dot' }), h('span', { class: 'muted' }, t('st_off'))));
      kids.push(h('div', { class: 'small dim', style: { marginBottom: '10px' } }, t('wifi_hint')));
      kids.push(h('button', { class: 'btn primary block', onclick: function () { pairFlow(App); } }, UI.ic('wifi'), t('find_computer')));
    }
    kids.push(h('div', { style: { height: '1px', background: 'var(--border)', margin: '16px 0' } }));
    kids.push(h('b', null, t('file_sync')), h('div', { class: 'small dim', style: { margin: '4px 0 10px' } }, t('file_hint')),
      h('div', { class: 'row', style: { gap: '8px' } },
        h('button', { class: 'btn', style: { flex: 1 }, onclick: function () {
          var pkg = Core.makePackage(db); App.save();
          var name = 'voidlock-' + Core.dkey().replace(/-/g, '') + '.voidsync';
          if (Native.shareFile(name, 'application/octet-stream', JSON.stringify(pkg))) UI.toast(t('file_saved'), 'success');
        } }, UI.ic('share'), t('save_file')),
        h('button', { class: 'btn', style: { flex: 1 }, onclick: function () { Native.pickFile().then(function (f) { if (f) importText(App, f.text); }); } }, UI.ic('file'), t('import_file'))));
    return card(t('sync_card'), kids);
  }

  function reportSheet(App) {
    var db = App.db, range = 14, today = Core.dkey();
    var fromF = UI.dateField(Core.dkey(Core.addDays(new Date(), -13))), toF = UI.dateField(today);
    var custom = h('div', { class: 'hide' }, UI.field(t('r_from'), fromF.el), UI.field(t('r_to'), toF.el));
    var nameIn = h('input', { type: 'text', maxlength: 40, placeholder: t('r_name'), value: db.settings.report_name || '' });
    var segBox = h('div');
    var firstDay = db.entries.concat(db.sessions.map(function (r) { return { date: Core.dkey(new Date(r.start * 1000)) }; })).map(function (e) { return e.date; }).sort()[0] || today;
    function draw() {
      segBox.innerHTML = '';
      segBox.appendChild(seg([[7, t('r_7')], [14, t('r_14')], [30, t('r_30')], [90, t('r_90')], ['all', t('r_all')], ['custom', t('r_custom')]], range, function (v) { range = v; custom.classList.toggle('hide', v !== 'custom'); draw(); }));
    }
    draw();
    function period() {
      if (range === 'custom') { var f = fromF.get(), e = toF.get(); return f <= e ? [f, e] : [e, f]; }
      if (range === 'all') return [firstDay, today];
      return [Core.dkey(Core.addDays(new Date(), -(range - 1))), today];
    }
    function make(kind) {
      var p = period(), nm = nameIn.value.trim();
      if (nm !== (db.settings.report_name || '')) { db.settings.report_name = nm; App.save(); }
      var r = Report.build(db, p[0], p[1], { name: nm, interactive: kind !== 'pdf' });
      var any = db.entries.some(function (e) { return e.date >= p[0] && e.date <= p[1]; }) || db.sessions.length || db.exams.some(function (e) { return e.date >= p[0] && e.date <= p[1]; });
      if (!any) return UI.toast(t('report_empty'), 'warn');
      if (kind === 'html') Native.shareFile(r.base + '.html', 'text/html', r.html);
      else if (kind === 'csv') Native.shareFile(r.base + '.csv', 'text/csv', r.csv);
      else Native.printHtml(r.title, r.html);
    }
    var s = UI.sheet({ title: t('report_title'), message: t('report_hint'), body: [segBox, custom, UI.field(t('r_name'), nameIn)],
      actions: [h('div', { class: 'col', style: { width: '100%', gap: '8px' } },
        h('button', { class: 'btn primary block', onclick: function () { make('pdf'); } }, UI.ic('file'), t('fmt_pdf')),
        h('button', { class: 'btn block', onclick: function () { make('html'); } }, UI.ic('globe'), t('fmt_html')),
        h('button', { class: 'btn block', onclick: function () { make('csv'); } }, UI.ic('stats'), t('fmt_csv')))] });
    s.el.querySelector('.actions').style.display = 'block';
  }
  Views.reportSheet = reportSheet;
  function reportCard(App) {
    return card(t('report'), [h('div', { class: 'small dim', style: { marginBottom: '10px' } }, t('report_hint')), h('button', { class: 'btn block', onclick: function () { reportSheet(App); } }, UI.ic('file'), t('report_make'))]);
  }

  function subjectsCard(App) {
    var db = App.db;
    var rows = db.subjects.map(function (s) {
      return h('div', { class: 'item', onclick: function () { Views.subjectSheet(App, s); } }, h('span', { class: 'dot', style: { '--c': s.color } }), h('b', { class: 'grow' }, s.name),
        s.words ? h('span', { class: 'pill', style: { '--c': 'var(--violet)' } }, t('words_learned')) : null, h('span', { class: 'dim', html: UI.icon('edit'), style: { width: '18px' } }));
    });
    return card(t('subjects'), [rows.length ? h('div', { class: 'list' }, rows) : h('div', { class: 'empty' }, t('no_subjects')),
      h('button', { class: 'btn block', style: { marginTop: '10px' }, onclick: function () { Views.subjectSheet(App, null); } }, UI.ic('plus'), t('add_subject'))]);
  }

  function settingsCard(App) {
    var db = App.db, goal = h('input', { type: 'text', inputmode: 'numeric', value: I18n.digits(db.settings.goal_min || 120), style: { textAlign: 'center' } });
    goal.addEventListener('change', function () { var v = Views.parseNum(goal.value); if (v && v >= 10 && v <= 1440) { db.settings.goal_min = Math.round(v); App.save(); App.render(); } else goal.value = I18n.digits(db.settings.goal_min); });
    return card(t('settings'), [
      h('label', { class: 'field', style: { marginTop: 0 } }, t('language')),
      seg([['fa', t('persian')], ['en', t('english')]], db.settings.lang, function (l) { db.settings.lang = l; I18n.setLang(l); App.save(); App.render(); }),
      h('label', { class: 'field' }, t('reduce_motion_label')),
      (function () {
        var cb = h('input', { type: 'checkbox' });
        cb.checked = db.settings.reduce_motion === true;
        cb.addEventListener('change', function () { db.settings.reduce_motion = cb.checked; App.save(); Motion.setReduced(cb.checked ? true : (db.settings.reduce_motion === false ? false : null)); });
        return h('label', { class: 'row sb', style: { padding: '2px 0 0' } }, h('span', { class: 'small dim' }, t('reduce_motion_hint')), cb);
      })(),
      h('label', { class: 'field' }, t('daily_goal')), goal,
      h('label', { class: 'field' }, t('theme')),
      seg([['ocean', t('theme_ocean')], ['void', t('theme_void')], ['midnight', t('theme_midnight')], ['paper', t('theme_paper')]], db.settings.theme || 'ocean', function (th) { db.settings.theme = th; App.applyTheme(); App.save(); App.render(); })]);
  }

  function aboutCard(App) {
    var db = App.db, u = App.update || { state: 'idle' }, kids = [];
    kids.push(h('div', { class: 'row sb' }, h('span', { class: 'muted' }, t('version')), h('b', { class: 'num' }, I18n.digits(Native.appVersion()))));
    kids.push(h('div', { class: 'row sb', style: { marginTop: '4px' } }, h('span', { class: 'muted' }, Intro.U('madeBy')), h('b', { dir: 'ltr' }, Intro.SIGN)));
    if (u.state === 'available' && u.info) {
      kids.push(h('div', { class: 'banner', style: { margin: '10px 0' } }, t('update_available', { v: I18n.digits(u.info.version) })));
      kids.push(h('button', { class: 'btn primary block', onclick: function () { App.installUpdate(); } }, UI.ic('down'), t('update_install')));
    } else if (u.state === 'downloading') kids.push(h('div', { class: 'banner', style: { margin: '10px 0' } }, u.stage === 'verifying' ? t('update_verify') : t('update_dl', { p: I18n.digits(u.p || 0) })));
    else if (u.state === 'perm') kids.push(h('div', { class: 'banner', style: { margin: '10px 0' } }, t('update_need_perm')), h('button', { class: 'btn block', onclick: function () { App.installUpdate(); } }, t('retry')));
    else if (u.state === 'error') kids.push(h('div', { class: 'banner', style: { margin: '10px 0' } }, t('update_failed', { err: u.err })));
    else if (u.state === 'none') kids.push(h('div', { class: 'small dim', style: { margin: '8px 0' } }, t('update_none')));
    if (u.state !== 'downloading') kids.push(h('button', { class: 'btn block', style: { marginTop: '10px' }, disabled: u.state === 'checking', onclick: function () { App.checkUpdate(true); } }, UI.ic('globe'), u.state === 'checking' ? t('checking') : t('check_update')));
    var auto = h('input', { type: 'checkbox' }); auto.checked = db.settings.update_check !== false;
    auto.addEventListener('change', function () { db.settings.update_check = auto.checked; App.save(); });
    kids.push(h('label', { class: 'row sb', style: { padding: '12px 0 0' } }, h('span', null, t('update_auto')), auto), h('div', { class: 'small dim', style: { marginTop: '6px' } }, t('update_hint')));
    Intro.settingsRows(App).forEach(function (r) { kids.push(r); });
    kids.push(h('button', { class: 'btn danger block', style: { marginTop: '16px' }, onclick: function () {
      UI.confirm(t('reset_q'), t('reset_msg'), t('delete'), true).then(function (ok) { if (ok) App.resetAll(); });
    } }, t('reset_data')));
    return card(t('about'), kids);
  }

  // ---------------------------------------------------------------- notifications (class / exam reminders, new version)
  function notifyCard(App) {
    var st = App.db.settings, shell = Native.hasShell(), allowed = Native.notificationsAllowed(), exact = Native.canExactAlarms();
    var kids = [h('div', { class: 'small dim', style: { marginBottom: '8px' } }, shell ? t('notify_hint') : t('notify_browser'))];
    if (shell && !allowed) kids.push(h('button', { class: 'btn primary block', onclick: function () { Native.requestNotifications(); setTimeout(function () { App.render(); }, 1800); } }, t('notify_enable')));
    [['classes', 'notify_classes'], ['exams', 'notify_exams'], ['updates', 'notify_updates']].forEach(function (r) {
      var cb = h('input', { type: 'checkbox' }); cb.checked = st['notify_' + r[0]] !== false;
      cb.addEventListener('change', function () { st['notify_' + r[0]] = cb.checked; App.save(); App.replan(); });
      kids.push(h('label', { class: 'row sb', style: { padding: '10px 0 0' } }, h('span', null, t(r[1])), cb));
    });
    if (shell && allowed && !exact) kids.push(h('div', { class: 'small dim', style: { marginTop: '10px' } }, t('notify_exact')),
      h('button', { class: 'btn block', style: { marginTop: '6px' }, onclick: function () { Native.openAlarmSettings(); } }, t('notify_exact_btn')));
    if (shell && allowed) kids.push(h('button', { class: 'btn block', style: { marginTop: '12px' }, onclick: function () { Native.notify(t('notify_test_title'), t('notify_test_text'), 'test|' + Date.now()); } }, t('notify_test')));
    return card(t('notify_title'), kids);
  }

  Views.more = function (host, App) {
    host.appendChild(syncCard(App));
    host.appendChild(notifyCard(App));
    host.appendChild(reportCard(App));
    host.appendChild(subjectsCard(App));
    host.appendChild(settingsCard(App));
    host.appendChild(aboutCard(App));
    host.appendChild(h('div', { class: 'intro-foot', dir: 'ltr' }, 'VOIDLOCK · ' + Intro.SIGN));
  };
})(typeof window !== 'undefined' ? window : globalThis);
