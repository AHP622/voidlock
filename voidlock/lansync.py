"""Wi-Fi sync with the phone. A small HTTP server on the local network (no Qt, standard library only).

The phone is always the one that connects. One request does both directions: it sends what it has, the computer merges it
(see sync.py) and answers with the merged result, so both end with the same data. While the phone app is open it asks
`/v1/rev` every few seconds, which is how a change made on the computer reaches the phone without anyone pressing anything.

  GET  /v1/ping   -> {"app": "voidlock", "version": 2, "device": {id, name}}          (no login: how the phone finds the computer)
  POST /v1/pair   {code, device: {id, name}} -> {token, device}                         (the 6-digit code shown on the computer)
  GET  /v1/rev    -> {rev}                                                              (needs the token; changes when data changes)
  POST /v1/sync   <sync package>  -> {package, rev, stats, changed}                     (needs the token)

Safety: only private-network addresses are answered, the pairing code lives 10 minutes and 5 wrong tries lock pairing for 5
minutes, the token is random (only its hash is stored here), and a merge that would delete a lot of data is refused here (it
has to be imported as a file, where the computer asks first). The traffic is plain HTTP inside the home network.

All data access goes through `backend.call(fn)`, which must run `fn` on the thread that owns the data (the Qt app passes
it to the main thread; tests call it directly).
"""
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import sync

PORTS = tuple(range(47821, 47831))
CODE_TTL = 600
LOCK_AFTER = 5
LOCK_SECONDS = 300
MAX_BODY = sync.MAX_BYTES


class NeedsReview(Exception):
    """The merge would remove a lot of data here: not done automatically."""


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def local_addresses():
    """Private IPv4 addresses of this computer (what the phone can reach), the one used to reach the internet first."""
    found = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))               # no packet is sent; this only picks the outgoing interface
        found.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        import psutil
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == socket.AF_INET:
                    found.append(a.address)
    except Exception:
        pass
    out = []
    for ip in found:
        try:
            p = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if p.is_private and not p.is_loopback and not p.is_link_local and ip not in out:
            out.append(ip)
    return out


class LanServer:
    def __init__(self, backend, ports=PORTS):
        self.backend, self.ports = backend, ports
        self.httpd, self.thread, self.port = None, None, None
        self._code, self._code_until = None, 0
        self._fails, self._locked_until = 0, 0
        self._lock = threading.Lock()

    # ---- lifecycle
    @property
    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd:
            return self.port
        for port in self.ports:
            try:
                server = self
                handler = type("Handler", (_Handler,), {"srv": server})
                httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
                httpd.daemon_threads = True
                self.httpd, self.port = httpd, port
                break
            except OSError:
                continue
        if not self.httpd:
            raise OSError("No free port for the sync server.")
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="lansync", daemon=True)
        self.thread.start()
        return self.port

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
        self.httpd, self.thread, self.port = None, None, None
        self._code = None

    # ---- pairing
    def new_code(self):
        """A fresh 6-digit code (shown on the computer, typed on the phone)."""
        with self._lock:
            self._code = f"{secrets.randbelow(10 ** 6):06d}"
            self._code_until = time.time() + CODE_TTL
            return self._code

    def code_valid_for(self):
        return max(0, int(self._code_until - time.time())) if self._code else 0

    def _pair(self, code, device):
        with self._lock:
            now = time.time()
            if now < self._locked_until:
                return None, "locked"
            if not self._code or now > self._code_until:
                return None, "no_code"
            ok = hmac.compare_digest(str(code).strip().replace(" ", ""), self._code)
            if not ok:
                self._fails += 1
                if self._fails >= LOCK_AFTER:
                    self._locked_until, self._fails, self._code = now + LOCK_SECONDS, 0, None
                return None, "wrong"
            self._code, self._fails = None, 0                      # a code works once
        token = secrets.token_hex(24)
        did = str(device.get("id") or "")[:64]
        name = str(device.get("name") or "Phone")[:60]
        if not did:
            return None, "bad"

        def store():
            s = sync.load_state(self.backend.home)
            s["paired"][did] = {"name": name, "th": _hash(token), "paired_at": int(time.time()), "last_seen": int(time.time())}
            sync.save_state(self.backend.home, s)
            self.backend.paired_changed()
        self.backend.call(store)
        return token, "ok"

    def _auth(self, header):
        if not header or not header.lower().startswith("bearer "):
            return None
        th = _hash(header[7:].strip())

        def find():
            s = sync.load_state(self.backend.home)
            for did, p in s["paired"].items():
                if hmac.compare_digest(p.get("th", ""), th):
                    p["last_seen"] = int(time.time())
                    sync.save_state(self.backend.home, s)
                    return {"id": did, "name": p.get("name", "?")}
            return None
        return self.backend.call(find)

    def paired(self):
        s = sync.load_state(self.backend.home)
        return [{"id": k, "name": v.get("name", "?"), "paired_at": v.get("paired_at"), "last_seen": v.get("last_seen")}
                for k, v in s["paired"].items()]

    def unpair(self, did):
        def do():
            s = sync.load_state(self.backend.home)
            s["paired"].pop(did, None)
            sync.save_state(self.backend.home, s)
        self.backend.call(do)


