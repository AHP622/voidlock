"""Draws a charts.Scene with QPainter (PDF pages, and the live charts inside the app)."""
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QToolTip, QWidget

FAMILIES = ["Vazirmatn", "Segoe UI", "Tahoma", "Noto Sans Arabic", "DejaVu Sans", "Arial"]


def _qcolor(c):
    c = str(c)
    if c.startswith("#") and len(c) == 9:                  # #RRGGBBAA (CSS order)
        q = QColor("#" + c[1:7])
        q.setAlpha(int(c[7:9], 16))
        return q
    return QColor(c)


def _font(size, bold=False):
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPixelSize(int(round(size)))
    f.setBold(bold)
    return f


def paint_scene(p, sc, x=0.0, y=0.0, scale=1.0):
    """Draw the scene with its top-left corner at (x, y), scaled."""
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    for it in sc.items:
        k = it[0]
        if k == "rect":
            _, rx, ry, rw, rh, fill, rad, _title, stroke = it
            p.setPen(QPen(_qcolor(stroke), 1) if stroke else Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_qcolor(fill)))
            if rw > 0 and rh > 0:
                if rad:
                    p.drawRoundedRect(QRectF(rx, ry, rw, rh), rad, rad)
                else:
                    p.drawRect(QRectF(rx, ry, rw, rh))
        elif k == "line":
            _, x1, y1, x2, y2, stroke, width, dash = it
            pen = QPen(_qcolor(stroke), width)
            if dash:
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern([float(v) / max(width, 1.0) for v in str(dash).split()])
            p.setPen(pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        elif k == "poly":
            _, pts, stroke, width, dash = it
            pen = QPen(_qcolor(stroke), width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            if dash:
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern([float(v) / max(width, 1.0) for v in str(dash).split()])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(QPointF(*pts[0]))
            for q in pts[1:]:
                path.lineTo(QPointF(*q))
            p.drawPath(path)
        elif k == "polygon":
            _, pts, fill, _title = it
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_qcolor(fill)))
            p.drawPolygon(QPolygonF([QPointF(*q) for q in pts]))
        elif k == "circle":
            _, cx, cy, r, fill, stroke, _title = it
            p.setPen(QPen(_qcolor(stroke), 1.6) if stroke else Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_qcolor(fill)))
            p.drawEllipse(QPointF(cx, cy), r, r)
        elif k == "text":
            _, tx, ty, s, size, fill, anchor, bold = it
            p.setFont(_font(size, bold))
            p.setPen(_qcolor(fill))
            fm = p.fontMetrics()
            wd = fm.horizontalAdvance(s) + 4
            left = tx - wd / 2 if anchor == "middle" else (tx - wd if anchor == "end" else tx)
            p.drawText(QRectF(left, ty - fm.ascent(), wd + 2, fm.height() + 2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, s)
    p.restore()


def scene_image(sc, scale=2.0):
    """A QImage of the scene (device pixel ratio set, so it lays out at its logical size)."""
    img = QImage(int(sc.w * scale), int(max(sc.h, 1) * scale), QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(scale)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    paint_scene(p, sc)
    p.end()
    return img


class ChartView(QWidget):
    """A live chart: `builder(width) -> Scene` is called again whenever the width changes. Hover shows the tooltips."""

    def __init__(self, builder=None, min_h=200):
        super().__init__()
        self._builder, self._sc, self._w = builder, None, -1
        self.setMouseTracking(True)
        self.setMinimumHeight(min_h)
        self._pending = False

    def set_builder(self, builder):
        self._builder, self._w = builder, -1
        self._relayout()

    def _relayout(self):
        if not self._builder or self.width() < 50:
            return
        self._sc = self._builder(self.width())
        self._w = self.width()
        h = int(max(self._sc.h, 60))
        if self.minimumHeight() != h:
            self.setMinimumHeight(h)
        self.update()

    def resizeEvent(self, e):
        if self.width() != self._w and not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._do)

    def _do(self):
        self._pending = False
        self._relayout()

    def paintEvent(self, e):
        if self._sc is None and self._builder:
            self._relayout()
        if self._sc is None:
            return
        p = QPainter(self)
        paint_scene(p, self._sc)
        p.end()

    def mouseMoveEvent(self, e):
        if not self._sc:
            return
        pos = e.position()
        tip = None
        for it in self._sc.items:
            if it[0] == "circle" and it[6] and (it[1] - pos.x()) ** 2 + (it[2] - pos.y()) ** 2 <= (it[3] + 7) ** 2:
                tip = it[6]
                break
            if it[0] == "rect" and it[7] and it[1] <= pos.x() <= it[1] + it[3] and it[2] <= pos.y() <= it[2] + it[4]:
                tip = it[7]
            if it[0] == "polygon" and it[3]:
                xs, ys = [q[0] for q in it[1]], [q[1] for q in it[1]]
                if min(xs) <= pos.x() <= max(xs) and min(ys) <= pos.y() <= max(ys):
                    tip = it[3]
                    break
        if tip:
            QToolTip.showText(e.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()
