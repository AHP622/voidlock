"""Wi-Fi sync with the phone, ENCRYPTED. A small HTTP server on the local network (standard library + `cryptography`; no Qt).

The phone is always the one that connects. One request does both directions: it sends what it has, the computer merges it
(see sync.py) and answers with the merged result, so both end with the same data. While the phone app is open (and about every
15 minutes in the background) it asks for the revision, which is how a change made on the computer reaches the phone.

  GET  /v1/ping           -> {"app": "voidlock", "version": 2, "proto": 2, "device": {id, name}}   (how the phone finds the computer)
  POST /v2/pair/start     {code, device: {id, name}, pub}  -> {pid, pub, device}                  (phone starts pairing)
  POST /v2/pair/status    {pid} -> {state: waiting | approved | denied}                           (phone waits for the person)
  POST /v2/call           {d, n, c}  encrypted envelope  -> {d, n, c}                              (hello / rev / sync)

Security (the traffic is plain HTTP inside the home network, so the protocol itself is encrypted and authenticated):
  * Pairing: the 6-digit code (10 minutes, one use, 5 wrong tries lock it for 5 minutes) only lets a phone ASK to pair. Both
    sides do an ECDH key exchange (P-256) and derive the shared key K (HKDF-SHA256). Each shows a 6-digit confirmation number
    derived from K; the person checks that both are the same and presses Allow on the computer. Somebody in the middle of the
    network ends up with a different K on each side, so the numbers differ and the person refuses.
  * Afterwards every call is an AES-256-GCM envelope under a key derived from K (the device id is authenticated as AAD, a request
    and a response use different AAD). Each request carries a counter that must grow, so an old recorded request is refused.
  * The key is stored in sync.json on both devices (like the data itself). Removing a phone deletes it.
  * Only private-network addresses are answered, and a merge that would delete a lot of data is refused here (it has to be
    imported as a file, where the computer asks first).

All data access goes through `backend.call(fn)`, which must run `fn` on the thread that owns the data (the Qt app passes
it to the main thread; tests call it directly).
"""
import base64
import hmac
import ipaddress
import json
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import sync

PROTO = 2
PORTS = tuple(range(47821, 47831))
CODE_TTL = 600
PENDING_TTL = 90
LOCK_AFTER = 5
LOCK_SECONDS = 300
MAX_BODY = sync.MAX_BYTES


class NeedsReview(Exception):
    """The merge would remove a lot of data here: not done automatically."""


class CryptoMissing(OSError):
    pass


# ------------------------------------------------------------------ crypto (the same constructions are in android .../native.js)
def _lib():
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    except ImportError as e:                                            # the exe ships it; a source install needs: pip install cryptography
        raise CryptoMissing("The 'cryptography' package is not installed (pip install cryptography).") from e
    return hashes, serialization, ec, AESGCM, HKDF


def b64e(b):
    return base64.b64encode(b).decode("ascii")


def b64d(s):
    return base64.b64decode(str(s).encode("ascii"), validate=True)


def new_keypair():
    """(private key object, public key as 65 raw bytes: 0x04 || X || Y)."""
    _h, ser, ec, _a, _k = _lib()
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key().public_bytes(ser.Encoding.X962, ser.PublicFormat.UncompressedPoint)


def _hkdf(key, salt, info, n):
    hashes, _s, _e, _a, HKDF = _lib()
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt, info=info).derive(key)


def derive_key(priv, peer_pub, phone_pub, server_pub):
    """K: ECDH shared secret -> HKDF, bound to both public keys (the same value on the phone and the computer)."""
    _h, _s, ec, _a, _k = _lib()
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), peer_pub)
    z = priv.exchange(ec.ECDH(), peer)
    return _hkdf(z, b"voidlock-pair-v2", phone_pub + server_pub, 32)


def sas_of(k):
    """The 6-digit number both devices show; the person checks that it is the same."""
    return "%06d" % (int.from_bytes(_hkdf(k, b"voidlock-sas-v2", b"sas", 4), "big") % 1000000)


def _aes_key(k):
    return _hkdf(k, b"voidlock-v2", b"enc", 32)


def seal(k, did, kind, obj):
    """kind is "req" or "res"; the device id and kind are authenticated (AAD) so a request cannot be passed off as a response."""
    _h, _s, _e, AESGCM, _k = _lib()
    nonce = secrets.token_bytes(12)
    ct = AESGCM(_aes_key(k)).encrypt(nonce, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), f"{did}|{kind}".encode("utf-8"))
    return {"d": did, "n": b64e(nonce), "c": b64e(ct)}


def open_env(k, did, kind, env):
    _h, _s, _e, AESGCM, _k = _lib()
    pt = AESGCM(_aes_key(k)).decrypt(b64d(env["n"]), b64d(env["c"]), f"{did}|{kind}".encode("utf-8"))
    return json.loads(pt.decode("utf-8"))


