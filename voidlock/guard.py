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
from . import __version__, classes as classtools, i18n, messages, rules, sounds
from .store import DEFAULT_SETTINGS, Store, clean_classes, read_json, read_json_checked, sanitize_settings, uid, write_json

MAX_SESSION_SEC = 12 * 3600        # failsafe: a *session* never enforces longer than this
IDLE_EXIT_SEC = 45                 # guard quits when there is nothing to enforce
HEARTBEAT_STALE = 6.0
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
            with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=5) as r:
                return email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp()
        except Exception:
            continue
    return None


class TrustedClock:
    """Internet-corrected time that the PC clock cannot move.

    The network is asked in a background thread (it used to run inside the enforcement loop: up to 15 seconds in which
    nothing was blocked and the heartbeat went stale whenever the PC was offline). After a successful sync the time
    is anchored to the monotonic clock, so changing the Windows clock later has no effect; a jump of the wall clock
    is detected and triggers a new sync."""
    SYNC_EVERY = 600.0

    def __init__(self):
        self.online = False
        self._anchor_real = None          # trusted epoch time at the last sync
        self._anchor_mono = None          # monotonic time at the last sync
        self._last_try = 0.0              # monotonic time of the last attempt
        self._busy = False
        self._wall_ref = (time.time(), time.monotonic())

    def _sync(self):
        try:
            t0 = time.monotonic()
            on = online_time()
            t1 = time.monotonic()
            if on:
                self._anchor_real = on + (t1 - t0) / 2.0
                self._anchor_mono = t1
                self._wall_ref = (time.time(), time.monotonic())
                self.online = True
        finally:
            self._busy = False

    def now(self):
        mono, wall = time.monotonic(), time.time()
        jumped = abs((wall - self._wall_ref[0]) - (mono - self._wall_ref[1])) > 5.0
        gap = mono - self._last_try
        if not self._busy and (self._last_try == 0.0 or gap > self.SYNC_EVERY or (jumped and gap > 30.0)):
            self._busy = True
            self._last_try = mono
            threading.Thread(target=self._sync, daemon=True).start()
        if self._anchor_real is None:
            return wall
        return self._anchor_real + (mono - self._anchor_mono)

    @property
    def offset(self):
        return self.now() - time.time()


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
        'If fso.FileExists(home & "\\classes.json") Then\r\n'
        '  Set f = fso.OpenTextFile(home & "\\classes.json", 1)\r\n'
        '  t = f.ReadAll\r\n'
        '  f.Close\r\n'
        '  If InStr(t, """enabled"": true") > 0 Then need = True\r\n'
        'End If\r\n'
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


_NO_WINDOW = 0x08000000


def task_xml(command, arguments, logon=False, highest=False):
    """Task Scheduler definition. The defaults of `schtasks /Create` are wrong for a guard: the task is not started
    on battery power, is stopped when the charger is unplugged, and is killed after 72 hours. This definition
    removes all three (a laptop that starts on battery used to come up without a guard until it was plugged in)."""
    from xml.sax.saxutils import escape
    trigger = ("<LogonTrigger><Enabled>true</Enabled></LogonTrigger>" if logon else
               "<TimeTrigger><Repetition><Interval>PT1M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>"
               "<StartBoundary>2024-01-01T00:00:00</StartBoundary><Enabled>true</Enabled></TimeTrigger>")
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
        f'<Triggers>{trigger}</Triggers>'
        '<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType>'
        f'<RunLevel>{"HighestAvailable" if highest else "LeastPrivilege"}</RunLevel></Principal></Principals>'
        '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>'
        '<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
        '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>'
        '<AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable>'
        '<RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><AllowStartOnDemand>true</AllowStartOnDemand>'
        '<Enabled>true</Enabled><Hidden>true</Hidden><WakeToRun>false</WakeToRun>'
        '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit><Priority>6</Priority></Settings>'
        f'<Actions Context="Author"><Exec><Command>{escape(command)}</Command>'
        f'<Arguments>{escape(arguments)}</Arguments></Exec></Actions></Task>')


