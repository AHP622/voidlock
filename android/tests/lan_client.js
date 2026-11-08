/* Phone side of the Wi-Fi sync test (encrypted protocol): used by lan_interop_test.py. Prints "SAS <number>" when it waits for the
 * person to allow the pairing on the computer, then one JSON line with the results. */
const path = require('path'), fs = require('fs');
const www = path.join(__dirname, '../app/src/main/assets/www/js');
global.Core = require(path.join(www, 'core.js'));
require(path.join(www, 'native.js'));           // sets global Native / Net (browser fetch fallback = Node's fetch)
const [, , port, code, file] = process.argv;
(async () => {
  const db = Core.ensure(JSON.parse(fs.readFileSync(file, 'utf8')));
  const addr = '127.0.0.1:' + port, out = {};
  out.ping = await Net.ping(addr);
  const dev = { id: db.sync.device_id, name: 'JS phone' };
  out.wrong = await Net.pairStart(addr, '000000', dev);
  const st = await Net.pairStart(addr, code, dev);
  out.pairStart = { ok: st.ok, sasLen: st.sas && st.sas.length };
  process.stdout.write('SAS ' + st.sas + '\n');
  const fin = await Net.pairFinish(st, null);
  out.pair = { ok: fin.ok, error: fin.error };
  db.sync.laptop = fin.lap;
  Net.persist = () => fs.writeFileSync(file, JSON.stringify(db));
  out.rev0 = (await Net.rev(db.sync.laptop)).rev;
  const s1 = await Net.syncOnce(db, db.sync.laptop);
  out.sync1 = { ok: s1.ok, changes: s1.changes, rev: s1.rev };
  out.entries = db.entries.length; out.todos = db.todos.map((t) => t.text);
  const s2 = await Net.syncOnce(db, db.sync.laptop);
  out.sync2 = { ok: s2.ok, changes: s2.changes, rev: s2.rev };
  out.badKey = (await Net.rev({ addr, did: db.sync.device_id, key: Net.crypto.b64e(new Uint8Array(32).fill(7)), seq: 0 })).status;
  // a request recorded earlier and sent again (an old counter value) must be refused by the computer
  const lap = db.sync.laptop, K = Net.crypto.b64d(lap.key);
  const old = await Net.crypto.seal(K, lap.did, 'req', { seq: 5, op: 'rev' });
  const r = await fetch('http://' + addr + '/v2/call', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(old) });
  out.oldCounter = r.status;
  // and the very same envelope twice
  const fresh = await Net.crypto.seal(K, lap.did, 'req', { seq: Date.now() + 100000, op: 'rev' });
  const a1 = await fetch('http://' + addr + '/v2/call', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fresh) });
  const a2 = await fetch('http://' + addr + '/v2/call', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fresh) });
  out.sameTwice = [a1.status, a2.status];
  fs.writeFileSync(file, JSON.stringify(db));
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
