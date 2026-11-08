/* Unit tests of the phone app's logic (no browser, no Android): node android/tests/js_unit_test.js */
const fs = require('fs'), path = require('path');
const www = path.join(__dirname, '../app/src/main/assets/www/js');
global.Core = require(path.join(www, 'core.js')); global.Jalali = require(path.join(www, 'jalali.js'));
const I18n = global.I18n = require(path.join(www, 'i18n.js'));
global.Charts = require(path.join(www, 'charts.js')); global.Report = require(path.join(www, 'report.js'));
let fails = 0;
const ok = (c, n) => { console.log((c ? 'PASS ' : 'FAIL ') + n); if (!c) fails++; };
const fresh = (name) => { const d = Core.ensure(Core.newDb()); d.sync.device_name = name || 'x'; return d; };

// ---- texts: every key used in the code exists in both languages
const files = fs.readdirSync(www).filter((f) => f.endsWith('.js'));
const used = new Set();
files.forEach((f) => { const src = fs.readFileSync(path.join(www, f), 'utf8'); for (const m of src.matchAll(/\b[tT]\(\s*'([a-z_0-9]+)'/g)) used.add(m[1]); });
['nav_today', 'nav_stats', 'nav_exams', 'nav_tasks', 'nav_more', 'k_taraz', 'k_rank', 'k_region', 'k_subjects', 'k_percent', 'theme_ocean', 'theme_void', 'theme_midnight', 'theme_paper'].forEach((k) => used.add(k));
used.delete('key');                               // the example in the comment at the top of i18n.js
const missing = [...used].filter((k) => !(k in I18n.S.fa) || !(k in I18n.S.en));
ok(!missing.length, 'every text key used in the code exists in Persian and English ' + (missing.length ? JSON.stringify(missing) : '(' + used.size + ' keys)'));
ok(JSON.stringify(Object.keys(I18n.S.fa).sort()) === JSON.stringify(Object.keys(I18n.S.en).sort()), 'both languages have exactly the same keys');
I18n.setLang('fa');
ok(I18n.dateStr('2026-11-06', true) === 'جمعه ۱۵ آبان' && I18n.num(1234567) === '۱٬۲۳۴٬۵۶۷', 'Persian dates (Jalali) and digits');

// ---- Jalali against the browser's own persian calendar
const fmt = new Intl.DateTimeFormat('en-u-ca-persian-nu-latn', { year: 'numeric', month: 'numeric', day: 'numeric' });
let bad = 0;
for (let t = Date.UTC(2015, 0, 1); t < Date.UTC(2040, 0, 1); t += 86400000 * 7) {
  const d = new Date(t + 12 * 3600e3), p = fmt.formatToParts(d).reduce((a, x) => { a[x.type] = x.value; return a; }, {});
  const j = Jalali.toJalali(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()), g = Jalali.toGregorian(j.jy, j.jm, j.jd);
  if (j.jy !== +(p.relatedYear || p.year) || j.jm !== +p.month || j.jd !== +p.day || g.gy !== d.getUTCFullYear() || g.gm !== d.getUTCMonth() + 1 || g.gd !== d.getUTCDate()) bad++;
}
ok(bad === 0, 'Jalali conversion matches Intl for 25 years');

// ---- colours
ok(Core.SUBJECT_COLORS.every((c) => Core.normalizeColor(c) === c), 'the preset colours are never changed');
ok(Core.normalizeColor('#000000') === '#616161' && Core.normalizeColor('#FFFFFF') === '#BDBDBD' && Core.normalizeColor('#1a1a40') === '#38388A', 'black / white / very dark colours are lifted exactly like the computer does');
ok(Core.normalizeColor('blue') === null && Core.normalizeColor('#12') === null, 'invalid colours are refused');

// ---- subjects, time, counters
let db = fresh(), m = Core.addSubject(db, 'Math', '#14B8A6');
ok(m.color === '#14B8A6' && Core.addSubject(db, ' math ') === m, 'a custom colour is kept; the same name is the same subject');
Core.addManual(db, new Date(), m.id, 90); Core.removeSubject(db, m.id);
ok(!Core.subject(db, m.id) && db.gone[m.id].name === 'Math' && Core.subjectOrGhost(db, m.id).ghost, 'a deleted subject keeps its name for its hours');
const back = Core.addSubject(db, 'math');
ok(back.id === m.id && !(m.id in db.gone), 'adding it again gives the old id back (the hours reconnect)');
Core.startTimer(db, m.id, new Date(2026, 0, 10, 23, 59, 50).getTime() / 1000);
const sec = Core.stopTimer(db, new Date(2026, 0, 11, 0, 0, 20).getTime() / 1000);
const e1 = db.entries.filter((e) => e.source === 'stopwatch').sort((a, b) => a.date < b.date ? -1 : 1);
ok(sec === 30 && e1.length === 2 && e1[0].date === '2026-01-10' && e1[0].sec === 10 && e1[1].date === '2026-01-11' && e1[1].sec === 20, 'a stopwatch over midnight is split between the two days');
Core.startTimer(db, m.id, Date.now() / 1000); Core.stopTimer(db, Date.now() / 1000 + 2);
ok(db.entries.filter((e) => e.source === 'stopwatch').length === 2, 'a stopwatch shorter than 5 seconds logs nothing');
db.sessions.push({ id: 'sess1', start: new Date(2026, 0, 12, 10, 0, 0).getTime() / 1000, subject: 'Math', planned_min: 25, focus_sec: 1500, status: 'completed' });
ok(Core.daySec(db, '2026-01-12') === 1500 && Core.daySubjectTimes(db, '2026-01-12')[0].subject.id === m.id, "a computer focus session counts in the day's total and is matched to the subject by name");
Core.setCounter(db, 'tests', '2026-01-12', m.id, 5); Core.setCounter(db, 'tests', '2026-01-12', m.id, -3);
ok(Core.counter(db, 'tests', '2026-01-12', m.id) === 0 && !db.tests['2026-01-12'], 'a counter never goes below zero and leaves no empty day');

// ---- exams
db = fresh(); const ex = Core.addExam(db, 'Mock', '2026-11-10'), xs = Core.addExamSubject(db, 'Calculus');
ok(Core.setExamResult(db, ex.id, { taraz: 99999, rank: 0, rank_region: 12.4, subjects: [{ sid: xs.id, pct: 150, taraz: -5 }], note: 'x' }), 'a result is saved');
const r = db.exams[0].result;
ok(r.taraz === 20000 && r.rank === 1 && r.rank_region === 12 && r.subjects[0].pct === 100 && r.subjects[0].taraz === 0, 'numbers are clamped like on the computer');
ok(!Core.setExamResult(db, ex.id, {}) && !db.exams[0].result, 'a result with nothing in it is removed');
Core.setExamResult(db, ex.id, { taraz: 7000, rank_region: 40, subjects: [{ sid: xs.id, pct: 55, taraz: 6100 }] });
Core.editExamSubject(db, xs.id, { name: 'Calc', color: '#9333EA' }); Core.removeExamSubject(db, xs.id);
const ep = Core.examProgress(db);
ok(ep.subjects.length === 1 && ep.subjects[0].name === 'Calc' && ep.subjects[0].color === '#9333EA' && ep.exams[0].rank_region === 40, 'a deleted exam subject keeps its name, colour and points');

// ---- sync between two phones (same engine as phone <-> computer)
const A = fresh('A'), B = fresh('B'); let t0 = Date.now() - 100000;                   // realistic clock (a tombstone older than 400 days is dropped)
const sa = Core.addSubject(A, 'Physics'); Core.addManual(A, new Date(), sa.id, 30); const td = Core.addTodo(A, new Date(), 'buy pens');
Core.observe(A, t0);
const send = (from, to, now) => { Core.observe(to, now); const plan = Core.prepare(to, JSON.stringify(Core.makePackage(from))); Core.commit(to, plan); return plan; };
let plan = send(A, B, t0 + 10); ok(plan.stats.entries.added === 1 && B.todos.length === 1, 'a package brings the other device\'s data');
Core.removeTodo(B, td.id); Core.observe(B, t0 + 100);
plan = send(B, A, t0 + 110); ok(A.todos.length === 0, 'a deletion travels');
Core.addTodo(B, new Date(), 'later'); Core.observe(B, t0 + 200);
const old = JSON.stringify(Core.makePackage(A)); const before = JSON.stringify(Core.records(B));
Core.commit(B, Core.prepare(B, old)); ok(JSON.stringify(Core.records(B)) === before, 'an old package changes nothing');
try { Core.prepare(B, JSON.stringify(Core.makePackage(B))); ok(false, 'own package refused'); } catch (e) { ok(e.name === 'SyncError', 'a package from this same device is refused'); }
try { Core.prepare(B, '{"format":"voidlock-sync","version":9,"device":{"id":"x"},"data":{}}'); ok(false, 'version'); } catch (e) { ok(/different version/.test(e.message), 'another format version is refused with a clear message'); }

// ---- report (HTML / CSV) and charts run left to right
db = fresh(); const rm = Core.addSubject(db, 'Math', '#8B5CF6'), rp = Core.addSubject(db, 'Physics', '#00C2FF');
const dayN = (n) => Core.dkey(Core.addDays(new Date(), -n));
Core.addManual(db, Core.addDays(new Date(), -2), rm.id, 90); Core.addManual(db, Core.addDays(new Date(), -1), rp.id, 45);
db.entries.push({ id: 'orph1', date: dayN(1), subject: 'gone-a', sec: 600, source: 'manual', t: 1 }, { id: 'orph2', date: dayN(1), subject: 'gone-b', sec: 300, source: 'manual', t: 2 });
Core.setCounter(db, 'tests', dayN(1), rp.id, 12);
const ex2 = Core.addExam(db, 'Mock A', dayN(1)), xs2 = Core.addExamSubject(db, 'Calculus');
Core.setExamResult(db, ex2.id, { taraz: 7000, rank: 900, rank_region: 40, subjects: [{ sid: xs2.id, pct: 55, taraz: 6100 }] });
for (const lang of ['fa', 'en']) {
  I18n.setLang(lang);
  const rep = Report.build(db, dayN(6), dayN(0)), lines = rep.csv.replace('\uFEFF', '').split('\r\n');
  ok(rep.html.includes('Math') && rep.html.includes('Physics') && rep.html.includes('Mock A') && rep.html.includes('<svg'), `[${lang}] the HTML report has subjects, the exam and charts`);
  ok(rep.csv.charCodeAt(0) === 0xFEFF && lines[0].split(',').length >= 7 && lines.length >= 8, `[${lang}] the CSV starts with the UTF-8 mark and has one row per day`);
  ok((rep.html.match(new RegExp(I18n.t('unknown_subject'), 'g')) || []).length >= 1 && lines[0].split(I18n.t('unknown_subject')).length === 2, `[${lang}] old deleted subjects are one line called "${I18n.t('unknown_subject')}"`);
  ok(rep.html.includes(`dir="${lang === 'fa' ? 'rtl' : 'ltr'}"`) && rep.html.includes('direction:ltr'), `[${lang}] the page follows the language, the charts stay left to right`);
}
I18n.setLang('fa');
const dd = [0, 1, 2, 3, 4].map((i) => ({ dk: dayN(4 - i), label: String(i), month: '', exam: false, sec: 3600 * (i + 1), parts: [{ name: 'Math', color: '#8B5CF6', sec: 3600 * (i + 1) }] }));
const chart = Charts.studyChart({ t: I18n.t, fa: true, days: dd, goalSec: 7200, width: 340 });
const barXs = [...chart.svg.matchAll(/<rect x="([\d.]+)" y="[\d.]+" width="[\d.]+" height="[\d.]+" rx="\d" fill="#8B5CF6"/g)].map((m) => +m[1]);
ok(barXs.length === 5 && barXs.every((x, i) => i === 0 || x > barXs[i - 1]), 'a Persian study chart runs from the left (oldest) to the right (newest)');
ok(/<text x="(2[0-9]|3[0-3])(\.\d+)?" y="[\d.]+" font-size="10.5" text-anchor="end"/.test(chart.svg), 'and its value axis is on the left');
console.log(fails ? `\n${fails} failure(s)` : '\nALL PASSED'); process.exit(fails ? 1 : 0);
