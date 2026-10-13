"""Vector icons drawn with QPainter on a 24x24 grid (no external assets)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush

NB = Qt.BrushStyle.NoBrush


def _rr(p, x, y, w, h, r):
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def _ln(p, x1, y1, x2, y2):
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _circ(p, cx, cy, r):
    p.drawEllipse(QPointF(cx, cy), r, r)


def _path(d):
    """Tiny path builder: list of ('M',x,y) ('L',x,y) ('C',x1,y1,x2,y2,x,y) ('Z',)"""
    path = QPainterPath()
    for seg in d:
        k = seg[0]
        if k == "M":
            path.moveTo(seg[1], seg[2])
        elif k == "L":
            path.lineTo(seg[1], seg[2])
        elif k == "C":
            path.cubicTo(*seg[1:7])
        elif k == "Z":
            path.closeSubpath()
    return path


def _fill(p, col):
    p.setBrush(QBrush(col))


def _overview(p, c):
    for x, y in ((4, 4), (13.5, 4), (4, 13.5), (13.5, 13.5)):
        _rr(p, x, y, 6.5, 6.5, 1.8)


def _shield(p, c):
    p.drawPath(_path([("M", 12, 3), ("L", 19.5, 6), ("L", 19.5, 12),
                      ("C", 19.5, 16.5, 16.5, 19.5, 12, 21),
                      ("C", 7.5, 19.5, 4.5, 16.5, 4.5, 12), ("L", 4.5, 6), ("Z",)]))


def _shield_check(p, c):
    _shield(p, c)
    p.drawPolyline([QPointF(8.8, 12), QPointF(11.2, 14.4), QPointF(15.4, 9.6)])


def _timer(p, c):
    _circ(p, 12, 13.5, 7.5)
    _ln(p, 12, 13.5, 12, 9.5)
    _ln(p, 9.5, 3.5, 14.5, 3.5)
    _ln(p, 12, 3.5, 12, 6)


def _calendar(p, c):
    _rr(p, 4, 5.5, 16, 14.5, 3)
    _ln(p, 4, 10.5, 20, 10.5)
    _ln(p, 8.5, 3.5, 8.5, 7.5)
    _ln(p, 15.5, 3.5, 15.5, 7.5)


def _chart(p, c):
    _ln(p, 6, 20, 6, 13)
    _ln(p, 12, 20, 12, 5.5)
    _ln(p, 18, 20, 18, 10)


def _sliders(p, c):
    for y, x in ((7, 9), (12, 15), (17, 8)):
        _ln(p, 4, y, 20, y)
        p.save()
        _fill(p, QColor("#0E121A"))
        _circ(p, x, y, 2.4)
        p.restore()


def _play(p, c):
    _fill(p, c)
    p.drawPath(_path([("M", 8, 5.5), ("L", 18.5, 12), ("L", 8, 18.5), ("Z",)]))


def _pause(p, c):
    _fill(p, c)
    _rr(p, 6.5, 5, 4, 14, 1.4)
    _rr(p, 13.5, 5, 4, 14, 1.4)


def _stop(p, c):
    _fill(p, c)
    _rr(p, 6, 6, 12, 12, 2.4)


def _plus(p, c):
    _ln(p, 12, 5, 12, 19)
    _ln(p, 5, 12, 19, 12)


def _minus(p, c):
    _ln(p, 5, 12, 19, 12)


def _search(p, c):
    _circ(p, 10.8, 10.8, 6)
    _ln(p, 15.3, 15.3, 20, 20)


def _close(p, c):
    _ln(p, 6, 6, 18, 18)
    _ln(p, 18, 6, 6, 18)


def _min(p, c):
    _ln(p, 6, 12, 18, 12)


def _max(p, c):
    _rr(p, 6, 6, 12, 12, 1.5)


def _restore(p, c):
    _rr(p, 5.5, 8.5, 10, 10, 1.5)
    p.drawPolyline([QPointF(8.5, 8.5), QPointF(8.5, 5.5), QPointF(18.5, 5.5),
                    QPointF(18.5, 15.5), QPointF(15.5, 15.5)])


def _lock(p, c):
    _rr(p, 5, 11, 14, 10, 3)
    p.drawPath(_path([("M", 8, 11), ("L", 8, 8), ("C", 8, 2.5, 16, 2.5, 16, 8), ("L", 16, 11)]))
    _circ(p, 12, 16, 1.2)


def _check(p, c):
    p.drawPolyline([QPointF(5, 12.5), QPointF(10, 17.5), QPointF(19, 7)])


def _trash(p, c):
    _ln(p, 4.5, 7, 19.5, 7)
    p.drawPath(_path([("M", 6.5, 7), ("L", 7.5, 19.5), ("L", 16.5, 19.5), ("L", 17.5, 7)]))
    p.drawPath(_path([("M", 9.5, 7), ("L", 9.5, 4.5), ("L", 14.5, 4.5), ("L", 14.5, 7)]))


def _warn(p, c):
    p.drawPath(_path([("M", 12, 4), ("L", 21, 19.5), ("L", 3, 19.5), ("Z",)]))
    _ln(p, 12, 10, 12, 14)
    _ln(p, 12, 16.6, 12, 16.7)


def _flame(p, c):
    p.drawPath(_path([("M", 12, 3), ("C", 13, 7, 18, 9, 18, 14.5), ("C", 18, 18.5, 15.3, 21, 12, 21),
                      ("C", 8.7, 21, 6, 18.5, 6, 14.5), ("C", 6, 12, 7.3, 10.5, 8.6, 9.5),
                      ("C", 9, 11, 9.8, 11.6, 10.5, 11.6), ("C", 10.5, 8, 11, 5.5, 12, 3), ("Z",)]))


def _clock(p, c):
    _circ(p, 12, 12, 8.5)
    p.drawPolyline([QPointF(12, 7), QPointF(12, 12), QPointF(15.5, 14)])


def _bolt(p, c):
    p.drawPath(_path([("M", 13, 3), ("L", 5.5, 13.5), ("L", 11.5, 13.5), ("L", 10.5, 21),
                      ("L", 18.5, 10), ("L", 12.5, 10), ("Z",)]))


def _folder(p, c):
    p.drawPath(_path([("M", 3.5, 7), ("L", 3.5, 18), ("C", 3.5, 19, 4, 19.5, 5, 19.5), ("L", 19, 19.5),
                      ("C", 20, 19.5, 20.5, 19, 20.5, 18), ("L", 20.5, 9.5),
                      ("C", 20.5, 8.5, 20, 8, 19, 8), ("L", 12, 8), ("L", 10, 5.5), ("L", 5, 5.5),
                      ("C", 4, 5.5, 3.5, 6, 3.5, 7), ("Z",)]))


def _edit(p, c):
    p.drawPath(_path([("M", 4.5, 19.5), ("L", 5.2, 15.2), ("L", 15.5, 4.9), ("L", 19.1, 8.5),
                      ("L", 8.8, 18.8), ("Z",)]))


def _refresh(p, c):
    p.drawArc(QRectF(5, 5, 14, 14), 40 * 16, 270 * 16)
    p.drawPolyline([QPointF(17.5, 3.5), QPointF(17.8, 8.2), QPointF(13.2, 8.2)])


def _download(p, c):
    _ln(p, 12, 4, 12, 15)
    p.drawPolyline([QPointF(7.5, 11), QPointF(12, 15.5), QPointF(16.5, 11)])
    _ln(p, 5, 20, 19, 20)


def _info(p, c):
    _circ(p, 12, 12, 8.5)
    _ln(p, 12, 11, 12, 16)
    _ln(p, 12, 7.8, 12, 7.9)


def _eye(p, c):
    p.drawPath(_path([("M", 2.5, 12), ("C", 5, 6.5, 8.5, 5.5, 12, 5.5), ("C", 15.5, 5.5, 19, 6.5, 21.5, 12),
                      ("C", 19, 17.5, 15.5, 18.5, 12, 18.5), ("C", 8.5, 18.5, 5, 17.5, 2.5, 12), ("Z",)]))
    _circ(p, 12, 12, 2.8)


def _terminal(p, c):
    _rr(p, 3.5, 5, 17, 14, 2.5)
    p.drawPolyline([QPointF(7.5, 10), QPointF(10.5, 12.3), QPointF(7.5, 14.6)])
    _ln(p, 12.5, 15, 16.5, 15)


ICONS = {
    "overview": _overview, "apps": _shield, "shield-check": _shield_check, "sessions": _timer,
    "schedule": _calendar, "analytics": _chart, "settings": _sliders, "play": _play,
    "pause": _pause, "stop": _stop, "plus": _plus, "minus": _minus, "search": _search,
    "close": _close, "min": _min, "max": _max, "restore": _restore, "lock": _lock,
    "check": _check, "trash": _trash, "warn": _warn, "flame": _flame, "clock": _clock,
    "bolt": _bolt, "folder": _folder, "edit": _edit, "refresh": _refresh,
    "download": _download, "info": _info, "eye": _eye, "terminal": _terminal,
}


def paint_icon(p: QPainter, name, rect, color, width=1.7):
    fn = ICONS.get(name)
    if fn is None:
        return
    rect = QRectF(rect)
    col = QColor(color)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = min(rect.width(), rect.height()) / 24.0
    p.translate(rect.center().x() - 12 * s, rect.center().y() - 12 * s)
    p.scale(s, s)
    pen = QPen(col, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(NB)
    fn(p, col)
    p.restore()
