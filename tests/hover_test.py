"""Buttons must never stay lit after the mouse moved quickly over them (offscreen). Run: python tests/hover_test.py"""
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import QEventLoop, QTimer
app = QApplication([])
from voidlock.theme import apply_theme
apply_theme("void")
from voidlock.app import NavButton, WinButton
from voidlock.widgets import Button, HoverTracker
FAILS = []
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)
def wait(ms):
    l = QEventLoop(); QTimer.singleShot(ms, l.quit); l.exec()

def make(kind):
    if kind == "nav": return NavButton("x", "clock", "t")
    if kind == "win": return WinButton("min", "Minimize")
    return Button("ok", "ghost", None)

for kind in ("nav", "button", "win"):
    w = QWidget(); lay = QVBoxLayout(w)
    bs = [make(kind) for _ in range(5)]
    for b in bs: lay.addWidget(b)
    w.show(); wait(100)
    # 1) leave events are lost: enter every one without a single leave
    HoverTracker._lit = None
    for b in bs:
        b.enterEvent(None); wait(20)
    wait(190)
    ok([round(b._hover) for b in bs[:4]] == [0, 0, 0, 0], f"[{kind}] entering one releases the previous ones even if leave never came")
    # 2) the pointer is not over the last one (offscreen cursor is far away) -> the guard releases it
    wait(450)
    ok(all(b._hover == 0.0 for b in bs), f"[{kind}] the guard releases a button whose pointer is not inside")
    # 3) fast sweeps with normal events
    for _ in range(8):
        for b in bs:
            b.enterEvent(None); wait(12); b.leaveEvent(None); wait(8)
    wait(500)
    ok(all(b._hover == 0.0 for b in bs), f"[{kind}] fast sweeps leave nothing lit")
    # 4) outside driven hover (maximize button answered by Windows): in, then the guard lets go
    (bs[0].nc_hover if hasattr(bs[0], 'nc_hover') else lambda on: bs[0].hover_in())(True); wait(100)
    ok(bs[0]._hover > 0.3, f"[{kind}] nc_hover(True) lights it")
    wait(400)
    ok(bs[0]._hover == 0.0, f"[{kind}] ...and it goes out when the pointer is not over it")
    w.close()
print("\nFAILED:" if FAILS else "\nALL PASSED", FAILS or "")
os._exit(1 if FAILS else 0)
