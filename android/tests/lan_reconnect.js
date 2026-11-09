/* The computer's address changed after the pairing (new port here; a new IP in real life): the phone must find it again by itself.
 * node lan_reconnect.js <phone.json> <old port> -> prints one JSON line. Used by lan_interop_test.py */
const path = require('path'), fs = require('fs');
const www = path.join(__dirname, '../app/src/main/assets/www/js');
global.Core = require(path.join(www, 'core.js'));
require(path.join(www, 'native.js'));
const [, , file, oldPort, mode] = process.argv;
(async () => {
  const db = Core.ensure(JSON.parse(fs.readFileSync(file, 'utf8'))), lap = db.sync.laptop, out = {};
  Net.persist = () => fs.writeFileSync(file, JSON.stringify(db));
  out.before = lap.addr;
  lap.seq = Math.max(lap.seq || 0, Date.now() + 300000);     // lan_client.js forged a counter 100 s ahead on the computer; a real phone only ever grows its own
  lap.addr = '127.0.0.1:' + oldPort;                         // what the phone remembers: nobody answers there any more
  if (mode === 'scan') {                                     // the address changed to a different network host: found by scanning the phone's own subnet
    Native.localIps = () => ['127.0.0.5'];
    lap.addr = '10.255.255.1:47821';
    const r3 = await Net.rev(lap, { force: true });
    out.scan = { status: r3.status, addr: lap.addr };
  } else if (mode === 'off') {                                      // the computer is really off: a clean "network" answer, no crash, no hang
    const t0 = Date.now(), r2 = await Net.rev(lap, { force: true });
    out.off = { status: r2.status, ms: Date.now() - t0 };
  } else {
    const r1 = await Net.rev(lap, { force: true });
    out.rev = { status: r1.status, hasRev: !!r1.rev }; out.after = lap.addr;
    const s = await Net.syncOnce(db, lap, { force: true });
    out.sync = { ok: s.ok };
  }
  out.saved = JSON.parse(fs.readFileSync(file, 'utf8')).sync.laptop || {};
  out.noJunk = !('_finding' in out.saved) && !('lastFind' in out.saved);
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
