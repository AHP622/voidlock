"""Pages: Study Sessions, Schedule, Analytics, Settings."""
import csv
import os
import sys
import time
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QSlider, QVBoxLayout, QWidget)

from . import classes as classtools, i18n, messages, rules, sounds
from .guard import emergency_recover
from .pages_a import Page
from .store import completed_count, fmt_hm, last_days, streak_days, today_focus_sec, uid, week_order
from .report_ui import export_report
from .theme import THEME_NAMES, THEME_ORDER
from .theme import Motion, T
from .mascot import BlockPopup, Heatmap
from .study import attempts_report, play_day
from .viz import BarChart, EmptyState, IconTile
from .widgets import (AC, Button, Card, Chip, ChipGrid, Divider, ThemePicker, Pill, ProgressBar, Segmented, Stepper, Ticker, Toggle,
                      clear_layout, label, reveal)


def section_title(text):
    return label(text.upper(), 11, QFont.Weight.Bold, T.text3, spacing=2.4)


def setting_row(title, desc, control):
    r = QHBoxLayout()
    r.setSpacing(16)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(label(title, 14, QFont.Weight.DemiBold))
    if desc:
        col.addWidget(label(desc, 12, color=T.text3, wrap=True))
    r.addLayout(col, 1)
    r.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return r


def setting_block(title, desc, control):
    """Title and description on top, a wide control (theme cards, many chips) underneath."""
    col = QVBoxLayout()
    col.setSpacing(6)
    col.addWidget(label(title, 14, QFont.Weight.DemiBold))
    if desc:
        col.addWidget(label(desc, 12, color=T.text3, wrap=True))
    col.addWidget(control)
    return col


# ============================================================ STUDY SESSIONS
class PresetRow(Card):
    def __init__(self, preset, on_load, on_delete):
        super().__init__(pad=12, hover=True)
        self.lay.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(IconTile(preset["name"], T.violet, 36))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(preset["name"], 14, QFont.Weight.DemiBold))
        col.addWidget(label(f"{preset['minutes']} min" + (" · strict" if preset.get("strict") else ""), 12,
                            color=T.text3, mono=True))
        row.addLayout(col, 1)
        b = Button("Load", "soft", height=32)
        b.setToolTip("Use this preset in the session configuration")
        b.clicked.connect(lambda: on_load(preset))
        d = Button("", "icon", "trash", "Delete preset", square=32)
        d.clicked.connect(lambda: on_delete(preset))
        row.addWidget(b)
        row.addWidget(d)
        self.lay.addLayout(row)


class SessionsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Study Sessions", "Configure and launch a focus session")
        row = QHBoxLayout()
        row.setSpacing(18)
        self.body.addLayout(row)
        self.cfg = Card(pad=24, accent=T.cyan)
        self.cfg.lay.setSpacing(14)
        self.cfg.lay.addWidget(section_title("Session configuration"))
        self.cfg.lay.addWidget(label("Subject", 13, QFont.Weight.DemiBold))
        self.subject = QLineEdit()
        self.subject.setPlaceholderText("What are you studying? e.g. Calculus, Physics…")
        self.subject.setMaxLength(40)
        self.cfg.lay.addWidget(self.subject)
        self.recent_row = QHBoxLayout()
        self.recent_row.setSpacing(8)
        self.cfg.lay.addLayout(self.recent_row)
        self.cfg.lay.addWidget(Divider())
        drow = QHBoxLayout()
        drow.addWidget(label("Duration", 13, QFont.Weight.DemiBold), 1)
        self.stepper = Stepper(ctx.plan["minutes"], 1, 480, 1, " min")
        drow.addWidget(self.stepper)
        self.cfg.lay.addLayout(drow)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 96)
        self.slider.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.slider.setToolTip("Drag to choose a length (5-minute steps)")
        self.cfg.lay.addWidget(self.slider)
        self.cfg.lay.addWidget(Divider())
        self.strict = Toggle(ctx.plan["strict"], tip="Disables pause and early end")
        self.cfg.lay.addLayout(setting_row("Strict mode", "Pause and End are disabled. Only the Emergency unlock "
                                           "(typed phrase + cooldown) can stop the session. Rules are locked.", self.strict))
        self.summary = label("", 12, color=T.text2, wrap=True)
        self.cfg.lay.addWidget(self.summary)
        self.b_start = Button("Start session", "primary", "play", height=48)
        self.cfg.lay.addWidget(self.b_start)
        row.addWidget(self.cfg, 3)

        right = QVBoxLayout()
        right.setSpacing(18)
        self.pre_card = Card(pad=20)
        h = QHBoxLayout()
        h.addWidget(section_title("Saved presets"))
        h.addStretch(1)
        self.b_save = Button("Save current", "ghost", "plus", height=32)
        h.addWidget(self.b_save)
        self.pre_card.lay.addLayout(h)
        self.pre_box = QVBoxLayout()
        self.pre_box.setSpacing(10)
        self.pre_card.lay.addLayout(self.pre_box)
        right.addWidget(self.pre_card)
        self.tip = Card(pad=18)
        self.tip.lay.addWidget(section_title("How blocking works"))
        self.tip.lay.addWidget(label(
            "While a session runs, a separate guard process closes every blocked program the moment it starts. "
            "The status always shows what the guard actually reports - if it cannot block something, you will "
            "see it here instead of a false sense of safety.", 12, color=T.text2, wrap=True))
        right.addWidget(self.tip)
        right.addStretch(1)
        row.addLayout(right, 2)
        self.body.addStretch(1)
        self._reveal = [self.cfg, self.pre_card, self.tip]

        self.subject.setText(ctx.plan.get("subject", ""))
        self.stepper.valueChanged.connect(self._from_stepper)
        self.slider.valueChanged.connect(lambda v: self.stepper.set_value(v * 5))
        self.strict.toggled.connect(self._changed)
        self.subject.textChanged.connect(self._changed)
        self.b_start.clicked.connect(self._start)
        self.b_save.clicked.connect(self._save_preset)
        ctx.session.changed.connect(self._lock_ui)
        self._sync_slider()

    def _sync_slider(self):
        self.slider.blockSignals(True)
        self.slider.setValue(self.stepper.value() // 5)
        self.slider.blockSignals(False)

    def _from_stepper(self, v):
        self._sync_slider()
        self._changed()

    def _changed(self, *a):
        p = self.ctx.plan
        p["minutes"], p["subject"], p["strict"] = self.stepper.value(), self.subject.text().strip(), self.strict.isChecked()
        n = len(self.ctx.store.enabled_apps())
        self.summary.setText(f"{p['minutes']} minutes · {n} application(s) will be blocked"
                             + (" · strict mode" if p["strict"] else "") +
                             ("" if n else "  -  no rules enabled: this would be a timer only."))
        self.ctx.session.changed.emit()

    def _lock_ui(self):
        busy = self.ctx.session.active
        self.b_start.setEnabled(not busy)
        self.b_start.setText("Session in progress" if busy else "Start session")

    def _start(self):
        self._changed()
        if self.ctx.start_session(self.stepper.value(), self.subject.text().strip(), self.strict.isChecked()):
            self.ctx.goto("overview")

    def _load(self, pr):
        self.stepper.set_value(pr["minutes"])
        self.strict.set_silent(bool(pr.get("strict")))
        self._changed()
        self.ctx.toast(f"Loaded “{pr['name']}”.", "info")

    def _delete(self, pr):
        if not self.ctx.confirm("Delete preset?", f"“{pr['name']}” will be removed.", "Delete", True, "trash"):
            return
        self.ctx.store.presets = [p for p in self.ctx.store.presets if p["id"] != pr["id"]]
        self.ctx.store.save_presets()
        self.refresh()
        self.ctx.presets_changed()

    def _save_preset(self):
        ed = QLineEdit()
        ed.setPlaceholderText("Preset name, e.g. Evening revision")
        ed.setMaxLength(24)
        m = self.ctx.new_modal().build("Save preset", f"{self.stepper.value()} minutes"
                                      + (" · strict" if self.strict.isChecked() else ""),
                                      ed, "Save", validator=lambda: bool(ed.text().strip()), icon="plus")
        ed.textChanged.connect(lambda _t: m.revalidate())
        if m.exec_modal():
            self.ctx.store.presets.append({"id": uid(), "name": ed.text().strip(), "minutes": self.stepper.value(),
                                           "strict": self.strict.isChecked()})
            self.ctx.store.save_presets()
            self.refresh()
            self.ctx.presets_changed()
            self.ctx.toast("Preset saved.", "success")

    def refresh(self):
        clear_layout(self.pre_box)
        pres = self.ctx.store.presets
        if not pres:
            self.pre_box.addWidget(EmptyState("sessions", "No presets", "Save your current configuration to reuse it "
                                                                         "with one click."))
        for pr in pres:
            self.pre_box.addWidget(PresetRow(pr, self._load, self._delete))
        clear_layout(self.recent_row)
        for s in self.ctx.store.settings.get("recent_subjects", [])[:4]:
            c = Chip(s, color=T.violet)
            c.clicked.connect(lambda _=False, s=s: self.subject.setText(s))
            self.recent_row.addWidget(c)
        self.recent_row.addStretch(1)
        self._lock_ui()
        self._changed()


# ============================================================ SCHEDULE
class DayChips(QWidget):
    """Weekday chips. multi=True lets several days be ticked (a session / class can be created for many days at once)."""
    changed = Signal()

    def __init__(self, week_start, days, multi=True):
        super().__init__()
        self.multi = multi
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.chips = {}
        for d in week_order(week_start):
            c = Chip(i18n.day_name(d, True) if i18n.is_fa() else i18n.day_name(d))
            c.set_checked_silent(d in days)
            c.toggled.connect(lambda on, d=d: self._toggled(d, on))
            lay.addWidget(c)
            self.chips[d] = c
        lay.addStretch(1)

    def _toggled(self, d, on):
        if not self.multi and on:
            for k, c in self.chips.items():
                if k != d:
                    c.set_checked_silent(False)
        self.changed.emit()

    def values(self):
        return [d for d, c in self.chips.items() if c.isChecked()]


class _TimeRows:
    """Start time + duration rows shared by the session and class forms."""

    def _time_rows(self, lay, entry, dur_max=480):
        t = QHBoxLayout()
        t.addWidget(label("Start time", 13, QFont.Weight.DemiBold), 1)
        h, m = [int(x) for x in entry["time"].split(":")]
        self.hh = Stepper(h, 0, 23, 1, "h")
        self.mm = Stepper(m, 0, 55, 5, "m")
        t.addWidget(self.hh)
        t.addWidget(self.mm)
        lay.addLayout(t)
        d = QHBoxLayout()
        d.addWidget(label("Duration", 13, QFont.Weight.DemiBold), 1)
        self.dur = Stepper(entry["minutes"], 1 if dur_max <= 480 else 5, dur_max, 5 if dur_max > 480 else 1, " min")
        d.addWidget(self.dur)
        lay.addLayout(d)
        for w in (self.hh, self.mm, self.dur):
            w.valueChanged.connect(lambda _v: self.changed.emit())

    def _warn_label(self, lay):
        self.warn = label("", 12, color=T.amber, wrap=True)
        self.warn.setVisible(False)
        lay.addWidget(self.warn)

    def _show_overlaps(self, classes, sessions, entry):
        days = self.days.values()
        hits = []
        t = f"{self.hh.value():02d}:{self.mm.value():02d}"
        for d in days:
            for name, when, kind in classtools.overlap_names(classes, sessions, d, t, self.dur.value(), entry.get("id")):
                hits.append(f"{name} ({i18n.digits(when)})")
        self.warn.setVisible(bool(hits))
        if hits:
            self.warn.setText(f"Overlaps with: {', '.join(dict.fromkeys(hits))}")


class ScheduleForm(QWidget, _TimeRows):
    changed = Signal()

    def __init__(self, entry, week_start, classes=(), sessions=()):
        super().__init__()
        self.deleted = False
        self._entry, self._classes, self._sessions = entry, list(classes), list(sessions)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(label("DAYS", 10, QFont.Weight.Bold, T.text3, spacing=2))
        self.days = DayChips(week_start, [entry["day"]], multi=True)
        lay.addWidget(self.days)
        self._time_rows(lay, entry)
        self.subject = QLineEdit(entry.get("subject", ""))
        self.subject.setPlaceholderText("Subject (optional)")
        self.subject.setMaxLength(40)
        lay.addWidget(self.subject)
        a = QHBoxLayout()
        a.addWidget(label("Start automatically", 13, QFont.Weight.DemiBold), 1)
        self.auto = Toggle(bool(entry.get("auto_start", False)))
        self.auto.setToolTip("Starts the session by itself when it is due (no question). Blocking begins right away.")
        a.addWidget(self.auto)
        lay.addLayout(a)
        e = QHBoxLayout()
        e.addWidget(label("Enabled", 13, QFont.Weight.DemiBold), 1)
        self.enabled = Toggle(entry.get("enabled", True))
        e.addWidget(self.enabled)
        lay.addLayout(e)
        self._warn_label(lay)
        self.b_del = Button("Delete this entry", "danger", "trash", height=36)
        lay.addWidget(self.b_del)
        self.b_del.setVisible(bool(entry.get("id")))
        self.days.changed.connect(self.changed.emit)
        self.changed.connect(lambda: self._show_overlaps(self._classes, self._sessions, self._entry))
        self.changed.emit()

    def valid(self):
        return bool(self.days.values())

    def values(self):
        return {"days": self.days.values(), "time": f"{self.hh.value():02d}:{self.mm.value():02d}",
                "minutes": self.dur.value(), "subject": self.subject.text().strip(), "enabled": self.enabled.isChecked(),
                "auto_start": self.auto.isChecked()}


class ClassForm(QWidget, _TimeRows):
    """Body of the 'Add class' dialog: a weekly class with a reminder some minutes before it starts."""
    changed = Signal()

    def __init__(self, entry, week_start, classes=(), sessions=()):
        super().__init__()
        self.deleted = False
        self._entry, self._classes, self._sessions = entry, list(classes), list(sessions)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        self.name = QLineEdit(entry.get("name", ""))
        self.name.setPlaceholderText("Class name, e.g. Math")
        self.name.setMaxLength(40)
        lay.addWidget(self.name)
        self.place = QLineEdit(entry.get("place", ""))
        self.place.setPlaceholderText("Place or teacher (optional)")
        self.place.setMaxLength(40)
        lay.addWidget(self.place)
        lay.addWidget(label("DAYS", 10, QFont.Weight.Bold, T.text3, spacing=2))
        self.days = DayChips(week_start, [entry["day"]], multi=True)
        lay.addWidget(self.days)
        self._time_rows(lay, entry, dur_max=600)
        r = QHBoxLayout()
        r.addWidget(label("Remind me before", 13, QFont.Weight.DemiBold), 1)
        self.remind = Stepper(int(entry.get("remind", 15)), 0, 120, 5, " min")
        self.remind.setToolTip("0 = no reminder")
        r.addWidget(self.remind)
        lay.addLayout(r)
        e = QHBoxLayout()
        e.addWidget(label("Enabled", 13, QFont.Weight.DemiBold), 1)
        self.enabled = Toggle(entry.get("enabled", True))
        e.addWidget(self.enabled)
        lay.addLayout(e)
        self._warn_label(lay)
        self.b_del = Button("Delete this class", "danger", "trash", height=36)
        lay.addWidget(self.b_del)
        self.b_del.setVisible(bool(entry.get("id")))
        self.name.textChanged.connect(lambda _t: self.changed.emit())
        self.days.changed.connect(self.changed.emit)
        self.changed.connect(lambda: self._show_overlaps(self._classes, self._sessions, self._entry))

    def valid(self):
        return bool(self.name.text().strip()) and bool(self.days.values())

    def values(self):
        return {"days": self.days.values(), "name": self.name.text().strip(), "place": self.place.text().strip(),
                "time": f"{self.hh.value():02d}:{self.mm.value():02d}", "minutes": self.dur.value(),
                "remind": self.remind.value(), "enabled": self.enabled.isChecked()}


def apply_days(items, entry, values, make):
    """Create / update entries for the ticked days. `entry` is the one being edited (or None when new).
    If its own day is still ticked it keeps that day, otherwise it moves to the first ticked day; every further ticked
    day gets a copy. Returns (created, updated)."""
    days = list(values["days"])
    base = {k: v for k, v in values.items() if k != "days"}
    created = updated = 0
    if entry is not None and entry in items:
        mine = entry["day"] if entry["day"] in days else days[0]
        old_time = (entry["day"], entry["time"])
        entry.update(base)
        entry["day"] = mine
        if (entry["day"], entry["time"]) != old_time:
            entry["last_fired"] = ""
            entry["rem_done"] = entry["start_done"] = ""
        updated = 1
        days = [d for d in days if d != mine]
    for d in days:
        items.append(make(d, base))
        created += 1
    return created, updated


class WindowForm(QWidget):
    """Body of the 'Add lock hours' dialog."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Name, e.g. School days")
        self.name.setMaxLength(28)
        lay.addWidget(self.name)
        lay.addWidget(label("DAYS", 10, QFont.Weight.Bold, T.text3, spacing=2))
        dr = QHBoxLayout()
        dr.setSpacing(6)
        self.day_chips = {}
        from .widgets import Chip
        for d in (5, 6, 0, 1, 2, 3, 4):
            c = Chip(i18n.day_name(d))
            c.set_checked_silent(d != 4)
            c.toggled.connect(lambda _c: self.changed.emit())
            dr.addWidget(c)
            self.day_chips[d] = c
        dr.addStretch(1)
        lay.addLayout(dr)
        for key, text, h, m in (("start", "From", 8, 0), ("end", "Until", 22, 0)):
            r = QHBoxLayout()
            r.addWidget(label(text, 13, QFont.Weight.DemiBold), 1)
            hh, mm = Stepper(h, 0, 23, 1, "h"), Stepper(m, 0, 55, 5, "m")
            setattr(self, key + "_h", hh)
            setattr(self, key + "_m", mm)
            r.addWidget(hh)
            r.addWidget(mm)
            lay.addLayout(r)
        lay.addWidget(label("CLOSE THESE CATEGORIES", 10, QFont.Weight.Bold, T.text3, spacing=2))
        cr = QHBoxLayout()
        cr.setSpacing(6)
        self.cat_chips = {}
        for cat in ("Games", "Launchers", "Social", "Media", "Sites"):
            c = Chip(cat, color=T.CATEGORY.get(cat, T.cyan))
            c.set_checked_silent(cat in ("Games", "Launchers"))
            c.toggled.connect(lambda _c: self.changed.emit())
            cr.addWidget(c)
            self.cat_chips[cat] = c
        cr.addStretch(1)
        lay.addLayout(cr)
        lay.addWidget(label("Outside these hours the apps are free to play. Lock hours can be added any time, but "
                            "removing them needs the release phrase and a wait.", 12, color=T.text3, wrap=True))

    def valid(self):
        return any(c.isChecked() for c in self.day_chips.values()) and any(c.isChecked() for c in self.cat_chips.values())

    def values(self):
        days = sorted(d for d, c in self.day_chips.items() if c.isChecked())
        cats = [k for k, c in self.cat_chips.items() if c.isChecked()]
        nm = self.name.text().strip() or "Lock hours"
        return {"name": nm, "days": days, "categories": cats, "enabled": True,
                "start": f"{self.start_h.value():02d}:{self.start_m.value():02d}",
                "end": f"{self.end_h.value():02d}:{self.end_m.value():02d}"}


def days_text(days, week_start):
    ds = set(days)
    if len(ds) == 7:
        return i18n.tr("Every day")
    order = [d for d in week_order(week_start) if d in ds]
    return "، ".join(i18n.day_name(d) for d in order) if i18n.is_fa() else ", ".join(i18n.day_name(d) for d in order)


class EntryChip(Card):
    """One block in the weekly grid: a study session (cyan) or a class (violet)."""

    def __init__(self, e, on_click, kind="session"):
        super().__init__(pad=10, hover=True)
        self.e, self._cb = e, on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lay.setSpacing(1)
        self.setToolTip("Click to edit")
        off = not e.get("enabled", True)
        col = T.text3 if off else (T.violet if kind == "class" else T.cyan)
        self.lay.addWidget(label(e["time"], 15, QFont.Weight.DemiBold, col, mono=True))
        extra = " · off" if off else (" · auto" if e.get("auto_start") else "")
        self.lay.addWidget(label(f"{e['minutes']} min" + extra, 11, color=T.text3))
        title = e.get("name") if kind == "class" else e.get("subject")
        if title:
            self.lay.addWidget(label(title, 12, QFont.Weight.DemiBold if kind == "class" else QFont.Weight.Normal,
                                     T.text2 if not off else T.text3))
        if kind == "class" and e.get("place"):
            self.lay.addWidget(label(e["place"], 11, color=T.text3))

    def mouseReleaseEvent(self, ev):
        if self.rect().contains(ev.position().toPoint()):
            self._cb(self.e)


class SchedulePage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Schedule", "Classes, study sessions and lock hours")
        top = QHBoxLayout()
        top.setSpacing(10)
        self.next_l = label("", 13, color=T.text2, wrap=True)
        top.addWidget(self.next_l, 1)
        self.b_class = Button("Add class", "soft", "book", height=42)
        self.b_add = Button("Add session", "primary", "plus", height=42)
        top.addWidget(self.b_class)
        top.addWidget(self.b_add)
        self.body.addLayout(top)
        # today
        self.today_card = Card(pad=20, accent=T.violet)
        th = QHBoxLayout()
        th.addWidget(label("TODAY", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.week_l = label("", 12, color=T.text3)
        th.addWidget(self.week_l)
        self.today_card.lay.addLayout(th)
        self.today_box = QVBoxLayout()
        self.today_box.setSpacing(8)
        self.today_card.lay.addLayout(self.today_box)
        self.body.addWidget(self.today_card)
        # lock hours
        self.hours_card = Card(pad=20, accent=T.cyan)
        hh = QHBoxLayout()
        hh.addWidget(label("LOCK HOURS", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.b_hours = Button("Add lock hours", "primary", "clock", height=38)
        hh.addWidget(self.b_hours)
        self.hours_card.lay.addLayout(hh)
        self.hours_state = label("", 13, QFont.Weight.DemiBold, T.cyan, wrap=True)
        self.hours_card.lay.addWidget(self.hours_state)
        self.hours_box = QVBoxLayout()
        self.hours_box.setSpacing(8)
        self.hours_card.lay.addLayout(self.hours_box)
        self.body.addWidget(self.hours_card)
        self.b_hours.clicked.connect(ctx.window_flow)
        self.grid = QHBoxLayout()
        self.grid.setSpacing(12)
        self.body.addLayout(self.grid)
        self.note = label("Classes remind you before they start. A scheduled session asks for your confirmation when it is "
                          "due (or starts by itself if you chose that), while VOIDLOCK is open - up to 30 minutes late.",
                          12, color=T.text3, wrap=True)
        self.body.addWidget(self.note)
        self.empty = EmptyState("schedule", "Nothing scheduled", "Add your classes and weekly study sessions. VOIDLOCK "
                                "reminds you before each class and when a session is due.", "Add session")
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self.b_add.clicked.connect(lambda: self.edit({"day": date.today().weekday(), "time": "18:00",
                                                      "minutes": ctx.store.settings["default_minutes"],
                                                      "subject": "", "enabled": True}, new=True))
        self.b_class.clicked.connect(lambda: self.edit_class({"day": date.today().weekday(), "time": "08:00",
                                                              "minutes": 90, "name": "", "place": "", "remind": 15,
                                                              "enabled": True}, new=True))
        self.empty.action.connect(self.b_add.click)
        self._cols = []

    def _refresh_hours(self):
        c = self.ctx
        clear_layout(self.hours_box)
        wins = c.store.windows
        self.hours_state.setText(c.hours_state() or "No lock hours yet. Add them to close games automatically at set times.")
        now = datetime.now()
        for w in wins:
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(IconTile(w.get("name", "H"), T.cyan, 34, icon="clock"))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(w.get("name") or "Lock hours", 14, QFont.Weight.DemiBold))
            col.addWidget(label(f"{days_text(w['days'], c.store.settings['week_start'])}  ·  {i18n.digits(w['start'])} - {i18n.digits(w['end'])}",
                                12, color=T.text3))
            row.addLayout(col, 1)
            for cat in w.get("categories", [])[:3]:
                row.addWidget(Pill(cat.upper(), T.CATEGORY.get(cat, T.cyan), px=10))
            if w.get("enabled", True) and rules.window_active(w, now):
                row.addWidget(Pill("ACTIVE NOW", T.cyan, dot=True, px=10))
            d = Button("", "icon", "trash", "Remove these lock hours…", square=32)
            d.clicked.connect(lambda _=False, w=w: (c.release_window_flow(w), self.refresh()))
            row.addWidget(d)
            wd = QWidget()
            wd.setLayout(row)
            self.hours_box.addWidget(wd)

    # ---- today: classes and sessions in time order
    def _today_items(self, now):
        st = self.ctx.store
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        items = []
        for s, e, c in classtools.today_list(st.classes, now):
            items.append((s, e, c["name"], "class", c.get("place", "")))
        for e in st.schedule:
            if e.get("enabled", True) and e["day"] == now.weekday():
                h, m = [int(x) for x in e["time"].split(":")]
                s = base.replace(hour=h, minute=m)
                items.append((s, s + timedelta(minutes=int(e["minutes"])), e.get("subject") or "Focus session", "session", ""))
        items.sort(key=lambda t: t[0])
        return items

    def _session_done(self, s, e):
        lo, hi = s.timestamp() - 300, e.timestamp() + 1800
        return any(lo <= float(r.get("start", 0)) <= hi for r in self.ctx.store.history)

    def _refresh_today(self):
        clear_layout(self.today_box)
        now = datetime.now()
        items = self._today_items(now)
        if not items:
            self.today_box.addWidget(label("Nothing planned for today.", 13, color=T.text3))
            return
        for s, e, name, kind, place in items:
            row = QHBoxLayout()
            row.setSpacing(12)
            col = T.violet if kind == "class" else T.cyan
            row.addWidget(label(f"{i18n.digits(s.strftime('%H:%M'))}", 15, QFont.Weight.DemiBold, col, mono=True))
            mid = QVBoxLayout()
            mid.setSpacing(0)
            mid.addWidget(label(name, 14, QFont.Weight.DemiBold))
            mins = int((e - s).total_seconds() // 60)
            sub = i18n.tr(f"Class · {mins} min" if kind == "class" else f"Study session · {mins} min") + (f" · {place}" if place else "")
            mid.addWidget(label(sub, 12, color=T.text3))
            row.addLayout(mid, 1)
            if s <= now < e:
                row.addWidget(Pill("NOW", T.green, dot=True, px=10))
            elif s > now:
                row.addWidget(label(i18n.fmt_in((s - now).total_seconds()), 12, color=T.text2))
            elif kind == "session":
                done = self._session_done(s, e)
                row.addWidget(Pill("DONE" if done else "MISSED", T.green if done else T.amber, px=10))
            else:
                row.addWidget(label("Finished", 12, color=T.text3))
            w = QWidget()
            w.setLayout(row)
            self.today_box.addWidget(w)

    def refresh(self):
        self._refresh_hours()
        self._refresh_today()
        clear_layout(self.grid)
        st = self.ctx.store
        sch, cls = st.schedule, st.classes
        self.empty.setVisible(not sch and not cls)
        today = date.today().weekday()
        self._cols = []
        wk_cls = wk_ses = 0
        for d in week_order(st.settings["week_start"]):
            col = Card(pad=12, accent=T.cyan if d == today else None)
            col.lay.setSpacing(8)
            ents = [(e["time"], e, "class") for e in cls if e["day"] == d] + [(e["time"], e, "session") for e in sch if e["day"] == d]
            ents.sort(key=lambda t: t[0])
            c_min = sum(int(e["minutes"]) for _t, e, k in ents if k == "class" and e.get("enabled", True))
            s_min = sum(int(e["minutes"]) for _t, e, k in ents if k == "session" and e.get("enabled", True))
            wk_cls += c_min
            wk_ses += s_min
            col.lay.addWidget(label(i18n.day_name(d).upper(), 11, QFont.Weight.Bold, T.cyan if d == today else T.text3,
                                    spacing=2, align=AC))
            if c_min + s_min:
                col.lay.addWidget(label(fmt_hm((c_min + s_min) * 60), 10, color=T.text3, mono=True, align=AC))
            for _t, e, kind in ents:
                col.lay.addWidget(EntryChip(e, (lambda e: self.edit_class(e)) if kind == "class" else (lambda e: self.edit(e)), kind))
            if not ents:
                col.lay.addWidget(label("-", 14, color=T.border_hi, align=AC))
            col.lay.addStretch(1)
            col.setMinimumHeight(190)
            self.grid.addWidget(col, 1)
            self._cols.append(col)
        self.week_l.setText(f"This week: {fmt_hm(wk_cls * 60)} classes · {fmt_hm(wk_ses * 60)} study sessions")
        self._reveal = [self.today_card, self.hours_card] + self._cols
        self.next_l.setText(self.ctx.schedule_summary())

    # ---- editing
    def _run_form(self, form, title, new, icon, width=520):
        m = self.ctx.new_modal().build(title, None, form, "Add" if new else "Save", icon=icon, width=width,
                                      validator=form.valid)
        form.changed.connect(m.revalidate)
        form.b_del.clicked.connect(lambda: (setattr(form, "deleted", True), m.finish(True)))
        return m.exec_modal()

    def edit(self, entry, new=False):
        st = self.ctx.store
        form = ScheduleForm(dict(entry), st.settings["week_start"], st.classes, st.schedule)
        if not self._run_form(form, "New scheduled session" if new else "Edit scheduled session", new, "schedule"):
            return
        if form.deleted:
            st.schedule = [e for e in st.schedule if e["id"] != entry.get("id")]
            self.ctx.toast("Entry deleted.", "info")
        else:
            cur = next((e for e in st.schedule if e["id"] == entry.get("id")), None)
            made, upd = apply_days(st.schedule, cur, form.values(),
                                   lambda d, b: {"id": uid(), "last_fired": "", "day": d, **b})
            self.ctx.toast(("Session scheduled." if new else "Entry updated.") if made + upd == 1 else
                           f"{made + upd} sessions scheduled.", "success")
        st.save_schedule()
        self.refresh()
        QTimer_stagger(self)

    def edit_class(self, entry, new=False):
        st = self.ctx.store
        form = ClassForm(dict(entry), st.settings["week_start"], st.classes, st.schedule)
        if not self._run_form(form, "New class" if new else "Edit class", new, "book"):
            return
        if form.deleted:
            st.classes = [e for e in st.classes if e["id"] != entry.get("id")]
            self.ctx.toast("Class deleted.", "info")
        else:
            cur = next((e for e in st.classes if e["id"] == entry.get("id")), None)
            made, upd = apply_days(st.classes, cur, form.values(),
                                   lambda d, b: {"id": uid(), "rem_done": "", "start_done": "", "day": d, **b})
            self.ctx.toast("Class saved." if made + upd == 1 else f"{made + upd} classes saved.", "success")
        st.save_classes()
        if any(c.get("enabled", True) for c in st.classes):
            from .guard import persist_protection_async
            persist_protection_async(True, st)         # the guard also shows class reminders while the window is closed
            self.ctx.guard.ensure()
        self.ctx.update_class_pill()
        self.refresh()
        QTimer_stagger(self)


def QTimer_stagger(page):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(20, page.stagger)


# ============================================================ ANALYTICS
class StatCard(Card):
    def __init__(self, icon, color, caption):
        super().__init__(pad=18, hover=True)
        self.lay.setSpacing(6)
        h = QHBoxLayout()
        h.addWidget(IconTile(color=color, size=34, icon=icon))
        h.addStretch(1)
        self.sub = label("", 11, color=T.text3)
        h.addWidget(self.sub)
        self.lay.addLayout(h)
        self.val = label("0", 28, QFont.Weight.DemiBold, mono=True)
        self.lay.addWidget(self.val)
        self.lay.addWidget(label(caption, 12, color=T.text2))

    def set(self, value, sub=""):
        self.val.setText(value)
        self.sub.setText(sub)


STATUS_LOOK = {"completed": ("COMPLETED", T.green), "ended": ("ENDED EARLY", T.amber),
               "emergency": ("EMERGENCY", T.red), "recovered": ("RECOVERED", T.violet)}


class AnalyticsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Analytics", "Your study, your tests and your discipline")
        self.export_card = Card(pad=16, accent=T.cyan)
        er = QHBoxLayout()
        er.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("Report for your advisor or parents", 14, QFont.Weight.DemiBold))
        col.addWidget(label("Study time, time per subject, a day-by-day table and the focus sessions - as an HTML page, a PDF or a CSV file.",
                            12, color=T.text3, wrap=True))
        er.addLayout(col, 1)
        self.b_report = Button("Export report…", "primary", "download", height=40)
        er.addWidget(self.b_report)
        self.export_card.lay.addLayout(er)
        self.body.addWidget(self.export_card)
        self.b_report.clicked.connect(lambda: export_report(self.ctx))
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(14)
        self.s_today = StatCard("clock", T.cyan, "Study today")
        self.s_goal = StatCard("bolt", T.violet, "Daily goal")
        self.s_tests = StatCard("check", T.green, "Tests this year")
        self.s_streak = StatCard("flame", T.amber, "Day streak")
        for s in (self.s_today, self.s_goal, self.s_tests, self.s_streak):
            self.stats_row.addWidget(s, 1)
        self.body.addLayout(self.stats_row)
        self.goal_bar = ProgressBar(height=6)
        self.s_goal.lay.addWidget(self.goal_bar)
        # weekly study
        self.chart_card = Card(pad=20)
        self.chart_card.lay.addWidget(section_title("Last 7 days · minutes of study"))
        self.chart = BarChart()
        self.chart_card.lay.addWidget(self.chart)
        self.body.addWidget(self.chart_card)
        # calendar heatmap
        self.heat_card = Card(pad=20)
        self.heat_card.lay.addWidget(section_title("Study calendar"))
        self.heat = Heatmap()
        self.heat_card.lay.addWidget(self.heat)
        self.body.addWidget(self.heat_card)
        # weekly discipline report
        self.rep_card = Card(pad=20, accent=T.violet)
        self.rep_card.lay.addWidget(section_title("Weekly report · attempts to play"))
        self.rep_stats = QHBoxLayout()
        self.rep_stats.setSpacing(14)
        self.r_att = StatCard("warn", T.red, "Blocked attempts")
        self.r_play = StatCard("bolt", T.violet, "Play time")
        self.r_weak = StatCard("clock", T.amber, "Weakest hours")
        for s in (self.r_att, self.r_play, self.r_weak):
            self.rep_stats.addWidget(s, 1)
        self.rep_card.lay.addLayout(self.rep_stats)
        self.rep_card.lay.addWidget(label("Attempts per day", 13, QFont.Weight.DemiBold))
        self.att_day = BarChart()
        self.att_day.setMinimumHeight(170)
        self.rep_card.lay.addWidget(self.att_day)
        self.rep_card.lay.addWidget(label("Attempts by hour of the day", 13, QFont.Weight.DemiBold))
        self.att_hour = BarChart()
        self.att_hour.setMinimumHeight(170)
        self.rep_card.lay.addWidget(self.att_hour)
        self.rep_top = QVBoxLayout()
        self.rep_top.setSpacing(6)
        self.rep_card.lay.addLayout(self.rep_top)
        self.insight = label("", 13, QFont.Weight.DemiBold, T.cyan, wrap=True)
        self.rep_card.lay.addWidget(self.insight)
        self.body.addWidget(self.rep_card)
        # year overview
        self.year_card = Card(pad=20)
        self.year_title = section_title("Year overview")
        self.year_card.lay.addWidget(self.year_title)
        self.year_stats = QHBoxLayout()
        self.year_stats.setSpacing(14)
        self.y_hours = StatCard("clock", T.cyan, "Study hours")
        self.y_tests = StatCard("check", T.green, "Tests solved")
        self.y_best = StatCard("flame", T.amber, "Best day")
        self.y_words = StatCard("book", T.violet, "Words learned")
        for s in (self.y_hours, self.y_tests, self.y_words, self.y_best):
            self.year_stats.addWidget(s, 1)
        self.year_card.lay.addLayout(self.year_stats)
        self.year_card.lay.addWidget(label("Study hours per month", 13, QFont.Weight.DemiBold))
        self.m_hours = BarChart()
        self.m_hours.setMinimumHeight(180)
        self.year_card.lay.addWidget(self.m_hours)
        self.year_card.lay.addWidget(label("Tests per month", 13, QFont.Weight.DemiBold))
        self.m_tests = BarChart()
        self.m_tests.setMinimumHeight(180)
        self.year_card.lay.addWidget(self.m_tests)
        self.body.addWidget(self.year_card)
        # sessions
        self.recent_card = Card(pad=20)
        self.recent_card.lay.addWidget(section_title("Recent sessions"))
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(0)
        self.recent_card.lay.addLayout(self.recent_box)
        self.body.addWidget(self.recent_card)
        self.body.addStretch(1)
        self._reveal = [self.s_today, self.s_goal, self.s_tests, self.s_streak, self.chart_card, self.heat_card,
                        self.rep_card, self.year_card, self.recent_card]

    def refresh(self):
        c, st, sl = self.ctx, self.ctx.store, self.ctx.study
        h = st.history
        today = date.today()
        goal = st.settings["daily_goal_min"]
        fa = i18n.is_fa()
        sec = sl.day_sec(today, True)
        self.s_today.set(fmt_hm(sec), "today")
        self.s_goal.set(f"{min(999, int(sec / 60 / max(1, goal) * 100))}%", f"{fmt_hm(goal * 60)} goal")
        self.goal_bar.set_value(sec / 60 / max(1, goal))
        jy = i18n.to_jalali(datetime(today.year, today.month, today.day))[0]
        year = jy if fa else today.year
        ys = sl.year_summary(year, jalali=fa)
        self.s_tests.set(str(ys["tests"]), f"{sl.day_tests(today)} today")
        n = sl.streak(600)
        self.s_streak.set(str(n), "keep going" if n else "start today")
        # weekly study (study timer + sessions)
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        vals = [sl.day_sec(d, True) for d in days]
        self.chart.set_data([i18n.day_name(d.weekday(), short=True) for d in days], vals, goal, 6)
        # calendar
        start = today - timedelta(days=today.weekday() + 7 * 14)
        self.heat.set_data(sl.heat(15), start)
        # weekly report
        rep = attempts_report(st, 7)
        pdays = [play_day(st, d) for d in days]
        played = sum(p["total"] for p in pdays)
        self.r_att.set(str(rep["total"]), "last 7 days")
        self.r_play.set(fmt_hm(played), "games, last 7 days")
        if rep["total"]:
            hs = rep["weak_start"]
            self.r_weak.set(i18n.digits(f"{hs:02d}:00-{(hs + 2) % 24:02d}:00"), f"{rep['weak_count']} attempts")
            self.insight.setText(f"Most attempts happen around {i18n.digits(f'{hs:02d}:00')} - plan something else for that time "
                                 f"(a walk, a snack, a short call).")
        else:
            self.r_weak.set("-", "")
            self.insight.setText("No attempts to open blocked programs this week. Great discipline!")
        per_day = rep["per_day"]
        self.att_day.set_data([i18n.day_name(d.weekday(), short=True) for d in days],
                              [per_day.get(d.isoformat(), 0) for d in days], 0, 6, divisor=1.0, fmt=lambda v: str(int(v)))
        ph = rep["per_hour"]
        self.att_hour.set_data([i18n.digits(str(hh)) if hh % 3 == 0 else "" for hh in range(24)], ph, 0, -1,
                               divisor=1.0, fmt=lambda v: str(int(v)))
        clear_layout(self.rep_top)
        for name, cnt in rep["top_apps"]:
            r = QHBoxLayout()
            r.addWidget(label(name, 13), 1)
            r.addWidget(Pill(i18n.digits(f"{cnt}x"), T.red, px=10))
            w = QWidget()
            w.setLayout(r)
            self.rep_top.addWidget(w)
        # year
        if fa:
            labels = [i18n.FA_MONTHS[k] for k in range(12)]
        else:
            import calendar
            labels = [calendar.month_abbr[k + 1] for k in range(12)]
        self.year_title.setText(i18n.tr("Year overview") + f" · {i18n.digits(year)}")
        self.y_hours.set(f"{ys['sec'] // 3600}h", f"{ys['active_days']} active days")
        self.y_tests.set(str(ys["tests"]), "this year")
        self.y_words.set(str(ys["words"]), "this year")
        bd, bs = ys["best"]
        self.y_best.set(fmt_hm(bs) if bd else "-", bd or "")
        cur_m = (i18n.to_jalali(datetime(today.year, today.month, today.day))[1] if fa else today.month) - 1
        self.m_hours.set_data(labels, [m[0] for m in ys["months"]], 0, cur_m)
        self.m_tests.set_data(labels, [m[1] for m in ys["months"]], 0, cur_m, divisor=1.0, fmt=lambda v: str(int(v)))
        # sessions
        self.recent_card.setVisible(bool(h))
        clear_layout(self.recent_box)
        for i, r in enumerate(sorted(h, key=lambda r: r["start"], reverse=True)[:8]):
            row = QHBoxLayout()
            row.setContentsMargins(0, 10, 0, 10)
            row.setSpacing(12)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(r.get("subject") or "Focus session", 14, QFont.Weight.DemiBold))
            dt = datetime.fromtimestamp(r["start"])
            col.addWidget(label(i18n.fmt_when(dt) + (" · " + i18n.tr("strict") if r.get("strict") else ""), 12, color=T.text3))
            row.addLayout(col, 1)
            row.addWidget(label(i18n.tr(fmt_hm(r["focus_sec"])) + " / " + i18n.tr(f"{r['planned_min']}m"), 13, color=T.text2, mono=True))
            text, color = STATUS_LOOK.get(r.get("status"), ("ENDED", T.text2))
            row.addWidget(Pill(text, color, px=10))
            w = QWidget()
            w.setLayout(row)
            self.recent_box.addWidget(w)
            if i < min(8, len(h)) - 1:
                self.recent_box.addWidget(Divider())


# ============================================================ SETTINGS
SOUND_NAMES = {"off": "Off", "soft": "Soft", "bell": "Bell", "chime": "Chime", "marimba": "Marimba", "zen": "Zen",
               "crystal": "Crystal", "pulse": "Pulse", "arcade": "Arcade", "drop": "Drop"}


class SettingsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Settings", "Preferences, safety and data")
        st = ctx.store.settings
        # --- focus
        c1 = Card(pad=22)
        c1.lay.addWidget(section_title("Focus"))
        self.goal = Stepper(st["daily_goal_min"], 15, 720, 15, " min")
        self.dflt = Stepper(st["default_minutes"], 1, 480, 1, " min")
        self.strict = Toggle(st["strict_default"])
        c1.lay.addLayout(setting_row("Daily focus goal", "Used by the progress bars and the weekly chart.", self.goal))
        c1.lay.addWidget(Divider())
        c1.lay.addLayout(setting_row("Default session length", "Shown on the timer and the main Start button.", self.dflt))
        c1.lay.addWidget(Divider())
        self.tgoal = Stepper(int(st.get("daily_tests_goal", 50)), 5, 1000, 5)
        c1.lay.addLayout(setting_row("Daily tests goal", "How many practice questions you aim to solve each day.", self.tgoal))
        c1.lay.addWidget(Divider())
        c1.lay.addLayout(setting_row("Strict mode by default", "New sessions start with pause and end disabled.", self.strict))
        self.body.addWidget(c1)
        # --- appearance
        c2 = Card(pad=22)
        c2.lay.addWidget(section_title("Appearance & calendar"))
        self.motion = Segmented(["Auto", "On", "Off"], ["auto", "on", "off"].index(st["reduce_motion"]))
        self.week = Segmented(["Saturday", "Sunday", "Monday"], {5: 0, 6: 1, 0: 2}.get(st["week_start"], 0))
        c2.lay.addLayout(setting_row("Reduce motion", "Auto follows the Windows “animation effects” setting.", self.motion))
        c2.lay.addWidget(Divider())
        c2.lay.addLayout(setting_row("Week starts on", "Affects the schedule layout.", self.week))
        c2.lay.addWidget(Divider())
        self.lang = Segmented(["English", "فارسی"], 1 if st.get("language") == "fa" else 0)
        c2.lay.addLayout(setting_row("Language", "Persian switches the whole interface to right-to-left with the "
                                     "Jalali calendar. The app restarts to apply it.", self.lang))
        c2.lay.addWidget(Divider())
        tnames = list(THEME_ORDER)
        self.theme = ThemePicker(tnames, THEME_NAMES, tnames.index(st.get("theme", "void")) if st.get("theme", "void") in tnames else 0)
        c2.lay.addLayout(setting_block("Theme", "Seven dark and two light themes. Click one to choose it; "
                                       "the app restarts to apply it.", self.theme))
        c2.lay.addWidget(Divider())
        self.fem = Toggle(bool(st.get("female_mascot", False)))
        c2.lay.addLayout(setting_row("Female character", "Switches the mascot to a girl version (hair, bow, lashes).", self.fem))
        c2.lay.addWidget(Divider())
        snames = list(sounds.STYLE_ORDER)
        self.sound = ChipGrid([SOUND_NAMES[k] for k in snames], snames.index(st.get("sound", "soft")) if st.get("sound", "soft") in snames else 1,
                              per_row=5)
        self.b_sound = Button("Test sound", "soft", "bolt", height=34)
        srow = QWidget()
        sl = QVBoxLayout(srow)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        sl.addWidget(self.sound)
        sl.addWidget(self.b_sound, 0, Qt.AlignmentFlag.AlignLeft)
        c2.lay.addLayout(setting_block("Sounds", "A short sound when a program is closed, when a class is about to start and when "
                                       "you reach a goal. Pick a style and press Test sound.", srow))
        self.body.addWidget(c2)
        # --- goal & personal message
        cg = Card(pad=22, accent=T.amber)
        cg.lay.addWidget(section_title("Goal & personal message"))
        self.field = QLineEdit(st.get("target_field", ""))
        self.field.setPlaceholderText("e.g. Industrial Engineering - Sharif")
        self.field.setFixedWidth(300)
        cg.lay.addLayout(setting_row("Target field", "Shown in the message when a blocked program is closed.", self.field))
        cg.lay.addWidget(Divider())
        j = st.get("exam_date") or [1406, 4, 10]
        self.ey, self.em, self.ed = Stepper(int(j[0]), 1400, 1420, 1), Stepper(int(j[1]), 1, 12, 1), Stepper(int(j[2]), 1, 31, 1)
        dwrap = QWidget()
        dl = QHBoxLayout(dwrap)
        dl.setContentsMargins(0, 0, 0, 0)
        for w_ in (self.ey, self.em, self.ed):
            dl.addWidget(w_)
        cg.lay.addLayout(setting_row("Exam date (Jalali)", "Year, month and day. The countdown uses this date.", dwrap))
        self.exam_l = label("", 12, color=T.text2)
        cg.lay.addWidget(self.exam_l)
        cg.lay.addWidget(Divider())
        self.cmsg = QLineEdit(st.get("custom_message", ""))
        self.cmsg.setPlaceholderText("Your own motivating sentence (optional)")
        self.cmsg.setMaxLength(120)
        self.cmsg.setFixedWidth(300)
        cg.lay.addLayout(setting_row("Your sentence", "Added to the message. Leave empty for the default one.", self.cmsg))
        self.b_preview = Button("Preview the message", "soft", "eye", height=38)
        pr = QHBoxLayout()
        pr.addWidget(self.b_preview)
        pr.addStretch(1)
        cg.lay.addLayout(pr)
        self.body.addWidget(cg)
        # --- focus points
        cp = Card(pad=22, accent=T.green)
        cp.lay.addWidget(section_title("Focus points"))
        self.track = Toggle(st.get("play_tracking", True))
        cp.lay.addLayout(setting_row("Watch my games", "VOIDLOCK notices when a game runs during unlocked hours. Needed to earn "
                                     "points. Only game names and minutes are saved, on this PC.", self.track))
        cp.lay.addWidget(Divider())
        self.ppd = Stepper(int(st.get("points_per_day", 5)), 1, 50, 1)
        cp.lay.addLayout(setting_row("Points per clean day", "A day counts as clean when you played no more than the allowance below.", self.ppd))
        cp.lay.addWidget(Divider())
        self.tol = Stepper(int(st.get("play_tolerance_min", 5)), 0, 120, 5, " min")
        cp.lay.addLayout(setting_row("Allowed play per day", "Short accidental launches do not spoil a clean day.", self.tol))
        cp.lay.addWidget(Divider())
        self.fri = Toggle(st.get("game_friday_only", True))
        cp.lay.addLayout(setting_row("Play pass only on Fridays", "The play reward (1.5-2 hours of gaming) can be used on Fridays only.", self.fri))
        self.body.addWidget(cp)
        # --- administrator guard
        ca = Card(pad=22, accent=T.violet)
        ca.lay.addWidget(section_title("Administrator guard"))
        self.adm_l = label("", 12, color=T.text2, wrap=True)
        ca.lay.addWidget(self.adm_l)
        ar = QHBoxLayout()
        self.b_adm_on = Button("Enable administrator guard", "violet", "shield-check", height=38)
        self.b_adm_off = Button("Remove", "ghost", height=38)
        ar.addWidget(self.b_adm_on)
        ar.addWidget(self.b_adm_off)
        ar.addStretch(1)
        ca.lay.addLayout(ar)
        self.body.addWidget(ca)
        # --- safety
        c3 = Card(pad=22, accent=T.violet)
        c3.lay.addWidget(section_title("Safety & recovery"))
        self.cool = Stepper(st["emergency_cooldown"], 5, 300, 5, " s")
        c3.lay.addLayout(setting_row("Emergency unlock cooldown", "How long you must wait (after typing UNLOCK) before an "
                                     "emergency stop is accepted.", self.cool))
        c3.lay.addWidget(Divider())
        self.longcool = Stepper(max(1, int(st.get("long_cooldown", 600)) // 60), 1, 60, 1, " min")
        c3.lay.addLayout(setting_row("Day-lock release wait", "How long you must wait (after typing RELEASE) before a "
                                     "multi-day lock can be released early.", self.longcool))
        c3.lay.addWidget(Divider())
        c3.lay.addWidget(label("If the app is closed or stuck", 14, QFont.Weight.DemiBold))
        self.rec_text = label("", 12, color=T.text2, wrap=True)
        c3.lay.addWidget(self.rec_text)
        r = QHBoxLayout()
        self.b_folder = Button("Open data folder", "ghost", "folder", height=38)
        self.b_recover = Button("Run recovery now", "danger", "shield-check",
                                "Clears any session and stops the guard immediately", height=38)
        r.addWidget(self.b_folder)
        r.addWidget(self.b_recover)
        r.addStretch(1)
        c3.lay.addLayout(r)
        self.body.addWidget(c3)
        # --- data
        c4 = Card(pad=22)
        c4.lay.addWidget(section_title("Data"))
        self.b_report = Button("Study report (HTML / PDF / CSV)…", "ghost", "download", height=38)
        self.b_export = Button("Export history (CSV)", "ghost", "download", height=38)
        self.b_clear = Button("Clear session history", "danger", "trash", height=38)
        self.b_reset = Button("Reset everything", "danger", "refresh", height=38)
        dr0 = QHBoxLayout()                 # the report on its own row (four buttons did not fit a narrow window)
        dr0.addWidget(self.b_report)
        dr0.addStretch(1)
        c4.lay.addLayout(dr0)
        dr = QHBoxLayout()
        for b in (self.b_export, self.b_clear, self.b_reset):
            dr.addWidget(b)
        dr.addStretch(1)
        c4.lay.addLayout(dr)
        self.data_l = label("", 12, color=T.text3)
        c4.lay.addWidget(self.data_l)
        self.body.addWidget(c4)
        cs = Card(pad=22)
        cs.lay.addWidget(section_title("Window & tray"))
        self.to_tray = Toggle(st.get("close_to_tray", True))
        self.tray_login = Toggle(st.get("tray_at_login", False))
        cs.lay.addLayout(setting_row("Keep running in the tray", "The window's close button hides VOIDLOCK next to the clock "
                                     "instead of quitting. Class reminders and checks keep working. Quit from the tray menu.", self.to_tray))
        cs.lay.addWidget(Divider())
        cs.lay.addLayout(setting_row("Start in the tray with Windows", "VOIDLOCK starts quietly when you sign in. The window does "
                                     "not open by itself - click the tray icon when you want it.", self.tray_login))
        self.body.addWidget(cs)
        cu = Card(pad=22)
        cu.lay.addWidget(section_title("Updates"))
        self.up_check = Toggle(st.get("update_check", True))
        self.up_auto = Toggle(st.get("update_auto_install", True))
        cu.lay.addLayout(setting_row("Check automatically", "Looks for a new version when VOIDLOCK starts and every few "
                                     "hours while it is open, and tells you when one is out.", self.up_check))
        cu.lay.addWidget(Divider())
        cu.lay.addLayout(setting_row("Install automatically", "Downloads, verifies (SHA-256) and installs updates when "
                                     "no session is running, then restarts.", self.up_auto))
        self.up_status = label("", 12, color=T.text2, wrap=True)
        cu.lay.addWidget(self.up_status)
        ur = QHBoxLayout()
        self.b_up_check = Button("Check now", "soft", "refresh", height=38)
        self.b_up_install = Button("Install update", "primary", "download", height=38)
        ur.addWidget(self.b_up_check)
        ur.addWidget(self.b_up_install)
        ur.addStretch(1)
        cu.lay.addLayout(ur)
        self.body.addWidget(cu)
        c5 = Card(pad=22)
        c5.lay.addWidget(section_title("Backups & transfer"))
        self.bk_info = label("", 12, color=T.text2, wrap=True)
        c5.lay.addWidget(self.bk_info)
        br = QHBoxLayout()
        self.b_backup = Button("Back up now", "soft", "download", height=38)
        self.b_restore = Button("Restore…", "ghost", "refresh", height=38)
        self.b_exp = Button("Export settings…", "ghost", "download", height=38)
        self.b_imp = Button("Import settings…", "ghost", "folder", height=38)
        for x in (self.b_backup, self.b_restore, self.b_exp, self.b_imp):
            br.addWidget(x)
        br.addStretch(1)
        c5.lay.addLayout(br)
        self.body.addWidget(c5)
        self.body.addStretch(1)
        self._reveal = [c1, c2, cg, cp, ca, c3, c4, cu, c5]

        self.goal.valueChanged.connect(lambda v: self._set("daily_goal_min", v))
        self.dflt.valueChanged.connect(lambda v: self._set("default_minutes", v, plan=True))
        self.cool.valueChanged.connect(self._set_cool)
        self.strict.toggled.connect(lambda v: self._set("strict_default", bool(v)))
        self.fem.toggled.connect(lambda v: self._set("female_mascot", bool(v)))
        self.motion.currentChanged.connect(lambda i: self._set("reduce_motion", ["auto", "on", "off"][i], motion=True))
        self.week.currentChanged.connect(lambda i: self._set("week_start", [5, 6, 0][i]))
        self.lang.currentChanged.connect(self._language)
        self.theme.currentChanged.connect(self._theme)
        self.sound.currentChanged.connect(lambda i: (self._set("sound", sounds.STYLE_ORDER[i]), self.ctx.play_sound("close")))
        self.b_sound.clicked.connect(lambda: self.ctx.play_sound("close"))
        self.tgoal.valueChanged.connect(lambda v: self._set("daily_tests_goal", v))
        self.field.editingFinished.connect(lambda: self._set("target_field", self.field.text().strip()))
        self.cmsg.editingFinished.connect(lambda: self._set("custom_message", self.cmsg.text().strip()))
        for w_ in (self.ey, self.em, self.ed):
            w_.valueChanged.connect(self._exam)
        self.b_preview.clicked.connect(self._preview)
        self.track.toggled.connect(self._tracking)
        self.ppd.valueChanged.connect(lambda v: self._set("points_per_day", v))
        self.tol.valueChanged.connect(lambda v: self._set("play_tolerance_min", v))
        self.fri.toggled.connect(lambda v: self._set("game_friday_only", bool(v)))
        self.b_adm_on.clicked.connect(ctx.enable_admin_guard)
        self.b_adm_off.clicked.connect(ctx.disable_admin_guard)
        self.up_check.toggled.connect(lambda v: self._set("update_check", bool(v)))
        self.to_tray.toggled.connect(lambda v: self._set("close_to_tray", bool(v)))
        self.tray_login.toggled.connect(self._tray_login)
        self.up_auto.toggled.connect(lambda v: self._set("update_auto_install", bool(v)))
        self.b_up_check.clicked.connect(self._check_now)
        self.b_up_install.clicked.connect(ctx.install_update)
        self.longcool.valueChanged.connect(self._set_longcool)
        self.b_backup.clicked.connect(self.backup_now)
        self.b_restore.clicked.connect(self.restore_flow)
        self.b_exp.clicked.connect(self.export_settings)
        self.b_imp.clicked.connect(self.import_settings)
        self.b_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ctx.store.home))))
        self.b_recover.clicked.connect(ctx.recovery_flow)
        self.b_export.clicked.connect(self.export_csv)
        self.b_report.clicked.connect(lambda: export_report(self.ctx))
        self.b_clear.clicked.connect(self.clear_history)
        self.b_reset.clicked.connect(self.reset_all)

    def _set(self, key, value, plan=False, motion=False):
        c = self.ctx
        c.store.settings[key] = value
        c.store.save_settings()
        if key == "female_mascot":
            from .mascot import set_style
            set_style(value)
        if plan and not c.session.active:
            c.plan["minutes"] = value
        if motion:
            c.apply_motion()
        c.settings_changed()

    def _set_longcool(self, v):
        """The wait before a day lock / lock hours can be released may be made longer at any time, never shorter
        while something is locked - otherwise the commitment could be undone from this very page."""
        st = self.ctx.store
        cur = int(st.settings.get("long_cooldown", 600))
        if v * 60 < cur and st.commitments_active():
            self.longcool.set_value(max(1, cur // 60), emit=False)
            self.ctx.toast("Locks are active - the release wait can only be made longer right now.", "warn")
            return
        self._set("long_cooldown", v * 60)

    def _set_cool(self, v):
        cur = int(self.ctx.store.settings.get("emergency_cooldown", 30))
        if v < cur and self.ctx.session.active:
            self.cool.set_value(cur, emit=False)
            self.ctx.toast("A session is running - the emergency wait can only be made longer right now.", "warn")
            return
        self._set("emergency_cooldown", v)

    def refresh(self):
        s = self.ctx.store
        cmd = ("VoidLock.exe --recover" if getattr(sys, "frozen", False) else "python main.py --recover")
        self.rec_text.setText(
            f"1. In the app: use Emergency unlock on the Overview page.\n"
            f"2. From a terminal: {cmd}\n"
            f"3. Manually: create an empty file named RECOVER in the data folder - the guard clears the "
            f"session within seconds.\n"
            f"Day locks are not cleared by these. To release one early use the release button in "
            f"Application Control, or run: {cmd.replace('--recover', '--release-locks')}\n"
            f"The guard never closes system-critical programs and never enforces for more than 12 hours.\n"
            f"Data folder: {s.home}")
        self.data_l.setText(f"{len(s.history)} saved sessions · {len(s.apps)} applications · {len(s.schedule)} scheduled")
        g = self.ctx.session.gstat
        elev = bool(g.get("alive") and g.get("elevated"))
        flag = self.ctx.store.p_admin_flag.exists()
        self.adm_l.setText(("Status: running with administrator rights - websites can be blocked and elevated programs closed."
                            if elev else
                            ("Status: set up, waiting for the guard to start with administrator rights." if flag else
                             "Status: not enabled. Website blocking and closing programs that run as administrator need it. "
                             "Windows asks for permission once.")))
        self.b_adm_on.setVisible(not flag)
        self.b_adm_off.setVisible(flag)
        self._exam_label()
        from . import __version__
        info = self.ctx.update_info
        self.up_status.setText(f"Current version {__version__}" + (f"  ·  {self.ctx.update_status}" if self.ctx.update_status else ""))
        self.b_up_install.setVisible(bool(info))
        bks = s.list_backups()
        last = i18n.fmt_when(datetime.fromtimestamp(bks[0]["mtime"])) if bks else "-"
        self.bk_info.setText(f"{len(bks)} automatic backups · last: {last}\nYour data lives outside the program folder, "
                             f"so updating or rebuilding the app never resets it:\n{s.home}")

    def _check_now(self):
        self.ctx.check_updates(manual=True)

    def _theme(self, i):
        code = THEME_ORDER[i]
        if code == self.ctx.store.settings.get("theme"):
            return
        self.ctx.store.settings["theme"] = code
        self.ctx.store.save_settings()
        if self.ctx.confirm("Restart to change theme", "VOIDLOCK restarts now to apply the theme. Running sessions and locks keep going.",
                            "Restart now", False, "refresh"):
            self.ctx.restart_app()
        else:
            self.ctx.toast("The new theme applies the next time you open VOIDLOCK.", "info")

    def _exam_label(self):
        y, m, d = self.ey.value(), self.em.value(), self.ed.value()
        self.exam_l.setText(f"{i18n.jalali_str(y, m, d)} · {messages.days_left(self.ctx.store.settings)} days left")

    def _exam(self, _v=None):
        y, m, d = self.ey.value(), self.em.value(), self.ed.value()
        d = min(d, 31 if m <= 6 else 30)
        self.ctx.store.settings["exam_date"] = [y, m, d]
        self.ctx.store.save_settings()
        self._exam_label()
        self.ctx.settings_changed()

    def _preview(self):
        title, body = messages.block_message(self.ctx.store.settings, "eFootball", "window")
        self.ctx.play_sound("close")
        self.ctx._popups.append(BlockPopup(title, body, 7000))

    def _tray_login(self, on):
        from .guard import tray_autostart
        self._set("tray_at_login", bool(on))
        tray_autostart(bool(on), self.ctx.store)

    def _tracking(self, on):
        self._set("play_tracking", bool(on))
        from .guard import persist_protection_async
        if on:
            persist_protection_async(True, self.ctx.store)
            self.ctx.guard.ensure()

    def _language(self, i):
        code = "fa" if i == 1 else "en"
        if code == self.ctx.store.settings.get("language"):
            return
        self.ctx.store.settings["language"] = code
        self.ctx.store.save_settings()
        if self.ctx.confirm("Restart to change language", "VOIDLOCK restarts now to apply the language. Running "
                            "sessions and locks keep going.", "Restart now", False, "refresh"):
            self.ctx.restart_app()
        else:
            self.ctx.toast("The new language applies the next time you open VOIDLOCK.", "info")

    def backup_now(self):
        name = self.ctx.store.snapshot("manual", force=True)
        self.refresh()
        self.ctx.toast("Backup created." if name else "Backup failed.", "success" if name else "error")

    def restore_flow(self):
        if self.ctx.session.active:
            return self.ctx.toast("End the current session first.", "warn")
        bks = self.ctx.store.list_backups()[:8]
        if not bks:
            return self.ctx.toast("There are no backups yet.", "warn")
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(6)
        chips, pick = [], {"i": 0}
        for i, bk in enumerate(bks):
            reason = bk["name"].split("-", 2)[-1]
            c = Chip(i18n.fmt_when(datetime.fromtimestamp(bk["mtime"])) + "  ·  " + reason)
            c.set_checked_silent(i == 0)

            def sel(_=False, i=i):
                pick["i"] = i
                for k, ch in enumerate(chips):
                    ch.set_checked_silent(k == i)
            c.clicked.connect(sel)
            chips.append(c)
            lay.addWidget(c)
        m = self.ctx.new_modal().build("Restore a backup", "Your current data is backed up first, so you can undo this. "
                                      "Day locks are never changed by a restore.", body, "Restore", icon="refresh", width=520)
        if m.exec_modal() and self.ctx.store.restore_backup(bks[pick["i"]]["name"]):
            self.ctx.reload_after_reset()
            self.ctx.toast("Backup restored.", "success")

    def export_settings(self):
        import json
        f, _ = QFileDialog.getSaveFileName(self, "Export settings", "voidlock-settings.json", "JSON (*.json)")
        if not f:
            return
        try:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(self.ctx.store.export_all(), fh, ensure_ascii=False, indent=1)
            self.ctx.toast("Settings exported.", "success")
        except OSError as e:
            self.ctx.toast(f"Export failed: {e}", "error")

    def import_settings(self):
        if self.ctx.session.active:
            return self.ctx.toast("End the current session first.", "warn")
        import json
        f, _ = QFileDialog.getOpenFileName(self, "Import settings", "", "JSON (*.json)")
        if not f:
            return
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return self.ctx.toast("That file is not a valid VOIDLOCK export.", "error")
        if not self.ctx.confirm("Import settings?", "Your settings, applications, presets, schedule and history "
                                "will be replaced by the file (a backup is made first). Day locks are not imported.",
                                "Import", True, "download"):
            return
        if self.ctx.store.import_all(data):
            self.ctx.reload_after_reset()
            self.ctx.toast("Settings imported.", "success")
        else:
            self.ctx.toast("That file is not a valid VOIDLOCK export.", "error")

    def export_csv(self):
        if not self.ctx.store.history:
            return self.ctx.toast("There is no history to export yet.", "warn")
        f, _ = QFileDialog.getSaveFileName(self, "Export history", "voidlock-history.csv", "CSV (*.csv)")
        if not f:
            return
        try:
            with open(f, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["start", "subject", "planned_min", "focus_sec", "status", "blocked_count"])
                for r in self.ctx.store.history:
                    w.writerow([datetime.fromtimestamp(r["start"]).isoformat(timespec="seconds"), r.get("subject", ""),
                                r.get("planned_min", 0), r.get("focus_sec", 0), r.get("status", ""), r.get("blocked_count", 0)])
            self.ctx.toast("History exported.", "success")
        except OSError as e:
            self.ctx.toast(f"Export failed: {e}", "error")

    def clear_history(self):
        if self.ctx.confirm("Clear session history?", "All saved sessions, streaks and charts will be erased.",
                            "Clear history", True, "trash"):
            self.ctx.store.reset_history()
            self.refresh()
            self.ctx.session.changed.emit()
            self.ctx.toast("History cleared.", "info")

    def reset_all(self):
        if self.ctx.session.active:
            return self.ctx.toast("End the current session first.", "warn")
        if self.ctx.store.active_locks():
            return self.ctx.toast("Day locks are active - they cannot be reset. Release them first.", "warn")
        if self.ctx.confirm("Reset everything?", "Settings, applications, presets, schedule and history return to "
                            "defaults.", "Reset all data", True, "refresh"):
            self.ctx.store.reset_all()
            self.ctx.reload_after_reset()
