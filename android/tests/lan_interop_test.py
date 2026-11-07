"""The phone's JavaScript client against the computer's real Python server (needs Node).
Run:  python android/tests/lan_interop_test.py"""
import json, os, shutil, subprocess, sys, tempfile
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
        r = subprocess.run(["node", str(Path(__file__).with_name("lan_client.js")), str(port), code, f], capture_output=True, text=True, encoding="utf-8", timeout=120)
        if r.returncode != 0: print(r.stderr); ok(False, "the JS client ran"); return 1
        o = json.loads(r.stdout)
        ok(o["ping"] and o["ping"]["device"]["id"], "the phone finds the computer with /v1/ping")
        ok(o["wrong"]["ok"] is False and o["wrong"]["error"] == "wrong", "a wrong code is refused with a clear reason")
        ok(o["pair"]["ok"], "pairing with the right code works")
        ok(o["sync1"]["ok"] and o["sync1"]["changes"] > 0, "the first sync brings the computer's data to the phone")
        ok(o["entries"] == 30 and "from the computer" in o["todos"] and "from the phone" in o["todos"], "the phone has its own data and the computer's")
        ok(o["sync2"]["ok"] and o["sync2"]["changes"] == 0, "a second sync changes nothing")
        ok(o["sync1"]["rev"] == o["sync2"]["rev"] or o["sync2"]["rev"], "the revision is returned")
        ok(o["badToken"] == 401, "a wrong token is refused")
        ok(any(t["text"] == "from the phone" for t in sl.d["todos"]), "the phone's task reached the computer")
        ok(len(sl.d["entries"]) == 30, "nothing was lost on the computer")
        phone = json.load(open(f, encoding="utf-8"))
        from voidlock.sync import _records
        a = json.loads(json.dumps(_records(lap)))
        ok(sorted(a["entries"]) == sorted(e["id"] for e in phone["entries"]), "both have exactly the same study entries")
    finally:
        srv.stop()
    print(); print(f"{len(FAILS)} failure(s)" if FAILS else "ALL PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
