"""Dialogs must never be squashed: no widget smaller than its minimum, none sticking out of its parent.
(A date row three steppers wide was wider than the dialog and got cut in half.)  Run: python tests/modal_layout_test.py"""
import os, sys, time, shutil, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = os.path.join(tempfile.gettempdir(), "vl_modal"); shutil.rmtree(home, ignore_errors=True)
os.environ["VOIDLOCK_HOME"] = home
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout
from voidlock import i18n
from voidlock.store import Store
st = Store(); st.settings["play_tracking"] = False; st.save_settings()
lang = sys.argv[1] if len(sys.argv) > 1 else "en"
i18n.set_language(lang)
from voidlock.theme import stylesheet, font
app = QApplication(sys.argv[:1]); app.setStyle("Fusion"); app.setStyleSheet(stylesheet()); app.setFont(font(13))
if lang == "fa":
    i18n.install_hooks(); app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
from voidlock.guard import GuardClient
from voidlock.app import MainWindow
from voidlock.overlays import Modal
from voidlock.pages_c import ExamEditor, SubjectForm
from voidlock.pages_b import ScheduleForm, ClassForm
from voidlock.widgets import Stepper

FAILS = []
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)
def pump(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.003)

def problems(root):
    out = []
    for w in root.findChildren(QWidget):
        if not w.isVisibleTo(root) or w.parent() is None:
            continue
        g, mh = w.geometry(), w.minimumSizeHint()
        if isinstance(w, QLabel) and w.wordWrap():
            continue                                  # wrapped labels get their height from their width
        if g.height() + 1 < mh.height() or g.width() + 1 < mh.width():
            out.append(f"{type(w).__name__} squashed {g.width()}x{g.height()} < {mh.width()}x{mh.height()}")
        p = w.parentWidget()
        if p is not None and not isinstance(p, QLabel) and (g.right() > p.width() + 2 or g.bottom() > p.height() + 2):
            out.append(f"{type(w).__name__} sticks out of {type(p).__name__}")
    return out

for W, H in ((900, 640), (1280, 800)):
    win = MainWindow(st, GuardClient(st)); win.resize(W, H); win.show(); pump(400)
    win.study.add_exam("Mock", date.today() + timedelta(days=9))
    cases = {
        "exams": (lambda: ExamEditor(win.study, lambda: None), "Exams", "The next exam is shown on this page, and you get a reminder the day before and on the day.", 520),
        "subject-new": (lambda: SubjectForm(), "Add subject", None, 460),
        "subject-edit": (lambda: SubjectForm(win.study.subjects()[0]), "Edit subject", "Renaming keeps all the hours and tests recorded for it.", 460),
        "session": (lambda: ScheduleForm({"day": 0, "time": "10:00", "minutes": 50, "subject": "", "enabled": True, "id": "x"}, 5, [], []), "New scheduled session", None, 520),
        "class": (lambda: ClassForm({"day": 0, "time": "10:00", "minutes": 50, "name": "A", "remind": 15, "enabled": True, "id": "x"}, 5, [], []), "New class", None, 520),
    }
    for name, (mk, title, msg, width) in cases.items():
        body = mk()
        m = win.new_modal().build(title, msg, body, "OK", "Cancel", width=width)
        m.open(); pump(450)
        bad = problems(m.panel)
        ok(not bad and m.panel.width() >= body.minimumSizeHint().width(), f"[{lang} {W}x{H}] '{name}' dialog is not squashed {bad[:3]}")
        m.finish(False); pump(250)
    win.scanner.stop(); win.guard.stop(); win.close(); pump(100)

# negative control: three full-width steppers in a 464 px column ARE flagged
holder = QWidget(); holder.setFixedWidth(300); lay = QHBoxLayout(holder)
for _ in range(3): lay.addWidget(Stepper(5, 1, 9, 1))
holder.show(); pump(100)
ok(bool(problems(holder)), "the checker does detect a squashed row (control)")
print("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
