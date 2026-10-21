"""Pages: base class, shared helpers, Overview and Application Control."""
import os
import sys
import time
from datetime import date, datetime

from PySide6.QtCore import QFileInfo, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import (QFileDialog, QFileIconProvider, QFrame, QHBoxLayout, QLineEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from . import i18n, rules, study as studymod
from .guard import is_protected
from .overlays import Modal
from .store import CATEGORIES, fmt_hm, streak_days, today_focus_sec, uid
from .theme import T, font, qc
from .mascot import Mascot
from .viz import EmptyState, IconTile, LockIcon, RingTimer, Skeleton
from .widgets import (AA, AC, Button, Card, Chip, Divider, Pill, ProgressBar, Segmented, Toggle, clear_layout,
                      label, reveal, set_label_color, tween)


class Page(QWidget):
    def __init__(self, ctx, title, subtitle):
        super().__init__()
        self.ctx, self.title, self.subtitle = ctx, title, subtitle
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.inner.setStyleSheet("background:transparent;")
        self.scroll.setWidget(self.inner)
        self.body = QVBoxLayout(self.inner)
        self.body.setContentsMargins(28, 6, 28, 28)
        self.body.setSpacing(18)
        outer.addWidget(self.scroll)
        self._reveal = []

    def stagger(self, widgets=None):
        for i, w in enumerate(widgets or self._reveal):
            reveal(w, delay=70 * i)

    def on_show(self):
        self.refresh()
        QTimer.singleShot(30, self.stagger)

    def refresh(self):
        pass


def _site_gate(ctx, app):
    """Websites are blocked through the hosts file, which needs administrator rights. Be honest about it."""
    if app.get("kind") != "site":
        return None
    g = ctx.session.gstat
    if g.get("alive") and not g.get("elevated"):
        return "NEEDS ADMIN", T.amber, "Website blocking needs the administrator guard. Enable it in Settings."
    if g.get("alive") and g.get("sites_error"):
        return "ERROR", T.red, g["sites_error"]
    return None


def app_status(ctx, app):
    """Honest per-app enforcement status derived from the guard's own report."""
    lk = ctx.store.lock_for(app["exe"])
    if lk:
        g = ctx.session.gstat
        if not g.get("alive") and time.time() - ctx.guard.launched_at >= 6:
            return "NOT ENFORCED", T.red, "The guard process is not running, so this lock is NOT being enforced."
        if ((g.get("per_app") or {}).get(app["exe"].lower()) or {}).get("denied"):
            return "DENIED", T.red, "Windows refused to terminate this process. Run the guard as administrator."
        gate = _site_gate(ctx, app)
        if gate:
            return gate
        until = i18n.fmt_when(datetime.fromtimestamp(lk["until"]))
        left = i18n.fmt_remaining(lk["until"] - time.time())
        return f"LOCKED · {left}", T.cyan, f"Locked until {until}. Blocked at all times, even without a session."
    wins = [w for w in ctx.store.windows if w.get("enabled", True)]
    if wins and app.get("category"):
        now = datetime.now()
        passon = studymod.pass_until(ctx.store) > time.time()
        if app["category"] in rules.blocked_categories(wins, now, passon):
            g = ctx.session.gstat
            if not g.get("alive") and time.time() - ctx.guard.launched_at >= 6:
                return "NOT ENFORCED", T.red, "The guard process is not running, so lock hours are NOT enforced."
            gate = _site_gate(ctx, app)
            if gate:
                return gate
            end = max(rules.window_end(w, now) for w in rules.active_windows(wins, now))
            return f"HOURS · {i18n.digits(end.strftime('%H:%M'))}", T.cyan, \
                f"Closed automatically during lock hours (until {i18n.fmt_when(end)})."
    if not app.get("enabled"):
        return "ALLOWED", T.text3, "No block rule for this app."
    s = ctx.session
    prot = s.protection()
    if s.state == "paused":
        return "SUSPENDED", T.amber, "Blocking is suspended while the session is paused."
    if s.state != "running":
        return "STANDBY", T.violet, "Will be blocked automatically during focus sessions."
    if prot["level"] == "failed":
        return "NOT ENFORCED", T.red, "The guard process is not running, so this app is NOT blocked."
    if prot["level"] == "starting":
        return "STARTING", T.violet, "Guard is starting."
    gate = _site_gate(ctx, app)
    if gate:
        return gate
    per = (s.gstat.get("per_app") or {}).get(app["exe"].lower(), {})
    if per.get("denied"):
        return "DENIED", T.red, ("Windows refused to terminate this process. It was probably started with "
                                 "higher privileges. Run the guard as administrator.")
    if per.get("killed"):
        return f"BLOCKED ×{per['killed']}", T.cyan, "Terminated by the guard during this session."
    return "ENFORCED", T.cyan, "The guard is watching for this process and will terminate it."


class QuickTile(Card):
    clicked = Signal()

    def __init__(self, title, minutes, tag="", parent=None):
        super().__init__(parent, pad=14, hover=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lay.setSpacing(2)
        self.title_l = label(title, 12, QFont.Weight.DemiBold, color=T.text2)
        self.min_l = label(f"{minutes}", 26, QFont.Weight.DemiBold, mono=True)
        self.sub_l = label("minutes" + (f" · {tag}" if tag else ""), 11, color=T.text3)
        for w in (self.title_l, self.min_l, self.sub_l):
            self.lay.addWidget(w)
        self.setToolTip(f"Start a {minutes}-minute session now")
        self._enabled = True

    def set_enabled_look(self, en):
        self._enabled = en
        self.setCursor(Qt.CursorShape.PointingHandCursor if en else Qt.CursorShape.ForbiddenCursor)
        self.setWindowOpacity(1.0)
        for w in (self.title_l, self.min_l, self.sub_l):
            w.setEnabled(en)
        self.setStyleSheet("" if en else f"QLabel{{color:{T.text3};}}")

    def mouseReleaseEvent(self, e):
        if self._enabled and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, e):
        if self._enabled and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.hasFocus():
            p = QPainter(self)
            p.setRenderHint(AA)
            p.setPen(QPen(qc(T.cyan, 0.8), 1.5))
            p.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), T.r_lg, T.r_lg)


