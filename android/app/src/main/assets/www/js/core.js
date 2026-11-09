/* VOIDLOCK core: data model, study logic, exams and the sync engine.
 * No DOM here, so it runs in the app and in Node tests. The sync part is a port of voidlock/sync.py (format "voidlock-sync",
 * version 2): the rules at the top of that file are the contract between the phone and the computer. */
(function (root) {
  'use strict';
  var FORMAT = 'voidlock-sync', VERSION = 2;
  var LIST_KINDS = ['subjects', 'entries', 'exams', 'exam_subjects', 'todos', 'sessions'];
  var LEAF_KINDS = ['tests', 'words'];
  var KINDS = LIST_KINDS.concat(LEAF_KINDS, ['gone']);
  var LOCAL_ONLY = { exams: ['notified'] };
  var MASS_DELETE_MIN = 10, TOMB_KEEP_MS = 400 * 86400 * 1000;
  var SUBJECT_COLORS = ['#FF5DA2', '#8B5CF6', '#00C2FF', '#34D399', '#FBBF24', '#FB7185', '#60A5FA', '#F97316'];

  function SyncError(msg) { this.message = msg; this.name = 'SyncError'; }
  SyncError.prototype = Object.create(Error.prototype);

  // ---------------------------------------------------------------- small helpers
  function uid() {
    var s = '';
    if (root.crypto && root.crypto.getRandomValues) {
      var a = new Uint8Array(5); root.crypto.getRandomValues(a);
      for (var i = 0; i < a.length; i++) s += ('0' + a[i].toString(16)).slice(-2);
    } else { for (var j = 0; j < 10; j++) s += Math.floor(Math.random() * 16).toString(16); }
    return s;
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function dkey(d) { d = d || new Date(); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function parseDkey(k) { var p = k.split('-'); return new Date(+p[0], +p[1] - 1, +p[2], 12, 0, 0); }
  function addDays(d, n) { var x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }
  function isObj(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }
  function clone(x) { return x === undefined ? undefined : JSON.parse(JSON.stringify(x)); }
  function sortedStringify(x) {
    if (Array.isArray(x)) return '[' + x.map(sortedStringify).join(',') + ']';
    if (isObj(x)) return '{' + Object.keys(x).sort().map(function (k) { return JSON.stringify(k) + ':' + sortedStringify(x[k]); }).join(',') + '}';
    return JSON.stringify(x);
  }
  function digest(v) {                                     // a local fingerprint (cyrb53): only this device compares it with itself
    var s = sortedStringify(v), h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (var i = 0; i < s.length; i++) {
      var ch = s.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761); h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
  }
  function eq(a, b) { return sortedStringify(a) === sortedStringify(b); }
  function nowMs() { return Date.now(); }

  // ---------------------------------------------------------------- colours (same rule as study.normalize_color)
  function normalizeColor(c, lo, hi) {
    lo = lo === undefined ? 0.38 : lo; hi = hi === undefined ? 0.74 : hi;
    if (typeof c !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(c.trim())) return null;
    var h6 = c.trim().slice(1);
    var r = parseInt(h6.slice(0, 2), 16) / 255, g = parseInt(h6.slice(2, 4), 16) / 255, b = parseInt(h6.slice(4, 6), 16) / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, h = 0, s = 0;
    if (mx !== mn) {
      var d = mx - mn; s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      if (mx === r) h = (g - b) / d + (g < b ? 6 : 0); else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
      h /= 6;
    }
    var l2 = Math.min(hi, Math.max(lo, l));
    if (l2 === l) return '#' + h6.toUpperCase();
    function hue(p, q, t) { if (t < 0) t += 1; if (t > 1) t -= 1; if (t < 1 / 6) return p + (q - p) * 6 * t; if (t < 1 / 2) return q; if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6; return p; }
    var rr, gg, bb;
    if (s === 0) { rr = gg = bb = l2; } else {
      var q = l2 < 0.5 ? l2 * (1 + s) : l2 + s - l2 * s, p = 2 * l2 - q;
      rr = hue(p, q, h + 1 / 3); gg = hue(p, q, h); bb = hue(p, q, h - 1 / 3);
    }
    function hx(v) { return ('0' + Math.round(v * 255).toString(16)).slice(-2).toUpperCase(); }
    return '#' + hx(rr) + hx(gg) + hx(bb);
  }

  // ---------------------------------------------------------------- the database
  function newDb() {
    return {
      v: 1, subjects: [], entries: [], tests: {}, words: {}, gone: {}, exams: [], exam_subjects: [], todos: [], sessions: [],
      active: null, weekly_schedule: { classes: [], sessions: [], week_start: 5 },
      settings: { lang: 'fa', goal_min: 120 },
      sync: { device_id: uid(), device_name: '', dg: {}, mt: {}, tomb: {}, peers: {}, laptop: null }
    };
  }
  function ensure(db) {
    db = isObj(db) ? db : newDb();
    ['subjects', 'entries', 'exams', 'exam_subjects', 'todos', 'sessions'].forEach(function (k) { if (!Array.isArray(db[k])) db[k] = []; });
    ['tests', 'words', 'gone'].forEach(function (k) { if (!isObj(db[k])) db[k] = {}; });
    if (!isObj(db.settings)) db.settings = {};
    if (!db.settings.lang) db.settings.lang = 'fa';
    if (typeof db.settings.goal_min !== 'number') db.settings.goal_min = 120;
    if (!isObj(db.sync)) db.sync = {};
    var s = db.sync;
    if (!s.device_id) s.device_id = uid();
    ['dg', 'mt', 'tomb', 'peers'].forEach(function (k) { if (!isObj(s[k])) s[k] = {}; });
    if (s.laptop === undefined) s.laptop = null;
    if (db.active === undefined) db.active = null;
    db.weekly_schedule = cleanTimetable(db.weekly_schedule) || { classes: [], sessions: [], week_start: 5 };
    return db;
  }

  // ---------------------------------------------------------------- subjects
  function sameName(a, b) { return String(a).trim().toLowerCase() === String(b).trim().toLowerCase(); }
  function subject(db, sid) { return db.subjects.find(function (s) { return s.id === sid; }) || null; }
  function addSubject(db, name, color, opts) {
    opts = opts || {};
    name = String(name || '').trim().slice(0, 24);
    if (!name) return null;
    var ex = db.subjects.find(function (s) { return sameName(s.name, name); });
    if (ex) return ex;
    var id = null;
    Object.keys(db.gone).forEach(function (k) { if (!id && sameName(db.gone[k].name || '', name)) id = k; });   // a deleted subject comes back with its hours
    if (id) delete db.gone[id]; else id = uid();
    var s = { id: id, name: name, color: normalizeColor(color) || SUBJECT_COLORS[db.subjects.length % SUBJECT_COLORS.length] };
    if (opts.words) s.words = true;
    if (opts.tests === false) s.tests = false;
    db.subjects.push(s);
    return s;
  }
  function editSubject(db, sid, patch) {
    var s = subject(db, sid); if (!s) return null;
    if (patch.name !== undefined && String(patch.name).trim()) s.name = String(patch.name).trim().slice(0, 24);
    var c = patch.color ? normalizeColor(patch.color) : null; if (c) s.color = c;
    if (patch.words !== undefined) { if (patch.words) s.words = true; else delete s.words; }
    if (patch.tests !== undefined) { if (patch.tests) delete s.tests; else s.tests = false; }
    return s;
  }
  function removeSubject(db, sid) {
    var s = subject(db, sid); if (!s) return;
    db.gone[sid] = { name: s.name, color: s.color || '#8A8F9C' };
    db.subjects = db.subjects.filter(function (x) { return x.id !== sid; });
    if (db.active && db.active.subject === sid) db.active = null;
  }
  function subjectOrGhost(db, sid) {
    var s = subject(db, sid); if (s) return s;
    var g = db.gone[sid] || {};
    return { id: sid, name: g.name || '?', color: g.color || '#8A8F9C', ghost: true };
  }

  // ---------------------------------------------------------------- study time
  function addEntry(db, date, sid, sec, source) {
    var e = { id: uid(), date: dkey(date), subject: sid, sec: Math.round(sec), source: source || 'manual', t: Date.now() / 1000 };
    db.entries.push(e);
    return e;
  }
  function addManual(db, date, sid, minutes) { return addEntry(db, date, sid, minutes * 60, 'manual'); }
  function removeEntry(db, id) { db.entries = db.entries.filter(function (e) { return e.id !== id; }); }
  function startTimer(db, sid, now) {
    now = now || Date.now() / 1000;
    if (db.active) stopTimer(db, now);
    db.active = { subject: sid, started: now, last_seen: now };
  }
  function elapsed(db, now) { return db.active ? Math.max(0, (now || Date.now() / 1000) - db.active.started) : 0; }
  function stopTimer(db, now) {
    var a = db.active; if (!a) return 0;
    now = now || Date.now() / 1000;
    var sec = Math.floor(Math.max(0, Math.min(now, a.started + 12 * 3600) - a.started));
    if (sec >= 5) splitOverMidnight(db, a.subject, a.started, a.started + sec, 'stopwatch');
    db.active = null;
    return sec;
  }
  function splitOverMidnight(db, sid, t0, t1, source) {
    var cur = t0;
    while (cur < t1) {
      var d = new Date(cur * 1000), mid = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1).getTime() / 1000;
      var end = Math.min(t1, mid), sec = Math.round(end - cur);
      if (sec > 0) db.entries.push({ id: uid(), date: dkey(d), subject: sid, sec: sec, source: source, t: Date.now() / 1000 });
      cur = end;
    }
  }
  function sessionDay(r) { return dkey(new Date(Number(r.start) * 1000)); }
  function daySec(db, date, includeRunning) {
    var k = typeof date === 'string' ? date : dkey(date), t = 0;
    db.entries.forEach(function (e) { if (e.date === k) t += e.sec | 0; });
    db.sessions.forEach(function (r) { if (sessionDay(r) === k) t += (r.focus_sec | 0); });
    if (includeRunning !== false && db.active && dkey(new Date(db.active.started * 1000)) === k) t += Math.floor(elapsed(db));
    return t;
  }
  function daySubjectTimes(db, date) {
    var k = typeof date === 'string' ? date : dkey(date), by = {}, order = [];
    function add(sid, name, sec) {
      if (sec <= 0) return;
      var s = db.subjects.find(function (x) { return x.id === sid; });
      var key = s ? s.id : 'n:' + String(name || '?').trim().toLowerCase();
      if (!by[key]) { by[key] = { subject: s || subjectOrGhost(db, sid), sec: 0 }; order.push(key); }
      by[key].sec += sec;
    }
    db.entries.forEach(function (e) { if (e.date === k) add(e.subject, null, e.sec | 0); });
    db.sessions.forEach(function (r) {
      if (sessionDay(r) !== k) return;
      var s = db.subjects.find(function (x) { return sameName(x.name, r.subject || ''); });
      add(s ? s.id : '', s ? null : (r.subject || '?'), r.focus_sec | 0);
    });
    if (db.active && dkey(new Date(db.active.started * 1000)) === k) add(db.active.subject, null, Math.floor(elapsed(db)));
    return order.map(function (x) { return by[x]; }).sort(function (a, b) { return b.sec - a.sec; });
  }
  function counter(db, kind, date, sid) { var d = db[kind][typeof date === 'string' ? date : dkey(date)]; return d && d[sid] ? d[sid] : 0; }
  function setCounter(db, kind, date, sid, n) {
    var k = typeof date === 'string' ? date : dkey(date); n = Math.max(0, Math.round(n));
    if (!db[kind][k]) db[kind][k] = {};
    if (n > 0) db[kind][k][sid] = n; else { delete db[kind][k][sid]; if (!Object.keys(db[kind][k]).length) delete db[kind][k]; }
  }

  // ---------------------------------------------------------------- to-dos
  function addTodo(db, date, text) { var t = { id: uid(), date: dkey(date), text: String(text).trim(), done: false }; if (t.text) db.todos.push(t); return t; }
  function toggleTodo(db, id) { db.todos.forEach(function (t) { if (t.id === id) t.done = !t.done; }); }
  function removeTodo(db, id) { db.todos = db.todos.filter(function (t) { return t.id !== id; }); }

  // ---------------------------------------------------------------- exams
  var PCT_RANGE = [-33.4, 100.0], TARAZ_MAX = 20000, RANK_MAX = 5000000;
  function exams(db) { return db.exams.slice().sort(function (a, b) { return (a.date + (a.time || '')) < (b.date + (b.time || '')) ? -1 : 1; }); }
  function addExam(db, name, date, time) {
    var e = { id: uid(), name: String(name).trim().slice(0, 40), date: typeof date === 'string' ? date : dkey(date), time: time || '' };
    if (e.name) db.exams.push(e); return e;
  }
  function updateExam(db, id, patch) {
    db.exams.forEach(function (e) {
      if (e.id !== id) return;
      if (patch.name !== undefined && String(patch.name).trim()) e.name = String(patch.name).trim().slice(0, 40);
      if (patch.date) e.date = patch.date;
      if (patch.time !== undefined) e.time = patch.time;
    });
  }
  function removeExam(db, id) { db.exams = db.exams.filter(function (e) { return e.id !== id; }); }
  function examSubject(db, sid) { return db.exam_subjects.find(function (s) { return s.id === sid; }) || null; }
  function addExamSubject(db, name, color) {
    name = String(name || '').trim().slice(0, 24); if (!name) return null;
    var same = db.exam_subjects.find(function (s) { return sameName(s.name, name); }); if (same) return same;
    var timer = db.subjects.find(function (s) { return sameName(s.name, name); });
    var s = { id: uid(), name: name, color: normalizeColor(color) || (timer && timer.color) || SUBJECT_COLORS[db.exam_subjects.length % SUBJECT_COLORS.length] };
    db.exam_subjects.push(s); return s;
  }
  function editExamSubject(db, sid, patch) {
    var s = examSubject(db, sid); if (!s) return null;
    if (patch.name !== undefined && String(patch.name).trim()) s.name = String(patch.name).trim().slice(0, 24);
    var c = patch.color ? normalizeColor(patch.color) : null; if (c) s.color = c;
    db.exams.forEach(function (e) { ((e.result || {}).subjects || []).forEach(function (r) { if (r.sid === sid) { r.name = s.name; r.color = s.color; } }); });
    return s;
  }
  function removeExamSubject(db, sid) { db.exam_subjects = db.exam_subjects.filter(function (s) { return s.id !== sid; }); }
  function setExamResult(db, eid, r) {
    var e = db.exams.find(function (x) { return x.id === eid; }); if (!e) return false;
    function clampInt(v, lo, hi) { return v === null || v === undefined || v === '' || isNaN(v) ? null : Math.max(lo, Math.min(hi, Math.round(Number(v)))); }
    var rows = [];
    (r.subjects || []).forEach(function (x) {
      var pct = x.pct === null || x.pct === undefined || x.pct === '' || isNaN(x.pct) ? null : Math.max(PCT_RANGE[0], Math.min(PCT_RANGE[1], Number(x.pct)));
      var tz = clampInt(x.taraz, 0, TARAZ_MAX);
      if (pct === null && tz === null) return;
      var s = x.sid ? examSubject(db, x.sid) : null;
      rows.push({ sid: x.sid || '', name: (s ? s.name : String(x.name || '')).trim(), color: (s && s.color) || x.color || '',
                  pct: pct === null ? null : Math.round(pct * 100) / 100, taraz: tz });
    });
    var taraz = clampInt(r.taraz, 0, TARAZ_MAX), rank = clampInt(r.rank, 1, RANK_MAX), region = clampInt(r.rank_region, 1, RANK_MAX);
    if (taraz === null && rank === null && region === null && !rows.length) { delete e.result; return false; }
    e.result = { taraz: taraz, rank: rank, rank_region: region, subjects: rows, note: String(r.note || '').trim().slice(0, 200) };
    return true;
  }
  function clearExamResult(db, eid) { db.exams.forEach(function (e) { if (e.id === eid) delete e.result; }); }
  function examSubjectKey(db, row) { return row.sid && examSubject(db, row.sid) ? row.sid : 'n:' + String(row.name || '').trim().toLowerCase(); }
  function examProgress(db) {
    var ex = exams(db).filter(function (e) { return e.result; }), subj = {}, out = [];
    ex.forEach(function (e, i) {
      var r = e.result, pcts = (r.subjects || []).filter(function (x) { return x.pct !== null && x.pct !== undefined; }).map(function (x) { return x.pct; });
      out.push({ id: e.id, name: e.name, date: e.date, taraz: r.taraz, rank: r.rank, rank_region: r.rank_region,
                 pct_avg: pcts.length ? pcts.reduce(function (a, b) { return a + b; }, 0) / pcts.length : null, note: r.note || '' });
      (r.subjects || []).forEach(function (row) {
        var key = examSubjectKey(db, row), s = row.sid ? examSubject(db, row.sid) : null;
        if (!subj[key]) subj[key] = { key: key, name: s ? s.name : (row.name || '?'), color: (s && s.color) || row.color || '#8A8F9C', points: [] };
        subj[key].points.push([i, row.pct, row.taraz]);
      });
    });
    return { exams: out, subjects: Object.keys(subj).map(function (k) { return subj[k]; }).sort(function (a, b) { return a.name < b.name ? -1 : 1; }) };
  }
  function nextExam(db, today) {
    var t = dkey(today || new Date()), list = exams(db);
    for (var i = 0; i < list.length; i++) if (list[i].date >= t) {
      return { exam: list[i], days: Math.round((parseDkey(list[i].date) - parseDkey(t)) / 86400000) };
    }
    return null;
  }

  // ================================================================ sync engine (port of voidlock/sync.py)
  function strip(kind, rec) {
    var drop = LOCAL_ONLY[kind]; if (!drop) return rec;
    var o = {}; Object.keys(rec).forEach(function (k) { if (drop.indexOf(k) < 0) o[k] = rec[k]; }); return o;
  }
  function sessionId(r) { return String(r.id || '') || 's' + Math.floor(Number(r.start || 0) * 1000); }
  function records(db) {
    var out = {}; KINDS.forEach(function (k) { out[k] = {}; });
    ['subjects', 'entries', 'exams', 'exam_subjects', 'todos'].forEach(function (kind) {
      db[kind].forEach(function (x) { if (isObj(x) && typeof x.id === 'string' && x.id) out[kind][x.id] = strip(kind, clone(x)); });
    });
    db.sessions.forEach(function (r) { if (isObj(r) && isFinite(Number(r.start))) { var id = sessionId(r); var c = clone(r); c.id = id; out.sessions[id] = c; } });
    LEAF_KINDS.forEach(function (kind) {
      Object.keys(db[kind]).forEach(function (day) {
        var row = db[kind][day]; if (!isObj(row)) return;
        Object.keys(row).forEach(function (sid) { var n = parseInt(row[sid], 10); if (n > 0) out[kind][day + '|' + sid] = { n: n }; });
      });
    });
    Object.keys(db.gone).forEach(function (k) { if (isObj(db.gone[k])) out.gone[k] = clone(db.gone[k]); });
    return out;
  }
  function observe(db, now) {
    now = now === undefined ? nowMs() : now;
    var s = db.sync, cur = records(db);
    KINDS.forEach(function (kind) {
      Object.keys(cur[kind]).forEach(function (rid) {
        var key = kind + '|' + rid, d = digest(cur[kind][rid]);
        if (s.dg[key] !== d) { s.dg[key] = d; s.mt[key] = now; }
        if (key in s.tomb && (s.mt[key] || 0) >= s.tomb[key]) delete s.tomb[key];
      });
    });
    Object.keys(s.dg).forEach(function (key) {
      var i = key.indexOf('|'), kind = key.slice(0, i), rid = key.slice(i + 1);
      if (cur[kind] && !(rid in cur[kind])) { delete s.dg[key]; delete s.mt[key]; s.tomb[key] = now; }
    });
    Object.keys(s.tomb).forEach(function (key) { if (now - s.tomb[key] > TOMB_KEEP_MS) delete s.tomb[key]; });
    return stateOf(cur, s);
  }
  function stateOf(cur, s) {
    var out = {}; KINDS.forEach(function (k) { out[k] = { recs: {}, tomb: {} }; });
    KINDS.forEach(function (kind) {
      Object.keys(cur[kind]).forEach(function (rid) { out[kind].recs[rid] = { mt: s.mt[kind + '|' + rid] || 0, v: cur[kind][rid] }; });
    });
    Object.keys(s.tomb).forEach(function (key) {
      var i = key.indexOf('|'), kind = key.slice(0, i), rid = key.slice(i + 1);
      if (out[kind] && !(rid in out[kind].recs)) out[kind].tomb[rid] = s.tomb[key];
    });
    return out;
  }
  function nameIds(recs) {
    var out = {};
    Object.keys(recs).forEach(function (rid) {
      var n = String(recs[rid].v.name || '').trim().toLowerCase();
      if (n) { (out[n] = out[n] || []).push(rid); }
    });
    return out;
  }
  function idMap(a, b) {
    var na = nameIds(a), nb = nameIds(b), m = {};
    Object.keys(na).forEach(function (n) {
      var other = nb[n]; if (!other) return;
      var all = na[n].concat(other.filter(function (x) { return na[n].indexOf(x) < 0; }));
      if (all.length > 1) { var keep = all.slice().sort()[0]; all.forEach(function (i) { if (i !== keep) m[i] = keep; }); }
    });
    return m;
  }
  function remapState(st, subj, exs) {
    var hasS = Object.keys(subj).length, hasE = Object.keys(exs).length;
    if (!hasS && !hasE) return st;
    [['subjects', subj], ['exam_subjects', exs]].forEach(function (p) {
      var kind = p[0], mp = p[1]; if (!Object.keys(mp).length) return;
      var recs = {}, tomb = {};
      Object.keys(st[kind].recs).forEach(function (i) { var j = mp[i] || i, e = st[kind].recs[i]; var v = clone(e.v); v.id = j; recs[j] = { mt: e.mt, v: v }; });
      Object.keys(st[kind].tomb).forEach(function (i) { tomb[mp[i] || i] = st[kind].tomb[i]; });
      st[kind] = { recs: recs, tomb: tomb };
    });
    if (hasS) {
      Object.keys(st.entries.recs).forEach(function (i) { var v = st.entries.recs[i].v; if (subj[v.subject]) v.subject = subj[v.subject]; });
      LEAF_KINDS.forEach(function (kind) {
        function mv(i) { var p = i.indexOf('|'); var sid = i.slice(p + 1); return i.slice(0, p) + '|' + (subj[sid] || sid); }
        var recs = {}, tomb = {};
        Object.keys(st[kind].recs).forEach(function (i) { var j = mv(i), e = st[kind].recs[i]; if (!recs[j] || e.mt >= recs[j].mt) recs[j] = e; });
        Object.keys(st[kind].tomb).forEach(function (i) { tomb[mv(i)] = st[kind].tomb[i]; });
        st[kind] = { recs: recs, tomb: tomb };
      });
      var gr = {}, gt = {};
      Object.keys(st.gone.recs).forEach(function (i) { gr[subj[i] || i] = st.gone.recs[i]; });
      Object.keys(st.gone.tomb).forEach(function (i) { gt[subj[i] || i] = st.gone.tomb[i]; });
      st.gone = { recs: gr, tomb: gt };
    }
    if (hasE) {
      Object.keys(st.exams.recs).forEach(function (i) {
        ((st.exams.recs[i].v.result || {}).subjects || []).forEach(function (row) { if (exs[row.sid]) row.sid = exs[row.sid]; });
      });
    }
    return st;
  }
  function winner(l, lt, r, rt) {
    var ev = [];
    [l, r].forEach(function (e) { if (e) ev.push({ t: e.mt, k: 1, s: sortedStringify(e.v), kind: 'rec', x: e }); });
    [lt, rt].forEach(function (t) { if (t !== undefined && t !== null) ev.push({ t: t, k: 0, s: '', kind: 'tomb', x: t }); });
    if (!ev.length) return null;
    var w = ev[0];
    ev.slice(1).forEach(function (e) {
      if (e.t > w.t || (e.t === w.t && (e.k > w.k || (e.k === w.k && e.s > w.s)))) w = e;
    });
    return w;
  }
  function merge(local, remote) {
    local = clone(local); remote = clone(remote);
    var sm = idMap(local.subjects.recs, remote.subjects.recs), em = idMap(local.exam_subjects.recs, remote.exam_subjects.recs);
    remapState(local, sm, em); remapState(remote, sm, em);
    var merged = {}, conflicts = 0;
    KINDS.forEach(function (kind) {
      var L = local[kind], R = remote[kind], out = { recs: {}, tomb: {} }, ids = {};
      [L.recs, R.recs, L.tomb, R.tomb].forEach(function (m) { Object.keys(m).forEach(function (k) { ids[k] = 1; }); });
      Object.keys(ids).forEach(function (rid) {
        var lr = L.recs[rid], rr = R.recs[rid];
        if (lr && rr && !eq(lr.v, rr.v)) conflicts++;
        var w = winner(lr, L.tomb[rid], rr, R.tomb[rid]);
        if (!w) return;
        if (w.kind === 'rec') out.recs[rid] = { mt: w.x.mt, v: clone(w.x.v) }; else out.tomb[rid] = w.x;
      });
      merged[kind] = out;
    });
    var remap = {}; Object.keys(sm).forEach(function (k) { remap[k] = sm[k]; }); Object.keys(em).forEach(function (k) { remap[k] = em[k]; });
    return { merged: merged, remap: remap, conflicts: conflicts };
  }
  function statsOf(local, merged) {
    var out = {};
    KINDS.forEach(function (kind) {
      var a = local[kind].recs, b = merged[kind].recs, added = 0, removed = 0, updated = 0;
      Object.keys(b).forEach(function (k) { if (!(k in a)) added++; else if (!eq(a[k].v, b[k].v)) updated++; });
      Object.keys(a).forEach(function (k) { if (!(k in b)) removed++; });
      out[kind] = { added: added, removed: removed, updated: updated };
    });
    return out;
  }
  function warningsOf(local, st) {
    var out = [];
    LIST_KINDS.forEach(function (kind) {
      var n = Object.keys(local[kind].recs).length, rm = st[kind].removed;
      if (rm >= MASS_DELETE_MIN && rm * 2 >= n) out.push(kind);
    });
    return out;
  }
  function packState(state) {
    var out = {};
    KINDS.forEach(function (kind) {
      out[kind] = {
        recs: Object.keys(state[kind].recs).map(function (id) { var e = state[kind].recs[id]; return { id: id, mt: e.mt, v: e.v }; }),
        tomb: state[kind].tomb
      };
    });
    return out;
  }
  function makePackage(db) {
    var st = observe(db);
    return { format: FORMAT, version: VERSION, device: { id: db.sync.device_id, name: db.sync.device_name || 'Phone' },
             created: Math.floor(Date.now() / 1000), data: packState(st), timetable: clone(db.weekly_schedule) };
  }
  function cleanTimetable(value) {
    if (!isObj(value)) return null;
    function items(list, classes) {
      if (!Array.isArray(list)) return [];
      return list.filter(function (x) {
        return isObj(x) && Number.isInteger(Number(x.day)) && Number(x.day) >= 0 && Number(x.day) <= 6 &&
          /^\d{2}:\d{2}$/.test(String(x.time || '')) && Number(x.minutes) >= 1 && (!classes || String(x.name || '') !== '');
      }).map(function (x) {
        return classes ? { id: String(x.id || ''), name: String(x.name || '').slice(0, 40), day: Number(x.day), time: String(x.time), minutes: Math.max(1, Math.min(600, Number(x.minutes))), enabled: x.enabled !== false, place: String(x.place || '').slice(0, 40) } :
          { id: String(x.id || ''), subject: String(x.subject || '').slice(0, 40), day: Number(x.day), time: String(x.time), minutes: Math.max(1, Math.min(600, Number(x.minutes))), enabled: x.enabled !== false };
      });
    }
    var ws = Number(value.week_start);
    return { classes: items(value.classes, true), sessions: items(value.sessions, false), week_start: [0, 5, 6].indexOf(ws) >= 0 ? ws : 5 };
  }
  function validRec(kind, r) {
    try {
      if (kind === 'subjects' || kind === 'exam_subjects') return typeof r.name === 'string' && r.name.trim() !== '';
      if (kind === 'entries') return isFinite(parseInt(r.sec, 10)) && typeof r.date === 'string' && r.date.length === 10;
      if (kind === 'exams') return typeof r.name === 'string' && typeof r.date === 'string' && r.date.length === 10;
      if (kind === 'todos') return typeof r.text === 'string';
      if (kind === 'sessions') return isFinite(Number(r.start));
      if (kind === 'tests' || kind === 'words') return Number.isInteger(r.n) && r.n > 0;
      return true;
    } catch (e) { return false; }
  }
  function cleanState(data) {
    if (!isObj(data)) throw new SyncError('The file has no data.');
    var out = {}; KINDS.forEach(function (k) { out[k] = { recs: {}, tomb: {} }; });
    KINDS.forEach(function (kind) {
      var part = data[kind]; if (!isObj(part)) return;
      (Array.isArray(part.recs) ? part.recs : []).forEach(function (x) {
        if (!isObj(x) || typeof x.id !== 'string' || !x.id || !isObj(x.v)) return;
        var mt = parseInt(x.mt, 10); if (!isFinite(mt)) return;
        if (LIST_KINDS.indexOf(kind) >= 0 && kind !== 'sessions' && x.v.id !== x.id) return;
        if ((kind === 'tests' || kind === 'words') && x.id.indexOf('|') < 0) return;
        var v = clone(x.v); if (kind === 'sessions') v.id = x.id;
        if (validRec(kind, v)) out[kind].recs[x.id] = { mt: mt, v: v };
      });
      if (isObj(part.tomb)) Object.keys(part.tomb).forEach(function (rid) {
        var ts = parseInt(part.tomb[rid], 10);
        if (rid && isFinite(ts) && !((kind === 'tests' || kind === 'words') && rid.indexOf('|') < 0)) out[kind].tomb[rid] = ts;
      });
    });
    return out;
  }
  function parsePackage(raw) {
    var pkg;
    try { pkg = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch (e) { throw new SyncError('That file is not a VOIDLOCK sync file.'); }
    if (!isObj(pkg) || pkg.format !== FORMAT) throw new SyncError('That file is not a VOIDLOCK sync file.');
    if (parseInt(pkg.version, 10) !== VERSION) throw new SyncError('This sync file was made by a different version of VOIDLOCK. Update both devices.');
    if (!isObj(pkg.device) || typeof pkg.device.id !== 'string' || !pkg.device.id) throw new SyncError('That sync file has no device id.');
    return { device: { id: pkg.device.id, name: String(pkg.device.name || '?').slice(0, 60) }, created: pkg.created, data: cleanState(pkg.data), timetable: cleanTimetable(pkg.timetable) };
  }
  function prepare(db, raw) {
    var pkg = parsePackage(raw);
    if (pkg.device.id === db.sync.device_id) throw new SyncError('This file was made by this same device.');
    var local = observe(db), mg = merge(local, pkg.data);
    var sm = {}, em = {};
    Object.keys(mg.remap).forEach(function (k) { if (local.subjects.recs[k]) sm[k] = mg.remap[k]; if (local.exam_subjects.recs[k]) em[k] = mg.remap[k]; });
    var mine = remapState(clone(local), sm, em), st = statsOf(mine, mg.merged);
    var timetableChanged = !!pkg.timetable && !eq(db.weekly_schedule, pkg.timetable);
    var plan = { peer: pkg.device, local: mine, remote: pkg.data, merged: mg.merged, remap: mg.remap, conflicts: mg.conflicts, stats: st, warn: warningsOf(mine, st), timetable: pkg.timetable, timetableChanged: timetableChanged };
    plan.changes = function () { var n = timetableChanged ? 1 : 0; Object.keys(st).forEach(function (k) { n += st[k].added + st[k].updated + st[k].removed; }); return n; };
    plan.removed = function () { var n = 0; LIST_KINDS.forEach(function (k) { n += st[k].removed; }); return n; };
    plan.added = function () { var n = 0; LIST_KINDS.forEach(function (k) { n += st[k].added; }); return n; };
    return plan;
  }
  function sortBy(items, keys) {
    return items.slice().sort(function (a, b) {
      for (var i = 0; i < keys.length; i++) { var x = String(a[keys[i]] === undefined ? '' : a[keys[i]]), y = String(b[keys[i]] === undefined ? '' : b[keys[i]]); if (x !== y) return x < y ? -1 : 1; }
      return 0;
    });
  }
  function applyMerged(db, merged, remap) {
    remap = remap || {};
    var recs = {}; KINDS.forEach(function (k) { recs[k] = {}; Object.keys(merged[k].recs).forEach(function (i) { recs[k][i] = merged[k].recs[i].v; }); });
    var order = {};
    ['subjects', 'todos', 'exam_subjects'].forEach(function (k) { order[k] = db[k].map(function (r) { return remap[r.id] || r.id; }); });
    function keepOrder(kind) {
      var first = order[kind].filter(function (i) { return i in recs[kind]; }).map(function (i) { return recs[kind][i]; });
      var seen = {}; first.forEach(function (r) { seen[r.id] = 1; });
      var rest = Object.keys(recs[kind]).filter(function (i) { return !seen[i]; }).map(function (i) { return recs[kind][i]; });
      return clone(first.concat(rest));
    }
    db.subjects = keepOrder('subjects'); db.exam_subjects = keepOrder('exam_subjects'); db.todos = keepOrder('todos');
    db.entries = clone(sortBy(Object.keys(recs.entries).map(function (i) { return recs.entries[i]; }), ['date', 't', 'id']));
    db.exams = clone(sortBy(Object.keys(recs.exams).map(function (i) { return recs.exams[i]; }), ['date', 'time', 'id']));
    LEAF_KINDS.forEach(function (kind) {
      var out = {};
      Object.keys(recs[kind]).sort().forEach(function (key) { var p = key.indexOf('|'); var day = key.slice(0, p), sid = key.slice(p + 1); (out[day] = out[day] || {})[sid] = recs[kind][key].n; });
      db[kind] = out;
    });
    db.gone = clone(recs.gone);
    if (db.active && remap[db.active.subject]) db.active.subject = remap[db.active.subject];
    db.sessions = clone(Object.keys(recs.sessions).map(function (i) { return recs.sessions[i]; }).sort(function (a, b) { return Number(a.start) - Number(b.start); }));
  }
  function commit(db, plan) {
    applyMerged(db, plan.merged, plan.remap);
    if (plan.timetable) db.weekly_schedule = clone(plan.timetable);
    var s = db.sync, cur = records(db);
    s.dg = {}; s.mt = {};
    KINDS.forEach(function (kind) {
      Object.keys(cur[kind]).forEach(function (rid) {
        var key = kind + '|' + rid, e = plan.merged[kind].recs[rid];
        s.dg[key] = digest(cur[kind][rid]); s.mt[key] = e ? e.mt : nowMs();
      });
    });
    s.tomb = {};
    KINDS.forEach(function (kind) { Object.keys(plan.merged[kind].tomb).forEach(function (rid) { if (!(rid in cur[kind])) s.tomb[kind + '|' + rid] = plan.merged[kind].tomb[rid]; }); });
    s.peers[plan.peer.id] = { name: plan.peer.name, last_sync: Math.floor(Date.now() / 1000) };
  }
  function forgetFingerprints(db) { db.sync.dg = {}; db.sync.mt = {}; db.sync.tomb = {}; }

  var Core = {
    FORMAT: FORMAT, VERSION: VERSION, SUBJECT_COLORS: SUBJECT_COLORS, SyncError: SyncError, KINDS: KINDS, LIST_KINDS: LIST_KINDS,
    uid: uid, dkey: dkey, parseDkey: parseDkey, addDays: addDays, clone: clone, eq: eq, digest: digest, normalizeColor: normalizeColor,
    newDb: newDb, ensure: ensure,
    subject: subject, addSubject: addSubject, editSubject: editSubject, removeSubject: removeSubject, subjectOrGhost: subjectOrGhost,
    addEntry: addEntry, addManual: addManual, removeEntry: removeEntry, startTimer: startTimer, stopTimer: stopTimer, elapsed: elapsed,
    daySec: daySec, daySubjectTimes: daySubjectTimes, counter: counter, setCounter: setCounter,
    addTodo: addTodo, toggleTodo: toggleTodo, removeTodo: removeTodo,
    exams: exams, addExam: addExam, updateExam: updateExam, removeExam: removeExam, examSubject: examSubject, addExamSubject: addExamSubject,
    editExamSubject: editExamSubject, removeExamSubject: removeExamSubject, setExamResult: setExamResult, clearExamResult: clearExamResult,
    examProgress: examProgress, nextExam: nextExam,
    records: records, observe: observe, makePackage: makePackage, parsePackage: parsePackage, prepare: prepare, commit: commit,
    forgetFingerprints: forgetFingerprints, merge: merge
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = Core; else root.Core = Core;
})(typeof window !== 'undefined' ? window : globalThis);
