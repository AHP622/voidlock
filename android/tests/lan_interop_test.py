"""The phone's JavaScript client (WebCrypto) against the computer's real Python server (needs Node): pairing with the confirmation
number, encrypted calls and a two-way sync. Run:  python android/tests/lan_interop_test.py"""
import json, os, shutil, subprocess, sys, tempfile, time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from voidlock import lansync, store as S, study, sync  # noqa: E402

FAILS = []


def ok(c, n):
    print(("PASS " if c else "FAIL ") + n)
    if not c: FAILS.append(n)


def main():
    if not shutil.which("node"):
        print("node not found: skipped"); return 0
    lap = S.Store(Path(tempfile.mkdtemp())); sl = study.StudyLog(lap)
    today = date.today(); sj = sl.subjects()[0]
    for i in range(30): sl.add_manual(today - timedelta(days=i), sj["id"], 20 + i)
    sl.add_todo(today, "from the computer")
    srv = lansync.LanServer(lansync.StoreBackend(lap, sl))
    port = srv.start(); code = srv.new_code()
    f = os.path.join(tempfile.mkdtemp(), "phone.json")
    subprocess.run(["node", str(Path(__file__).with_name("jsdev.js")), "init", f], check=True, capture_output=True)
    db = json.load(open(f, encoding="utf-8"))
    db["todos"].append({"id": "phonetodo1", "date": today.isoformat(), "text": "from the phone", "done": False})
    json.dump(db, open(f, "w", encoding="utf-8"))
    try:
        p = subprocess.Popen(["node", str(Path(__file__).with_name("lan_client.js")), str(port), code, f], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        line = p.stdout.readline().strip()                                         # "SAS 123456"
        ok(line.startswith("SAS "), "the phone shows a confirmation number and waits")
        sas = line.split()[1]
        pend = None
        for _ in range(100):
            pend = srv.pending()
            if pend: break
            time.sleep(0.1)
        ok(pend and pend["sas"] == sas, "the computer shows the SAME number (JavaScript and Python derived the same key)")
        srv.approve(pend["pid"])
        rest = p.stdout.read(); err = p.stderr.read(); p.wait(timeout=120)
        if p.returncode != 0: print(err); ok(False, "the JS client ran"); return 1
        o = json.loads(rest.strip().splitlines()[-1])
        ok(o["ping"] and o["ping"]["proto"] == 2, "the phone finds the computer with /v1/ping and sees protocol 2")
        ok(o["wrong"]["ok"] is False and o["wrong"]["error"] == "wrong", "a wrong code is refused with a clear reason")
        ok(o["pair"]["ok"], "after the person allows it, pairing finishes with a verified encrypted call")
        ok(o["sync1"]["ok"] and o["sync1"]["changes"] > 0, "the first sync brings the computer's data to the phone")
        ok(o["entries"] == 30 and "from the computer" in o["todos"] and "from the phone" in o["todos"], "the phone has its own data and the computer's")
        ok(o["sync2"]["ok"] and o["sync2"]["changes"] == 0, "a second sync changes nothing")
        ok(o["sync2"]["rev"], "the revision is returned")
        ok(o["badKey"] == 401, "a phone with a wrong key is refused")
        ok(o["oldCounter"] == 401, "a request with an old counter (a replay) is refused")
        ok(o["sameTwice"] == [200, 401], "the very same encrypted request sent twice is accepted once")
        ok(any(t["text"] == "from the phone" for t in sl.d["todos"]), "the phone's task reached the computer")
        ok(len(sl.d["entries"]) == 30, "nothing was lost on the computer")
        phone = json.load(open(f, encoding="utf-8"))
        a = json.loads(json.dumps(sync._records(lap)))
        ok(sorted(a["entries"]) == sorted(e["id"] for e in phone["entries"]), "both have exactly the same study entries")
        ok("key" in (phone["sync"]["laptop"] or {}) and "secret" not in json.dumps(sl.d), "the phone keeps its key; the study data does not contain it")
        # ---- the computer's address changes after the pairing (here: another port) -> the phone finds it again by itself
        import socket
        srv.stop()
        blockers = []
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0", port)); s.listen(); blockers.append(s)
        srv = lansync.LanServer(lansync.StoreBackend(lap, sl))
        port2 = srv.start()
        ok(port2 != port, f"the computer came back on another port ({port} -> {port2})")
        r = subprocess.run(["node", str(Path(__file__).with_name("lan_reconnect.js")), f, str(port)], capture_output=True, text=True, encoding="utf-8", timeout=120)
        if r.returncode != 0: print(r.stderr)
        mv = json.loads(r.stdout.strip().splitlines()[-1])
        ok(mv["rev"]["status"] == 200 and mv["after"] == f"127.0.0.1:{port2}", "the phone found the computer at its new address by itself (no 'forget and pair again')")
        ok(mv["sync"]["ok"], "and the sync after that works")
        ok(mv["noJunk"], "the saved pairing holds no search state")
        srv.stop()
        for b in blockers: b.close()
        r = subprocess.run(["node", str(Path(__file__).with_name("lan_reconnect.js")), f, "9", "off"], capture_output=True, text=True, encoding="utf-8", timeout=120)
        off = json.loads(r.stdout.strip().splitlines()[-1])
        ok(off["off"]["status"] == 0 and off["off"]["ms"] < 20000, f"a computer that is off gives a clean network error ({off['off']['ms']} ms)")
        ok(off["saved"].get("key") and off["noJunk"], "and the pairing is kept (the phone never has to pair again just because the computer was off)")
        srv = lansync.LanServer(lansync.StoreBackend(lap, sl))
        port3 = srv.start()
        r = subprocess.run(["node", str(Path(__file__).with_name("lan_reconnect.js")), f, "9", "scan"], capture_output=True, text=True, encoding="utf-8", timeout=120)
        if r.returncode != 0: print(r.stderr)
        sc = json.loads(r.stdout.strip().splitlines()[-1])
        ok(sc["scan"]["status"] == 200 and sc["scan"]["addr"].startswith("127.0.0.") and sc["scan"]["addr"].endswith(f":{port3}"), f"a computer with a new IP address is found by scanning the phone's network ({sc['scan']['addr']})")
    finally:
        srv.stop()
    print(); print(f"{len(FAILS)} failure(s)" if FAILS else "ALL PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
