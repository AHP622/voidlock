"""Painted visual components: RingTimer, LockIcon, BarChart, Skeleton, IconTile, EmptyState."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QSize, Signal
from PySide6.QtGui import (QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap)
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from .icons import paint_icon
from .store import fmt_hm
from .theme import Motion, T, font, qc
from .widgets import AA, AC, AnimWidget, Button, label, tween


def _ease(u):
    u = max(0.0, min(1.0, u))
    return 1 - (1 - u) ** 3


class RingTimer(AnimWidget):
    """Animated countdown ring: moving conical gradient, pulse while focus is active,
    per-digit roll transitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 250)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.state = "idle"
        self.total = 1.0
        self.remaining = 1.0
        self.label_txt = "READY"
        self.sub_txt = ""
        self._prog = 1.0
        self._t = 0.0
        self._last = None
        self._text = "00:00"
        self._chars = []          # [{ch, prev, t0}]
        self._set_text("00:00", animate=False)

    def sizeHint(self):
        return QSize(316, 316)

    def set_session(self, state, total, remaining, label_txt, sub_txt, text):
        from .i18n import tr
        self.state, self.total, self.remaining = state, max(1.0, total), remaining
        self.label_txt, self.sub_txt = tr(label_txt), tr(sub_txt)
        self._set_text(text)
        self.update()

    def _target(self):
        if self.state in ("running", "paused"):
            return max(0.0, min(1.0, self.remaining / self.total))
        if self.state == "completed":
            return 0.0
        return 1.0

    def _set_text(self, text, animate=True):
        old = self._text
        new_chars = []
        for i, ch in enumerate(text):
            prev = None
            if animate and not Motion.reduced and len(old) == len(text) and old[i] != ch:
                prev = old[i]
            new_chars.append({"ch": ch, "prev": prev, "t0": self._t if prev is not None else 0})
        self._chars = new_chars
        self._text = text

    def on_tick(self, t):
        dt = 0.016 if self._last is None else min(0.05, t - self._last)
        self._last = t
        self._t = t
        tg = self._target()
        moving = abs(tg - self._prog) > 0.0004
        if moving:
            self._prog += (tg - self._prog) * min(1.0, dt * (10 if self.state != "idle" else 4))
        busy = (self.state in ("running",) and not Motion.reduced) or moving or \
            any(c["prev"] is not None and t - c["t0"] < 0.3 for c in self._chars) or self.state == "completed"
        if busy:
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        w, h = self.width(), self.height()
        side = min(w, h)
        c = QPointF(w / 2, h / 2)
        R = side / 2 - 40
        t = self._t
        running = self.state == "running"
        done = self.state == "completed"
        paused = self.state == "paused"
        accent = T.green if done else (T.amber if paused else T.cyan)

        # ambient breathing glow
        if running and not Motion.reduced:
            breath = (math.sin(t * 1.6) + 1) / 2
            p.setPen(Qt.PenStyle.NoPen)
            for i, (grow, a) in enumerate(((30, 0.025), (20, 0.04), (10, 0.05))):
                p.setBrush(qc(T.cyan, a * (0.5 + breath)))
                rr = R + grow * (0.6 + 0.4 * breath)
                p.drawEllipse(c, rr, rr)
            # expanding pulse ring
            ph = (t * 0.55) % 1.0
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qc(T.cyan, (1 - ph) * 0.30), 2))
            p.drawEllipse(c, R + 10 + ph * 22, R + 10 + ph * 22)

        # tick marks
        for i in range(60):
            ang = math.radians(i * 6 - 90)
            major = i % 5 == 0
            r1 = R - 20
            r2 = r1 - (8 if major else 4)
            p.setPen(QPen(qc(T.text3, 0.55 if major else 0.22), 1.4 if major else 1))
            p.drawLine(QPointF(c.x() + r1 * math.cos(ang), c.y() + r1 * math.sin(ang)),
                       QPointF(c.x() + r2 * math.cos(ang), c.y() + r2 * math.sin(ang)))

        rect = QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R)
        # track
        p.setBrush(Qt.BrushStyle.NoBrush)
        tp = QPen(qc(T.border, 1), 10)
        tp.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(tp)
        p.drawEllipse(c, R, R)

        prog = max(0.0, min(1.0, self._prog))
        if prog > 0.002:
            span = int(-prog * 360 * 16)
            grad = QConicalGradient(c, (-t * 24 if (running and not Motion.reduced) else 90))
            if done:
                grad.setColorAt(0, QColor(T.green)); grad.setColorAt(1, QColor(T.green))
            elif paused:
                grad.setColorAt(0, QColor(T.amber)); grad.setColorAt(1, QColor("#F59E0B"))
            else:
                dim = 1.0 if self.state != "idle" else 0.55
                grad.setColorAt(0.0, qc(T.cyan, dim))
                grad.setColorAt(0.45, qc(T.violet, dim))
                grad.setColorAt(0.9, qc(T.cyan, dim))
                grad.setColorAt(1.0, qc(T.cyan, dim))
            for width, alpha in ((24, 0.06), (17, 0.10)):
                gp = QPen(qc(accent, alpha), width)
                gp.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(gp)
                p.drawArc(rect, 90 * 16, span)
            pen = QPen(grad, 10)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, span)
            end_ang = math.radians(90 - prog * 360)
            ex = c.x() + R * math.cos(end_ang)
            ey = c.y() - R * math.sin(end_ang)
            if self.state in ("running", "paused") and prog > 0.01:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(accent, 0.25))
                p.drawEllipse(QPointF(ex, ey), 11, 11)
                p.setBrush(QColor("#FFFFFF"))
                p.drawEllipse(QPointF(ex, ey), 4.5, 4.5)

        # centre: digits
        fpx = max(34, int(R * 0.46))
        f = font(fpx, QFont.Weight.Medium, mono=True, keep_mono=True)
        p.setFont(f)
        fm = p.fontMetrics()
        adv = fm.horizontalAdvance("0")
        widths = [adv * (0.5 if ch["ch"] == ":" else 1.0) for ch in self._chars]
        total_w = sum(widths)
        x = c.x() - total_w / 2
        base_y = c.y() - R * 0.18
        h_line = fm.height()
        for ch, cw in zip(self._chars, widths):
            u = _ease((t - ch["t0"]) / 0.24) if ch["prev"] is not None else 1.0
            col = QColor(T.text if self.state != "idle" else T.text2)
            if ch["prev"] is not None and u < 1.0:
                oc = QColor(col); oc.setAlphaF(1 - u)
                p.setPen(oc)
                p.drawText(QRectF(x, base_y - h_line / 2 - u * 16, cw, h_line), AC, ch["prev"])
                nc = QColor(col); nc.setAlphaF(u)
                p.setPen(nc)
                p.drawText(QRectF(x, base_y - h_line / 2 + (1 - u) * 16, cw, h_line), AC, ch["ch"])
            else:
                p.setPen(col)
                p.drawText(QRectF(x, base_y - h_line / 2, cw, h_line), AC, ch["ch"])
            x += cw

        # status label
        p.setFont(font(max(11, int(R * 0.075)), QFont.Weight.Bold, spacing=3.2))
        p.setPen(QColor(accent if self.state != "idle" else T.text2))
        lab_y = base_y + h_line / 2 + 6
        p.drawText(QRectF(c.x() - R, lab_y, 2 * R, 26), AC, self.label_txt)
        p.setFont(font(max(11, int(R * 0.07)), QFont.Weight.Normal))
        p.setPen(QColor(T.text3))
        p.drawText(QRectF(c.x() - R * 0.9, lab_y + 26, 1.8 * R, 22), AC, self.sub_txt)


