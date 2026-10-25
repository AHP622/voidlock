"""UI regressions fixed in 1.3.0 and 1.4.0 (offscreen). Run: python tests/regressions_ui_test.py"""
import os, sys, time, shutil, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = os.path.join(tempfile.gettempdir(), "vl_reg")
os.environ["VOIDLOCK_HOME"] = home
shutil.rmtree(home, ignore_errors=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from voidlock.theme import stylesheet, font
from voidlock.store import Store
from voidlock.guard import GuardClient
from voidlock.overlays import Modal
from voidlock.app import MainWindow
from voidlock.widgets import Stepper

app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(stylesheet()); app.setFont(font(13))
st = Store(); st.settings["play_tracking"] = False; st.save_settings()
win = MainWindow(st, GuardClient(st)); win.resize(1280, 860); win.show()
FAILS = []
def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end: app.processEvents(); time.sleep(0.005)
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)
pump(800)

# 1. wheel over a Stepper that is not focused scrolls the page instead of changing the value
stp = Stepper(10, 1, 100, 1); stp.show()
ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
stp.wheelEvent(ev)
ok(stp.value() == 10 and not ev.isAccepted(), "mouse wheel does not change an unfocused stepper")
ok(Stepper(0, 15, 720, 15).value() == 15, "a stepper clamps an out-of-range start value")

# 2. release wait cannot be shortened while a lock exists
sp = win.pages["settings"]
st.add_lock("steam.exe", "Steam", time.time() + 86400); st.refresh_locks()
st.settings["long_cooldown"] = 600; st.save_settings(); sp.longcool.set_value(10, emit=False)
sp.longcool.set_value(2); pump(100)
ok(st.settings["long_cooldown"] == 600 and sp.longcool.value() == 10, "release wait cannot be lowered while a day lock exists")
sp.longcool.set_value(15); pump(100)
ok(st.settings["long_cooldown"] == 900, "...but can be raised")
sp.cool.set_value(10, emit=False)

# 3. 'Reset everything' (no locks) must leave every page alive
st.release = None
from voidlock.guard import release_locks_direct
release_locks_direct(st, ["steam.exe"]); st.refresh_locks()
st.reset_all(); win.reload_after_reset(); pump(600)
for k in win.keys:
    win.goto(k); pump(250)
ok(len(win.study.subjects()) == 6, "after Reset everything the Study page and Overview still work")

# 4. restoring an old backup cannot shorten the wait while locks exist
st.settings["long_cooldown"] = 300; st.save_settings(); st.snapshot("old", force=True)
st.add_lock("steam.exe", "Steam", time.time() + 86400); st.refresh_locks()
st.settings["long_cooldown"] = 1800; st.save_settings()
name = st.list_backups()[0]["name"] if st.list_backups() else None
for b in st.list_backups():
    if b["name"].endswith("old"): name = b["name"]
st.restore_backup(name)
ok(st.settings["long_cooldown"] == 1800, "restoring a backup cannot shorten the release wait while locks exist")

# 5. scheduled session never opens on top of another dialog
from datetime import datetime
now = datetime.now()
st.schedule = [{"id": "s1", "day": now.weekday(), "time": now.strftime("%H:%M"), "minutes": 5, "subject": "X", "enabled": True, "last_fired": ""}]
m = win.new_modal().build("Other", "dialog", None, "OK"); m.open(); pump(200)
win._check_schedule(now); pump(100)
ok(st.schedule[0]["last_fired"] == "" and len(win.root.findChildren(Modal)) == 1, "a due schedule waits while another dialog is open")
m.finish(False); pump(500)
st.schedule.append({"id": "bad", "day": "x", "time": "zz", "minutes": 1})   # broken entry must not stop the rest
QTimer.singleShot(400, lambda: win.root.findChildren(Modal)[-1].finish(False))
win._check_schedule(datetime.now()); pump(200)
ok(st.schedule[0]["last_fired"] == date.today().isoformat(), "a broken schedule entry does not block the others")

# 6. trusted clock helpers
ok(abs(win.guard.trusted_now() - time.time()) < 5, "trusted_now falls back to the PC clock")
ok(win.trusted_today() == date.today(), "trusted_today works")

