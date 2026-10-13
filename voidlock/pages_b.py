"""Pages: Study Sessions, Schedule, Analytics, Settings."""
import csv
import os
import sys
import time
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QSlider, QVBoxLayout, QWidget)

from . import i18n
from .guard import emergency_recover
from .pages_a import Page
from .store import completed_count, fmt_hm, last_days, streak_days, today_focus_sec, uid, week_order
from .theme import Motion, T
from .viz import BarChart, EmptyState, IconTile
from .widgets import (AC, Button, Card, Chip, Divider, Pill, ProgressBar, Segmented, Stepper, Ticker, Toggle,
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
        self.stepper = Stepper(ctx.plan["minutes"], 5, 240, 5, " min")
        drow.addWidget(self.stepper)
        self.cfg.lay.addLayout(drow)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 48)
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
class ScheduleForm(QWidget):
    def __init__(self, entry, week_start):
        super().__init__()
        self.deleted = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        self.order = week_order(week_start)
        lay.addWidget(label("DAY", 10, QFont.Weight.Bold, T.text3, spacing=2))
        self.day = Segmented([i18n.day_name(d) for d in self.order], self.order.index(entry["day"]))
        lay.addWidget(self.day)
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
        self.dur = Stepper(entry["minutes"], 5, 240, 5, " min")
        d.addWidget(self.dur)
        lay.addLayout(d)
        self.subject = QLineEdit(entry.get("subject", ""))
        self.subject.setPlaceholderText("Subject (optional)")
        self.subject.setMaxLength(40)
        lay.addWidget(self.subject)
        e = QHBoxLayout()
        e.addWidget(label("Enabled", 13, QFont.Weight.DemiBold), 1)
        self.enabled = Toggle(entry.get("enabled", True))
        e.addWidget(self.enabled)
        lay.addLayout(e)
        self.b_del = Button("Delete this entry", "danger", "trash", height=36)
        self.b_del.setVisible(bool(entry.get("id")))
        lay.addWidget(self.b_del)

    def values(self):
        return {"day": self.order[self.day.current()], "time": f"{self.hh.value():02d}:{self.mm.value():02d}",
                "minutes": self.dur.value(), "subject": self.subject.text().strip(), "enabled": self.enabled.isChecked()}


class EntryChip(Card):
    def __init__(self, e, on_click):
        super().__init__(pad=10, hover=True)
        self.e, self._cb = e, on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lay.setSpacing(1)
        self.setToolTip("Click to edit")
        off = not e.get("enabled", True)
        self.lay.addWidget(label(e["time"], 15, QFont.Weight.DemiBold, T.text3 if off else T.cyan, mono=True))
        self.lay.addWidget(label(f"{e['minutes']} min" + (" · off" if off else ""), 11, color=T.text3))
        if e.get("subject"):
            self.lay.addWidget(label(e["subject"], 12, color=T.text2 if not off else T.text3))

    def mouseReleaseEvent(self, ev):
        if self.rect().contains(ev.position().toPoint()):
            self._cb(self.e)


