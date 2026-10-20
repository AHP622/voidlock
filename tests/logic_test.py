"""Logic tests (no Qt needed):  python -m unittest tests.logic_test   (or: python tests/logic_test.py)"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from voidlock import guard, hosts, i18n, rules, study, updater  # noqa: E402
from voidlock.store import Store, read_json, write_json  # noqa: E402


class Tmp(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="vl_test_")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)


class StoreTests(Tmp):
    def test_concurrent_writes_never_fail_or_corrupt(self):
        p = os.path.join(self.home, "x.json")
        errs = []

        def w(n):
            try:
                for i in range(60):
                    write_json(p, {"n": n, "i": i})
            except Exception as e:           # noqa: BLE001
                errs.append(e)
        ts = [threading.Thread(target=w, args=(n,)) for n in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertIn("n", read_json(p))
        self.assertEqual([f for f in os.listdir(self.home) if f.endswith(".tmp")], [])

    def test_empty_app_list_is_kept_not_reset_to_defaults(self):
        Store(self.home)
        write_json(os.path.join(self.home, "apps.json"), [])
        self.assertEqual(Store(self.home).apps, [])

    def test_missing_app_file_gets_defaults(self):
        self.assertGreater(len(Store(self.home).apps), 5)

    def test_corrupt_file_restored_from_backup(self):
        s = Store(self.home)
        s.snapshot("t", force=True)
        open(os.path.join(self.home, "apps.json"), "w").write("{not json")
        s2 = Store(self.home)
        self.assertGreater(len(s2.apps), 5)
        self.assertTrue(any("apps.json" in n for n in s2.notices))

    def test_import_rejects_malformed_entries(self):
        s = Store(self.home)
        before = len(s.apps)
        ok = s.import_all({"voidlock_export": 3, "apps": [{"oops": 1}, "str", 5],
                           "history": [1, {"start": 1}], "schedule": [{"x": 1}], "presets": [{}]})
        self.assertTrue(ok)
        self.assertEqual(len(s.apps), before)          # nothing valid -> unchanged
        self.assertEqual(s.history, [{"start": 1}])
        self.assertEqual(s.schedule, [])
        self.assertTrue(all("name" in p for p in s.presets))

    def test_locks_can_only_grow(self):
        s = Store(self.home)
        s.add_lock("a.exe", "A", time.time() + 1000)
        s.add_lock("a.exe", "A", time.time() + 10)
        self.assertGreater(s.lock_for("a.exe")["until"], time.time() + 900)

    def test_trusted_now_uses_guard_offset(self):
        s = Store(self.home)
        write_json(s.p_status, {"clock_online": True, "clock_offset": 3600.0, "heartbeat": time.time()})
        self.assertAlmostEqual(s.trusted_now(), time.time() + 3600, delta=2)
        s2 = Store(self.home)
        write_json(s2.p_status, {"clock_online": True, "clock_offset": 3600.0, "heartbeat": time.time() - 999})
        self.assertAlmostEqual(s2.trusted_now(), time.time(), delta=2)      # stale status is ignored


class RulesTests(unittest.TestCase):
    def test_next_change_matches_brute_force(self):
        import random
        random.seed(11)

        def brute(ws, dt):
            cur = bool(rules.active_windows(ws, dt))
            t = dt.replace(second=0, microsecond=0)
            for i in range(1, 8 * 24 * 60 + 1):
                t2 = t + timedelta(minutes=i)
                if bool(rules.active_windows(ws, t2)) != cur:
                    return t2
        for _ in range(120):
            ws = [{"id": str(k), "start": f"{random.randint(0, 23):02d}:{random.choice([0, 30]):02d}",
                   "end": f"{random.randint(0, 23):02d}:{random.choice([0, 30]):02d}",
                   "days": random.sample(range(7), random.randint(0, 7)), "enabled": True, "categories": ["Games"]}
                  for k in range(random.randint(0, 3))]
            dt = datetime(2026, 10, 20) + timedelta(minutes=random.randint(0, 20000), seconds=random.randint(0, 59))
            self.assertEqual(rules.next_change(ws, dt), brute(ws, dt))

    def test_window_crossing_midnight(self):
        w = {"start": "22:00", "end": "02:00", "days": [4]}            # Friday night
        self.assertTrue(rules.window_active(w, datetime(2026, 10, 23, 23, 0)))     # Fri 23:00
        self.assertTrue(rules.window_active(w, datetime(2026, 10, 24, 1, 0)))      # Sat 01:00
        self.assertFalse(rules.window_active(w, datetime(2026, 10, 24, 3, 0)))


class JalaliTests(unittest.TestCase):
    NOWRUZ = {1399: (2020, 3, 20), 1400: (2021, 3, 21), 1403: (2024, 3, 20), 1404: (2025, 3, 21), 1405: (2026, 3, 21),
              1406: (2027, 3, 21), 1407: (2028, 3, 20), 1408: (2029, 3, 20), 1409: (2030, 3, 21)}

    def test_nowruz(self):
        for y, g in self.NOWRUZ.items():
            self.assertEqual(i18n.from_jalali(y, 1, 1), g)
            self.assertEqual(i18n.to_jalali(datetime(*g)), (y, 1, 1))

    def test_leap_years(self):
        self.assertEqual([y for y in range(1398, 1420) if i18n.is_jalali_leap(y)], [1399, 1403, 1408, 1412, 1416])

    def test_round_trip(self):
        d = date(2000, 1, 1)
        while d < date(2060, 1, 1):
            self.assertEqual(i18n.from_jalali(*i18n.to_jalali(datetime(d.year, d.month, d.day))), (d.year, d.month, d.day))
            d += timedelta(days=1)

    def test_exam_date(self):
        self.assertEqual(i18n.from_jalali(1406, 4, 10), (2027, 7, 1))

    def test_invalid(self):
        for bad in ((1406, 13, 1), (1406, 12, 30), (1406, 7, 31), (1406, 1, 0)):
            with self.assertRaises(ValueError):
                i18n.from_jalali(*bad)


class StudyTests(Tmp):
    def test_dkey_accepts_datetime(self):
        self.assertEqual(study.dkey(datetime(2026, 10, 20, 13, 5)), "2026-10-20")
        self.assertEqual(study.dkey(date(2026, 10, 20)), "2026-10-20")
        self.assertEqual(study.dkey("2026-10-20"), "2026-10-20")

    def test_friday_rule_uses_trusted_time(self):
        s = Store(self.home)
        s.settings["game_friday_only"] = True
        P = study.Points(s)
        fri, thu = date(2026, 10, 23), date(2026, 10, 22)
        self.assertTrue(P.game_day_ok(fri))
        self.assertFalse(P.game_day_ok(thu))

    def test_stopwatch_split_over_midnight(self):
        s = Store(self.home)
        log = study.StudyLog(s)
        sid = log.subjects()[0]["id"]
        t0 = datetime(2026, 10, 20, 23, 50).timestamp()
        log.start(sid, t0)
        self.assertEqual(log.stop(t0 + 1200), 1200)
        self.assertEqual(log.day_entries_sec("2026-10-20"), 600)
        self.assertEqual(log.day_entries_sec("2026-10-21"), 600)

    def test_stopwatch_stopped_at_sleep_time(self):
        s = Store(self.home)
        log = study.StudyLog(s)
        sid = log.subjects()[0]["id"]
        t0 = time.time() - 3 * 3600
        log.start(sid, t0)
        self.assertEqual(log.stop(t0 + 600), 600)       # what the app does on wake-up: stop at the last tick


class HostsTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(hosts.normalize("https://www.YouTube.com/watch?v=1"), "youtube.com")
        self.assertEqual(hosts.normalize("evil.com\n0.0.0.0 bank.com"), "")
        self.assertEqual(hosts.normalize("localhost"), "")

    def test_apply_and_remove_block(self):
        base = "127.0.0.1 localhost\n"
        t = hosts.apply_to_text(base, ["youtube.com"])
        self.assertIn("0.0.0.0 youtube.com", t)
        self.assertTrue(t.startswith(base))
        self.assertEqual(hosts.apply_to_text(t, []), base)


class UpdaterTests(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(updater.is_newer("v1.2.10", "1.2.9"))
        self.assertFalse(updater.is_newer("v1.2.9", "1.2.9"))
        self.assertFalse(updater.is_newer("v1.2.8", "1.2.9"))

    def test_url_policy(self):
        for u in ("https://github.com/a/b", "https://objects.githubusercontent.com/x"):
            updater._safe_url(u)
        for u in ("http://github.com/a", "https://evilgithub.com/a", "https://github.com.evil.io/a"):
            with self.assertRaises(updater.UpdateError):
                updater._safe_url(u)

    def test_redirect_is_checked(self):
        h = updater._SafeRedirect()
        with self.assertRaises(updater.UpdateError):
            h.redirect_request(None, None, 302, "Found", {}, "https://evil.example/VoidLock.exe")


class GuardTests(Tmp):
    def test_clock_never_blocks_when_offline(self):
        c = guard.TrustedClock(fetch=lambda: (time.sleep(2), None)[1])
        t = time.time()
        c.now()
        self.assertLess(time.time() - t, 0.3)

    def test_clock_offset(self):
        c = guard.TrustedClock(fetch=lambda: time.time() + 100)
        c.now()
        time.sleep(0.3)
        self.assertAlmostEqual(c.now() - time.time(), 100, delta=2)
        self.assertTrue(c.online)

    def test_single_instance_lock(self):
        code = ("import sys,time;sys.path.insert(0,%r);from voidlock import guard;"
                "print(guard.acquire_guard_lock(%r),flush=True);time.sleep(2)" % (ROOT, self.home))
        p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        self.addCleanup(p.kill)
        self.assertEqual(p.stdout.readline().strip(), "True")
        self.assertFalse(guard.acquire_guard_lock(self.home))
        p.wait()
        self.assertTrue(guard.acquire_guard_lock(self.home))

    @unittest.skipIf(sys.platform == "win32", "uses `sleep` as the blocked program")
    def test_guard_blocks_restores_locks_and_is_single(self):
        write_json(os.path.join(self.home, "settings.json"), {"play_tracking": False})
        write_json(os.path.join(self.home, "apps.json"), [])
        victim = subprocess.Popen(["sleep", "300"])
        self.addCleanup(victim.kill)
        write_json(os.path.join(self.home, "session.json"), {
            "state": "running", "session_id": "s1", "started_at": time.time(), "ends_at": time.time() + 600,
            "remaining": 600, "planned_sec": 600, "blocked": [{"exe": "sleep", "name": "Sleep", "kind": "app"}]})
        env = dict(os.environ, PYTHONPATH=ROOT)
        gs = [subprocess.Popen([sys.executable, os.path.join(ROOT, "main.py"), "--guard", "--home", self.home], env=env)
              for _ in range(2)]
        for g in gs:
            self.addCleanup(g.kill)
        time.sleep(3.5)
        self.assertIsNotNone(victim.poll(), "blocked program was not terminated")
        self.assertEqual(len([g for g in gs if g.poll() is None]), 1, "exactly one guard must survive")
        v2 = subprocess.Popen(["sleep", "300"])
        self.addCleanup(v2.kill)
        write_json(os.path.join(self.home, "session.json"), {"state": "idle"})
        write_json(os.path.join(self.home, "locks.json"), {"version": 1, "locks": [
            {"id": "x", "exe": "sleep", "name": "Sleep", "until": time.time() + 3600, "created": time.time()}]})
        time.sleep(3)
        self.assertIsNotNone(v2.poll(), "day-locked program was not terminated")
        write_json(os.path.join(self.home, "locks.json"), {"version": 1, "locks": []})      # tamper
        time.sleep(3)
        self.assertEqual(len(read_json(os.path.join(self.home, "locks.json"))["locks"]), 1, "lock was not restored")

    def test_stop_never_kills_a_foreign_process(self):
        s = Store(self.home, service=True)
        other = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
        self.addCleanup(other.kill)
        write_json(s.p_status, {"pid": other.pid, "heartbeat": time.time()})
        guard.GuardClient(s).stop()
        time.sleep(0.3)
        self.assertIsNone(other.poll())


if __name__ == "__main__":
    unittest.main(verbosity=2)