class LockIcon(AnimWidget):
    """Animated padlock: shackle springs shut when locked, glows while enforcing."""

    def __init__(self, size=64, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._open = 1.0
        self._locked = False
        self._color = T.text3
        self._t = 0.0

    def set_locked(self, locked, color=None):
        if color:
            self._color = color
        if locked != self._locked:
            self._locked = locked
            from PySide6.QtCore import QEasingCurve
            tween(self, self._open, 0.0 if locked else 1.0, 520, self._so, QEasingCurve.Type.OutBack,
                  overshoot=2.6)
        self.update()

    def _so(self, v):
        self._open = float(v)
        self.update()

    def on_tick(self, t):
        self._t = t
        if self._locked and not Motion.reduced:
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        s = self.width() / 24.0
        c = QColor(self._color)
        if self._locked and not Motion.reduced:
            k = (math.sin(self._t * 2.0) + 1) / 2
            p.setPen(Qt.PenStyle.NoPen)
            for i, a in enumerate((0.05, 0.08, 0.10)):
                p.setBrush(qc(self._color, a * (0.6 + 0.8 * k)))
                rad = self.width() * (0.62 - i * 0.1)
                p.drawEllipse(QPointF(self.width() / 2, self.height() / 2), rad, rad)
        p.save()
        p.scale(s, s)
        lift = 3.6 * max(0.0, self._open)
        pen = QPen(c, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(8, 11)
        path.lineTo(8, 8 - lift)
        path.cubicTo(8, 2.5 - lift, 16, 2.5 - lift, 16, 8 - lift)
        path.lineTo(16, 11 - lift * 0.6)
        p.drawPath(path)
        p.setBrush(qc(self._color, 0.16))
        p.drawRoundedRect(QRectF(5, 11, 14, 10), 3, 3)
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(12, 15.3), 1.3, 1.3)
        p.drawRoundedRect(QRectF(11.4, 15.5, 1.2, 3), 0.6, 0.6)
        p.restore()


class BarChart(AnimWidget):
    """Weekly focus bars with staggered rise animation, goal line and hover readout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setMouseTracking(True)
        self.labels, self.values, self.goal = [], [], 0
        self._t0 = None
        self._t = 0.0
        self._hover = -1
        self._today = -1

    def set_data(self, labels, values_sec, goal_min, today_index=-1):
        self.labels, self.values, self.goal = labels, values_sec, goal_min
        self._today = today_index
        self._t0 = None
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        self._t0 = None

    def on_tick(self, t):
        self._t = t
        if self._t0 is None:
            self._t0 = t
        if Motion.reduced:
            return
        if t - self._t0 < 1.2:
            self.update()

    def _geom(self):
        n = max(1, len(self.values))
        left, right, top, bottom = 38, 8, 26, 28
        plot = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)
        slot = plot.width() / n
        return plot, slot

    def mouseMoveEvent(self, e):
        plot, slot = self._geom()
        i = int((e.position().x() - plot.left()) // slot) if slot else -1
        if i >= 0 and self.isRightToLeft():
            i = len(self.values) - 1 - i
        i = i if 0 <= i < len(self.values) else -1
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        plot, slot = self._geom()
        mins = [v / 60 for v in self.values]
        top_v = max([self.goal, max(mins or [0]), 30]) * 1.15
        # grid
        p.setFont(font(11, mono=True))
        for k in range(5):
            y = plot.bottom() - plot.height() * k / 4
            p.setPen(QPen(qc(T.border, 0.9), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(T.text3))
            val = top_v * k / 4
            p.drawText(QRectF(0, y - 9, plot.left() - 6, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignAbsolute,
                       f"{int(round(val / 5.0) * 5)}")
        # goal line
        if self.goal > 0:
            gy = plot.bottom() - plot.height() * self.goal / top_v
            pen = QPen(qc(T.violet, 0.8), 1.2, Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))
            p.setPen(QColor(T.violet))
            p.setFont(font(10, QFont.Weight.DemiBold, spacing=1))
            from .i18n import tr
            p.drawText(QRectF(plot.right() - 70, gy - 18, 70, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute, tr("GOAL"))
        bw = min(46, slot * 0.52)
        rtl = self.isRightToLeft()
        n = len(mins)
        for i, m in enumerate(mins):
            si = (n - 1 - i) if rtl else i
            if Motion.reduced:
                u = 1.0
            elif self._t0 is None:
                u = 0.0
            else:
                u = _ease((self._t - self._t0 - i * 0.07) / 0.55)
            hgt = plot.height() * (m / top_v) * u
            x = plot.left() + slot * si + (slot - bw) / 2
            hov = i == self._hover
            r = QRectF(x, plot.bottom() - max(hgt, 3 if u > 0.05 else 0), bw, max(hgt, 3 if u > 0.05 else 0))
            if m <= 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(T.border_hi, 0.6))
                p.drawRoundedRect(QRectF(x, plot.bottom() - 4, bw, 4), 2, 2)
            else:
                g = QLinearGradient(r.bottomLeft(), r.topLeft())
                g.setColorAt(0, qc(T.violet, 0.9 if not hov else 1))
                g.setColorAt(1, qc(T.cyan, 0.95 if not hov else 1))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(g)
                p.drawRoundedRect(r, 7, 7)
                if hov:
                    p.setBrush(qc(T.cyan, 0.12))
                    p.drawRoundedRect(r.adjusted(-4, -4, 4, 0), 9, 9)
            p.setPen(QColor(T.cyan if i == self._today else T.text3))
            p.setFont(font(11, QFont.Weight.Bold if i == self._today else QFont.Weight.Normal))
            p.drawText(QRectF(plot.left() + slot * si, plot.bottom() + 6, slot, 18), AC,
                       self.labels[i] if i < len(self.labels) else "")
        if 0 <= self._hover < len(mins):
            i = self._hover
            from .i18n import tr
            txt = f"{self.labels[i]}  ·  {tr(fmt_hm(self.values[i]))}" if self.values[i] else f"{self.labels[i]}  ·  {tr('no focus')}"
            p.setFont(font(12, QFont.Weight.DemiBold))
            tw = p.fontMetrics().horizontalAdvance(txt) + 20
            cx = plot.left() + slot * ((n - 1 - i) if rtl else i) + slot / 2
            bx = max(plot.left(), min(plot.right() - tw, cx - tw / 2))
            by = max(2.0, plot.bottom() - plot.height() * (mins[i] / top_v) - 44)
            p.setBrush(QColor(T.raised))
            p.setPen(QPen(qc(T.border_hi), 1))
            p.drawRoundedRect(QRectF(bx, by, tw, 28), 8, 8)
            p.setPen(QColor(T.text))
            p.drawText(QRectF(bx, by, tw, 28), AC, txt)


class Skeleton(AnimWidget):
    """Shimmering placeholder rows for loading states."""

    def __init__(self, rows=5, row_h=64, gap=10, parent=None):
        super().__init__(parent)
        self.rows, self.row_h, self.gap = rows, row_h, gap
        self.setMinimumHeight(rows * (row_h + gap))
        self._t = 0.0

    def on_tick(self, t):
        self._t = t
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        sweep = ((self._t * 0.7) % 1.6) - 0.3
        for i in range(self.rows):
            r = QRectF(0, i * (self.row_h + self.gap), self.width(), self.row_h)
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            g.setColorAt(0, QColor(T.panel2))
            g.setColorAt(max(0.0, min(1.0, sweep - 0.12)), QColor(T.panel2))
            g.setColorAt(max(0.0, min(1.0, sweep)), QColor(T.raised))
            g.setColorAt(max(0.0, min(1.0, sweep + 0.12)), QColor(T.panel2))
            g.setColorAt(1, QColor(T.panel2))
            p.setBrush(g)
            p.setPen(QPen(qc(T.border), 1))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(T.border_hi, 0.6))
            p.drawRoundedRect(QRectF(16, r.top() + 14, 36, 36), 10, 10)
            p.drawRoundedRect(QRectF(68, r.top() + 18, 160, 10), 5, 5)
            p.drawRoundedRect(QRectF(68, r.top() + 38, 100, 8), 4, 4)


class IconTile(QWidget):
    """Rounded tile: real executable icon if available, else a tinted initial/glyph."""

    def __init__(self, text="?", color=T.cyan, size=40, icon=None, pixmap: QPixmap = None, parent=None):
        super().__init__(parent)
        self.text, self.color, self.icon, self.pix = text, color, icon, pixmap
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, qc(self.color, 0.22))
        g.setColorAt(1, qc(self.color, 0.07))
        p.setBrush(g)
        p.setPen(QPen(qc(self.color, 0.35), 1))
        p.drawRoundedRect(r, self.width() * 0.28, self.width() * 0.28)
        if self.pix and not self.pix.isNull():
            s = int(self.width() * 0.6)
            p.drawPixmap(int((self.width() - s) / 2), int((self.height() - s) / 2), s, s,
                         self.pix.scaled(s * 2, s * 2, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        elif self.icon:
            paint_icon(p, self.icon, r.adjusted(self.width() * 0.22, self.width() * 0.22,
                                                -self.width() * 0.22, -self.width() * 0.22), self.color, 1.8)
        else:
            p.setPen(QColor(self.color))
            p.setFont(font(int(self.width() * 0.42), QFont.Weight.Bold))
            p.drawText(r, AC, (self.text or "?")[:1].upper())


class EmptyState(QWidget):
    action = Signal()

    def __init__(self, icon, title, text, button=None, color=T.cyan, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(20, 34, 20, 34)
        lay.addWidget(IconTile(color=color, size=64, icon=icon), 0, AC)
        lay.addSpacing(8)
        lay.addWidget(label(title, 17, QFont.Weight.DemiBold, align=AC), 0, AC)
        lb = label(text, 13, color=T.text2, wrap=True, align=AC)
        lb.setFixedWidth(360)
        lb.setMinimumHeight(lb.heightForWidth(360) + 4)
        lay.addWidget(lb, 0, AC)
        if button:
            b = Button(button, "primary")
            b.clicked.connect(self.action.emit)
            lay.addSpacing(8)
            lay.addWidget(b, 0, AC)
