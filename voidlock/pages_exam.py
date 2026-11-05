"""The Exams tab: exam days, the results you got (percent and taraz per subject, total taraz, rank) and your progress."""
from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget

from . import charts, i18n, report, study as studymod
from .charts_qt import ChartView
from .pages_a import Page
from .pages_b import StatCard
from .pages_c import ColorPicker
from .theme import T
from .viz import EmptyState, IconTile
from .widgets import AC, Button, Card, DateField, Divider, Pill, Segmented, clear_layout, label, set_label_color

KINDS = ["taraz", "rank", "region", "subjects", "percent"]
KIND_NAMES = ["Total taraz", "Overall rank", "Region rank", "Taraz by subject", "Percent by subject"]


def dark_palette():
    pal = dict(charts.LIGHT)
    pal.update(text=T.text2, muted=T.text3, grid=T.border, axis=T.border_hi, goal=T.violet, avg=T.cyan, ma=T.violet, accent=T.cyan,
               accent2=T.violet, area=T.cyan + "22", line1=T.cyan, line2="#60A5FA", exam=T.amber)
    return pal


def _lang():
    return "fa" if i18n.is_fa() else "en"


class ExamForm(QWidget):
    """Name + day of one exam."""
    changed = Signal()

    def __init__(self, exam=None):
        super().__init__()
        exam = exam or {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        self.name = QLineEdit(exam.get("name", ""))
        self.name.setPlaceholderText("Exam name, e.g. Mock exam 3")
        self.name.setMaxLength(40)
        lay.addWidget(self.name)
        d = date.fromisoformat(exam["date"]) if exam.get("date") else date.today()
        self.date = DateField(d)
        lay.addWidget(self.date)
        self.name.textChanged.connect(lambda _t: self.changed.emit())

    def valid(self):
        return bool(self.name.text().strip())

    def values(self):
        return {"name": self.name.text().strip(), "date": self.date.value()}


class ExamSubjectForm(QWidget):
    """Add / edit one subject of the exam form: a name and a colour."""
    changed = Signal()

    def __init__(self, s=None, taken=(), hints=None):
        """`taken`: names of the OTHER exam subjects (a name can be used once). `hints`: {name: colour} of the study-timer
        subjects: typing the name of one of them proposes its colour, so one lesson has one colour everywhere."""
        super().__init__()
        s = s or {}
        self.taken = {str(n).strip().casefold() for n in taken}
        self.hints, self._touched = hints or {}, bool(s)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)
        self.name = QLineEdit(s.get("name", ""))
        self.name.setPlaceholderText("Subject name, e.g. Calculus")
        self.name.setMaxLength(24)
        lay.addWidget(self.name)
        self.cp = ColorPicker()
        if s.get("color"):
            self.cp.set_color(s["color"])
        else:
            self.cp.set_color(self.cp.colors[len(self.taken) % len(self.cp.colors)])
        lay.addWidget(self.cp)
        self.cp.picked.connect(self._on_picked)
        self.name.textChanged.connect(self._on_name)

    def _on_picked(self):
        self._touched = True

    def _on_name(self, t):
        c = self.hints.get(t.strip().casefold())
        if c and not self._touched:
            self.cp.set_color(c)
        self.changed.emit()

    def valid(self):
        t = self.name.text().strip().casefold()
        return bool(t) and t not in self.taken

    def values(self):
        return {"name": self.name.text().strip(), "color": self.cp.color()}


