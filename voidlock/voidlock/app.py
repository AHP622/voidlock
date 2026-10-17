"""Main window: frameless shell, sidebar, top bar, page stack, and the application context
(the object pages talk to). UI state only - blocking lives in guard.py."""
import ctypes
import sys
import time
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QLinearGradient, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLineEdit, QMainWindow, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import __version__
from . import messages, rules, sounds, updater
from .core import Scanner, SessionController, UpdateWorker
from . import i18n
from .guard import GuardClient, child_env, emergency_recover, is_protected, persist_protection
from .i18n import tr
from .icons import paint_icon
from .overlays import Modal, ToastHost, typed_body
from .mascot import BlockPopup, Confetti
from .pages_a import AppsPage, OverviewPage
from .pages_b import AnalyticsPage, SchedulePage, SessionsPage, SettingsPage
from .pages_c import RewardsPage, StudyPage
from .study import Points, StudyLog
from .store import Store, fmt_clock, read_json, write_json
from .theme import Motion, T, font, qc, system_reduced_motion
from .viz import LockIcon
from .widgets import AA, AC, AnimWidget, Button, Stepper, Ticker, Toggle, label, reveal, tween

NAV = [("overview", "Overview", "overview"), ("study", "Study Timer", "stopwatch"),
       ("apps", "Application Control", "apps"), ("sessions", "Study Sessions", "sessions"),
       ("schedule", "Schedule", "schedule"), ("rewards", "Rewards", "star"),
       ("analytics", "Analytics", "analytics"), ("settings", "Settings", "settings")]


class NavButton(QAbstractButton):
    def __init__(self, text, icon, tip):
        super().__init__()
        self.setText(text)
        self.icon_name = icon
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(tip)
        self._on = 0.0
        self._hover = 0.0
        self._kb = False
        self.setFont(font(14, QFont.Weight.DemiBold))
        self.toggled.connect(lambda c: tween(self, self._on, 1.0 if c else 0.0, 260, self._so))

    def focusInEvent(self, e):
        self._kb = e.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)
        super().focusInEvent(e)

    def _so(self, v):
        self._on = float(v)
        self.update()

    def set_active(self, a):
        self.blockSignals(True)
        self.setChecked(a)
        self.blockSignals(False)
        tween(self, self._on, 1.0 if a else 0.0, 260, self._so)

    def enterEvent(self, e):
        tween(self, self._hover, 1.0, 120, self._sh)
        super().enterEvent(e)

    def leaveEvent(self, e):
        tween(self, self._hover, 0.0, 180, self._sh)
        super().leaveEvent(e)

    def _sh(self, v):
        self._hover = float(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        o = self._on
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, qc(T.cyan, 0.14 * o))
        g.setColorAt(1, qc(T.violet, 0.06 * o))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(T.raised, 0.7 * self._hover * (1 - o)))
        p.drawRoundedRect(r, 11, 11)
        p.setBrush(g)
        p.drawRoundedRect(r, 11, 11)
        if o > 0.01:
            p.setBrush(qc(T.cyan, o))
            h = 18 * o + 4
            bx = self.width() - 3 if self.isRightToLeft() else 0
            p.drawRoundedRect(QRectF(bx, r.center().y() - h / 2, 3, h), 1.5, 1.5)
        col = T.cyan if o > 0.5 else (T.text if self._hover > 0.4 else T.text2)
        rtl = self.isRightToLeft()
        paint_icon(p, self.icon_name, QRectF((self.width() - 38) if rtl else 18, r.center().y() - 10, 20, 20), col, 1.8)
        p.setPen(qc(T.text if o > 0.5 or self._hover > 0.4 else T.text2))
        p.setFont(self.font())
        if rtl:
            p.drawText(QRectF(r.left(), r.top(), r.width() - 50, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute, self.text())
        else:
            p.drawText(QRectF(50, r.top(), r.width() - 50, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute, self.text())
        if self.hasFocus() and self._kb:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qc(T.cyan, 0.5), 1.2))
            p.drawRoundedRect(r, 11, 11)


