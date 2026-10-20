"""In-window modal dialogs and toasts (no OS windows, so they animate and trap focus reliably)."""
from PySide6.QtCore import QEasingCurve, QEventLoop, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget)

from .icons import paint_icon
from .theme import Motion, T, font, qc
from .widgets import AA, AC, Button, label, tween


class Modal(QWidget):
    """Scrim + centred panel. Use Modal.ask(...) (blocking, returns bool) or open()/closed signal."""

    def __init__(self, host: QWidget, background: QWidget = None):
        super().__init__(host)
        self.host, self.background = host, background
        self._k = 0.0
        self.result_ok = False
        self._loop = None
        self._validator = None
        self._cooldown = 0
        self._cool_timer = None
        self.setGeometry(host.rect())
        self.panel = QFrame(self)
        self.panel.setObjectName("mpanel")
        self.panel.setStyleSheet(
            f"QFrame#mpanel{{background:{T.panel2}; border:1px solid {T.border_hi}; border-radius:18px;}}")
        self.panel.setFixedWidth(460)
        self.fx = QGraphicsOpacityEffect(self.panel)
        self.panel.setGraphicsEffect(self.fx)
        self.v = QVBoxLayout(self.panel)
        self.v.setContentsMargins(26, 24, 26, 22)
        self.v.setSpacing(12)
        self.body = None

    def build(self, title, message=None, body=None, confirm="Confirm", cancel="Cancel", danger=False,
              validator=None, cooldown=0, icon=None, icon_color=T.cyan, width=460):
        self.panel.setFixedWidth(width)
        head = QHBoxLayout()
        head.setSpacing(12)
        if icon:
            from .viz import IconTile
            head.addWidget(IconTile(color=T.red if danger else icon_color, size=40, icon=icon))
        head.addWidget(label(title, 18, QFont.Weight.DemiBold), 1)
        self.v.addLayout(head)
        if message:
            self.v.addWidget(label(message, 13, color=T.text2, wrap=True))
        if body is not None:
            self.body = body
            self.v.addWidget(body)
        self.v.addSpacing(6)
        row = QHBoxLayout()
        row.addStretch(1)
        self.b_cancel = Button(cancel, "ghost")
        self.b_ok = Button(confirm, "danger" if danger else "primary")
        self._ok_text = confirm
        self.b_cancel.clicked.connect(lambda: self.finish(False))
        self.b_ok.clicked.connect(lambda: self.finish(True))
        if cancel:
            row.addWidget(self.b_cancel)
        row.addWidget(self.b_ok)
        self.v.addLayout(row)
        self._validator = validator
        self._cooldown = cooldown
        self._refresh_ok()
        if cooldown > 0:
            self._cool_timer = QTimer(self)
            self._cool_timer.timeout.connect(self._cool_tick)
            self._cool_timer.start(1000)
        return self

    def revalidate(self):
        self._refresh_ok()

    def _refresh_ok(self):
        ok = (self._validator() if self._validator else True) and self._cooldown <= 0
        self.b_ok.setEnabled(bool(ok))
        if self._cooldown > 0:
            from . import i18n
            unit = "ثانیه" if i18n.is_fa() else "s"
            self.b_ok.setText(f"{i18n.tr(self._ok_text)} ({i18n.digits(self._cooldown)} {unit})" if i18n.is_fa()
                              else f"{self._ok_text} ({self._cooldown}s)")
        else:
            self.b_ok.setText(self._ok_text)
        self.b_ok.updateGeometry()

    def _cool_tick(self):
        self._cooldown -= 1
        if self._cooldown <= 0 and self._cool_timer:
            self._cool_timer.stop()
        self._refresh_ok()

    # ---- lifecycle
    def open(self):
        self.setGeometry(self.host.rect())
        self.panel.adjustSize()
        self.show()
        self.raise_()
        self._place(0.0)
        if self.background:
            self.background.setEnabled(False)
        tween(self, 0.0, 1.0, 260, self._anim, QEasingCurve.Type.OutCubic)
        first = self.body.findChild(QLineEdit) if self.body else None
        (first or self.b_ok if self.b_ok.isEnabled() else self.b_cancel).setFocus()
        if first:
            first.setFocus()

    def _anim(self, v):
        self._k = float(v)
        self.fx.setOpacity(self._k)
        self._place(self._k)
        self.update()

    def _place(self, k):
        self.panel.adjustSize()
        x = (self.width() - self.panel.width()) // 2
        y = (self.height() - self.panel.height()) // 2 + int((1 - k) * 22)
        self.panel.move(x, max(8, y))

    def resizeEvent(self, e):
        self._place(self._k)

    def finish(self, ok):
        if ok and not self.b_ok.isEnabled():
            return
        if getattr(self, "_closing", False):      # a double click / Esc during the fade-out must not run this twice
            return
        self._closing = True
        self.result_ok = ok
        if self.background:
            self.background.setEnabled(True)

        def done():
            self.hide()
            self.deleteLater()
            if self._loop:
                self._loop.quit()
            self.host.setFocus()

        tween(self, self._k, 0.0, 160, self._anim, QEasingCurve.Type.InCubic, done=done)

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), qc(T.scrim, 0.72 * self._k))

    def mousePressEvent(self, e):
        e.accept()  # scrim swallows clicks

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.finish(False)
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.b_ok.isEnabled():
            self.finish(True)
        else:
            super().keyPressEvent(e)

    def exec_modal(self):
        self.open()
        self._loop = QEventLoop(self)
        self._loop.exec()
        return self.result_ok


