"""Painted pieces of the Overview dashboard: sparkline, stat card, daily bar chart, subject donut, the small start-session square.
Data comes from dashboard.py; colours come from the theme, so every theme gets the same look."""
import math
from datetime import datetime

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from . import i18n
from .icons import paint_icon
from .theme import T, font, qc
from .widgets import AA, AC, AnimWidget, Button, Card, Pill, label, tween


ABS_L = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignVCenter
ABS_R = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignVCenter


def shrinkable(lbl):
    """A label that wraps and never forces its card (and so the page) wider than the window."""
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    lbl.setMinimumWidth(0)
    return lbl


def mix(c1, c2, t):
    """Colour between two hex colours (t=0 -> c1, t=1 -> c2)."""
    a, b = QColor(c1), QColor(c2)
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def num(s):
    """Digits in the language of the UI (painted text is not translated by the label hooks)."""
    return i18n.digits(str(s)) if i18n.is_fa() else str(s)


def _smooth(path, pts):
    for i in range(1, len(pts)):
        cx = (pts[i - 1].x() + pts[i].x()) / 2
        path.cubicTo(QPointF(cx, pts[i - 1].y()), QPointF(cx, pts[i].y()), pts[i])


def menu_style():
    return (f"QMenu {{ background:{T.raised}; color:{T.text}; border:1px solid {T.border_hi}; border-radius:10px; padding:6px; }}"
            f"QMenu::item {{ padding:8px 18px; border-radius:7px; }}"
            f"QMenu::item:selected {{ background:{T.panel2}; color:{T.cyan}; }}"
            f"QMenu::separator {{ height:1px; background:{T.border}; margin:5px 8px; }}")


def popup(menu, anchor):
    """Opens `menu` under the widget `anchor`."""
    menu.setStyleSheet(menu_style())
    menu.exec(anchor.mapToGlobal(QPoint(0, anchor.height() + 4)))


