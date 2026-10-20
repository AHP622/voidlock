"""Enforcement service (runs as a separate process) and its UI-side client.

The UI never blocks anything itself. It writes session.json / locks.json; the guard process
reads them, terminates blocked processes, and reports what actually happened in status.json.
The UI only ever displays what the guard reports.

Two kinds of rules are enforced:
  * session rules  - while a focus session is running (not paused)
  * day locks      - per-app locks for several days; enforced continuously, survive restarts
"""
import email.utils
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil

from . import hosts as hostsmod
from . import i18n, messages, rules, sounds
from .store import DEFAULT_SETTINGS, Store, read_json, uid, write_json

MAX_SESSION_SEC = 12 * 3600        # failsafe: a *session* never enforces longer than this
IDLE_EXIT_SEC = 45                 # guard quits when there is nothing to enforce
HEARTBEAT_STALE = 4.0
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "VoidLockGuard"

# Never terminated, whatever the rules say (prevents accidental lock-out).
PROTECTED = {
    "explorer.exe", "taskmgr.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe",
    "windowsterminal.exe", "regedit.exe", "mmc.exe", "msconfig.exe", "control.exe",
    "system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe",
    "sihost.exe", "ctfmon.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "taskhostw.exe", "runtimebroker.exe", "audiodg.exe",
    "voidlock.exe", "python.exe", "pythonw.exe", "python", "python3", "bash", "sh", "systemd",
}


def is_protected(exe):
    return exe.strip().lower() in PROTECTED


def _log(store, msg):
    try:
        p = store.p_log
        if p.exists() and p.stat().st_size > 200_000:
            p.write_text("", encoding="utf-8")
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def online_time():
    """Real time from an HTTP Date header, so changing the Windows clock cannot end a lock early."""
    for u in ("https://www.google.com", "https://www.microsoft.com", "https://www.cloudflare.com"):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=5)
            return email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp()
        except Exception:
            continue
    return None


class TrustedClock:
    """PC clock corrected by internet time. The lookup runs in a background thread: an offline PC used to
    freeze the whole guard for up to 15 s (no blocking, stale heartbeat, a second guard being started)."""

    def __init__(self, fetch=None):
        self.offset = 0.0
        self.online = False
        self._fetch = fetch or online_time
        self._next = 0.0
        self._busy = False

    def _work(self):
        try:
            on = self._fetch()
        except Exception:
            on = None
        t = time.time()
        if on:
            self.offset = on - t
            self.online = True
            self._next = t + 600
        else:
            self._next = t + 120          # offline: try again sooner, keep the last known offset
        self._busy = False

    def now(self):
        t = time.time()
        if t >= self._next and not self._busy:
            self._busy = True
            threading.Thread(target=self._work, daemon=True).start()
        return t + self.offset


_LOCK_HANDLE = []        # keeps the guard's lock file open for the life of the process


def acquire_guard_lock(home):
    """Exclusive lock held by the running guard (released by the OS when the process dies). Returns True when
    this process is the only guard. Two guards used to be possible when the UI, the watchdog and the sign-in
    entry started one at the same moment."""
    try:
        path = Path(home) / "guard.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return True                      # cannot even create it: do not lock the user out of enforcement
    try:
        if sys.platform == "win32":
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"1")
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return False
    except Exception:
        os.close(fd)
        return True
    _LOCK_HANDLE.append(fd)
    return True


def _is_guard_process(pid):
    """True unless we can positively tell that `pid` is NOT a VOIDLOCK guard (a recycled PID)."""
    try:
        cmd = psutil.Process(pid).cmdline()
    except psutil.NoSuchProcess:
        return False
    except Exception:                    # AccessDenied: an elevated guard - cannot be read, cannot be stopped either
        return True
    return "--guard" in cmd


# ------------------------------------------------------------------ autostart (Windows)
def child_env():
    """Environment for spawning another copy of ourselves. With a PyInstaller one-file exe the child
    must get its OWN temp folder; otherwise closing the UI while the guard still runs fails with
    'Failed to remove temporary directory: _MEI...'."""
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def command_line(store):
    if getattr(sys, "frozen", False):
        base = [sys.executable]
    else:
        main = Path(__file__).resolve().parent.parent / "main.py"
        exe = sys.executable
        if sys.platform == "win32" and exe.lower().endswith("python.exe"):
            pw = exe[:-10] + "pythonw.exe"
            exe = pw if os.path.exists(pw) else exe
        base = [exe, str(main)]
    return base + ["--guard", "--home", str(store.home)]


