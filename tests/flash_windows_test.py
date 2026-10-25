"""No stray top-level window may flash while navigating (setVisible(True) on a widget that has no parent opens a tiny
window of its own for a moment). Run: python tests/flash_windows_test.py"""
import os, sys, time, shutil, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = os.path.join(tempfile.gettempdir(), "vl_flash"); shutil.rmtree(home, ignore_errors=True)
os.environ["VOIDLOCK_HOME"] = home
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, datetime, timedelta
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication
from voidlock.theme import stylesheet, font
from voidlock.store import Store
from voidlock.guard import GuardClient
from voidlock.app import MainWindow

app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(stylesheet()); app.setFont(font(13))
st = Store(); st.settings["play_tracking"] = False; st.save_settings()
win = MainWindow(st, GuardClient(st)); win.resize(1280, 900); win.show()
seen = []


class F(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Show and hasattr(obj, "isWindow") and obj.isWindow() and obj is not win:
            seen.append((type(obj).__name__, getattr(obj, "text", lambda: "")() if hasattr(obj, "text") else ""))
        return False


flt = F(); app.installEventFilter(flt)
def pump(ms):
    e = time.time() + ms / 1000
    while time.time() < e: app.processEvents(); time.sleep(0.005)
pump(500)
FAILS = []
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)

sp = win.pages["study"]; win.goto("study"); pump(300)
seen.clear()
for k in range(6):
    sp.goto_day(date.today() - timedelta(days=k + 1)); pump(120)
sp.goto_day(date.today()); pump(120)
ok(not seen, f"moving between days opens no stray window ({seen[:3]})")

# forms for an existing entry / class, custom app rows
from voidlock.pages_b import ScheduleForm, ClassForm
seen.clear()
f = ScheduleForm({"id": "x", "day": 0, "time": "10:00", "minutes": 30, "subject": "", "enabled": True}, 5); pump(100)
g = ClassForm({"id": "y", "day": 0, "time": "10:00", "minutes": 30, "name": "A", "remind": 15, "enabled": True}, 5); pump(100)
ok(not seen, f"building the edit forms opens no stray window ({seen[:3]})")
seen.clear()
st.apps.append({"id": "cu", "name": "Mine", "exe": "mine.exe", "category": "Other", "enabled": False, "custom": True, "path": ""})
st.save_apps(); win.goto("apps"); win.pages["apps"].refresh(); pump(600)
ok(not seen, f"the apps list with a custom app opens no stray window ({seen[:3]})")
from voidlock.pages_c import ExamEditor, SubjectForm
seen.clear()
SubjectForm(); SubjectForm({"id": "x", "name": "A", "color": "#fff"}); ExamEditor(win.study, lambda: None); pump(100)
ok(not seen, f"the subject and exam forms open no stray window ({seen[:3]})")
for key in win.keys:
    seen.clear(); win.goto(key); pump(250)
    ok(not seen, f"opening '{key}' opens no stray window ({seen[:3]})")
win.scanner.stop(); win.guard.stop()
print("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