class ExamResultForm(QWidget):
    """Total taraz, overall rank, rank in the region, and percent + taraz for each subject of the exam. The subjects are the
    student's own exam subjects (added here or on the Exams tab), not the study-timer subjects. Persian digits are fine;
    empty = not known."""
    changed = Signal()

    def __init__(self, sl, exam):
        super().__init__()
        self.sl, self.exam = sl, exam
        old = exam.get("result") or {}
        self._old_rows = {self.sl.subject_key(r): r for r in old.get("subjects", [])}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)
        top = QGridLayout()
        top.setHorizontalSpacing(10)
        self.total = self._edit(old.get("taraz"), "Total taraz")
        self.rank = self._edit(old.get("rank"), "Overall rank")
        self.region = self._edit(old.get("rank_region"), "Region rank")
        for c, (txt, w) in enumerate((("Total taraz", self.total), ("Overall rank", self.rank), ("Region rank", self.region))):
            top.addWidget(label(txt, 12, color=T.text2), 0, c)
            top.addWidget(w, 1, c)
        lay.addLayout(top)
        lay.addWidget(Divider())
        head = QGridLayout()
        head.setHorizontalSpacing(10)
        head.addWidget(label("Subject", 11, QFont.Weight.Bold, T.text3), 0, 0)
        head.addWidget(label("Percent", 11, QFont.Weight.Bold, T.text3, align=AC), 0, 1)
        head.addWidget(label("Taraz", 11, QFont.Weight.Bold, T.text3, align=AC), 0, 2)
        head.setColumnStretch(0, 1)
        lay.addLayout(head)
        inner = QWidget()
        self.grid = QGridLayout(inner)
        self.grid.setContentsMargins(0, 0, 6, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(6)
        self.grid.setColumnStretch(0, 1)
        self.rows = []
        self.empty_hint = label("No subjects yet. Type the name of a subject below and press Add.", 12, color=T.text3, wrap=True)
        self.grid.addWidget(self.empty_hint, 0, 0, 1, 3)
        for s in self.sl.exam_subjects():
            self._add_row(s, emit=False)
        self._extra = [r for r in old.get("subjects", []) if not self.sl.exam_subject(r.get("sid"))]      # of deleted subjects: kept as they are
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidget(inner)
        self.scroll.setFixedHeight(232)               # fixed: adding a subject below never resizes the open dialog, the list scrolls
        lay.addWidget(self.scroll)
        # add a subject right here
        add = QHBoxLayout()
        add.setSpacing(8)
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("New subject, e.g. Calculus")
        self.new_name.setMaxLength(24)
        self.b_new = Button("Add subject", "soft", "plus", height=38)
        add.addWidget(self.new_name, 1)
        add.addWidget(self.b_new)
        lay.addLayout(add)
        self.new_name.returnPressed.connect(self.add_subject)
        self.b_new.clicked.connect(lambda _=False: self.add_subject())
        self.note = QLineEdit(old.get("note", ""))
        self.note.setPlaceholderText("Note (optional)")
        self.note.setMaxLength(120)
        lay.addWidget(self.note)
        self.err = label("", 12, color=T.red)
        lay.addWidget(self.err)
        self.b_clear = Button("Remove this result", "danger", "trash", height=34)
        lay.addWidget(self.b_clear)
        self.b_clear.setVisible(bool(exam.get("result")))
        self.cleared = False
        for e in (self.total, self.rank, self.region, self.note):
            e.textChanged.connect(lambda _t: self.changed.emit())
        self._fit()

    def _fit(self):
        n = len(self.rows)
        self.empty_hint.setVisible(n == 0)

    def _add_row(self, s, emit=True):
        i = len(self.rows)
        r = self._old_rows.get(self.sl.subject_key({"sid": s["id"], "name": s["name"]}), {})
        pct = self._edit(r.get("pct"), "%")
        tz = self._edit(r.get("taraz"), "Taraz")
        nm = QHBoxLayout()
        nm.setSpacing(8)
        nm.addWidget(IconTile(s["name"], s["color"], 24))
        nl = label(s["name"], 13)
        nl.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
        nm.addWidget(nl, 1)
        w = QWidget()
        w.setLayout(nm)
        self.grid.addWidget(w, i + 1, 0)
        self.grid.addWidget(pct, i + 1, 1)
        self.grid.addWidget(tz, i + 1, 2)
        self.rows.append((s, pct, tz))
        pct.textChanged.connect(lambda _t: self.changed.emit())
        tz.textChanged.connect(lambda _t: self.changed.emit())
        return pct

    def add_subject(self):
        name = self.new_name.text().strip()
        if not name:
            return
        known = {x["id"] for x in self.sl.exam_subjects()}
        s = self.sl.add_exam_subject(name)
        if s and s["id"] not in known:
            first = self._add_row(s)
            self._fit()
            first.setFocus()
        self.new_name.clear()

    @staticmethod
    def _edit(value, placeholder):
        e = QLineEdit("" if value is None else (f"{value:g}" if isinstance(value, float) else str(value)))
        e.setPlaceholderText(i18n.tr(placeholder))
        e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e.setMinimumWidth(90)
        return e

    def _num(self, edit, lo, hi, integer=False):
        txt = edit.text().strip()
        if not txt:
            return None, True
        v = studymod.parse_number(txt)
        if v is None or v < lo or v > hi:
            return None, False
        return (int(round(v)) if integer else v), True

    def parsed(self):
        """(values, error). Anything left empty is simply unknown."""
        ok_all = True
        total, ok = self._num(self.total, 0, studymod.StudyLog.TARAZ_MAX, True)
        ok_all &= ok
        rank, ok = self._num(self.rank, 1, studymod.StudyLog.RANK_MAX, True)
        ok_all &= ok
        region, ok = self._num(self.region, 1, studymod.StudyLog.RANK_MAX, True)
        ok_all &= ok
        rows = []
        for s, pe, te in self.rows:
            pct, ok1 = self._num(pe, *studymod.StudyLog.PCT_RANGE)
            tz, ok2 = self._num(te, 0, studymod.StudyLog.TARAZ_MAX, True)
            ok_all &= ok1 and ok2
            if pct is not None or tz is not None:
                rows.append({"sid": s["id"], "pct": pct, "taraz": tz})
        rows += [{"sid": r.get("sid", ""), "name": r.get("name", ""), "color": r.get("color", ""), "pct": r.get("pct"), "taraz": r.get("taraz")}
                 for r in self._extra]
        return {"taraz": total, "rank": rank, "rank_region": region, "subjects": rows, "note": self.note.text().strip()}, ok_all

    def valid(self):
        _v, ok = self.parsed()
        self.err.setText("" if ok else i18n.tr("Check the numbers: percent from -33 to 100, taraz up to 20000, rank 1 or more."))
        return ok

    def values(self):
        return self.parsed()[0]


class ExamCard(Card):
    def __init__(self, page, e):
        super().__init__(pad=14, hover=True)
        self.lay.setSpacing(6)
        sl = page.ctx.study
        d = date.fromisoformat(e["date"])
        left = (d - date.today()).days
        row = QHBoxLayout()
        row.setSpacing(10)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(e["name"], 14, QFont.Weight.DemiBold))
        when = ("Today" if left == 0 else "Tomorrow" if left == 1 else f"in {left} days" if left > 1 else f"{-left} days ago")
        col.addWidget(label(f"{i18n.fmt_when(datetime(d.year, d.month, d.day), with_time=False)} · {i18n.tr(when)}", 12,
                            color=T.amber if 0 <= left <= 3 else T.text3))
        row.addLayout(col, 1)
        r = e.get("result")
        if r:
            fa = i18n.is_fa()
            if r.get("taraz") is not None:
                row.addWidget(Pill(f"{i18n.tr('Taraz')} {charts.fmt_int(r['taraz'], fa)}", T.cyan, px=11))
            if r.get("rank") is not None:
                row.addWidget(Pill(f"{i18n.tr('Rank')} {charts.fmt_int(r['rank'], fa)}", T.violet, px=11))
            if r.get("rank_region") is not None:
                row.addWidget(Pill(f"{i18n.tr('Region')} {charts.fmt_int(r['rank_region'], fa)}", T.green, px=11))
        b_res = Button("Edit results" if r else "Enter results", "soft" if r else "primary", "check", height=34)
        b_res.clicked.connect(lambda _=False: page.enter_results(e))
        b_ed = Button("", "icon", "edit", "Edit exam", square=32)
        b_ed.clicked.connect(lambda _=False: page.edit_exam(e))
        b_del = Button("", "icon", "trash", "Delete", square=32)
        b_del.clicked.connect(lambda _=False: page.delete_exam(e))
        for w in (b_res, b_ed, b_del):
            row.addWidget(w)
        self.lay.addLayout(row)
        if r and r.get("note"):
            self.lay.addWidget(label(r["note"], 12, color=T.text3))


