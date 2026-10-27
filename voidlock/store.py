"""Local persistence (JSON files) and derived statistics. No UI imports."""
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from .sounds import STYLE_ORDER

SCHEMA = 3
DATA_FILES = ["settings.json", "apps.json", "history.json", "schedule.json", "presets.json", "study.json", "classes.json"]
BACKUP_ONLY = ["points.json"]      # backed up for crash recovery, never restored/imported by the user
MAX_BACKUPS = 15


def default_home():
    env = os.environ.get("VOIDLOCK_HOME")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "VoidLock"
    return Path.home() / ".voidlock"


def read_json_checked(path, retries=4):
    """Returns (status, data). status: 'ok' | 'missing' | 'corrupt' | 'error'.
    'error' means the file exists but could not be read (for example another process holds it for a moment
    on Windows). It is NOT the same as 'missing': callers must never treat it as 'no data'."""
    last = None
    for attempt in range(retries):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return "ok", json.load(f)
        except FileNotFoundError:
            return "missing", None
        except ValueError:
            return "corrupt", None
        except OSError as e:               # PermissionError / sharing violation: retry briefly
            last = e
            time.sleep(0.04 * (attempt + 1))
    return "error", last


def read_json(path, default=None):
    status, data = read_json_checked(path)
    return data if status == "ok" else default