def autostart(enable, store):
    """Start the guard at Windows sign-in (needed so day locks survive reboots)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                cmd = " ".join(f'"{c}"' for c in command_line(store))
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


TASK_NAME = "VoidLockWatchdog"
ADMIN_TASK = "VoidLockGuardAdmin"


def _watchdog_vbs(store):
    """Tiny script run by Task Scheduler every minute: if something needs enforcing (day locks, lock hours,
    play tracking) but the guard stopped - for example it was ended in Task Manager - start it again."""
    cmd = " ".join('"' + c + '"' for c in command_line(store)).replace('"', '""')
    home = str(store.home).replace('"', '""')
    return (
        'Option Explicit\r\n'
        'On Error Resume Next\r\n'
        'Dim fso, sh, home, t, f, need, alive, p\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'home = "{home}"\r\n'
        'need = False\r\n'
        'For Each p In Array("locks_guard.json", "windows_guard.json")\r\n'
        '  If fso.FileExists(home & "\\" & p) Then\r\n'
        '    Set f = fso.OpenTextFile(home & "\\" & p, 1)\r\n'
        '    t = f.ReadAll\r\n'
        '    f.Close\r\n'
        '    If InStr(t, """until""") > 0 Or InStr(t, """start""") > 0 Then need = True\r\n'
        '  End If\r\n'
        'Next\r\n'
        'If fso.FileExists(home & "\\settings.json") Then\r\n'
        '  Set f = fso.OpenTextFile(home & "\\settings.json", 1)\r\n'
        '  t = f.ReadAll\r\n'
        '  f.Close\r\n'
        '  If InStr(t, """play_tracking"": true") > 0 Then need = True\r\n'
        'End If\r\n'
        'If need Then\r\n'
        '  alive = False\r\n'
        '  If fso.FileExists(home & "\\status.json") Then\r\n'
        '    If DateDiff("s", fso.GetFile(home & "\\status.json").DateLastModified, Now) < 15 Then alive = True\r\n'
        '  End If\r\n'
        '  If Not alive Then\r\n'
        '    If fso.FileExists(home & "\\admin_guard.flag") Then\r\n'
        f'      sh.Run "schtasks /Run /TN {ADMIN_TASK}", 0, False\r\n'
        '    Else\r\n'
        f'      sh.Run "{cmd}", 0, False\r\n'
        '    End If\r\n'
        '  End If\r\n'
        'End If\r\n'
    )


def watchdog_task(enable, store):
    """Windows only. Registers/removes the once-a-minute watchdog (no admin rights needed)."""
    if sys.platform != "win32":
        return False
    try:
        flags = 0x08000000
        if enable:
            vbs = store.home / "watchdog.vbs"
            vbs.write_text(_watchdog_vbs(store), encoding="utf-16")     # BOM: non-ASCII paths stay intact
            tr = f'wscript.exe //B //Nologo "{vbs}"'
            subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "MINUTE", "/MO", "1", "/TR", tr, "/F"],
                           capture_output=True, creationflags=flags)
        else:
            subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, creationflags=flags)
        return True
    except Exception:
        return False


def persist_protection(enable, store):
    """Sign-in start + the watchdog: what keeps day locks / lock hours alive across reboots and kills."""
    if enable and store.p_admin_flag.exists():
        autostart(False, store)            # the administrator task already starts the guard at sign-in
    else:
        autostart(enable, store)
    watchdog_task(enable, store)


def admin_guard_install(store):
    """Run ELEVATED (UAC). Creates a logon task that starts the guard with administrator rights, which is
    needed for website blocking (hosts file) and for closing programs that run as administrator."""
    if sys.platform != "win32":
        return False, "Windows only."
    try:
        cmd = " ".join(f'"{c}"' for c in command_line(store))
        r = subprocess.run(["schtasks", "/Create", "/TN", ADMIN_TASK, "/SC", "ONLOGON", "/RL", "HIGHEST", "/TR", cmd, "/F"],
                           capture_output=True, text=True, creationflags=0x08000000)
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "schtasks failed").strip()
        store.p_admin_flag.write_text("1", encoding="utf-8")
        GuardClient(store).stop()
        time.sleep(1.0)
        subprocess.run(["schtasks", "/Run", "/TN", ADMIN_TASK], capture_output=True, creationflags=0x08000000)
        return True, ""
    except Exception as e:
        return False, str(e)