class ExamsPage(Page):
    def __init__(self, ctx):
        super().__init__(ctx, "Exams", "Your exams, results and progress")
        self.kind = 0
        top = QHBoxLayout()
        top.setSpacing(10)
        self.next_l = label("", 13, color=T.text2, wrap=True)
        top.addWidget(self.next_l, 1)
        self.b_add = Button("Add exam", "primary", "plus", height=42)
        top.addWidget(self.b_add)
        self.body.addLayout(top)
        self.kpis = QHBoxLayout()
        self.kpis.setSpacing(12)
        self.k_next = StatCard("schedule", T.amber, "Days to the next exam")
        self.k_taraz = StatCard("analytics", T.cyan, "Latest total taraz")
        self.k_best = StatCard("flame", T.violet, "Best total taraz")
        self.k_rank = StatCard("star", T.green, "Latest overall rank")
        self.k_region = StatCard("star", T.violet, "Latest region rank")
        self.k_count = StatCard("check", T.text2, "Exams with results")
        for k in (self.k_next, self.k_taraz, self.k_best, self.k_rank, self.k_region, self.k_count):
            self.kpis.addWidget(k, 1)
        self.body.addLayout(self.kpis)
        # progress chart
        self.chart_card = Card(pad=20, accent=T.cyan)
        hr = QHBoxLayout()
        hr.addWidget(label("PROGRESS", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.kind_seg = Segmented(KIND_NAMES, 0)
        hr.addWidget(self.kind_seg)
        self.chart_card.lay.addLayout(hr)
        self.chart = ChartView(None, 260)
        self.chart_card.lay.addWidget(self.chart)
        self.insight = label("", 13, color=T.text2, wrap=True)
        self.chart_card.lay.addWidget(self.insight)
        self.body.addWidget(self.chart_card)
        self.empty = EmptyState("check", "No exam results yet", "Add an exam, then enter its results: percent and taraz of every subject, "
                                "your total taraz and your rank. The progress charts appear here.", "Add exam")
        self.body.addWidget(self.empty)
        # latest exam by subject
        self.last_card = Card(pad=20)
        self.last_title = label("", 11, QFont.Weight.Bold, T.text3, spacing=2.4)
        self.last_card.lay.addWidget(self.last_title)
        self.last_grid = QGridLayout()
        self.last_grid.setHorizontalSpacing(14)
        self.last_grid.setVerticalSpacing(8)
        self.last_card.lay.addLayout(self.last_grid)
        self.body.addWidget(self.last_card)
        # the subjects of the exam form
        self.subj_card = Card(pad=20)
        sh = QHBoxLayout()
        sh.addWidget(label("EXAM SUBJECTS", 11, QFont.Weight.Bold, T.text3, spacing=2.4), 1)
        self.b_subj = Button("Add subject", "soft", "plus", height=34)
        sh.addWidget(self.b_subj)
        self.subj_card.lay.addLayout(sh)
        self.subj_hint = label("These are the subjects you enter results for. They are separate from the Study Timer subjects.", 12, color=T.text3, wrap=True)
        self.subj_card.lay.addWidget(self.subj_hint)
        self.subj_box = QVBoxLayout()
        self.subj_box.setSpacing(6)
        self.subj_card.lay.addLayout(self.subj_box)
        self.body.addWidget(self.subj_card)
        # list
        self.list_card = Card(pad=20)
        self.list_card.lay.addWidget(label("ALL EXAMS", 11, QFont.Weight.Bold, T.text3, spacing=2.4))
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(8)
        self.list_card.lay.addLayout(self.list_box)
        self.body.addWidget(self.list_card)
        self.body.addStretch(1)
        self.b_add.clicked.connect(self.add_exam)
        self.b_subj.clicked.connect(lambda _=False: self.add_subject())
        self.empty.action.connect(self.add_exam)
        self.kind_seg.currentChanged.connect(self._kind)
        self._reveal = [self.chart_card, self.last_card, self.subj_card, self.list_card]

    def _kind(self, i):
        self.kind = i
        self._draw_chart()

    # ---- drawing
    def _res(self):
        return report.results_data(self.ctx.study, None, _lang())

    def _draw_chart(self):
        res = self._res()
        kind, pal, lang = KINDS[self.kind], dark_palette(), _lang()
        self.chart.set_builder(lambda w: report.exam_chart(res, kind, lang, pal, max(300, w), 270))

    def refresh(self):
        sl = self.ctx.study
        lang, fa = _lang(), i18n.is_fa()
        fi = lambda n: charts.fmt_int(n, fa)
        res = self._res()
        today = date.today()
        ex, dleft = sl.next_exam(today)
        if ex:
            self.next_l.setText(f"Next exam: {ex['name']} · " + i18n.tr("Today" if dleft == 0 else "Tomorrow" if dleft == 1 else f"in {dleft} days"))
        else:
            self.next_l.setText("No exam added yet")
        self.k_next.set(i18n.digits(str(dleft)) if ex else "-", ex["name"] if ex else "")
        has = bool(res)
        for c in (self.chart_card, self.last_card):
            c.setVisible(has)
        self.empty.setVisible(not has)

        def delta(w, v, better_up=True):
            if v in (None, 0):
                w.setText("")
                return
            good = (v > 0) == better_up
            w.setText(("▲ " if v > 0 else "▼ ") + fi(abs(v)))
            set_label_color(w, T.green if good else T.red)
        if res:
            lt, best, lr = res["latest"], res["best_taraz"], res["latest"]
            self.k_taraz.set(fi(lt["taraz"]) if lt["taraz"] is not None else "-")
            delta(self.k_taraz.sub, lt["delta"])
            self.k_best.set(fi(best["taraz"]) if best else "-", best["short"] if best else "")
            self.k_rank.set(fi(lr["rank"]) if lr["rank"] is not None else "-")
            delta(self.k_rank.sub, lr["delta_rank"])
            self.k_region.set(fi(lr["rank_region"]) if lr.get("rank_region") is not None else "-")
            delta(self.k_region.sub, lr.get("delta_region"))
            self.k_count.set(i18n.digits(str(res["count"])))
            ftl = res["first_to_last"]
            if ftl is not None:
                self.insight.setText(f"Taraz change from the first to the latest exam: {'+' if ftl > 0 else ''}{fi(ftl) if ftl >= 0 else '-' + fi(-ftl)}")
            else:
                self.insight.setText("")
            self._draw_chart()
            self._fill_last(res)
        else:
            for k in (self.k_taraz, self.k_best, self.k_rank, self.k_region, self.k_count):
                k.set("-")
                k.sub.setText("")
        self._fill_subjects()
        self._fill_list()

    def _fill_subjects(self):
        clear_layout(self.subj_box)
        subs = self.ctx.study.exam_subjects()
        if not subs:
            self.subj_box.addWidget(label("No subjects yet. Add the subjects of your exam, then enter the results.", 12, color=T.text2))
        for s in subs:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(IconTile(s["name"], s["color"], 24))
            nl = label(s["name"], 13)
            nl.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(nl, 1)
            b_ed = Button("", "icon", "edit", "Edit subject", square=30)
            b_ed.clicked.connect(lambda _=False, s=s: self.edit_subject(s))
            b_del = Button("", "icon", "trash", "Delete", square=30)
            b_del.clicked.connect(lambda _=False, s=s: self.delete_subject(s))
            row.addWidget(b_ed)
            row.addWidget(b_del)
            w = QWidget()
            w.setLayout(row)
            self.subj_box.addWidget(w)

    def _fill_last(self, res):
        clear_layout(self.last_grid)
        lt = res["latest"]
        self.last_title.setText(f"{i18n.tr('LATEST EXAM')} · {lt['name']}")
        fa = i18n.is_fa()
        heads = ("Subject", "Percent", "Taraz", "Change")
        for c, h in enumerate(heads):
            self.last_grid.addWidget(label(h, 11, QFont.Weight.Bold, T.text3, align=None if c == 0 else AC), 0, c)
        n = len(res["exams"]) - 1
        r = 1
        for s in res["subjects"]:
            pt = next((p for p in s["points"] if p[0] == n), None)
            if not pt:
                continue
            nm = QHBoxLayout()
            nm.setSpacing(8)
            nm.addWidget(IconTile(s["name"], s["color"], 24))
            nl = label(s["name"], 13)
            nl.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
            nm.addWidget(nl, 1)
            w = QWidget()
            w.setLayout(nm)
            self.last_grid.addWidget(w, r, 0)
            pct = f"{charts.digits(f'{pt[1]:.1f}', fa)}{'٪' if fa else '%'}" if pt[1] is not None else "-"
            self.last_grid.addWidget(label(pct, 13, align=AC), r, 1)
            self.last_grid.addWidget(label(charts.fmt_int(pt[2], fa) if pt[2] is not None else "-", 13, QFont.Weight.DemiBold, align=AC), r, 2)
            d = label("", 12, align=AC)
            if s["delta"]:
                d.setText(("▲ " if s["delta"] > 0 else "▼ ") + charts.fmt_int(abs(s["delta"]), fa))
                set_label_color(d, T.green if s["delta"] > 0 else T.red)
            self.last_grid.addWidget(d, r, 3)
            r += 1
        self.last_grid.setColumnStretch(0, 1)

    def _fill_list(self):
        clear_layout(self.list_box)
        sl = self.ctx.study
        exams = sl.exams()                                   # oldest first: one plain timeline, the way the dates run
        if not exams:
            self.list_box.addWidget(label("No exams yet. Add the days of your exams.", 12, color=T.text3))
        for e in exams:
            self.list_box.addWidget(ExamCard(self, e))

    # ---- actions
    def add_exam(self):
        form = ExamForm()
        m = self.ctx.new_modal().build("Add exam", None, form, "Add", validator=form.valid, icon="schedule", width=520)
        form.changed.connect(m.revalidate)
        if m.exec_modal():
            v = form.values()
            self.ctx.study.add_exam(v["name"], v["date"])
            self.refresh()

    def edit_exam(self, e):
        form = ExamForm(e)
        m = self.ctx.new_modal().build("Edit exam", None, form, "Save", validator=form.valid, icon="edit", width=520)
        form.changed.connect(m.revalidate)
        if m.exec_modal():
            v = form.values()
            self.ctx.study.update_exam(e["id"], v["name"], v["date"])
            self.refresh()

    def delete_exam(self, e):
        if self.ctx.confirm("Delete exam?", f"“{e['name']}” and its results will be removed.", "Delete", True, "trash"):
            self.ctx.study.remove_exam(e["id"])
            self.refresh()

    def add_subject(self):
        sl = self.ctx.study
        form = ExamSubjectForm(taken=[x["name"] for x in sl.exam_subjects()],
                               hints={x["name"].strip().casefold(): x["color"] for x in sl.subjects()})
        m = self.ctx.new_modal().build("Add subject", None, form, "Add", validator=form.valid, icon="book", width=460)
        form.changed.connect(m.revalidate)
        if m.exec_modal():
            v = form.values()
            sl.add_exam_subject(v["name"], v["color"])
            self.refresh()

    def edit_subject(self, s):
        sl = self.ctx.study
        form = ExamSubjectForm(s, taken=[x["name"] for x in sl.exam_subjects() if x["id"] != s["id"]])
        m = self.ctx.new_modal().build("Edit subject", "Renaming keeps the results already saved for it.", form, "Save",
                                       validator=form.valid, icon="edit", width=460)
        form.changed.connect(m.revalidate)
        if m.exec_modal():
            v = form.values()
            sl.edit_exam_subject(s["id"], v["name"], v["color"])
            self.refresh()

    def delete_subject(self, s):
        if self.ctx.confirm("Delete subject?", f"“{s['name']}” will be removed from the exam form. Results already saved for it stay "
                            "in your charts and reports.", "Delete", True, "trash"):
            self.ctx.study.remove_exam_subject(s["id"])
            self.refresh()

    def enter_results(self, e):
        form = ExamResultForm(self.ctx.study, e)
        m = self.ctx.new_modal().build(f"{i18n.tr('Results')} · {e['name']}",
                                       "Fill in what you know. Percent and taraz are per subject; leave the rest empty.", form, "Save",
                                       validator=form.valid, icon="check", width=580)
        form.changed.connect(m.revalidate)
        form.b_clear.clicked.connect(lambda: (setattr(form, "cleared", True), m.finish(True)))
        if not m.exec_modal():
            return
        sl = self.ctx.study
        if form.cleared:
            sl.clear_exam_result(e["id"])
            self.ctx.toast("Result removed.", "info")
        else:
            v = form.values()
            saved = sl.set_exam_result(e["id"], v["taraz"], v["rank"], v["subjects"], v["note"], v["rank_region"])
            self.ctx.toast("Results saved." if saved else "Nothing to save.", "success" if saved else "warn")
        self.refresh()
