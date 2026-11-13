/* Weekly classes: the same list the computer has (it travels with the sync). A "Classes" mode in the Tasks tab with the week laid out day by day,
 * a sheet to add / edit a class (name, day, time, length, place, reminder), and a small "next class" card for the Today tab. */
(function (root) {
  'use strict';
  var h = UI.h, t = function (k, v) { return I18n.t(k, v); };
  var Views = root.Views = root.Views || {};
  var REMINDS = [0, 5, 10, 15, 30, 60];
  function card(title, kids, cls) { return h('section', { class: 'card ' + (cls || '') }, title ? h('h3', null, title) : null, kids); }
  function dayName(wd) { return I18n.lang === 'fa' ? WinCharts.FA_DAYS[wd] : WinCharts.EN_DAYS[wd]; }
  function weekOrder(db) { var ws = parseInt(db.settings.week_start === undefined ? 5 : db.settings.week_start, 10); if (!isFinite(ws)) ws = 5; return [0, 1, 2, 3, 4, 5, 6].map(function (k) { return (ws + k) % 7; }); }
  function hm(d) { return (d.getHours() < 10 ? '0' : '') + d.getHours() + ':' + (d.getMinutes() < 10 ? '0' : '') + d.getMinutes(); }
  function range(c) {
    var p = c.time.split(':'), s = new Date(2000, 0, 1, +p[0], +p[1]), e = new Date(s.getTime() + c.minutes * 60000);
    return I18n.digits(c.time + ' – ' + hm(e));
  }
  function remindText(n) { return n ? t('remind_min', { n: I18n.digits(n) }) : t('remind_off'); }

  // ---------------------------------------------------------------- add / edit sheet
  function classSheet(App, c) {
    var db = App.db, editing = !!c;
    var name = h('input', { type: 'text', maxlength: 40, placeholder: t('class_name'), value: c ? c.name : '' });
    var day = h('select'); weekOrder(db).forEach(function (wd) { day.appendChild(h('option', { value: wd }, dayName(wd))); });
    day.value = String(c ? c.day : Classes.weekday(new Date()));
    var time = h('input', { type: 'time', value: c ? c.time : '17:00' });
    var mins = h('input', { type: 'number', inputmode: 'numeric', min: 5, max: 600, step: 5, value: c ? c.minutes : 90 });
    var place = h('input', { type: 'text', maxlength: 40, placeholder: t('class_place'), value: c ? c.place || '' : '' });
    var rem = h('select'); REMINDS.forEach(function (n) { rem.appendChild(h('option', { value: n }, remindText(n))); });
    rem.value = String(c ? c.remind : 15);
    var on = h('input', { type: 'checkbox' }); on.checked = c ? c.enabled !== false : true;
    function save() {
      var f = { name: name.value.trim(), day: +day.value, time: time.value, minutes: +mins.value, remind: +rem.value, place: place.value.trim(), enabled: on.checked };
      if (!f.name) return UI.toast(t('class_need_name'), 'warn');
      if (!/^\d{1,2}:\d{2}$/.test(f.time || '')) return UI.toast(t('class_need_time'), 'warn');
      if (editing) Core.updateClass(db, c.id, f); else Core.addClass(db, f);
      s.close(); App.changed();
    }
    var acts = [];
    if (editing) acts.push(h('button', { class: 'btn danger', onclick: function () { s.close(); Core.removeClass(db, c.id); App.changed(); UI.toast(t('class_deleted'), 'info'); } }, t('delete')));
    acts.push(h('button', { class: 'btn primary', onclick: save }, t('save')));
    var s = UI.sheet({ title: editing ? t('edit_class') : t('add_class'), body: [UI.field(t('class_name'), name), UI.field(t('class_day'), day),
      h('div', { class: 'row', style: { gap: '10px' } }, h('div', { class: 'grow' }, UI.field(t('class_time'), time)), h('div', { class: 'grow' }, UI.field(t('class_minutes'), mins))),
      UI.field(t('class_place'), place), UI.field(t('class_remind'), rem),
      h('label', { class: 'row sb', style: { padding: '12px 0 0' } }, h('span', null, t('class_enabled')), on)], actions: acts });
  }

  // ---------------------------------------------------------------- the week
  function nextClassCard(App, full) {
    var db = App.db, now = new Date(), cn = Classes.currentOrNext(db.classes, now);
    if (!db.classes.length) return null;
    if (!cn.state) return full ? card(null, h('div', { class: 'small dim' }, t('class_none'))) : null;
    var left = cn.state === 'now' ? cn.end - now : cn.start - now;
    var line = cn.state === 'now' ? t('class_now') + ' · ' + t('class_until', { t: I18n.digits(hm(cn.end)) }) : t('class_next') + ' · ' + t('class_in', { d: I18n.dur(left / 1000) });
    return card(null, h('div', { class: 'row', style: { gap: '12px', alignItems: 'center' } },
      h('div', { class: 'cls-ico' + (cn.state === 'now' ? ' on' : '') }, UI.ic('today')),
      h('div', { class: 'grow' }, h('div', { class: 'cls-name' }, cn.cls.name), h('div', { class: 'small dim' }, line + (cn.cls.place ? ' · ' + cn.cls.place : '')))), 'cls-next');
  }
  Views.nextClassCard = nextClassCard;

  Views.classesList = function (host, App) {
    var db = App.db, today = Classes.weekday(new Date());
    var nx = nextClassCard(App, true); if (nx) host.appendChild(nx);
    host.appendChild(h('button', { class: 'btn primary block', style: { margin: '2px 0 12px' }, onclick: function () { classSheet(App, null); } }, UI.ic('plus'), ' ', t('add_class')));
    if (!db.classes.length) { host.appendChild(card(null, h('div', { class: 'empty' }, t('no_classes')))); return; }
    var week = h('section', { class: 'card cls-week' });
    weekOrder(db).forEach(function (wd) {
      var list = Core.classes(db).filter(function (c) { return c.day === wd; });
      week.appendChild(h('div', { class: 'cls-day' + (wd === today ? ' today' : '') }, dayName(wd), wd === today ? h('span', { class: 'cls-today' }, t('today')) : null,
        list.length ? null : h('span', { class: 'cls-free' }, t('class_free_day'))));
      list.forEach(function (c) {
        week.appendChild(h('button', { class: 'cls-row' + (c.enabled === false ? ' off' : ''), onclick: function () { classSheet(App, c); } },
          h('div', { class: 'cls-time num' }, range(c)),
          h('div', { class: 'grow', style: { textAlign: 'start', minWidth: 0 } }, h('div', { class: 'cls-name' }, c.name), c.place ? h('div', { class: 'small dim' }, c.place) : null),
          h('span', { class: 'cls-badge' }, c.enabled === false ? t('class_off') : remindText(c.remind))));
      });
    });
    host.appendChild(week);
  };
  Views.classSheet = classSheet;
})(typeof window !== 'undefined' ? window : globalThis);