def admin_task_outdated(store):
    """True when the administrator task still points to an older copy of the app (after an update)."""
    if sys.platform != "win32" or not store.p_admin_flag.exists():
        return False
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", ADMIN_TASK, "/V", "/FO", "LIST"],
                           capture_output=True, text=True, creationflags=0x08000000)
        if r.returncode != 0:
            return True
        exe = command_line(store)[0].lower()
        return exe not in r.stdout.lower()
    except Exception:
        return False


def admin_guard_remove(store):
    if sys.platform != "win32":
        return False
    try:
        subprocess.run(["schtasks", "/Delete", "/TN", ADMIN_TASK, "/F"], capture_output=True, creationflags=0x08000000)
        store.p_admin_flag.unlink(missing_ok=True)
        hostsmod.write_hosts([])
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ lock bookkeeping
def _merge_known(known, locks):
    for l in locks or []:
        try:
            exe = l["exe"].strip().lower()
            until = float(l["until"])
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        cur = known.get(exe)
        if cur is None:
            known[exe] = {"exe": l["exe"], "name": l.get("name", l["exe"]), "until": until,
                          "id": l.get("id"), "created": l.get("created", time.time())}
        elif until > cur["until"]:      # a lock can only ever grow, never shrink
            cur["until"] = until


def _persist(store, known):
    data = {"version": 1, "locks": list(known.values())}
    write_json(store.p_locks, data)
    write_json(store.p_locks_guard, data)


def _merge_windows(known, windows):
    for w in windows or []:
        try:
            wid = w["id"]
            rules.hm(w["start"]); rules.hm(w["end"])
        except (KeyError, ValueError, TypeError):
            continue
        if wid not in known:                      # lock hours can only be added here, never edited away
            known[wid] = w


def _persist_windows(store, known):
    data = {"version": 1, "windows": list(known.values())}
    write_json(store.p_windows, data)
    write_json(store.p_windows_guard, data)


def release_locks_direct(store, exes=(), windows=()):
    """Remove locks / lock hours (file level). Used by the guard on a release request, and by the UI
    when the guard is not running."""
    exes = {e.lower() for e in exes}
    wins = set(windows)
    for p in (store.p_locks, store.p_locks_guard):
        d = read_json(p, {}) or {}
        locks = [l for l in d.get("locks", []) if l.get("exe", "").lower() not in exes]
        write_json(p, {"version": 1, "locks": locks})
    if wins:
        for p in (store.p_windows, store.p_windows_guard):
            d = read_json(p, {}) or {}
            write_json(p, {"version": 1, "windows": [w for w in d.get("windows", []) if w.get("id") not in wins]})


RANK = {"lock": 3, "session": 2, "window": 1}


