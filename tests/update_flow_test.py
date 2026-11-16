"""Update flow (offscreen): background download with progress, 'install now or later?', 6-hour reminders, reuse of a
finished download after a restart. Network and install are faked. Run: python tests/update_flow_test.py [fa] [shot.png]"""
import os, sys, time, shutil, tempfile, hashlib
os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = os.path.join(tempfile.gettempdir(), "vl_upd")
os.environ["VOIDLOCK_HOME"] = home
shutil.rmtree(home, ignore_errors=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FA = "fa" in sys.argv[1:]
SHOT = next((a for a in sys.argv[1:] if a.endswith(".png")), None)
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from voidlock import i18n, updater
from voidlock.store import Store
if FA:
    s0 = Store(); s0.settings["language"] = "fa"; s0.save_settings()
i18n.set_language("fa" if FA else "en")
from voidlock.theme import stylesheet, font, apply_theme
apply_theme("void")
from voidlock.guard import GuardClient
from voidlock.overlays import Modal
from voidlock.app import MainWindow

app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(stylesheet()); app.setFont(font(13))
i18n.install_hooks()
if FA:
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
from voidlock import __version__
st = Store(); st.settings.update(play_tracking=False, intro_done=True, tips_enabled=False, intro_version=__version__); st.save_settings()
win = MainWindow(st, GuardClient(st)); win.resize(1280, 860); win.show()
FAILS = []
def pump(ms):
    end = time.time() + ms / 1000
    while time.time() < end: app.processEvents(); time.sleep(0.005)
def ok(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c: FAILS.append(m)
def until(cond, ms=4000):
    end = time.time() + ms / 1000
    while time.time() < end and not cond(): app.processEvents(); time.sleep(0.005)
    return cond()
pump(600)

# ---- fakes: GitHub, the download, the swap of the exe, the restart
PAYLOAD = b"MZ" + b"x" * 5000
SHA = hashlib.sha256(PAYLOAD).hexdigest()
INFO = {"tag": "v9.9.9", "version": "9.9.9", "sha": SHA, "sha_url": "", "url": "https://github.com/x/y", "size": len(PAYLOAD) * 4000, "notes": ""}
calls = {"download": 0, "apply": [], "restart": 0}
GATE = {"hold": 0.0}
def fake_check(repo=None, timeout=10): return dict(INFO)
def fake_download(info, dest, progress=None, **k):
    calls["download"] += 1
    Path(dest).mkdir(parents=True, exist_ok=True)
    for p in (0, 7, 7, 7, 31, 58, 99):
        if progress: progress(p)
        time.sleep(0.04 + GATE["hold"])
    f = Path(dest) / updater.ASSET
    f.write_bytes(PAYLOAD)
    return f
updater.check, updater.download = fake_check, fake_download
updater.apply = lambda path, target=None: calls["apply"].append(str(path))
win.restart_app = lambda: calls.__setitem__("restart", calls["restart"] + 1)
win.guard.stop = lambda *a, **k: None
sys.frozen = True                                  # updates only install into the built exe
win.isActiveWindow = lambda: True                  # the offscreen platform has no real focus

def answer(button, wait=250):
    """Press a button of the next dialog that opens."""
    def go():
        ms = win.root.findChildren(Modal)
        if ms:
            getattr(ms[0], button).click()
    QTimer.singleShot(wait, go)

sp = win.pages["settings"]
win.goto("settings"); pump(300)
st.settings["update_auto_install"] = True; st.settings["update_check"] = True; st.save_settings()
seen = []
orig = win._on_update_progress
def _spy(p):
    before = win.update_progress
    orig(p)
    if win.update_progress != before:                # only a really new percentage reaches the UI
        seen.append((p, sp.up_bar._target, sp.up_pct.text()))
win._on_update_progress = _spy

# 1. check -> automatic download -> progress shown -> asks
answer("b_cancel", 1200)                           # the person picks "Later"
win.check_updates(manual=False, startup=True)
ok(until(lambda: win.update_ready is not None, 6000), "download finishes and the file is marked ready")
pump(1800)
ps = [p for p, _, _ in seen]
ok(ps == sorted(ps) and len(set(ps)) == len(ps) and ps[-1] == 99, f"progress is reported once per new percentage, rising: {ps}")
ok(all(abs(t - p / 100) < 1e-9 for p, t, _ in seen), "the bar value follows the percentage")
ok(any("31" in t.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) for _, _, t in seen), "the percentage text shows the number")
ok(sp.up_bar._target == 1.0 and sp.up_prog.isVisible(), "the bar is full and visible when the download is done")
ok(calls["download"] == 1 and calls["apply"] == [], "nothing is installed without asking")
ok(st.settings.get("update_remind_at", 0) > time.time() + 5.9 * 3600, "'Later' schedules the next reminder about 6 hours ahead")
ok(st.settings.get("update_ready_tag") == "v9.9.9", "the waiting download is remembered")
if SHOT:
    sp.scroll.verticalScrollBar().setValue(sp.scroll.verticalScrollBar().maximum()); pump(500)
    win.grab().save(SHOT); print("saved", SHOT)

# 2. not due yet -> silent; due -> asks again; "Install now" installs
win._update_tick(); pump(200)
ok(not win.root.findChildren(Modal), "no question before the 6 hours are over")
st.settings["update_remind_at"] = time.time() - 1
answer("b_ok", 300)
win._update_tick(); pump(600)
ok(len(calls["apply"]) == 1 and calls["apply"][0].endswith(updater.ASSET), "'Install now' swaps in the downloaded file")
pump(1200)
ok(calls["restart"] == 1, "and restarts the program")
ok("update_ready_tag" not in st.settings and st.settings.get("update_last_tag") == "v9.9.9", "state is cleaned after installing")

# 3. never during a session / hidden window pops a notice and pushes the reminder
win._upd_applying = False
win.update_ready = str(Path(home) / "updates" / updater.ASSET)
st.settings.update(update_ready_tag="v9.9.9", update_ready_version="9.9.9", update_remind_at=time.time() - 1)
win.session.state = "running"
win._update_tick(); pump(200)
ok(not win.root.findChildren(Modal), "no question while a study session is running")
win.session.state = "idle"
popups = []
win.notify_popup = lambda t, b, ms=9000: popups.append((t, b))
win.isActiveWindow = lambda: False
win._update_tick()
ok(popups and popups[0][0] == "UPDATE READY" and win._ask_on_show, "window not in front: a notice instead of a dialog")
ok(st.settings["update_remind_at"] > time.time() + 5.9 * 3600, "...and the next reminder is 6 hours away")
win.isActiveWindow = lambda: True
answer("b_cancel", 300)
win._update_tick(); pump(700)
ok(not win._ask_on_show and not win._asking_update, "when the window is in front again the question is asked once")

# 4. a finished download survives a restart and is not downloaded twice
(Path(home) / "updates" / updater.ASSET).write_bytes(PAYLOAD)
w2 = updater.verify_ready(dict(INFO, size=len(PAYLOAD)), Path(home) / "updates")
ok(w2 is not None, "a complete, matching file from an earlier run is accepted")
(Path(home) / "updates" / updater.ASSET).write_bytes(b"MZ" + b"y" * 5000)
ok(updater.verify_ready(dict(INFO, size=0), Path(home) / "updates") is None, "a file with a different checksum is rejected")
(Path(home) / "updates" / updater.ASSET).write_bytes(b"MZ" + b"x" * 10)
ok(updater.verify_ready(dict(INFO, size=0), Path(home) / "updates") is None, "a truncated file is rejected")

# 5. a failed download re-enables the buttons and shows the message
win.update_ready = None; win.update_progress = None
def bad(info, dest, progress=None, **k): raise updater.UpdateError("connection reset")
updater.download = bad
win._auto_retries = 99
win.toast = lambda *a, **k: None
win.download_update(auto=False)
until(lambda: not win._downloading, 3000); pump(200)
sp.refresh_update_box()
ok(sp.b_up_install.isEnabled() and "connection reset" in win.update_status and not sp.up_prog.isVisible(), "failure: message shown, button usable again, bar hidden")
print("\nFAILED:" if FAILS else "\nALL OK", FAILS or "")
win._quitting = True
sys.stdout.flush()
os._exit(1 if FAILS else 0)
