/* Phone side of the Wi-Fi sync test: used by lan_interop_test.py (the computer's server runs in Python). */
const path = require('path'), fs = require('fs');
const www = path.join(__dirname, '../app/src/main/assets/www/js');
global.Core = require(path.join(www, 'core.js'));
require(path.join(www, 'native.js'));           // sets global Native / Net (browser fetch fallback = Node's fetch)
const [, , port, code, file] = process.argv;
(async () => {
  const db = Core.ensure(JSON.parse(fs.readFileSync(file, 'utf8')));
  const addr = '127.0.0.1:' + port, out = {};
  out.ping = await Net.ping(addr);
  out.wrong = await Net.pair(addr, '000000', { id: db.sync.device_id, name: 'JS phone' });
  const p = await Net.pair(addr, code, { id: db.sync.device_id, name: 'JS phone' });
  out.pair = { ok: p.ok };
  db.sync.laptop = { addr, token: p.token, id: p.device && p.device.id, name: p.device && p.device.name };
  out.rev0 = (await Net.rev(db.sync.laptop)).rev;
  const s1 = await Net.syncOnce(db, db.sync.laptop);
  out.sync1 = { ok: s1.ok, changes: s1.changes, rev: s1.rev };
  out.entries = db.entries.length; out.todos = db.todos.map((t) => t.text);
  const s2 = await Net.syncOnce(db, db.sync.laptop);
  out.sync2 = { ok: s2.ok, changes: s2.changes, rev: s2.rev };
  out.badToken = (await Net.rev({ addr, token: 'nope' })).status;
  fs.writeFileSync(file, JSON.stringify(db));
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
