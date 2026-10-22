"""Pages: Study Timer (subject stopwatch, plan, daily log) and Rewards (focus points)."""
import time
from datetime import date, datetime, timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from . import i18n, messages, study as studymod
from .icons import paint_icon
from .mascot import Mascot
from .pages_a import Page
from .store import fmt_hm
from .study import SUBJECT_COLORS, play_day
from .theme import Motion, T, font, qc
from .viz import EmptyState, IconTile
from .widgets import (AA, AC, Button, Card, Chip, Divider, Pill, ProgressBar, Stepper, Toggle, clear_layout,
                      label, set_label_color, tween)


def fmt_hms(sec):
    sec = max(0, int(sec))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class ColorPicker(QWidget):
    def __init__(self, colors=SUBJECT_COLORS, parent=None):
        super().__init__(parent)
        self.colors, self.cur = colors, 0
        self.setFixedHeight(36)
        self.setFixedWidth(len(colors) * 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def color(self):
        return self.colors[self.cur]

    def mousePressEvent(self, e):
        self.cur = max(0, min(len(self.colors) - 1, int(e.position().x() // 36)))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        for i, c in enumerate(self.colors):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c))
            p.drawEllipse(QPointF(18 + i * 36, 18), 11, 11)
            if i == self.cur:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(T.text), 2))
                p.drawEllipse(QPointF(18 + i * 36, 18), 15, 15)


class SubjectTile(Card):
    clicked = Signal()
    delete = Signal()

    def __init__(self, subject):
        super().__init__(None, pad=14, hover=True)
        self.s = subject
        self.active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(IconTile(subject["name"], subject["color"], 34))
        self.name_l = label(subject["name"], 14, QFont.Weight.DemiBold)
        top.addWidget(self.name_l, 1)
        self.b_del = Button("", "icon", "trash", "Delete this subject", square=30)
        self.b_del.hide()
        self.b_del.clicked.connect(self.delete.emit)
        top.addWidget(self.b_del)
        self.lay.addLayout(top)
        self.time_l = label("00:00:00", 20, QFont.Weight.DemiBold, mono=True)
        self.hint_l = label("Tap to start", 11, color=T.text3)
        self.lay.addWidget(self.time_l)
        self.lay.addWidget(self.hint_l)
        self._phase = 0.0

    def set_state(self, text, active):
        self.time_l.setText(text)
        if active != self.active:
            self.active = active
            self.hint_l.setText("Running - tap to stop" if active else "Tap to start")
            set_label_color(self.time_l, self.s["color"] if active else T.text)
        self.update()

    def mouseReleaseEvent(self, e):
        if self.rect().contains(e.position().toPoint()) and not self.b_del.isVisible():
            self.clicked.emit()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.active or self.hasFocus():
            p = QPainter(self)
            p.setRenderHint(AA)
            k = (1 + __import__("math").sin(time.time() * 3)) / 2 if (self.active and not Motion.reduced) else 0.5
            c = QColor(self.s["color"])
            c.setAlphaF(0.55 + 0.4 * k if self.active else 0.7)
            p.setPen(QPen(c, 2))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), T.r_lg, T.r_lg)


class CheckRow(QWidget):
    toggled = Signal()
    removed = Signal()

    def __init__(self, todo):
        super().__init__()
        self.todo = todo
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(*((4, 0, 36, 0) if i18n.is_fa() else (36, 0, 4, 0)))
        self.lb = label(todo["text"], 13)
        self.lb.setWordWrap(False)
        lay.addWidget(self.lb, 1)
        d = Button("", "icon", "close", "Remove", square=28)
        d.clicked.connect(self.removed.emit)
        lay.addWidget(d)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style()

    def _style(self):
        f = self.lb.font()
        f.setStrikeOut(bool(self.todo["done"]))
        self.lb.setFont(f)
        set_label_color(self.lb, T.text3 if self.todo["done"] else T.text)

    def mouseReleaseEvent(self, e):
        self.toggled.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(4 if not self.isRightToLeft() else self.width() - 26, (self.height() - 22) / 2, 22, 22)
        done = self.todo["done"]
        p.setPen(QPen(QColor(T.cyan if done else T.border_hi), 1.6))
        p.setBrush(qc(T.cyan, 0.9) if done else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 7, 7)
        if done:
            paint_icon(p, "check", r.adjusted(3, 3, -3, -3), T.on_accent, 2.4)


