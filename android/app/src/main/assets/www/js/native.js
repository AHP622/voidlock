/* Bridge to the Android shell (when present) with browser fallbacks, the Wi-Fi sync client and the GitHub updater.
 * The shell exposes window.Android (see MainActivity.kt / Bridge.kt). All network calls go through Native.http so that the app
 * does not depend on browser CORS / mixed-content rules (the computer speaks plain HTTP on the local network). */
(function (root) {
  'use strict';
  var A = root.Android || null, pending = {}, seq = 0;
  var listeners = { apk: null, openFile: null };

  function b64ToText(b64) {
    if (!b64) return '';
    var bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  }
  // called by the shell
  root.__native = {
    onHttp: function (id, status, b64) { var p = pending[id]; if (p) { delete pending[id]; p({ status: status, text: b64ToText(b64) }); } },
    onApk: function (stage, a, b) { if (listeners.apk) listeners.apk(stage, a, b); },
    onOpenFile: function (name, text) { if (listeners.openFile) listeners.openFile(name, text); }
  };

  function http(method, url, opts) {
    opts = opts || {};
    var timeout = opts.timeout || 15000;
    if (A && A.http) {
      return new Promise(function (resolve) {
        var id = 'h' + (++seq);
        pending[id] = resolve;
        setTimeout(function () { if (pending[id]) { delete pending[id]; resolve({ status: 0, text: 'timeout' }); } }, timeout + 3000);
        try { A.http(id, method, url, JSON.stringify(opts.headers || {}), opts.body || '', timeout); }
        catch (e) { delete pending[id]; resolve({ status: 0, text: String(e) }); }
      });
    }
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null, to = setTimeout(function () { if (ctl) ctl.abort(); }, timeout);
    return fetch(url, { method: method, headers: opts.headers || {}, body: opts.body || undefined, signal: ctl ? ctl.signal : undefined })
      .then(function (r) { return r.text().then(function (t) { clearTimeout(to); return { status: r.status, text: t }; }); })
      .catch(function (e) { clearTimeout(to); return { status: 0, text: String(e) }; });
  }
  function json(res) { try { return JSON.parse(res.text); } catch (e) { return null; } }

  var Native = {
    available: !!A,
    http: http, json: json,
    deviceName: function () { try { if (A && A.deviceName) return String(A.deviceName()); } catch (e) {} return 'Phone'; },
    appVersion: function () { try { if (A && A.appVersion) return String(A.appVersion()); } catch (e) {} return (root.VOIDLOCK_CONFIG || {}).version || '0'; },
    localIps: function () { try { if (A && A.localIps) return JSON.parse(A.localIps()); } catch (e) {} return []; },
    keepAwake: function (on) { try { if (A && A.keepAwake) A.keepAwake(!!on); } catch (e) {} },
    setBackgroundSync: function (on) { try { if (A && A.setBackgroundSync) A.setBackgroundSync(!!on); } catch (e) {} },
    bgDone: function (ok) { try { if (A && A.bgDone) A.bgDone(!!ok); } catch (e) {} },
    printHtml: function (title, html) {
      if (A && A.printHtml) { try { A.printHtml(title, html); return true; } catch (e) { return false; } }
      var w = root.open('', '_blank'); if (!w) return false; w.document.write(html); w.document.close(); setTimeout(function () { try { w.print(); } catch (e) {} }, 400); return true;
    },
    shareFile: function (name, mime, text) {
      if (A && A.shareFile) { try { A.shareFile(name, mime, text); return true; } catch (e) { return false; } }
      var url = URL.createObjectURL(new Blob([text], { type: mime })), a = document.createElement('a');
      a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(url); }, 4000); return true;
    },
    saveFile: function (name, mime, text) { if (A && A.saveFile) { try { return String(A.saveFile(name, mime, text)) === 'ok'; } catch (e) { return false; } } return Native.shareFile(name, mime, text); },
    pickFile: function () {
      return new Promise(function (resolve) {
        var inp = document.createElement('input'); inp.type = 'file'; inp.accept = '.voidsync,application/json,text/plain,*/*';
        inp.onchange = function () { var f = inp.files && inp.files[0]; if (!f) return resolve(null); var r = new FileReader(); r.onload = function () { resolve({ name: f.name, text: String(r.result) }); }; r.onerror = function () { resolve(null); }; r.readAsText(f); };
        inp.click();
      });
    },
    installApk: function (url, shaUrl, cb) { listeners.apk = cb; if (A && A.installApk) A.installApk(url, shaUrl); else cb('error', 'Not running inside the Android app', 0); },
    openInstallSettings: function () { try { if (A && A.openInstallSettings) A.openInstallSettings(); } catch (e) {} },
    onOpenFile: function (fn) { listeners.openFile = fn; }
  };

  // ------------------------------------------------------------ Wi-Fi sync client (talks to voidlock/lansync.py)
  var PORTS = [47821, 47822, 47823, 47824, 47825, 47826, 47827, 47828, 47829, 47830];
  function base(addr) { addr = String(addr).trim().replace(/^https?:\/\//, '').replace(/\/+$/, ''); return 'http://' + addr; }
  function ping(addr, timeout) {
    return http('GET', base(addr) + '/v1/ping', { timeout: timeout || 1500 }).then(function (r) {
      var j = r.status === 200 ? json(r) : null;
      return j && j.app === 'voidlock' && j.device ? { addr: addr, device: j.device, version: j.version, proto: j.proto || 1 } : null;
    });
  }
  function scan(onFound, onProgress) {
    var ips = Native.localIps(), hosts = [], seen = {}, found = [];
    ips.forEach(function (ip) {
      var p = ip.split('.'); if (p.length !== 4) return;
      var pre = p.slice(0, 3).join('.');
      for (var i = 1; i < 255; i++) { var h = pre + '.' + i; if (!seen[h] && h !== ip) { seen[h] = 1; hosts.push(h); } }
    });
    var jobs = []; hosts.forEach(function (h) { jobs.push(h + ':' + PORTS[0]); });
    var idx = 0, done = 0, total = jobs.length;
    return new Promise(function (resolve) {
      if (!total) return resolve(found);
      function next() {
        if (idx >= jobs.length) return;
        var addr = jobs[idx++];
        ping(addr, 900).then(function (res) {
          if (res) { found.push(res); if (onFound) onFound(res); }
          done++; if (onProgress) onProgress(done, total);
          if (done >= total) resolve(found); else next();
        });
      }
      for (var k = 0; k < 40; k++) next();
    });
  }
  // ---- encryption (same constructions as voidlock/lansync.py: ECDH P-256 -> HKDF-SHA256 -> AES-256-GCM)
  var te = new TextEncoder();
  function subtle() { var c = root.crypto && root.crypto.subtle; if (!c) throw new Error('Web Crypto is not available'); return c; }
  function b64e(u8) { var s = ''; for (var i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); }
  function b64d(str) { var bin = atob(str), u = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  function concat(a, b) { var o = new Uint8Array(a.length + b.length); o.set(a, 0); o.set(b, a.length); return o; }
  function hkdf(keyBytes, salt, info, n) {
    return subtle().importKey('raw', keyBytes, 'HKDF', false, ['deriveBits']).then(function (k) {
      return subtle().deriveBits({ name: 'HKDF', hash: 'SHA-256', salt: te.encode(salt), info: typeof info === 'string' ? te.encode(info) : info }, k, n * 8);
    }).then(function (b) { return new Uint8Array(b); });
  }
  function newKeyPair() {
    return subtle().generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']).then(function (kp) {
      return subtle().exportKey('raw', kp.publicKey).then(function (pub) { return { priv: kp.privateKey, pub: new Uint8Array(pub) }; });
    });
  }
  function deriveKey(priv, peerPub, phonePub, serverPub) {
    return subtle().importKey('raw', peerPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []).then(function (peer) {
      return subtle().deriveBits({ name: 'ECDH', public: peer }, priv, 256);
    }).then(function (z) { return hkdf(new Uint8Array(z), 'voidlock-pair-v2', concat(phonePub, serverPub), 32); });
  }
  function sasOf(K) { return hkdf(K, 'voidlock-sas-v2', 'sas', 4).then(function (b) { var n = ((b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]) >>> 0; return ('000000' + (n % 1000000)).slice(-6); }); }
  function aesKey(K) { return hkdf(K, 'voidlock-v2', 'enc', 32).then(function (raw) { return subtle().importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']); }); }
  function seal(K, did, kind, obj) {
    var iv = root.crypto.getRandomValues(new Uint8Array(12));
    return aesKey(K).then(function (key) { return subtle().encrypt({ name: 'AES-GCM', iv: iv, additionalData: te.encode(did + '|' + kind) }, key, te.encode(JSON.stringify(obj))); })
      .then(function (ct) { return { d: did, n: b64e(iv), c: b64e(new Uint8Array(ct)) }; });
  }
  function openEnv(K, did, kind, env) {
    return aesKey(K).then(function (key) { return subtle().decrypt({ name: 'AES-GCM', iv: b64d(env.n), additionalData: te.encode(did + '|' + kind) }, key, b64d(env.c)); })
      .then(function (pt) { return JSON.parse(new TextDecoder('utf-8').decode(pt)); });
  }

  // ---- pairing: the code only lets the phone ASK; both devices then show the same 6-digit number and the person allows it on the computer
  function pairStart(addr, code, device) {
    return newKeyPair().then(function (kp) {
      return http('POST', base(addr) + '/v2/pair/start', { body: JSON.stringify({ code: String(code).replace(/\s+/g, ''), device: device, pub: b64e(kp.pub) }),
        headers: { 'Content-Type': 'application/json' }, timeout: 8000 }).then(function (r) {
        var j = json(r);
        if (r.status !== 200 || !j || !j.pid) return { ok: false, error: j && j.error ? j.error : (r.status === 0 ? 'network' : 'bad') };
        var spub = b64d(j.pub);
        return deriveKey(kp.priv, spub, kp.pub, spub).then(function (K) {
          return sasOf(K).then(function (sas) { return { ok: true, pid: j.pid, K: K, sas: sas, device: j.device, addr: addr, did: device.id }; });
        });
      });
    });
  }
  /* waits until the person allows (or refuses) on the computer; then proves with a first encrypted call that both have the key */
  function pairFinish(st, shouldStop) {
    var deadline = Date.now() + 100000;
    function poll() {
      if (shouldStop && shouldStop()) return Promise.resolve({ ok: false, error: 'cancelled' });
      if (Date.now() > deadline) return Promise.resolve({ ok: false, error: 'expired' });
      return http('POST', base(st.addr) + '/v2/pair/status', { body: JSON.stringify({ pid: st.pid }), headers: { 'Content-Type': 'application/json' }, timeout: 6000 }).then(function (r) {
        var j = json(r), state = j && j.state;
        if (state === 'approved') {
          var lap = { addr: st.addr, key: b64e(st.K), did: st.did, id: st.device && st.device.id, name: (st.device && st.device.name) || '?', seq: 0, lastRev: null };
          return secureCall(lap, 'hello', null, 8000).then(function (c) { return c.status === 200 ? { ok: true, lap: lap } : { ok: false, error: 'key' }; });
        }
        if (state === 'denied') return { ok: false, error: 'denied' };
        return new Promise(function (res) { setTimeout(res, 1500); }).then(poll);
      });
    }
    return poll();
  }

  // ---- encrypted calls: {d, n, c} envelopes; the counter must grow (an old recorded request is refused by the computer)
  function secureCall(lap, op, extra, timeout) {
    lap.seq = Math.max((lap.seq || 0) + 1, Date.now());
    if (Net.persist) Net.persist();
    var seq = lap.seq, K = b64d(lap.key), body = { seq: seq, op: op };
    if (extra) Object.keys(extra).forEach(function (k) { body[k] = extra[k]; });
    return seal(K, lap.did, 'req', body).then(function (env) {
      return http('POST', base(lap.addr) + '/v2/call', { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(env), timeout: timeout || 20000 });
    }).then(function (r) {
      if (r.status === 401) return { status: 401 };
      if (r.status !== 200) return { status: r.status };
      var env = json(r); if (!env) return { status: 0 };
      return openEnv(K, lap.did, 'res', env).then(function (d) { return d.seq === seq ? { status: 200, data: d } : { status: 0, error: 'replay' }; })
        .catch(function () { return { status: 0, error: 'decrypt' }; });
    }).catch(function (e) { return { status: 0, error: String(e && e.message || e) }; });
  }
  function rev(lap) { return secureCall(lap, 'rev', null, 6000).then(function (c) { return { status: c.status, rev: c.data && c.data.rev }; }); }
  function syncOnce(db, lap) {
    var pkg = Core.makePackage(db);
    return secureCall(lap, 'sync', { package: pkg }, 60000).then(function (c) {
      var d = c.data;
      if (c.status === 200 && d && d.ok && d.package) {
        var plan = Core.prepare(db, d.package), changes = plan.changes();
        Core.commit(db, plan);
        return { ok: true, changes: changes, rev: d.rev, plan: plan };
      }
      if (c.status === 200 && d) return { ok: false, status: d.error === 'invalid' ? 422 : 409, error: d.error, message: d.message };
      return { ok: false, status: c.status, error: c.status === 0 ? 'network' : 'bad' };
    });
  }

  // ------------------------------------------------------------ updates from GitHub Releases
  function cmpVer(a, b) {
    var x = String(a).replace(/^v/, '').split('.').map(Number), y = String(b).replace(/^v/, '').split('.').map(Number);
    for (var i = 0; i < Math.max(x.length, y.length); i++) { var d = (x[i] || 0) - (y[i] || 0); if (d) return d > 0 ? 1 : -1; }
    return 0;
  }
  function checkUpdate() {
    var cfg = root.VOIDLOCK_CONFIG || {};
    return http('GET', 'https://api.github.com/repos/' + cfg.repo + '/releases/latest', { headers: { Accept: 'application/vnd.github+json' }, timeout: 15000 }).then(function (r) {
      var j = r.status === 200 ? json(r) : null;
      if (!j || !j.tag_name) return { ok: false, error: r.status === 403 ? 'GitHub rate limit' : (r.status === 0 ? 'network' : 'HTTP ' + r.status) };
      var apk = (j.assets || []).find(function (a) { return a.name === 'VoidLock.apk'; });
      var sha = (j.assets || []).find(function (a) { return a.name === 'VoidLock.apk.sha256'; });
      var cur = Native.appVersion();
      return { ok: true, tag: j.tag_name, version: j.tag_name.replace(/^v/, ''), newer: cmpVer(j.tag_name, cur) > 0, hasApk: !!(apk && sha), url: apk && apk.browser_download_url, shaUrl: sha && sha.browser_download_url };
    });
  }
  var Net = { PORTS: PORTS, ping: ping, scan: scan, pairStart: pairStart, pairFinish: pairFinish, secureCall: secureCall, rev: rev, syncOnce: syncOnce, checkUpdate: checkUpdate, cmpVer: cmpVer,
              persist: null, crypto: { newKeyPair: newKeyPair, deriveKey: deriveKey, sasOf: sasOf, seal: seal, openEnv: openEnv, b64e: b64e, b64d: b64d } };
  root.Native = Native; root.Net = Net;
  if (typeof module !== 'undefined' && module.exports) module.exports = { Native: Native, Net: Net };
})(typeof window !== 'undefined' ? window : globalThis);