class SchedulePage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Schedule", "Plan recurring weekly sessions")
        top = QHBoxLayout()
        self.next_l = label("", 13, color=T.text2)
        top.addWidget(self.next_l, 1)
        self.b_add = Button("Add session", "primary", "plus", height=42)
        top.addWidget(self.b_add)
        self.body.addLayout(top)
        self.grid = QHBoxLayout()
        self.grid.setSpacing(12)
        self.body.addLayout(self.grid)
        self.note = label("Scheduled sessions ask for your confirmation when they are due, while VOIDLOCK is open.",
                          12, color=T.text3, wrap=True)
        self.body.addWidget(self.note)
        self.empty = EmptyState("schedule", "Nothing scheduled", "Add a weekly session and VOIDLOCK will remind you "
                                "to start it on time.", "Add session")
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self.b_add.clicked.connect(lambda: self.edit({"day": date.today().weekday(), "time": "18:00",
                                                      "minutes": ctx.store.settings["default_minutes"],
                                                      "subject": "", "enabled": True}, new=True))
        self.empty.action.connect(self.b_add.click)
        self._cols = []

    def refresh(self):
        clear_layout(self.grid)
        sch = self.ctx.store.schedule
        self.empty.setVisible(not sch)
        today = date.today().weekday()
        self._cols = []
        for d in week_order(self.ctx.store.settings["week_start"]):
            col = Card(pad=12, accent=T.cyan if d == today else None)
            col.lay.setSpacing(8)
            col.lay.addWidget(label(i18n.day_name(d).upper(), 11, QFont.Weight.Bold, T.cyan if d == today else T.text3,
                                    spacing=2, align=AC))
            ents = sorted([e for e in sch if e["day"] == d], key=lambda e: e["time"])
            for e in ents:
                col.lay.addWidget(EntryChip(e, lambda e: self.edit(e)))
            if not ents:
                col.lay.addWidget(label("-", 14, color=T.border_hi, align=AC))
            col.lay.addStretch(1)
            col.setMinimumHeight(190)
            self.grid.addWidget(col, 1)
            self._cols.append(col)
        self._reveal = self._cols
        nxt = self.ctx.next_scheduled()
        self.next_l.setText(f"Next: {nxt}" if nxt else "No upcoming sessions.")

    def edit(self, entry, new=False):
        form = ScheduleForm(dict(entry), self.ctx.store.settings["week_start"])
        m = self.ctx.new_modal().build("New scheduled session" if new else "Edit scheduled session", None, form,
                                      "Add" if new else "Save", icon="schedule", width=500)
        form.b_del.clicked.connect(lambda: (setattr(form, "deleted", True), m.finish(True)))
        if not m.exec_modal():
            return
        sch = self.ctx.store.schedule
        if form.deleted:
            self.ctx.store.schedule = [e for e in sch if e["id"] != entry.get("id")]
            self.ctx.toast("Entry deleted.", "info")
        elif new:
            sch.append({"id": uid(), "last_fired": "", **form.values()})
            self.ctx.toast("Session scheduled.", "success")
        else:
            for e in sch:
                if e["id"] == entry["id"]:
                    e.update(form.values())
                    e["last_fired"] = ""
            self.ctx.toast("Entry updated.", "success")
        self.ctx.store.save_schedule()
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
        super().__init__(ctx, "Analytics", "Your focus over time")
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(14)
        self.s_today = StatCard("clock", T.cyan, "Focus today")
        self.s_goal = StatCard("bolt", T.violet, "Daily goal")
        self.s_done = StatCard("check", T.green, "Completed sessions")
        self.s_streak = StatCard("flame", T.amber, "Day streak")
        for s in (self.s_today, self.s_goal, self.s_done, self.s_streak):
            self.stats_row.addWidget(s, 1)
        self.body.addLayout(self.stats_row)
        self.goal_bar = ProgressBar(height=6)
        self.s_goal.lay.addWidget(self.goal_bar)
        self.chart_card = Card(pad=20)
        self.chart_card.lay.addWidget(section_title("Last 7 days · minutes of focus"))
        self.chart = BarChart()
        self.chart_card.lay.addWidget(self.chart)
        self.body.addWidget(self.chart_card)
        self.recent_card = Card(pad=20)
        self.recent_card.lay.addWidget(section_title("Recent sessions"))
        self.recent_box = QVBoxLayout()
        self.recent_box.setSpacing(0)
        self.recent_card.lay.addLayout(self.recent_box)
        self.body.addWidget(self.recent_card)
        self.empty = EmptyState("analytics", "No sessions yet", "Complete your first focus session and your "
                                "statistics will appear here.", "Start a session")
        self.empty.action.connect(lambda: ctx.goto("sessions"))
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self._reveal = [self.s_today, self.s_goal, self.s_done, self.s_streak, self.chart_card, self.recent_card]

    def refresh(self):
        st = self.ctx.store
        h = st.history
        self.empty.setVisible(not h)
        self.chart_card.setVisible(bool(h))
        self.recent_card.setVisible(bool(h))
        sec = today_focus_sec(h)
        goal = st.settings["daily_goal_min"]
        self.s_today.set(fmt_hm(sec), "today")
        self.s_goal.set(f"{min(999, int(sec / 60 / max(1, goal) * 100))}%", f"{fmt_hm(goal * 60)} goal")
        self.goal_bar.set_value(sec / 60 / max(1, goal))
        self.s_done.set(str(completed_count(h)), f"{completed_count(h, 7)} this week")
        n = streak_days(h)
        self.s_streak.set(str(n), "keep going" if n else "start today")
        days, vals = last_days(h, 7)
        self.chart.set_data([i18n.day_name(d.weekday(), short=True) for d in days], vals, goal, 6)
        if i18n.is_fa():
            self.chart.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        clear_layout(self.recent_box)
        for i, r in enumerate(sorted(h, key=lambda r: r["start"], reverse=True)[:8]):
            row = QHBoxLayout()
            row.setContentsMargins(0, 10, 0, 10)
            row.setSpacing(12)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(r.get("subject") or "Focus session", 14, QFont.Weight.DemiBold))
            dt = datetime.fromtimestamp(r["start"])
            col.addWidget(label(i18n.fmt_when(dt) + (" · " + i18n.tr("strict") if r.get("strict") else ""), 12,
                                color=T.text3))
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
class SettingsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Settings", "Preferences, safety and data")
        st = ctx.store.settings
        # --- focus
        c1 = Card(pad=22)
        c1.lay.addWidget(section_title("Focus"))
        self.goal = Stepper(st["daily_goal_min"], 15, 720, 15, " min")
        self.dflt = Stepper(st["default_minutes"], 5, 240, 5, " min")
        self.strict = Toggle(st["strict_default"])
        c1.lay.addLayout(setting_row("Daily focus goal", "Used by the progress bars and the weekly chart.", self.goal))
        c1.lay.addWidget(Divider())
        c1.lay.addLayout(setting_row("Default session length", "Shown on the timer and the main Start button.", self.dflt))
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
        self.body.addWidget(c2)
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
        self.b_export = Button("Export history (CSV)", "ghost", "download", height=38)
        self.b_clear = Button("Clear session history", "danger", "trash", height=38)
        self.b_reset = Button("Reset everything", "danger", "refresh", height=38)
        dr = QHBoxLayout()
        for b in (self.b_export, self.b_clear, self.b_reset):
            dr.addWidget(b)
        dr.addStretch(1)
        c4.lay.addLayout(dr)
        self.data_l = label("", 12, color=T.text3)
        c4.lay.addWidget(self.data_l)
        self.body.addWidget(c4)
        cu = Card(pad=22)
        cu.lay.addWidget(section_title("Updates"))
        self.up_repo = QLineEdit(st.get("update_repo", ""))
        self.up_repo.setPlaceholderText("owner/repo")
        self.up_repo.setFixedWidth(260)
        self.up_check = Toggle(st.get("update_check", True))
        self.up_auto = Toggle(st.get("update_auto_install", True))
        cu.lay.addLayout(setting_row("GitHub repository", "Where new versions are published (Releases). Leave empty to "
                                     "turn updates off.", self.up_repo))
        cu.lay.addWidget(Divider())
        cu.lay.addLayout(setting_row("Check automatically", "Looks for a new version when VOIDLOCK starts.", self.up_check))
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
        self._reveal = [c1, c2, c3, c4, cu, c5]

        self.goal.valueChanged.connect(lambda v: self._set("daily_goal_min", v))
        self.dflt.valueChanged.connect(lambda v: self._set("default_minutes", v, plan=True))
        self.cool.valueChanged.connect(lambda v: self._set("emergency_cooldown", v))
        self.strict.toggled.connect(lambda v: self._set("strict_default", bool(v)))
        self.motion.currentChanged.connect(lambda i: self._set("reduce_motion", ["auto", "on", "off"][i], motion=True))
        self.week.currentChanged.connect(lambda i: self._set("week_start", [5, 6, 0][i]))
        self.lang.currentChanged.connect(self._language)
        self.up_repo.editingFinished.connect(self._save_repo)
        self.up_check.toggled.connect(lambda v: self._set("update_check", bool(v)))
        self.up_auto.toggled.connect(lambda v: self._set("update_auto_install", bool(v)))
        self.b_up_check.clicked.connect(self._check_now)
        self.b_up_install.clicked.connect(ctx.install_update)
        self.longcool.valueChanged.connect(lambda v: self._set("long_cooldown", v * 60))
        self.b_backup.clicked.connect(self.backup_now)
        self.b_restore.clicked.connect(self.restore_flow)
        self.b_exp.clicked.connect(self.export_settings)
        self.b_imp.clicked.connect(self.import_settings)
        self.b_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ctx.store.home))))
        self.b_recover.clicked.connect(ctx.recovery_flow)
        self.b_export.clicked.connect(self.export_csv)
        self.b_clear.clicked.connect(self.clear_history)
        self.b_reset.clicked.connect(self.reset_all)

    def _set(self, key, value, plan=False, motion=False):
        c = self.ctx
        c.store.settings[key] = value
        c.store.save_settings()
        if plan and not c.session.active:
            c.plan["minutes"] = value
        if motion:
            c.apply_motion()
        c.settings_changed()

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
        from . import __version__
        info = self.ctx.update_info
        self.up_status.setText(f"Current version {__version__}" + (f"  ·  {self.ctx.update_status}" if self.ctx.update_status else ""))
        self.b_up_install.setVisible(bool(info))
        bks = s.list_backups()
        last = i18n.fmt_when(datetime.fromtimestamp(bks[0]["mtime"])) if bks else "-"
        self.bk_info.setText(f"{len(bks)} automatic backups · last: {last}\nYour data lives outside the program folder, "
                             f"so updating or rebuilding the app never resets it:\n{s.home}")

    def _save_repo(self):
        from .updater import valid_repo
        repo = self.up_repo.text().strip()
        if repo and not valid_repo(repo):
            return self.ctx.toast("The repository must look like owner/repo.", "error")
        self.ctx.store.settings["update_repo"] = repo
        self.ctx.store.settings["update_last_check"] = 0
        self.ctx.store.save_settings()
        self.ctx.toast("Update source saved." if repo else "Updates are turned off.", "success")

    def _check_now(self):
        self._save_repo()
        self.ctx.check_updates(manual=True)

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
                                r["planned_min"], r["focus_sec"], r["status"], r.get("blocked_count", 0)])
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