# ------------------------------------------------------------------ sparkline + stat card
class Sparkline(QWidget):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._v, self._c = [], color or T.cyan

    def sizeHint(self):
        return QSize(96, 40)

    def minimumSizeHint(self):
        return QSize(34, 40)

    def set_data(self, values, color=None):
        self._v = [float(x) for x in values]
        if color:
            self._c = color
        self.update()

    def paintEvent(self, e):
        n = len(self._v)
        if n < 2:
            return
        p = QPainter(self)
        p.setRenderHint(AA)
        w, h = self.width(), self.height()
        lo, hi = min(self._v), max(self._v)
        span = (hi - lo) or 1.0
        pts = [QPointF(2 + i * (w - 4) / (n - 1), h - 4 - (h - 10) * (v - lo) / span) for i, v in enumerate(self._v)]
        if hi == lo:                                       # a flat line sits in the middle
            pts = [QPointF(q.x(), h / 2) for q in pts]
        path = QPainterPath(pts[0])
        _smooth(path, pts)
        fill = QPainterPath(path)
        fill.lineTo(QPointF(w - 2, h))
        fill.lineTo(QPointF(2, h))
        fill.closeSubpath()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, qc(self._c, 0.32))
        g.setColorAt(1, qc(self._c, 0.0))
        p.fillPath(fill, QBrush(g))
        pen = QPen(QColor(self._c), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


class StatCard(Card):
    """A small headline number with its change and a sparkline."""

    def __init__(self, title, color, parent=None):
        super().__init__(parent, pad=16)
        self.lay.setSpacing(3)
        self.setMinimumWidth(0)
        self._color = color
        cap = label(title, 11, QFont.Weight.Bold, T.text3, spacing=2.0)
        shrinkable(cap)
        self.lay.addWidget(cap)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.val = label("-", 25, QFont.Weight.DemiBold)
        self.val.setMinimumWidth(0)
        row.addWidget(self.val, 1)
        self.spark = Sparkline(color)
        row.addWidget(self.spark, 0, Qt.AlignmentFlag.AlignBottom)
        self.lay.addLayout(row)
        self.chg = shrinkable(label("", 12, color=T.text3))
        self.lay.addWidget(self.chg)

    def set(self, value_text, change_text="", change_color=None, spark=None):
        self.val.setText(value_text)
        self.chg.setText(change_text)
        self.chg.setStyleSheet(f"color:{change_color or T.text3}; background:transparent;")
        if spark is not None:
            self.spark.set_data(spark, self._color)


# ------------------------------------------------------------------ daily bars
class DailyChart(QWidget):
    """One column per day (gradient), the daily goal as a dashed line, the 7-day average as a smooth line, exam days highlighted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(214)
        self.setMouseTracking(True)
        self._ch = None
        self._grow = 1.0
        self._geo = None
        self._seen = False

    def set_chart(self, ch):
        first = self._ch is None
        self._ch = ch
        if first and not self._seen:
            self._seen = True
            self._grow = 0.0
            tween(self, 0.0, 1.0, 650, self._set_grow)
        self.update()

    def _set_grow(self, v):
        self._grow = float(v)
        self.update()

    def _layout(self):
        W, H = self.width(), self.height()
        rtl = self.isRightToLeft()
        ml, mr = (6, 30) if rtl else (30, 6)
        mt, mb = 40, 38
        return W, H, rtl, ml, mr, mt, mb, W - ml - mr, H - mt - mb

    def mouseMoveEvent(self, e):
        ch = self._ch
        if ch and ch["bars"]:
            W, H, rtl, ml, mr, mt, mb, pw, ph = self._layout()
            n = len(ch["bars"])
            x = e.position().x()
            i = int((ml + pw - x) / (pw / n)) if rtl else int((x - ml) / (pw / n))
            if 0 <= i < n:
                b = ch["bars"][i]
                from .store import fmt_hm
                d = datetime(b["date"].year, b["date"].month, b["date"].day)
                QToolTip.showText(e.globalPosition().toPoint(), f"{i18n.fmt_when(d, False)}\n{i18n.tr(fmt_hm(b['sec']))}", self)
        super().mouseMoveEvent(e)

    def paintEvent(self, e):
        ch = self._ch
        if not ch or not ch["bars"]:
            return
        try:
            self._paint(ch)
        except Exception as ex:             # a drawing problem must never take the page down
            import sys
            print("DailyChart:", ex, file=sys.stderr)

    def _legend(self, p, W, rtl, ch):
        """Hours / 7-day average / goal / exam, drawn in the top margin; items that do not fit are left out (never a wider page)."""
        from .dashboard import tx
        items = [("dot", QColor(T.cyan), tx("Hours", "ساعت")), ("line", QColor(T.violet).lighter(125) if not T.light else QColor(T.violet), tx("7-day average", "میانگین ۷ روزه"))]
        if ch["goal_sec"]:
            items.append(("dash", qc(T.violet, 0.95), tx("Goal", "هدف")))
        if any(b["exam"] for b in ch["bars"]):
            items.append(("tri", QColor(T.amber), tx("Exam", "آزمون")))
        p.setFont(font(11))
        fm = p.fontMetrics()
        x = (W - 8) if rtl else 8
        for kind, col, text in items:
            tw = fm.horizontalAdvance(text)
            need = tw + 38
            if (rtl and x - need < 6) or (not rtl and x + need > W - 6):
                break
            ix = x - 8 if rtl else x + 8
            cy = 12.0
            if kind == "dot":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawEllipse(QPointF(ix, cy), 4.5, 4.5)
            elif kind in ("line", "dash"):
                pen = QPen(col, 2.4)
                if kind == "dash":
                    pen.setDashPattern([3.0, 2.5])
                p.setPen(pen)
                p.drawLine(QPointF(ix - 8, cy), QPointF(ix + 8, cy))
            else:
                tri = QPainterPath(QPointF(ix - 5, cy - 4))
                tri.lineTo(QPointF(ix + 5, cy - 4))
                tri.lineTo(QPointF(ix, cy + 5))
                tri.closeSubpath()
                p.fillPath(tri, QBrush(col))
            p.setPen(QColor(T.text2))
            tx0 = (ix - 14 - tw) if rtl else (ix + 14)
            p.drawText(QRectF(tx0, 2, tw + 4, 20), ABS_L | Qt.AlignmentFlag.AlignVCenter, text)
            x = (x - need - 10) if rtl else (x + need + 10)

    def _paint(self, ch):
        p = QPainter(self)
        p.setRenderHint(AA)
        W, H, rtl, ml, mr, mt, mb, pw, ph = self._layout()
        bars, n = ch["bars"], len(ch["bars"])
        top = ch["top_h"] * 3600.0
        goal = ch["goal_sec"]
        slot = pw / n
        bw = max(3.0, min(16.0, slot * 0.62))
        base = mt + ph
        fa = i18n.is_fa()

        def X(i):
            return (ml + pw - (i + 0.5) * slot) if rtl else (ml + (i + 0.5) * slot)

        def Y(sec):
            return base - ph * min(sec, top) / top

        self._legend(p, W, rtl, ch)
        # grid + hour labels
        p.setFont(font(10))
        for hh in range(0, ch["top_h"] + 1, ch["step_h"]):
            y = Y(hh * 3600)
            pen = QPen(qc(T.text, 0.08 if hh else 0.14), 1)
            if hh:
                pen.setDashPattern([3.0, 5.0])
            p.setPen(pen)
            p.drawLine(QPointF(ml, y), QPointF(W - mr, y))
            p.setPen(QColor(T.text3))
            lab = QRectF((W - mr + 4) if rtl else 0, y - 8, (mr - 4) if rtl else (ml - 6), 16)
            p.drawText(lab, ABS_L if rtl else ABS_R, num(hh))
        # exam days
        for i, b in enumerate(bars):
            if b["exam"]:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(T.amber, 0.12))
                p.drawRoundedRect(QRectF(X(i) - slot / 2 + 1, mt - 2, slot - 2, ph + 2), 5, 5)
                tri = QPainterPath(QPointF(X(i) - 5, mt - 11))
                tri.lineTo(QPointF(X(i) + 5, mt - 11))
                tri.lineTo(QPointF(X(i), mt - 3))
                tri.closeSubpath()
                p.fillPath(tri, QBrush(QColor(T.amber)))
        # columns
        top_c, low_c = mix(T.cyan, "#7FF3FF", 0.45), mix(T.cyan, "#2F6BFF", 0.85)
        best = max(range(n), key=lambda k: bars[k]["sec"]) if any(b["sec"] for b in bars) else -1
        for i, b in enumerate(bars):
            if b["sec"] <= 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(T.border_hi))
                p.drawEllipse(QPointF(X(i), base - 2), 1.8, 1.8)
                continue
            hgt = max(2.0, (base - Y(b["sec"])) * self._grow)
            r = QRectF(X(i) - bw / 2, base - hgt, bw, hgt)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            reached = goal and b["sec"] >= goal
            g.setColorAt(0, qc(top_c, 1.0 if reached else 0.86))
            g.setColorAt(1, qc(low_c, 1.0 if reached else 0.62))
            p.setPen(Qt.PenStyle.NoPen)
            if reached:                                       # a soft glow behind the days that reached the goal
                p.setBrush(qc(T.cyan, 0.13))
                p.drawRoundedRect(r.adjusted(-3, -3, 3, 0), 6, 6)
            p.setBrush(g)
            rad = min(4.5, bw / 2, hgt / 2)
            p.drawRoundedRect(r, rad, rad)
        # goal line
        if goal:
            pen = QPen(qc(T.violet, 0.95), 1.4)
            pen.setDashPattern([6.0, 5.0])
            p.setPen(pen)
            p.drawLine(QPointF(ml, Y(goal)), QPointF(W - mr, Y(goal)))
        # 7-day average
        pts = [QPointF(X(i), Y(b["ma"])) for i, b in enumerate(bars) if b["ma"] is not None]
        if len(pts) > 1:
            path = QPainterPath(pts[0])
            _smooth(path, pts)
            halo = QPen(qc(T.panel, 0.9), 5.4)
            halo.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(halo)
            p.drawPath(path)
            line = QPen(QColor(T.violet).lighter(125) if not T.light else QColor(T.violet), 2.8)
            line.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(line)
            p.drawPath(path)
        # best day value
        if best >= 0 and self._grow > 0.9:
            p.setPen(QColor(T.text))
            p.setFont(font(11, QFont.Weight.Bold))
            p.drawText(QRectF(X(best) - 24, Y(bars[best]["sec"]) - 20, 48, 16), AC, num(f"{bars[best]['sec'] / 3600:.1f}"))
        # day labels (+ the month name where a month starts)
        p.setFont(font(10))
        step = 1
        while slot * step < 24:
            step += 1
        prev_m = None
        for i, b in enumerate(bars):
            d = b["date"]
            if fa:
                jy, jm, jd = i18n.to_jalali(datetime(d.year, d.month, d.day))
                day_txt, mkey, mname = num(jd), (jy, jm), i18n.FA_MONTHS[jm - 1]
            else:
                day_txt, mkey, mname = str(d.day), (d.year, d.month), d.strftime("%b")
            month_start = prev_m is not None and mkey != prev_m or i == 0
            prev_m = mkey
            if (n - 1 - i) % step == 0 or month_start:
                p.setPen(QColor(T.text if month_start else T.text3))
                p.drawText(QRectF(X(i) - 20, base + 6, 40, 14), AC, day_txt)
                if month_start:
                    p.setPen(QColor(T.text2))
                    p.drawText(QRectF(X(i) - 30, base + 20, 60, 14), AC, mname)


# ------------------------------------------------------------------ donut + legend
class ShareChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self._rows, self._total = [], 0

    def minimumSizeHint(self):
        return QSize(150, 170)

    def set_data(self, rows, total):
        self._rows, self._total = rows, total
        self.update()

    def paintEvent(self, e):
        try:
            self._paint()
        except Exception as ex:
            import sys
            print("ShareChart:", ex, file=sys.stderr)

    def _paint(self):
        p = QPainter(self)
        p.setRenderHint(AA)
        W, H = self.width(), self.height()
        rtl = self.isRightToLeft()
        size = max(80, min(H - 8, int(W * 0.46), 190))
        sw = max(12, size // 8)
        dx = (W - size - 2) if rtl else 2
        rect = QRectF(dx + sw / 2, (H - size) / 2 + sw / 2, size - sw, size - sw)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qc(T.text, 0.07), sw))
        p.drawEllipse(rect)
        tot = float(self._total)
        if tot <= 0 or not self._rows:
            p.setPen(QColor(T.text3))
            p.setFont(font(12))
            p.drawText(rect, AC, i18n.tr("No study time yet"))
            return
        ang = 90.0
        for name, color, sec in self._rows:
            span = 360.0 * sec / tot
            if span < 0.5:
                continue
            pen = QPen(QColor(color), sw)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            gap = 2.4 if len(self._rows) > 1 else 0.0
            if span > gap:
                p.drawArc(rect, int(-(ang - gap / 2) * 16), int(-(span - gap) * 16))
            ang -= span
        hours = tot / 3600.0
        p.setPen(QColor(T.text))
        p.setFont(font(max(15, size // 7), QFont.Weight.Bold))
        p.drawText(QRectF(rect.left(), rect.center().y() - size / 6.5, rect.width(), size / 4), AC, num(f"{hours:.0f}" if hours >= 10 else f"{hours:.1f}"))
        p.setPen(QColor(T.text3))
        p.setFont(font(10))
        p.drawText(QRectF(rect.left(), rect.center().y() + size / 22, rect.width(), 16), AC, i18n.tr("hours"))
        # legend
        lx0, lx1 = ((6, W - size - 18) if rtl else (size + 18, W - 6))
        rows = self._rows[:6]
        rh = min(26.0, (H - 6) / max(1, len(rows)))
        y = (H - rh * len(rows)) / 2
        for name, color, sec in rows:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            dot_x = lx1 - 5 if rtl else lx0 + 5
            p.drawEllipse(QPointF(dot_x, y + rh / 2), 4.5, 4.5)
            p.setPen(QColor(T.text))
            p.setFont(font(12))
            nm = name or i18n.tr("Others")
            tx0, tx1 = (lx0 + 40, lx1 - 16) if rtl else (lx0 + 16, lx1 - 40)
            fm = p.fontMetrics()
            p.drawText(QRectF(tx0, y, tx1 - tx0, rh), ABS_R if rtl else ABS_L,
                       fm.elidedText(nm, Qt.TextElideMode.ElideRight, int(tx1 - tx0)))
            p.setPen(QColor(T.text2))
            p.drawText(QRectF((lx0 if rtl else lx1 - 38), y, 38, rh), ABS_L if rtl else ABS_R,
                       num(round(sec / tot * 100)) + ("٪" if i18n.is_fa() else "%"))
            y += rh


# ------------------------------------------------------------------ the start-session square
class MiniRing(AnimWidget):
    """Ring with the play button (idle), the countdown (running / paused) or a check (completed)."""
    clicked = Signal()

    def __init__(self, size=88, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.state, self.frac, self.text = "idle", 0.0, ""
        self._hover = 0.0
        self._pulse = 0.0
        self.setMouseTracking(True)

    def set_state(self, state, frac, text):
        self.state, self.frac, self.text = state, max(0.0, min(1.0, frac)), text
        self.setCursor(Qt.CursorShape.PointingHandCursor if state in ("idle", "completed") else Qt.CursorShape.ArrowCursor)
        self.update()

    def on_tick(self, t):
        if self.state == "running":
            self._pulse = (t % 2.4) / 2.4
            self.update()

    def enterEvent(self, e):
        tween(self, self._hover, 1.0, 140, self._sh)
        super().enterEvent(e)

    def leaveEvent(self, e):
        tween(self, self._hover, 0.0, 220, self._sh)
        super().leaveEvent(e)

    def _sh(self, v):
        self._hover = float(v)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.state in ("idle", "completed"):
            self.clicked.emit()
        super().mousePressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        s = min(self.width(), self.height())
        sw = 6.0
        rect = QRectF((self.width() - s) / 2 + sw / 2 + 1, (self.height() - s) / 2 + sw / 2 + 1, s - sw - 2, s - sw - 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(qc(T.text, 0.09), sw))
        p.drawEllipse(rect)
        col = {"paused": T.amber, "completed": T.green}.get(self.state, T.cyan)
        if self.state in ("running", "paused", "completed"):
            frac = 1.0 if self.state == "completed" else self.frac
            g = QLinearGradient(rect.topLeft(), rect.bottomRight())
            g.setColorAt(0, QColor(col))
            g.setColorAt(1, mix(col, T.violet, 0.5) if self.state != "completed" else QColor(col))
            pen = QPen(QBrush(g), sw)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, int(-frac * 360 * 16))
        c = rect.center()
        if self.state in ("idle", "completed"):
            rad = rect.width() / 2 - 11 + 1.5 * self._hover
            if self._hover > 0.01:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(T.cyan, 0.16 * self._hover))
                p.drawEllipse(c, rad + 6, rad + 6)
            g = QLinearGradient(c.x() - rad, c.y() - rad, c.x() + rad, c.y() + rad)
            g.setColorAt(0, QColor(T.cyan))
            g.setColorAt(1, QColor(T.cyan_end))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, rad, rad)
            ic = QRectF(c.x() - rad * 0.5, c.y() - rad * 0.5, rad, rad)
            paint_icon(p, "check" if self.state == "completed" else "play", ic, T.on_accent, 2.4)
        else:
            if self.state == "running":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(T.cyan, 0.10 * (1 - self._pulse)))
                p.drawEllipse(c, rect.width() / 2 - 9 + 6 * self._pulse, rect.width() / 2 - 9 + 6 * self._pulse)
            p.setPen(QColor(T.text))
            p.setFont(font(15, QFont.Weight.Bold, mono=True, keep_mono=True))
            p.drawText(rect, AC, self.text)


class StartSquare(Card):
    """The small corner card that starts / controls a focus session. Buttons are attributes so the page can wire them."""

    def __init__(self, parent=None):
        super().__init__(parent, pad=12, accent=T.cyan)
        self.setFixedSize(172, 184)
        self.lay.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.pill = Pill("READY", T.cyan, px=10)
        top.addWidget(self.pill)
        top.addStretch(1)
        self.b_menu = Button("▾", "ghost", tip="Quick start presets", height=24, square=24)
        top.addWidget(self.b_menu)
        self.lay.addLayout(top)
        self.ring = MiniRing(78)
        self.lay.addWidget(self.ring, 0, AC)
        self.line1 = label("", 13, QFont.Weight.DemiBold, align=AC)
        self.line2 = label("", 11, color=T.text2, align=AC)
        self.lay.addWidget(self.line1)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self.line2)               # the bottom slot shows this line, or the control buttons while a session runs
        self.b_pause = Button("", "soft", "pause", "Pause blocking and the countdown (Ctrl+Enter)", square=30)
        self.b_resume = Button("", "primary", "play", "Resume (Ctrl+Enter)", square=30)
        self.b_end = Button("", "danger", "stop", "End now and keep the focus time so far", square=30)
        self.b_emerg = Button("", "soft", "shield-check", "Emergency unlock - always available. Type UNLOCK and wait for the cooldown.", square=30)
        self.b_new = Button("", "primary", "play", "New session", square=30)
        self.b_dismiss = Button("", "soft", "close", "Dismiss", square=30)
        for b in (self.b_pause, self.b_resume, self.b_end, self.b_emerg, self.b_new, self.b_dismiss):
            row.addWidget(b)
            b.hide()
        row.addStretch(1)
        self.controls = QWidget()
        self.controls.setFixedHeight(32)
        self.controls.setLayout(row)
        self.lay.addWidget(self.controls)
        self.lay.setContentsMargins(12, 10, 12, 8)

    def apply(self, state, total, remaining, clock_text, l1, l2, strict, active):
        """state: idle | running | paused | completed."""
        names = {"idle": ("READY", T.cyan), "running": ("DEEP WORK", T.green), "paused": ("PAUSED", T.amber), "completed": ("COMPLETE", T.green)}
        txt, col = names[state]
        self.pill.set(txt, col)
        frac = (remaining / total) if state in ("running", "paused") and total > 0 else (1.0 if state == "completed" else 0.0)
        self.ring.set_state(state, frac, clock_text)
        self.line1.setText(l1)
        self.line2.setText(l2)
        vis = {self.b_pause: state == "running" and not strict, self.b_resume: state == "paused", self.b_end: active and not strict,
               self.b_emerg: active, self.b_new: state == "completed", self.b_dismiss: state == "completed"}
        for b, v in vis.items():
            if b.isVisible() != v:
                b.setVisible(v)
        self.line2.setVisible(not any(vis.values()))
        self.b_menu.setEnabled(state in ("idle", "completed"))
