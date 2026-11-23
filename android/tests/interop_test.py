"""The computer (Python) and the phone (JavaScript) must end up with the same data after any mix of work and syncs.
Run:  python android/tests/interop_test.py        (needs Node)"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
from voidlock import store as S, study, sync  # noqa: E402

JS = str(Path(__file__).with_name("jsdev.js"))
FAILS = []


def ok(cond, name):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def node(cmd, f, arg=None, stdin=None):
    r = subprocess.run(["node", JS, cmd, f] + ([arg] if arg is not None else []), input=stdin, capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return json.loads(r.stdout) if r.stdout.strip() else None


def norm(x):
    """Numbers compare by value (55 == 55.0) and key order does not matter."""
    if isinstance(x, float) and x == int(x):
        return int(x)
    if isinstance(x, dict):
        return {k: norm(v) for k, v in sorted(x.items())}
    if isinstance(x, list):
        return [norm(v) for v in x]
    return x


class Py:
    def __init__(self):
        self.st = S.Store(Path(tempfile.mkdtemp()))
        self.sl = study.StudyLog(self.st)
        self.st.study["subjects"] = []

    def op(self, o):
        sl, d = self.sl, date.fromisoformat(o["date"]) if o.get("date") else date.today()
        by = lambda lst, n: next((x for x in lst if x["name"].lower() == str(n).lower()), None)
        t = o["t"]
        if t == "add_subject": sl.add_subject(o["name"], o.get("color"))
        elif t == "remove_subject":
            s = by(sl.subjects(), o["name"]); s and sl.remove_subject(s["id"])
        elif t == "add_entry":
            s = by(sl.subjects(), o["name"]); s and sl.add_manual(d, s["id"], o["min"])
        elif t == "remove_entry":
            e = next((x for x in sl.d["entries"] if x["sec"] == o["sec"]), None)
            if e: sl.d["entries"].remove(e); sl.save()
        elif t == "add_todo": sl.add_todo(d, o["text"])
        elif t == "remove_todo":
            x = next((x for x in sl.d["todos"] if x["text"] == o["text"]), None); x and sl.remove_todo(x["id"])
        elif t == "toggle_todo":
            x = next((x for x in sl.d["todos"] if x["text"] == o["text"]), None); x and sl.toggle_todo(x["id"])
        elif t == "add_exam": sl.add_exam(o["name"], d)
        elif t == "remove_exam":
            x = next((x for x in sl.d["exams"] if x["name"] == o["name"]), None); x and sl.remove_exam(x["id"])
        elif t == "add_exam_subject": sl.add_exam_subject(o["name"], o.get("color"))
        elif t == "exam_result":
            e = next((x for x in sl.d["exams"] if x["name"] == o["name"]), None); s = by(sl.exam_subjects(), o["subject"])
            if e and s: sl.set_exam_result(e["id"], o["taraz"], o["rank"], [{"sid": s["id"], "pct": o["pct"], "taraz": o["taraz"]}], "", o["region"])
        elif t == "add_class":
            self.st.classes = S.clean_classes(self.st.classes + [{"id": S.uid(), "name": o["name"], "day": o["day"], "time": o["time"], "minutes": o["min"],
                                                                  "remind": o["remind"], "place": o["place"]}])
            self.st.save_classes()
        elif t == "edit_class":
            c = next((x for x in self.st.classes if x["name"] == o["name"]), None)
            if c:
                c["time"], c["place"] = o["time"], o["place"]
                self.st.classes = S.clean_classes(self.st.classes)
                self.st.save_classes()
        elif t == "remove_class":
            self.st.classes = [c for c in self.st.classes if c["name"] != o["name"]]
            self.st.save_classes()
        elif t == "counter":
            s = by(sl.subjects(), o["name"])
            if s:
                k = o["kind"]; day = sl.d[k].setdefault(d.isoformat(), {})
                if o["n"] > 0: day[s["id"]] = o["n"]
                else: day.pop(s["id"], None); (not day) and sl.d[k].pop(d.isoformat(), None)
                sl.save()

    def export(self):
        return sync.make_package(self.st)

    def imp(self, raw):
        plan = sync.prepare(self.st, raw)
        sync.commit(self.st, plan, sl=self.sl)

    def records(self):
        return json.loads(json.dumps(sync._records(self.st)))


def rand_op(rnd, step, names, ex_names):
    today = date.today()
    day = (today - timedelta(days=rnd.randint(0, 40))).isoformat()
    r = rnd.random()
    if r < 0.30: return {"t": "add_entry", "name": rnd.choice(names), "min": rnd.randint(5, 180), "date": day}
    if r < 0.38: return {"t": "add_todo", "text": f"todo {step}", "date": day}
    if r < 0.43: return {"t": "remove_todo", "text": f"todo {rnd.randint(0, step)}"}
    if r < 0.48: return {"t": "toggle_todo", "text": f"todo {rnd.randint(0, step)}"}
    if r < 0.54: return {"t": "add_subject", "name": rnd.choice(names + ["Geo", "Bio"]), "color": rnd.choice([None, "#14B8A6", "#9333EA"])}
    if r < 0.57: return {"t": "remove_subject", "name": rnd.choice(names)}
    if r < 0.63: return {"t": "add_exam", "name": f"exam {step}", "date": (today + timedelta(days=rnd.randint(-15, 50))).isoformat()}
    if r < 0.66: return {"t": "remove_exam", "name": f"exam {rnd.randint(0, step)}"}
    if r < 0.70: return {"t": "add_exam_subject", "name": rnd.choice(ex_names)}
    if r < 0.76: return {"t": "exam_result", "name": f"exam {rnd.randint(0, step)}", "subject": rnd.choice(ex_names), "taraz": rnd.randint(4000, 9000),
                         "rank": rnd.randint(1, 20000), "region": rnd.randint(1, 900), "pct": rnd.choice([40, 55.5, 62.25, 71])}
    if r < 0.82: return {"t": "counter", "kind": rnd.choice(["tests", "words"]), "name": rnd.choice(names), "n": rnd.randint(0, 40), "date": day}
    hm = lambda: f"{rnd.randint(6, 21):02d}:{rnd.choice([0, 15, 30, 45]):02d}"
    if r < 0.86: return {"t": "add_class", "name": f"class {step}", "day": rnd.randint(0, 6), "time": hm(), "min": rnd.choice([45, 60, 90, 120]), "remind": rnd.choice([0, 10, 15, 30]),
                         "place": rnd.choice(["", "Room 12", "Online"])}
    if r < 0.89: return {"t": "edit_class", "name": f"class {rnd.randint(0, step)}", "time": hm(), "place": rnd.choice(["", "Hall B"])}
    if r < 0.92: return {"t": "remove_class", "name": f"class {rnd.randint(0, step)}"}
    return None


def main():
    if not shutil.which("node"):
        print("node not found: skipped")
        return 0
    names = ["Math", "Physics", "Chem", "Bio", "Lit"]
    ex_names = ["Calculus", "Physics", "Chem"]
    for seed in range(12):
        rnd = random.Random(seed)
        tmp = tempfile.mkdtemp()
        f = os.path.join(tmp, "phone.json")
        node("init", f)
        py = Py()
        added = []
        for step in range(140):
            o = rand_op(rnd, step, names, ex_names)
            who = rnd.choice(["py", "js"])
            if o and who == "py": py.op(o)
            elif o: node("op", f, json.dumps(o))
            if rnd.random() < 0.10:                                                  # a sync, in a random direction
                if rnd.random() < 0.5:
                    node("import", f, stdin=json.dumps(py.export()))
                else:
                    py.imp(json.dumps(node("export", f)))
            time.sleep(0.002)
        for _ in range(2):                                                           # settle: py -> js, js -> py, py -> js
            node("import", f, stdin=json.dumps(py.export()))
            py.imp(json.dumps(node("export", f)))
        node("import", f, stdin=json.dumps(py.export()))
        a, b = norm(py.records()), norm(node("records", f))
        same = a == b
        if not same:
            for k in a:
                if a[k] != b.get(k):
                    print("  differs in", k, len(a[k]), len(b.get(k, {})))
        ok(same, f"[seed {seed}] the computer (Python) and the phone (JavaScript) hold identical data")
        n = sum(len(v) for v in a.values())
        ok(n > 20, f"[seed {seed}] the data is not trivially empty ({n} records)")
    # packages are exchanged in both directions between the two implementations and a damaged one is refused
    f = os.path.join(tempfile.mkdtemp(), "p.json")
    node("init", f)
    bad = node("import", f, stdin="not json")
    ok(bad["ok"] is False and "not a VOIDLOCK" in bad["error"], "the phone refuses a file that is not a sync file")
    py = Py()
    py.op({"t": "add_subject", "name": "Math"})
    py.op({"t": "add_entry", "name": "Math", "min": 120})
    res = node("import", f, stdin=json.dumps(py.export()))
    ok(res["ok"] and res["stats"]["entries"]["added"] == 1, "the phone imports a package made by the computer")
    own = node("export", f)
    try:
        sync.prepare(py.st, json.dumps({**own, "device": {"id": sync.load_state(py.st.home)["device_id"], "name": "x"}}))
        ok(False, "the computer refuses a package carrying its own id")
    except sync.SyncError:
        ok(True, "the computer refuses a package carrying its own id")
    print()
    print(f"{len(FAILS)} failure(s)" if FAILS else "ALL PASSED")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