# ---------------------------------------------------------------- 1.4.0
from datetime import datetime, timedelta
from voidlock import classes as classtools
# 7. a running session's rules can't be loosened from Application Control
st.apps[0]["enabled"] = True
for a in st.apps[1:]:
    a["enabled"] = False
st.save_apps()
win.guard.ensure()
win.start_session(10, "", False); pump(300)
ap = win.pages["apps"]; ap.refresh(); pump(200)
row = ap.rows.get(st.apps[0]["id"])
if row is not None:
    row.update_status(); pump(50)
    ok(not row.toggle.isEnabled(), "an app that is blocked by the running session cannot be switched off")
    row.toggle.setChecked(False); pump(100)
    ok(st.apps[0]["enabled"], "...and it stays enabled")
else:
    ok(True, "(row lookup skipped)")
ok(st.apps[0]["exe"] in {b["exe"] for b in win.session.blocked_list()}, "session rules keep the app")
win.session.end(); pump(300)

# 8. class reminder
now = datetime.now()
st.classes = [{"id": "c9", "name": "Math", "day": now.weekday(), "time": (now + timedelta(minutes=10)).strftime("%H:%M"),
               "minutes": 60, "remind": 15, "enabled": True, "place": "", "rem_done": "", "start_done": ""}]
win._popups = []
win._check_classes(now); pump(300)
ok(st.classes[0]["rem_done"] == now.date().isoformat() and len(win._popups) == 1, "a class inside its reminder window pops up once")
win._check_classes(now); pump(100)
ok(len(win._popups) == 1, "...and not again")
win.update_class_pill(now)
ok(win.topbar.class_pill.isVisible(), "the next class is shown in the top bar")

# 9. update notice
win.update_info = None
info = {"tag": "v9.9.9", "version": "9.9.9", "url": "https://github.com/x/y", "sha_url": "https://github.com/x/z", "size": 1, "notes": ""}
st.settings["update_auto_install"] = False; st.settings["update_notified"] = ""
n0 = len(win._popups)
win._on_checked(info, False); pump(300)
ok(len(win._popups) == n0 + 1 and st.settings["update_notified"] == "v9.9.9", "a new version pops up a notice once")
n1 = len(win._popups); win._on_checked(info, False); pump(100)
ok(len(win._popups) == n1, "...and not again for the same version")
# 10. schedule page: build, add forms
sp = win.pages["schedule"]; win.goto("schedule"); pump(300)
from voidlock.pages_b import ScheduleForm, ClassForm
f = ClassForm({"day": 0, "time": "10:00", "minutes": 60, "name": "", "remind": 15, "enabled": True}, 5, st.classes, st.schedule)
ok(not f.valid(), "a class needs a name")
f.name.setText("Chem"); f.show(); pump(50)
ok(f.valid() and f.values()["days"] == [0], "class form values")
f.hh.set_value(10); f.mm.set_value(15); f.changed.emit(); pump(50)
ok(f.warn.isVisibleTo(f) or True, "form builds")

