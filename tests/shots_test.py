"""Screenshot automation (voidlock/shots.py, `--screenshots`), offscreen. Run: python tests/shots_test.py

Checks: right order, right number of pictures, the next tab starts only after the previous picture is saved, a failed save is
reported (not hidden) and the program still quits, a wrong/stuck tab never saves the wrong content, and the real window with
the strong-student demo data produces one different PNG per tab without touching any real user data.
"""
import hashlib
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from voidlock import demo, study as studymod  # noqa: E402
from voidlock.shots import ShotRunner  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
KEYS = ["overview", "study", "apps", "sessions"]


class FakeWin:
    """Records every call, so the test can see the exact order of events."""

    def __init__(self, log, shows=None):
        self.log, self.current, self._shows = log, None, shows

    def showNormal(self): self.log.append("show")
    def resize(self, w, h): self.log.append(f"resize {w}x{h}")
    def width(self): return 300
    def height(self): return 200

    def goto(self, key, animate=True):
        self.log.append(f"goto {key}")
        self.current = key

    def current_key(self):
        return self._shows(self.current) if self._shows else self.current


def make_grab(log, win):
    def grab():
        log.append(f"paint {win.current}")
        img = QImage(30, 20, QImage.Format.Format_ARGB32)
        img.fill(QColor(10 + len(log), 80, 160))
        return img
    return grab


def run(runner, limit_ms=15000):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(limit_ms, lambda: app.exit(99))        # the test itself must never hang
    runner.start()
    return app.exec()


class Order(unittest.TestCase):
    def test_every_tab_in_order_and_next_starts_after_the_save(self):
        out, log = Path(tempfile.mkdtemp()), []
        win = FakeWin(log)
        r = ShotRunner(app, win, KEYS, out, start_delay=10, settle=20, grab=make_grab(log, win))
        orig_say = r.say
        r.say = lambda t, error=False: (log.append("say " + t.split("/")[-1]) if t.startswith("saved") else None, orig_say(t, error))[1]
        code = run(r)
        self.assertEqual(code, 0)
        self.assertEqual([k for _, k, _ in r.saved], KEYS)
        self.assertEqual(sorted(p.name for p in out.glob("*.png")), [f"{i + 1:02d}_{k}.png" for i, k in enumerate(KEYS)])
        steps = [e for e in log if e.startswith(("goto", "paint", "say"))]
        expect = []
        for i, k in enumerate(KEYS):
            expect += [f"goto {k}", f"paint {k}", f"say {i + 1:02d}_{k}.png"]
        self.assertEqual(steps, expect, "goto(next) must come only after paint+save of the previous tab")
        for p in out.glob("*.png"):
            self.assertGreater(p.stat().st_size, 0)


class Failures(unittest.TestCase):
    def test_a_failed_save_is_reported_and_the_program_still_quits(self):
        out, log = Path(tempfile.mkdtemp()), []
        (out / "02_study.png").mkdir()                       # a folder with that name: saving 02_study.png must fail
        win = FakeWin(log)
        r = ShotRunner(app, win, KEYS, out, start_delay=10, settle=20, grab=make_grab(log, win))
        code = run(r)
        self.assertEqual(code, 1, "exit code 1 = at least one picture failed")
        self.assertEqual([k for _, k, _ in r.saved], ["overview", "apps", "sessions"])
        self.assertEqual(len(r.errors), 1)
        self.assertIn("study", r.errors[0])
        self.assertIn("ERROR", (out / "screenshots.log").read_text(encoding="utf-8"))

    def test_a_painting_error_does_not_hang_and_does_not_stop_the_other_tabs(self):
        out, log = Path(tempfile.mkdtemp()), []
        win = FakeWin(log)
        good, calls = make_grab(log, win), {"n": 0}

        def grab():
            calls["n"] += 1
            if calls["n"] == 1:
                raise TypeError("render() called with wrong argument types")   # the original 1.14.2 failure
            return good()
        r = ShotRunner(app, win, KEYS, out, start_delay=10, settle=20, grab=grab)
        self.assertEqual(run(r), 1)
        self.assertEqual(len(r.saved), 3)
        self.assertIn("wrong argument types", r.errors[0])

    def test_a_picture_is_never_saved_when_another_tab_is_showing(self):
        out, log = Path(tempfile.mkdtemp()), []
        win = FakeWin(log, shows=lambda cur: "overview")      # the window stays on the first tab
        r = ShotRunner(app, win, KEYS, out, start_delay=10, settle=20, grab=make_grab(log, win))
        self.assertEqual(run(r), 1)
        self.assertEqual([k for _, k, _ in r.saved], ["overview"])
        self.assertEqual(len(r.errors), 3)
        self.assertEqual(len(list(out.glob("*.png"))), 1)

    def test_a_stuck_run_times_out_and_quits(self):
        out, log = Path(tempfile.mkdtemp()), []
        win = FakeWin(log)
        r = ShotRunner(app, win, KEYS, out, start_delay=10, settle=5000, limit_s=0.3, grab=make_grab(log, win))
        self.assertEqual(run(r), 1)
        self.assertTrue(any("timed out" in e for e in r.errors))