class TimeStrip(QWidget):
    """Compact 'who got how much time' summary for one day: one stacked bar and one wrapped line of labels.
    Only subjects with time appear, longest first; nothing is shown for an empty day."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(8)
        self.bar = _StackBar()
        lay.addWidget(self.bar)
        self.legend = QLabel()
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setWordWrap(True)
        self.legend.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
        self.legend.setStyleSheet(f"color:{T.text2}; font-size:12px; background:transparent;")
        lay.addWidget(self.legend)
        self.setVisible(False)

    @staticmethod
    def short(sec):
        m = int(sec) // 60
        h, m = divmod(m, 60)
        if i18n.is_fa():
            return i18n.digits(f"{h}:{m:02d}") if h else i18n.digits(f"{m}") + " " + i18n.tr("min")
        return f"{h}h {m:02d}m" if h else f"{m}m"

    def set_items(self, items):
        """items: [(name, color, seconds)]"""
        self.setVisible(bool(items))
        if not items:
            return
        self.bar.set_items([(c, v) for _n, c, v in items])
        gap = "&nbsp;&nbsp;&nbsp;&nbsp;"
        parts = [f'<span style="color:{c};">&#9679;</span>&nbsp;{i18n.tr(n)}&nbsp;'
                 f'<span style="color:{T.text3};">{self.short(v)}</span>' for n, c, v in items]
        html = gap.join(parts)
        self.legend.setText(f'<div dir="rtl">{html}</div>' if i18n.is_fa() else html)


class _StackBar(QWidget):
    def __init__(self):
        super().__init__()
        self.items = []
        self.setFixedHeight(10)

    def set_items(self, items):
        self.items = items
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        w, h = self.width(), self.height()
        if self.isRightToLeft():
            p.translate(w, 0)
            p.scale(-1, 1)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        p.setClipPath(path)
        p.fillRect(QRectF(0, 0, w, h), qc(T.border, 0.9))
        total = sum(v for _c, v in self.items) or 1
        x, gap = 0.0, 2.0
        for k, (c, v) in enumerate(self.items):
            seg = max(4.0, (w - gap * (len(self.items) - 1)) * v / total)
            p.fillRect(QRectF(x, 0, seg, h), QColor(c))
            x += seg + gap


class CounterRow(QWidget):
    changed = Signal(int)

    def __init__(self, subject, value, kind="tests", bump=10, with_time=False):
        super().__init__()
        self.v, self.bump = value, bump
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)
        lay.addWidget(IconTile(subject["name"], subject["color"], 28))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(subject["name"] if kind == "tests" else subject["name"] + " · " + i18n.tr("Words"), 13))
        self.time_l = label("", 11, color=T.text2, mono=True)
        col.addWidget(self.time_l)
        # (setVisible(True) on a widget that has no parent yet opens it as a tiny window of its own for a moment)
        if not with_time:
            self.time_l.hide()
        lay.addLayout(col, 1)
        self.b_m = Button("", "soft", "minus", "-1", square=34)
        self.val = label(str(value), 16, QFont.Weight.DemiBold, mono=True, align=AC)
        self.val.setMinimumWidth(46)
        self.b_p = Button("", "soft", "plus", "+1", square=34)
        self.b_10 = Button(f"+{bump}", "soft", None, f"+{bump}", height=34)
        for b in (self.b_m, self.val, self.b_p, self.b_10):
            lay.addWidget(b)
        for b in (self.b_m, self.b_p):
            b.setAutoRepeat(True)
            b.setAutoRepeatDelay(350)
            b.setAutoRepeatInterval(70)
        self.b_m.clicked.connect(lambda: self.set(self.v - 1))
        self.b_p.clicked.connect(lambda: self.set(self.v + 1))
        self.b_10.clicked.connect(lambda: self.set(self.v + self.bump))

    def set_time(self, sec):
        """Study time of this subject on the shown day (it used to show only the number of tests)."""
        self.time_l.setText(fmt_hm(sec) if sec > 0 else "-")

    def set(self, v):
        v = max(0, min(9999, v))
        if v != self.v:
            self.v = v
            self.val.setText(str(v))
            self.changed.emit(v)


# ============================================================ STUDY TIMER
class StudyPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Study Timer", "Track every minute, subject by subject")
        self.sel = date.today()
        self.tiles = {}
        self._sig = None
        # ---- hero
        hero = Card(pad=22, accent=T.cyan)
        hr = QHBoxLayout()
        hr.setSpacing(22)
        self.mascot = Mascot(128)
        hr.addWidget(self.mascot)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(label("TODAY", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        self.total_l = label("00:00:00", 44, QFont.Weight.DemiBold, mono=True)
        col.addWidget(self.total_l)
        self.goal_bar = ProgressBar(height=10)
        col.addWidget(self.goal_bar)
        self.goal_l = label("", 12, color=T.text2)
        col.addWidget(self.goal_l)
        hr.addLayout(col, 1)
        dd = QVBoxLayout()
        dd.setSpacing(2)
        dd.addWidget(label("COUNTDOWN", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 0, Qt.AlignmentFlag.AlignRight)
        self.dday = label("D-0", 34, QFont.Weight.DemiBold, T.amber, mono=True)
        dd.addWidget(self.dday, 0, Qt.AlignmentFlag.AlignRight)
        self.dday_l = label("", 12, color=T.text2, wrap=True)
        self.dday_l.setMaximumWidth(260)
        self.dday_l.setAlignment(Qt.AlignmentFlag.AlignRight)
        dd.addWidget(self.dday_l, 0, Qt.AlignmentFlag.AlignRight)
        self.streak_l = label("", 12, color=T.amber)
        dd.addWidget(self.streak_l, 0, Qt.AlignmentFlag.AlignRight)
        hr.addLayout(dd)
        hero.lay.addLayout(hr)
        self.body.addWidget(hero)

        # ---- subjects + plan
        row = QHBoxLayout()
        row.setSpacing(18)
        self.body.addLayout(row)
        sc = Card(pad=20)
        h = QHBoxLayout()
        h.addWidget(label("SUBJECTS", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.b_manage = Button("Manage", "ghost", "edit", height=32)
        self.b_add = Button("Add subject", "soft", "plus", height=32)
        h.addWidget(self.b_manage)
        h.addWidget(self.b_add)
        sc.lay.addLayout(h)
        self.grid_host = QWidget()
        self.grid = QVBoxLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        sc.lay.addWidget(self.grid_host)
        self.running_l = label("", 12, color=T.text3)
        sc.lay.addWidget(self.running_l)
        row.addWidget(sc, 3)
        pc = Card(pad=20)
        ph = QHBoxLayout()
        ph.addWidget(label("TODAY'S PLAN", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.plan_l = label("", 12, color=T.text2)
        ph.addWidget(self.plan_l)
        pc.lay.addLayout(ph)
        self.todo_in = QLineEdit()
        self.todo_in.setPlaceholderText("Add a task and press Enter…")
        self.todo_in.setMaxLength(80)
        pc.lay.addWidget(self.todo_in)
        self.todo_box = QVBoxLayout()
        self.todo_box.setSpacing(0)
        pc.lay.addLayout(self.todo_box)
        pc.lay.addStretch(1)
        row.addWidget(pc, 2)

        # ---- daily log
        lg = Card(pad=22)
        lh = QHBoxLayout()
        lh.addWidget(label("DAILY LOG", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.b_prev = Button("", "icon", "chev-l", "Previous day", square=34)
        self.date_l = label("", 14, QFont.Weight.DemiBold, align=AC)
        self.date_l.setMinimumWidth(190)
        self.b_next = Button("", "icon", "chev-r", "Next day", square=34)
        self.b_today = Button("Today", "ghost", height=32)
        for w in (self.b_prev, self.date_l, self.b_next, self.b_today):
            lh.addWidget(w)
        lg.lay.addLayout(lh)
        sr = QHBoxLayout()
        self.day_total = label("", 13, color=T.text2)
        sr.addWidget(self.day_total, 1)
        lg.lay.addLayout(sr)
        self.strip = TimeStrip()                  # how the day's time was split between subjects
        lg.lay.addWidget(self.strip)
        lg.lay.addWidget(Divider())
        lg.lay.addWidget(label("Tests solved", 14, QFont.Weight.DemiBold))
        self.counters = QVBoxLayout()
        self.counters.setSpacing(2)
        lg.lay.addLayout(self.counters)
        self.tests_bar = ProgressBar(height=8)
        lg.lay.addWidget(self.tests_bar)
        self.tests_l = label("", 12, color=T.text2)
        lg.lay.addWidget(self.tests_l)
        self.words_box_w = QWidget()                      # language subjects: words learned
        wl = QVBoxLayout(self.words_box_w)
        wl.setContentsMargins(0, 6, 0, 0)
        wl.setSpacing(2)
        wl.addWidget(Divider())
        wl.addWidget(label("Words learned", 14, QFont.Weight.DemiBold))
        self.words = QVBoxLayout()
        self.words.setSpacing(2)
        wl.addLayout(self.words)
        self.words_l = label("", 12, color=T.text2)
        wl.addWidget(self.words_l)
        lg.lay.addWidget(self.words_box_w)
        lg.lay.addWidget(Divider())
        lg.lay.addWidget(label("Add study time manually", 14, QFont.Weight.DemiBold))
        self.man_chips = QHBoxLayout()
        self.man_chips.setSpacing(8)
        lg.lay.addLayout(self.man_chips)
        mr = QHBoxLayout()
        self.man_min = Stepper(30, 5, 600, 5, " min")
        self.b_man = Button("Add time", "primary", "plus", height=38)
        mr.addWidget(self.man_min)
        mr.addWidget(self.b_man)
        mr.addStretch(1)
        lg.lay.addLayout(mr)
        self.body.addWidget(lg)
        self.body.addStretch(1)
        self.man_sid = None
        self.manage = False
        self.rows, self.word_rows = {}, {}

        self.b_add.clicked.connect(self.add_subject)
        self.b_manage.clicked.connect(self.toggle_manage)
        self.todo_in.returnPressed.connect(self.add_todo)
        self.b_prev.clicked.connect(lambda: self.goto_day(self.sel - timedelta(days=1)))
        self.b_next.clicked.connect(lambda: self.goto_day(min(date.today(), self.sel + timedelta(days=1))))
        self.b_today.clicked.connect(lambda: self.goto_day(date.today()))
        self.b_man.clicked.connect(self.add_manual)
        self._reveal = [hero, sc, pc, lg]
        self.build_tiles()

    # ---- helpers
    @property
    def sl(self):
        return self.ctx.study

    def goto_day(self, d):
        self.sel = d
        self.build_log()
        self.refresh()

    def build_tiles(self):
        clear_layout(self.grid)
        self.tiles = {}
        subs = self.sl.subjects()
        if not subs:
            self.grid.addWidget(EmptyState("book", "No subjects yet", "Add your subjects, then tap one to start the timer.",
                                           "Add subject"))
            self.grid.itemAt(0).widget().action.connect(self.add_subject)
            return
        r = None
        for i, s in enumerate(subs):
            if i % 2 == 0:
                r = QHBoxLayout()
                r.setSpacing(10)
                self.grid.addLayout(r)
            t = SubjectTile(s)
            t.clicked.connect(lambda s=s: self.toggle_subject(s["id"]))
            t.delete.connect(lambda s=s: self.delete_subject(s))
            t.b_del.setVisible(self.manage)
            r.addWidget(t, 1)
            self.tiles[s["id"]] = t
        if len(subs) % 2 == 1:
            r.addStretch(1)

    def build_log(self):
        clear_layout(self.counters)
        clear_layout(self.words)
        self.rows, self.word_rows = {}, {}
        for s in self.sl.subjects():
            cr = CounterRow(s, self.sl.day_tests(self.sel, s["id"]))
            cr.changed.connect(lambda v, s=s: self.set_tests(s["id"], v))
            self.counters.addWidget(cr)
            self.rows[s["id"]] = cr
        for s in self.sl.word_subjects():
            wr = CounterRow(s, self.sl.day_words(self.sel, s["id"]), kind="words", bump=20, with_time=False)
            wr.changed.connect(lambda v, s=s: self.set_words(s["id"], v))
            self.words.addWidget(wr)
            self.word_rows[s["id"]] = wr
        self.words_box_w.setVisible(bool(self.word_rows))
        clear_layout(self.man_chips)
        subs = self.sl.subjects()
        self.man_sid = subs[0]["id"] if subs and self.man_sid not in {x["id"] for x in subs} else self.man_sid
        chips = []
        for s in subs:
            c = Chip(s["name"], color=s["color"])
            c.set_checked_silent(s["id"] == self.man_sid)

            def pick(_=False, sid=s["id"]):
                self.man_sid = sid
                for k, (cc, ssid) in enumerate(chips):
                    cc.set_checked_silent(ssid == sid)
            c.clicked.connect(pick)
            chips.append((c, s["id"]))
            self.man_chips.addWidget(c)
        self.man_chips.addStretch(1)

    # ---- actions
    def toggle_subject(self, sid):
        a = self.sl.active()
        if a and a["subject"] == sid:
            sec = self.sl.stop()
            self.ctx.toast(f"Saved {fmt_hm(sec)} of study.", "success")
            self.ctx.after_study_change()
        else:
            self.sl.start(sid)
            self.ctx.toast(f"Timer started: {self.sl.subject(sid)['name']}", "info")
        self.refresh()

    def toggle_manage(self):
        self.manage = not self.manage
        for t in self.tiles.values():
            t.b_del.setVisible(self.manage)

    def add_subject(self):
        ed = QLineEdit()
        ed.setPlaceholderText("Subject name, e.g. Math")
        ed.setMaxLength(24)
        cp = ColorPicker()
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(ed)
        lay.addWidget(cp)
        wrow = QHBoxLayout()
        wrow.addWidget(label("Count words learned (for a language)", 13), 1)
        wt = Toggle(False)
        wrow.addWidget(wt)
        lay.addLayout(wrow)
        ed.textChanged.connect(lambda t: wt.set_silent(bool(studymod._WORDS_NAME.search(t))))   # English / زبان ...
        m = self.ctx.new_modal().build("Add subject", None, body, "Add", validator=lambda: bool(ed.text().strip()), icon="book")
        ed.textChanged.connect(lambda _t: m.revalidate())
        if m.exec_modal():
            self.sl.add_subject(ed.text(), cp.color(), words=wt.isChecked())
            self.build_tiles()
            self.build_log()
            self.refresh()

    def delete_subject(self, s):
        if self.ctx.confirm("Delete subject?", f"“{s['name']}” will be removed from the list. Time already recorded stays in your totals.",
                            "Delete", True, "trash"):
            self.sl.remove_subject(s["id"])
            self.build_tiles()
            self.build_log()
            self.refresh()

    def add_todo(self):
        t = self.todo_in.text().strip()
        if t:
            self.sl.add_todo(date.today(), t)
            self.todo_in.clear()
            self.refresh()

    def set_tests(self, sid, v):
        self.sl.set_tests(self.sel, sid, v)
        self.refresh()
        self.ctx.after_study_change()

    def set_words(self, sid, v):
        self.sl.set_words(self.sel, sid, v)
        self.refresh()
        self.ctx.after_study_change()

    def add_manual(self):
        if not self.man_sid:
            return self.ctx.toast("Add a subject first.", "warn")
        self.sl.add_manual(self.sel, self.man_sid, self.man_min.value())
        self.ctx.toast(f"Added {self.man_min.value()} min.", "success")
        self.refresh()
        self.ctx.after_study_change()

    # ---- refresh (also called every second while visible)
    def on_show(self):
        self.build_tiles()
        self.build_log()
        super().on_show()

    def refresh(self):
        c, sl, st = self.ctx, self.sl, self.ctx.store
        now = time.time()
        today = date.today()
        total = sl.day_sec(today, True, now, include_sessions=False)
        self.total_l.setText(fmt_hms(total))
        goal = st.settings["daily_goal_min"]
        self.goal_bar.set_value(total / 60 / max(1, goal))
        self.goal_l.setText(f"of {fmt_hm(goal * 60)} daily goal · {min(100, int(total / 60 / max(1, goal) * 100))}%")
        a = sl.active()
        run = bool(a) or c.session.state == "running"
        self.mascot.set_state("happy" if total >= goal * 60 else ("study" if run else "idle"))
        left = messages.days_left(st.settings)
        self.dday.setText(f"D-{left}" if left >= 0 else "D+" + str(-left))
        field = (st.settings.get("target_field") or "").strip()
        j = st.settings.get("exam_date") or [1406, 4, 10]
        self.dday_l.setText((field + " · " if field else "") + i18n.jalali_str(*[int(x) for x in j]))
        n = sl.streak(600)
        self.streak_l.setText(f"{n}-day focus streak" if n else "Study 10+ minutes to start a streak")
        # subject tiles
        for sid, t in self.tiles.items():
            act = bool(a and a["subject"] == sid)
            t.set_state(fmt_hms(sl.subject_day_sec(today, sid, now)), act)
        self.running_l.setText(f"Running: {sl.subject(a['subject'])['name']}" if a and sl.subject(a["subject"]) else "No timer is running.")
        # plan
        todos = sl.todos(today)
        sig = tuple((t["id"], t["done"]) for t in todos)
        if sig != self._sig:
            self._sig = sig
            clear_layout(self.todo_box)
            for t in todos:
                r = CheckRow(t)
                r.toggled.connect(lambda t=t: (sl.toggle_todo(t["id"]), self.refresh(), self.ctx.after_study_change()))
                r.removed.connect(lambda t=t: (sl.remove_todo(t["id"]), self.refresh()))
                self.todo_box.addWidget(r)
            if not todos:
                self.todo_box.addWidget(label("Nothing planned yet - add your first task.", 12, color=T.text3))
        self.plan_l.setText(f"{sum(1 for t in todos if t['done'])}/{len(todos)} done" if todos else "")
        # daily log header
        self.date_l.setText(i18n.fmt_when(datetime(self.sel.year, self.sel.month, self.sel.day), with_time=False)
                            + (" · " + i18n.tr("Today") if self.sel == today else ""))
        self.b_next.setEnabled(self.sel < today)
        self.day_total.setText(f"Study time this day: {fmt_hm(sl.day_sec(self.sel, True, now, include_sessions=False))}")
        self.strip.set_items([(s["name"], s["color"], v) for s, v in sl.day_subject_times(self.sel, now)])
        if self.word_rows:
            self.words_l.setText(f"Words this day: {sl.day_words(self.sel)} · year total {sl.year_words(self.sel.year)}")
        tests = sl.day_tests(self.sel)
        tg = int(st.settings.get("daily_tests_goal", 50))
        self.tests_bar.set_value(tests / max(1, tg))
        self.tests_l.setText(f"{tests} of {tg} tests · year total {sl.year_tests(self.sel.year)}")


# ============================================================ REWARDS
KIND_ICON = {"movie": "eye", "video": "play", "game": "bolt", "other": "gift"}


class RewardCard(Card):
    def __init__(self, ctx, r, cost, can):
        super().__init__(None, pad=16, hover=True)
        self.lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(IconTile(color=T.cyan if r["kind"] != "game" else T.violet, size=38, icon=KIND_ICON.get(r["kind"], "gift")))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(r["name"], 14, QFont.Weight.DemiBold))
        extra = f"{r['minutes']} min of play" if r["kind"] == "game" else {"movie": "Enjoy a film", "video": "A long video"}.get(r["kind"], "A treat")
        col.addWidget(label(extra, 11, color=T.text3))
        top.addLayout(col, 1)
        d = Button("", "icon", "trash", "Remove this reward", square=28)
        d.clicked.connect(lambda: ctx.pages["rewards"].delete_reward(r))
        top.addWidget(d)
        self.lay.addLayout(top)
        pr = QHBoxLayout()
        self.price = label(f"★ {cost}", 20, QFont.Weight.DemiBold, T.amber, mono=True)
        pr.addWidget(self.price)
        if r["kind"] == "game" and ctx.store.settings.get("game_friday_only", True):
            pr.addWidget(label("Usable on Fridays only", 11, color=T.violet))
        pr.addStretch(1)
        self.lay.addLayout(pr)
        self.btn = Button("Claim", "primary" if can else "soft", "gift", height=38)
        self.btn.setEnabled(can)
        self.btn.setToolTip("" if can else "Not enough points yet")
        self.btn.clicked.connect(lambda: ctx.pages["rewards"].claim(r))
        self.lay.addWidget(self.btn)


class RewardsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Rewards", "Every day without gaming earns points")
        self._shown = 0
        hero = Card(pad=22, accent=T.amber)
        hr = QHBoxLayout()
        hr.setSpacing(22)
        self.mascot = Mascot(120)
        hr.addWidget(self.mascot)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("FOCUS POINTS", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        self.bal = label("0", 52, QFont.Weight.DemiBold, T.amber, mono=True)
        col.addWidget(self.bal)
        self.today_l = label("", 13, color=T.text2, wrap=True)
        col.addWidget(self.today_l)
        self.streak_l = label("", 12, color=T.green)
        col.addWidget(self.streak_l)
        hr.addLayout(col, 1)
        hero.lay.addLayout(hr)
        self.pass_pill = Pill("", T.violet, dot=True)
        self.pass_pill.hide()
        hero.lay.addWidget(self.pass_pill, 0, Qt.AlignmentFlag.AlignLeft)
        self.rule_l = label("", 12, color=T.text3, wrap=True)
        hero.lay.addWidget(self.rule_l)
        self.body.addWidget(hero)
        sh = QHBoxLayout()
        sh.addWidget(label("REWARD SHOP", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.b_new = Button("Add reward", "soft", "plus", height=34)
        sh.addWidget(self.b_new)
        self.body.addLayout(sh)
        self.shop = QVBoxLayout()
        self.shop.setSpacing(14)
        self.body.addLayout(self.shop)
        tk = Card(pad=20)
        tk.lay.addWidget(label("YOUR TICKETS", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        self.tickets = QVBoxLayout()
        self.tickets.setSpacing(8)
        tk.lay.addLayout(self.tickets)
        self.body.addWidget(tk)
        hist = Card(pad=20)
        hist.lay.addWidget(label("RECENT POINTS", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        self.hist = QVBoxLayout()
        self.hist.setSpacing(0)
        hist.lay.addLayout(self.hist)
        self.body.addWidget(hist)
        self.body.addStretch(1)
        self.b_new.clicked.connect(self.add_reward)
        self._reveal = [hero, tk, hist]
        self._sig = None

    @property
    def P(self):
        return self.ctx.points

    def on_show(self):
        self.ctx.process_points()
        self._sig = None
        super().on_show()

    def refresh(self):
        c, P, st = self.ctx, self.ctx.points, self.ctx.store
        s = st.settings
        bal = P.balance
        if bal != self._shown:
            a, b = self._shown, bal
            tween(self, a, b, 700, lambda v: self.bal.setText(str(int(round(v)))), done=lambda: self.bal.setText(str(b)))
            self._shown = b
        today_rec = play_day(st, date.today())
        played = int(today_rec["total"] // 60)
        tol = int(s.get("play_tolerance_min", 5))
        if not s.get("play_tracking", True):
            self.today_l.setText("Play tracking is off, so no points are earned. Turn it on in Settings.")
            self.mascot.set_state("sad")
        elif played > tol:
            self.today_l.setText(f"Today: {played} min of play - today will not earn points.")
            self.mascot.set_state("sad")
        else:
            self.today_l.setText(f"Today: {played} min played (up to {tol} min is fine). Stay clean until midnight for +{s.get('points_per_day', 5)}.")
            self.mascot.set_state("happy" if bal else "idle")
        n = P.clean_streak()
        self.streak_l.setText(f"{n} clean day(s) in a row · +{s.get('streak_bonus', 10)} bonus every 7" if n else "Your clean-day streak starts tonight.")
        pu = studymod.pass_until(st)
        left = pu - time.time()
        if left > 0:
            self.pass_pill.set(f"Play pass active · {int(left // 60) + 1} min left", T.violet)
            self.pass_pill.show()
        else:
            self.pass_pill.hide()
        self.rule_l.setText(f"{s.get('points_per_day', 5)} points for every day without playing. The play reward (1.5-2 hours) costs "
                            f"a lot of points and can only be used on Fridays. Days when VOIDLOCK was not watching do not count.")
        sig = (bal, len(P.d["rewards"]), tuple((t["id"], t["used"]) for t in P.d["tickets"]), c.trusted_today().weekday(),
               bool(s.get("game_friday_only", True)))
        if sig == self._sig:
            return
        self._sig = sig
        clear_layout(self.shop)
        rr = None
        for i, r in enumerate(P.d["rewards"]):
            cost = P.cost(r)
            if i % 2 == 0:
                rr = QHBoxLayout()
                rr.setSpacing(14)
                self.shop.addLayout(rr)
            rr.addWidget(RewardCard(c, r, cost, bal >= cost), 1)
        if P.d["rewards"] and len(P.d["rewards"]) % 2 == 1:
            rr.addStretch(1)
        if not P.d["rewards"]:
            self.shop.addWidget(label("No rewards - add one with the button above.", 12, color=T.text3))
        clear_layout(self.tickets)
        un = P.unused()
        if not un:
            self.tickets.addWidget(label("No tickets yet. Claim a reward and it appears here.", 12, color=T.text3))
        for t in un:
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(IconTile(color=T.violet, size=32, icon=KIND_ICON.get(t["kind"], "gift")))
            row.addWidget(label(t["name"], 13, QFont.Weight.DemiBold), 1)
            can = t["kind"] != "game" or P.game_day_ok(c.trusted_today())
            b = Button(("Use now" if can else "Use on Friday") if t["kind"] == "game" else "Mark as used",
                       "primary" if (t["kind"] == "game" and can) else "soft", height=34)
            b.setEnabled(can)
            if not can:
                b.setToolTip("Play passes can only be used on Fridays.")
            b.clicked.connect(lambda _=False, t=t: self.use_ticket(t))
            row.addWidget(b)
            w = QWidget()
            w.setLayout(row)
            self.tickets.addWidget(w)
        clear_layout(self.hist)
        led = list(reversed(P.d["ledger"]))[:8]
        if not led:
            self.hist.addWidget(label("Nothing yet. The first points arrive after your first clean day.", 12, color=T.text3))
        for i, e in enumerate(led):
            row = QHBoxLayout()
            row.setContentsMargins(0, 8, 0, 8)
            note = {"clean": "A day without playing", "bonus": "Streak bonus", "played": "Played - no points",
                    "unverified": "Not enough monitoring - no points", "spend": e.get("note", "")}.get(e["kind"], e.get("note", ""))
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(note, 13, QFont.Weight.DemiBold))
            try:
                d = date.fromisoformat(e["date"])
                col.addWidget(label(i18n.fmt_when(datetime(d.year, d.month, d.day), with_time=False), 11, color=T.text3))
            except ValueError:
                pass
            row.addLayout(col, 1)
            pts = e["pts"]
            row.addWidget(label(("+" if pts > 0 else "") + str(pts) if pts else "-", 14, QFont.Weight.DemiBold,
                                T.green if pts > 0 else (T.red if pts < 0 else T.text3), mono=True))
            w = QWidget()
            w.setLayout(row)
            self.hist.addWidget(w)
            if i < len(led) - 1:
                self.hist.addWidget(Divider())

    # ---- actions
    def claim(self, r):
        cost = self.P.cost(r)
        if not self.ctx.confirm("Claim reward?", f"“{r['name']}” costs {cost} points. You can use it whenever you are ready.",
                                "Claim", False, "gift"):
            return
        t, err = self.P.claim(r["id"])
        if not t:
            return self.ctx.toast(err, "warn")
        self.ctx.celebrate("reward")
        self.ctx.toast(f"Claimed: {r['name']}", "success")
        self._sig = None
        self.refresh()

    def use_ticket(self, t):
        if t["kind"] == "game":
            if not self.P.game_day_ok(self.ctx.trusted_today()):
                return self.ctx.toast("Play passes can only be used on Fridays.", "warn")
            if not self.ctx.confirm("Start your play pass?", f"Lock hours for games are lifted for {t['minutes']} minutes starting now. "
                                    f"Multi-day locks and focus sessions still apply.", "Start now", False, "bolt"):
                return
            if not self.P.use_ticket(t["id"]):
                return
            until = studymod.start_pass(self.ctx.store, int(t["minutes"]), self.ctx.guard.trusted_now())
            self.ctx.guard.ensure()
            self.ctx.toast(f"Play pass started - {t['minutes']} minutes. Have fun!", "success")
        else:
            if not self.P.use_ticket(t["id"]):
                return
            self.ctx.toast("Enjoy it! You earned it.", "success")
        self._sig = None
        self.refresh()
        self.ctx.session.changed.emit()

    def delete_reward(self, r):
        if self.ctx.confirm("Remove reward?", f"“{r['name']}” will be removed from the shop.", "Remove", True, "trash"):
            self.P.d["rewards"] = [x for x in self.P.d["rewards"] if x["id"] != r["id"]]
            self.P.save()
            self._sig = None
            self.refresh()

    def add_reward(self):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        ed = QLineEdit()
        ed.setPlaceholderText("Reward name, e.g. Ice cream")
        ed.setMaxLength(32)
        lay.addWidget(ed)
        kinds = [("other", "Treat"), ("movie", "Movie"), ("video", "Video"), ("game", "Gaming")]
        sel = {"k": "other"}
        row = QHBoxLayout()
        chips = []
        for k, name in kinds:
            c = Chip(name)
            c.set_checked_silent(k == "other")

            def pick(_=False, k=k):
                sel["k"] = k
                for cc, kk in chips:
                    cc.set_checked_silent(kk == k)
            c.clicked.connect(pick)
            chips.append((c, k))
            row.addWidget(c)
        row.addStretch(1)
        lay.addLayout(row)
        cr = QHBoxLayout()
        cr.addWidget(label("Cost (points)", 13, QFont.Weight.DemiBold), 1)
        cost = Stepper(30, 1, 1000, 5)
        cr.addWidget(cost)
        lay.addLayout(cr)
        mr = QHBoxLayout()
        mr.addWidget(label("Play minutes (gaming only)", 13, QFont.Weight.DemiBold), 1)
        mins = Stepper(90, 15, 300, 15, " min")
        mr.addWidget(mins)
        lay.addLayout(mr)
        m = self.ctx.new_modal().build("Add reward", None, body, "Add", validator=lambda: bool(ed.text().strip()), icon="gift")
        ed.textChanged.connect(lambda _t: m.revalidate())
        if m.exec_modal():
            self.P.d["rewards"].append({"id": studymod.uid(), "name": ed.text().strip(), "kind": sel["k"],
                                        "cost": cost.value(), "minutes": mins.value() if sel["k"] == "game" else 0})
            self.P.save()
            self._sig = None
            self.refresh()
