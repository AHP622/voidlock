"""The Overview dashboard numbers (voidlock/dashboard.py): no Qt needed.  python tests/dashboard_test.py"""
import random
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voidlock import dashboard as D, store as S, study  # noqa: E402


def build():
    st = S.Store(Path(tempfile.mkdtemp()))
    sl = study.StudyLog(st)
    sl.d["subjects"] = []
    subs = [sl.add_subject(n, c) for n, c in (("Math", "#8B5CF6"), ("Physics", "#00C2FF"), ("Chem", "#34D399"), ("Bio", "#FBBF24"), ("Lit", "#FF5DA2"), ("Arabic", "#60A5FA"), ("Geo", "#F97316"))]
    rnd = random.Random(3)
    today = date.today()
    for k in range(60, -1, -1):
        d = today - timedelta(days=k)
        if rnd.random() < 0.15 and k:
            continue
        for s in rnd.sample(subs, 3):
            sl.add_manual(d, s["id"], rnd.randint(20, 90))
    return st, sl, subs, today


class Dash(unittest.TestCase):
    def test_daily_and_chart(self):
        st, sl, subs, today = build()
        secs = D.daily(sl, today, 30, extra_today=120)
        self.assertEqual(len(secs), 30 + D.LOOKBACK)
        self.assertEqual(secs[today], sl.day_sec(today, True) + 120)
        ch = D.chart(secs, today, 30, 4 * 3600, [today - timedelta(days=3)])
        self.assertEqual(len(ch["bars"]), 30)
        self.assertEqual(ch["bars"][-1]["date"], today)
        self.assertTrue(all(b["ma"] is not None for b in ch["bars"]), "a full week of history exists before the first bar")
        self.assertEqual(sum(1 for b in ch["bars"] if b["exam"]), 1)
        self.assertGreaterEqual(ch["top_h"] * 3600, max(b["sec"] for b in ch["bars"]))
        self.assertGreaterEqual(ch["top_h"] * 3600, 4 * 3600)

    def test_moving_average_starts_honestly(self):
        self.assertEqual(D.moving_average([1] * 5), [None] * 5)
        self.assertEqual(D.moving_average([7] * 8)[6:], [7.0, 7.0])

    def test_streak_matches_the_study_log(self):
        st, sl, subs, today = build()
        secs = D.daily(sl, today, 30)
        for back in (0, 1, 5, 9):
            self.assertEqual(D.streak_at(secs, today - timedelta(days=back)), sl.streak(D.STREAK_MIN_SEC, today - timedelta(days=back)))

    def test_kpis(self):
        st, sl, subs, today = build()
        secs = D.daily(sl, today, 30)
        pts = study.Points(st)
        pts.add(40, "clean", day=today.isoformat())
        pts.add(10, "clean", day=(today - timedelta(days=2)).isoformat())
        st.history = [{"start": datetime.combine(today, datetime.min.time()).timestamp() + 3600, "focus_sec": 3000, "status": "completed"},
                      {"start": datetime.combine(today - timedelta(days=9), datetime.min.time()).timestamp() + 3600, "focus_sec": 1500, "status": "completed"}]
        k = D.kpis(secs, st.history, pts, today)
        self.assertEqual(k["today"]["value"], secs[today])
        self.assertEqual(len(k["today"]["spark"]), 7)
        self.assertEqual(k["points"]["change"], 40)
        self.assertEqual(k["points"]["spark"][-1], pts.balance)
        self.assertEqual(k["points"]["spark"][0], pts.balance - 50)            # 6 days ago: neither the +10 (2 days ago) nor today's +40 existed yet
        self.assertEqual(k["points"]["spark"][4], 10)                          # end of the day the +10 arrived
        self.assertEqual(k["focus"]["value"], 3000)
        self.assertEqual(k["focus"]["change"], 100)                           # 3000 vs 1500 the week before
        self.assertEqual(k["streak"]["spark"][-1], k["streak"]["value"])

    def test_pct_change(self):
        self.assertIsNone(D.pct_change(5, 0))
        self.assertEqual(D.pct_change(150, 100), 50)
        self.assertEqual(D.pct_change(50, 100), -50)

    def test_share_adds_up_and_groups_small_subjects(self):
        st, sl, subs, today = build()
        rows, total = D.share(sl, today, 30, keep=5)
        self.assertEqual(sum(r[2] for r in rows), total)
        self.assertLessEqual(len(rows), 6)
        self.assertEqual(rows[-1][0], "")                                      # the "others" row
        direct = sum(sl.day_sec(today - timedelta(days=i), True, include_sessions=False) for i in range(30))
        self.assertEqual(total, direct)

    def test_recent_and_upcoming(self):
        st, sl, subs, today = build()
        now = datetime.now()
        hist = [{"start": (now - timedelta(days=k)).timestamp(), "subject": "Math", "focus_sec": 100 * k, "planned_min": 45, "status": "completed"} for k in range(5)] + [{"bad": 1}]
        rs = D.recent_sessions(hist, 3)
        self.assertEqual([r["focus_sec"] for r in rs], [0, 100, 200])
        sl.add_exam("Mock", today + timedelta(days=6))
        cls = [{"id": "a", "name": "Physics", "day": (now + timedelta(hours=2)).weekday(), "time": (now + timedelta(hours=2)).strftime("%H:%M"), "minutes": 90, "remind": 10, "enabled": True}]
        up = D.upcoming(sl, cls, now, "Lock hours: Games until 22:00")
        kinds = [u["kind"] for u in up]
        self.assertEqual(kinds, ["exam", "class", "hours"])
        self.assertEqual(up[0]["days"], 6)
        self.assertTrue(1 <= up[1]["minutes"] <= 120)

    def test_chart_axis_steps_stay_readable(self):
        for hrs in (1, 3, 5, 7.5, 11, 30):
            secs = {date.today(): int(hrs * 3600)}
            ch = D.chart(secs, date.today(), 1, 0)
            self.assertLessEqual(ch["top_h"] / ch["step_h"], 5)
            self.assertGreaterEqual(ch["top_h"], hrs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
