/* App: state, storage, navigation, timers, Wi-Fi sync loop, updates. */
(function (root) {
  'use strict';
  var KEY = 'voidlock.db', h = UI.h, t = function (k, v) { return I18n.t(k, v); };
  var App = root.App = { db: null, view: 'today', range: 14, taskDay: null, examKind: 'taraz', tick: null, syncState: 'off', syncMsg: '', syncing: false, dirty: false, update: { state: 'idle' } };
  var saveTimer = null, syncTimer = null;

  // ------------------------------------------------------------------ storage
  App.load = function () {
    var raw = null, db = null;
    try { raw = localStorage.getItem(KEY); } catch (e) {}
    try { db = raw ? JSON.parse(raw) : null; } catch (e) { db = null; }
    App.db = Core.ensure(db);
    if (!App.db.sync.device_name) App.db.sync.device_name = Native.deviceName();
    I18n.setLang(App.db.settings.lang); App.applyTheme();
  };
  App.saveNow = function () { clearTimeout(saveTimer); saveTimer = null; try { localStorage.setItem(KEY, JSON.stringify(App.db)); } catch (e) { UI.toast('Storage error: ' + e, 'error'); } };
  App.save = function () { if (saveTimer) return; saveTimer = setTimeout(App.saveNow, 250); };
  App.applyTheme = function () { document.documentElement.setAttribute('data-theme', App.db.settings.theme || 'ocean'); };

  // ------------------------------------------------------------------ changes and rendering
  App.changed = function () { App.dirty = true; App.save(); App.render(); App.scheduleSync(); };
  App.refresh = function () { App.save(); App.render(); };
  App.go = function (v) { App.view = v; var el = document.getElementById('view'); App.render(); el.scrollTop = 0; };
  var TITLES = { today: 'nav_today', stats: 'nav_stats', exams: 'nav_exams', tasks: 'nav_tasks', more: 'nav_more' };
  App.render = function () {
    var host = document.getElementById('view'), sc = host.scrollTop;
    host.innerHTML = ''; App.tick = null;
    try { Views[App.view](host, App); }
    catch (e) { host.appendChild(h('section', { class: 'card' }, h('b', null, 'Error'), h('pre', { style: { whiteSpace: 'pre-wrap', fontSize: '12px', direction: 'ltr' } }, String(e && e.stack || e)))); if (root.console) console.error(e); }
    host.scrollTop = sc;
    var nav = document.getElementById('nav'); nav.innerHTML = '';
    Object.keys(TITLES).forEach(function (k) { nav.appendChild(h('button', { class: App.view === k ? 'on' : '', onclick: function () { if (App.view !== k) App.go(k); }, html: UI.icon(k) + '<span>' + t(TITLES[k]) + '</span>' })); });
    var title = document.getElementById('top-title'); title.innerHTML = '';
    title.appendChild(document.createTextNode(App.view === 'today' ? t('app') : t(TITLES[App.view])));
    title.appendChild(h('small', null, I18n.dateStr(Core.dkey(), true)));
    App.renderStatus();
    Native.keepAwake(!!(App.db.active && Core.subject(App.db, App.db.active.subject)));
  };
  App.renderStatus = function () {
    var box = document.getElementById('top-actions'); box.innerHTML = '';
    var lap = App.db.sync.laptop, st = lap ? App.syncState : 'off';
    box.appendChild(h('button', { class: 'icon-btn', 'aria-label': t('sync'), onclick: function () { if (lap) App.syncNow(true); else App.go('more'); } },
      h('span', { html: UI.icon(lap ? 'sync' : 'wifi') }), lap ? h('span', { class: 'status-dot ' + st }) : null));
  };

  // ------------------------------------------------------------------ Wi-Fi sync
  App.scheduleSync = function () {
    var lap = App.db.sync.laptop; if (!lap || App.db.settings.auto_sync === false) return;
    clearTimeout(syncTimer); syncTimer = setTimeout(function () { App.syncNow(false); }, 3000);
  };
  App.syncNow = function (manual) {
    var db = App.db, lap = db.sync.laptop;
    if (!lap) return Promise.resolve();
    if (App.syncing) return Promise.resolve();
    App.syncing = true; App.syncState = 'busy'; App.renderStatus(); if (manual && App.view === 'more') App.render();
    return Net.rev(lap).then(function (rv) {
      if (rv.status === 401) return { ok: false, status: 401 };
      if (rv.status !== 200) return { ok: false, status: 0, error: 'network' };
      return Net.syncOnce(db, lap);
    }).catch(function (e) { return { ok: false, status: 0, error: String(e && e.message || e) }; }).then(function (r) {
      App.syncing = false;
      if (r.ok) {
        lap.lastRev = r.rev; lap.last = Date.now(); App.dirty = false; App.syncState = 'ok'; App.syncMsg = '';
        App.saveNow();
        if (r.changes) App.render(); else if (App.view === 'more') App.render();
        if (manual) UI.toast(r.changes ? t('synced_ok') : t('up_to_date'), 'success');
      } else {
        App.syncState = 'err';
        if (r.status === 401) { App.syncMsg = t('unauthorized'); }
        else if (r.error === 'needs_review') { App.syncMsg = t('needs_review'); if (manual) UI.toast(t('needs_review'), 'warn'); }
        else if (r.status === 422) { App.syncMsg = syncMessage(r); }
        else App.syncMsg = '';
        if (manual && r.error !== 'needs_review') UI.toast(r.status === 401 ? t('unauthorized') : t('network_error'), 'error');
        App.saveNow(); App.renderStatus(); if (App.view === 'more') App.render();
      }
      App.renderStatus();
    });
  };
  function syncMessage(r) { return r.message || t('unknown_error'); }
  App.poll = function () {
    var lap = App.db.sync.laptop;
    if (!lap || App.db.settings.auto_sync === false || App.syncing || document.visibilityState === 'hidden') return;
    if (App.dirty || !lap.lastRev) return App.syncNow(false);
    Net.rev(lap).then(function (rv) {
      if (rv.status === 200) {
        if (App.syncState === 'err') { App.syncState = 'ok'; App.renderStatus(); }
        if (rv.rev !== lap.lastRev) App.syncNow(false);
      } else if (App.syncState !== 'err') { App.syncState = 'err'; App.syncMsg = rv.status === 401 ? t('unauthorized') : ''; App.renderStatus(); if (App.view === 'more') App.render(); }
    });
  };

  // ------------------------------------------------------------------ updates (GitHub releases)
  App.checkUpdate = function (manual) {
    App.update = { state: 'checking' }; if (App.view === 'more') App.render();
    return Net.checkUpdate().then(function (r) {
      App.db.settings.last_update_check = Date.now(); App.save();
      if (!r.ok) App.update = manual ? { state: 'error', err: r.error } : { state: 'idle' };
      else if (r.newer && r.hasApk) { App.update = { state: 'available', info: r }; if (!manual) UI.toast(t('update_available', { v: I18n.digits(r.version) }), 'info'); }
      else App.update = { state: 'none' };
      if (App.view === 'more') App.render();
    });
  };
  App.installUpdate = function () {
    var info = App.update.info; if (!info) return;
    App.update = { state: 'downloading', p: 0, stage: 'downloading', info: info }; if (App.view === 'more') App.render();
    var last = 0;
    Native.installApk(info.url, info.shaUrl, function (stage, a, b) {
      if (stage === 'downloading') { App.update.p = b ? Math.floor(a * 100 / b) : 0; if (Date.now() - last < 400) return; last = Date.now(); }
      else if (stage === 'verifying') App.update.stage = 'verifying';
      else if (stage === 'ready') App.update = { state: 'available', info: info };
      else if (stage === 'need_permission') { App.update = { state: 'perm', info: info }; Native.openInstallSettings(); }
      else if (stage === 'error') App.update = { state: 'error', err: String(a) };
      if (App.view === 'more') App.render();
    });
  };

  App.resetAll = function () {
    var lang = App.db.settings.lang, theme = App.db.settings.theme;
    try { localStorage.removeItem(KEY); } catch (e) {}
    App.db = Core.ensure(null); App.db.settings.lang = lang; App.db.settings.theme = theme; App.db.settings.welcomed = true; App.db.sync.device_name = Native.deviceName();
    App.syncState = 'off'; App.saveNow(); App.render(); UI.toast(t('saved'), 'success');
  };

  // ------------------------------------------------------------------ first run and boot
  function welcome() {
    var db = App.db; if (db.settings.welcomed || db.subjects.length || db.entries.length || db.sync.laptop) return;
    var s = UI.sheet({ title: t('welcome'), message: t('welcome_msg'), body: null, onClose: function () { db.settings.welcomed = true; App.save(); },
      actions: [h('button', { class: 'btn', onclick: function () { s.close(); } }, t('start_fresh')),
                h('button', { class: 'btn primary', onclick: function () { s.close(); App.go('more'); setTimeout(function () { Views.pairFlow(App); }, 350); } }, t('from_laptop'))] });
  }
  root.__back = function () { if (UI.closeTop()) return true; if (App.view !== 'today') { App.go('today'); return true; } return false; };

  // "#bg": the Android background sync opens this page without a screen: one sync, save, tell the shell, nothing else
  function bgMode() {
    App.bg = true; App.render = function () {}; App.renderStatus = function () {};
    App.load(); Net.persist = App.saveNow;
    var finished = false;
    function finish() { if (finished) return; finished = true; App.saveNow(); Native.bgDone(true); }
    setTimeout(finish, 65000);
    if (!App.db.sync.laptop || App.db.settings.auto_sync === false) return finish();
    App.syncNow(false).then(finish, finish);
  }

  App.boot = function () {
    if (location.hash === '#bg') return bgMode();
    App.load();
    Net.persist = App.saveNow;                                  // the request counter is saved before every encrypted call
    var a = App.db.active;
    if (a && Core.elapsed(App.db) > 12 * 3600) { App.db.active = null; App.saveNow(); UI.toast(t('timer_hint'), 'warn'); }
    App.syncState = App.db.sync.laptop ? 'ok' : 'off';
    App.render();
    setInterval(function () { if (App.tick) App.tick(); }, 1000);
    setInterval(App.poll, 12000);
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') App.saveNow();
      else { App.load(); Net.persist = App.saveNow; App.render(); setTimeout(App.poll, 400); }       // the background sync may have changed the data
    });
    root.addEventListener('pagehide', App.saveNow);
    Native.onOpenFile(function (name, text) { App.go('more'); Views.importText(App, text); });
    setTimeout(welcome, 500);
    var st = App.db.settings;
    if (st.update_check !== false && Date.now() - (st.last_update_check || 0) > 12 * 3600 * 1000) setTimeout(function () { App.checkUpdate(false); }, 4000);
    if (App.db.sync.laptop) { setTimeout(App.poll, 1500); Native.setBackgroundSync(App.db.settings.bg_sync !== false); }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', App.boot); else App.boot();
})(window);
