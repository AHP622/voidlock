"""android/.../js/classes.js must agree with voidlock/classes.py (occurrences, today's list, current/next class).  python android/tests/classes_parity_test.py"""
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from voidlock import classes as C, store as S  # noqa: E402

JS = ROOT / "android/app/src/main/assets/www/js/classes.js"
FAILS = []


def main():
    rnd = random.Random(5)
    cls = S.clean_classes([{"id": f"c{i}", "name": f"C{i}", "day": rnd.randint(0, 6), "time": f"{rnd.randint(0, 23):02d}:{rnd.choice([0, 15, 30, 45]):02d}",
                            "minutes": rnd.choice([30, 45, 60, 90, 180, 600]), "remind": rnd.choice([0, 5, 15, 30]), "enabled": rnd.random() > 0.2} for i in range(18)])
    base = datetime(2026, 11, 8, 0, 0)
    nows = [base + timedelta(minutes=rnd.randint(0, 60 * 24 * 21), seconds=rnd.randint(0, 59)) for _ in range(150)]
    expected = []
    for now in nows:
        occ = [[s.isoformat(), e.isoformat(), c["id"]] for s, e, c in C.occurrences(cls, now)]
        tl = [[s.isoformat(), e.isoformat(), c["id"]] for s, e, c in C.today_list(cls, now)]
        st, c, s, e = C.current_or_next(cls, now)
        expected.append({"occ": occ, "today": tl, "cur": [st, c["id"] if c else None, s.isoformat() if s else None, e.isoformat() if e else None]})
    code = f"""
const C = require({json.dumps(str(JS))}); const d = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const iso = (x) => x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0') + 'T' + String(x.getHours()).padStart(2, '0') + ':' + String(x.getMinutes()).padStart(2, '0') + ':' + String(x.getSeconds()).padStart(2, '0');
const out = d.nows.map((n) => {{ const p = n.match(/\\d+/g).map(Number), now = new Date(p[0], p[1] - 1, p[2], p[3], p[4], p[5]);
  const f = (o) => [iso(o.start), iso(o.end), o.cls.id]; const cur = C.currentOrNext(d.cls, now);
  return {{ occ: C.occurrences(d.cls, now).map(f), today: C.todayList(d.cls, now).map(f), cur: [cur.state, cur.cls ? cur.cls.id : null, cur.start ? iso(cur.start) : null, cur.end ? iso(cur.end) : null] }}; }});
process.stdout.write(JSON.stringify(out));
"""
    p = subprocess.run(["node", "-e", code], input=json.dumps({"cls": cls, "nows": [n.isoformat() for n in nows]}), capture_output=True, text=True, encoding="utf-8", timeout=60)
    if p.returncode:
        print(p.stderr)
        return 1
    got = json.loads(p.stdout)
    bad = [i for i, (a, b) in enumerate(zip(expected, got)) if a != b]
    for i in bad[:2]:
        print("DIFF at", nows[i], "\n py:", expected[i]["cur"], expected[i]["occ"][:2], "\n js:", got[i]["cur"], got[i]["occ"][:2])
    print(("PASS" if not bad else "FAIL") + f" the phone's classes.js equals classes.py on {len(nows)} random moments ({len(bad)} differences)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