# ------------------------------------------------------------------ this computer's addresses
_VIRTUAL = re.compile(r"vethernet|hyper-v|vmware|virtualbox|vbox|\btap\b|tap-|\btun\b|wintun|wireguard|openvpn|nord|proton|express|surfshark|loopback|bluetooth|"
                      r"docker|wsl|npcap|isatap|teredo|pseudo|zerotier|tailscale|hamachi|vpn|tunnel|ppp|v2ray|clash|sing-box", re.I)
_WIFI = re.compile(r"wi-?fi|wlan|wireless|wl\d", re.I)
_ETH = re.compile(r"ethernet|\beth\d|en\d|lan", re.I)


def local_addresses():
    """Private IPv4 addresses of this computer that a phone on the same network can reach: Wi-Fi and Ethernet first, VPN / virtual
    adapters (which a phone cannot reach, and which hide the real address while a VPN is on) last or not at all."""
    cand = []                                                           # (rank, ip)
    try:
        import psutil
        stats = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            st = stats.get(name)
            if st is not None and not st.isup:
                continue
            virtual = bool(_VIRTUAL.search(name))
            rank = 3 if virtual else 0 if _WIFI.search(name) else 1 if _ETH.search(name) else 2
            for a in addrs:
                if a.family == socket.AF_INET:
                    cand.append((rank, a.address))
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))                                # no packet is sent; this only picks the outgoing interface
        cand.append((2, s.getsockname()[0]))
        s.close()
    except OSError:
        pass
    out, seen = [], set()
    for rank, ip in sorted(cand, key=lambda c: c[0]):
        try:
            p = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if p.is_private and not p.is_loopback and not p.is_link_local and ip not in seen and (rank < 3 or not out):
            seen.add(ip)
            out.append(ip)
    return out


