"""Joyful animated pieces: Mascot, Confetti, Heatmap and the 'program closed' popup card."""
import math
import random
from datetime import date, timedelta

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .store import fmt_hm
from .theme import Motion, T, font, qc
from .widgets import AA, AC, AnimWidget, Button, label, tween


STYLE = {"female": False}


def set_style(female):
    """Switches every mascot between the default and the female look (hair, bow, lashes, lipstick)."""
    STYLE["female"] = bool(female)


class Mascot(AnimWidget):
    """A friendly blob. States: idle (sleepy), study (focused, glasses), happy (cheering), sad."""

    def __init__(self, size=120, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state = "idle"
        self._t = 0.0
        self._mood = 0.0           # smooth 0..1 blend towards the 'happy' look
        self._last = None
        self.setToolTip("")

    def set_state(self, s):
        if s != self.state:
            self.state = s
            self.update()

    def on_tick(self, t):
        dt = 0.016 if self._last is None else min(0.05, t - self._last)
        self._last = t
        self._t = t
        target = 1.0 if self.state == "happy" else 0.0
        self._mood += (target - self._mood) * min(1.0, dt * 6)
        if not Motion.reduced or abs(target - self._mood) > 0.01:
            self.update()

    def _blink(self):
        ph = (self._t % 3.6)
        return 1.0 if ph > 0.14 else abs(math.cos(ph / 0.14 * math.pi / 2)) * 0.0 + (ph / 0.14)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        W = self.width()
        t = 0.0 if Motion.reduced else self._t
        st = self.state
        speed = {"idle": 1.1, "study": 1.7, "happy": 4.0, "sad": 0.8}[st]            # calmer than before
        amp = {"idle": 0.02, "study": 0.024, "happy": 0.06, "sad": 0.01}[st]
        bounce = math.sin(t * speed) * amp * W
        squash = 1 + math.sin(t * speed + 1.2) * amp * 0.9
        cx, cy = W / 2, W * 0.56 + bounce
        bw, bh = W * 0.58 * (2 - squash) * 0.5 * 2 / 1.0 * 0.5, W * 0.62 * squash * 0.5
        bw = W * 0.30 * (2 - squash)
        bh = W * 0.31 * squash
        # shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc("#000000", 0.18 if not T.light else 0.10))
        p.drawEllipse(QPointF(cx, W * 0.9), bw * 0.8 * (1 - bounce / W * 2), W * 0.04)
        fem = STYLE["female"]
        if fem:
            # hair behind the body: a cap on top and two side locks
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#2B1B3D"))
            p.drawEllipse(QRectF(cx - bw * 1.12, cy - bh * 1.22, bw * 2.24, bh * 1.25))
            p.drawRoundedRect(QRectF(cx - bw * 1.12, cy - bh * 0.35, bw * 0.32, bh * 1.25), bw * 0.16, bw * 0.16)
            p.drawRoundedRect(QRectF(cx + bw * 0.80, cy - bh * 0.35, bw * 0.32, bh * 1.25), bw * 0.16, bw * 0.16)
        # body
        g = QLinearGradient(cx - bw, cy - bh, cx + bw, cy + bh)
        g.setColorAt(0, QColor(T.cyan))
        g.setColorAt(1, QColor(T.violet))
        path = QPainterPath()
        path.addRoundedRect(QRectF(cx - bw, cy - bh, 2 * bw, 2 * bh), bw * 0.9, bh * 0.85)
        p.setBrush(g)
        p.drawPath(path)
        # glossy highlight
        p.setBrush(qc("#FFFFFF", 0.28))
        p.drawEllipse(QRectF(cx - bw * 0.62, cy - bh * 0.82, bw * 0.5, bh * 0.28))
        if fem:
            # hair bow
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FF6B9A"))
            p.drawEllipse(QPointF(cx + bw * 0.62, cy - bh * 0.92), bw * 0.22, bw * 0.14)
            p.drawEllipse(QPointF(cx + bw * 0.92, cy - bh * 0.92), bw * 0.22, bw * 0.14)
            p.setBrush(QColor("#D6336C"))
            p.drawEllipse(QPointF(cx + bw * 0.77, cy - bh * 0.92), bw * 0.07, bw * 0.07)
        # arms (happy: raised)
        arm = QColor(T.violet)
        p.setBrush(arm)
        lift = self._mood
        for sx in (-1, 1):
            ax = cx + sx * (bw + W * 0.015)
            ay = cy + bh * 0.1 - lift * bh * 0.9 + math.sin(t * 9 + sx) * lift * W * 0.02
            p.drawEllipse(QPointF(ax, ay), W * 0.055, W * 0.075)
        # cheeks
        p.setBrush(qc("#FF8FB8", 0.55))
        ey = cy - bh * 0.12
        for sx in (-1, 1):
            p.drawEllipse(QPointF(cx + sx * bw * 0.62, ey + bh * 0.34), W * 0.045, W * 0.028)
        # eyes
        eye_dx = bw * 0.42
        blink = self._blink() if st != "happy" else 1.0
        open_ = blink * (0.55 if st == "idle" else 1.0)
        for sx in (-1, 1):
            ex = cx + sx * eye_dx
            if st == "happy":
                pen = QPen(QColor("#1B1330"), W * 0.03)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(QRectF(ex - W * 0.05, ey - W * 0.04, W * 0.10, W * 0.09), 20 * 16, 140 * 16)
                p.setPen(Qt.PenStyle.NoPen)
                continue
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            ew, eh = W * 0.075, W * 0.095 * max(0.08, open_)
            p.drawEllipse(QPointF(ex, ey), ew, eh)
            p.setBrush(QColor("#1B1330"))
            look = math.sin(t * 0.9) * W * 0.02 if st == "study" else 0
            pdx = look
            pdy = (eh * 0.15) + (W * 0.012 if st == "sad" else 0)
            p.drawEllipse(QPointF(ex + pdx, ey + pdy), W * 0.038, min(eh, W * 0.045))
            if fem:
                # lashes on the outer corner of each eye
                lp = QPen(QColor("#1B1330"), W * 0.012)
                lp.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(lp)
                for k in range(3):
                    ax_ = ex + sx * ew * (0.55 + 0.22 * k)
                    ay_ = ey - eh * (0.75 - 0.15 * k)
                    p.drawLine(QPointF(ax_, ay_), QPointF(ax_ + sx * W * 0.03, ay_ - W * 0.025 + k * W * 0.005))
                p.setPen(Qt.PenStyle.NoPen)
        # mouth
        mpen = QPen(QColor("#D6336C") if fem else QColor("#1B1330"), W * 0.026)
        mpen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(mpen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        my = ey + bh * 0.55
        if st == "happy":
            p.setBrush(QColor("#1B1330"))
            p.drawChord(QRectF(cx - W * 0.07, my - W * 0.045, W * 0.14, W * 0.10), 180 * 16, 180 * 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FF6B8A"))
            p.drawEllipse(QPointF(cx, my + W * 0.03), W * 0.03, W * 0.016)
        elif st == "sad":
            p.drawArc(QRectF(cx - W * 0.045, my, W * 0.09, W * 0.05), 20 * 16, 140 * 16)
        elif st == "study":
            p.drawLine(QPointF(cx - W * 0.03, my + W * 0.01), QPointF(cx + W * 0.03, my + W * 0.01))
        else:
            p.drawArc(QRectF(cx - W * 0.04, my - W * 0.02, W * 0.08, W * 0.05), 200 * 16, 140 * 16)
        # glasses for study
        if st == "study":
            gp = QPen(qc("#1B1330", 0.9), W * 0.016)
            p.setPen(gp)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for sx in (-1, 1):
                p.drawEllipse(QPointF(cx + sx * eye_dx, ey), W * 0.098, W * 0.098)
            p.drawLine(QPointF(cx - eye_dx + W * 0.098, ey), QPointF(cx + eye_dx - W * 0.098, ey))
        # floating "z" while sleepy, sparkles while happy
        p.setPen(Qt.PenStyle.NoPen)
        if st == "idle" and not Motion.reduced:
            for i in range(2):
                ph = ((t * 0.5) + i * 0.5) % 1.0
                f = font(int(W * (0.10 + 0.05 * ph)), QFont.Weight.Bold)
                p.setFont(f)
                p.setPen(qc(T.text3, 1 - ph))
                p.drawText(QPointF(cx + bw * 0.7 + ph * W * 0.12, cy - bh * 0.9 - ph * W * 0.18), "z")
        if st == "happy" and not Motion.reduced:
            for i in range(5):
                ang = t * 2 + i * 1.26
                r = W * (0.40 + 0.04 * math.sin(t * 4 + i))
                sx_, sy_ = cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.85
                p.setBrush(qc(T.amber, 0.9))
                p.drawEllipse(QPointF(sx_, sy_), W * 0.018, W * 0.018)


class Confetti(AnimWidget):
    """Full-window overlay. burst() throws coloured paper; it hides itself when everything has fallen."""

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.parts = []
        self._last = None
        self.hide()

    def burst(self, n=140, origin=None):
        if Motion.reduced:
            return
        self.setGeometry(self.host.rect())
        w, h = self.width(), self.height()
        ox, oy = origin if origin else (w / 2, h * 0.35)
        cols = [T.cyan, T.violet, T.amber, T.green, "#FF8FB8", "#FFFFFF"]
        for _ in range(n):
            ang = random.uniform(-math.pi, 0)
            sp = random.uniform(250, 900)
            self.parts.append({"x": ox, "y": oy, "vx": math.cos(ang) * sp * random.uniform(0.4, 1),
                               "vy": math.sin(ang) * sp, "rot": random.uniform(0, 6.28),
                               "vr": random.uniform(-9, 9), "c": random.choice(cols),
                               "s": random.uniform(6, 12), "shape": random.choice(("r", "c"))})
        self.show()
        self.raise_()

    def on_tick(self, t):
        dt = 0.016 if self._last is None else min(0.05, t - self._last)
        self._last = t
        h = self.height()
        for q in self.parts:
            q["vy"] += 1300 * dt
            q["vx"] *= 0.992
            q["x"] += q["vx"] * dt
            q["y"] += q["vy"] * dt
            q["rot"] += q["vr"] * dt
        self.parts = [q for q in self.parts if q["y"] < h + 30]
        if not self.parts:
            self.hide()
            self._last = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        p.setPen(Qt.PenStyle.NoPen)
        for q in self.parts:
            p.save()
            p.translate(q["x"], q["y"])
            p.rotate(math.degrees(q["rot"]))
            p.setBrush(QColor(q["c"]))
            if q["shape"] == "r":
                p.drawRect(QRectF(-q["s"] / 2, -q["s"] / 4, q["s"], q["s"] / 2))
            else:
                p.drawEllipse(QPointF(0, 0), q["s"] / 3, q["s"] / 3)
            p.restore()


class Heatmap(AnimWidget):
    """Study calendar: columns = weeks, rows = weekdays; colour = study time (like a contribution graph)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cols, self.start = [], None
        self.setMouseTracking(True)
        self.setMinimumHeight(150)
        self._hover = None
        self._t0 = None
        self._t = 0.0
        self.fa = False

    def set_data(self, cols, start):
        self.cols, self.start = cols, start
        self._t0 = None
        self.update()

    def on_tick(self, t):
        self._t = t
        if self._t0 is None:
            self._t0 = t
        if not Motion.reduced and t - self._t0 < 1.4:
            self.update()

    def _cell(self):
        n = max(1, len(self.cols))
        c = min((self.width() - 4) / n, (self.height() - 4) / 7)
        return max(8, c)

    def mouseMoveEvent(self, e):
        c = self._cell()
        w = int(e.position().x() // c)
        d = int(e.position().y() // c)
        h = (w, d) if 0 <= w < len(self.cols) and 0 <= d < 7 and self.cols[w][d] >= 0 else None
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    @staticmethod
    def level(sec):
        m = sec / 60
        return 0 if m < 1 else 1 if m < 45 else 2 if m < 90 else 3 if m < 180 else 4

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        c = self._cell()
        gap = max(2.0, c * 0.14)
        n = len(self.cols)
        rtl = self.isRightToLeft()
        for wi, col in enumerate(self.cols):
            for di, sec in enumerate(col):
                if sec < 0:
                    continue
                x = (self.width() - (wi + 1) * c) if rtl else wi * c
                r = QRectF(x + gap / 2, di * c + gap / 2, c - gap, c - gap)
                u = 1.0 if (Motion.reduced or self._t0 is None and False) else max(0.0, min(1.0, (self._t - (self._t0 or self._t) - wi * 0.03) / 0.35))
                if self._t0 is None and not Motion.reduced:
                    u = 0.0
                lv = self.level(sec)
                col_c = QColor(T.border) if lv == 0 else qc(T.cyan, (0.30, 0.55, 0.78, 1.0)[lv - 1])
                if lv >= 3:
                    col_c = QColor(T.cyan).lighter(100 if lv == 3 else 85) if False else col_c
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col_c)
                rr = r.adjusted((1 - u) * c * 0.3, (1 - u) * c * 0.3, -(1 - u) * c * 0.3, -(1 - u) * c * 0.3)
                p.drawRoundedRect(rr, 3, 3)
                if self._hover == (wi, di):
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.setPen(QPen(QColor(T.text), 1.4))
                    p.drawRoundedRect(r, 3, 3)
        if self._hover and self.start:
            wi, di = self._hover
            d = self.start + timedelta(days=7 * wi + di)
            from . import i18n
            from datetime import datetime
            txt = f"{i18n.fmt_when(datetime(d.year, d.month, d.day), with_time=False)}  ·  {i18n.tr(fmt_hm(self.cols[wi][di]))}"
            p.setFont(font(12, QFont.Weight.DemiBold))
            tw = p.fontMetrics().horizontalAdvance(txt) + 20
            x = max(2.0, min(self.width() - tw - 2, (self.width() - (wi + 1) * c if rtl else wi * c) - tw / 2 + c / 2))
            y = max(2.0, di * c - 34)
            p.setBrush(QColor(T.raised))
            p.setPen(QPen(qc(T.border_hi), 1))
            p.drawRoundedRect(QRectF(x, y, tw, 26), 8, 8)
            p.setPen(QColor(T.text))
            p.drawText(QRectF(x, y, tw, 26), AC, txt)


class BlockPopup(QWidget):
    """Small always-on-top card shown when a blocked program was closed (while VOIDLOCK is open)."""

    def __init__(self, title, body, ms=9000):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(440, 190)
        self._k = 0.0
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(16)
        self.mascot = Mascot(92)
        self.mascot.set_state("happy")
        lay.addWidget(self.mascot)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label(title, 12, QFont.Weight.Bold, T.cyan, spacing=2.4))
        lb = label(body, 14, QFont.Weight.Medium, T.text, wrap=True)
        lb.setMinimumWidth(250)
        col.addWidget(lb, 1)
        lay.addLayout(col, 1)
        scr = QApplication.primaryScreen().availableGeometry()
        self._end = (scr.right() - self.width() - 24, scr.bottom() - self.height() - 24)
        self.move(self._end[0] + 40, self._end[1])
        self.show()
        tween(self, 0.0, 1.0, 380, self._anim)
        QTimer.singleShot(ms, self._close)

    def _anim(self, v):
        self._k = float(v)
        self.setWindowOpacity(min(1.0, self._k))
        self.move(int(self._end[0] + 40 * (1 - self._k)), self._end[1])

    def _close(self):
        tween(self, 1.0, 0.0, 300, self._anim, done=self.deleteLater)

    def mousePressEvent(self, e):
        self._close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(T.panel2))
        g.setColorAt(1, QColor(T.panel))
        p.setBrush(g)
        p.setPen(QPen(qc(T.cyan, 0.6), 1.5))
        p.drawRoundedRect(r, 18, 18)