def _show_box(title, body):
    """Native always-on-top message box (used only when the VOIDLOCK window is not open)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, body, title, 0x40 | 0x1000 | 0x40000)
    except Exception:
        pass


# ------------------------------------------------------------------ guard process
def run_guard(home=None, interval=1.0):
    store = Store(home, service=True)
    pid = os.getpid()
    for _try in range(15):               # a guard that is being replaced needs a moment to let go
        if acquire_guard_lock(store.home):
            break
        time.sleep(0.2)
    else:
        return                           # another guard is already running
    old = read_json(store.p_status, {}) or {}
    if old.get("pid") and old["pid"] != pid and psutil.pid_exists(old["pid"]) \
            and time.time() - old.get("heartbeat", 0) < HEARTBEAT_STALE and _is_guard_process(old["pid"]) \
            and not _LOCK_HANDLE:
        return                           # (only reached when the lock file could not be used)
    started = time.time()
    clock = TrustedClock()
    per_app, denied, errors = {}, set(), []
    kills_session = 0
    cur_session = None
    idle_since = time.time()
    mode = "idle"
    known = {}
    known_w = {}
    _merge_known(known, (read_json(store.p_locks_guard, {}) or {}).get("locks"))
    _merge_known(known, (read_json(store.p_locks, {}) or {}).get("locks"))
    _merge_windows(known_w, (read_json(store.p_windows_guard, {}) or {}).get("windows"))
    _merge_windows(known_w, (read_json(store.p_windows, {}) or {}).get("windows"))
    _log(store, f"guard started pid={pid} locks={len(known)} windows={len(known_w)}")
    active = {}
    app_t = {}
    settings, settings_t = dict(DEFAULT_SETTINGS), 0.0
    catalog, catalog_t = [], 0.0
    sites_applied, sites_err, sites_want, sites_t = [], "", frozenset(), 0.0
    play = (read_json(store.p_play, {}) or {}).get("days", {})
    play_dirty, play_flush, last_tick = False, time.time(), time.time()
    attempts = (read_json(store.p_attempts, {}) or {}).get("list", [])
    last_attempt = {}
    events = (read_json(store.p_events, {}) or {}).get("list", [])
    box_busy = threading.Event()
    playing_now = False
    active_win_names = []

    def publish(extra_mode=None):
        write_json(store.p_status, {
            "pid": pid, "heartbeat": time.time(), "started": started,
            "mode": extra_mode or mode, "session_id": cur_session,
            "killed": kills_session, "per_app": per_app, "denied": sorted(denied),
            "errors": errors[-5:], "platform": sys.platform, "elevated": _is_admin(),
            "locks_active": len(active), "clock_online": clock.online,
            "clock_offset": round(clock.offset, 1), "windows": len(known_w),
            "windows_active": active_win_names, "playing_now": playing_now,
            "sites_applied": sites_applied, "sites_error": sites_err,
        })

    def flush_play(force=False):
        nonlocal play_dirty, play_flush
        if play_dirty and (force or time.time() - play_flush > 30):
            write_json(store.p_play, {"days": dict(sorted(play.items())[-400:])})
            play_dirty, play_flush = False, time.time()

    def record_block(exe, name, why, now):
        """One 'attempt' per program per 15 s: log, sound, personal message."""
        if now - last_attempt.get(exe, 0) < 15:
            return
        last_attempt[exe] = now
        attempts.append({"t": now, "exe": exe, "name": name, "why": why})
        del attempts[:-3000]
        write_json(store.p_attempts, {"list": attempts})
        ev = {"id": uid(), "t": now, "exe": exe, "name": name, "why": why}
        events.append(ev)
        del events[:-20]
        write_json(store.p_events, {"list": events})
        sounds.play("close", settings.get("sound", "soft"))
        ui = read_json(store.p_ui_alive, {}) or {}
        ui_hidden = time.time() - float(ui.get("t", 0)) > 6 or not ui.get("visible", True)
        if ui_hidden and not box_busy.is_set() and sys.platform == "win32":
            title, body = messages.block_message(settings, name, why)
            box_busy.set()
            threading.Thread(target=lambda: (_show_box(title, body), box_busy.clear()), daemon=True).start()

    while True:
        loop_start = time.time()
        try:
            # ---- session recovery file: only honoured for the session it was meant for
            if store.p_recover.exists():
                cur = read_json(store.p_session, {}) or {}
                try:
                    want = store.p_recover.read_text(encoding="utf-8").strip()
                    mtime = store.p_recover.stat().st_mtime
                except OSError:
                    want, mtime = "", 0
                try:
                    store.p_recover.unlink()
                except OSError:
                    pass
                fresh = (want and want == cur.get("session_id")) or \
                        (not want and mtime >= float(cur.get("started_at", 0) or 0) - 1)
                if fresh and cur.get("state") in ("running", "paused"):
                    write_json(store.p_session, {"state": "idle", "recovered": True,
                                                 "session_id": cur.get("session_id")})
                    _log(store, "recovery requested -> session cleared")
                    mode = "recovered"
                    per_app.clear(); denied.clear()
                    publish()
                    time.sleep(1.2)
                    mode = "idle"
                    idle_since = time.time()
                    continue
                _log(store, "stale recovery file ignored")

            tnow = clock.now()
            now = time.time()
            # ---- settings + app catalogue (cheap, cached)
            if now - settings_t > 10:
                settings = {**DEFAULT_SETTINGS, **(read_json(store.p_settings, {}) or {})}
                i18n.set_language(settings.get("language", "en"))
                settings_t = now
            if now - catalog_t > 4:
                catalog = read_json(store.p_apps, []) or []
                catalog_t = now

            # ---- release requests (day locks / lock hours)
            rel = read_json(store.p_release, None)
            if isinstance(rel, dict) and (rel.get("exes") or rel.get("windows")):
                for e in rel.get("exes", []):
                    known.pop(e.strip().lower(), None)
                for wid in rel.get("windows", []):
                    known_w.pop(wid, None)
                _log(store, f"released: {rel}")
                try:
                    store.p_release.unlink()
                except OSError:
                    pass
                _persist(store, known)
                _persist_windows(store, known_w)

            # ---- day locks (trusted time so the PC clock cannot end them early)
            file_locks = (read_json(store.p_locks, {}) or {}).get("locks")
            _merge_known(known, file_locks)
            for k in [k for k, v in known.items() if v["until"] <= tnow]:
                known.pop(k)
                _log(store, f"lock expired: {k}")
            on_disk = {}
            for l in file_locks or []:
                try:
                    on_disk[l["exe"].strip().lower()] = float(l["until"])
                except (KeyError, ValueError, TypeError, AttributeError):
                    pass
            if on_disk != {k: v["until"] for k, v in known.items()}:      # edited / shortened / deleted -> restore
                _persist(store, known)
            active = {k: v for k, v in known.items() if v["until"] > tnow and not is_protected(k)}

            # ---- lock hours
            file_w = (read_json(store.p_windows, {}) or {}).get("windows")
            _merge_windows(known_w, file_w)
            if {w.get("id") for w in file_w or []} != set(known_w):          # edited / deleted -> restore
                _persist_windows(store, known_w)
            ldt = datetime.fromtimestamp(tnow)
            pass_active = float((read_json(store.p_pass, {}) or {}).get("until", 0) or 0) > tnow
            wins = list(known_w.values())
            active_win_names = [w.get("name") or "hours" for w in rules.active_windows(wins, ldt)]
            cats = rules.blocked_categories(wins, ldt, pass_active)

            # ---- focus session
            st = read_json(store.p_session, {}) or {}
            state = st.get("state", "idle")
            if st.get("session_id") != cur_session:
                cur_session = st.get("session_id")
                kills_session = 0
                per_app.clear(); denied.clear(); errors.clear()
            ends = float(st.get("ends_at", 0) or 0)
            started_at = float(st.get("started_at", now) or now)
            if state == "running" and (ends <= now or ends - now > MAX_SESSION_SEC):
                mode = "expired"
            elif state == "running":
                mode = "enforcing"
            elif state == "paused":
                mode = "paused"
            else:
                mode = "idle"

            # ---- what must be blocked right now: key -> (kind, name, reason)
            targets = {}

            def want(key, kind, name, reason):
                key = key.strip().lower()
                if is_protected(key) or not key:
                    return
                cur = targets.get(key)
                if cur is None or RANK[reason] > RANK[cur[2]]:
                    targets[key] = (kind, name, reason)

            kind_of = {a["exe"].strip().lower(): a.get("kind", "app") for a in catalog if a.get("exe")}
            if mode == "enforcing":
                for b in st.get("blocked", []):
                    if b.get("exe"):
                        want(b["exe"], b.get("kind") or kind_of.get(b["exe"].strip().lower(), "app"), b.get("name", b["exe"]), "session")
            for k, v in active.items():
                want(k, kind_of.get(k, "app"), v.get("name", k), "lock")
            if cats:
                for a in catalog:
                    if a.get("category") in cats and a.get("exe"):
                        want(a["exe"], a.get("kind", "app"), a.get("name", a["exe"]), "window")

            app_t = {k: v for k, v in targets.items() if v[0] != "site"}
            site_t = {k: v for k, v in targets.items() if v[0] == "site"}
            for exe, (_k, _n, reason) in app_t.items():
                rec = per_app.setdefault(exe, {"killed": 0, "last": 0, "denied": False})
                rec["lock"] = reason == "lock"
                rec["reason"] = reason
            for exe in list(per_app):
                if exe not in app_t:
                    per_app.pop(exe, None)

            # ---- one pass over the process list: close blocked programs, watch games
            games = {a["exe"].strip().lower() for a in catalog
                     if a.get("category") == "Games" and a.get("kind", "app") != "site" and a.get("exe")}
            track = bool(settings.get("play_tracking", True))
            if app_t or (track and games):
                killed, running_games = _scan(store, app_t, per_app, denied, errors, now, games if track else set())
                for name in killed:
                    kind, disp, reason = app_t[name]
                    record_block(name, disp, reason, now)
            else:
                running_games = set()
            kills_session = sum(v["killed"] for v in per_app.values())

            # ---- play-time accounting (only what is really still running counts)
            dt = max(0.0, min(10.0, now - last_tick))
            last_tick = now
            if track:
                day = play.setdefault(datetime.fromtimestamp(now).date().isoformat(), {"monitored": 0, "total": 0, "apps": {}})
                day["monitored"] = round(day["monitored"] + dt, 1)
                playing_now = bool(running_games)
                if playing_now:
                    day["total"] = round(day["total"] + dt, 1)
                    for g_ in running_games:
                        day["apps"][g_] = round(day["apps"].get(g_, 0) + dt, 1)
                play_dirty = True
            else:
                playing_now = False
            flush_play()

            # ---- websites through the hosts file (needs administrator rights)
            want_sites = frozenset(site_t)
            if want_sites != sites_want or now - sites_t > 60:
                sites_t = now
                if want_sites or sites_want or hostsmod.current_block_domains():
                    ok, msg = hostsmod.write_hosts(sorted(want_sites))
                    sites_err = "" if ok else msg
                    if ok:
                        sites_applied = sorted(want_sites)
                    elif want_sites:
                        sites_applied = []
                sites_want = want_sites

            persistent = bool(active or known_w or track or mode in ("enforcing", "paused") or want_sites)
            if persistent:
                idle_since = now
            publish()
            if not persistent and mode in ("idle", "expired") and now - idle_since > IDLE_EXIT_SEC:
                flush_play(True)
                persist_protection(False, store)
                publish("exited")
                _log(store, "guard idle -> exiting")
                return
        except Exception as e:  # never die silently, never lock the user out
            errors.append(f"{type(e).__name__}: {e}")
            _log(store, f"error {e!r}")
            try:
                publish()
            except Exception:
                pass
        time.sleep(max(0.2, (interval if app_t else 1.5) - (time.time() - loop_start)))


def _scan(store, blocked, per_app, denied, errors, now, games):
    """One pass over running processes. Terminates blocked programs; returns (killed_names, running_games)."""
    me = os.getpid()
    killed, playing = [], set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if not name or proc.info["pid"] == me:
                continue
            if name not in blocked:
                if name in games:
                    playing.add(name)
                continue
            rec = per_app[name]
            try:
                proc.terminate()
                try:
                    proc.wait(0.4)
                except psutil.TimeoutExpired:
                    proc.kill()
                rec["killed"] += 1
                rec["last"] = now
                rec["denied"] = False
                denied.discard(name)
                if name not in killed:
                    killed.append(name)
                _log(store, f"terminated {name} pid={proc.info['pid']}")
            except psutil.AccessDenied:
                rec["denied"] = True
                denied.add(name)
                if name in games:
                    playing.add(name)          # still running = still playing (honest)
                msg = f"permission denied for {name}"
                if msg not in errors:
                    errors.append(msg)
                    _log(store, msg)
            except psutil.NoSuchProcess:
                pass
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except psutil.AccessDenied:
            continue
    return killed, playing


def _is_admin():
    try:
        if sys.platform == "win32":
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


# ------------------------------------------------------------------ UI-side client
class GuardClient:
    """Starts the guard, reads its status. Contains no Qt code."""

    def __init__(self, store: Store):
        self.store = store
        self.launched_at = 0.0
        self.launch_error = None
        self.attempts = 0

    def status(self):
        st = read_json(self.store.p_status, {}) or {}
        pid = st.get("pid")
        alive = bool(pid) and psutil.pid_exists(pid) and \
            time.time() - st.get("heartbeat", 0) < HEARTBEAT_STALE and st.get("mode") != "exited"
        st["alive"] = alive
        return st

    def _cmd(self):
        return command_line(self.store)

    def ensure(self):
        """Start the guard if it is not running. Returns True if a launch was made."""
        st = self.status()
        if st["alive"]:
            # A guard without administrator rights is running although the admin guard is enabled (for
            # example it was started before the admin task existed). It can not block websites, so swap it.
            wrong_rights = (sys.platform == "win32" and self.store.p_admin_flag.exists()
                            and not st.get("elevated") and time.time() - self.launched_at > 120)
            if not wrong_rights:
                return False
            self.stop()
            time.sleep(1.0)
        if self.store.p_admin_flag.exists() and sys.platform == "win32":
            try:
                r = subprocess.run(["schtasks", "/Run", "/TN", ADMIN_TASK], capture_output=True,
                                   creationflags=0x08000000)
                if r.returncode == 0:
                    self.launched_at = time.time()
                    self.launch_error = None
                    self.attempts += 1
                    return True
            except Exception:
                pass
        try:
            kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                  "stderr": subprocess.DEVNULL, "close_fds": True, "env": child_env()}
            if sys.platform == "win32":
                kw["creationflags"] = 0x00000008 | 0x08000000 | 0x00000200
            else:
                kw["start_new_session"] = True
            subprocess.Popen(self._cmd(), **kw)
            self.launched_at = time.time()
            self.launch_error = None
            self.attempts += 1
            return True
        except Exception as e:
            self.launch_error = f"{type(e).__name__}: {e}"
            return False

    def start_elevated(self):
        """Windows only: relaunch the guard with administrator rights (UAC prompt)."""
        if sys.platform != "win32":
            return False, "Administrator elevation is only available on Windows."
        try:
            import ctypes
            if getattr(sys, "frozen", False):
                os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            cmd = self._cmd()
            params = " ".join(f'"{c}"' for c in cmd[1:])
            r = ctypes.windll.shell32.ShellExecuteW(None, "runas", cmd[0], params, None, 0)
            if r <= 32:
                return False, "Elevation was cancelled or refused."
            self.launched_at = time.time()
            return True, ""
        except Exception as e:
            return False, str(e)

    def stop(self):
        st = read_json(self.store.p_status, {}) or {}
        pid = st.get("pid")
        if pid and pid != os.getpid() and psutil.pid_exists(pid) and _is_guard_process(pid):
            try:
                psutil.Process(pid).terminate()
            except Exception:
                pass

    def release(self, exes=(), windows=()):
        """Ask the guard to drop locks / lock hours (or do it directly if it is not running)."""
        exes = [e.lower() for e in exes]
        if self.status()["alive"]:
            write_json(self.store.p_release, {"exes": exes, "windows": list(windows), "t": time.time()})
        else:
            release_locks_direct(self.store, exes, windows)
            if not (read_json(self.store.p_locks_guard, {}) or {}).get("locks") and \
                    not (read_json(self.store.p_windows_guard, {}) or {}).get("windows"):
                persist_protection(False, self.store)
        self.store.refresh_locks()
        self.store.refresh_windows()

    def release_locks(self, exes):
        self.release(exes=exes)

    def install_admin(self):
        """Ask Windows for administrator rights once and install the elevated guard task."""
        if sys.platform != "win32":
            return False, "Administrator elevation is only available on Windows."
        try:
            import ctypes
            if getattr(sys, "frozen", False):
                os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            base = command_line(self.store)
            args = [a for a in base[1:] if a != "--guard"] + ["--install-admin-guard"]
            params = " ".join(f'"{c}"' for c in args)
            r = ctypes.windll.shell32.ShellExecuteW(None, "runas", base[0], params, None, 0)
            return (r > 32), ("" if r > 32 else "Elevation was cancelled or refused.")
        except Exception as e:
            return False, str(e)


def emergency_recover(store: Store):
    """Out-of-band recovery of a *session*: clears it and stops the guard. Day locks are not
    cleared here - they have their own (slower) release path."""
    sid = (read_json(store.p_session, {}) or {}).get("session_id")
    write_json(store.p_session, {"state": "idle", "recovered": True, "session_id": sid})
    try:
        store.p_recover.write_text(sid or "", encoding="utf-8")
    except OSError:
        pass
    if not (read_json(store.p_locks_guard, {}) or {}).get("locks"):
        GuardClient(store).stop()