def write_json(path, data):
    """Atomic write so the guard never reads a half-written file. The temp name is unique per process, so the
    UI and the guard can never trample each other's temp file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        for attempt in range(8):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:  # Windows: reader holds the file for a moment
                time.sleep(0.03 * (attempt + 1))
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


CATEGORIES = ["Games", "Launchers", "Social", "Media", "Browsers", "Sites", "Other"]

# exe names are matched case-insensitively against running process names
DEFAULT_APPS = [
    ("eFootball", "eFootball.exe", "Games", True),
    ("Battlefield 2042", "BF2042.exe", "Games", True),
    ("Battlefield V", "bfv.exe", "Games", True),
    ("Battlefield 1", "bf1.exe", "Games", True),
    ("Counter-Strike 2", "cs2.exe", "Games", True),
    ("VALORANT", "VALORANT-Win64-Shipping.exe", "Games", True),
    ("League of Legends", "LeagueClient.exe", "Games", False),
    ("Fortnite", "FortniteClient-Win64-Shipping.exe", "Games", False),
    ("PUBG", "TslGame.exe", "Games", False),
    ("GTA V", "GTA5.exe", "Games", False),
    ("Steam", "steam.exe", "Launchers", True),
    ("Epic Games Launcher", "EpicGamesLauncher.exe", "Launchers", True),
    ("Discord", "Discord.exe", "Social", False),
    ("Telegram", "Telegram.exe", "Social", False),
    ("WhatsApp", "WhatsApp.exe", "Social", False),
    ("Spotify", "Spotify.exe", "Media", False),
    ("VLC media player", "vlc.exe", "Media", False),
    ("Google Chrome", "chrome.exe", "Browsers", False),
    ("Microsoft Edge", "msedge.exe", "Browsers", False),
    ("Firefox", "firefox.exe", "Browsers", False),
]

DEFAULT_SETTINGS = {
    "female_mascot": False,
    "daily_goal_min": 120,
    "default_minutes": 50,
    "strict_default": False,
    "emergency_cooldown": 30,
    "reduce_motion": "auto",     # auto | on | off
    "week_start": 5,             # 0=Mon ... 5=Sat, 6=Sun
    "language": "en",            # en | fa
    "theme": "void",             # see THEME_KEYS
    "sound": "soft",             # off | soft | bell
    "target_field": "",          # shown in the message when a blocked program is closed
    "exam_date": [1406, 4, 10],  # Jalali [year, month, day]
    "custom_message": "",
    "play_tracking": True,       # watch games during unlocked hours (needed for focus points)
    "points_per_day": 5,
    "streak_bonus": 10,          # extra points at every 7 clean days in a row
    "game_friday_only": True,    # the play pass (1.5-2 h of gaming) can only be used on Fridays
    "play_tolerance_min": 5,     # minutes of play that still count as a "clean" day
    "daily_tests_goal": 50,
    "report_name": "",           # student name printed on the study report
    "close_to_tray": True,       # the window's close button hides it in the tray (the program keeps running)
    "tray_at_login": False,      # start hidden in the tray when Windows starts (the window does NOT open)
    "tray_hint_shown": False,
    "update_check": True,
    "update_auto_install": True,
    "update_last_check": 0,
    "long_cooldown": 600,        # seconds to wait before a multi-day lock can be released early
    "last_subject": "",
    "recent_subjects": [],
}

DEFAULT_PRESETS = [
    {"id": "p25", "name": "Pomodoro", "minutes": 25, "strict": False},
    {"id": "p50", "name": "Deep Work", "minutes": 50, "strict": False},
    {"id": "p90", "name": "Marathon", "minutes": 90, "strict": False},
]

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def week_order(start):
    return [(start + i) % 7 for i in range(7)]


def uid():
    return uuid.uuid4().hex[:10]


THEME_KEYS = ("void", "candy", "ocean", "forest", "sunset", "midnight", "graphite", "paper", "mint")   # = theme.THEMES
_INT_RANGES = {
    "daily_goal_min": (15, 720), "default_minutes": (1, 480), "emergency_cooldown": (5, 300),
    "points_per_day": (1, 50), "streak_bonus": (0, 500), "play_tolerance_min": (0, 120),
    "daily_tests_goal": (5, 1000), "long_cooldown": (5, 3600),
}
_ENUMS = {"reduce_motion": ("auto", "on", "off"), "language": ("en", "fa"), "theme": THEME_KEYS,
          "sound": STYLE_ORDER, "week_start": (5, 6, 0)}
_BOOLS = ("female_mascot", "strict_default", "play_tracking", "game_friday_only", "update_check", "update_auto_install",
          "close_to_tray", "tray_at_login", "tray_hint_shown")
# never taken from an imported file: they decide where code comes from
_NOT_IMPORTED = ("update_last_check", "update_last_tag", "update_notified")


def sanitize_settings(s):
    """Hand-edited / imported / older settings can hold values the UI cannot show (it would crash while building the
    Settings page). Put every value back into its valid range. Unknown keys are kept."""
    out = dict(DEFAULT_SETTINGS)
    out.update(s if isinstance(s, dict) else {})
    for k, (lo, hi) in _INT_RANGES.items():
        try:
            out[k] = max(lo, min(hi, int(out[k])))
        except (TypeError, ValueError):
            out[k] = DEFAULT_SETTINGS[k]
    for k, allowed in _ENUMS.items():
        if out.get(k) not in allowed:
            out[k] = DEFAULT_SETTINGS[k]
    for k in _BOOLS:
        out[k] = bool(out.get(k))
    out.pop("update_repo", None)             # fixed in the program now (updater.REPO)
    for k in ("target_field", "custom_message", "last_subject", "report_name"):
        if not isinstance(out.get(k), str):
            out[k] = ""
    ex = out.get("exam_date")
    if not (isinstance(ex, (list, tuple)) and len(ex) == 3 and all(isinstance(x, int) and not isinstance(x, bool) for x in ex)
            and 1300 <= ex[0] <= 1500 and 1 <= ex[1] <= 12 and 1 <= ex[2] <= 31):
        out["exam_date"] = list(DEFAULT_SETTINGS["exam_date"])
    else:
        out["exam_date"] = list(ex)
    rs = out.get("recent_subjects")
    out["recent_subjects"] = [x for x in rs if isinstance(x, str)][:6] if isinstance(rs, list) else []
    try:
        out["update_last_check"] = float(out.get("update_last_check", 0))
    except (TypeError, ValueError):
        out["update_last_check"] = 0
    return out


def clean_apps(apps, dedupe=False):
    """Every app needs id / name / exe / category / enabled. Entries that cannot work are dropped."""
    out, seen = [], set()
    for a in apps if isinstance(apps, list) else []:
        if not isinstance(a, dict):
            continue
        exe = str(a.get("exe") or "").strip()
        if not exe or "/" in exe or "\\" in exe:
            continue
        if dedupe:
            if exe.lower() in seen:
                continue
            seen.add(exe.lower())
        d = dict(a)
        d["exe"] = exe
        d["name"] = str(a.get("name") or exe).strip()[:60] or exe
        d["category"] = a.get("category") if a.get("category") in CATEGORIES else "Other"
        d["enabled"] = bool(a.get("enabled"))
        d["custom"] = bool(a.get("custom"))
        d["path"] = a.get("path") if isinstance(a.get("path"), str) else ""
        d["id"] = str(a.get("id") or uid())
        if d.get("kind") not in (None, "site", "app"):
            d.pop("kind")
        out.append(d)
    return out


def clean_schedule(items):
    out = []
    for e in items if isinstance(items, list) else []:
        try:
            if not isinstance(e, dict):
                continue
            day = int(e["day"])
            h, m = str(e["time"]).split(":")
            h, m, mins = int(h), int(m), int(e["minutes"])
            if not (0 <= day <= 6 and 0 <= h <= 23 and 0 <= m <= 59 and mins >= 1):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        d = dict(e)
        d.update(day=day, time=f"{h:02d}:{m:02d}", minutes=mins)
        d.setdefault("id", uid())
        d.setdefault("subject", "")
        d.setdefault("enabled", True)
        out.append(d)
    return out


def clean_classes(items):
    """Weekly classes: {id, name, day 0-6 (Mon=0), time "HH:MM", minutes, remind (minutes before), enabled, place}."""
    out = []
    for c in items if isinstance(items, list) else []:
        try:
            if not isinstance(c, dict):
                continue
            day = int(c["day"])
            h, m = str(c["time"]).split(":")
            h, m = int(h), int(m)
            if not (0 <= day <= 6 and 0 <= h <= 23 and 0 <= m <= 59):
                continue
            name = str(c.get("name") or "").strip()[:40]
            if not name:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        d = dict(c)
        try:
            d["minutes"] = max(5, min(600, int(c.get("minutes", 90))))
            d["remind"] = max(0, min(180, int(c.get("remind", 15))))
        except (TypeError, ValueError):
            d["minutes"], d["remind"] = 90, 15
        d.update(name=name, day=day, time=f"{h:02d}:{m:02d}", enabled=bool(c.get("enabled", True)),
                 place=str(c.get("place") or "")[:40])
        d["id"] = str(c.get("id") or uid())
        d.setdefault("rem_done", "")
        d.setdefault("start_done", "")
        out.append(d)
    return out


def clean_presets(items):
    out = []
    for p in items if isinstance(items, list) else []:
        try:
            if not isinstance(p, dict):
                continue
            d = dict(p)
            d["minutes"] = max(1, min(480, int(p["minutes"])))
            d["name"] = str(p.get("name") or f"{d['minutes']} min")[:24]
            d["strict"] = bool(p.get("strict"))
            d["id"] = str(p.get("id") or uid())
        except (KeyError, TypeError, ValueError):
            continue
        out.append(d)
    return out


def clean_history(items):
    out = []
    for r in items if isinstance(items, list) else []:
        try:
            if not isinstance(r, dict):
                continue
            d = dict(r)
            d["start"] = float(r["start"])
            d["focus_sec"] = max(0, int(r.get("focus_sec", 0)))
            d["planned_min"] = max(0, int(r.get("planned_min", 0)))
            d.setdefault("status", "ended")
        except (KeyError, TypeError, ValueError):
            continue
        out.append(d)
    return out


class Store:
    """JSON persistence. Data lives in the user profile (never inside the program folder), so
    updating or rebuilding the app never resets it. Every start also writes a rolling backup,
    and corrupt files are quarantined and restored from the newest backup instead of reset."""

    def __init__(self, home=None, service=False):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.service = service              # the guard process reads only; it never migrates/backs up
        self.p_settings = self.home / "settings.json"
        self.p_apps = self.home / "apps.json"
        self.p_history = self.home / "history.json"
        self.p_schedule = self.home / "schedule.json"
        self.p_presets = self.home / "presets.json"
        self.p_classes = self.home / "classes.json"
        self.p_meta = self.home / "meta.json"
        self.p_session = self.home / "session.json"   # UI -> guard
        self.p_status = self.home / "status.json"     # guard -> UI
        self.p_locks = self.home / "locks.json"       # multi-day locks (UI + guard)
        self.p_locks_guard = self.home / "locks_guard.json"
        self.p_release = self.home / "release.json"   # UI -> guard: release request
        self.p_windows = self.home / "windows.json"   # lock hours (UI adds, guard keeps a copy)
        self.p_windows_guard = self.home / "windows_guard.json"
        self.p_points = self.home / "points.json"     # focus points ledger, tickets, rewards (UI)
        self.p_pass = self.home / "pass.json"         # active play pass (UI -> guard)
        self.p_play = self.home / "play.json"         # play time per day (guard -> UI)
        self.p_attempts = self.home / "attempts.json" # blocked launch attempts (guard -> UI)
        self.p_events = self.home / "events.json"     # "program was closed" events (guard -> UI)
        self.p_study = self.home / "study.json"       # subjects, study entries, tests, to-dos (UI)
        self.p_admin_flag = self.home / "admin_guard.flag"
        self.p_ui_alive = self.home / "ui_alive.json"
        self.p_recover = self.home / "RECOVER"
        self.p_log = self.home / "guard.log"
        self.backup_dir = self.home / "backups"
        self.notices = []                   # human-readable things that happened while loading
        self.unreadable = set()             # files that exist but could not be read right now (never overwritten)
        self.load_error = None
        self.settings = dict(DEFAULT_SETTINGS)
        self.apps, self.history, self.schedule, self.presets, self.locks = [], [], [], [], []
        self.classes = []
        self.windows, self.study = [], {}
        if not service:
            self._import_legacy_if_first_run()
        self.load()
        if not service:
            self._migrate()
            self.snapshot("start")

    # ---- robust reading
    def _read(self, path, kind):
        """Returns data of type `kind`, or None when missing / unreadable. Only genuinely corrupt files are quarantined
        and restored from the newest backup that has a valid copy. A file that is merely locked for a moment is left
        alone (it used to be treated as corrupt, which replaced fresh data with an old backup)."""
        status, data = read_json_checked(path)
        if status in ("missing", "error"):
            if status == "error":
                self.unreadable.add(path.name)
            return None
        if status == "ok" and isinstance(data, kind):
            return data
        if self.service:
            return None
        try:
            bad = path.with_name(path.name + f".corrupt-{int(time.time())}")
            path.replace(bad)
        except OSError:
            pass
        for b in self.list_backups():
            cand = b["path"] / path.name
            data = read_json(cand)
            if isinstance(data, kind):
                write_json(path, data)
                self.notices.append(f"{path.name} was damaged and was restored from backup {b['name']}.")
                return data
        self.notices.append(f"{path.name} was damaged and could not be restored; defaults were used.")
        return None

    def load(self):
        s = self._read(self.p_settings, dict)
        self.settings = sanitize_settings(s)
        apps = self._read(self.p_apps, list)
        if not apps:
            apps = [self._default_app(n, e, c, en) for n, e, c, en in DEFAULT_APPS]
            # defaults are only written when there is really no file (never over one that was just locked)
            if not self.service and "apps.json" not in self.unreadable and not self.p_apps.exists():
                write_json(self.p_apps, apps)
        elif not self.service:
            apps = clean_apps(apps)
        self.apps = apps
        self.history = clean_history(self._read(self.p_history, list) or [])
        self.schedule = clean_schedule(self._read(self.p_schedule, list) or [])
        self.classes = clean_classes(self._read(self.p_classes, list) or [])
        pre = clean_presets(self._read(self.p_presets, list))
        if not pre:
            pre = [dict(x) for x in DEFAULT_PRESETS]
            if not self.service and "presets.json" not in self.unreadable and not self.p_presets.exists():
                write_json(self.p_presets, pre)
        self.presets = pre
        st = self._read(self.p_study, dict)
        self.study = st if st else {}
        self.refresh_locks()
        self.refresh_windows()

    @staticmethod
    def _default_app(n, e, c, en):
        return {"id": uid(), "name": n, "exe": e, "category": c, "enabled": en, "custom": False, "path": ""}

    # ---- migration (additive only: never removes or resets user data)
    def _migrate(self):
        meta = read_json(self.p_meta, {}) or {}
        seen = set(meta.get("seen_defaults", []))
        have = {a["exe"].lower() for a in self.apps}
        if not meta:   # first run of a version with meta: treat current defaults as already seen
            seen = {e.lower() for _n, e, _c, _en in DEFAULT_APPS}
        added = 0
        for n, e, c, en in DEFAULT_APPS:
            if e.lower() not in seen and e.lower() not in have:
                self.apps.append(self._default_app(n, e, c, False))   # new defaults arrive switched off
                added += 1
            seen.add(e.lower())
        for a in self.apps:   # fill fields added by newer versions
            a.setdefault("id", uid()); a.setdefault("custom", False); a.setdefault("path", "")
        if added:
            self.save_apps()
        write_json(self.p_meta, {"schema": SCHEMA, "seen_defaults": sorted(seen),
                                 "updated": time.time()})

    def _import_legacy_if_first_run(self):
        if self.p_settings.exists() or self.p_apps.exists() or self.p_history.exists():
            return
        cands = [Path.home() / ".voidlock", Path.home() / "VoidLock"]
        for var in ("LOCALAPPDATA", "PROGRAMDATA"):
            if os.environ.get(var):
                cands.append(Path(os.environ[var]) / "VoidLock")
        for c in cands:
            if c.resolve() != self.home.resolve() and any((c / f).exists() for f in DATA_FILES):
                for f in DATA_FILES:
                    if (c / f).exists():
                        shutil.copy2(c / f, self.home / f)
                self.notices.append(f"Imported your previous data from {c}.")
                return

    # ---- backups
    def _digest(self, folder):
        h = hashlib.sha1()
        for f in DATA_FILES + BACKUP_ONLY:
            p = Path(folder) / f
            if p.exists():
                h.update(f.encode()); h.update(p.read_bytes())
        return h.hexdigest()

    def list_backups(self):
        out = []
        if self.backup_dir.exists():
            for d in sorted(self.backup_dir.iterdir(), reverse=True):
                if d.is_dir():
                    out.append({"name": d.name, "path": d, "mtime": d.stat().st_mtime})
        return out

    def snapshot(self, reason="manual", force=False):
        """Copy the data files into backups/<timestamp>. Skipped when nothing changed."""
        try:
            last = self.list_backups()
            if not force and last and self._digest(last[0]["path"]) == self._digest(self.home):
                return None
            d = self.backup_dir / (time.strftime("%Y%m%d-%H%M%S") + "-" + reason)
            d.mkdir(parents=True, exist_ok=True)
            for f in DATA_FILES + BACKUP_ONLY:
                if (self.home / f).exists():
                    shutil.copy2(self.home / f, d / f)
            for old in self.list_backups()[MAX_BACKUPS:]:
                shutil.rmtree(old["path"], ignore_errors=True)
            return d.name
        except OSError:
            return None

    def restore_backup(self, name):
        src = self.backup_dir / name
        if not src.is_dir():
            return False
        self.snapshot("before-restore", force=True)
        wait = int(self.settings.get("long_cooldown", 600))
        for f in DATA_FILES:
            if (src / f).exists():
                shutil.copy2(src / f, self.home / f)
        self.load()
        self._keep_commitments(wait)
        return True

    def export_all(self):
        return {"voidlock_export": SCHEMA, "settings": self.settings, "apps": self.apps,
                "history": self.history, "schedule": self.schedule, "presets": self.presets, "study": self.study,
                "classes": self.classes}

    def commitments_active(self):
        """True while a day lock or lock hours exist: things that must not be made easier from the settings."""
        return bool(self.active_locks() or self.windows)

    def _keep_commitments(self, wait):
        """A restore / import brings back older settings. While locks exist the release wait may only grow."""
        if self.commitments_active() and int(self.settings.get("long_cooldown", 600)) < int(wait):
            self.settings["long_cooldown"] = int(wait)
            self.save_settings()

    def import_all(self, data):
        """Replaces data from an export. Locks are never imported (they cannot be removed this way). Everything is
        validated first; the update source is never taken from a file (it decides where program code comes from)."""
        if not isinstance(data, dict) or "voidlock_export" not in data:
            return False
        self.snapshot("before-import", force=True)
        wait = int(self.settings.get("long_cooldown", 600))
        if isinstance(data.get("settings"), dict):
            keep = {k: self.settings.get(k) for k in _NOT_IMPORTED if k in self.settings}
            self.settings = sanitize_settings({**DEFAULT_SETTINGS, **data["settings"], **keep})
        if isinstance(data.get("apps"), list):
            apps = clean_apps(data["apps"], dedupe=True)
            if apps:
                self.apps = apps
        if isinstance(data.get("history"), list):
            self.history = clean_history(data["history"])
        if isinstance(data.get("schedule"), list):
            self.schedule = clean_schedule(data["schedule"])
        if isinstance(data.get("classes"), list):
            self.classes = clean_classes(data["classes"])
        if isinstance(data.get("presets"), list):
            pre = clean_presets(data["presets"])
            if pre:
                self.presets = pre
        if isinstance(data.get("study"), dict):
            self.study = data["study"]
        self._keep_commitments(wait)
        for f in (self.save_study, self.save_settings, self.save_apps, self.save_history, self.save_schedule, self.save_presets,
                  self.save_classes):
            f()
        return True

    # ---- multi-day locks
    def _read_list(self, path, key, current):
        """Lock files are shared with the guard. If one is momentarily unreadable we keep the list we already have
        instead of pretending there are no locks (which used to make the next write drop the other locks)."""
        status, data = read_json_checked(path)
        if status == "missing":
            return []
        if status == "ok":
            return data.get(key, []) if isinstance(data, dict) and isinstance(data.get(key, []), list) else []
        return current

    def refresh_locks(self):
        self.locks = self._read_list(self.p_locks, "locks", self.locks)

    def active_locks(self, now=None):
        now = now or time.time()
        return [l for l in self.locks if float(l.get("until", 0)) > now]

    def lock_for(self, exe, now=None):
        exe = exe.lower()
        return next((l for l in self.active_locks(now) if l["exe"].lower() == exe), None)

    def refresh_windows(self):
        self.windows = self._read_list(self.p_windows, "windows", self.windows)

    def add_window(self, w):
        """Lock hours can be added freely; removing/shortening them goes through the release flow."""
        self.refresh_windows()
        w = dict(w)
        w.setdefault("id", uid())
        w.setdefault("enabled", True)
        w.setdefault("created", time.time())
        self.windows.append(w)
        write_json(self.p_windows, {"version": 1, "windows": self.windows})
        return w

    def add_lock(self, exe, name, until):
        """Create or EXTEND a lock. A lock can never be shortened from here."""
        self.refresh_locks()
        cur = next((l for l in self.locks if l["exe"].lower() == exe.lower()), None)
        if cur:
            cur["until"] = max(float(cur["until"]), float(until))
            cur["name"] = name
        else:
            self.locks.append({"id": uid(), "exe": exe, "name": name, "until": float(until),
                               "created": time.time()})
        write_json(self.p_locks, {"version": 1, "locks": self.locks})

    def save_settings(self):
        write_json(self.p_settings, self.settings)

    def save_apps(self):
        write_json(self.p_apps, self.apps)

    def save_history(self):
        write_json(self.p_history, self.history)

    def save_schedule(self):
        write_json(self.p_schedule, self.schedule)

    def save_classes(self):
        write_json(self.p_classes, self.classes)

    def save_presets(self):
        write_json(self.p_presets, self.presets)

    def save_study(self):
        write_json(self.p_study, self.study)

    # ---- apps
    def enabled_apps(self):
        return [a for a in self.apps if a.get("enabled")]

    def find_exe(self, exe):
        exe = exe.strip().lower()
        return next((a for a in self.apps if a["exe"].lower() == exe), None)

    # ---- history
    def add_record(self, rec):
        self.history.append(rec)
        self.history = self.history[-2000:]
        self.save_history()

    def has_record(self, session_id):
        return any(r.get("id") == session_id for r in self.history)

    def remember_subject(self, subject):
        subject = (subject or "").strip()
        if not subject:
            return
        rs = [s for s in self.settings.get("recent_subjects", []) if s != subject]
        self.settings["recent_subjects"] = ([subject] + rs)[:6]
        self.settings["last_subject"] = subject
        self.save_settings()

    def reset_history(self):
        self.history = []
        self.save_history()

    def reset_all(self):
        self.snapshot("before-reset", force=True)
        for p in (self.p_settings, self.p_apps, self.p_history, self.p_schedule, self.p_presets, self.p_study,
                  self.p_classes):
            try:
                p.unlink()
            except OSError:
                pass
        self.load()


# ------------------------------------------------------------------ statistics
def _day(rec):
    try:
        return datetime.fromtimestamp(rec["start"]).date()
    except Exception:
        return None


def focus_by_day(history):
    out = {}
    for r in history:
        d = _day(r)
        if d:
            try:
                out[d] = out.get(d, 0) + int(r.get("focus_sec", 0))
            except (TypeError, ValueError):
                pass
    return out


def today_focus_sec(history):
    return focus_by_day(history).get(date.today(), 0)


def last_days(history, n=7):
    by = focus_by_day(history)
    today = date.today()
    days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
    return days, [by.get(d, 0) for d in days]


def completed_count(history, days=None):
    n = 0
    cutoff = date.today() - timedelta(days=days - 1) if days else None
    for r in history:
        if r.get("status") != "completed":
            continue
        d = _day(r)
        if cutoff is None or (d and d >= cutoff):
            n += 1
    return n


def streak_days(history, min_sec=600):
    by = focus_by_day(history)
    d = date.today()
    if by.get(d, 0) < min_sec:
        d -= timedelta(days=1)  # today may still be in progress
    n = 0
    while by.get(d, 0) >= min_sec:
        n += 1
        d -= timedelta(days=1)
    return n


def fmt_hm(sec):
    sec = int(sec)
    h, m = divmod(sec // 60, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def fmt_clock(sec):
    sec = max(0, int(round(sec)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