def typed_body(prompt, expected, on_change):
    """Body widget with a line edit that must equal `expected`."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 4, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(label(prompt, 12, color=T.text3))
    ed = QLineEdit()
    ed.setPlaceholderText(expected)
    ed.textChanged.connect(lambda _t: on_change())
    lay.addWidget(ed)
    w.edit = ed
    return w


class _Toast(QFrame):
    COLORS = {"info": T.cyan, "success": T.green, "error": T.red, "warn": T.amber}
    ICONS = {"info": "info", "success": "check", "error": "warn", "warn": "warn"}

    def __init__(self, parent, text, kind):
        super().__init__(parent)
        self.kind, self.text_ = kind, text
        col = self.COLORS.get(kind, T.cyan)
        self.setStyleSheet(f"QFrame{{background:{T.raised}; border:1px solid {qc(col, 0.5).name(QColor.NameFormat.HexArgb)};"
                           f"border-radius:12px;}}")
        lay = QHBoxLayout(self)
        from .i18n import is_fa
        lay.setContentsMargins(*((18, 12, 46, 12) if is_fa() else (46, 12, 18, 12)))
        self.lb = label(text, 13, QFont.Weight.Medium, wrap=True)
        self.lb.setMaximumWidth(420)
        if is_fa():
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.lb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        lay.addWidget(self.lb)
        self.adjustSize()
        self._col = col

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(AA)
        ix = self.width() - 34 if self.isRightToLeft() else 14
        paint_icon(p, self.ICONS.get(self.kind, "info"), QRectF(ix, (self.height() - 20) / 2, 20, 20),
                   self._col, 1.9)


class ToastHost(QWidget):
    """Stack of transient notifications in the bottom-right corner."""

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(host.rect())
        self.items = []

    def push(self, text, kind="info", ms=3400):
        t = _Toast(self, text, kind)
        t.adjustSize()
        t.show()
        self.items.append(t)
        self.setGeometry(self.host.rect())
        self.raise_()
        self._layout(animate_new=t)
        QTimer.singleShot(ms, lambda: self._dismiss(t))

    def _dismiss(self, t):
        if t not in self.items:
            return
        self.items.remove(t)
        fx = t.graphicsEffect()
        if not isinstance(fx, QGraphicsOpacityEffect):
            fx = QGraphicsOpacityEffect(t)
            t.setGraphicsEffect(fx)
        tween(t, 1.0, 0.0, 220, fx.setOpacity, done=t.deleteLater)
        self._layout()

    def _layout(self, animate_new=None):
        y = self.height() - 24
        for t in reversed(self.items):
            y -= t.height()
            x = self.width() - t.width() - 26
            target = QPoint(x, y)
            if t is animate_new and not Motion.reduced:
                fx = QGraphicsOpacityEffect(t)
                t.setGraphicsEffect(fx)
                t.move(x + 30, y)
                tween(t, 0.0, 1.0, 300, lambda v, t=t, fx=fx, x=x, y=y: (fx.setOpacity(v), t.move(int(x + 30 * (1 - v)), y)),
                      done=lambda t=t: t.setGraphicsEffect(None))
            else:
                t.move(target)
            y -= 10
