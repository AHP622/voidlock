"""UI regressions fixed in 1.3.0 (offscreen). Run: python tests/regressions_ui_test.py"""
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
ok(len(win.study.subjects()) == 5, "after Reset everything the Study page and Overview still work")

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
win.scanner.stop(); win.guard.stop()
print("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
