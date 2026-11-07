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
      return j && j.app === 'voidlock' && j.device ? { addr: addr, device: j.device, version: j.version } : null;
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
  function pair(addr, code, device) {
    return http('POST', base(addr) + '/v1/pair', { body: JSON.stringify({ code: String(code).replace(/\s+/g, ''), device: device }),
      headers: { 'Content-Type': 'application/json' }, timeout: 8000 }).then(function (r) {
      var j = json(r);
      if (r.status === 200 && j && j.token) return { ok: true, token: j.token, device: j.device };
      var err = j && j.error ? j.error : (r.status === 0 ? 'network' : 'bad');
      return { ok: false, error: err };
    });
  }
  function authed(method, path, lap, body, timeout) {
    var h = { Authorization: 'Bearer ' + lap.token }; if (body) h['Content-Type'] = 'application/json';
    return http(method, base(lap.addr) + path, { headers: h, body: body, timeout: timeout || 20000 });
  }
  function rev(lap) { return authed('GET', '/v1/rev', lap, null, 5000).then(function (r) { var j = json(r); return { status: r.status, rev: j && j.rev }; }); }
  function syncOnce(db, lap) {
    var pkg = Core.makePackage(db);
    return authed('POST', '/v1/sync', lap, JSON.stringify(pkg), 60000).then(function (r) {
      var j = json(r);
      if (r.status === 200 && j && j.package) {
        var plan = Core.prepare(db, j.package);
        var changes = plan.changes();
        Core.commit(db, plan);
        return { ok: true, changes: changes, rev: j.rev, plan: plan };
      }
      return { ok: false, status: r.status, error: j && j.error ? j.error : (r.status === 0 ? 'network' : 'bad'), message: j && j.message };
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
  var Net = { PORTS: PORTS, ping: ping, scan: scan, pair: pair, rev: rev, syncOnce: syncOnce, checkUpdate: checkUpdate, cmpVer: cmpVer };
  root.Native = Native; root.Net = Net;
  if (typeof module !== 'undefined' && module.exports) module.exports = { Native: Native, Net: Net };
})(typeof window !== 'undefined' ? window : globalThis);
