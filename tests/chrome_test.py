"""Window chrome logic that Windows drives (offscreen): the maximize button answers WM_NCHITTEST with HTMAXBUTTON (Snap Layouts),
its hover / press / click are forwarded, edges still resize, and the window asks for minimize / maximize / system-menu hints.
Run: python tests/chrome_test.py"""
import os, sys, time, shutil, tempfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = os.path.join(tempfile.gettempdir(), "vl_chrome"); shutil.rmtree(home, ignore_errors=True)
os.environ["VOIDLOCK_HOME"] = home
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
from voidlock import i18n, __version__
from voidlock.store import Store
i18n.set_language("en")
from voidlock.theme import stylesheet, font, apply_theme
apply_theme("void")
from voidlock.guard import GuardClient
from voidlock.app import MainWindow
app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(stylesheet()); app.setFont(font(13))
st = Store(); st.settings.update(play_tracking=False, intro_done=True, tips_enabled=False, intro_version=__version__); st.save_settings()
win = MainWindow(st, GuardClient(st)); win.resize(1280, 860); win.show()
FAILS = []
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)
def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end: app.processEvents(); time.sleep(0.005)
pump(500)

fl = win.windowFlags()
ok(bool(fl & Qt.WindowType.WindowMinimizeButtonHint) and bool(fl & Qt.WindowType.WindowMaximizeButtonHint) and bool(fl & Qt.WindowType.WindowSystemMenuHint),
   "the frameless window asks for the minimize / maximize / system-menu hints (taskbar click and Snap Layouts need them)")
ok(bool(fl & Qt.WindowType.FramelessWindowHint), "it is still frameless")

def lp(gx, gy): return ((gy & 0xFFFF) << 16) | (gx & 0xFFFF)
def msg(m, gx=0, gy=0, w=0): return SimpleNamespace(message=m, lParam=lp(gx, gy), wParam=w)
def centre(b):
    p = b.mapToGlobal(QPoint(b.width() // 2, b.height() // 2)); return p.x(), p.y()

bx, by = centre(win.topbar.b_max)
ok(win._chrome_message(msg(0x0084, bx, by), 0x0084) == (True, 9), "the pointer over the maximize button hit-tests as HTMAXBUTTON")
mx, my = centre(win.topbar.b_min)
ok(win._chrome_message(msg(0x0084, mx, my), 0x0084) is None, "the minimize button is left to Qt")
cx, cy = centre(win.topbar.b_close)
ok(win._chrome_message(msg(0x0084, cx, cy), 0x0084) is None, "the close button is left to Qt")
tl = win.mapToGlobal(QPoint(2, 2))
ok(win._chrome_message(msg(0x0084, tl.x(), tl.y()), 0x0084) == (True, 13), "the top-left corner still resizes")
br = win.mapToGlobal(QPoint(win.width() - 2, win.height() - 2))
ok(win._chrome_message(msg(0x0084, br.x(), br.y()), 0x0084) == (True, 17), "the bottom-right corner still resizes")
mid = win.mapToGlobal(QPoint(win.width() // 2, win.height() // 2))
ok(win._chrome_message(msg(0x0084, mid.x(), mid.y()), 0x0084) is None, "the middle of the window is plain client area")

# hover / press / click forwarded to the Qt button
toggles = []
win.toggle_max = lambda: toggles.append(1)
b = win.topbar.b_max
win._chrome_message(msg(0x00A0, bx, by, 9), 0x00A0); pump(100)
ok(b._hover > 0.3, "WM_NCMOUSEMOVE over the button lights it")
win._chrome_message(msg(0x00A0, mid.x(), mid.y(), 1), 0x00A0); pump(300)
ok(b._hover < 0.05, "moving off the button (still in the non-client area) lets go")
r = win._chrome_message(msg(0x00A1, bx, by, 9), 0x00A1)
ok(r == (True, 0) and win._max_pressed, "pressing it is swallowed and remembered")
r = win._chrome_message(msg(0x00A2, bx, by, 9), 0x00A2)
ok(r == (True, 0) and toggles == [1], "releasing it on the button maximizes / restores once")
win._chrome_message(msg(0x00A1, bx, by, 9), 0x00A1)
r = win._chrome_message(msg(0x00A2, mid.x(), mid.y(), 1), 0x00A2)
ok(r == (True, 0) and toggles == [1] and not win._max_pressed, "pressing it and releasing elsewhere does nothing")
ok(win._chrome_message(msg(0x00A2, mid.x(), mid.y(), 1), 0x00A2) is None, "a release that never started on the button is ignored")

# maximized: still the button, but no edge resizing
win.showMaximized(); pump(300)
bx, by = centre(win.topbar.b_max)
ok(win._chrome_message(msg(0x0084, bx, by), 0x0084) == (True, 9), "maximized: the button is still HTMAXBUTTON")
ok(win._chrome_message(msg(0x0084, 1, 1), 0x0084) is None, "maximized: no edge resizing")
# one-click weekly report (computer)
from datetime import date, timedelta
from pathlib import Path
from voidlock import report_ui
win.study.add_todo(date.today() - timedelta(days=2), "weekly plan")
win.toast = lambda *a, **k: None
out = Path(home) / "weekly"
p = report_ui.quick_weekly_report(win, folder=out, reveal=False)
ok(p is not None and Path(p).exists() and str(p).endswith(".html") and Path(p).parent == out, "the weekly report is saved as an HTML file in the folder")
h = Path(p).read_text(encoding="utf-8")
ok('id="plans"' in h and "weekly plan" in h and "Daily plans" in h, "it has the daily plans (inside the last 7 days)")
v = report_ui.weekly_values(win, today=date(2026, 11, 18))
ok(v["start"] == date(2026, 11, 12) and v["end"] == date(2026, 11, 18) and v["fmt"] == "html", "the period is the 7 days ending today")
ok(report_ui.quick_weekly_report(win, folder=Path(home) / "x" / "\0bad", reveal=False) is None, "a folder that cannot be made gives an error toast and None")
print("\nFAILED:" if FAILS else "\nALL PASSED", FAILS or "")
sys.stdout.flush(); os._exit(1 if FAILS else 0)
