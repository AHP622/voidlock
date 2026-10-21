"""Reusable animated primitives: ticker, tween, Button, Toggle, Chip, Stepper, Card..."""
import time

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QObject, QPointF, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QSizePolicy, QVBoxLayout, QWidget)

from .icons import paint_icon
from .theme import Motion, T, font, qc

AA = QPainter.RenderHint.Antialiasing
AC = Qt.AlignmentFlag.AlignCenter
AL = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignAbsolute
AV = Qt.AlignmentFlag.AlignVCenter


# ------------------------------------------------------------------ animation core
class Ticker(QObject):
    """One shared frame clock. Runs only while at least one widget is visible and animating."""
    tick = Signal(float)
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = Ticker()
        return cls._inst

    def __init__(self):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on)
        self._n = 0
        self._t0 = time.perf_counter()

    def now(self):
        return time.perf_counter() - self._t0

    def _on(self):
        self.tick.emit(self.now())

    def acquire(self):
        self._n += 1
        self.refresh()

    def release(self):
        self._n = max(0, self._n - 1)
        self.refresh()

    def refresh(self):
        if self._n > 0:
            self._timer.start(250 if Motion.reduced else 16)
        else:
            self._timer.stop()


class AnimWidget(QWidget):
    """Widget that receives frame ticks only while visible."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ticking = False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._ticking:
            self._ticking = True
            Ticker.get().tick.connect(self.on_tick)
            Ticker.get().acquire()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._stop_ticking()

    def _stop_ticking(self):
        if self._ticking:
            self._ticking = False
            try:
                Ticker.get().tick.disconnect(self.on_tick)
            except (RuntimeError, TypeError):
                pass
            try:
                Ticker.get().release()
            except RuntimeError:     # interpreter shutdown: the timer is already gone
                pass

    def closeEvent(self, e):
        self._stop_ticking()
        super().closeEvent(e)

    def on_tick(self, t):
        self.update()


def tween(owner, a, b, ms, cb, easing=QEasingCurve.Type.OutCubic, done=None, overshoot=None):
    """Run a value animation. With reduced motion the end value is applied immediately."""
    ms = Motion.ms(ms)
    if ms == 0:
        cb(b)
        if done:
            done()
        return None
    an = QVariantAnimation(owner)
    an.setStartValue(float(a))
    an.setEndValue(float(b))
    an.setDuration(ms)
    curve = QEasingCurve(easing)
    if overshoot is not None:
        curve.setOvershoot(overshoot)
    an.setEasingCurve(curve)
    an.valueChanged.connect(cb)
    if done:
        an.finished.connect(done)
    an.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return an


def reveal(widget, delay=0, dy=14, ms=420):
    """Staggered entrance: fade + rise. Safe under layouts (restores the final position)."""
    if Motion.reduced or widget is None:
        return

    def go():
        if not widget.isVisible():
            return
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
        end = widget.pos()
        widget.move(end.x(), end.y() + dy)
        grp_done = {"n": 0}

        def fin():
            grp_done["n"] += 1
            if grp_done["n"] == 2:
                widget.setGraphicsEffect(None)

        a = QPropertyAnimation(eff, b"opacity", widget)
        a.setDuration(ms)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(fin)
        b = QPropertyAnimation(widget, b"pos", widget)
        b.setDuration(ms)
        b.setStartValue(QPointF(end.x(), end.y() + dy).toPoint())
        b.setEndValue(end)
        b.setEasingCurve(QEasingCurve.Type.OutCubic)
        b.finished.connect(fin)
        a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        b.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    QTimer.singleShot(max(0, delay), go)


def label(text="", px=13, weight=QFont.Weight.Normal, color=T.text, mono=False, spacing=0.0,
          wrap=False, align=None):
    lb = QLabel()
    lb.setText(text)
    lb.setFont(font(px, weight, mono, spacing))
    lb.setStyleSheet(f"color:{color}; background:transparent;")
    lb.setWordWrap(wrap)
    if align is not None:
        lb.setAlignment(align)
    return lb


def clear_layout(lay):
    """Remove and destroy every child of a layout (hides first so nothing lingers visually)."""
    while lay.count():
        it = lay.takeAt(0)
        wd = it.widget()
        if wd is not None:
            wd.hide()
            wd.setParent(None)
            wd.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


def set_label_color(lb, color):
    lb.setStyleSheet(f"color:{color}; background:transparent;")


# ------------------------------------------------------------------ buttons
class Button(QAbstractButton):
    """variant: primary | ghost | danger | violet | soft | icon"""

    def __init__(self, text="", variant="ghost", icon=None, tip=None, parent=None, height=40,
                 square=None):
        super().__init__(parent)
        self.setText(text)
        self.variant = variant
        self.icon_name = icon
        self._hover = 0.0
        self._scale = 1.0
        self._kb = False
        self._h = height
        self._square = square
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(font(13, QFont.Weight.DemiBold))
        if tip:
            self.setToolTip(tip)
        self.pressed.connect(self._down)
        self.released.connect(self._up)
        if square:
            self.setFixedSize(square, square)
        else:
            self.setMinimumHeight(height)
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def set_icon(self, name):
        self.icon_name = name
        self.update()

    def sizeHint(self):
        if self._square:
            return QSize(self._square, self._square)
        w = self.fontMetrics().horizontalAdvance(self.text()) + 34
        if self.icon_name:
            w += 24 if self.text() else 0
        return QSize(max(w, 44), self._h)

    def enterEvent(self, e):
        tween(self, self._hover, 1.0, 140, self._set_hover)
        super().enterEvent(e)

    def leaveEvent(self, e):
        tween(self, self._hover, 0.0, 200, self._set_hover)
        super().leaveEvent(e)

    def _set_hover(self, v):
        self._hover = float(v)
        self.update()

    def _set_scale(self, v):
        self._scale = float(v)
        self.update()

    def _down(self):
        tween(self, self._scale, 0.94, 80, self._set_scale)

    def _up(self):  # spring back
        tween(self, self._scale, 1.0, 380, self._set_scale, QEasingCurve.Type.OutBack, overshoot=3.2)

    def focusInEvent(self, e):
        self._kb = e.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                                  Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(e)
        self.update()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        en = self.isEnabled()
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        c = r.center()
        p.translate(c)
        p.scale(self._scale, self._scale)
        p.translate(-c)
        rad = min(T.r_md, r.height() / 2)
        h = self._hover
        v = self.variant
        txt = T.text
        if v == "primary":
            if en and h > 0:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc(T.cyan, 0.16 * h))
                p.drawRoundedRect(r.adjusted(-3, -3, 3, 3), rad + 3, rad + 3)
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor(T.cyan).lighter(100 + int(10 * h)))
            g.setColorAt(1, QColor(T.cyan_end).lighter(100 + int(8 * h)))
            p.setBrush(g if en else qc(T.border_hi))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, rad, rad)
            txt = T.on_accent if en else T.text3
        elif v == "violet":
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor(T.violet).lighter(100 + int(14 * h)))
            g.setColorAt(1, QColor(T.violet_end).lighter(100 + int(10 * h)))
            p.setBrush(g if en else qc(T.border_hi))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, rad, rad)
            txt = "#FFFFFF" if en else T.text3
        elif v == "danger":
            p.setBrush(qc(T.red, 0.06 + 0.16 * h))
            p.setPen(QPen(qc(T.red, 0.55 + 0.4 * h), 1))
            p.drawRoundedRect(r, rad, rad)
            txt = T.red if en else T.text3
        elif v == "soft":
            p.setBrush(qc(T.raised, 0.7 + 0.3 * h))
            p.setPen(QPen(qc(T.border_hi, 0.6 + 0.4 * h), 1))
            p.drawRoundedRect(r, rad, rad)
            txt = T.text if en else T.text3
        elif v == "icon":
            p.setBrush(qc(T.raised, 0.9 * h))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, 9, 9)
            txt = T.text2 if h < 0.5 else T.text
        else:  # ghost
            p.setBrush(qc(T.raised, 0.8 * h))
            p.setPen(QPen(qc(T.border_hi if h < 0.2 else T.text3, 1), 1))
            p.drawRoundedRect(r, rad, rad)
            txt = T.text if en else T.text3
        if v == "danger" and self.variant == "danger" and self.isEnabled() and h > 0.6:
            txt = "#FFFFFF" if False else T.red
        if self._kb and self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qc(T.cyan, 0.9), 1.6))
            p.drawRoundedRect(r.adjusted(-2.5, -2.5, 2.5, 2.5), rad + 2, rad + 2)
        # content
        fm = self.fontMetrics()
        tw = fm.horizontalAdvance(self.text())
        iw = 18 if self.icon_name else 0
        gap = 8 if (self.icon_name and self.text()) else 0
        total = iw + gap + tw
        x = r.center().x() - total / 2
        p.setPen(QColor(txt))
        rtl = self.isRightToLeft()
        ix = x + tw + gap if rtl else x
        tx = x if rtl else x + iw + gap
        if self.icon_name:
            paint_icon(p, self.icon_name, QRectF(ix, r.center().y() - 9, 18, 18), txt, 1.8)
        if self.text():
            p.setFont(self.font())
            p.drawText(QRectF(tx, r.top(), tw + 4, r.height()), AV | AL, self.text())


class Chip(QAbstractButton):
    """Small selectable filter chip."""

    def __init__(self, text, parent=None, color=T.cyan, count=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.color = color
        self._on = 0.0
        self._hover = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(font(12, QFont.Weight.DemiBold))
        self.setFixedHeight(32)
        self.toggled.connect(lambda c: tween(self, self._on, 1.0 if c else 0.0, 180, self._s))

    def _s(self, v):
        self._on = float(v)
        self.update()

    def set_checked_silent(self, c):
        self.blockSignals(True)
        self.setChecked(c)
        self.blockSignals(False)
        self._on = 1.0 if c else 0.0
        self.update()

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 28, 32)

    def enterEvent(self, e):
        tween(self, self._hover, 1.0, 120, self._h)
        super().enterEvent(e)

    def leaveEvent(self, e):
        tween(self, self._hover, 0.0, 160, self._h)
        super().leaveEvent(e)

    def _h(self, v):
        self._hover = float(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        o = self._on
        p.setBrush(qc(self.color, 0.14 * o + 0.05 * self._hover))
        border = QColor(self.color)
        border.setAlphaF(0.75 * o)
        base = qc(T.border_hi, 1 - o)
        p.setPen(QPen(border if o > 0.5 else base, 1))
        p.drawRoundedRect(r, 16, 16)
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qc(T.cyan, 0.7), 1.4))
            p.drawRoundedRect(r.adjusted(-1.5, -1.5, 1.5, 1.5), 17, 17)
        col = QColor(T.text2)
        tc = QColor(self.color)
        mix = QColor(int(col.red() + (tc.red() - col.red()) * o), int(col.green() + (tc.green() - col.green()) * o),
                     int(col.blue() + (tc.blue() - col.blue()) * o))
        p.setPen(mix)
        p.setFont(self.font())
        p.drawText(r, AC, self.text())


class Toggle(QAbstractButton):
    def __init__(self, checked=False, parent=None, tip=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if tip:
            self.setToolTip(tip)
        self.toggled.connect(lambda c: tween(self, self._pos, 1.0 if c else 0.0, 320, self._s,
                                             QEasingCurve.Type.OutBack, overshoot=2.2))

    def _s(self, v):
        self._pos = float(v)
        self.update()

    def set_silent(self, c):
        self.blockSignals(True)
        self.setChecked(c)
        self.blockSignals(False)
        self._pos = 1.0 if c else 0.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(2, 4, -2, -4)
        k = max(0.0, min(1.0, self._pos))
        en = self.isEnabled()
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, qc(T.cyan, (0.9 if en else 0.35) * k + 0.0))
        g.setColorAt(1, qc(T.violet, (0.9 if en else 0.35) * k))
        p.setBrush(qc(T.raised, 1 - k * 0.6))
        p.setPen(QPen(qc(T.border_hi, 1 - k), 1))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        if k > 0.01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        pos = (1 - self._pos) if self.isRightToLeft() else self._pos
        x = r.left() + 3 + (r.width() - d - 6) * pos
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc("#000000", 0.35))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))
        p.setBrush(QColor("#FFFFFF") if en else QColor(T.text3))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(qc(T.cyan, 0.8), 1.5))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 2, -0.5, -2), 13, 13)


class Pill(QWidget):
    """Tinted status label."""

    def __init__(self, text="", color=T.cyan, dot=False, parent=None, px=11):
        super().__init__(parent)
        from .i18n import tr
        self._t, self._c, self._dot = tr(text), color, dot
        self._px = px
        self.setFont(font(px, QFont.Weight.DemiBold, spacing=0.6))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._upd()

    def set(self, text, color=None):
        from .i18n import tr
        self._t = tr(text)
        if color:
            self._c = color
        self._upd()

    def _upd(self):
        self.setFixedSize(self.sizeHint())
        self.update()

    def sizeHint(self):
        self.ensurePolished()
        w = self.fontMetrics().horizontalAdvance(self._t) + 0.7 * len(self._t) + 30 + (12 if self._dot else 0)
        return QSize(int(w), 24)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(qc(self._c, 0.13))
        p.setPen(QPen(qc(self._c, 0.4), 1))
        p.drawRoundedRect(r, 12, 12)
        rtl = self.isRightToLeft()
        left, right = 6.0, r.width() - 6.0
        if self._dot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(self._c))
            dx = (r.width() - 14) if rtl else 14
            p.drawEllipse(QPointF(dx, r.center().y()), 3, 3)
            if rtl:
                right -= 16
            else:
                left += 16
        tc = QColor(self._c).darker(135) if T.light else qc(self._c)
        p.setPen(tc)
        p.setFont(self.font())
        p.drawText(QRectF(left, 0, right - left, r.height()), AC, self._t)


# ------------------------------------------------------------------ containers
class Card(QFrame):
    def __init__(self, parent=None, pad=20, accent=None, hover=False):
        super().__init__(parent)
        self.accent = accent
        self._hover_fx = hover
        self._h = 0.0
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(pad, pad, pad, pad)
        self.lay.setSpacing(12)
        if hover:
            self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, e):
        if self._hover_fx:
            tween(self, self._h, 1.0, 160, self._sh)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._hover_fx:
            tween(self, self._h, 0.0, 220, self._sh)
        super().leaveEvent(e)

    def _sh(self, v):
        self._h = float(v)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(T.panel2))
        g.setColorAt(1, QColor(T.panel))
        p.setBrush(g)
        edge = QColor(T.border_hi if self._h > 0.01 else T.border)
        if self.accent:
            edge = qc(self.accent, 0.25 + 0.4 * self._h)
        p.setPen(QPen(edge, 1))
        p.drawRoundedRect(r, T.r_lg, T.r_lg)
        # hairline highlight along the top edge
        hl = QLinearGradient(r.topLeft(), r.topRight())
        hl.setColorAt(0, qc("#FFFFFF", 0))
        hl.setColorAt(0.5, qc("#FFFFFF", 0.07 + 0.06 * self._h))
        hl.setColorAt(1, qc("#FFFFFF", 0))
        p.setPen(QPen(hl, 1))
        p.drawLine(QPointF(r.left() + T.r_lg, r.top() + 0.5), QPointF(r.right() - T.r_lg, r.top() + 0.5))


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{T.border}; border:none;")


class Stepper(QWidget):
    """[-] value [+]  with hold-free click steps, wheel and keyboard (Up/Down)."""
    valueChanged = Signal(int)

    def __init__(self, value=50, lo=1, hi=999, step=5, suffix="", parent=None):
        super().__init__(parent)
        self.lo, self.hi, self.step, self.suffix = lo, hi, step, suffix
        try:
            self._v = max(lo, min(hi, int(value)))
        except (TypeError, ValueError):
            self._v = lo
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.b_minus = Button("", "soft", "minus", "Decrease", square=36)
        self.b_plus = Button("", "soft", "plus", "Increase", square=36)
        self.lbl = label("", 15, QFont.Weight.DemiBold, mono=True, align=AC)
        self.lbl.setMinimumWidth(78)
        lay.addWidget(self.b_minus)
        lay.addWidget(self.lbl)
        lay.addWidget(self.b_plus)
        for b in (self.b_minus, self.b_plus):
            b.setAutoRepeat(True)
            b.setAutoRepeatDelay(350)
            b.setAutoRepeatInterval(70)
        self.b_minus.clicked.connect(lambda: self.set_value(self._v - self.step))
        self.b_plus.clicked.connect(lambda: self.set_value(self._v + self.step))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._show()

    def value(self):
        return self._v

    def set_value(self, v, emit=True):
        v = max(self.lo, min(self.hi, int(v)))
        if v != self._v:
            self._v = v
            self._show()
            if emit:
                self.valueChanged.emit(v)
        self.b_minus.setEnabled(self._v > self.lo)
        self.b_plus.setEnabled(self._v < self.hi)

    def _show(self):
        self.lbl.setText(f"{self._v}{self.suffix}")
        self.b_minus.setEnabled(self._v > self.lo)
        self.b_plus.setEnabled(self._v < self.hi)

    def wheelEvent(self, e):
        # Only when the stepper was clicked into focus. Otherwise the wheel belongs to the page: scrolling Settings
        # used to change whatever value happened to be under the mouse (even the day-lock release wait).
        if not self.hasFocus() and not any(b.hasFocus() for b in (self.b_minus, self.b_plus)):
            e.ignore()
            return
        self.set_value(self._v + (self.step if e.angleDelta().y() > 0 else -self.step))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Right):
            self.set_value(self._v + self.step)
        elif e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Left):
            self.set_value(self._v - self.step)
        else:
            super().keyPressEvent(e)


class Segmented(QWidget):
    currentChanged = Signal(int)

    def __init__(self, options, current=0, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.chips = []
        for i, o in enumerate(options):
            c = Chip(o)
            c.set_checked_silent(i == current)
            c.clicked.connect(lambda _=False, i=i: self.set_current(i))
            lay.addWidget(c)
            self.chips.append(c)
        lay.addStretch(1)
        self._cur = current

    def current(self):
        return self._cur

    def set_current(self, i, emit=True):
        for k, c in enumerate(self.chips):
            c.set_checked_silent(k == i)
        if i != self._cur:
            self._cur = i
            if emit:
                self.currentChanged.emit(i)


class _SearchIcon(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(44, 44)

    def paintEvent(self, e):
        p = QPainter(self)
        paint_icon(p, "search", QRectF(13, 13, 18, 18),
                   T.cyan if self.parent().edit.hasFocus() else T.text3, 1.8)


class SearchField(QWidget):
    from PySide6.QtWidgets import QLineEdit as _LE
    textChanged = Signal(str)

    def __init__(self, placeholder="Search", parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QLineEdit
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText(placeholder)
        from .i18n import is_fa
        pad = "padding-left:34px; padding-right:36px;" if is_fa() else "padding-left:36px; padding-right:34px;"
        self.edit.setStyleSheet(
            f"QLineEdit{{{pad} background:{T.panel2};"
            f"border:1px solid {T.border}; border-radius:12px; min-height:22px;}}"
            f"QLineEdit:hover{{border-color:{T.border_hi};}} QLineEdit:focus{{border:1px solid {T.cyan};}}")
        self.edit.textChanged.connect(self._chg)
        self.edit.installEventFilter(self)
        self.clear_btn = Button("", "icon", "close", "Clear search", self, square=28)
        self.clear_btn.clicked.connect(lambda: (self.edit.clear(), self.edit.setFocus()))
        self.clear_btn.hide()
        self.icon_overlay = _SearchIcon(self)
        self.setFixedHeight(44)
        self.setMinimumWidth(220)

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if ev.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self.icon_overlay.update()
        return False

    def _chg(self, t):
        self.clear_btn.setVisible(bool(t))
        self.textChanged.emit(t)

    def text(self):
        return self.edit.text()

    def focus(self):
        self.edit.setFocus()
        self.edit.selectAll()

    def resizeEvent(self, e):
        self.edit.setGeometry(0, 0, self.width(), self.height())
        from .i18n import is_fa
        if is_fa():
            self.clear_btn.move(6, (self.height() - 28) // 2)
            self.icon_overlay.move(self.width() - 44, 0)
        else:
            self.clear_btn.move(self.width() - 34, (self.height() - 28) // 2)
            self.icon_overlay.move(0, 0)
        self.icon_overlay.raise_()



class ProgressBar(AnimWidget):
    def __init__(self, parent=None, height=8):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._target = 0.0
        self._v = 0.0
        self._last = None

    def set_value(self, v):
        self._target = max(0.0, min(1.0, v))
        self.update()

    def on_tick(self, t):
        if abs(self._target - self._v) > 0.0005:
            dt = 0.016 if self._last is None else min(0.05, t - self._last)
            self._v += (self._target - self._v) * min(1.0, dt * 7)
            self.update()
        self._last = t

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(T.border))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        w = max(r.height(), r.width() * self._v) if self._v > 0.003 else 0
        if w:
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, QColor(T.cyan))
            g.setColorAt(1, QColor(T.violet))
            p.setBrush(g)
            left = (r.right() - w) if self.isRightToLeft() else r.left()
            p.drawRoundedRect(QRectF(left, r.top(), w, r.height()), r.height() / 2, r.height() / 2)
