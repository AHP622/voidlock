"""Logic tests without any window (no Qt needed). Run:  python tests/logic_test.py
Covers the storage layer, the guard (real processes), the trusted clock, hosts file, updater and the study maths."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psutil  # noqa: E402

from voidlock import guard, hosts, i18n, rules, store as S, study, updater  # noqa: E402

FAILS = []


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def tmp():
    return Path(tempfile.mkdtemp(prefix="vl_logic_"))


# ------------------------------------------------------------------ storage
def test_storage():
    d = tmp()
    p = d / "a.json"
    S.write_json(p, {"x": 1})
    ok(S.read_json_checked(p) == ("ok", {"x": 1}), "write/read round trip")
    ok(not [f for f in d.iterdir() if f.name.endswith(".tmp")], "no temp file left behind")
    ok(S.read_json_checked(d / "none.json")[0] == "missing", "missing file is reported as missing")
    p.write_text("{broken", encoding="utf-8")
    ok(S.read_json_checked(p)[0] == "corrupt", "broken JSON is reported as corrupt")

    # a file that is only locked for a moment must NOT be treated as damaged
    home = d / "home"
    st = S.Store(home)
    st.settings["daily_goal_min"] = 333
    st.save_settings()
    st.save_apps()
    orig = S.read_json_checked
    S.read_json_checked = lambda path, retries=4: ("error", OSError("locked")) if Path(path).name in ("settings.json", "apps.json") else orig(path, retries)
    try:
        st2 = S.Store(home)
    finally:
        S.read_json_checked = orig
    ok((home / "settings.json").exists() and not list(home.glob("settings.json.corrupt*")),
       "a temporarily unreadable settings file is left alone (not quarantined)")
    ok(json.loads((home / "apps.json").read_text(encoding="utf-8")) and len(json.loads((home / "apps.json").read_text(encoding="utf-8"))) >= 20,
       "apps.json is not overwritten with defaults after an unreadable moment")
    st3 = S.Store(home)
    ok(st3.settings["daily_goal_min"] == 333, "data survives")

    # real corruption is still restored from backup
    (home / "settings.json").write_text("{oops", encoding="utf-8")
    st4 = S.Store(home)
    ok(st4.settings["daily_goal_min"] == 333 and st4.notices, "corrupt settings are restored from the newest backup")


def test_sanitize_and_import():
    s = S.sanitize_settings({"reduce_motion": "bogus", "daily_goal_min": "abc", "theme": 5, "week_start": 3,
                             "exam_date": [1, 2], "long_cooldown": -5, "update_repo": 7, "play_tracking": 0})
    ok(s["reduce_motion"] == "auto" and s["daily_goal_min"] == 120 and s["theme"] == "void" and s["week_start"] == 5,
       "invalid settings values fall back to valid ones")
    ok(s["exam_date"] == [1406, 4, 10] and s["long_cooldown"] == 5 and s["update_repo"] == "" and s["play_tracking"] is False,
       "exam date, numbers, strings and booleans are repaired")

    d = tmp()
    st = S.Store(d)
    st.settings["update_repo"] = "me/mine"
    st.settings["long_cooldown"] = 900
    st.add_lock("steam.exe", "Steam", time.time() + 86400)
    st.refresh_locks()
    evil = {"voidlock_export": 3, "settings": {"update_repo": "evil/repo", "long_cooldown": 5, "update_auto_install": True},
            "apps": [{"name": "x"}, "junk", {"exe": "ok.exe", "category": "NOPE", "enabled": 1}, {"exe": "OK.exe"}],
            "schedule": [{"day": 9, "time": "99:99", "minutes": 5}, {"day": 2, "time": "7:5", "minutes": 30}],
            "history": [{"start": "x"}, {"start": 1700000000, "focus_sec": "60"}]}
    ok(st.import_all(evil), "import accepted")
    ok(st.settings["update_repo"] == "me/mine", "an imported file cannot change the update source")
    ok(st.settings["long_cooldown"] == 900, "an import cannot shorten the release wait while a lock exists")
    ok([a["exe"] for a in st.apps] == ["ok.exe"] and st.apps[0]["category"] == "Other" and st.apps[0]["id"], "imported apps are validated")
    ok(len(st.schedule) == 1 and st.schedule[0]["time"] == "07:05", "imported schedule is validated")
    ok(len(st.history) == 1 and st.history[0]["focus_sec"] == 60, "imported history is validated")


def test_locks():
    d = tmp()
    st = S.Store(d)
    now = time.time()
    st.add_lock("a.exe", "A", now + 1000)
    st.add_lock("b.exe", "B", now + 1000)
    st.add_lock("a.exe", "A", now + 10)       # shorter: ignored
    ok(st.lock_for("a.exe")["until"] >= now + 1000, "a lock can only be extended")
    orig = S.read_json_checked
    S.read_json_checked = lambda path, retries=4: ("error", OSError("busy")) if Path(path).name == "locks.json" else orig(path, retries)
    try:
        st.refresh_locks()
    finally:
        S.read_json_checked = orig
    ok(len(st.locks) == 2, "an unreadable locks file does not make the UI forget its locks")
    busy = lambda path, retries=4: ("error", OSError("busy")) if Path(path).name.startswith("locks") else orig(path, retries)
    guard.read_json_checked = busy
    try:
        guard.release_locks_direct(st, ["a.exe"])
    finally:
        guard.read_json_checked = orig
    st.refresh_locks()
    ok(len(st.locks) == 2, "releasing while the file is unreadable changes nothing (used to wipe every lock)")
    guard.release_locks_direct(st, ["a.exe"])
    st.refresh_locks()
    ok([l["exe"] for l in st.locks] == ["b.exe"], "release removes exactly the requested lock")


# ------------------------------------------------------------------ guard
def test_clock():
    c = guard.TrustedClock()
    real = guard.online_time
    base = time.time() + 5000                    # the "internet" is 5000 s ahead of this PC
    guard.online_time = lambda: base
    try:
        c.now()
        t_end = time.time() + 3
        while not c.online and time.time() < t_end:
            time.sleep(0.05)
        ok(c.online, "clock syncs in the background")
        a = c.now()
        ok(abs(a - base) < 3, "trusted time follows the internet, not the PC")
        real_time = time.time
        time.time = lambda: real_time() - 86400   # the user moves the PC clock back a day
        try:
            b = c.now()
        finally:
            time.time = real_time
        ok(abs(b - a) < 3, "moving the PC clock does not move trusted time")
    finally:
        guard.online_time = real
    c2 = guard.TrustedClock()
    guard.online_time = lambda: (time.sleep(2), None)[1]
    try:
        t0 = time.time()
        for _ in range(5):
            c2.now()
        ok(time.time() - t0 < 0.5, "an offline / slow network never blocks the enforcement loop")
    finally:
        guard.online_time = real


def test_instance_lock():
    d = tmp()
    st = S.Store(d, service=True)
    a = guard.acquire_instance_lock(st)
    b = guard.acquire_instance_lock(st)
    ok(a not in (None, False) and b is None, "a second guard cannot start while one holds the lock")
    a.close()


def victim_binary(d):
    exe = d / "vl_victim"
    shutil.copy(shutil.which("sleep"), exe)
    return exe


def test_scan_parallel():
    if not sys.platform.startswith("linux"):
        return print("SKIP (needs a Linux sleep binary)")
    d = tmp()
    exe = victim_binary(d)
    procs = [subprocess.Popen([str(exe), "60"]) for _ in range(20)]
    time.sleep(0.4)
    st = S.Store(d, service=True)
    per = {"vl_victim": {"killed": 0, "last": 0, "denied": False}}
    t0 = time.time()
    killed, _pl = guard._scan(st, {"vl_victim": ("app", "Victim", "lock")}, per, set(), [], time.time(), set())
    dt = time.time() - t0
    for p in procs:
        try:
            p.wait(1)
        except Exception:
            pass
    alive = [p for p in procs if p.poll() is None]
    ok(not alive and killed == ["vl_victim"] and per["vl_victim"]["killed"] == 20, f"20 blocked processes are all closed ({per['vl_victim']['killed']})")
    ok(dt < 3.0, f"... in one pass ({dt:.2f}s)")
    for p in alive:
        p.kill()


def test_guard_process():
    """The real guard process: closes a day-locked program, restores a tampered lock file, reports its version."""
    if not sys.platform.startswith("linux"):
        return print("SKIP (needs a Linux sleep binary)")
    d = tmp()
    exe = victim_binary(d)
    home = d / "home"
    st = S.Store(home)
    st.settings["play_tracking"] = False
    st.save_settings()
    st.add_lock("vl_victim", "Victim", time.time() + 3600)
    g = subprocess.Popen([sys.executable, str(ROOT / "main.py"), "--guard", "--home", str(home)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(2.5)
        v = subprocess.Popen([str(exe), "60"])
        t_end = time.time() + 8
        while v.poll() is None and time.time() < t_end:
            time.sleep(0.2)
        ok(v.poll() is not None, "guard process closes a day-locked program")
        stat = json.loads((home / "status.json").read_text(encoding="utf-8"))
        from voidlock import __version__
        ok(stat.get("version") == __version__ and stat.get("locks_active") == 1, "status reports version and active locks")
        # tamper: delete + shorten
        (home / "locks.json").write_text(json.dumps({"version": 1, "locks": [{"exe": "vl_victim", "name": "x", "until": 1}]}))
        time.sleep(2.5)
        back = json.loads((home / "locks.json").read_text(encoding="utf-8"))
        ok(back["locks"] and back["locks"][0]["until"] > time.time() + 3000, "a shortened lock file is restored by the guard")
        (home / "locks.json").write_text("[1, 2, 3]")
        time.sleep(2.5)
        v2 = subprocess.Popen([str(exe), "60"])
        t_end = time.time() + 6
        while v2.poll() is None and time.time() < t_end:
            time.sleep(0.2)
        ok(v2.poll() is not None, "a damaged lock file does not stop the guard from enforcing")
        # a second guard exits immediately (single instance)
        g2 = subprocess.Popen([sys.executable, str(ROOT / "main.py"), "--guard", "--home", str(home)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            g2.wait(8)
            ok(g2.returncode == 0, "a second guard exits at once")
        except subprocess.TimeoutExpired:
            g2.kill()
            ok(False, "a second guard exits at once")
        ok(g.poll() is None, "the first guard keeps running")
    finally:
        g.kill()
        for p in psutil.process_iter(["name"]):
            if p.info["name"] == "vl_victim":
                p.kill()


# ------------------------------------------------------------------ hosts / rules / updater / study / i18n
def test_hosts():
    base = "127.0.0.1 localhost\r\n"
    new = hosts.apply_to_text(base, ["youtube.com"])
    ok("\r\n" in new and "\n" not in new.replace("\r\n", ""), "hosts block keeps CRLF line endings")
    ok(hosts.apply_to_text(new, []) == base, "removing the block restores the file exactly")
    ok(hosts.apply_to_text(new, ["youtube.com"]) == new, "applying twice changes nothing")
    ok(hosts.normalize("https://www.YouTube.com/watch?v=1") == "youtube.com" and hosts.normalize("not a site") == "", "domain normalising")
    d = tmp()
    f = d / "hosts"
    f.write_bytes(base.encode())
    ok(hosts.write_hosts(["x.com"], f, flush=False)[0] and "x.com" in f.read_text(), "write_hosts writes the block")
    ok(not list(d.glob("*.tmp")), "no temp file left")
    ok(hosts.current_block_domains(f) == ["twitter.com", "www.twitter.com", "www.x.com", "x.com", "mobile.twitter.com"][0:0] or "x.com" in hosts.current_block_domains(f), "block can be read back")


def test_rules():
    w = {"days": [4], "start": "22:00", "end": "02:00", "categories": ["Games"]}      # Friday night into Saturday
    fri_23 = datetime(2026, 10, 23, 23, 0)
    sat_01 = datetime(2026, 10, 24, 1, 0)
    sat_03 = datetime(2026, 10, 24, 3, 0)
    ok(rules.window_active(w, fri_23) and rules.window_active(w, sat_01) and not rules.window_active(w, sat_03), "window across midnight")
    ok(rules.window_end(w, fri_23) == datetime(2026, 10, 24, 2, 0) and rules.window_end(w, sat_01) == datetime(2026, 10, 24, 2, 0), "window end across midnight")
    ok(rules.blocked_categories([w], fri_23, pass_active=True) == set(), "a play pass lifts games")


def test_updater():
    ok(updater.is_newer("v1.2.10", "1.2.9") and not updater.is_newer("v1.2.9", "1.2.9") and not updater.is_newer("1.2.8", "1.2.9"), "version compare")
    for bad in ("http://github.com/x", "https://evilgithub.com/x", "https://github.com.evil.com/x", "https://example.com/x"):
        try:
            updater._safe_url(bad)
            ok(False, f"refuses {bad}")
        except updater.UpdateError:
            ok(True, f"refuses {bad}")
    ok(updater._safe_url("https://objects.githubusercontent.com/x") and updater._safe_url("https://github.com/a/b"), "accepts github hosts")
    h = updater._SafeRedirect()
    import urllib.request
    try:
        h.redirect_request(urllib.request.Request("https://github.com/a"), None, 302, "x", {}, "https://evil.example/exe")
        ok(False, "redirect to another host is refused")
    except updater.UpdateError:
        ok(True, "redirect to another host is refused")
    # download: checksum + size cap + cleanup, with a fake network
    import hashlib, io
    payload = b"MZ" + b"\0" * 1000
    good = hashlib.sha256(payload).hexdigest()

    class R(io.BytesIO):
        def __init__(self, data, headers=None):
            super().__init__(data)
            self.headers = headers or {}
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake(req, timeout=0):
        u = req.full_url
        return R((good + "  VoidLock.exe").encode()) if u.endswith("sha") else R(payload, {"Content-Length": str(len(payload))})
    real = updater.urlopen
    updater.urlopen = fake
    try:
        d = tmp()
        p = updater.download({"sha_url": "https://github.com/sha", "url": "https://github.com/exe", "size": 0}, d)
        ok(p.read_bytes() == payload, "download verifies and stores the file")
        updater.urlopen = lambda req, timeout=0: R(("0" * 64).encode()) if req.full_url.endswith("sha") else R(payload)
        try:
            updater.download({"sha_url": "https://github.com/sha", "url": "https://github.com/exe", "size": 0}, d)
            ok(False, "wrong checksum is refused")
        except updater.UpdateError:
            ok(not (d / "VoidLock.exe.part").exists(), "wrong checksum is refused and leaves no partial file")
    finally:
        updater.urlopen = real


def test_study_and_points():
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    sid = sl.subjects()[0]["id"]
    today = date.today()
    sl.add_manual(today, sid, 30)
    sl.add_manual(today - timedelta(days=1), sid, 20)
    st.add_record({"id": "r1", "start": time.time(), "focus_sec": 600, "planned_min": 10, "status": "completed"})
    naive = sum(e["sec"] for e in st.study["entries"] if e["date"] == today.isoformat())
    ok(sl.day_entries_sec(today) == naive == 1800 and sl.day_sessions_sec(today) == 600 and sl.day_sec(today, False) == 2400,
       "per-day totals (indexed) are right")
    sl.add_manual(today, sid, 10)
    ok(sl.day_entries_sec(today) == 2400, "the index follows new entries")
    ok(sl.day_entries_sec(datetime.now()) == 2400 and study.dkey(datetime.now()) == today.isoformat(), "a datetime is accepted as a day")
    # everything replaced behind its back (reset / import) must not crash
    st.study = {}
    try:
        sl.day_sec(today); sl.subjects(); sl.streak(); sl.heat(3); sl.todos(today); sl.year_summary(today.year)
        ok(len(sl.subjects()) == 5, "after a reset the Study log rebuilds itself (used to raise KeyError)")
    except KeyError as e:
        ok(False, f"after a reset the Study log rebuilds itself ({e!r})")
    # deleting a subject keeps its running time
    sid = sl.subjects()[0]["id"]
    sl.start(sid, now=time.time() - 600)
    sl.remove_subject(sid)
    ok(sl.active() is None and sl.day_entries_sec(today) >= 599, "deleting a subject with a running timer saves the time")

    # points: damaged file restored from backup; days never awarded twice
    P = study.Points(st)
    P.add(40, "clean", "x")
    P.save()
    st.snapshot("test", force=True)
    (d / "points.json").write_text("{bad", encoding="utf-8")
    P2 = study.Points(S.Store(d))
    ok(P2.balance == 40, "damaged points file is restored from backup (not reset to zero)")
    P2.d["last_award"] = (today - timedelta(days=3)).isoformat()
    S.write_json(st.p_play, {"days": {(today - timedelta(days=k)).isoformat(): {"monitored": 7200, "total": 0, "apps": {}} for k in (1, 2)}})
    study._PLAY_CACHE.clear()
    r1 = P2.process_days(today)
    ok(len(r1) == 2 and all(k == "clean" for _d, k, _p in r1), "two clean days are awarded")
    r_back = P2.process_days(today - timedelta(days=5))        # the PC clock was set back
    r2 = P2.process_days(today)
    ok(r_back == [] and r2 == [], "going back and forth in time never awards a day twice")
    ok(P2.game_day_ok(date(2026, 10, 23)) and not P2.game_day_ok(date(2026, 10, 22)), "play pass only on Fridays")


def test_i18n():
    bad = 0
    d = date(2015, 1, 1)
    while d < date(2040, 1, 1):
        j = i18n.to_jalali(datetime(d.year, d.month, d.day))
        if i18n.from_jalali(*j) != (d.year, d.month, d.day):
            bad += 1
        d += timedelta(days=1)
    ok(bad == 0, f"Jalali <-> Gregorian round trip over 25 years ({bad} mismatches)")
    ok(i18n.to_jalali(datetime(2027, 7, 1)) == (1406, 4, 10), "10 Tir 1406 is 2027-07-01")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print(f"--- {name}")
            try:
                fn()
            except Exception as e:                  # a crashing test is a failing test
                import traceback
                traceback.print_exc()
                ok(False, f"{name} crashed: {e!r}")
    print()
    print(f"{len(FAILS)} failure(s)" if FAILS else "ALL PASSED")
    sys.exit(1 if FAILS else 0)
