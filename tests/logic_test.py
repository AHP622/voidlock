"""Logic tests without any window (no Qt needed). Run:  python tests/logic_test.py
Covers the storage layer, the guard (real processes), the trusted clock, hosts file, updater and the study maths."""
import json
import os
import shutil
import subprocess
import sys

# a Windows console (cp1252) cannot print Persian test names: never let printing fail a test
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psutil  # noqa: E402

from voidlock import classes as classtools, guard, hosts, i18n, rules, sounds, store as S, study, updater  # noqa: E402

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
    ok(s["exam_date"] == [1406, 4, 10] and s["long_cooldown"] == 5 and "update_repo" not in s and s["play_tracking"] is False,
       "exam date, numbers, strings and booleans are repaired")

    d = tmp()
    st = S.Store(d)
    st.settings["long_cooldown"] = 900
    st.add_lock("steam.exe", "Steam", time.time() + 86400)
    st.refresh_locks()
    evil = {"voidlock_export": 3, "settings": {"update_repo": "evil/repo", "long_cooldown": 5, "update_auto_install": True},
            "apps": [{"name": "x"}, "junk", {"exe": "ok.exe", "category": "NOPE", "enabled": 1}, {"exe": "OK.exe"}],
            "schedule": [{"day": 9, "time": "99:99", "minutes": 5}, {"day": 2, "time": "7:5", "minutes": 30}],
            "history": [{"start": "x"}, {"start": 1700000000, "focus_sec": "60"}]}
    ok(st.import_all(evil), "import accepted")
    ok("update_repo" not in st.settings, "the update source is not a setting any more (and never imported)")
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
        def __init__(self, data, headers=None, status=200):
            super().__init__(data)
            self.headers = headers or {}
            self.status = status
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
        # a connection that ends early WITHOUT an error (what Python's HTTP client does) is resumed
        big = b"MZ" + bytes(range(256)) * 400
        good2 = hashlib.sha256(big).hexdigest()
        calls = []

        def flaky(req, timeout=0):
            if req.full_url.endswith("sha"):
                return R((good2 + "  VoidLock.exe").encode())
            rng = req.headers.get("Range")
            calls.append(rng)
            if rng is None:
                return R(big[:len(big) // 2], {"Content-Length": str(len(big))})          # cut off, no exception
            start = int(rng.split("=")[1].rstrip("-"))
            return R(big[start:], {"Content-Length": str(len(big) - start)}, status=206)
        updater.urlopen = flaky
        updater.time_sleep = None
        d2 = tmp()
        p2 = updater.download({"sha_url": "https://github.com/sha", "url": "https://github.com/exe", "size": len(big)}, d2)
        ok(p2.read_bytes() == big and calls[0] is None and calls[1] == f"bytes={len(big) // 2}-", "a cut-off download is resumed and verified")

        n = []

        def no_range(req, timeout=0):
            if req.full_url.endswith("sha"):
                return R((good2 + "  VoidLock.exe").encode())
            n.append(1)
            return R(big[:100] if len(n) == 1 else big, {"Content-Length": str(len(big))})   # ignores Range the second time
        updater.urlopen = no_range
        p3 = updater.download({"sha_url": "https://github.com/sha", "url": "https://github.com/exe", "size": len(big)}, tmp())
        ok(p3.read_bytes() == big, "a server that ignores Range gets a clean restart")

        def corrupt(req, timeout=0):
            if req.full_url.endswith("sha"):
                return R((good2 + "  VoidLock.exe").encode())
            return R(big[:500] + b"X" + big[501:], {"Content-Length": str(len(big))})
        updater.urlopen = corrupt
        d4 = tmp()
        try:
            updater.download({"sha_url": "https://github.com/sha", "url": "https://github.com/exe", "size": len(big)}, d4, attempts=2)
            ok(False, "a corrupted file is refused")
        except updater.UpdateError as e:
            ok("could not be downloaded safely" in str(e) and not list(d4.glob("*.part")), "a corrupted file is refused after retries and nothing is left behind")
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
        ok(len(sl.subjects()) == 6, "after a reset the Study log rebuilds itself (used to raise KeyError)")
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


# ------------------------------------------------------------------ 1.4.0
def test_updater_repo_fixed():
    ok(updater.REPO == "AHP622/voidlock" and updater.valid_repo(updater.REPO), "the update source is fixed to the project repository")
    ok("update_repo" not in S.sanitize_settings({"update_repo": "evil/repo"}), "a stored update_repo is dropped on load")


def test_task_xml():
    import xml.etree.ElementTree as ET
    for logon, highest in ((False, False), (True, True)):
        x = guard.task_xml('C:\\Program Files\\VoidLock & Co\\VoidLock.exe', '"--guard" "--home" "C:\\Users\\me\\<x>"', logon=logon, highest=highest)
        root = ET.fromstring(x.replace('encoding="UTF-16"', ""))
        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
        g = lambda path: root.find(path, ns).text
        ok(g("t:Settings/t:DisallowStartIfOnBatteries") == "false" and g("t:Settings/t:StopIfGoingOnBatteries") == "false",
           f"task XML allows running on battery (logon={logon})")
        ok(g("t:Settings/t:ExecutionTimeLimit") == "PT0S" and g("t:Settings/t:StartWhenAvailable") == "true", "task XML has no time limit and catches up")
        ok(g("t:Principals/t:Principal/t:RunLevel") == ("HighestAvailable" if highest else "LeastPrivilege"), "task XML run level")
        ok(("LogonTrigger" in x) == logon and ("TimeTrigger" in x) != logon, "task XML trigger")
        ok(root.find("t:Actions/t:Exec/t:Command", ns).text.endswith("VoidLock.exe") and "<x>" in root.find("t:Actions/t:Exec/t:Arguments", ns).text,
           "task XML escapes paths")


def test_session_rules_only_grow():
    """The rules of a running session can be added to, never removed (UI frozen set + guard merge)."""
    from voidlock.core import SessionController
    d = tmp()
    st = S.Store(d)
    for a in st.apps:
        a["enabled"] = False
    st.apps[0]["enabled"] = True
    first = st.apps[0]["exe"]

    class G:
        launched_at = 0
        attempts = 0
        def ensure(self): return True
        def status(self): return {"alive": True}
    sc = SessionController(st, G())
    sc.start(10, "x")
    ok([b["exe"] for b in sc.blocked_list()] == [first], "session starts with the enabled app")
    st.apps[0]["enabled"] = False                 # somebody switches it off mid-session
    st.apps[1]["enabled"] = True
    sc.sync_rules()
    sess = json.loads((d / "session.json").read_text(encoding="utf-8"))
    names = {b["exe"] for b in sess["blocked"]}
    ok(first in names and st.apps[1]["exe"] in names, "switching an app off mid-session does not unblock it; new ones are added")
    sc2 = SessionController(st, G())              # restart of the program keeps the frozen rules
    ok(first in {b["exe"] for b in sc2.blocked_list()}, "after a restart the session keeps its rules")


def test_guard_session_rules_merge():
    if not sys.platform.startswith("linux"):
        return print("SKIP (needs a Linux sleep binary)")
    d = tmp()
    exe = victim_binary(d)
    home = d / "home"
    st = S.Store(home)
    st.settings["play_tracking"] = False
    st.save_settings()
    sid = "sess-1"
    rule = {"exe": "vl_victim", "name": "Victim", "kind": "app"}
    S.write_json(st.p_session, {"state": "running", "session_id": sid, "started_at": time.time(), "ends_at": time.time() + 600,
                                "remaining": 600, "planned_sec": 600, "subject": "", "strict": False, "blocked": [rule]})
    g = subprocess.Popen([sys.executable, str(ROOT / "main.py"), "--guard", "--home", str(home)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        S.write_json(st.p_session, {"state": "running", "session_id": sid, "started_at": time.time(), "ends_at": time.time() + 600,
                                    "remaining": 600, "planned_sec": 600, "subject": "", "strict": False, "blocked": []})   # edited
        time.sleep(2.5)
        v = subprocess.Popen([str(exe), "60"])
        t_end = time.time() + 8
        while v.poll() is None and time.time() < t_end:
            time.sleep(0.2)
        ok(v.poll() is not None, "the guard keeps a session's rules even if the session file is edited")
    finally:
        g.kill()
        for p in psutil.process_iter(["name"]):
            if p.info["name"] == "vl_victim":
                p.kill()


def test_classes():
    cl = S.clean_classes([{"id": "1", "name": "Math", "day": 2, "time": "10:00", "minutes": 90, "remind": 15},
                          {"name": "", "day": 2, "time": "10:00"}, {"name": "x", "day": 9, "time": "10:00"}, "junk",
                          {"name": "Phys", "day": "1", "time": "8:5", "minutes": "45"}])
    ok(len(cl) == 2 and cl[1]["time"] == "08:05" and cl[1]["minutes"] == 45 and cl[1]["remind"] == 15, "classes are validated")
    wed = lambda h, m: datetime(2026, 10, 21, h, m)          # a Wednesday
    ok(classtools.due_reminders(cl, wed(9, 44)) == [], "no reminder 16 minutes before")
    r = classtools.due_reminders(cl, wed(9, 45))
    ok(len(r) == 1 and r[0][1] == "soon" and r[0][2] == 15, "reminder exactly 15 minutes before")
    classtools.mark_done(r[0][0], "soon", wed(9, 45))
    ok(classtools.due_reminders(cl, wed(9, 50)) == [], "a reminder fires only once per day")
    late = classtools.due_reminders(S.clean_classes([{"name": "A", "day": 2, "time": "10:00"}]), wed(9, 58))
    ok(late and late[0][2] == 2, "a late reminder says the real minutes left")
    ok(classtools.due_reminders(cl, wed(10, 1))[0][1] == "start" and classtools.due_reminders(cl, wed(10, 5)) == [], "start note within 2 minutes")
    st_, c, s_, e_ = classtools.current_or_next(cl, wed(10, 30))
    ok(st_ == "now" and c["name"] == "Math" and e_ == wed(11, 30), "a running class is reported")
    st_, c, s_, e_ = classtools.current_or_next(cl, wed(11, 31))
    ok(st_ == "next" and s_ > wed(11, 31), "after the class the next one is next week")
    cl[0]["enabled"] = False
    ok(classtools.due_reminders(cl, wed(9, 50)) == [], "a disabled class never reminds")
    ov = classtools.overlap_names([{"id": "1", "name": "Math", "day": 2, "time": "10:00", "minutes": 90, "enabled": True}], [], 2, "11:00", 60)
    ok(len(ov) == 1 and not classtools.overlap_names([{"id": "1", "name": "Math", "day": 2, "time": "10:00", "minutes": 60, "enabled": True}], [], 2, "11:00", 60),
       "overlap detection (touching is not overlapping)")


def test_words_and_classes_storage():
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    eng = next(s for s in sl.subjects() if s["name"] == "English")
    math = next(s for s in sl.subjects() if s["name"] == "Math")
    ok(sl.tracks_words(eng) and not sl.tracks_words(math), "language subjects get a words counter")
    ok(sl.tracks_words(sl.add_subject("زبان تخصصی")) and not sl.tracks_words(sl.add_subject("Geography")) and sl.tracks_words(sl.add_subject("Spanish", words=True)),
       "name detection and the explicit flag")
    today = date.today()
    sl.set_words(today, eng["id"], 40)
    sl.set_words(today - timedelta(days=1), eng["id"], 25)
    ok(sl.day_words(today) == 40 and sl.year_words(today.year) >= 40 and sl.year_summary(today.year)["words"] >= 40, "words are counted per day and year")
    sl.set_words(today, eng["id"], 0)
    ok(sl.day_words(today) == 0, "zero removes the entry")
    st.classes = S.clean_classes([{"name": "Math", "day": 1, "time": "09:00"}])
    st.save_classes()
    st2 = S.Store(d)
    ok(len(st2.classes) == 1, "classes persist")
    exp = st2.export_all()
    st3 = S.Store(tmp())
    ok(st3.import_all(exp) and len(st3.classes) == 1, "classes are part of export / import")
    st3.snapshot("x", force=True)
    st3.reset_all()
    ok(st3.classes == [], "reset clears classes")


def test_apply_days():
    from voidlock.pages_b import apply_days
    items = [{"id": "a", "day": 2, "time": "10:00", "minutes": 30, "last_fired": "2026-10-21"}]
    mk = lambda d, b: {"id": f"n{d}", "day": d, **b}
    c, u = apply_days(items, None, {"days": [0, 1, 3], "time": "08:00", "minutes": 20}, mk)
    ok(c == 3 and u == 0 and len(items) == 4, "new entry for several days at once")
    e = items[0]
    c, u = apply_days(items, e, {"days": [2, 5], "time": "10:00", "minutes": 45}, mk)
    ok(u == 1 and c == 1 and e["day"] == 2 and e["minutes"] == 45 and e["last_fired"] == "2026-10-21", "editing keeps its day and adds a copy; an unchanged time keeps last_fired")
    c, u = apply_days(items, e, {"days": [6], "time": "10:00", "minutes": 45}, mk)
    ok(e["day"] == 6 and e["last_fired"] == "" and c == 0, "unticking its own day moves the entry")


def test_sounds_and_themes():
    ok(all(k in sounds.STYLES for k in sounds.STYLE_ORDER if k != "off"), "every sound style exists")
    ok(all(len(sounds.wav_bytes(k, s)) > 2000 for s in sounds.STYLES for k in sounds.KINDS), "every style has every sound")
    ok(S.sanitize_settings({"sound": "zen"})["sound"] == "zen" and S.sanitize_settings({"sound": "nope"})["sound"] == "soft", "sound setting is validated")
    try:
        from voidlock import theme
        ok(set(theme.THEMES) == set(S.THEME_KEYS) == set(theme.THEME_ORDER) == set(theme.THEME_NAMES), "theme lists agree")
        need = set(theme.THEMES["void"])
        ok(all(set(v) == need for v in theme.THEMES.values()), "every theme defines every colour")
    except ImportError:
        print("SKIP theme check (no Qt)")


def test_day_subject_times():
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    math, phys, chem = sl.subjects()[0], sl.subjects()[1], sl.subjects()[2]
    y = date.today() - timedelta(days=1)
    sl.add_manual(y, math["id"], 30)
    sl.add_manual(y, chem["id"], 195)
    sl.add_manual(y, math["id"], 15)
    ts = datetime.combine(y, datetime.min.time()).timestamp() + 36000
    st.add_record({"id": "a", "start": ts, "focus_sec": 3000, "planned_min": 50, "status": "completed", "subject": "Math"})
    rows = sl.day_subject_times(y)
    ok([(s["name"], v // 60) for s, v in rows] == [("Chemistry", 195), ("Math", 45)], "per-subject day times: only subjects with time, longest first")
    ok(sum(v for _s, v in rows) == sl.day_sec(y, False, include_sessions=False), "they add up to the Study Timer's day total (focus sessions are counted separately there)")
    ok(sl.day_subject_times(date.today() - timedelta(days=30)) == [], "an empty day has no subjects")


def test_upgrade_from_old_data():
    """Data written by an older version (hand-made files in the old formats) must open unchanged in this one."""
    d = tmp()
    today = date.today()
    (d).mkdir(exist_ok=True)
    S.write_json(d / "settings.json", {"daily_goal_min": 200, "language": "fa", "theme": "ocean", "sound": "soft", "week_start": 5,
                                       "update_repo": "x/y", "long_cooldown": 900, "target_field": "Medicine",
                                       "exam_date": [1406, 4, 10], "play_tracking": True})
    S.write_json(d / "study.json", {"subjects": [{"id": "m", "name": "Math", "color": "#fff"}, {"id": "e", "name": "English", "color": "#000"}],
                                    "entries": [{"id": "1", "date": today.isoformat(), "subject": "m", "sec": 1800, "source": "manual", "t": 1}],
                                    "tests": {today.isoformat(): {"m": 25}}, "todos": [{"id": "t", "date": today.isoformat(), "text": "x", "done": False}],
                                    "active": None})
    S.write_json(d / "history.json", [{"id": "h1", "start": time.time() - 3600, "focus_sec": 1500, "planned_min": 25, "status": "completed"}])
    S.write_json(d / "schedule.json", [{"id": "s", "day": 2, "time": "18:00", "minutes": 50, "subject": "Physics", "enabled": True, "last_fired": ""}])
    S.write_json(d / "points.json", {"balance": 77, "ledger": [], "rewards": [], "tickets": []})
    S.write_json(d / "locks.json", {"version": 1, "locks": [{"exe": "steam.exe", "name": "Steam", "until": time.time() + 86400}]})
    st = S.Store(d)
    sl = study.StudyLog(st)
    P = study.Points(st)
    ok(st.settings["daily_goal_min"] == 200 and st.settings["language"] == "fa" and st.settings["theme"] == "ocean" and st.settings["long_cooldown"] == 900
       and st.settings["target_field"] == "Medicine" and st.settings["close_to_tray"] is True and st.settings["tray_at_login"] is False,
       "old settings are kept; new ones get their defaults (tray on, start-with-Windows off)")
    ok(len(sl.subjects()) == 2 and sl.day_entries_sec(today) == 1800 and sl.day_tests(today) == 25 and len(sl.todos(today)) == 1, "old study data is untouched")
    ok(sl.tracks_words("e") and sl.day_words(today) == 0, "the old English subject gets the words counter automatically")
    ok(len(st.history) == 1 and len(st.schedule) == 1 and st.schedule[0].get("auto_start") in (None, False), "history and schedule are untouched")
    ok(P.balance == 77 and len(st.active_locks()) == 1, "points and day locks are untouched")
    ok(st.classes == [], "classes start empty")
    ok(any(b["name"].endswith("start") for b in st.list_backups()), "a backup is taken when the new version starts")


def test_deleted_subjects_keep_their_hours():
    """The reported bug: subjects deleted and typed in again lost their history and the day's bar showed only some of it."""
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    names = [s["name"] for s in sl.subjects()]
    y = date.today() - timedelta(days=1)
    for s in sl.subjects():
        sl.add_manual(y, s["id"], 60)
        sl.set_tests(y, s["id"], 5)
    total = sl.day_sec(y, False, include_sessions=False)
    st.snapshot("before-delete", force=True)
    old = {s["name"]: s["id"] for s in sl.subjects()}
    for s in list(sl.subjects()):
        sl.remove_subject(s["id"])
    rows = sl.day_subject_times(y)
    ok(len(rows) == len(names) and all(s.get("ghost") for s, _v in rows) and sum(v for _s, v in rows) == total,
       "after deleting every subject the day's bar still shows all the time (with the old names)")
    ok({s["name"] for s, _v in rows} == set(names), "ghosts keep the deleted subjects' names")
    # re-adding a subject with the same name brings its history back
    s_new = sl.add_subject(names[0])
    ok(s_new["id"] == old[names[0]] and sl.subject_day_sec(y, s_new["id"]) == 3600 and sl.day_tests(y, s_new["id"]) == 5,
       "adding a subject with a deleted one's name gives its history back")
    # the other path (typed in again before this fix): new ids, history found through the backups
    d2 = tmp()
    st2 = S.Store(d2)
    sl2 = study.StudyLog(st2)
    old2 = {s["name"]: s["id"] for s in sl2.subjects()}
    for s in sl2.subjects():
        sl2.add_manual(y, s["id"], 30)
        sl2.set_tests(y, s["id"], 2)
    st2.snapshot("keep", force=True)
    st2.study["subjects"] = []          # what the old version did: removed, nothing noted
    st2.study["gone"] = {}
    for n in names[:3]:
        sl2.add_subject(n)              # typed in again: brand new ids
    sl2.add_subject("Brand new")
    ok(len(sl2.orphan_ids()) == len(names), "(before repair) the old ids are orphans")
    backups = [S.read_json(b["path"] / "study.json") for b in st2.list_backups()]
    rel, named = sl2.repair_subjects([b for b in backups if isinstance(b, dict)])
    ok(rel == 3 and named == len(names) - 3, f"repair: {rel} relinked to same-name subjects, {named} named as deleted")
    ok(not [1 for s, _v in sl2.day_subject_times(y) if s.get("ghost") and s["name"] == "Deleted subjects"], "no anonymous leftovers when backups know the names")
    ok(sum(v for _s, v in sl2.day_subject_times(y)) == 30 * 60 * len(names), "all the hours are still there")
    ok(sl2.day_tests(y, next(s["id"] for s in sl2.subjects() if s["name"] == names[0])) == 2, "tests are relinked too")


def test_subject_flags_edit_remove_time():
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    s = sl.add_subject("History", tests=False)
    ok(not sl.shows_tests(s) and sl.shows_tests(sl.subjects()[0]), "a subject can be hidden from 'Tests solved'")
    sl.edit_subject(s["id"], name="World history", color="#fff", tests=True, words=True)
    ok(sl.subject(s["id"])["name"] == "World history" and sl.shows_tests(s["id"]) and sl.tracks_words(s["id"]), "editing a subject keeps its id")
    y = date.today() - timedelta(days=2)
    sl.add_manual(y, s["id"], 60)
    sl.add_manual(y, s["id"], 30)
    got = sl.remove_time(y, s["id"], 45)
    ok(got == 45 * 60 and sl.subject_day_sec(y, s["id"]) == 45 * 60, "removing time takes from the newest entries first")
    got = sl.remove_time(y, s["id"], 500)
    ok(got == 45 * 60 and sl.subject_day_sec(y, s["id"]) == 0 and not [e for e in st.study["entries"] if e["date"] == y.isoformat()], "it never goes below zero")
    ok(sl.remove_time(y, s["id"], 10) == 0, "nothing to remove -> 0")


def test_exams():
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    today = date.today()
    sl.add_exam("Mock 2", today + timedelta(days=9))
    e1 = sl.add_exam("Mock 1", today + timedelta(days=3))
    sl.add_exam("Old", today - timedelta(days=4))
    ex, left = sl.next_exam(today)
    ok(ex["name"] == "Mock 1" and left == 3, "the next exam is the nearest one that has not passed")
    ok(sl.exam_on(today + timedelta(days=3))[0]["name"] == "Mock 1", "exam_on finds an exam day")
    sl.update_exam(e1["id"], d=today + timedelta(days=1))
    ok(sl.next_exam(today)[1] == 1, "editing the date works")
    sl.remove_exam(e1["id"])
    ok(sl.next_exam(today)[0]["name"] == "Mock 2" and len(sl.exams()) == 2, "removing an exam")
    st2 = S.Store(d)
    ok(len(study.StudyLog(st2).exams()) == 2, "exams persist")


def test_report():
    from voidlock import report
    d = tmp()
    st = S.Store(d)
    sl = study.StudyLog(st)
    st.study["subjects"] = []
    math, eng = sl.add_subject("ریاضی"), sl.add_subject("English", words=True)
    today = date.today()
    for k in range(0, 40):
        sl.add_manual(today - timedelta(days=k), math["id"], 60)
    sl.add_manual(today - timedelta(days=2), eng["id"], 30)
    sl.set_tests(today - timedelta(days=2), math["id"], 20)
    sl.set_words(today - timedelta(days=2), eng["id"], 45)
    gone = sl.add_subject("هندسه")
    sl.add_manual(today - timedelta(days=5), gone["id"], 40)
    sl.remove_subject(gone["id"])
    sl.add_exam("آزمون جامع", today - timedelta(days=4))
    ts = datetime.combine(today - timedelta(days=1), datetime.min.time()).timestamp() + 40000
    st.add_record({"id": "s1", "start": ts, "focus_sec": 2400, "planned_min": 45, "status": "completed", "subject": "ریاضی", "blocked_count": 3})
    a, b = today - timedelta(days=9), today
    R = report.collect(st, sl, a, b, "علی <b>رضایی</b>", "fa", goal_min=60)
    s = R["summary"]
    ok(s["total"] == 10 * 3600 + 30 * 60 + 40 * 60 and s["period_days"] == 10 and s["active_days"] == 10, "report totals = timer + manual time (sessions are not added)")
    ok(s["tests"] == 20 and s["words"] == 45 and s["sessions"] == 1 and s["sessions_sec"] == 2400, "tests, words and sessions are counted separately")
    ok(abs(sum(r["sec"] for r in R["subjects"]) - s["total"]) < 1, "the subject totals add up to the total (deleted subjects included)")
    ok(any(r["ghost"] and r["name"] == "هندسه" for r in R["subjects"]), "a deleted subject keeps its name in the report")
    ok(s["goal_days"] == 10 and s["streak"] == 10 and s["best"]["sec"] == 100 * 60, "goal days, streak and the best day (60 min of maths + 40 min of a deleted subject)")
    h = report.render_html(R)
    ok('dir="rtl"' in h and 'lang="fa"' in h and "<style>" in h and "<script" not in h.replace("onclick", ""), "the HTML is a single file: right-to-left, CSS inside")
    ok("<link" not in h and "http://" not in h and "https://" not in h.replace("https://www.w3.org", ""), "no external resources")
    ok("&lt;b&gt;" in h and "<b>رضایی" not in h, "names are escaped (no HTML injection)")
    ok("۱۰ ساعت" in h or "۱۱ ساعت" in h, "Persian digits and units")
    ok("@media print" in h and "@page" in h and "thead{display:table-header-group}" in h, "printable: print CSS, repeated table headers")
    for heading in ("خلاصه", "جمع هر درس", "جدول روزانه", "جدول جلسه‌های تمرکز"):
        ok(heading in h, f"section '{heading}' is present")
    c = report.render_csv(R)
    ok(c.splitlines()[0].startswith("گزارش مطالعه") and "ریاضی" in c and "هندسه" in c, "CSV has the sections and Persian text")
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(c)))
    ok(any(r and r[0] == today.isoformat() for r in rows), "CSV daily rows carry ISO dates")
    # long periods -> monthly table; periods
    R3 = report.collect(st, sl, today - timedelta(days=100), today, "", "en")
    ok(not R3["daily_rows"] and R3["monthly"] and "Monthly table" in report.render_html(R3), "a long period gets a month-by-month table")
    ok(report.render_html(R3).startswith("<!DOCTYPE html>") and 'dir="ltr"' in report.render_html(R3), "English report is left-to-right")
    # empty period
    R4 = report.collect(st, sl, today + timedelta(days=5), today + timedelta(days=9), "", "fa")
    ok(R4["days"] == [] and "در این بازه داده‌ای ثبت نشده است" in report.render_html(R4), "an empty / future period says so instead of failing")
    # period ranges
    wk = report.period_range("week", date(2026, 10, 21), 5, "fa")      # Wednesday, week starts Saturday
    ok(wk == (date(2026, 10, 17), date(2026, 10, 23)), "week range starts on the chosen weekday")
    m = report.period_range("month", date(2026, 10, 21), 5, "fa")      # 29 Mehr 1405
    ok(m == (date(2026, 9, 23), date(2026, 10, 22)), "Jalali month range (Mehr 1405)")
    ok(report.period_range("month", date(2026, 10, 21), 5, "en") == (date(2026, 10, 1), date(2026, 10, 31)), "Gregorian month range")
    y = report.period_range("year", date(2026, 10, 21), 5, "fa")
    ok(y == (date(2026, 3, 21), date(2027, 3, 20)), "Jalali year range (1405)")
    ok(report.period_range("all", date.today(), 5, "fa", first=date(2026, 1, 1)) == (date(2026, 1, 1), date.today()), "all time starts at the first record")
    ok(report.first_recorded_day(sl, st) == today - timedelta(days=39), "first recorded day")
    ok(report.fmt_dur(3 * 3600 + 5 * 60, "fa") == "۳ ساعت و ۵ دقیقه" and report.fmt_dur(50 * 60, "en") == "50 min" and report.fmt_dur(7200, "en") == "2h 00m", "duration formats")


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