class LanServer:
    def __init__(self, backend, ports=PORTS):
        self.backend, self.ports = backend, ports
        self.httpd, self.thread, self.port = None, None, None
        self._code, self._code_until = None, 0
        self._fails, self._locked_until = 0, 0
        self._pending = None
        self._lock = threading.Lock()

    # ---- lifecycle
    @property
    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd:
            return self.port
        _lib()                                                          # no crypto library: do not listen at all
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
        self._code, self._pending = None, None

    # ---- pairing
    def new_code(self):
        """A fresh 6-digit code (shown on the computer, typed on the phone). It only lets a phone ask to pair."""
        with self._lock:
            self._code = f"{secrets.randbelow(10 ** 6):06d}"
            self._code_until = time.time() + CODE_TTL
            self._pending = None
            return self._code

    def cancel_pairing(self):
        with self._lock:
            self._code, self._pending = None, None

    def code_valid_for(self):
        return max(0, int(self._code_until - time.time())) if self._code else 0

    def _pair_start(self, code, device, phone_pub_b64):
        """-> (reply dict, error). A valid code creates a pending request that the person must allow on the computer."""
        try:
            phone_pub = b64d(phone_pub_b64)
            if len(phone_pub) != 65 or phone_pub[0] != 4:
                raise ValueError
        except Exception:
            return None, "bad"
        did = str(device.get("id") or "")[:64]
        name = str(device.get("name") or "Phone")[:60]
        if not did:
            return None, "bad"
        with self._lock:
            now = time.time()
            if now < self._locked_until:
                return None, "locked"
            if not self._code or now > self._code_until:
                return None, "no_code"
            if not hmac.compare_digest(str(code).strip().replace(" ", ""), self._code):
                self._fails += 1
                if self._fails >= LOCK_AFTER:
                    self._locked_until, self._fails, self._code = now + LOCK_SECONDS, 0, None
                return None, "wrong"
            self._code, self._fails = None, 0                          # a code starts one pairing only
            priv, server_pub = new_keypair()
            k = derive_key(priv, phone_pub, phone_pub, server_pub)
            pid = secrets.token_urlsafe(12)
            sas = sas_of(k)
            self._pending = {"pid": pid, "device": {"id": did, "name": name}, "key": k, "sas": sas, "state": "waiting", "t": now}
        self.backend.call(lambda: self.backend.pair_request({"name": name, "sas": sas, "pid": pid}))
        return {"pid": pid, "pub": b64e(server_pub), "device": self.backend.call(self.backend.device)}, None

    def pending(self):
        """What the person has to decide: {pid, name, sas} or None."""
        with self._lock:
            p = self._pending
            if p and p["state"] == "waiting" and time.time() - p["t"] <= PENDING_TTL:
                return {"pid": p["pid"], "name": p["device"]["name"], "sas": p["sas"]}
        return None

    def approve(self, pid):
        with self._lock:
            p = self._pending
            if not p or p["pid"] != pid or p["state"] != "waiting" or time.time() - p["t"] > PENDING_TTL:
                return False
            p["state"] = "approved"
            dev, k = p["device"], p["key"]

        def store():
            s = sync.load_state(self.backend.home)
            s["paired"][dev["id"]] = {"name": dev["name"], "key": b64e(k), "seq": 0, "paired_at": int(time.time()), "last_seen": int(time.time())}
            sync.save_state(self.backend.home, s)
            self.backend.paired_changed()
        self.backend.call(store)
        return True

    def deny(self, pid):
        with self._lock:
            if self._pending and self._pending["pid"] == pid and self._pending["state"] == "waiting":
                self._pending["state"] = "denied"
                return True
        return False

    def _pair_status(self, pid):
        with self._lock:
            p = self._pending
            if not p or p["pid"] != pid:
                return "denied"
            if p["state"] == "waiting" and time.time() - p["t"] > PENDING_TTL:
                p["state"] = "denied"
            return p["state"]

    # ---- encrypted calls
    def _lookup(self, did):
        """(key bytes, last seq) of a paired phone, or None."""
        def find():
            p = sync.load_state(self.backend.home)["paired"].get(did)
            return (b64d(p["key"]), int(p.get("seq", 0))) if p and p.get("key") else None
        try:
            return self.backend.call(find)
        except Exception:
            return None

    def _bump_seq(self, did, seq):
        def do():
            s = sync.load_state(self.backend.home)
            p = s["paired"].get(did)
            if p is None or seq <= int(p.get("seq", 0)):
                return False
            p["seq"], p["last_seen"] = seq, int(time.time())
            sync.save_state(self.backend.home, s)
            return True
        return self.backend.call(do)

    def handle_call(self, env):
        """-> (http status, reply dict). Anything that is not a valid, fresh envelope from a paired phone is just a 401."""
        try:
            did = str(env["d"])
            found = self._lookup(did)
            if not found:
                return 401, {"error": "unauthorized"}
            k, last = found
            req = open_env(k, did, "req", env)
            seq = int(req["seq"])
            if seq <= last or not self._bump_seq(did, seq):
                return 401, {"error": "unauthorized"}
        except Exception:
            return 401, {"error": "unauthorized"}
        op = req.get("op")
        b = self.backend
        try:
            if op == "hello":
                out = {"ok": True, "device": b.call(b.device), "rev": b.call(b.rev)}
            elif op == "rev":
                out = {"ok": True, "rev": b.call(b.rev)}
            elif op == "sync":
                pkg = json.dumps(req.get("package"), ensure_ascii=False).encode("utf-8")
                out = {"ok": True, **b.call(lambda: b.sync(pkg, {"id": did}))}
            else:
                out = {"ok": False, "error": "bad_op"}
        except sync.SyncError as e:
            out = {"ok": False, "error": "invalid", "message": str(e)}
        except NeedsReview:
            out = {"ok": False, "error": "needs_review"}
        except Exception as e:                                          # never leak a stack trace over the network
            out = {"ok": False, "error": "failed", "message": type(e).__name__}
        return 200, seal(k, did, "res", {"seq": seq, **out})

    def paired(self):
        s = sync.load_state(self.backend.home)
        return [{"id": k, "name": v.get("name", "?"), "paired_at": v.get("paired_at"), "last_seen": v.get("last_seen")}
                for k, v in s["paired"].items()]

    def unpair(self, did):
        def do():
            s = sync.load_state(self.backend.home)
            s["paired"].pop(did, None)
            sync.save_state(self.backend.home, s)
            self.backend.paired_changed()
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
            return self._send(200, {"app": "voidlock", "version": sync.VERSION, "proto": PROTO, "device": s.backend.call(s.backend.device)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._client_ok():
            return self._send(403, {"error": "forbidden"})
        path = self.path.split("?")[0]
        s = self.srv
        body = self._body()
        if body is None:
            return self._send(413, {"error": "too big"})
        try:
            req = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "bad request"})
        if not isinstance(req, dict):
            return self._send(400, {"error": "bad request"})
        if path == "/v2/call":
            code, out = s.handle_call(req)
            return self._send(code, out)
        if path == "/v2/pair/start":
            dev = req.get("device")
            if not isinstance(dev, dict) or req.get("code") is None or not req.get("pub"):
                return self._send(400, {"error": "bad request"})
            out, why = s._pair_start(req["code"], dev, req["pub"])
            if out:
                return self._send(200, out)
            return self._send({"locked": 429, "no_code": 409, "wrong": 403}.get(why, 400), {"error": why})
        if path == "/v2/pair/status":
            return self._send(200, {"state": s._pair_status(str(req.get("pid", "")))})
        self._send(404, {"error": "not found"})


class StoreBackend:
    """What the server needs from the app. `call` runs a function on the thread that owns the data (the Qt main thread)."""

    def __init__(self, store, study=None, call=None, on_changed=None, on_paired=None, on_pair_request=None):
        self.store, self.sl = store, study
        self.call = call or (lambda fn: fn())
        self.on_changed = on_changed or (lambda plan: None)
        self.on_paired = on_paired or (lambda: None)
        self.on_pair_request = on_pair_request or (lambda info: None)

    def pair_request(self, info):
        self.on_pair_request(info)

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
