// Navigation regression test (jsdom, no Android needed): node android/tests/nav_test.js  (needs `npm i jsdom` in a folder on NODE_PATH)
const { JSDOM, ResourceLoader } = require('jsdom'), fs = require('fs'), path = require('path');
const dir = path.resolve(__dirname, '../app/src/main/assets/www'), BASE = 'https://appassets.androidplatform.net/assets/www/';
class L extends ResourceLoader { fetch(u) { return Promise.resolve(u.startsWith(BASE) ? fs.readFileSync(path.join(dir, u.slice(BASE.length).split('?')[0])) : Buffer.from('')); } }
let fails = 0; const ok = (c, m) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) fails++; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const dom = new JSDOM(fs.readFileSync(path.join(dir, 'index.html'), 'utf8'), { url: BASE + 'index.html', runScripts: 'dangerously', resources: new L(), pretendToBeVisual: true,
    beforeParse(w) { w.TextEncoder = TextEncoder; w.TextDecoder = TextDecoder; w.crypto = require('crypto').webcrypto; } });
  const w = dom.window, d = w.document; await sleep(1500);
  const App = w.App, nav = d.getElementById('nav'), view = d.getElementById('view');
  ok(App.perf.boots === 1, 'boot ran once');
  const shell0 = App.perf.shellBuilds, navEl = nav.children[0];
  for (const i of [1, 2, 3, 4, 0, 1, 0]) { nav.children[i].click(); await sleep(3); }
  ok(App.perf.shellBuilds === shell0 && nav.children[0] === navEl, 'bottom bar is built once and reused');
  ok(App.perf.navs === 7, 'each tab click is one navigation');
  nav.children[1].click(); await sleep(3); App.boot(); ok(App.perf.boots === 1, 'a second boot() is ignored');
  // scroll memory: Stats -> scroll -> Tasks -> Stats keeps the position
  Object.defineProperty(view, 'scrollHeight', { value: 5000, configurable: true });
  view.scrollTop = 321; nav.children[3].click(); await sleep(3); ok(App.view === 'tasks', 'moved to Tasks');
  nav.children[1].click(); await sleep(3); ok(view.scrollTop === 321, 'Stats scroll position restored (' + view.scrollTop + ')');
  // Back walks the history instead of jumping to Today
  while (w.UI.closeTop()) {}   // the first-run welcome sheet is open on a fresh database: Back closes sheets first (by design)
  ok(w.__back() === true && App.view === 'tasks', 'Back returns to the previous tab (Tasks)');
  ok(w.__back() === true && App.view === 'stats', 'Back returns again (Stats)');
  while (w.__back()) {} ok(App.view === 'today' && w.__back() === false, 'Back ends on Today, then lets the app go to background');
  // a data change re-renders but plays no entrance animation
  if (!App.db.subjects.length) { w.Core.addSubject(App.db, 'Math', '#00D9F5', { tests: true }); App.changed(); }
  nav.children[4].click(); await sleep(3); nav.children[0].click(); await sleep(3);
  ok(view.classList.contains('v-in'), 'tab switch plays the entrance'); App.changed(); ok(!view.classList.contains('v-in'), 'data change does not replay it');
  // timer is wall-clock based: survives navigation and a simulated 90 s gap
  w.Core.startTimer(App.db, App.db.subjects[0].id); const st = App.db.active.started; App.changed();
  for (const i of [1, 2, 0]) { nav.children[i].click(); await sleep(3); }
  ok(App.db.active && App.db.active.started === st, 'timer start time unchanged after navigation');
  App.db.active.started -= 90; ok(Math.round(w.Core.elapsed(App.db)) >= 90, 'elapsed derives from start time (>= 90 s after a 90 s gap)');
  // return to app with unchanged data does not re-render; changed data does
  Object.defineProperty(d, 'visibilityState', { value: 'visible', configurable: true });
  App.saveNow(); const r = App.perf.renders; d.dispatchEvent(new w.Event('visibilitychange')); await sleep(3); ok(App.perf.renders === r, 'foreground with same data: no re-render');
  const db2 = JSON.parse(w.localStorage.getItem('voidlock.db')); db2.settings.goal_min = 77; w.localStorage.setItem('voidlock.db', JSON.stringify(db2));
  d.dispatchEvent(new w.Event('visibilitychange')); await sleep(3); ok(App.perf.renders === r + 1 && App.db.settings.goal_min === 77, 'foreground after external change: re-read and redraw');
  console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
})();
