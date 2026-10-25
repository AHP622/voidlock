"""Reusable animated primitives: ticker, tween, Button, Toggle, Chip, Stepper, Card..."""
import time

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QObject, QPointF, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QAbstractButton, QScrollArea, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
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
        self._timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._timer.timeout.connect(self._on)
        try:
            from PySide6.QtGui import QGuiApplication
            if QGuiApplication.instance() is not None:
                QGuiApplication.instance().applicationStateChanged.connect(self._on_app_state)
        except Exception:
            pass
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

    # Ambient animations (the character's breathing, pulsing dots) run at a calm 30 frames per second, and at 5 while
    # the window is in the background or minimised. They used to run at 60 all the time, which kept the CPU busy and made
    # everything feel restless. Short transitions (toggles, bars, fades) have their own animators and stay smooth.
    FRAME_MS, BACKGROUND_MS, REDUCED_MS = 33, 200, 250

    def _on_app_state(self, _state=None):
        self.refresh()

    def refresh(self):
        if self._n <= 0:
            self._timer.stop()
            return
        if Motion.reduced:
            ms = self.REDUCED_MS
        else:
            try:
                from PySide6.QtGui import QGuiApplication
                active = QGuiApplication.applicationState() == Qt.ApplicationState.ApplicationActive
            except Exception:
                active = True
            ms = self.FRAME_MS if active else self.BACKGROUND_MS
        if self._timer.interval() != ms or not self._timer.isActive():
            self._timer.start(ms)


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


def reveal(widget, delay=0, dy=0, ms=240):
    """Gentle fade-in, optionally staggered by `delay`.

    The widget is hidden at once (opacity 0) and only the fade is delayed. (It used to be shown fully, then switched off
    and faded in again after the delay: every page flashed on arrival. It also slid by a few pixels, which fought with the
    layout whenever a value changed during the animation and made things jitter.) `dy` is kept for old callers and ignored."""
    if Motion.reduced or widget is None:
        return
    old = widget.graphicsEffect()
    if old is not None and getattr(old, "_vl_reveal", False):
        old.setOpacity(0.0)                       # restart: reuse the effect that is already there
        eff = old
    else:
        eff = QGraphicsOpacityEffect(widget)
        eff._vl_reveal = True
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
    gen = getattr(eff, "_vl_gen", 0) + 1
    eff._vl_gen = gen

    def go():
        if getattr(eff, "_vl_gen", 0) != gen:
            return                                # a newer reveal took over
        try:
            a = QPropertyAnimation(eff, b"opacity", eff)
        except RuntimeError:
            return                                # the widget was deleted meanwhile
        a.setDuration(Motion.ms(ms))
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutQuad)

        def fin():
            try:
                if widget.graphicsEffect() is eff and getattr(eff, "_vl_gen", 0) == gen:
                    widget.setGraphicsEffect(None)   # no effect left behind: it would re-render the widget on every paint
            except RuntimeError:
                pass
        a.finished.connect(fin)
        a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    if delay <= 0:
        QTimer.singleShot(0, go)
    else:
        QTimer.singleShot(int(delay), go)


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

    def __init__(self, value=50, lo=1, hi=999, step=5, suffix="", parent=None, label_w=78):
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
        self.lbl.setMinimumWidth(label_w)
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