class StatusPill(AnimWidget):
    def __init__(self):
        super().__init__()
        self.title, self.color, self.pulse = "STANDBY", T.text2, False
        self.setFixedHeight(32)
        self.setFont(font(11, QFont.Weight.Bold, spacing=1.6))
        self._t = 0.0
        self.setMinimumWidth(140)

    def set(self, title, color, pulse, tip=""):
        self.title, self.color, self.pulse = tr(title), color, pulse
        self.setToolTip(tip)
        self.ensurePolished()
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(self.title) + 60)
        self.update()

    def on_tick(self, t):
        self._t = t
        if self.pulse and not Motion.reduced:
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(qc(self.color, 0.12))
        p.setPen(QPen(qc(self.color, 0.45), 1))
        p.drawRoundedRect(r, 16, 16)
        import math
        rtl = self.isRightToLeft()
        cx, cy = (self.width() - 18) if rtl else 18, r.center().y()
        p.setPen(Qt.PenStyle.NoPen)
        if self.pulse and not Motion.reduced:
            k = (self._t * 0.9) % 1.0
            p.setBrush(qc(self.color, (1 - k) * 0.35))
            p.drawEllipse(QRectF(cx - 4 - 7 * k, cy - 4 - 7 * k, 8 + 14 * k, 8 + 14 * k))
        p.setBrush(qc(self.color))
        p.drawEllipse(QRectF(cx - 4, cy - 4, 8, 8))
        p.setPen(qc(self.color))
        p.setFont(self.font())
        if rtl:
            p.drawText(QRectF(0, 0, r.width() - 32, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute, self.title)
        else:
            p.drawText(QRectF(32, 0, r.width() - 32, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute, self.title)


class WinButton(Button):
    """Window control with a red hover for close."""

    def __init__(self, icon, tip, close=False):
        super().__init__("", "icon", icon, tip, square=38)
        self.close_style = close

    def paintEvent(self, e):
        if self.close_style and self._hover > 0.02:
            p = QPainter(self)
            p.setRenderHint(AA)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(T.red, 0.85 * self._hover))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(3, 3, -3, -3), 9, 9)
            paint_icon(p, self.icon_name, QRectF(self.rect()).adjusted(9, 9, -9, -9), "#FFFFFF", 1.9)
            return
        super().paintEvent(e)


class TopBar(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedHeight(76)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(28, 12, 14, 8)
        lay.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.title = label("Overview", 23, QFont.Weight.DemiBold)
        self.sub = label("", 12, color=T.text3)
        col.addWidget(self.title)
        col.addWidget(self.sub)
        lay.addLayout(col, 1)
        self.title.setMinimumWidth(260)
        self.clock = label("", 12, color=T.text2, mono=True)
        lay.addWidget(self.clock)
        self.pill = StatusPill()
        lay.addWidget(self.pill)
        lay.addSpacing(6)
        self.b_min = WinButton("min", "Minimize")
        self.b_max = WinButton("max", "Maximize")
        self.b_close = WinButton("close", "Close", True)
        for b in (self.b_min, self.b_max, self.b_close):
            lay.addWidget(b)
        self.b_min.clicked.connect(win.showMinimized)
        self.b_max.clicked.connect(win.toggle_max)
        self.b_close.clicked.connect(win.close)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.childAt(e.position().toPoint()) in (None, self.title, self.sub, self.clock):
            h = self.win.windowHandle()
            if h:
                h.startSystemMove()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.win.toggle_max()


class Sidebar(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setFixedWidth(240)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 18, 14, 16)
        lay.setSpacing(4)
        brand = QHBoxLayout()
        brand.setContentsMargins(8, 0, 0, 0)
        brand.setSpacing(10)
        self.logo = LockIcon(38)
        self.logo.set_locked(True, T.cyan)
        brand.addWidget(self.logo)
        bc = QVBoxLayout()
        bc.setSpacing(0)
        bc.addWidget(label("VOIDLOCK", 17, QFont.Weight.Bold, T.text, spacing=3.2))
        bc.addWidget(label("FOCUS GUARD", 9, QFont.Weight.DemiBold, T.cyan, spacing=2.6))
        brand.addLayout(bc)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(26)
        self.buttons = {}
        for i, (key, text, icon) in enumerate(NAV):
            b = NavButton(text, icon, f"{tr(text)}  (Ctrl+{i + 1})")
            b.clicked.connect(lambda _=False, k=key: win.goto(k))
            lay.addWidget(b)
            self.buttons[key] = b
        lay.addStretch(1)
        self.card = QFrame()
        self.card.setObjectName("sidecard")
        self.card.setStyleSheet(f"QFrame#sidecard{{background:{T.panel2}; border:1px solid {T.border}; border-radius:14px;}}")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(2)
        self.m_state = label("STANDBY", 11, QFont.Weight.Bold, T.text2, spacing=2)
        self.m_time = label("No active session", 13, QFont.Weight.DemiBold, mono=True)
        cl.addWidget(self.m_state)
        cl.addWidget(self.m_time)
        lay.addWidget(self.card)
        lay.addWidget(label(f"v{__version__}", 10, color=T.text3), 0, Qt.AlignmentFlag.AlignHCenter)

    def set_active(self, key):
        for k, b in self.buttons.items():
            b.set_active(k == key)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), qc(T.panel, 0.55))
        p.setPen(QPen(qc(T.border), 1))
        bx = 0 if self.isRightToLeft() else self.width() - 1
        p.drawLine(bx, 0, bx, self.height())


class FadeStack(QStackedWidget):
    def show_index(self, i, animate=True):
        if i == self.currentIndex():
            return
        self.setCurrentIndex(i)
        if animate:
            w = self.currentWidget()
            QTimer.singleShot(0, lambda: reveal(w, 0, dy=14, ms=300))