def create_task(store, name, xml):
    """Registers a task from XML. Returns (ok, message)."""
    f = store.home / f"{name}.task.xml"
    try:
        f.write_text(xml, encoding="utf-16")
        r = subprocess.run(["schtasks", "/Create", "/TN", name, "/XML", str(f), "/F"], capture_output=True, text=True,
                           creationflags=_NO_WINDOW)
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()
    except Exception as e:
        return False, str(e)
    finally:
        try:
            f.unlink()
        except OSError:
            pass


def relax_task_power_settings(name):
    """Fallback for a task created the old way: allow start / keep running on battery, no time limit."""
    ps = ("Set-ScheduledTask -TaskName '%s' -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries "
          "-DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero))" % name)
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       creationflags=_NO_WINDOW, timeout=30)
    except Exception:
        pass


def task_runs_on_battery(name):
    """True when the task may start and keep running on battery power. None when it cannot be checked."""
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", name, "/XML"], capture_output=True, text=True,
                           creationflags=_NO_WINDOW, timeout=20)
        if r.returncode != 0:
            return None
        x = r.stdout
        return ("<DisallowStartIfOnBatteries>false" in x and "<StopIfGoingOnBatteries>false" in x)
    except Exception:
        return None


def watchdog_task(enable, store):
    """Windows only. Registers/removes the once-a-minute watchdog (no admin rights needed)."""
    if sys.platform != "win32":
        return False
    try:
        flags = _NO_WINDOW
        if enable:
            vbs = store.home / "watchdog.vbs"
            vbs.write_text(_watchdog_vbs(store), encoding="utf-16")     # BOM: non-ASCII paths stay intact
            ok, _msg = create_task(store, TASK_NAME, task_xml("wscript.exe", f'//B //Nologo "{vbs}"'))
            if not ok:                                                    # very old Windows: the plain command
                tr = f'wscript.exe //B //Nologo "{vbs}"'
                subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "MINUTE", "/MO", "1", "/TR", tr, "/F"],
                               capture_output=True, creationflags=flags)
                relax_task_power_settings(TASK_NAME)
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


def persist_protection_async(enable, store):
    """Task Scheduler / registry calls take a moment: keep them off the UI thread."""
    threading.Thread(target=persist_protection, args=(enable, store), daemon=True).start()


