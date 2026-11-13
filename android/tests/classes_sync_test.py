"""Weekly classes travel with the sync (computer <-> phone): a class made on the computer arrives on the phone, one made or edited on the phone
arrives on the computer, deletions travel, and the per-device 'reminder already shown today' marks are NOT shared.
Run: python android/tests/classes_sync_test.py   (needs Node)"""
import json
import os
import sys
import tempfile
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interop_test as I  # noqa: E402

ok = I.ok


def main():
    tmp = tempfile.mkdtemp()
    f = os.path.join(tmp, "phone.json")
    I.node("init", f)
    py = I.Py()
    today = date.today().isoformat()
    py.st.classes = I.S.clean_classes([
        {"id": "c1", "name": "Calculus", "day": 0, "time": "17:00", "minutes": 90, "remind": 15, "place": "Room 3", "rem_done": today, "start_done": today},
        {"id": "c2", "name": "Physics", "day": 2, "time": "9:30", "minutes": 60, "remind": 0, "enabled": False}])
    py.st.save_classes()
    node_import = lambda: I.node("import", f, stdin=json.dumps(py.export()))
    node_import()
    phone = json.load(open(f, encoding="utf-8"))
    names = sorted(c["name"] for c in phone["classes"])
    ok(names == ["Calculus", "Physics"], "classes made on the computer arrive on the phone")
    cal = next(c for c in phone["classes"] if c["name"] == "Calculus")
    ok(cal["time"] == "17:00" and cal["place"] == "Room 3" and cal["remind"] == 15, "with their time, place and reminder")
    ok("rem_done" not in cal and "start_done" not in cal, "the computer's 'already reminded today' marks are not sent to the phone")
    phys = next(c for c in phone["classes"] if c["name"] == "Physics")
    ok(phys["enabled"] is False and phys["time"] == "09:30", "a disabled class stays disabled; the time is normalised (9:30 -> 09:30)")
    # the phone edits one and adds one
    time.sleep(0.01)
    I.node("op", f, json.dumps({"t": "edit_class", "name": "Calculus", "time": "18:15", "place": "Hall B"}))
    I.node("op", f, json.dumps({"t": "add_class", "name": "Chemistry", "day": 4, "time": "08:00", "min": 75, "remind": 10, "place": ""}))
    py.imp(json.dumps(I.node("export", f)))
    byn = {c["name"]: c for c in py.st.classes}
    ok(sorted(byn) == ["Calculus", "Chemistry", "Physics"], "a class added on the phone arrives on the computer")
    ok(byn["Calculus"]["time"] == "18:15" and byn["Calculus"]["place"] == "Hall B", "an edit made on the phone arrives on the computer")
    ok(byn["Calculus"]["rem_done"] == today and byn["Calculus"]["start_done"] == today, "the computer keeps its own 'reminded today' marks")
    ok(byn["Chemistry"]["rem_done"] == "" and byn["Chemistry"]["id"], "a class that is new here has no marks")
    # deletion on the computer reaches the phone
    time.sleep(0.01)
    py.st.classes = [c for c in py.st.classes if c["name"] != "Physics"]
    py.st.save_classes()
    node_import()
    ok(sorted(c["name"] for c in json.load(open(f, encoding="utf-8"))["classes"]) == ["Calculus", "Chemistry"], "a class deleted on the computer is deleted on the phone")
    # an old file without classes must not wipe the classes here
    old = json.loads(json.dumps(py.export()))
    old["data"].pop("classes", None)
    I.node("import", f, stdin=json.dumps(old))
    ok(len(json.load(open(f, encoding="utf-8"))["classes"]) == 2, "a package from an older version (no classes) leaves the classes alone")
    print("\n%d failure(s)" % len(I.FAILS) if I.FAILS else "\nALL PASSED")
    return 1 if I.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