# ============================================================ OVERVIEW
class OverviewPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Overview", "Your focus command center")
        row = QHBoxLayout()
        row.setSpacing(18)
        self.body.addLayout(row)

        # ---- left: timer
        self.timer_card = Card(pad=22, accent=T.cyan)
        self.ring = RingTimer()
        self.timer_card.lay.addStretch(1)
        self.timer_card.lay.addWidget(self.ring, 0, AC)
        self.msg = label("", 12, color=T.text3, align=AC)
        self.timer_card.lay.addWidget(self.msg)
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        ctl.addStretch(1)
        self.b_start = Button("Start session", "primary", "play", height=46)
        self.b_pause = Button("Pause", "soft", "pause", "Pause blocking and the countdown (Ctrl+Enter)", height=46)
        self.b_resume = Button("Resume", "primary", "play", "Resume (Ctrl+Enter)", height=46)
        self.b_end = Button("End session", "danger", "stop", "End now and keep the focus time so far", height=46)
        self.b_emerg = Button("Emergency", "ghost", "shield-check",
                              "Emergency unlock - always available. Type UNLOCK and wait for the cooldown.", height=46)
        self.b_new = Button("New session", "primary", "play", height=46)
        self.b_dismiss = Button("Dismiss", "ghost", height=46)
        for b in (self.b_start, self.b_pause, self.b_resume, self.b_end, self.b_emerg, self.b_new, self.b_dismiss):
            ctl.addWidget(b)
        ctl.addStretch(1)
        self.timer_card.lay.addLayout(ctl)
        self.timer_card.lay.addSpacing(4)
        self.timer_card.lay.addWidget(Divider())
        hdr = QHBoxLayout()
        hdr.addWidget(label("QUICK START", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        hdr.addStretch(1)
        self.b_custom = Button("Custom…", "ghost", "edit", "Choose any length and subject", height=32)
        hdr.addWidget(self.b_custom)
        self.timer_card.lay.addLayout(hdr)
        self.tiles_row = QHBoxLayout()
        self.tiles_row.setSpacing(12)
        self.timer_card.lay.addLayout(self.tiles_row)
        self.timer_card.lay.addStretch(1)
        self.tiles = []
        row.addWidget(self.timer_card, 5)

        # ---- right column
        col = QVBoxLayout()
        col.setSpacing(18)
        row.addLayout(col, 3)
        self.prot_card = Card(pad=20)
        top = QHBoxLayout()
        top.setSpacing(14)
        self.lock = LockIcon(60)
        top.addWidget(self.lock)
        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        tcol.addWidget(label("PROTECTION", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        self.prot_title = label("STANDBY", 21, QFont.Weight.DemiBold)
        tcol.addWidget(self.prot_title)
        top.addLayout(tcol, 1)
        self.prot_card.lay.addLayout(top)
        self.prot_detail = label("", 12, color=T.text2, wrap=True)
        self.prot_card.lay.addWidget(self.prot_detail)
        self.prot_card.lay.addWidget(Divider())
        self.kv_guard = self._kv("Guard process")
        self.kv_killed = self._kv("Blocked this session")
        self.kv_rules = self._kv("Rules armed")
        self.kv_locks = self._kv("Day locks")
        self.kv_points = self._kv("Focus points")
        for kv in (self.kv_guard, self.kv_killed, self.kv_rules, self.kv_locks, self.kv_points):
            self.prot_card.lay.addLayout(kv[0])
        self.hours_l = label("", 12, QFont.Weight.DemiBold, T.cyan, wrap=True)
        self.prot_card.lay.addWidget(self.hours_l)
        self.b_retry = Button("Restart guard", "soft", "refresh", height=36)
        self.b_admin = Button("Run guard as administrator", "violet", "shield-check", height=36)
        self.prot_card.lay.addWidget(self.b_retry)
        self.prot_card.lay.addWidget(self.b_admin)
        col.addWidget(self.prot_card)

        self.today_card = Card(pad=20)
        th = QHBoxLayout()
        th.addWidget(label("TODAY", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.mascot = Mascot(76)
        th.addWidget(self.mascot)
        self.today_card.lay.addLayout(th)
        self.today_big = label("0m", 28, QFont.Weight.DemiBold, mono=True)
        self.today_sub = label("", 12, color=T.text2)
        self.today_bar = ProgressBar(height=8)
        self.today_card.lay.addWidget(self.today_big)
        self.today_card.lay.addWidget(self.today_bar)
        self.today_card.lay.addWidget(self.today_sub)
        self.streak_l = label("", 12, color=T.amber)
        self.today_card.lay.addWidget(self.streak_l)
        col.addWidget(self.today_card)

        self.rules_card = Card(pad=20)
        h = QHBoxLayout()
        h.addWidget(label("BLOCK RULES", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        h.addStretch(1)
        self.b_manage = Button("Manage", "ghost", height=30)
        h.addWidget(self.b_manage)
        self.rules_card.lay.addLayout(h)
        self.rules_box = QVBoxLayout()
        self.rules_box.setSpacing(8)
        self.rules_card.lay.addLayout(self.rules_box)
        col.addWidget(self.rules_card)
        col.addStretch(1)
        self.body.addStretch(1)

        self.b_start.clicked.connect(self.ctx.quick_start_default)
        self.b_new.clicked.connect(lambda: (ctx.session.dismiss(), ctx.quick_start_default()))
        self.b_dismiss.clicked.connect(ctx.session.dismiss)
        self.b_pause.clicked.connect(ctx.session.pause)
        self.b_resume.clicked.connect(ctx.session.resume)
        self.b_end.clicked.connect(ctx.end_flow)
        self.b_emerg.clicked.connect(ctx.emergency_flow)
        self.b_custom.clicked.connect(ctx.custom_start_flow)
        self.b_retry.clicked.connect(ctx.restart_guard)
        self.b_admin.clicked.connect(ctx.elevate_guard)
        self.b_manage.clicked.connect(lambda: ctx.goto("apps"))
        ctx.session.changed.connect(self._maybe_refresh)
        self._rule_rows = []
        self._reveal = [self.timer_card, self.prot_card, self.today_card, self.rules_card]
        self._sig = None
        self.build_tiles()

    def _kv(self, k):
        r = QHBoxLayout()
        r.addWidget(label(k, 12, color=T.text3))
        r.addStretch(1)
        v = label("-", 12, QFont.Weight.DemiBold, mono=True)
        r.addWidget(v)
        return r, v

    def build_tiles(self):
        for t in self.tiles:
            t.setParent(None)
            t.deleteLater()
        self.tiles = []
        for pr in self.ctx.store.presets[:4]:
            t = QuickTile(pr["name"], pr["minutes"], "strict" if pr.get("strict") else "")
            t.clicked.connect(lambda pr=pr: self.ctx.quick_start_preset(pr))
            self.tiles_row.addWidget(t)
            self.tiles.append(t)
        if not self.tiles:
            lb = label("No presets yet. Create some in Study Sessions.", 12, color=T.text3)
            self.tiles_row.addWidget(lb)
            self.tiles.append(lb)

    def _maybe_refresh(self):
        if self.isVisible():
            self.refresh()

    def refresh(self):
        c, s, st = self.ctx, self.ctx.session, self.ctx.store
        state = s.state
        prot = s.protection()
        # ring
        sub = f"{(s.subject or 'Focus session')} · {round(s.planned / 60)} min"
        labels = {"idle": ("READY", f"{st.settings['default_minutes']} min · press Start"),
                  "running": ("DEEP WORK", sub), "paused": ("PAUSED", sub),
                  "completed": ("COMPLETE", f"Saved · +{round(s.planned / 60)} min focus")}
        lab, subt = labels[state]
        total = s.planned if state != "idle" else st.settings["default_minutes"] * 60
        rem = s.remaining if state in ("running", "paused") else (0 if state == "completed" else total)
        self.ring.set_session(state, total, rem, lab, subt, s.clock_text())
        # buttons
        strict_active = s.strict and s.active
        vis = {self.b_start: state == "idle", self.b_pause: state == "running" and not s.strict,
               self.b_resume: state == "paused", self.b_end: s.active and not s.strict,
               self.b_emerg: s.active, self.b_new: state == "completed", self.b_dismiss: state == "completed"}
        for b, v in vis.items():
            if b.isVisible() != v:
                b.setVisible(v)
        txt = f"Start {st.settings['default_minutes']} min" if not c.plan.get("subject") else \
            f"Start · {c.plan['subject'][:14]}"
        src = f"Start {c.plan['minutes']} min"
        if getattr(self, "_start_src", None) != src:
            self._start_src = src
            self.b_start.setText(src)
            self.b_start.updateGeometry()
        msg = {"idle": "Blocked apps are terminated by a background guard during sessions.",
               "running": "Strict mode is on: pause and end are disabled. Emergency unlock is always available."
               if strict_active else "Focus mode is active.",
               "paused": "Paused - blocking is suspended.",
               "completed": "Great work. Blocking has stopped."}[state]
        if getattr(self, "_msg_src", None) != msg:
            self._msg_src = msg
            self.msg.setText(msg)
        for t in self.tiles:
            if isinstance(t, QuickTile):
                t.set_enabled_look(state in ("idle", "completed"))
        self.b_custom.setEnabled(state in ("idle", "completed"))
        # protection
        self.lock.set_locked(prot["locked"], prot["color"])
        self.prot_title.setText(prot["title"])
        set_label_color(self.prot_title, prot["color"])
        self.prot_detail.setText(prot["detail"])
        g = s.gstat
        self.kv_guard[1].setText(f"running · {g.get('pid')}" if g.get("alive") else "not running")
        set_label_color(self.kv_guard[1], T.green if g.get("alive") else T.text3)
        killed = g.get("killed", 0) if g.get("session_id") == s.session_id and s.active else 0
        self.kv_killed[1].setText(str(killed))
        self.kv_rules[1].setText(str(len(st.enabled_apps())))
        nl = len(st.active_locks())
        self.kv_locks[1].setText(str(nl))
        set_label_color(self.kv_locks[1], T.cyan if nl else T.text)
        self.b_retry.setVisible(prot["level"] == "failed")
        self.b_admin.setVisible(prot["level"] == "partial")
        # today
        goal = st.settings["daily_goal_min"]
        sec = c.study.day_sec(date.today(), True) + (int(s.planned - s.remaining) if s.active else 0)
        self.today_big.setText(fmt_hm(sec))
        self.today_bar.set_value(sec / 60 / max(1, goal))
        self.today_sub.setText(f"of {fmt_hm(goal * 60)} daily goal · {min(100, int(sec / 60 / max(1, goal) * 100))}%")
        n = c.study.streak(600)
        self.streak_l.setText(f"{n}-day focus streak" if n else "Focus 10+ minutes to start a streak")
        set_label_color(self.streak_l, T.amber if n else T.text3)
        self.kv_points[1].setText(str(c.points.balance))
        set_label_color(self.kv_points[1], T.amber)
        ht = c.hours_state()
        self.hours_l.setText(ht)
        self.hours_l.setVisible(bool(ht))
        goal_hit = sec >= goal * 60
        run = s.state == "running" or bool(c.study.active())
        self.mascot.set_state("happy" if goal_hit else ("study" if run else "idle"))
        self._refresh_rules()

    def _refresh_rules(self):
        apps = self.ctx.store.enabled_apps()
        sig = tuple((a["id"], app_status(self.ctx, a)[0]) for a in apps[:6]) + (len(apps),)
        if sig == self._sig:
            return
        self._sig = sig
        clear_layout(self.rules_box)
        if not apps:
            self.rules_box.addWidget(label("No apps are blocked. Open Application Control to add rules.",
                                           12, color=T.text3, wrap=True))
            return
        for a in apps[:6]:
            r = QHBoxLayout()
            r.setSpacing(10)
            r.addWidget(IconTile(a["name"], T.CATEGORY.get(a["category"], T.cyan), 26))
            r.addWidget(label(a["name"], 13), 1)
            text, color, tip = app_status(self.ctx, a)
            pill = Pill(text, color, px=10)
            pill.setToolTip(tip)
            r.addWidget(pill)
            w = QWidget()
            w.setLayout(r)
            self.rules_box.addWidget(w)
        if len(apps) > 6:
            self.rules_box.addWidget(label(f"+ {len(apps) - 6} more", 12, color=T.text3))


# ============================================================ APPLICATION CONTROL
class AddAppForm(QWidget):
    def __init__(self, on_change, pick_cb=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Display name, e.g. Dota 2")
        self.exe = QLineEdit()
        self.exe.setPlaceholderText("Executable name, e.g. dota2.exe")
        self.path = ""
        lay.addWidget(label("NAME", 10, QFont.Weight.Bold, T.text3, spacing=2))
        lay.addWidget(self.name)
        lay.addWidget(label("EXECUTABLE", 10, QFont.Weight.Bold, T.text3, spacing=2))
        row = QHBoxLayout()
        row.addWidget(self.exe, 1)
        self.browse = Button("Browse…", "soft", "folder", height=40)
        row.addWidget(self.browse)
        lay.addLayout(row)
        lay.addWidget(label("CATEGORY", 10, QFont.Weight.Bold, T.text3, spacing=2))
        self.cats = [c for c in CATEGORIES if c != "Sites"]
        self.cat = Segmented(self.cats, 0)
        lay.addWidget(self.cat)
        self.err = label("", 12, color=T.red, wrap=True)
        lay.addWidget(self.err)
        self.name.textChanged.connect(lambda _t: on_change())
        self.exe.textChanged.connect(lambda _t: on_change())
        self.browse.clicked.connect(self._browse)

    def _browse(self):
        flt = "Programs (*.exe);;All files (*)" if sys.platform == "win32" else "All files (*)"
        f, _ = QFileDialog.getOpenFileName(self, "Choose the application", "", flt)
        if f:
            self.path = f
            self.exe.setText(os.path.basename(f))
            if not self.name.text().strip():
                self.name.setText(os.path.splitext(os.path.basename(f))[0])

    def category(self):
        return self.cats[self.cat.current()]


class AppRow(QFrame):
    def __init__(self, ctx, app, page):
        super().__init__()
        self.ctx, self.app, self.page = ctx, app, page
        self._h = 0.0
        self.setFixedHeight(66)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(14)
        color = T.CATEGORY.get(app["category"], T.cyan)
        pix = None
        if app.get("path") and os.path.exists(app["path"]):
            pix = QFileIconProvider().icon(QFileInfo(app["path"])).pixmap(48, 48)
        lay.addWidget(IconTile(app["name"], color, 42, pixmap=pix, icon="globe" if app.get("kind") == "site" else None))
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addStretch(1)
        col.addWidget(label(app["name"], 14, QFont.Weight.DemiBold))
        col.addWidget(label(app["exe"], 11, color=T.text3, mono=True))
        col.addStretch(1)
        lay.addLayout(col, 1)
        self.cat_pill = Pill(app["category"].upper(), color, px=10)
        lay.addWidget(self.cat_pill)
        self.run_pill = Pill("RUNNING", T.green, dot=True, px=10)
        self.run_pill.setToolTip("This program is running right now.")
        lay.addWidget(self.run_pill)
        self.status = Pill("STANDBY", T.violet, px=10)
        self.status.setMinimumWidth(110)
        lay.addWidget(self.status)
        self.b_lock = Button("", "icon", "lock", "Lock this app for several days", square=34)
        self.b_ext = Button("", "icon", "plus", "Extend the lock", square=34)
        self.b_rel = Button("", "icon", "warn", "Release the lock early…", square=34)
        self.b_lock.clicked.connect(lambda: ctx.lock_flow([app]))
        self.b_ext.clicked.connect(lambda: ctx.lock_flow([app], extend=True))
        self.b_rel.clicked.connect(lambda: ctx.release_flow(app))
        for b in (self.b_lock, self.b_ext, self.b_rel):
            lay.addWidget(b)
        self.toggle = Toggle(app.get("enabled", False), tip="Block this app during focus sessions")
        self.toggle.toggled.connect(self._toggled)
        lay.addWidget(self.toggle)
        self.b_del = Button("", "icon", "trash", "Remove this custom app", square=34)
        self.b_del.setVisible(bool(app.get("custom")))
        self.b_del.clicked.connect(lambda: page.remove_app(app))
        lay.addWidget(self.b_del)
        self.update_status()

    def update_status(self):
        text, color, tip = app_status(self.ctx, self.app)
        self.status.set(text, color)
        self.status.setToolTip(tip)
        self.run_pill.setVisible(self.app["exe"].lower() in self.ctx.running)
        sess = self.ctx.session
        strict = sess.strict and sess.active
        lk = self.ctx.store.lock_for(self.app["exe"])
        if lk:
            self.app["enabled"] = True
        # While a session runs, what is blocked can grow but never shrink (otherwise the first thing to do mid-session
        # would be to switch the game off here).
        held = sess.active and bool(self.app.get("enabled"))
        self.b_lock.setVisible(not lk)
        self.b_ext.setVisible(bool(lk))
        self.b_rel.setVisible(bool(lk))
        self.b_del.setVisible(bool(self.app.get("custom")) and not lk)
        self.toggle.setEnabled(not (strict or lk or held))
        if lk:
            self.toggle.setToolTip("Locked for several days. Use the release button to end the lock early.")
        elif held:
            self.toggle.setToolTip("Blocked for the whole session. It can be turned off after the session ends.")
        elif strict:
            self.toggle.setToolTip("Locked during a strict session.")
        else:
            self.toggle.setToolTip("Block this app during focus sessions")
        if self.toggle.isChecked() != bool(self.app.get("enabled")):
            self.toggle.set_silent(bool(self.app.get("enabled")))

    def _toggled(self, on):
        if self.ctx.store.lock_for(self.app["exe"]) and not on:
            return self.toggle.set_silent(True)
        if self.ctx.session.active and self.app.get("enabled") and not on:
            self.ctx.toast("This app stays blocked until the session ends.", "warn")
            return self.toggle.set_silent(True)
        self.app["enabled"] = bool(on)
        self.ctx.store.save_apps()
        self.ctx.session.sync_rules()
        self.page.after_rule_change()

    def enterEvent(self, e):
        tween(self, self._h, 1.0, 140, self._sh)
        super().enterEvent(e)

    def leaveEvent(self, e):
        tween(self, self._h, 0.0, 200, self._sh)
        super().leaveEvent(e)

    def _sh(self, v):
        self._h = float(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setBrush(qc(T.panel2, 0.9) if self._h < 0.05 else qc(T.raised, 0.55 + 0.3 * self._h))
        p.setPen(QPen(qc(T.border if self._h < 0.5 else T.border_hi), 1))
        p.drawRoundedRect(r, 14, 14)
        if self.app.get("enabled"):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(T.cyan, 0.9))
            bx = self.width() - 3 if self.isRightToLeft() else 0
            p.drawRoundedRect(bx, 18, 3, self.height() - 36, 1.5, 1.5)


class AppsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Application Control", "Choose what is blocked while you focus")
        from .widgets import SearchField
        self.search = SearchField("Search by name or executable…  (Ctrl+K)")
        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.search, 1)
        self.b_add = Button("Add application", "primary", "plus", height=44)
        self.b_site = Button("Add website", "violet", "globe", height=44)
        top.addWidget(self.b_site)
        top.addWidget(self.b_add)
        self.body.addLayout(top)
        tip = Card(pad=14, accent=T.cyan)
        trow = QHBoxLayout()
        trow.setSpacing(12)
        trow.addWidget(IconTile(color=T.cyan, size=30, icon="lock"))
        trow.addWidget(label("To lock a game for several days: click the padlock on its row, choose the days, then "
                             "confirm.", 12, color=T.text2, wrap=True), 1)
        tip.lay.addLayout(trow)
        self.body.addWidget(tip)
        self._tip = tip
        # filters
        fwrap = QVBoxLayout()
        fwrap.setSpacing(8)
        frow = QHBoxLayout()
        frow.setSpacing(8)
        frow2 = QHBoxLayout()
        frow2.setSpacing(8)
        self.stat_chips = {}
        for key, text in (("all", "All"), ("blocked", "Blocked"), ("allowed", "Allowed"), ("running", "Running now")):
            c = Chip(text)
            c.set_checked_silent(key == "all")
            c.clicked.connect(lambda _=False, k=key: self.set_status(k))
            frow.addWidget(c)
            self.stat_chips[key] = c
        frow.addStretch(1)
        self.cat_chips = {}
        for cat in ["All"] + CATEGORIES:
            c = Chip(cat, color=T.CATEGORY.get(cat, T.cyan))
            c.set_checked_silent(cat == "All")
            c.clicked.connect(lambda _=False, k=cat: self.set_cat(k))
            frow2.addWidget(c)
            self.cat_chips[cat] = c
        frow2.addStretch(1)
        fwrap.addLayout(frow)
        fwrap.addLayout(frow2)
        self.body.addLayout(fwrap)
        # summary + bulk
        srow = QHBoxLayout()
        self.summary = label("", 12, color=T.text3)
        srow.addWidget(self.summary, 1)
        self.b_all_on = Button("Block all shown", "ghost", "lock", height=32)
        self.b_all_off = Button("Allow all shown", "ghost", height=32)
        self.b_lock_all = Button("Lock all shown…", "ghost", "lock", "Lock every visible app for several days", height=32)
        srow.addWidget(self.b_lock_all)
        srow.addWidget(self.b_all_on)
        srow.addWidget(self.b_all_off)
        self.body.addLayout(srow)
        self.admin_card = Card(pad=14, accent=T.violet)
        ar = QHBoxLayout()
        ar.setSpacing(12)
        ar.addWidget(IconTile(color=T.violet, size=30, icon="shield-check"))
        ar.addWidget(label("Website blocking needs the administrator guard (Windows asks for permission once). "
                           "Until then the websites below are NOT blocked.", 12, color=T.text2, wrap=True), 1)
        self.b_admin = Button("Enable", "violet", "shield-check", height=36)
        ar.addWidget(self.b_admin)
        self.admin_card.lay.addLayout(ar)
        self.admin_card.hide()
        self.b_admin.clicked.connect(ctx.enable_admin_guard)
        self.body.addWidget(self.admin_card)
        # banner for scan errors
        self.banner = Card(pad=12, accent=T.amber)
        self.banner_l = label("", 12, color=T.amber, wrap=True)
        self.banner.lay.addWidget(self.banner_l)
        self.banner.hide()
        self.body.addWidget(self.banner)
        self.skel = Skeleton(rows=6)
        self.body.addWidget(self.skel)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(10)
        self.list_w = QWidget()
        self.list_w.setLayout(self.list_box)
        self.body.addWidget(self.list_w)
        self.empty = EmptyState("search", "No applications match", "Try another search or clear the filters.",
                                "Clear filters")
        self.empty.hide()
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self.status_f, self.cat_f = "all", "All"
        self.rows = {}
        self._loaded = False
        self.search.textChanged.connect(lambda _t: self.apply_filter())
        self.empty.action.connect(self.clear_filters)
        self.b_add.clicked.connect(self.add_flow)
        self.b_site.clicked.connect(self.add_site)
        self.b_all_on.clicked.connect(lambda: self.bulk(True))
        self.b_all_off.clicked.connect(lambda: self.bulk(False))
        self.b_lock_all.clicked.connect(lambda: ctx.lock_flow(self.visible_apps()))
        self.build_rows()
        self.list_w.hide()
        self._reveal = [self._tip, self.list_w]

    def build_rows(self):
        for r in self.rows.values():
            r.setParent(None)
            r.deleteLater()
        self.rows = {}
        for a in self.ctx.store.apps:
            row = AppRow(self.ctx, a, self)
            self.list_box.addWidget(row)
            self.rows[a["id"]] = row

    def on_show(self):
        self._loaded = self.ctx.scan_ready
        if not self._loaded:
            self.skel.show()
            self.list_w.hide()
            QTimer.singleShot(1800, self._finish_loading)
        else:
            self._finish_loading()
        super().on_show()

    def _finish_loading(self):
        if self._loaded and self.list_w.isVisible():
            return
        self._loaded = True
        self.skel.hide()
        self.list_w.show()
        self.apply_filter()
        QTimer.singleShot(20, lambda: [reveal(r, 30 * i, dy=10, ms=300) for i, r in enumerate(list(self.rows.values())[:9])
                                       if r.isVisible()])

    def add_site(self):
        a = self.ctx.site_flow()
        if not a:
            return
        row = AppRow(self.ctx, a, self)
        self.list_box.insertWidget(0, row)
        self.rows[a["id"]] = row
        self.apply_filter()
        reveal(row, 0, dy=10, ms=300)

    def refresh(self):
        g = self.ctx.session.gstat
        has_sites = any(a.get("kind") == "site" and a.get("enabled") for a in self.ctx.store.apps)
        self.admin_card.setVisible(has_sites and not (g.get("alive") and g.get("elevated")))
        err = self.ctx.scan_error
        self.banner.setVisible(bool(err))
        if err:
            self.banner_l.setText("Could not read the running-process list (" + err +
                                  "). 'Running now' indicators may be missing; blocking is unaffected.")
        if self._loaded and not self.skel.isVisible():
            for r in self.rows.values():
                r.update_status()
            self.apply_filter()
        elif self.ctx.scan_ready and self.skel.isVisible():
            self._finish_loading()

    def set_status(self, k):
        self.status_f = k
        for key, c in self.stat_chips.items():
            c.set_checked_silent(key == k)
        self.apply_filter()

    def set_cat(self, k):
        self.cat_f = k
        for key, c in self.cat_chips.items():
            c.set_checked_silent(key == k)
        self.apply_filter()

    def clear_filters(self):
        self.search.edit.clear()
        self.set_status("all")
        self.set_cat("All")

    def visible_apps(self):
        q = self.search.text().strip().lower()
        out = []
        for a in self.ctx.store.apps:
            if q and q not in a["name"].lower() and q not in a["exe"].lower():
                continue
            if self.cat_f != "All" and a["category"] != self.cat_f:
                continue
            if self.status_f == "blocked" and not a.get("enabled"):
                continue
            if self.status_f == "allowed" and a.get("enabled"):
                continue
            if self.status_f == "running" and a["exe"].lower() not in self.ctx.running:
                continue
            out.append(a)
        return out

    def apply_filter(self):
        vis = {a["id"] for a in self.visible_apps()}
        for aid, row in self.rows.items():
            row.setVisible(aid in vis)
        n, total = len(vis), len(self.ctx.store.apps)
        blocked = len(self.ctx.store.enabled_apps())
        self.summary.setText(f"Showing {n} of {total} applications · {blocked} blocked")
        self.empty.setVisible(n == 0 and self._loaded)
        self.b_all_on.setEnabled(n > 0)
        self.b_all_off.setEnabled(n > 0)
        self.b_lock_all.setEnabled(n > 0)

    def focus_search(self):
        self.search.focus()

    def after_rule_change(self):
        self.apply_filter()
        self.ctx.session.changed.emit()

    def bulk(self, on):
        if self.ctx.session.strict and self.ctx.session.active:
            return self.ctx.toast("Rules are locked during a strict session.", "warn")
        if not on and self.ctx.session.active:
            return self.ctx.toast("Nothing can be allowed again until the session ends.", "warn")
        apps = self.visible_apps()
        if not on:
            apps = [a for a in apps if not self.ctx.store.lock_for(a["exe"])]
        if on and any(a["category"] == "Browsers" for a in apps):
            if not self.ctx.confirm("Block browsers too?", "Your visible list includes web browsers. Blocking them "
                                    "will also close the browser you may use for studying.", "Block all", True, "warn"):
                return
        for a in apps:
            a["enabled"] = on
        self.ctx.store.save_apps()
        self.ctx.session.sync_rules()
        for r in self.rows.values():
            r.update_status()
        self.apply_filter()
        self.ctx.toast(f"{'Blocking' if on else 'Allowing'} {len(apps)} application(s).", "success")

    def remove_app(self, app):
        if self.ctx.session.active:
            return self.ctx.toast("Finish the session before removing applications.", "warn")
        if self.ctx.store.lock_for(app["exe"]):
            return self.ctx.toast("This app is locked and cannot be removed.", "warn")
        if not self.ctx.confirm("Remove application?", f"{app['name']} ({app['exe']}) will be removed from the list.",
                                "Remove", True, "trash"):
            return
        self.ctx.store.apps = [a for a in self.ctx.store.apps if a["id"] != app["id"]]
        self.ctx.store.save_apps()
        row = self.rows.pop(app["id"], None)
        if row:
            row.setParent(None)
            row.deleteLater()
        self.apply_filter()
        self.ctx.toast("Application removed.", "info")

    def add_flow(self):
        if self.ctx.session.strict and self.ctx.session.active:
            return self.ctx.toast("Rules are locked during a strict session.", "warn")
        holder = {}

        def validate():
            f = holder["form"]
            name, exe = f.name.text().strip(), f.exe.text().strip()
            f.err.setText("")
            if not name or not exe:
                return False
            if "/" in exe or "\\" in exe:
                f.err.setText("Enter only the file name (for example game.exe), not a path.")
                return False
            if sys.platform == "win32" and not exe.lower().endswith(".exe"):
                f.err.setText("Windows executables end with .exe")
                return False
            if is_protected(exe):
                f.err.setText(f"{exe} is a protected system program and can never be blocked.")
                return False
            if self.ctx.store.find_exe(exe):
                f.err.setText("This executable is already in the list.")
                return False
            return True

        form = AddAppForm(lambda: m.revalidate())
        holder["form"] = form
        m = self.ctx.new_modal().build("Add application", "Blocked programs are closed by the guard during sessions.",
                                      form, "Add", validator=validate, icon="plus", width=580)
        if not m.exec_modal():
            return
        a = {"id": uid(), "name": form.name.text().strip(), "exe": form.exe.text().strip(),
             "category": form.category(), "enabled": True, "custom": True, "path": form.path}
        self.ctx.store.apps.append(a)
        self.ctx.store.save_apps()
        self.ctx.session.sync_rules()
        row = AppRow(self.ctx, a, self)
        self.list_box.insertWidget(0, row)
        self.rows[a["id"]] = row
        self.apply_filter()
        reveal(row, 0, dy=10, ms=300)
        self.ctx.toast(f"{a['name']} added and blocked.", "success")