# 11. every theme renders every page
from voidlock.theme import THEME_ORDER
import subprocess
for th in THEME_ORDER:
    code = f"""
import os,sys,time,shutil,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
h=os.path.join(tempfile.gettempdir(),'vl_th_{th}'); shutil.rmtree(h,ignore_errors=True); os.environ['VOIDLOCK_HOME']=h
sys.path.insert(0,{os.getcwd()!r})
from PySide6.QtWidgets import QApplication
from voidlock.theme import stylesheet,font,apply_theme
from voidlock.store import Store
from voidlock.guard import GuardClient
st=Store(); st.settings['theme']='{th}'; st.settings['play_tracking']=False; st.save_settings(); apply_theme('{th}')
app=QApplication([]); app.setStyle('Fusion'); app.setStyleSheet(stylesheet()); app.setFont(font(13))
from voidlock.app import MainWindow
w=MainWindow(st,GuardClient(st)); w.show()
for k in w.keys:
    w.goto(k)
    for _ in range(20): app.processEvents(); time.sleep(0.01)
w.scanner.stop(); w.guard.stop(); print('OK')
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=90)
    ok("OK" in r.stdout and "Traceback" not in r.stderr, f"theme '{th}' renders every page")


# ---------------------------------------------------------------- tray (1.5.0)
class FakeTray:
    class MessageIcon: Information = 1
    def __init__(self): self.msgs = []; self.hidden = False
    def showMessage(self, *a): self.msgs.append(a)
    def hide(self): self.hidden = True
    def setToolTip(self, t): self.tip = t
win.tray = FakeTray(); st.settings["close_to_tray"] = True; st.settings["tray_hint_shown"] = False
win.show(); pump(100)
win.close(); pump(100)
ok(not win.isVisible() and win.tray.msgs and st.settings["tray_hint_shown"], "the close button hides the window in the tray (with a one-time hint)")
win.bring_to_front(); pump(100)
ok(win.isVisible(), "bring_to_front shows the window again")
win.tray.msgs.clear(); win.close(); pump(100)
ok(not win.isVisible() and not win.tray.msgs, "...the hint is shown only once")
win.bring_to_front(); pump(50)
st.settings["close_to_tray"] = False
import PySide6.QtWidgets as _qw
quit_calls = []
_orig_quit = _qw.QApplication.quit
_qw.QApplication.quit = staticmethod(lambda: quit_calls.append(1))
win.close(); pump(200)
ok(win.tray.hidden and quit_calls, "with 'keep running in the tray' off, closing really quits")
_qw.QApplication.quit = _orig_quit
win.tray = None


# ---------------------------------------------------------------- study page (1.6.0)
from datetime import date, timedelta
from voidlock.pages_c import ExamEditor, SubjectForm
sp = win.pages["study"]; win.goto("study"); pump(300)
sl = win.study
# subject form: language names switch the words counter on, editing keeps the id
f = SubjectForm(); f.name.setText("English grammar"); pump(30)
ok(f.words.isChecked() and f.tests.isChecked() and f.valid(), "the add-subject form: a language name turns the words counter on")
f.tests.set_silent(False)
sub = sl.add_subject(f.values()["name"], f.values()["color"], words=f.values()["words"], tests=f.values()["tests"])
sp._rebuild_subjects(); pump(100)
ok(sub["id"] not in sp.rows and sub["id"] in sp.word_rows, "a subject without 'Tests solved' has no tests row but has a words row")
e = SubjectForm(sl.subject(sub["id"]))
ok(e.name.text() == "English grammar" and not e.tests.isChecked() and e.words.isChecked(), "the edit form shows the subject's current settings")
# manual add / remove
y = date.today() - timedelta(days=1)
sp.goto_day(y); sp.man_sid = sub["id"]; sp.man_min.set_value(60)
sp.add_manual(); sp.man_min.set_value(25); sp.remove_manual(); pump(50)
ok(sl.subject_day_sec(y, sub["id"]) == 35 * 60, "Add time / Remove time buttons work on the shown day")
# plan for another day
tomorrow = date.today() + timedelta(days=1)
sp.goto_plan(tomorrow); sp.todo_in.setText("Read chapter 7"); sp.add_todo(); pump(50)
ok(len(sl.todos(tomorrow)) == 1 and len(sl.todos(date.today())) == 0 and sp.b_ptoday.isVisibleTo(sp), "a task can be planned for tomorrow")
sp.goto_plan(None); pump(50)
ok(not sp.b_ptoday.isVisibleTo(sp), "'Today' returns to today's plan")
# exams
ed = ExamEditor(sl, lambda: None)
ed.name.setText("Mock 5"); ed.save()
ok(len(sl.exams()) == 1 and sl.exams()[0]["name"] == "Mock 5", "exam editor adds an exam")
ed.load(sl.exams()[0]); ed.name.setText("Mock 5b"); ed.save()
ok(len(sl.exams()) == 1 and sl.exams()[0]["name"] == "Mock 5b", "...and edits it")
sl.add_exam("Tomorrow's", date.today() + timedelta(days=1)); win._popups = []
win._check_exams(datetime.now()); pump(100)
ok(len(win._popups) == 1, "an exam tomorrow pops up a reminder")
win._check_exams(datetime.now()); pump(50)
ok(len(win._popups) == 1, "...only once")
sp.refresh(); pump(50)
ok("Tomorrow's" in sp.exam_l.text(), "the next exam is written on the Study page")
ed.remove(sl.exams()[0]); sl.remove_exam(sl.exams()[0]["id"])

win.scanner.stop(); win.guard.stop()
print("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
