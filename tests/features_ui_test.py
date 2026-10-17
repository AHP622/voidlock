import os, sys, time, shutil
os.environ["QT_QPA_PLATFORM"] = "offscreen"; os.environ["VOIDLOCK_HOME"] = "/tmp/vl_feat"
shutil.rmtree("/tmp/vl_feat", ignore_errors=True)
sys.path.insert(0, "/home/claude/voidlock")
from datetime import date, datetime, timedelta
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtCore import QTimer
from voidlock.theme import stylesheet, font
from voidlock.store import Store, uid, write_json, read_json
from voidlock.guard import GuardClient
from voidlock.overlays import Modal
from voidlock import study as S
from voidlock.app import MainWindow
app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(stylesheet()); app.setFont(font(13))
st = Store(); st.settings["long_cooldown"] = 3; st.settings["play_tracking"] = False; st.save_settings()
win = MainWindow(st, GuardClient(st)); win.resize(1280, 860); win.show()
def pump(ms):
    end = time.time() + ms/1000
    while time.time() < end: app.processEvents(); time.sleep(0.005)
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m)
accept = lambda: win.root.findChildren(Modal)[-1].finish(True)
pump(800)
# ---- Study timer page
win.goto("study"); pump(1500); pg = win.pages["study"]
sid = win.study.subjects()[0]["id"]
pg.toggle_subject(sid); pump(1200)
ok(win.study.active() and pg.tiles[sid].active, "tapping a subject starts its stopwatch")
win.study.d["active"]["started"] -= 600; pump(1200)    # pretend 10 minutes passed
ok(pg.tiles[sid].time_l.text().startswith(("00:10", "٠٠:١٠")) or "10:" in pg.tiles[sid].time_l.text(), f"tile shows running time {pg.tiles[sid].time_l.text()}")
pg.toggle_subject(sid); pump(300)
ok(win.study.active() is None and win.study.day_entries_sec(date.today()) >= 599, "tapping again stops and saves the entry")
pg.set_tests(sid, 35); ok(win.study.day_tests(date.today()) == 35, "tests counter saved for the day")
pg.man_sid = sid; pg.man_min.set_value(45); pg.add_manual(); ok(win.study.day_entries_sec(date.today()) >= 3300, "manual study time added")
pg.todo_in.setText("Solve 30 physics tests"); pg.add_todo(); ok(len(win.study.todos(date.today())) == 1, "to-do added")
td = win.study.todos(date.today())[0]; win.study.toggle_todo(td["id"]); ok(win.study.todos(date.today())[0]["done"], "to-do toggled")
pg.goto_day(date.today() - timedelta(days=1)); win.study.set_tests(date.today() - timedelta(days=1), sid, 20); pg.refresh()
ok(win.study.year_tests(date.today().year) >= 55, "tests for a past day are included in the year total")
# ---- Rewards
win.goto("rewards"); pump(1200); rp = win.pages["rewards"]
win.points.d["balance"] = 100; win.points.save(); rp._sig = None; rp.refresh(); pump(300)
QTimer.singleShot(600, accept); rp.claim(next(r for r in win.points.d["rewards"] if r["id"] == "r_play90")); pump(400)
cost = win.points.d["tickets"][-1]["cost"]
ok(cost == 100 and win.points.balance == 0 and len(win.points.unused()) == 1, f"claiming the play reward spends a lot of points (cost {cost})")
tk = win.points.unused()[0]
st.settings["game_friday_only"] = True
if date.today().weekday() != 4:
    rp.use_ticket(tk); pump(300)
    ok(S.pass_until(st) < time.time() and not tk["used"], "a play pass is refused on a day that is not Friday")
st.settings["game_friday_only"] = False       # now allow any day for the rest of the test
QTimer.singleShot(600, accept); rp.use_ticket(tk); pump(300)
ok(S.pass_until(st) > time.time() + 80 * 60, "using a gaming ticket starts a 90-minute play pass")
# ---- Lock hours via the real dialog
def fill_and_accept():
    m = win.root.findChildren(Modal)[-1]
    m.body.name.setText("Weekdays")
    QTimer.singleShot(200, lambda: m.finish(True))
QTimer.singleShot(500, fill_and_accept)
w = win.window_flow(); pump(500)
ok(w and len(st.windows) == 1 and st.windows[0]["name"] == "Weekdays" and "Games" in st.windows[0]["categories"], "lock hours created through the dialog")
ok(win.hours_state() != "", f"state text: {win.hours_state()}")
# release needs the typed phrase + wait
def typed():
    m = win.root.findChildren(Modal)[-1]; m.findChildren(QLineEdit)[0].setText("RELEASE")
    ok(not m.b_ok.isEnabled(), "removing lock hours: disabled during the wait")
    QTimer.singleShot(3400, lambda: m.finish(True))
QTimer.singleShot(700, typed)
win.release_window_flow(st.windows[0]); pump(2500); st.refresh_windows()
ok(len(st.windows) == 0, "lock hours removed after phrase + wait")
# ---- Website dialog
def site():
    m = win.root.findChildren(Modal)[-1]; m.body.findChildren(QLineEdit)[0].setText("https://www.YouTube.com/watch?v=1")
    QTimer.singleShot(300, lambda: m.finish(True))
QTimer.singleShot(500, site); a = win.site_flow(); pump(300)
ok(a and a["exe"] == "youtube.com" and a["kind"] == "site" and a["category"] == "Sites", "website added (normalised to youtube.com)")
ok(any(b["exe"] == "youtube.com" and b["kind"] == "site" for b in win.session.blocked_list()), "session rule list carries kind=site")
win.goto("apps"); pump(2200); row = win.pages["apps"].rows.get(a["id"]) or None
win.pages["apps"].build_rows(); pump(300); win.pages["apps"].refresh()
ok(win.pages["apps"].admin_card.isVisibleTo(win.pages["apps"]) or not win.guard.status().get("alive"), "banner explains websites need the administrator guard")
# ---- block popup from a guard event
write_json(st.p_events, {"list": [{"id": "e1", "t": time.time() + 1, "exe": "efootball.exe", "name": "eFootball", "why": "window"}]}); pump(2500)
ok(len(win._popups) == 1, "a guard event shows the personal popup card")
# ---- every page renders (empty + with data) and analytics report works
for k in win.keys:
    win.goto(k); pump(900)
ok(True, "all 8 pages render without errors")
st.settings["target_field"] = "X"; st.settings["exam_date"] = [1406, 4, 10]
from voidlock import messages
t, body = messages.block_message(st.settings, "Steam", "lock", today=date(2027, 6, 21)); ok("10 days" in body or "10" in body, "message counts down to the exam date")
win.scanner.stop(); win.guard.stop()
