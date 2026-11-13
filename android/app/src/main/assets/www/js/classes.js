/* Weekly classes: what is next, what is running now, today's list and the reminders to schedule. A port of voidlock/classes.py (the computer's
 * rules), checked against it by android/tests/classes_parity_test.py. Days: 0 = Monday ... 6 = Sunday (like the computer). */
(function (root) {
  'use strict';
  function wd(d) { return (d.getDay() + 6) % 7; }
  function dayStart(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0); }
  function startOf(c, day) { var p = String(c.time).split(':'); return new Date(day.getFullYear(), day.getMonth(), day.getDate(), parseInt(p[0], 10), parseInt(p[1], 10), 0, 0); }
  function minutesOf(c) { var m = parseInt(c.minutes === undefined ? 90 : c.minutes, 10); return isFinite(m) ? m : 90; }
  function on(c) { return c.enabled !== false; }

  /** [{start, end, cls}] for the classes of yesterday (still running), today and the coming days, sorted by start; only those not over yet. */
  function occurrences(classes, now, days) {
    days = days === undefined ? 8 : days;
    var base = dayStart(now), out = [];
    for (var add = -1; add < days; add++) {
      var d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + add);
      classes.forEach(function (c) {
        if (!on(c) || c.day !== wd(d)) return;
        var s = startOf(c, d), e = new Date(s.getTime() + minutesOf(c) * 60000);
        if (e.getTime() > now.getTime()) out.push({ start: s, end: e, cls: c });
      });
    }
    return out.sort(function (a, b) { return a.start - b.start; });
  }
  function todayList(classes, now) {
    var base = dayStart(now), out = [];
    classes.forEach(function (c) { if (on(c) && c.day === wd(now)) { var s = startOf(c, base); out.push({ start: s, end: new Date(s.getTime() + minutesOf(c) * 60000), cls: c }); } });
    return out.sort(function (a, b) { return a.start - b.start; });
  }
  /** {state: 'now' | 'next' | null, cls, start, end} */
  function currentOrNext(classes, now) {
    var occ = occurrences(classes, now), i;
    for (i = 0; i < occ.length; i++) if (occ[i].start <= now && now < occ[i].end) return { state: 'now', cls: occ[i].cls, start: occ[i].start, end: occ[i].end };
    for (i = 0; i < occ.length; i++) if (occ[i].start > now) return { state: 'next', cls: occ[i].cls, start: occ[i].start, end: occ[i].end };
    return { state: null, cls: null, start: null, end: null };
  }
  /** The reminders to hand to the phone's alarm clock: one per class occurrence, `remind` minutes before it starts (at the start when remind is 0). */
  function reminders(classes, now, horizonDays) {
    var out = [];
    occurrences(classes, now, horizonDays || 8).forEach(function (o) {
      var lead = parseInt(o.cls.remind === undefined ? 15 : o.cls.remind, 10) || 0, at = new Date(o.start.getTime() - lead * 60000);
      if (o.start <= now) return;                                   // already running: nothing to remind about
      if (at <= now) at = now;                                      // the reminder time passed but the class has not begun: tell at once
      out.push({ id: 'class|' + o.cls.id + '|' + o.start.getTime(), kind: 'class', at: at.getTime(), start: o.start.getTime(), lead: lead, name: o.cls.name, place: o.cls.place || '' });
    });
    return out;
  }
  var Classes = { occurrences: occurrences, todayList: todayList, currentOrNext: currentOrNext, reminders: reminders, weekday: wd };
  if (typeof module !== 'undefined' && module.exports) module.exports = Classes; else root.Classes = Classes;
})(typeof window !== 'undefined' ? window : globalThis);