def admin_guard_install(store):
    """Run ELEVATED (UAC). Creates a logon task that starts the guard with administrator rights, which is
    needed for website blocking (hosts file) and for closing programs that run as administrator."""
    if sys.platform != "win32":
        return False, "Windows only."
    try:
        parts = command_line(store)
        args = " ".join(f'"{c}"' for c in parts[1:])
        ok, msg = create_task(store, ADMIN_TASK, task_xml(parts[0], args, logon=True, highest=True))
        if not ok:                                                        # fall back to the plain command
            cmd = " ".join(f'"{c}"' for c in parts)
            r = subprocess.run(["schtasks", "/Create", "/TN", ADMIN_TASK, "/SC", "ONLOGON", "/RL", "HIGHEST", "/TR", cmd, "/F"],
                               capture_output=True, text=True, creationflags=_NO_WINDOW)
            if r.returncode != 0:
                return False, (r.stderr or r.stdout or msg or "schtasks failed").strip()
            relax_task_power_settings(ADMIN_TASK)
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
        if exe not in r.stdout.lower():
            return True
        return task_runs_on_battery(ADMIN_TASK) is False       # created by an older version: refuse to start on battery
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
    when the guard is not running. A file that cannot be read is left untouched (writing it back from an empty read
    would have dropped every other lock)."""
    exes = {e.lower() for e in exes}
    wins = set(windows)
    if exes:
        for p in (store.p_locks, store.p_locks_guard):
            status, d = read_json_checked(p)
            if status == "missing":
                continue
            if status != "ok" or not isinstance(d, dict):
                continue
            locks = [l for l in d.get("locks", []) if str(l.get("exe", "")).lower() not in exes]
            write_json(p, {"version": 1, "locks": locks})
    if wins:
        for p in (store.p_windows, store.p_windows_guard):
            status, d = read_json_checked(p)
            if status != "ok" or not isinstance(d, dict):
                continue
            write_json(p, {"version": 1, "windows": [w for w in d.get("windows", []) if w.get("id") not in wins]})


def _rd(path):
    """A JSON file as a dict, always (a damaged file must never stop the enforcement loop)."""
    d = read_json(path, None)
    return d if isinstance(d, dict) else {}


def acquire_instance_lock(store):
    """Only one guard may enforce at a time (the old heartbeat check could be raced by the watchdog, the sign-in
    start and the UI starting a guard in the same second). Returns an open file handle to keep, False when locking is
    not possible here (then we simply run), or None when another guard already holds the lock."""
    try:
        fh = open(store.home / "guard.lock", "a+")
    except OSError:
        return False
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0, 2)
            if fh.tell() == 0:
                fh.write("1")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError as e:
        import errno
        if isinstance(e, (BlockingIOError, PermissionError)) or e.errno in (errno.EACCES, errno.EAGAIN, 36):
            fh.close()
            return None
        return False


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
    instance = acquire_instance_lock(store)        # keep the handle: the lock lives as long as this process
    if instance is None:
        return
    old = _rd(store.p_status)
    if instance is False and old.get("pid") and old["pid"] != pid and psutil.pid_exists(old["pid"]) \
            and time.time() - old.get("heartbeat", 0) < HEARTBEAT_STALE:
        return
    started = time.time()
    clock = TrustedClock()
    per_app, denied, errors = {}, set(), []
    kills_session = 0
    class_seen, class_check = set(), 0.0     # class reminders shown while the VOIDLOCK window is closed
    has_classes = [False]
    sess_sid, sess_rules = None, {}        # rules of the running session (merge-only)
    cur_session = None
    idle_since = time.time()
    mode = "idle"
    known = {}
    known_w = {}
    _merge_known(known, _rd(store.p_locks_guard).get("locks"))
    _merge_known(known, _rd(store.p_locks).get("locks"))
    _merge_windows(known_w, _rd(store.p_windows_guard).get("windows"))
    _merge_windows(known_w, _rd(store.p_windows).get("windows"))
    _log(store, f"guard started pid={pid} locks={len(known)} windows={len(known_w)}")
    active = {}
    app_t = {}
    settings, settings_t = dict(DEFAULT_SETTINGS), 0.0
    catalog, catalog_t = [], 0.0
    sites_applied, sites_err, sites_want, sites_t = [], "", frozenset(), 0.0
    play = _rd(store.p_play).get("days", {})
    if not isinstance(play, dict):
        play = {}
    play_dirty, play_flush, last_tick = False, time.time(), time.time()
    attempts = _rd(store.p_attempts).get("list", [])
    if not isinstance(attempts, list):
        attempts = []
    last_attempt = {}
    events = _rd(store.p_events).get("list", [])
    if not isinstance(events, list):
        events = []
    box_busy = threading.Event()
    playing_now = False
    active_win_names = []

    def publish(extra_mode=None):
        write_json(store.p_status, {
            "pid": pid, "heartbeat": time.time(), "started": started, "version": __version__,
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
        try:
            sounds.play("close", settings.get("sound", "soft"))
        except Exception:
            pass
        ui = _rd(store.p_ui_alive)
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
                cur = _rd(store.p_session)
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
                settings = sanitize_settings(_rd(store.p_settings))
                i18n.set_language(settings.get("language", "en"))
                settings_t = now
            if now - catalog_t > 4:
                cat_raw = read_json(store.p_apps, [])
                catalog = [a for a in cat_raw if isinstance(a, dict)] if isinstance(cat_raw, list) else []
                catalog_t = now

            # ---- release requests (day locks / lock hours)
            rel = _rd(store.p_release)
            if rel.get("exes") or rel.get("windows"):
                for e in rel.get("exes") or []:
                    known.pop(str(e).strip().lower(), None)
                for wid in rel.get("windows") or []:
                    known_w.pop(wid, None)
                _log(store, f"released: {rel}")
                try:
                    store.p_release.unlink()
                except OSError:
                    pass
                _persist(store, known)
                _persist_windows(store, known_w)

            # ---- day locks (trusted time so the PC clock cannot end them early)
            file_locks = _rd(store.p_locks).get("locks")
            if not isinstance(file_locks, list):
                file_locks = []
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
            file_w = _rd(store.p_windows).get("windows")
            if not isinstance(file_w, list):
                file_w = []
            _merge_windows(known_w, file_w)
            if {w.get("id") for w in file_w if isinstance(w, dict)} != set(known_w):          # edited / deleted -> restore
                _persist_windows(store, known_w)
            ldt = datetime.fromtimestamp(tnow)
            try:
                pass_active = float(_rd(store.p_pass).get("until", 0) or 0) > tnow
            except (TypeError, ValueError):
                pass_active = False
            wins = list(known_w.values())
            active_win_names = [w.get("name") or "hours" for w in rules.active_windows(wins, ldt)]
            cats = rules.blocked_categories(wins, ldt, pass_active)

            # ---- focus session
            st = _rd(store.p_session)
            state = st.get("state", "idle")
            if st.get("session_id") != cur_session:
                cur_session = st.get("session_id")
                kills_session = 0
                per_app.clear(); denied.clear(); errors.clear()
            ends = float(st.get("ends_at", 0) or 0)
            started_at = float(st.get("started_at", now) or now)
            if state == "running" and (ends <= now or now - started_at > MAX_SESSION_SEC):
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
            # Session rules only ever grow while the session runs (the file can be edited, the UI can be tricked: the
            # guard keeps what it has seen for this session id).
            sid_now = st.get("session_id") if state in ("running", "paused") else None
            if sid_now != sess_sid:
                sess_sid, sess_rules = sid_now, {}
            if sid_now:
                for b in st.get("blocked") or []:
                    if isinstance(b, dict) and b.get("exe"):
                        sess_rules[b["exe"].strip().lower()] = b
            if mode == "enforcing":
                for kx, b in sess_rules.items():
                    want(b["exe"], b.get("kind") or kind_of.get(kx, "app"), b.get("name", b["exe"]), "session")
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

            if now - class_check >= 10 or class_check == 0.0:
                class_check = now
                raw = read_json(store.p_classes, [])
                cl = clean_classes(raw) if isinstance(raw, list) else []
                cl = [c for c in cl if c.get("enabled", True)]
                has_classes[0] = bool(cl)
                ui_a = _rd(store.p_ui_alive)
                if cl and time.time() - float(ui_a.get("t", 0) or 0) > 6 and sys.platform == "win32":
                    ldt_now = datetime.fromtimestamp(tnow)
                    for c, kind, left in classtools.due_reminders(cl, ldt_now):
                        key = (c["id"], ldt_now.date().isoformat(), kind)
                        if key in class_seen or box_busy.is_set():
                            continue
                        class_seen.add(key)
                        place = f" · {c['place']}" if c.get("place") else ""
                        text = (i18n.tr(f"{c['name']} starts in {left} minutes") if kind == "soon"
                                else i18n.tr(f"{c['name']} is starting now")) + place
                        box_busy.set()
                        threading.Thread(target=lambda t=text: (_show_box(i18n.tr("CLASS SOON"), t), box_busy.clear()),
                                         daemon=True).start()
            persistent = bool(active or known_w or track or mode in ("enforcing", "paused") or want_sites
                              or has_classes[0])
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
            del errors[:-20]
            _log(store, f"error {e!r}")
            try:
                publish()
            except Exception:
                pass
        time.sleep(max(0.2, (interval if app_t else 1.5) - (time.time() - loop_start)))


def _scan(store, blocked, per_app, denied, errors, now, games):
    """One pass over running processes. Terminates blocked programs; returns (killed_names, running_games).

    All matching processes get the terminate request first and are then waited for together. (Waiting for every
    process one by one took up to 0.4 s each: a browser with 30 processes kept the loop busy for 12 s.)"""
    me = os.getpid()
    killed, playing = [], set()
    victims = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if not name or proc.info["pid"] == me:
                continue
            if name not in blocked:
                if name in games:
                    playing.add(name)
                continue
            rec = per_app.get(name)
            if rec is None:
                continue
            try:
                proc.terminate()
                victims.append((proc, name))
            except psutil.AccessDenied:
                _mark_denied(store, rec, denied, errors, name, name in games, playing)
            except psutil.NoSuchProcess:
                pass
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            continue
    if victims:
        _gone, alive = psutil.wait_procs([p for p, _n in victims], timeout=0.6)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                pass
        if alive:
            psutil.wait_procs(alive, timeout=0.4)
        for p, name in victims:
            rec = per_app[name]
            try:
                still = p.is_running() and p.status() != psutil.STATUS_ZOMBIE
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                still = False
            except psutil.AccessDenied:
                still = True
            if still:
                _mark_denied(store, rec, denied, errors, name, name in games, playing)
                continue
            rec["killed"] += 1
            rec["last"] = now
            rec["denied"] = False
            denied.discard(name)
            if name not in killed:
                killed.append(name)
            _log(store, f"terminated {name} pid={p.pid}")
    return killed, playing


def _mark_denied(store, rec, denied, errors, name, is_game, playing):
    rec["denied"] = True
    denied.add(name)
    if is_game:
        playing.add(name)          # still running = still playing (honest)
    msg = f"permission denied for {name}"
    if msg not in errors:
        errors.append(msg)
        _log(store, msg)


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
        self._swapped = False

    @staticmethod
    def _enforcing_session(st):
        return st.get("mode") in ("enforcing", "paused")

    def status(self):
        st = _rd(self.store.p_status)
        pid = st.get("pid")
        try:
            alive = bool(pid) and psutil.pid_exists(pid) and \
                time.time() - float(st.get("heartbeat", 0)) < HEARTBEAT_STALE and st.get("mode") != "exited"
        except (TypeError, ValueError):
            alive = False
        st["alive"] = alive
        return st

    def trusted_now(self):
        """Internet-corrected time as the guard sees it (falls back to the PC clock when the guard is offline).
        Used wherever the UI creates something that the guard later measures with its own trusted clock - a day lock
        or a play pass - so moving the Windows clock cannot make them longer or shorter."""
        st = self.status()
        try:
            if st.get("alive") and st.get("clock_online"):
                return time.time() + float(st.get("clock_offset", 0.0))
        except (TypeError, ValueError):
            pass
        return time.time()

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
            # After an update the old guard keeps running the old code until it ends. Swap it once, when idle.
            stale_code = (st.get("version") != __version__ and not self._swapped
                          and not self._enforcing_session(st) and time.time() - self.launched_at > 30)
            if not (wrong_rights or stale_code):
                return False
            if stale_code:
                self._swapped = True
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
        st = _rd(self.store.p_status)
        pid = st.get("pid")
        if pid and psutil.pid_exists(pid):
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
            if not _rd(self.store.p_locks_guard).get("locks") and \
                    not _rd(self.store.p_windows_guard).get("windows") and \
                    not self.store.settings.get("play_tracking", True) and \
                    not any(c.get("enabled", True) for c in self.store.classes):
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
    sid = _rd(store.p_session).get("session_id")
    write_json(store.p_session, {"state": "idle", "recovered": True, "session_id": sid})
    try:
        store.p_recover.write_text(sid or "", encoding="utf-8")
    except OSError:
        pass
    if not _rd(store.p_locks_guard).get("locks"):
        GuardClient(store).stop()
