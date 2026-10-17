"""UI-side state: the session controller and process scanner.
Contains no blocking logic - enforcement lives entirely in guard.py."""
import time

import psutil
from PySide6.QtCore import QObject, QThread, Signal

from . import updater
from .guard import GuardClient, emergency_recover
from .store import Store, fmt_clock, read_json, uid, write_json
from .theme import T


class Scanner(QThread):
    """Lists running process names off the UI thread."""
    scanned = Signal(object)
    failed = Signal(str)

    def __init__(self, interval=3.0):
        super().__init__()
        self.interval = interval
        self._run = True

    def run(self):
        while self._run:
            try:
                names = set()
                for p in psutil.process_iter(["name"]):
                    n = p.info.get("name")
                    if n:
                        names.add(n.lower())
                self.scanned.emit(names)
            except Exception as e:
                self.failed.emit(f"{type(e).__name__}: {e}")
            for _ in range(int(self.interval * 10)):
                if not self._run:
                    return
                self.msleep(100)

    def stop(self):
        self._run = False
        self.wait(1500)


class SessionController(QObject):
    changed = Signal()          # any state change (buttons, ring, status)
    finished = Signal(dict)     # a session record was saved
    notify = Signal(str, str)   # (message, kind)

    def __init__(self, store: Store, guard: GuardClient):
        super().__init__()
        self.store, self.guard = store, guard
        self.state = "idle"     # idle | running | paused | completed
        self.session_id = None
        self.planned = 0.0
        self.remaining = 0.0
        self.subject = ""
        self.strict = False
        self.started_at = 0.0
        self.ends_at = 0.0
        self.gstat = {"alive": False}
        self.last_record = None
        self._failed_notified = False
        self.restore()

    # ---- helpers
    def blocked_list(self):
        return [{"exe": a["exe"], "name": a["name"], "kind": a.get("kind", "app")} for a in self.store.enabled_apps()]

    def _write(self, state):
        write_json(self.store.p_session, {
            "state": state, "session_id": self.session_id, "started_at": self.started_at,
            "ends_at": self.ends_at, "remaining": self.remaining, "planned_sec": self.planned,
            "subject": self.subject, "strict": self.strict, "blocked": self.blocked_list(),
        })

    def sync_rules(self):
        if self.state in ("running", "paused"):
            self._write(self.state)

    @property
    def active(self):
        return self.state in ("running", "paused")

    # ---- transitions
    def start(self, minutes, subject="", strict=False):
        if self.active:
            return False
        self.session_id = uid()
        self.planned = float(minutes * 60)
        self.remaining = self.planned
        self.subject = (subject or "").strip()
        self.strict = bool(strict)
        self.started_at = time.time()
        self.ends_at = self.started_at + self.planned
        self.state = "running"
        self._failed_notified = False
        self.guard.attempts = 0
        try:
            self.store.p_recover.unlink()  # never let an old recovery file clear a new session
        except OSError:
            pass
        self.store.remember_subject(self.subject)
        self._write("running")
        self.guard.ensure()
        self.changed.emit()
        return True

    def pause(self):
        if self.state != "running" or self.strict:
            return False
        self.remaining = max(0.0, self.ends_at - time.time())
        self.state = "paused"
        self._write("paused")
        self.changed.emit()
        return True

    def resume(self):
        if self.state != "paused":
            return False
        self.ends_at = time.time() + self.remaining
        self.state = "running"
        self._write("running")
        self.guard.ensure()
        self.changed.emit()
        return True

    def end(self, status="ended"):
        if not self.active:
            return
        if self.state == "running":
            self.remaining = max(0.0, self.ends_at - time.time())
        focus = int(self.planned - self.remaining)
        self._finalize(status, focus)
        self.state = "idle"
        self.changed.emit()

    def dismiss(self):
        if self.state == "completed":
            self.state = "idle"
            self.changed.emit()

    def _finalize(self, status, focus):
        killed = int(self.gstat.get("killed", 0)) if self.gstat.get("session_id") == self.session_id else 0
        rec = {"id": self.session_id, "subject": self.subject, "start": self.started_at,
               "end": time.time(), "planned_min": round(self.planned / 60),
               "focus_sec": focus, "status": status, "blocked_count": killed,
               "strict": self.strict}
        write_json(self.store.p_session, {"state": "idle", "session_id": self.session_id})
        if focus >= 60 or status == "completed":
            self.store.add_record(rec)
            self.last_record = rec
            self.finished.emit(rec)

    def tick(self):
        """Called once per second by the main window."""
        now = time.time()
        self.gstat = self.guard.status()
        if self.state == "running":
            self.remaining = max(0.0, self.ends_at - now)
            if self.remaining <= 0:
                self._finalize("completed", int(self.planned))
                self.remaining = 0.0
                self.state = "completed"
                self.changed.emit()
                return
        # guard watchdog: needed for a running session with rules, or for any active day lock
        need = (self.state == "running" and bool(self.store.enabled_apps())) or bool(self.store.active_locks()) \
            or bool(self.store.windows) or bool(self.store.settings.get("play_tracking", True))
        if need and not self.gstat["alive"] and now - self.guard.launched_at > 6:
            if self.guard.attempts >= 4 and now - self.guard.launched_at > 300:
                self.guard.attempts = 0
            if self.guard.attempts < 4:
                self.guard.ensure()
            elif not self._failed_notified:
                self._failed_notified = True
                self.notify.emit("Enforcement guard could not be started - apps are NOT being blocked.", "error")
        if self.gstat["alive"]:
            self._failed_notified = False
        # external recovery (CLI / RECOVER file) cleared the session
        if self.active:
            ext = read_json(self.store.p_session, {}) or {}
            if ext.get("state") == "idle" and ext.get("session_id") == self.session_id:
                if self.state == "running":
                    self.remaining = max(0.0, self.ends_at - now)
                self._finalize("recovered", int(self.planned - self.remaining))
                self.state = "idle"
                self.notify.emit("Session cleared by recovery. Nothing is blocked now.", "warn")
        self.changed.emit()

    def restore(self):
        st = read_json(self.store.p_session, {}) or {}
        s = st.get("state")
        if s not in ("running", "paused") or not st.get("session_id"):
            return
        self.session_id = st["session_id"]
        self.planned = float(st.get("planned_sec", 0))
        self.subject = st.get("subject", "")
        self.strict = bool(st.get("strict", False))
        self.started_at = float(st.get("started_at", time.time()))
        self.ends_at = float(st.get("ends_at", 0))
        self.remaining = float(st.get("remaining", 0))
        if s == "paused":
            self.state = "paused"
            return
        if self.ends_at > time.time():
            self.state = "running"
            self.remaining = self.ends_at - time.time()
            self.guard.ensure()
        elif not self.store.has_record(self.session_id):
            self.remaining = 0.0
            self._finalize("completed", int(self.planned))
            self.state = "completed"
        else:
            write_json(self.store.p_session, {"state": "idle", "session_id": self.session_id})

    def emergency(self):
        """Always available, even in strict mode. Logged as 'emergency'."""
        if not self.active:
            return
        if self.state == "running":
            self.remaining = max(0.0, self.ends_at - time.time())
        focus = int(self.planned - self.remaining)
        emergency_recover(self.store)
        self._finalize("emergency", focus)
        self.state = "idle"
        self.changed.emit()

    # ---- honest protection report
    def protection(self):
        st, g = self.state, self.gstat
        n = len(self.store.enabled_apps())
        locks = self.store.active_locks()
        starting = time.time() - self.guard.launched_at < 6
        guard_has_locks = bool(g.get("alive")) and g.get("locks_active", 0) > 0

        def lock_report():
            denied = [e for e in g.get("denied", []) if any(l["exe"].lower() == e for l in locks)]
            until = max(float(l["until"]) for l in locks)
            from . import i18n
            from datetime import datetime
            when = i18n.fmt_when(datetime.fromtimestamp(until))
            if denied:
                return {"level": "partial", "title": "PARTIAL", "color": T.amber, "locked": True,
                        "detail": "Permission denied for locked app(s): " + ", ".join(denied[:3]) +
                                  ". They can still run."}
            return {"level": "locks", "title": "LOCKS ACTIVE", "color": T.cyan, "locked": True,
                    "detail": f"{len(locks)} app(s) are locked until {when}."}

        if st in ("idle", "completed"):
            if locks:
                if guard_has_locks:
                    return lock_report()
                if starting:
                    return {"level": "starting", "title": "STARTING", "color": T.violet, "locked": False,
                            "detail": "Starting the enforcement guard..."}
                return {"level": "failed", "title": "NOT ENFORCING", "color": T.red, "locked": False,
                        "detail": "Locks are set but the guard is not running. Locked apps are NOT blocked."}
            wins = [w for w in self.store.windows if w.get("enabled", True)]
            if wins:
                from . import rules
                from datetime import datetime
                active_now = rules.active_windows(wins, datetime.now())
                if active_now and not (g.get("alive") and g.get("windows", 0) > 0):
                    if starting:
                        return {"level": "starting", "title": "STARTING", "color": T.violet, "locked": False,
                                "detail": "Starting the enforcement guard..."}
                    return {"level": "failed", "title": "NOT ENFORCING", "color": T.red, "locked": False,
                            "detail": "Lock hours are active but the guard is not running. Games are NOT blocked."}
                if active_now:
                    return {"level": "hours", "title": "LOCK HOURS", "color": T.cyan, "locked": True,
                            "detail": "Lock hours are active. Blocked categories are closed automatically."}
            return {"level": "standby", "title": "STANDBY", "color": T.text2, "locked": False,
                    "detail": "No active session. Nothing is being blocked."}
        if st == "paused":
            if locks and guard_has_locks:
                return {"level": "paused", "title": "PAUSED", "color": T.amber, "locked": True,
                        "detail": f"Session blocking is suspended. {len(locks)} day-locked app(s) stay blocked."}
            return {"level": "paused", "title": "PAUSED", "color": T.amber, "locked": False,
                    "detail": "Blocking is suspended while the session is paused."}
        if n == 0 and not locks:
            return {"level": "norules", "title": "TIMER ONLY", "color": T.amber, "locked": False,
                    "detail": "No block rules are enabled, so no application is being blocked."}
        live = g.get("alive") and g.get("session_id") == self.session_id and g.get("mode") == "enforcing"
        if live:
            denied = g.get("denied", [])
            if denied:
                return {"level": "partial", "title": "PARTIAL", "color": T.amber, "locked": True,
                        "detail": f"Permission denied for {len(denied)} app(s): " + ", ".join(denied[:3]) +
                                  ". They can still run."}
            return {"level": "enforcing", "title": "ENFORCING", "color": T.cyan, "locked": True,
                    "detail": f"Guard process is terminating {max(n, len(locks))} blocked app(s)."}
        if starting:
            return {"level": "starting", "title": "STARTING", "color": T.violet, "locked": False,
                    "detail": "Starting the enforcement guard..."}
        return {"level": "failed", "title": "NOT ENFORCING", "color": T.red, "locked": False,
                "detail": "The enforcement guard is not running. Applications are NOT blocked."}

    def clock_text(self):
        if self.state in ("running", "paused"):
            return fmt_clock(self.remaining)
        if self.state == "completed":
            return "00:00"
        return fmt_clock(self.store.settings.get("default_minutes", 50) * 60)


class UpdateWorker(QThread):
    """Checks GitHub or downloads a verified release off the UI thread."""
    checked = Signal(object)
    progress = Signal(int)
    downloaded = Signal(str)
    failed = Signal(str)

    def __init__(self, mode, repo="", info=None, dest=None):
        super().__init__()
        self.mode, self.repo, self.info, self.dest = mode, repo, info, dest

    def run(self):
        try:
            if self.mode == "check":
                self.checked.emit(updater.check(self.repo))
            else:
                self.downloaded.emit(str(updater.download(self.info, self.dest, self.progress.emit)))
        except updater.UpdateError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")
