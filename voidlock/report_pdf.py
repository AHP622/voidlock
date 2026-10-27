"""PDF of the study report, drawn with Qt (QTextDocument for the tables, QPainter for the two charts and the page footer)."""
from datetime import datetime

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt, QUrl
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter,
                           QPen, QTextDocument, QTextOption)

from . import i18n, report

DPI = 96
MARGIN_MM = 14
FOOTER_PX = 26
FAMILIES = ["Vazirmatn", "Segoe UI", "Tahoma", "Noto Sans Arabic", "DejaVu Sans", "Arial"]


def _font(pt=10, bold=False):
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPointSizeF(pt)
    f.setBold(bold)
    return f


def _share_image(R, width):
    """One stacked bar: the share of every subject."""
    scale = 2
    h = 18
    img = QImage(int(width * scale), int(h * scale), QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(scale)           # drawn at 2x for sharp edges, laid out at its logical size
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, h), h / 2, h / 2)
    p.setClipPath(path)
    p.fillRect(QRectF(0, 0, width, h), QColor("#e8edf5"))
    total = sum(r["sec"] for r in R["subjects"]) or 1
    x = 0.0
    rtl = R["lang"] == "fa"
    for r in R["subjects"]:
        w = width * r["sec"] / total
        if w <= 0:
            continue
        rect = QRectF(width - x - w, 0, w, h) if rtl else QRectF(x, 0, w, h)
        p.fillRect(rect, QColor(r["color"]))
        p.setPen(QPen(QColor("white"), 1.2))
        p.drawLine(QPointF(rect.left(), 0), QPointF(rect.left(), h))
        x += w
    p.end()
    return img


def _daily_image(R, width, height=190):
    scale = 2
    img = QImage(int(width * scale), int(height * scale), QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(scale)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    lang = R["lang"]
    rtl = lang == "fa"
    mode, series = report.chart_series(R)
    goal = R["goal_sec"] if mode == "day" else 0
    pad_b, pad_t = 22, 8
    mx = max(max((v for _l, v, _e in series), default=0), goal or 0, 1)
    n = max(1, len(series))
    slot = width / n
    bw = max(2.0, min(22.0 if mode == "day" else 50.0, slot * 0.68))
    p.setFont(_font(7.5))
    step = (1 if n <= 14 else (2 if n <= 31 else 7)) if mode == "day" else 1
    for i, (lab, v, exam) in enumerate(series):
        cx = (width - (i + 0.5) * slot) if rtl else (i + 0.5) * slot
        hh = (height - pad_b - pad_t) * v / mx
        color = ("#0e7490" if (goal and v >= goal) else "#7c9cd6") if mode == "day" else "#0e7490"
        if exam:
            color = "#d97706"
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        if hh > 0:
            p.drawRoundedRect(QRectF(cx - bw / 2, height - pad_b - hh, bw, hh), 2, 2)
        if i % step == 0:
            p.setPen(QColor("#64748b"))
            p.drawText(QRectF(cx - max(14, slot / 2), height - pad_b + 4, max(28, slot), 14), Qt.AlignmentFlag.AlignCenter, lab)
    if goal:
        gy = pad_t + (height - pad_b - pad_t) * (1 - goal / mx)
        pen = QPen(QColor("#a855f7"), 1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(0, gy), QPointF(width, gy))
    p.end()
    return img


def write_pdf(R, path):
    """Writes the report to `path`. Returns the number of pages."""
    lang = R["lang"]
    rtl = lang == "fa"
    w = QPdfWriter(path)
    w.setResolution(DPI)
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    w.setPageMargins(QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM), QPageLayout.Unit.Millimeter)
    w.setTitle(report.STR[lang]["title"])
    w.setCreator("VOIDLOCK " + R["version"])
    area = w.pageLayout().paintRectPixels(w.resolution())
    width, height = area.width(), area.height()

    doc = QTextDocument()
    doc.setDefaultFont(_font(10))
    opt = QTextOption()
    opt.setTextDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
    doc.setDefaultTextOption(opt)
    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("chart_share"), _share_image(R, width - 4))
    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("chart_daily"), _daily_image(R, width - 4))
    doc.setHtml(report.render_pdf_html(R))
    body_h = height - FOOTER_PX
    doc.setPageSize(QSizeF(width, body_h))
    pages = max(1, doc.pageCount())

    p = QPainter(w)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    for i in range(pages):
        if i:
            w.newPage()
        p.save()
        p.setClipRect(QRectF(0, 0, width, body_h))
        p.translate(0, -i * body_h)
        doc.drawContents(p, QRectF(0, i * body_h, width, body_h))
        p.restore()
        p.setPen(QColor("#64748b"))
        p.setFont(_font(8))
        label = f"VOIDLOCK · {report.STR[lang]['title']} · " + (report._digits(f"صفحه {i + 1} از {pages}", lang) if rtl else f"Page {i + 1} of {pages}")
        p.drawText(QRectF(0, height - FOOTER_PX + 6, width, FOOTER_PX - 6), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, label)
    p.end()
    return pages