class ChipGrid(QWidget):
    """Like Segmented, but wraps into rows (for a longer list of options)."""
    currentChanged = Signal(int)

    def __init__(self, options, current=0, per_row=5, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QGridLayout
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.chips = []
        for i, o in enumerate(options):
            c = Chip(o)
            c.set_checked_silent(i == current)
            c.clicked.connect(lambda _=False, i=i: self.set_current(i))
            lay.addWidget(c, i // per_row, i % per_row)
            self.chips.append(c)
        lay.setColumnStretch(per_row, 1)
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


class ThemePicker(QWidget):
    """Little preview cards, one per theme (background, panel and accent colours); click one to choose it."""
    currentChanged = Signal(int)

    def __init__(self, keys, names, current=0, parent=None):
        super().__init__(parent)
        from .theme import THEMES
        self._themes = [THEMES[k] for k in keys]
        self._names = [names[k] for k in keys]
        self._cur, self._hover = current, -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(78)
        self._cw, self._gap = 78, 10
        self.setMinimumWidth(len(keys) * (self._cw + self._gap))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def current(self):
        return self._cur

    def set_current(self, i, emit=True):
        if i != self._cur:
            self._cur = i
            self.update()
            if emit:
                self.currentChanged.emit(i)

    def _idx(self, pos):
        i = int(pos.x() // (self._cw + self._gap))
        return i if 0 <= i < len(self._themes) and pos.x() % (self._cw + self._gap) <= self._cw else -1

    def mouseMoveEvent(self, e):
        i = self._idx(e.position())
        if i != self._hover:
            self._hover = i
            self.setToolTip(i18n_tr(self._names[i]) if i >= 0 else "")
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, e):
        i = self._idx(e.position())
        if i >= 0:
            self.set_current(i)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(AA)
        for i, th in enumerate(self._themes):
            x = i * (self._cw + self._gap)
            r = QRectF(x + 1, 1, self._cw - 2, 52)
            p.setPen(QPen(qc(T.cyan if i == self._cur else T.border_hi, 1.0 if i == self._cur else 0.7), 2 if i == self._cur else 1))
            p.setBrush(QColor(th["bg"]))
            p.drawRoundedRect(r, 10, 10)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(th["panel"]))
            p.drawRoundedRect(QRectF(x + 8, 9, self._cw - 16, 22), 6, 6)
            p.setBrush(QColor(th["cyan"]))
            p.drawRoundedRect(QRectF(x + 12, 15, 26, 6), 3, 3)
            p.setBrush(QColor(th["violet"]))
            p.drawEllipse(QPointF(x + self._cw - 17, 20), 5, 5)
            p.setBrush(QColor(th["raised"]))
            p.drawRoundedRect(QRectF(x + 8, 36, self._cw - 16, 10), 5, 5)
            p.setPen(QColor(T.text if i == self._cur else T.text2))
            p.setFont(font(11, QFont.Weight.DemiBold if i == self._cur else QFont.Weight.Normal))
            p.drawText(QRectF(x, 56, self._cw, 18), AC, i18n_tr(self._names[i]))


def i18n_tr(s):
    from .i18n import tr
    return tr(s)


class SmoothScrollArea(QScrollArea):
    """Scroll area whose mouse wheel glides instead of jumping a whole notch at once."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = None
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.verticalScrollBar().setValue(int(v)))

    def wheelEvent(self, e):
        bar = self.verticalScrollBar()
        if Motion.reduced or bar.maximum() == 0 or e.angleDelta().y() == 0 or e.modifiers() != Qt.KeyboardModifier.NoModifier:
            return super().wheelEvent(e)
        base = self._target if (self._target is not None and self._anim.state() == QAbstractAnimation.State.Running) else bar.value()
        self._target = max(bar.minimum(), min(bar.maximum(), base - e.angleDelta().y() * 0.75))
        self._anim.stop()
        self._anim.setStartValue(float(bar.value()))
        self._anim.setEndValue(float(self._target))
        self._anim.start()
        e.accept()


class DateField(QWidget):
    """Year / month / day steppers: Jalali in Persian, Gregorian in English; an invalid day (31 Shahrivar...) is pulled back."""
    changed = Signal()

    def __init__(self, d=None):
        super().__init__()
        from datetime import date as _date, datetime as _dt
        from . import i18n
        self._i18n, self._dt, self._date = i18n, _dt, _date
        self.jalali = i18n.is_fa()
        d = d or _date.today()
        y, m, dd = i18n.to_jalali(_dt(d.year, d.month, d.day)) if self.jalali else (d.year, d.month, d.day)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        # compact: three full-size steppers (510 px) were wider than a dialog and got squashed
        self.y = Stepper(y, 1300 if self.jalali else 2000, 1500 if self.jalali else 2100, 1, label_w=56)
        self.m = Stepper(m, 1, 12, 1, label_w=34)
        self.d = Stepper(dd, 1, 31, 1, label_w=34)
        for w in (self.y, self.m, self.d):
            row.addWidget(w)
            w.valueChanged.connect(self._changed)
        row.addStretch(1)
        lay.addLayout(row)
        self.hint = label("", 12, color=T.text3)
        lay.addWidget(self.hint)
        self._changed()

    def value(self):
        y, m, d = self.y.value(), self.m.value(), self.d.value()
        if self.jalali:
            for dd in range(d, 0, -1):
                try:
                    g = self._i18n.from_jalali(y, m, dd)
                    if self._i18n.to_jalali(self._dt(*g)) == (y, m, dd):
                        return self._date(*g)
                except ValueError:
                    continue
            return self._date.today()
        import calendar
        return self._date(y, m, min(d, calendar.monthrange(y, m)[1]))

    def _changed(self, _v=None):
        v = self.value()
        self.hint.setText(self._i18n.fmt_when(self._dt(v.year, v.month, v.day), with_time=False))
        self.changed.emit()
