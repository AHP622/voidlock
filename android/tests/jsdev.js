#!/usr/bin/env node
/* A phone for tests: keeps its database in a JSON file and runs one command per call (used by tests/interop_test.py). */
const fs = require('fs'), path = require('path');
const Core = require(path.join(__dirname, '../app/src/main/assets/www/js/core.js'));
const [, , cmd, file, arg] = process.argv;
const load = () => Core.ensure(JSON.parse(fs.readFileSync(file, 'utf8')));
const save = (db) => fs.writeFileSync(file, JSON.stringify(db));
const out = (x) => process.stdout.write(JSON.stringify(x));
function readStdin() { return fs.readFileSync(0, 'utf8'); }
function byName(db, kind, name) { return db[kind].find((s) => s.name.toLowerCase() === String(name).toLowerCase()); }

if (cmd === 'init') {
  const db = Core.newDb(); db.sync.device_name = 'JS phone'; db.subjects = []; save(db); out({ id: db.sync.device_id });
} else if (cmd === 'op') {
  const db = load(), op = JSON.parse(arg), d = op.date ? Core.parseDkey(op.date) : new Date();
  switch (op.t) {
    case 'add_subject': Core.addSubject(db, op.name, op.color); break;
    case 'remove_subject': { const s = byName(db, 'subjects', op.name); if (s) Core.removeSubject(db, s.id); break; }
    case 'add_entry': { const s = byName(db, 'subjects', op.name); if (s) Core.addManual(db, d, s.id, op.min); break; }
    case 'remove_entry': { const e = db.entries.find((x) => x.sec === op.sec); if (e) Core.removeEntry(db, e.id); break; }
    case 'add_todo': Core.addTodo(db, d, op.text); break;
    case 'remove_todo': { const t = db.todos.find((x) => x.text === op.text); if (t) Core.removeTodo(db, t.id); break; }
    case 'toggle_todo': { const t = db.todos.find((x) => x.text === op.text); if (t) Core.toggleTodo(db, t.id); break; }
    case 'add_exam': Core.addExam(db, op.name, d); break;
    case 'remove_exam': { const e = db.exams.find((x) => x.name === op.name); if (e) Core.removeExam(db, e.id); break; }
    case 'add_exam_subject': Core.addExamSubject(db, op.name, op.color); break;
    case 'exam_result': {
      const e = db.exams.find((x) => x.name === op.name), s = byName(db, 'exam_subjects', op.subject);
      if (e && s) Core.setExamResult(db, e.id, { taraz: op.taraz, rank: op.rank, rank_region: op.region, subjects: [{ sid: s.id, pct: op.pct, taraz: op.taraz }] });
      break;
    }
    case 'counter': { const s = byName(db, 'subjects', op.name); if (s) Core.setCounter(db, op.kind, d, s.id, op.n); break; }
  }
  save(db); out({ ok: true });
} else if (cmd === 'export') {
  const db = load(); const p = Core.makePackage(db); save(db); out(p);
} else if (cmd === 'import') {
  const db = load();
  try {
    const plan = Core.prepare(db, readStdin()); Core.commit(db, plan); save(db);
    out({ ok: true, stats: plan.stats, warn: plan.warn, changes: plan.changes() });
  } catch (e) { out({ ok: false, error: String(e.message || e), name: e.name }); }
} else if (cmd === 'records') {
  const db = load(); out(Core.records(db));
} else if (cmd === 'forget') {
  const db = load(); Core.forgetFingerprints(db); save(db); out({ ok: true });
}
