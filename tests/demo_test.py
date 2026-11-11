"""The screenshot demo data (voidlock/demo.py): complete, believable, in both languages, and never on top of real data."""
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from voidlock import dashboard as D, demo, intro, report, store as S, study  # noqa: E402


def make(lang):
    st = S.Store(Path(tempfile.mkdtemp()))
    sl, pts = study.StudyLog(st), study.Points(st)
    assert not demo.has_data(st, sl)
    demo.fill(st, sl, pts, lang)
    return st, sl, pts


class Demo(unittest.TestCase):
    def test_both_languages_fill_everything(self):
        for lang in ("fa", "en"):
            st, sl, pts = make(lang)
            self.assertEqual(len(sl.subjects()), 6)
            self.assertGreater(len(sl.d["entries"]), 60)
            self.assertEqual(len([e for e in sl.exams() if e.get("result")]), 5)
            self.assertEqual(len(st.classes), 5)
            self.assertEqual(len(st.history), 14)
            self.assertGreater(pts.balance, 100)
            self.assertTrue(sl.todos(date.today()))
            self.assertTrue(demo.has_data(st, sl), "a second run must refuse to touch it")
            r = [x for x in sl.exams() if x.get("result")][-1]["result"]
            self.assertIsNotNone(r["rank_region"])

    def test_the_dashboard_and_the_report_work_on_it(self):
        st, sl, pts = make("fa")
        today = date.today()
        secs = D.daily(sl, today, 30)
        k = D.kpis(secs, st.history, pts, today)
        self.assertGreater(k["today"]["value"], 0)
        rows, total = D.share(sl, today, 30)
        self.assertGreater(total, 3600 * 20)
        up = D.upcoming(sl, st.classes, datetime.now())
        self.assertIn("exam", [u["kind"] for u in up])
        R = report.collect(st, sl, today - timedelta(days=29), today, name="demo", lang="fa", goal_min=240)
        self.assertGreater(R["summary"]["total"], 0)
        self.assertTrue(report.render_html(R).startswith("<!DOCTYPE html>"))

    def test_tab_order_matches_the_sidebar(self):
        self.assertEqual(demo.order_of_tabs(), intro.ORDER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
