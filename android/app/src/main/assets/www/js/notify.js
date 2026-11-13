/* Reminders on the phone: class reminders, exam reminders (the evening before and the morning of the exam, like the computer's "exam tomorrow /
 * today") and the "new version" notice. This file only decides WHAT to remind and WHEN; the Android shell (Reminders.kt) keeps the alarms and
 * shows the notifications even when the app is closed. Everything is re-planned whenever classes / exams change, after a sync and when the app opens. */
(function (root) {
  'use strict';
  var T = {
    fa: { soon: '{n} دقیقه دیگر شروع می‌شود', start: 'کلاس شروع شد', examTomorrow: 'فردا آزمون دارید', examToday: 'امروز آزمون دارید', update: 'نسخه‌ی تازه‌ی VOIDLOCK آماده است', updateText: 'نسخه‌ی {v} را از بخش «بیشتر» نصب کنید.' },
    en: { soon: 'starts in {n} min', start: 'Class has started', examTomorrow: 'Exam tomorrow', examToday: 'Exam today', update: 'A new VOIDLOCK version is ready', updateText: 'Install v{v} from the More tab.' }
  };
  function lang() { return root.I18n && root.I18n.lang === 'en' ? 'en' : 'fa'; }
  function tx(k, v) { var s = T[lang()][k]; if (v) Object.keys(v).forEach(function (n) { s = s.replace('{' + n + '}', root.I18n ? root.I18n.digits(v[n]) : v[n]); }); return s; }
  function on(st, k) { return !st || st['notify_' + k] !== false; }
  function hm(ms) { var d = new Date(ms); return (d.getHours() < 10 ? '0' : '') + d.getHours() + ':' + (d.getMinutes() < 10 ? '0' : '') + d.getMinutes(); }
  function dig(s) { return root.I18n ? root.I18n.digits(s) : s; }
  function atTime(dk, hh, mm) { var p = dk.split('-'); return new Date(+p[0], +p[1] - 1, +p[2], hh, mm, 0, 0).getTime(); }

  /** [{id, at (ms), title, text, channel}] for the next days, soonest first. */
  function plan(db, now, horizonDays) {
    var out = [], st = db.settings || {}, nowMs = now.getTime();
    if (on(st, 'classes')) {
      root.Classes.reminders(db.classes || [], now, horizonDays || 8).forEach(function (r) {
        out.push({ id: r.id, at: r.at, channel: 'class', title: r.name + ' — ' + (r.lead > 0 ? tx('soon', { n: r.lead }) : tx('start')),
                   text: dig(hm(r.start)) + (r.place ? ' · ' + r.place : '') });
      });
    }
    if (on(st, 'exams')) {
      var tod = root.Core.dkey(now), last = root.Core.dkey(root.Core.addDays(now, horizonDays || 8));
      (root.Core.exams(db) || []).forEach(function (e) {
        if (e.date < tod || e.date > last) return;
        var eve = atTime(root.Core.dkey(root.Core.addDays(root.Core.parseDkey(e.date), -1)), 18, 0), morn = atTime(e.date, 7, 0), when = e.time ? ' · ' + dig(e.time) : '';
        if (eve > nowMs) out.push({ id: 'exam|' + e.id + '|eve', at: eve, channel: 'exam', title: tx('examTomorrow'), text: e.name + when });
        if (morn > nowMs) out.push({ id: 'exam|' + e.id + '|day', at: morn, channel: 'exam', title: tx('examToday'), text: e.name + when });
      });
    }
    return out.sort(function (a, b) { return a.at - b.at; });
  }
  /** Hands the plan to the Android shell (nothing happens in a browser). */
  function sync(App) {
    try { if (root.Native && root.Native.scheduleReminders) root.Native.scheduleReminders(JSON.stringify(plan(App.db, new Date()))); } catch (e) { /* reminders must never break the app */ }
  }
  /** The "new version" notice, once per version. */
  function updateNotice(App, info) {
    var st = App.db.settings;
    if (!on(st, 'updates') || !info || st.update_notified === info.version) return false;
    st.update_notified = info.version; App.save();
    if (root.Native && root.Native.notify) root.Native.notify(tx('update'), tx('updateText', { v: info.version }), 'update|' + info.version);
    return true;
  }
  root.Notify = { plan: plan, sync: sync, updateNotice: updateNotice, T: T };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.Notify;
})(typeof window !== 'undefined' ? window : globalThis);
