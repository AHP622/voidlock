"""The 'Export study report' dialog (for an advisor or parents): period, language, format -> HTML / PDF / CSV file."""
from datetime import date
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from . import i18n, report
from .theme import T
from .widgets import ChipGrid, DateField, Segmented, Toggle, label

PERIODS = ["day", "week", "month", "year", "all", "custom"]
PERIOD_NAMES = ["Day", "Week", "Month", "Year", "All time", "Custom"]
FORMATS = ["html", "pdf", "csv"]
FORMAT_NAMES = ["HTML (web page)", "PDF", "CSV (Excel)"]


class ReportForm(QWidget):
    changed = Signal()

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        st = ctx.store.settings
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        self.name = QLineEdit(st.get("report_name", ""))
        self.name.setPlaceholderText("Student name (shown on the report)")
        self.name.setMaxLength(40)
        lay.addWidget(self.name)
        lay.addWidget(label("PERIOD", 10, QFont.Weight.Bold, T.text3, spacing=2))
        self.period = ChipGrid(PERIOD_NAMES, 2, per_row=3)
        lay.addWidget(self.period)
        self.anchor_l = label("A day inside the period", 12, color=T.text2)
        self.anchor = DateField(date.today())
        self.from_l = label("From", 12, color=T.text2)
        self.d_from = DateField(date.today().replace(day=1))
        self.to_l = label("To", 12, color=T.text2)
        self.d_to = DateField(date.today())
        for w in (self.anchor_l, self.anchor, self.from_l, self.d_from, self.to_l, self.d_to):
            lay.addWidget(w)
        self.range_l = label("", 13, QFont.Weight.DemiBold, T.cyan, wrap=True)
        lay.addWidget(self.range_l)
        row = QHBoxLayout()
        row.addWidget(label("Report language", 13), 1)
        self.lang = Segmented(["فارسی", "English"], 0 if i18n.is_fa() else 1)
        row.addWidget(self.lang)
        lay.addLayout(row)
        lay.addWidget(label("FORMAT", 10, QFont.Weight.Bold, T.text3, spacing=2))
        self.fmt = ChipGrid(FORMAT_NAMES, 0, per_row=3)
        lay.addWidget(self.fmt)
        for attr, text in (("inc_exams", "Include exam results and progress"), ("inc_sched", "Include the weekly timetable (classes and study)")):
            r = QHBoxLayout()
            r.addWidget(label(text, 13), 1)
            tg = Toggle(True)
            r.addWidget(tg)
            lay.addLayout(r)
            setattr(self, attr, tg)
        self.period.currentChanged.connect(self._sync)
        self.lang.currentChanged.connect(self._sync)
        for w in (self.anchor, self.d_from, self.d_to):
            w.changed.connect(self._sync)
        self._sync()

    def kind(self):
        return PERIODS[self.period.current()]

    def report_lang(self):
        return "fa" if self.lang.current() == 0 else "en"

    def range(self):
        k = self.kind()
        ctx = self.ctx
        first = report.first_recorded_day(ctx.study, ctx.store) if k == "all" else None
        return report.period_range(k, self.anchor.value(), ctx.store.settings.get("week_start", 5), self.report_lang(),
                                   first=first, custom=(self.d_from.value(), self.d_to.value()))

    def _sync(self, *_):
        k = self.kind()
        single = k in ("day", "week", "month", "year")
        for w in (self.anchor_l, self.anchor):
            w.setVisible(single)
        for w in (self.from_l, self.d_from, self.to_l, self.d_to):
            w.setVisible(k == "custom")
        a, b = self.range()
        lang = self.report_lang()
        text = report.fmt_date(a, lang, weekday=(a == b)) if a == b else f"{report.fmt_date(a, lang)}  -  {report.fmt_date(b, lang)}"
        self.range_l.setText(text)
        self.changed.emit()

    def valid(self):
        return True

    def values(self):
        a, b = self.range()
        return {"name": self.name.text().strip(), "lang": self.report_lang(), "start": a, "end": b, "fmt": FORMATS[self.fmt.current()],
                "kind": self.kind(), "exams": self.inc_exams.isChecked(), "schedule": self.inc_sched.isChecked()}


def build_report(ctx, v):
    """The report data for the chosen values (also used by tests)."""
    return report.collect(ctx.store, ctx.study, v["start"], v["end"], v["name"], v["lang"],
                          goal_min=int(ctx.store.settings.get("daily_goal_min", 120)),
                          include_schedule=v.get("schedule", True), include_exams=v.get("exams", True))


def write_report(R, fmt, path):
    if fmt == "html":
        report.write_text(path, report.render_html(R))
    elif fmt == "csv":
        report.write_text(path, report.render_csv(R), bom=True)          # BOM: Excel opens the Persian text correctly
    elif fmt == "pdf":
        from .report_pdf import write_pdf
        write_pdf(R, str(path))
    else:
        raise ValueError(fmt)


def default_path(v):
    docs = Path.home() / "Documents"
    base = docs if docs.exists() else Path.home()
    a, b = v["start"], v["end"]
    span = a.isoformat() if a == b else f"{a.isoformat()}_{b.isoformat()}"
    return base / f"VoidLock-report-{span}.{v['fmt']}"


def export_report(ctx):
    form = ReportForm(ctx)
    m = ctx.new_modal().build("Export study report",
                              "For your advisor or parents: study time, time per subject, charts, exam results and progress, the weekly timetable and the focus sessions.",
                              form, "Choose file…", icon="download", width=540, validator=form.valid)
    form.changed.connect(m.revalidate)
    if not m.exec_modal():
        return None
    v = form.values()
    ctx.store.settings["report_name"] = v["name"]
    ctx.store.save_settings()
    filt = {"html": "Web page (*.html)", "pdf": "PDF (*.pdf)", "csv": "CSV (*.csv)"}[v["fmt"]]
    path, _ = QFileDialog.getSaveFileName(ctx, i18n.tr("Save report"), str(default_path(v)), filt)
    if not path:
        return None
    try:
        R = build_report(ctx, v)
        write_report(R, v["fmt"], path)
    except Exception as e:                          # a full disk, a file open in another program...
        ctx.toast(i18n.tr(f"Could not save the report: {e}"), "error")
        return None
    ctx.toast("Report saved.", "success")
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    return path
