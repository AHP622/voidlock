/* A good-looking demo database for screenshots: node make_demo_db.js <out.json> [fa|en] */
const path = require('path'), fs = require('fs');
const www = path.join(__dirname, '../app/src/main/assets/www/js');
global.Core = require(path.join(www, 'core.js')); global.Classes = require(path.join(www, 'classes.js'));
const [, , out, lang = 'fa'] = process.argv;
const db = Core.ensure(Core.newDb()); db.subjects = [];
let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const names = lang === 'fa' ? ['ریاضی', 'فیزیک', 'شیمی', 'زیست', 'ادبیات', 'عربی'] : ['Math', 'Physics', 'Chemistry', 'Biology', 'Literature', 'English'];
const colors = ['#8B5CF6', '#00C2FF', '#34D399', '#FBBF24', '#FF5DA2', '#60A5FA'];
const subs = names.map((n, i) => Core.addSubject(db, n, colors[i]));
const day = (n) => Core.addDays(new Date(), -n);
for (let k = 34; k >= 1; k--) {
  if (rnd() < 0.1) continue;
  const picks = subs.slice().sort(() => rnd() - 0.5).slice(0, 2 + Math.floor(rnd() * 3));
  picks.forEach((s) => Core.addManual(db, day(k), s.id, 25 + Math.floor(rnd() * 95)));
  picks.slice(0, 2).forEach((s) => { Core.setCounter(db, 'tests', Core.dkey(day(k)), s.id, 10 + Math.floor(rnd() * 50)); });
  if (rnd() < 0.4) Core.setCounter(db, 'words', Core.dkey(day(k)), subs[5].id, 10 + Math.floor(rnd() * 30));
}
subs.slice(0, 4).forEach((s, i) => Core.addManual(db, new Date(), s.id, [95, 50, 40, 25][i]));
Core.setCounter(db, 'tests', Core.dkey(new Date()), subs[0].id, 36); Core.setCounter(db, 'words', Core.dkey(new Date()), subs[5].id, 18);
const xs = names.slice(0, 5).map((n, i) => Core.addExamSubject(db, n, colors[i]));
[[28, 'آزمون ۱ ماز', 0], [21, 'آزمون ۲ ماز', 1], [14, 'آزمون ۳ ماز', 2], [7, 'آزمون ۴ ماز', 3]].forEach(([off, nm, i]) => {
  const e = Core.addExam(db, lang === 'fa' ? nm : 'Mock ' + (i + 1), Core.dkey(day(off)));
  Core.setExamResult(db, e.id, { taraz: 6100 + i * 210 + Math.floor(rnd() * 90), rank: 9800 - i * 1100 + Math.floor(rnd() * 200), rank_region: 480 - i * 55 + Math.floor(rnd() * 12),
    subjects: xs.map((x) => ({ sid: x.id, pct: 38 + i * 8 + Math.floor(rnd() * 25), taraz: 5200 + i * 250 + Math.floor(rnd() * 900) })) });
});
Core.addExam(db, lang === 'fa' ? 'آزمون جامع ۵' : 'Final mock', Core.dkey(Core.addDays(new Date(), 6)));
[['حل ۴۰ تست ریاضی', 0], ['مرور فصل ۳ فیزیک', 0], ['خلاصه‌نویسی شیمی', 1]].forEach(([tx, off]) => { try { Core.addTodo(db, Core.addDays(new Date(), off), lang === 'fa' ? tx : 'Task ' + tx.length); } catch (e) {} });
const clsData = lang === 'fa' ? [['حسابان', 0, '17:00', 'معین کرمی'], ['فیزیک', 1, '19:00', 'دکتر رضایی'], ['شیمی', 2, '16:30', 'آنلاین'], ['زیست', 3, '18:00', 'آنلاین'], ['ادبیات', 5, '09:00', 'آقای احمدی']]
  : [['Calculus', 0, '17:00', 'Mr. Karimi'], ['Physics', 1, '19:00', 'Dr. Rezaei'], ['Chemistry', 2, '16:30', 'Online'], ['Biology', 3, '18:00', 'Online'], ['Literature', 5, '09:00', 'Mr. Ahmadi']];
clsData.forEach(([n, d, tm, pl]) => Core.addClass(db, { name: n, day: d, time: tm, minutes: 90, remind: 15, place: pl }));
// a class running right now or about to start, so the "next class" card has something to show
{ const now = new Date(), st = new Date(now.getTime() + 70 * 60000); Core.addClass(db, { name: lang === 'fa' ? 'کلاس امروز' : 'Today class', day: Classes.weekday(now), time: String(st.getHours()).padStart(2, '0') + ':' + String(st.getMinutes()).padStart(2, '0'), minutes: 60, remind: 10, place: lang === 'fa' ? 'سالن ۲' : 'Hall 2' }); }
db.settings.lang = lang; db.settings.goal_min = 240; db.settings.welcomed = true; db.settings.seen_version = JSON.parse(JSON.stringify(require('fs').readFileSync(path.join(www, '../config.js'), 'utf8').match(/version: "([^"]+)"/)[1]));
db.settings.tips_seen = { today: 1, stats: 1, exams: 1, tasks: 1, more: 1 };
fs.writeFileSync(out, JSON.stringify(db));
