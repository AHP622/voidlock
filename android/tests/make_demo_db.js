/* A good-looking demo database for screenshots: node make_demo_db.js <out.json> [fa|en] */
const path = require('path'), fs = require('fs');
const www = path.join(__dirname, '../app/src/main/assets/www/js');
global.Core = require(path.join(www, 'core.js'));
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
db.settings.lang = lang; db.settings.goal_min = 240; db.settings.welcomed = true; db.settings.seen_version = '1.12.0';
db.settings.tips_seen = { today: 1, stats: 1, exams: 1, tasks: 1, more: 1 };
fs.writeFileSync(out, JSON.stringify(db));