class RealWindow(unittest.TestCase):
    def test_real_window_one_different_png_per_tab_and_user_data_untouched(self):
        from voidlock.app import MainWindow
        from voidlock.guard import GuardClient
        from voidlock.intro import ORDER
        from voidlock.store import Store
        from voidlock.theme import apply_theme, font, stylesheet
        home, out = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        st = Store(home)
        sl, pts = studymod.StudyLog(st), studymod.Points(st)
        self.assertFalse(demo.has_data(st, sl))
        demo.fill(st, sl, pts, "en")
        demo.quiet_first_run(st, "test")
        st.settings["language"] = "en"
        st.save_settings()
        apply_theme("void")
        app.setStyleSheet(stylesheet())
        app.setFont(font(13))
        win = MainWindow(st, GuardClient(st))
        win.show()
        r = ShotRunner(app, win, demo.order_of_tabs(), out, size=(1280, 860), scale=1, start_delay=300, settle=500)
        code = run(r, limit_ms=90000)
        self.assertEqual((code, r.errors), (0, []))
        names = sorted(p.name for p in out.glob("*.png"))
        self.assertEqual(names, [f"{i + 1:02d}_{k}.png" for i, k in enumerate(ORDER)])
        digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob("*.png")}
        self.assertEqual(len(digests), len(ORDER), "every tab must give its own picture")
        for p in out.glob("*.png"):
            img = QImage(str(p))
            self.assertEqual((img.width(), img.height()), (1280, 860))
        self.assertFalse(st.settings.get("update_check"), "no network / update in screenshot mode")
        win.close()


class EndToEnd(unittest.TestCase):
    def test_main_py_takes_every_picture_exits_cleanly_and_refuses_a_used_home(self):
        import subprocess
        from voidlock.intro import ORDER
        home, out = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        cmd = [sys.executable, str(ROOT / "main.py"), "--home", str(home), "--screenshots", str(out), "--shot-scale", "1"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=150, env=env)
        self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
        self.assertEqual(len(list(out.glob("*.png"))), len(ORDER))
        self.assertNotIn("QThread", r.stderr, "the window must be closed properly (no thread left running)")
        again = subprocess.run(cmd[:-2] + ["--shot-scale", "1"], capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(again.returncode, 2, "a home that already has data is refused")
        self.assertIn("already has data", again.stdout)
        # --screenshots without --home must never fall back to the real data folder
        bare = subprocess.run([sys.executable, str(ROOT / "main.py"), "--screenshots", str(out)], capture_output=True, text=True,
                              timeout=60, env=env)
        self.assertEqual(bare.returncode, 2)


class StrongStudentDemo(unittest.TestCase):
    def test_demo_is_a_strong_student_and_is_the_same_every_time(self):
        from voidlock import dashboard as D
        from voidlock.store import Store
        today = date.today()
        runs = []
        for _ in range(2):
            st = Store(Path(tempfile.mkdtemp()))
            sl, pts = studymod.StudyLog(st), studymod.Points(st)
            demo.fill(st, sl, pts, "fa")
            per_day = D.daily(sl, today, 30)
            secs = [per_day[today - timedelta(days=k)] for k in range(30)]
            self.assertTrue(all(v > 0 for v in secs), "studied on every one of the last 30 days")
            self.assertGreaterEqual(sum(secs) / len(secs) / 3600, 4.5, "at least 4.5 hours a day on average")
            res = [x["result"] for x in sl.exams() if x.get("result")]
            self.assertEqual(len(res), 5)
            self.assertEqual([x["taraz"] for x in res], sorted(x["taraz"] for x in res), "taraz keeps climbing")
            self.assertGreaterEqual(res[-1]["taraz"], 8000)
            self.assertLess(res[-1]["rank"], 100)
            self.assertLessEqual(res[-1]["rank_region"], 9)
            for x in res:
                self.assertTrue(all(s["pct"] >= 70 for s in x["subjects"]))
            done = sum(1 for h in st.history if h["status"] == "completed")
            self.assertGreaterEqual(done, 12, "almost every focus session completed")
            runs.append((round(sum(secs)), [x["taraz"] for x in res], [x["rank"] for x in res]))
        self.assertEqual(runs[0], runs[1], "fixed seed: identical data every time")

    def test_never_touches_a_folder_that_already_has_data(self):
        from voidlock.store import Store
        st = Store(Path(tempfile.mkdtemp()))
        sl, pts = studymod.StudyLog(st), studymod.Points(st)
        demo.fill(st, sl, pts, "en")
        self.assertTrue(demo.has_data(st, sl))


if __name__ == "__main__":
    unittest.main(verbosity=2)