class Root(QWidget):
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), qc(T.bg))
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, qc(T.cyan, 0.04))
        g.setColorAt(0.5, qc(T.bg, 0))
        g.setColorAt(1, qc(T.violet, 0.06))
        p.fillRect(self.rect(), g)
        if not self.window().isMaximized():
            p.setPen(QPen(qc(T.border_hi), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))


class MainWindow(QMainWindow):
    """Also serves as the context object handed to every page."""

    def __init__(self, store: Store, guard: GuardClient):
        super().__init__()
        self.setWindowTitle("VOIDLOCK")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.resize(1280, 800)
        self.setMinimumSize(1040, 680)
        self.store, self.guard = store, guard
        self.session = SessionController(store, guard)
        self.study = StudyLog(store)
        self.study.restore()
        self.points = Points(store)
        self._last_event_t = time.time()
        self._popups = []
        self._last_hb = 0.0
        self._last_points = 0.0
        self.running, self.scan_ready, self.scan_error = set(), False, None
        s = store.settings
        self.plan = {"minutes": s["default_minutes"], "subject": s.get("last_subject", ""), "strict": s["strict_default"]}
        self.apply_motion()
        self._sched_busy = False
        self._first = True
        self.update_info, self._upd_worker, self.update_status = None, None, ""

        self.root = Root()
        self.setCentralWidget(self.root)
        outer = QHBoxLayout(self.root)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        self.shell = QWidget()
        outer.addWidget(self.shell)
        sl = QHBoxLayout(self.shell)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        self.sidebar = Sidebar(self)
        sl.addWidget(self.sidebar)
        right = QVBoxLayout()
        right.setSpacing(0)
        sl.addLayout(right, 1)
        self.topbar = TopBar(self)
        right.addWidget(self.topbar)
        self.stack = FadeStack()
        right.addWidget(self.stack, 1)
        self.pages = {}
        for key, cls in (("overview", OverviewPage), ("study", StudyPage), ("apps", AppsPage),
                         ("sessions", SessionsPage), ("schedule", SchedulePage), ("rewards", RewardsPage),
                         ("analytics", AnalyticsPage), ("settings", SettingsPage)):
            pg = cls(self)
            self.pages[key] = pg
            self.stack.addWidget(pg)
        self.keys = list(self.pages)
        self.toasts = ToastHost(self.root)
        self.confetti = Confetti(self.root)
        self.session.notify.connect(self.toast)
        self.session.changed.connect(self._on_changed)
        self.session.finished.connect(self._on_finished)

        for i, k in enumerate(self.keys):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, activated=lambda k=k: self.goto(k))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._find)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._toggle_run)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._toggle_run)

        self.scanner = Scanner()
        self.scanner.scanned.connect(self._scanned)
        self.scanner.failed.connect(self._scan_failed)
        self.scanner.start()
        self.tick = QTimer(self)
        self.tick.timeout.connect(self._second)
        self.tick.start(1000)
        self.goto("overview", animate=False)
        self._second()
        QTimer.singleShot(7000, lambda: self.check_updates(False))
        if self.store.active_locks() or self.store.windows or self.store.settings.get("play_tracking", True):
            QTimer.singleShot(2500, lambda: persist_protection(True, self.store))   # exe may have moved/rebuilt
        QTimer.singleShot(3500, self.process_points)

    # ------------------------------------------------------------ window chrome
    def toggle_max(self):
        if self.isMaximized():
            self.showNormal()
            self.topbar.b_max.set_icon("max")
        else:
            self.showMaximized()
            self.topbar.b_max.set_icon("restore")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toasts"):
            self.toasts.setGeometry(self.root.rect())
            self.confetti.setGeometry(self.root.rect())

    def nativeEvent(self, eventType, message):
        """Edge resizing for the frameless window on Windows (WM_NCHITTEST)."""
        if sys.platform == "win32" and eventType == b"windows_generic_MSG":
            try:
                import ctypes.wintypes as wt
                msg = wt.MSG.from_address(int(message))
                if msg.message == 0x0084 and not self.isMaximized():
                    x = ctypes.c_short(msg.lParam & 0xFFFF).value
                    y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                    dpr = self.devicePixelRatioF()
                    pt = self.mapFromGlobal(QPoint(int(x / dpr), int(y / dpr)))
                    m, w, h = 7, self.width(), self.height()
                    left, right, top, bot = pt.x() < m, pt.x() > w - m, pt.y() < m, pt.y() > h - m
                    code = None
                    if top and left: code = 13
                    elif top and right: code = 14
                    elif bot and left: code = 16
                    elif bot and right: code = 17
                    elif left: code = 10
                    elif right: code = 11
                    elif top: code = 12
                    elif bot: code = 15
                    if code:
                        return True, code
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def closeEvent(self, e):
        if self.session.active:
            ok = self.confirm("Close VOIDLOCK?", "Your session keeps running: the guard process continues blocking "
                              "in the background until the timer ends. Reopen VOIDLOCK any time to manage it.",
                              "Close window", False, "info")
            if not ok:
                e.ignore()
                return
        self.study.heartbeat()
        self.scanner.stop()
        self.store.snapshot("exit")
        super().closeEvent(e)

    # ------------------------------------------------------------ navigation
    def goto(self, key, animate=True):
        i = self.keys.index(key)
        pg = self.pages[key]
        self.topbar.title.setText(pg.title)
        self.topbar.sub.setText(pg.subtitle)
        self.sidebar.set_active(key)
        pg.on_show()
        self.stack.show_index(i, animate and not self._first)
        self._first = False
        if key == "overview" and animate is False:
            QTimer.singleShot(60, pg.stagger)

    def current_key(self):
        return self.keys[self.stack.currentIndex()]

    def _find(self):
        self.goto("apps")
        QTimer.singleShot(60, self.pages["apps"].focus_search)

    def _toggle_run(self):
        s = self.session
        if s.state == "running":
            s.pause() or self.toast("Strict mode: pause is disabled.", "warn")
        elif s.state == "paused":
            s.resume()
        elif s.state in ("idle", "completed"):
            s.dismiss()
            self.quick_start_default()

    # ------------------------------------------------------------ periodic
    def _second(self):
        self.store.refresh_locks()
        self.store.refresh_windows()
        self.session.tick()
        now = time.time()
        if now - self._last_hb > 2:
            self._last_hb = now
            write_json(self.store.p_ui_alive, {"t": now})
            if self.study.active() and int(now) % 10 < 2:
                self.study.heartbeat(now)
        self._poll_events()
        if now - self._last_points > 3600:
            self._last_points = now
            self.process_points()
        if self.current_key() in ("study", "rewards"):
            self.pages[self.current_key()].refresh()
        if self.study.active():
            self._check_goal()
        now = datetime.now()
        self.topbar.clock.setText(i18n.fmt_clock_line(now))
        if now.second % 15 == 0 or self._first:
            self._check_schedule(now)

    def _on_changed(self):
        prot = self.session.protection()
        pulse = prot["level"] in ("enforcing", "starting", "locks", "hours")
        self.topbar.pill.set(prot["title"], prot["color"], pulse, prot["detail"])
        sb = self.sidebar
        sb.m_state.setText(prot["title"])
        sb.m_state.setStyleSheet(f"color:{prot['color']}; background:transparent;")
        sb.m_time.setText(fmt_clock(self.session.remaining) if self.session.active else "No active session")
        sb.logo.set_locked(prot["locked"], prot["color"] if prot["locked"] else T.text3)
        if self.current_key() == "apps":
            self.pages["apps"].refresh()

    def _on_finished(self, rec):
        st = rec["status"]
        if st == "completed":
            self.toast(f"Session complete · {rec['planned_min']} min of focus saved.", "success")
            self.celebrate("done")
        if self.current_key() == "analytics":
            self.pages["analytics"].refresh()

    def _scanned(self, names):
        self.running = names
        self.scan_ready = True
        self.scan_error = None
        if self.current_key() == "apps":
            self.pages["apps"].refresh()

    def _scan_failed(self, msg):
        self.scan_error = msg
        self.scan_ready = True
        if self.current_key() == "apps":
            self.pages["apps"].refresh()

    # ------------------------------------------------------------ services for pages
    def toast(self, text, kind="info"):
        self.toasts.push(text, kind)

    def new_modal(self):
        return Modal(self.root, self.shell)

    def confirm(self, title, message, confirm="Confirm", danger=False, icon=None):
        m = self.new_modal().build(title, message, None, confirm, "Cancel", danger, icon=icon or "info")
        return m.exec_modal()

    def apply_motion(self):
        mode = self.store.settings.get("reduce_motion", "auto")
        Motion.reduced = system_reduced_motion() if mode == "auto" else mode == "on"
        Ticker.get().refresh()

    def settings_changed(self):
        self.pages["overview"].refresh()
        if self.current_key() in ("analytics", "schedule", "settings"):
            self.pages[self.current_key()].refresh()
        self._on_changed()

    def presets_changed(self):
        self.pages["overview"].build_tiles()

    def reload_after_reset(self):
        s = self.store.settings
        self.plan.update({"minutes": s["default_minutes"], "subject": "", "strict": s["strict_default"]})
        self.apply_motion()
        self.pages["apps"].build_rows()
        self.pages["overview"].build_tiles()
        for pg in self.pages.values():
            pg.refresh()
        self.toast("All data was reset to defaults.", "info")

    def start_session(self, minutes, subject="", strict=False):
        s = self.session
        if s.active:
            self.toast("A session is already in progress.", "warn")
            return False
        if not self.store.enabled_apps():
            if not self.confirm("No block rules enabled", "No application is set to be blocked, so this would only "
                                "be a timer. Start anyway?", "Start timer only", False, "warn"):
                return False
        if strict and not self.confirm("Start in strict mode?", "You will not be able to pause or end this session. "
                                       "Only the Emergency unlock (typed phrase + cooldown) can stop it early.",
                                       "Start strict session", True, "lock"):
            return False
        if s.state == "completed":
            s.dismiss()
        ok = s.start(minutes, subject, strict)
        if ok:
            self.toast(f"Focus session started · {minutes} min", "success")
        return ok

    def quick_start_default(self):
        p = self.plan
        self.start_session(p["minutes"], p["subject"], p["strict"])

    def quick_start_preset(self, pr):
        if self.session.active:
            return self.toast("A session is already in progress.", "warn")
        self.start_session(pr["minutes"], self.plan.get("subject", ""), bool(pr.get("strict")))

    def custom_start_flow(self):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        subj = QLineEdit(self.plan.get("subject", ""))
        subj.setPlaceholderText("Subject (optional)")
        subj.setMaxLength(40)
        lay.addWidget(subj)
        r = QHBoxLayout()
        r.addWidget(label("Duration", 13, QFont.Weight.DemiBold), 1)
        dur = Stepper(self.plan["minutes"], 5, 240, 5, " min")
        r.addWidget(dur)
        lay.addLayout(r)
        r2 = QHBoxLayout()
        r2.addWidget(label("Strict mode", 13, QFont.Weight.DemiBold), 1)
        strict = Toggle(self.plan["strict"])
        r2.addWidget(strict)
        lay.addLayout(r2)
        m = self.new_modal().build("Custom session", None, body, "Start", icon="sessions")
        if m.exec_modal():
            self.plan.update({"minutes": dur.value(), "subject": subj.text().strip(), "strict": strict.isChecked()})
            self.start_session(dur.value(), subj.text().strip(), strict.isChecked())

    def end_flow(self):
        if self.session.strict:
            return self.toast("Strict mode: use Emergency unlock to stop early.", "warn")
        if self.confirm("End this session?", "Blocking stops immediately. The focus time so far is saved.",
                        "End session", True, "stop"):
            self.session.end("ended")
            self.toast("Session ended. Blocking stopped.", "info")

    PHRASES_FA = {"UNLOCK": "باز کن", "RELEASE": "رها کن"}

    def _typed_modal(self, title, message, confirm, phrase="UNLOCK", cooldown=None, icon="shield-check"):
        cool = int(self.store.settings.get("emergency_cooldown", 30)) if cooldown is None else int(cooldown)
        fa = self.PHRASES_FA.get(phrase, phrase)
        shown = fa if i18n.is_fa() else phrase
        holder = {}
        body = typed_body(tr("Type {p} to confirm").replace("{p}", shown) if False else
                          (tr(f"Type {phrase} to confirm") if not i18n.is_fa() else f"برای تأیید «{fa}» (یا {phrase}) را تایپ کنید"),
                          shown, lambda: holder["m"].revalidate())
        ok = lambda: body.edit.text().strip().upper() == phrase or body.edit.text().strip() == fa
        m = self.new_modal().build(title, message, body, confirm, "Keep focusing", True,
                                  validator=ok, cooldown=cool, icon=icon)
        holder["m"] = m
        return m.exec_modal()

    def _emergency_modal(self, title, message, confirm):
        return self._typed_modal(title, message, confirm, "UNLOCK")

    def emergency_flow(self):
        if not self.session.active:
            return
        if self._emergency_modal("Emergency unlock", "This stops blocking right away and is recorded in your history "
                                 "as an emergency stop. Take a breath first - the button unlocks after a short wait.",
                                 "Unlock now"):
            self.session.emergency()
            self.toast("Emergency unlock complete. Nothing is blocked now.", "warn")

    def recovery_flow(self):
        if self._emergency_modal("Run recovery", "Clears the session state and stops the guard process. Use this if "
                                 "something is stuck or blocking incorrectly.", "Run recovery"):
            if self.session.active:
                self.session.emergency()
            else:
                emergency_recover(self.store)
            self.toast("Recovery done. Guard stopped and session cleared.", "success")

    def restart_guard(self):
        self.guard.stop()
        self.guard.attempts = 0
        self.guard.launched_at = 0
        time.sleep(0.3)
        self.guard.ensure()
        if self.guard.launch_error:
            self.toast("Could not start guard: " + self.guard.launch_error, "error")
        else:
            self.toast("Restarting the enforcement guard…", "info")

    def elevate_guard(self):
        ok, msg = self.guard.start_elevated()
        self.toast("Requested administrator guard." if ok else msg, "info" if ok else "warn")

    # ------------------------------------------------------------ joy: sounds, confetti, popups, points
    def play_sound(self, kind):
        sounds.play(kind, self.store.settings.get("sound", "soft"))

    def celebrate(self, kind="reward"):
        self.confetti.burst()
        self.play_sound("reward" if kind == "reward" else "done")

    def _poll_events(self):
        try:
            ev = (read_json(self.store.p_events, {}) or {}).get("list", [])
        except Exception:
            return
        for e in ev:
            if e.get("t", 0) > self._last_event_t:
                self._last_event_t = e["t"]
                title, body = messages.block_message(self.store.settings, e.get("name", ""), e.get("why", "session"))
                self._popups = [p for p in self._popups if p.isVisible()]
                self._popups.append(BlockPopup(title, body))
                if self.current_key() in ("overview", "apps"):
                    self.pages[self.current_key()].refresh()

    def process_points(self):
        res = self.points.process_days()
        gained = sum(p for _d, _k, p in res)
        if gained > 0:
            days = sum(1 for _d, k, _p in res if k == "clean")
            self.toast(f"+{gained} focus points for {days} clean day(s)!", "success")
            self.celebrate("reward")
        elif any(k == "played" for _d, k, _p in res):
            self.toast("A day with play: no points for it. Tomorrow is a new chance.", "info")
        if self.current_key() == "rewards":
            self.pages["rewards"].refresh()

    def after_study_change(self):
        self._check_goal()
        if self.current_key() == "overview":
            self.pages["overview"].refresh()

    def _check_goal(self):
        goal = self.store.settings["daily_goal_min"] * 60
        today = date.today().isoformat()
        if self.study.day_sec(date.today()) >= goal and self.store.study.get("goal_hit") != today:
            self.store.study["goal_hit"] = today
            self.store.save_study()
            self.toast("Daily goal reached - amazing work!", "success")
            self.celebrate("done")

    def hours_state(self):
        """Human text about lock hours right now (for the Overview / Schedule), or ''."""
        wins = [w for w in self.store.windows if w.get("enabled", True)]
        if not wins:
            return ""
        now = datetime.now()
        act = rules.active_windows(wins, now)
        if act:
            cats = sorted({c for w in act for c in w.get("categories", [])})
            end = max(rules.window_end(w, now) for w in act)
            return f"Lock hours: {', '.join(i18n.tr(c) for c in cats)} locked until {i18n.fmt_when(end)}"
        nxt = rules.next_change(wins, now)
        return f"Play time: lock hours start {i18n.fmt_when(nxt)}" if nxt else "Play time: no lock hours ahead"

    # ------------------------------------------------------------ lock hours, websites, administrator guard
    def window_flow(self):
        from .pages_b import WindowForm
        form = WindowForm()
        m = self.new_modal().build("Add lock hours", "Choose the days and times when these apps are closed automatically.",
                                  form, "Add", validator=form.valid, icon="clock", width=540)
        form.changed.connect(m.revalidate)
        if not m.exec_modal():
            return False
        w = self.store.add_window(form.values())
        persist_protection(True, self.store)
        self.guard.attempts = 0
        self.guard.ensure()
        self.session.changed.emit()
        self.toast("Lock hours added. They can only be removed with the release phrase.", "success")
        return w

    def release_window_flow(self, w):
        cool = int(self.store.settings.get("long_cooldown", 600))
        if self._typed_modal("Remove lock hours?", f"“{w.get('name') or 'Lock hours'}” will stop protecting you. "
                             f"Removing a commitment should take effort - take the time to be sure.",
                             "Remove lock hours", "RELEASE", cool, "lock"):
            self.guard.release(windows=[w["id"]])
            self.session.changed.emit()
            self.toast("Lock hours removed.", "warn")
            return True
        return False

    def site_flow(self):
        from . import hosts as hostsmod
        from PySide6.QtWidgets import QLineEdit as _LE
        from .widgets import Chip
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        ed = _LE()
        ed.setPlaceholderText("Website, e.g. youtube.com")
        lay.addWidget(ed)
        row = QHBoxLayout()
        row.setSpacing(8)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        for i, (nm, dom) in enumerate(hostsmod.PRESETS):
            c = Chip(nm)
            c.clicked.connect(lambda _=False, d=dom, n=nm: (ed.setText(d), ed.setProperty("nm", n)))
            (row if i < 5 else row2).addWidget(c)
        row.addStretch(1)
        row2.addStretch(1)
        lay.addLayout(row)
        lay.addLayout(row2)
        err = label("", 12, color=T.red, wrap=True)
        lay.addWidget(err)

        def valid():
            d = hostsmod.normalize(ed.text())
            err.setText("")
            if not ed.text().strip():
                return False
            if not d:
                err.setText("That does not look like a website address.")
                return False
            if self.store.find_exe(d):
                err.setText("This website is already in the list.")
                return False
            return True
        m = self.new_modal().build("Add website", "The site is blocked in every browser while a session runs, during lock "
                                  "hours, or while locked. Administrator permission is needed once.", body, "Add",
                                  validator=valid, icon="globe", width=560)
        ed.textChanged.connect(lambda _t: m.revalidate())
        if not m.exec_modal():
            return None
        d = hostsmod.normalize(ed.text())
        name = ed.property("nm") if (ed.property("nm") and d in [x for _n, x in hostsmod.PRESETS]) else d
        from .store import uid
        a = {"id": uid(), "name": name, "exe": d, "category": "Sites", "kind": "site", "enabled": True,
             "custom": True, "path": ""}
        self.store.apps.append(a)
        self.store.save_apps()
        self.session.sync_rules()
        self.toast(f"{name} added and blocked." + ("" if self.guard.status().get("elevated") else " Enable the administrator guard to enforce it."), "success")
        return a

    def enable_admin_guard(self):
        if not self.confirm("Enable the administrator guard?", "Windows will ask for permission once. After that the guard "
                            "starts with administrator rights at sign-in. This is what lets VOIDLOCK block websites and "
                            "close programs that run as administrator.", "Continue", False, "shield-check"):
            return
        ok, msg = self.guard.install_admin()
        if not ok:
            return self.toast(msg or "Could not start the elevated setup.", "error")
        self.toast("Setting up… accept the Windows prompt. The status updates in a few seconds.", "info")

    def disable_admin_guard(self):
        if self.confirm("Remove the administrator guard?", "Website blocking stops working until you enable it again.",
                        "Remove", True, "warn"):
            from .guard import GuardClient as _G
            import subprocess
            self.store.p_admin_flag.unlink(missing_ok=True)
            self.toast("Removed. If Windows asks, accept it to delete the task.", "info")
            self.guard.stop()
            try:
                import ctypes
                base = self.guard._cmd()
                params = " ".join(f'"{c}"' for c in [a for a in base[1:] if a != "--guard"] + ["--remove-admin-guard"])
                ctypes.windll.shell32.ShellExecuteW(None, "runas", base[0], params, None, 0)
            except Exception:
                pass

    # ------------------------------------------------------------ updates (GitHub releases)
    def _set_update_status(self, text):
        self.update_status = text
        if self.current_key() == "settings":
            self.pages["settings"].refresh()

    def check_updates(self, manual=False):
        s = self.store.settings
        repo = (s.get("update_repo") or "").strip()
        if not repo:
            return self.toast("Set the update source (owner/repo) first.", "warn") if manual else None
        if not manual and (not s.get("update_check") or time.time() - float(s.get("update_last_check", 0)) < 6 * 3600):
            return
        if self._upd_worker and self._upd_worker.isRunning():
            return
        w = UpdateWorker("check", repo)
        w.checked.connect(lambda i: self._on_checked(i, manual))
        w.failed.connect(lambda m: self._on_update_failed(m, manual))
        self._upd_worker = w
        self._set_update_status("Checking for updates…")
        w.start()

    def _on_checked(self, info, manual):
        s = self.store.settings
        s["update_last_check"] = time.time()
        self.store.save_settings()
        if info and info["tag"] == s.get("update_last_tag"):
            info = None
            self._set_update_status("The latest release has the same version number as this app. Bump __version__ before tagging.")
            return
        self.update_info = info
        if info is None:
            self._set_update_status("You are up to date.")
            if manual:
                self.toast("You are up to date.", "success")
            return
        self._set_update_status(f"Version {info['version']} is available.")
        if s.get("update_auto_install") and not manual:
            self.install_update(auto=True)
        else:
            self.toast(f"Update {info['version']} is available. Open Settings to install it.", "info")

    def _on_update_failed(self, msg, manual):
        self._set_update_status(msg)
        if manual:
            self.toast(msg, "error")

    def install_update(self, auto=False):
        info = self.update_info
        if not info:
            return
        if not getattr(sys, "frozen", False):
            return self._set_update_status("Updates install into the built VoidLock.exe. When running from source, use git pull.")
        if self.session.active or self.root.findChildren(Modal):
            if auto:
                QTimer.singleShot(60_000, lambda: self.install_update(True))   # try again later, never mid-session
            else:
                self.toast("Finish the current session first.", "warn")
            return
        if not auto and not self.confirm("Install update?", f"Version {info['version']} will be downloaded and installed. "
                                         f"VOIDLOCK restarts; sessions and locks keep going.", "Install", False, "download"):
            return
        w = UpdateWorker("download", info=info, dest=str(self.store.home / "updates"))
        w.progress.connect(lambda p: self._set_update_status(f"Downloading update… {p}%"))
        w.downloaded.connect(self._apply_downloaded)
        w.failed.connect(lambda m: self._on_update_failed(m, True))
        self._upd_worker = w
        self._set_update_status("Downloading update…")
        w.start()

    def _apply_downloaded(self, path):
        try:
            updater.apply(path)
        except updater.UpdateError as e:
            return self._on_update_failed(str(e), True)
        self.store.settings["update_last_tag"] = self.update_info["tag"]
        self.store.save_settings()
        if not (self.session.active or self.store.active_locks()):
            self.guard.stop()          # nothing enforced right now: let the new guard code take over
        self.toast("Update installed. Restarting…", "success")
        QTimer.singleShot(900, self.restart_app)

    # ------------------------------------------------------------ multi-day locks
    def lock_flow(self, apps, extend=False):
        apps = [a for a in apps if not is_protected(a["exe"])]
        if not apps:
            return self.toast("Nothing to lock.", "warn")
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        row = QHBoxLayout()
        row.addWidget(label("Lock duration", 13, QFont.Weight.DemiBold), 1)
        days = Stepper(7, 1, 365, 1, " d")
        row.addWidget(days)
        lay.addLayout(row)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        from .widgets import Chip
        for d in (1, 3, 7, 10, 14, 30):
            c = Chip(f"{d} d")
            c.clicked.connect(lambda _=False, d=d: days.set_value(d))
            chips.addWidget(c)
        chips.addStretch(1)
        lay.addLayout(chips)
        until_l = label("", 13, QFont.Weight.DemiBold, color=T.cyan, wrap=True)
        lay.addWidget(until_l)
        mins = int(self.store.settings.get("long_cooldown", 600)) // 60
        warn = f"These apps are closed automatically - even with no session running and after restarting " \
               f"the PC. Releasing early needs the phrase RELEASE and a {mins}-minute wait."
        lay.addWidget(label(warn, 12, color=T.text3, wrap=True))
        if any(a["category"] == "Browsers" for a in apps):
            lay.addWidget(label("Warning: this includes a web browser you may need for studying.", 12,
                                color=T.amber, wrap=True))

        def base_until(a):
            cur = self.store.lock_for(a["exe"])
            return max(time.time(), float(cur["until"])) if (cur and extend) else time.time()

        def upd(_v=None):
            until = base_until(apps[0]) + days.value() * 86400
            until_l.setText(f"Locked until {i18n.fmt_when(datetime.fromtimestamp(until))}")
        days.valueChanged.connect(upd)
        upd()
        title = "Extend lock" if extend else "Lock for several days"
        names = ", ".join(a["name"] for a in apps[:3]) + (f" +{len(apps) - 3}" if len(apps) > 3 else "")
        m = self.new_modal().build(title, names, body, "Extend lock" if extend else "Lock now", "Cancel",
                                  False, cooldown=3, icon="lock", width=520)
        if not m.exec_modal():
            return False
        for a in apps:
            self.store.add_lock(a["exe"], a["name"], base_until(a) + days.value() * 86400)
            a["enabled"] = True
        self.store.save_apps()
        self.store.refresh_locks()
        persist_protection(True, self.store)
        self.guard.attempts = 0
        self.guard.ensure()
        self.session.sync_rules()
        self.session.changed.emit()
        self.toast(f"{len(apps)} app(s) locked for {days.value()} day(s).", "success")
        return True

    def release_flow(self, app):
        cool = int(self.store.settings.get("long_cooldown", 600))
        lk = self.store.lock_for(app["exe"])
        if not lk:
            return
        until = i18n.fmt_when(datetime.fromtimestamp(lk["until"]))
        if self._typed_modal("Release lock early?", f"{app['name']} is locked until {until}. Releasing it "
                             f"breaks your commitment. Take the time to be sure.", "Release lock", "RELEASE",
                             cool, "lock"):
            self.guard.release_locks([app["exe"]])
            self.session.changed.emit()
            self.toast(f"{app['name']} was released.", "warn")

    def restart_app(self):
        import subprocess
        cmd = [sys.executable] + ([] if getattr(sys, "frozen", False) else [sys.argv[0]])
        cmd += ["--after", str(__import__("os").getpid()), "--home", str(self.store.home)]
        try:
            subprocess.Popen(cmd, close_fds=True, env=child_env())
        except Exception as e:
            return self.toast(f"Could not restart: {e}", "error")
        self.scanner.stop()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    # ------------------------------------------------------------ schedule
    def next_scheduled(self):
        now = datetime.now()
        best = None
        for e in self.store.schedule:
            if not e.get("enabled", True):
                continue
            h, m = [int(x) for x in e["time"].split(":")]
            for add in range(8):
                d = (now + timedelta(days=add)).replace(hour=h, minute=m, second=0, microsecond=0)
                if d.weekday() == e["day"] and d > now:
                    if best is None or d < best[0]:
                        best = (d, e)
                    break
        if not best:
            return None
        d, e = best
        return f"{i18n.day_name(d.weekday())} {i18n.digits(e['time'])}" + (f" · {e['subject']}" if e.get("subject") else "") + " · " + tr(f"{e['minutes']} min")

    def _check_schedule(self, now):
        if self._sched_busy:
            return
        today = now.date().isoformat()
        for e in self.store.schedule:
            if not e.get("enabled", True) or e["day"] != now.weekday() or e.get("last_fired") == today:
                continue
            h, m = [int(x) for x in e["time"].split(":")]
            due = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if 0 <= (now - due).total_seconds() <= 180:
                e["last_fired"] = today
                self.store.save_schedule()
                if self.session.active:
                    self.toast(f"Scheduled session “{e.get('subject') or 'Focus'}” skipped - a session is running.", "warn")
                    return
                self._sched_busy = True
                try:
                    if self.confirm("Scheduled session", f"{e.get('subject') or 'Focus session'} · {e['minutes']} min is due now.",
                                    "Start now", False, "schedule"):
                        self.start_session(e["minutes"], e.get("subject", ""), False)
                finally:
                    self._sched_busy = False
                return
