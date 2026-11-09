"""The phone's report (android .../js/report.js) must be the computer's report (voidlock/report.py): same data in, same report out.
Run:  python android/tests/report_parity_test.py      (needs Node; no Qt)"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
from voidlock import report, store as S, study, sync  # noqa: E402

FAILS = []


def ok(cond, name):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def make_data():
    """A rich computer-side database: subjects (one deleted), entries over 40 days, tests, words, exams with results, sessions."""
    home = Path(tempfile.mkdtemp())
    st = S.Store(home)
    sl = study.StudyLog(st)
    st.study["subjects"] = []
    names = [("Math", "#8B5CF6"), ("Physics", "#00C2FF"), ("Chemistry", "#34D399"), ("Biology", "#FBBF24"), ("Literature", "#FB7185"),
             ("English", "#60A5FA"), ("Geometry", "#F97316")]
    subs = [sl.add_subject(n, c) for n, c in names]
    import random
    rnd = random.Random(7)
    today = date.today()
    for k in range(40, 0, -1):
        d = today - timedelta(days=k)
        if rnd.random() < 0.15:
            continue
        for s in rnd.sample(subs, rnd.randint(1, 4)):
            sl.add_manual(d, s["id"], rnd.randint(10, 150))
        for s in rnd.sample(subs, 2):
            if rnd.random() < 0.7:
                sl.set_tests(d, s["id"], rnd.randint(5, 60))
            if rnd.random() < 0.3:
                sl.set_words(d, s["id"], rnd.randint(5, 40))
    sl.remove_subject(subs[6]["id"])                       # its time stays as a "deleted" subject
    es = [sl.add_exam_subject(n, c) for n, c in names[:5]]
    for i, off in enumerate((30, 22, 14, 7)):
        e = sl.add_exam(f"Mock {i + 1}", today - timedelta(days=off))
        rows = [{"sid": x["id"], "pct": 40 + rnd.randint(0, 50), "taraz": 4800 + rnd.randint(0, 3000)} for x in es]
        sl.set_exam_result(e["id"], taraz=6000 + i * 150 + rnd.randint(-80, 80), rank=9000 - i * 700 + rnd.randint(-200, 200),
                           rank_region=420 - i * 40 + rnd.randint(-15, 15), subjects=rows, note="note %d" % i if i % 2 else "")
    sl.add_exam("Future exam", today + timedelta(days=5))
    hist = []
    for k in range(10):
        t0 = datetime.combine(today - timedelta(days=k * 3 + 1), datetime.min.time()) + timedelta(hours=9)
        hist.append({"start": t0.timestamp(), "subject": "Math", "planned_min": 60, "focus_sec": 3300 - 60 * k, "status": "completed", "blocked_count": k})
    st.history = hist
    st.save_history() if hasattr(st, "save_history") else None
    return st, sl


def js_report(pkg_path, lang, frm, to, name, goal_min):
    code = f"""
const path = require('path'), fs = require('fs');
const W = {json.dumps(str(ROOT / 'android/app/src/main/assets/www/js'))};
global.Core = require(path.join(W, 'core.js')); global.Jalali = require(path.join(W, 'jalali.js'));
const Report = require(path.join(W, 'report.js'));
const db = Core.ensure(Core.newDb()); db.subjects = [];
const plan = Core.prepare(db, fs.readFileSync({json.dumps(str(pkg_path))}, 'utf8')); Core.commit(db, plan);
db.settings.goal_min = {goal_min};
const r = Report.build(db, {json.dumps(frm)}, {json.dumps(to)}, {{ lang: {json.dumps(lang)}, name: {json.dumps(name)}, version: {json.dumps(report.__version__)}, interactive: true }});
process.stdout.write(JSON.stringify({{ html: r.html, csv: r.csv }}));
"""
    p = subprocess.run(["node", "-e", code], capture_output=True, text=True, encoding="utf-8", timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


NUM = re.compile(r"-?\d+(?:\.\d+)?")


def norm_html(h):
    """Both sides must agree on everything a person reads; ignore the creation date and tiny float differences in drawing."""
    h = re.sub(r"(<span>[^<]*(?:Created|تاریخ تهیه): )[^<]*(</span>)", r"\1X\2", h)
    h = re.sub(r"\s+", " ", h)
    return h


def svg_numbers(h):
    return [float(x) for x in NUM.findall(" ".join(re.findall(r'<svg.*?</svg>', h, flags=re.S)))]


def compare(lang, frm_off, to_off, name):
    st, sl = make_data()
    today = date.today()
    frm, to = today - timedelta(days=frm_off), today - timedelta(days=to_off)
    pkg = Path(tempfile.mkdtemp()) / "x.voidsync"
    pkg.write_text(json.dumps(sync.make_package(st)), encoding="utf-8")
    R = report.collect(st, sl, frm, to, name=name, lang=lang, goal_min=150)
    py_html, py_csv = report.render_html(R), report.render_csv(R)
    js = js_report(pkg, lang, frm.isoformat(), to.isoformat(), name, 150)
    tag = f"[{lang} {frm_off}d..{to_off}d]"
    # text of the page: strip the svg pictures, compare the rest exactly
    strip = lambda h: re.sub(r"<svg.*?</svg>", "<svg/>", norm_html(h), flags=re.S)
    a, b = strip(py_html), strip(js["html"])
    if a != b:
        # show the first difference
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
        print("   py :", a[max(0, i - 120):i + 160])
        print("   js :", b[max(0, i - 120):i + 160])
    ok(a == b, f"{tag} HTML text is identical")
    pa, pb = svg_numbers(py_html), svg_numbers(js["html"])
    same = len(pa) == len(pb) and all(abs(x - y) <= 0.11 for x, y in zip(pa, pb))
    if not same:
        print("   svg numbers:", len(pa), len(pb), next(((x, y) for x, y in zip(pa, pb) if abs(x - y) > 0.11), None))
    ok(same, f"{tag} charts are drawn identically ({len(pa)} numbers)")
    ca, cb = py_csv.replace("\r\n", "\n"), js["csv"].lstrip("\ufeff").replace("\r\n", "\n")
    ca = re.sub(r"^(.*(?:Created|تاریخ تهیه).*)$", "G", ca, flags=re.M)
    cb = re.sub(r"^(.*(?:Created|تاریخ تهیه).*)$", "G", cb, flags=re.M)
    if ca != cb:
        la, lb = ca.split("\n"), cb.split("\n")
        i = next((k for k in range(min(len(la), len(lb))) if la[k] != lb[k]), 0)
        print("   py csv:", la[i]); print("   js csv:", lb[i])
    def cells(txt):
        import csv as _csv, io
        out = []
        for row in _csv.reader(io.StringIO(txt)):
            r = []
            for c in row:
                try:
                    r.append(float(c))              # a percent kept as 57.0 on the computer arrives as 57 on the phone (JSON)
                except ValueError:
                    r.append(c)
            out.append(r)
        return out
    ok(cells(ca) == cells(cb), f"{tag} CSV is identical")


if __name__ == "__main__":
    for lang in ("en", "fa"):
        compare(lang, 13, 0, "Sara")
        compare(lang, 39, 0, "")
        compare(lang, 100, 3, "Ali")       # longer than 62 days: monthly table
    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)