class _Handler(BaseHTTPRequestHandler):
    srv = None
    protocol_version = "HTTP/1.1"
    timeout = 30

    def log_message(self, *a):
        pass

    # ---- plumbing
    def _client_ok(self):
        try:
            p = ipaddress.ip_address(self.client_address[0])
            return p.is_private or p.is_loopback
        except ValueError:
            return False

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            return None
        return self.rfile.read(n) if n else b""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_GET(self):
        if not self._client_ok():
            return self._send(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        s = self.srv
        if path == "/v1/ping":
            return self._send(200, {"app": "voidlock", "version": sync.VERSION, "device": s.backend.call(s.backend.device)})
        if path == "/v1/rev":
            if not s._auth(self.headers.get("Authorization")):
                return self._send(401, {"error": "unauthorized"})
            return self._send(200, {"rev": s.backend.call(s.backend.rev)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._client_ok():
            return self._send(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        s = self.srv
        body = self._body()
        if body is None:
            return self._send(413, {"error": "too big"})
        if path == "/v1/pair":
            try:
                req = json.loads(body.decode("utf-8"))
                dev = req.get("device") if isinstance(req, dict) else None
                code = req.get("code")
            except (ValueError, UnicodeDecodeError, AttributeError):
                return self._send(400, {"error": "bad request"})
            if not isinstance(dev, dict) or code is None:
                return self._send(400, {"error": "bad request"})
            token, why = s._pair(code, dev)
            if token:
                return self._send(200, {"token": token, "device": s.backend.call(s.backend.device)})
            return self._send({"locked": 429, "no_code": 409, "wrong": 403}.get(why, 400), {"error": why})
        if path == "/v1/sync":
            peer = s._auth(self.headers.get("Authorization"))
            if not peer:
                return self._send(401, {"error": "unauthorized"})
            try:
                out = s.backend.call(lambda: s.backend.sync(body, peer))
            except sync.SyncError as e:
                return self._send(422, {"error": "invalid", "message": str(e)})
            except NeedsReview:
                return self._send(409, {"error": "needs_review"})
            return self._send(200, out)
        self._send(404, {"error": "not found"})


class StoreBackend:
    """What the server needs from the app. `call` runs a function on the thread that owns the data (the Qt main thread)."""

    def __init__(self, store, study=None, call=None, on_changed=None, on_paired=None):
        self.store, self.sl = store, study
        self.call = call or (lambda fn: fn())
        self.on_changed = on_changed or (lambda plan: None)
        self.on_paired = on_paired or (lambda: None)

    @property
    def home(self):
        return self.store.home

    def paired_changed(self):
        self.on_paired()

    def device(self):
        s = sync.load_state(self.home)
        return {"id": s["device_id"], "name": s["device_name"]}

    def rev(self):
        return sync.content_rev(self.store)

    def sync(self, raw, peer):
        plan = sync.prepare(self.store, raw)
        if plan.warn:
            raise NeedsReview()
        changed = plan.changes() > 0
        if changed:
            sync.commit(self.store, plan, sl=self.sl, backup="auto")
            self.on_changed(plan)
        else:
            sync.touch_peer(self.home, plan.peer)
        return {"package": sync.make_package(self.store), "rev": sync.content_rev(self.store), "stats": plan.stats, "changed": changed}
