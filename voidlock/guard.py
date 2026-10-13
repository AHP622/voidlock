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
import time
import urllib.request
from pathlib import Path

import psutil

from .store import Store, read_json, write_json

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
    def __init__(self):
        self.offset = 0.0
        self.last = 0.0
        self.online = False

    def now(self):
        t = time.time()
        if t - self.last > 600 or self.last == 0:
            self.last = t
            on = online_time()
            if on:
                self.offset = on - t
                self.online = True
        return t + self.offset


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


def _watchdog_vbs(store):
    """Tiny script run by Task Scheduler every minute: if day locks exist but the guard stopped
    (for example it was ended in Task Manager), start it again. Silent (no window)."""
    cmd = " ".join('"' + c + '"' for c in command_line(store)).replace('"', '""')
    home = str(store.home).replace('"', '""')
    return (
        'Option Explicit\r\n'
        'On Error Resume Next\r\n'
        'Dim fso, sh, home, t, f, need, alive\r\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\r\n'
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'home = "{home}"\r\n'
        'need = False\r\n'
        'If fso.FileExists(home & "\\locks_guard.json") Then\r\n'
        '  Set f = fso.OpenTextFile(home & "\\locks_guard.json", 1)\r\n'
        '  t = f.ReadAll\r\n'
        '  f.Close\r\n'
        '  If InStr(t, """until""") > 0 Then need = True\r\n'
        'End If\r\n'
        'If need Then\r\n'
        '  alive = False\r\n'
        '  If fso.FileExists(home & "\\status.json") Then\r\n'
        '    If DateDiff("s", fso.GetFile(home & "\\status.json").DateLastModified, Now) < 15 Then alive = True\r\n'
        '  End If\r\n'
        f'  If Not alive Then sh.Run "{cmd}", 0, False\r\n'
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
    """Autostart at sign-in + the watchdog: what keeps day locks alive across reboots and kills."""
    autostart(enable, store)
    watchdog_task(enable, store)


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


def release_locks_direct(store, exes):
    """Remove locks (file level). Used by the guard on a release request, and by the UI when
    the guard is not running."""
    exes = {e.lower() for e in exes}
    for p in (store.p_locks, store.p_locks_guard):
        d = read_json(p, {}) or {}
        locks = [l for l in d.get("locks", []) if l.get("exe", "").lower() not in exes]
        write_json(p, {"version": 1, "locks": locks})


# ------------------------------------------------------------------ guard process
def run_guard(home=None, interval=1.0):
    store = Store(home, service=True)
    pid = os.getpid()
    old = read_json(store.p_status, {})
    if old.get("pid") and old["pid"] != pid and psutil.pid_exists(old["pid"]) \
            and time.time() - old.get("heartbeat", 0) < HEARTBEAT_STALE:
        return
    started = time.time()
    clock = TrustedClock()
    per_app, denied, errors = {}, set(), []
    kills_session = 0
    cur_session = None
    idle_since = time.time()
    mode = "idle"
    known = {}
    _merge_known(known, (read_json(store.p_locks_guard, {}) or {}).get("locks"))
    _merge_known(known, (read_json(store.p_locks, {}) or {}).get("locks"))
    _log(store, f"guard started pid={pid} locks={len(known)}")
    active = {}

    def publish(extra_mode=None):
        write_json(store.p_status, {
            "pid": pid, "heartbeat": time.time(), "started": started,
            "mode": extra_mode or mode, "session_id": cur_session,
            "killed": kills_session, "per_app": per_app, "denied": sorted(denied),
            "errors": errors[-5:], "platform": sys.platform, "elevated": _is_admin(),
            "locks_active": len(active), "clock_online": clock.online,
            "clock_offset": round(clock.offset, 1),
        })

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

            # ---- day locks (trusted time so the PC clock cannot end them early)
            tnow = clock.now()
            rel = read_json(store.p_release, None)
            if isinstance(rel, dict) and rel.get("exes"):
                for e in rel["exes"]:
                    known.pop(e.strip().lower(), None)
                _log(store, f"locks released: {rel['exes']}")
                try:
                    store.p_release.unlink()
                except OSError:
                    pass
                _persist(store, known)
            before = {k: v["until"] for k, v in known.items()}
            _merge_known(known, (read_json(store.p_locks, {}) or {}).get("locks"))
            for k in [k for k, v in known.items() if v["until"] <= tnow]:
                known.pop(k)
                _log(store, f"lock expired: {k}")
            if {k: v["until"] for k, v in known.items()} != before or not store.p_locks.exists():
                _persist(store, known)
            active = {k: v for k, v in known.items() if v["until"] > tnow and not is_protected(k)}

            # ---- focus session
            st = read_json(store.p_session, {}) or {}
            state = st.get("state", "idle")
            now = time.time()
            if st.get("session_id") != cur_session:
                cur_session = st.get("session_id")
                kills_session = 0
                per_app.clear(); denied.clear(); errors.clear()
            ends = float(st.get("ends_at", 0) or 0)
            started_at = float(st.get("started_at", now) or now)
            targets = {}
            if state == "running" and (ends <= now or now - started_at > MAX_SESSION_SEC):
                mode = "expired"
            elif state == "running":
                mode = "enforcing"
                for b in st.get("blocked", []):
                    if b.get("exe") and not is_protected(b["exe"]):
                        targets[b["exe"].strip().lower()] = False
            elif state == "paused":
                mode = "paused"
            else:
                mode = "idle"
            for k in active:                       # day locks apply in every mode, even paused
                targets[k] = True
            for exe, is_lock in targets.items():
                rec = per_app.setdefault(exe, {"killed": 0, "last": 0, "denied": False})
                rec["lock"] = is_lock or rec.get("lock", False)
            for exe in list(per_app):
                if exe not in targets:
                    per_app.pop(exe, None)
            if targets:
                _enforce(store, targets, per_app, denied, errors, now)
            kills_session = sum(v["killed"] for v in per_app.values())

            if mode in ("enforcing", "paused") or active:
                idle_since = now
            publish()
            if mode in ("idle", "expired") and not active and now - idle_since > IDLE_EXIT_SEC:
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
        time.sleep(max(0.2, interval - (time.time() - loop_start)))


def _enforce(store, blocked, per_app, denied, errors, now):
    me = os.getpid()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name not in blocked or proc.info["pid"] == me:
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
                _log(store, f"terminated {name} pid={proc.info['pid']}")
            except psutil.AccessDenied:
                rec["denied"] = True
                denied.add(name)
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
        if self.status()["alive"]:
            return False
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
        if pid and psutil.pid_exists(pid):
            try:
                psutil.Process(pid).terminate()
            except Exception:
                pass

    def release_locks(self, exes):
        """Ask the guard to drop locks (or do it directly if it is not running)."""
        exes = [e.lower() for e in exes]
        if self.status()["alive"]:
            write_json(self.store.p_release, {"exes": exes, "t": time.time()})
        else:
            release_locks_direct(self.store, exes)
            if not (read_json(self.store.p_locks_guard, {}) or {}).get("locks"):
                persist_protection(False, self.store)
        self.store.refresh_locks()


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
