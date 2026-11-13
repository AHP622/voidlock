"""The phone's classes in Chromium: the Classes mode of the Tasks tab, adding / editing / deleting, the next-class card on Today, and the report.
python android/tests/classes_ui_test.py [outdir]"""
import json, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
www = root / "app/src/main/assets/www"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if out: out.mkdir(parents=True, exist_ok=True)
FAILS = []


def ok(c, n):
    print(("PASS " if c else "FAIL ") + n)
    if not c: FAILS.append(n)


subprocess.run(["node", str(root / "tests/make_demo_db.js"), "/tmp/demo_cls.json", "fa"], check=True)
demo = open("/tmp/demo_cls.json", encoding="utf-8").read()
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8767", "--directory", str(www)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ctx.add_init_script("if(!localStorage.getItem('seeded')){localStorage.setItem('voidlock.db', %s);localStorage.setItem('seeded','1');}" % json.dumps(demo))
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto("http://127.0.0.1:8767/index.html"); pg.wait_for_timeout(1200)
        ok(pg.locator(".cls-next").count() == 1, "Today shows the next-class card")
        ok("کلاس امروز" in pg.locator(".cls-next").inner_text(), "and it is the class that starts in about an hour")
        if out: pg.screenshot(path=str(out / "today_next_class.png"))
        pg.locator("#nav button").nth(3).click(); pg.wait_for_timeout(500)
        pg.get_by_text("کلاس‌ها", exact=True).first.click(); pg.wait_for_timeout(500)
        ok(pg.locator(".cls-row").count() == 6, "the Classes mode lists the 6 classes of the week")
        if out: pg.screenshot(path=str(out / "classes_week.png"))
        pg.get_by_text("افزودن کلاس").first.click(); pg.wait_for_timeout(500)
        pg.locator("#layer input[type=text]").first.fill("زبان")
        pg.locator("#layer input[type=time]").fill("20:15")
        pg.locator("#layer input[type=number]").fill("45")
        if out: pg.screenshot(path=str(out / "class_sheet.png"))
        pg.get_by_role("button", name="ذخیره").click(); pg.wait_for_timeout(600)
        db = pg.evaluate("JSON.parse(localStorage.getItem('voidlock.db'))")
        z = [c for c in db["classes"] if c["name"] == "زبان"]
        ok(len(z) == 1 and z[0]["time"] == "20:15" and z[0]["minutes"] == 45 and z[0]["remind"] == 15, "a class added in the sheet is saved with its time, length and reminder")
        ok(pg.locator(".cls-row").count() == 7, "and appears in the week")
        pg.locator(".cls-row", has_text="زبان").click(); pg.wait_for_timeout(500)
        pg.locator("#layer select").nth(1).select_option("30")
        pg.get_by_role("button", name="ذخیره").click(); pg.wait_for_timeout(500)
        db = pg.evaluate("JSON.parse(localStorage.getItem('voidlock.db'))")
        ok([c for c in db["classes"] if c["name"] == "زبان"][0]["remind"] == 30, "editing a class changes it")
        pg.locator(".cls-row", has_text="زبان").click(); pg.wait_for_timeout(500)
        pg.get_by_role("button", name="حذف").click(); pg.wait_for_timeout(600)
        ok(pg.locator(".cls-row").count() == 6, "deleting a class removes it")
        # reminders: a fake Android shell receives the plan
        pg.evaluate("window.__plan = null; Native.scheduleReminders = (j) => { window.__plan = JSON.parse(j); }; Native.hasShell = () => true; Native.notificationsAllowed = () => true; Native.canExactAlarms = () => true; App.replan();")
        pg.wait_for_timeout(1600)
        plan = pg.evaluate("window.__plan")
        ok(plan and any(x["channel"] == "class" for x in plan) and all(x["at"] > 0 and x["title"] and x["id"] for x in plan), "the reminder plan reaches the shell: " + str(len(plan or [])) + " reminders")
        pg.evaluate("(() => { const d = App.db; d.settings.notify_classes = false; App.replan(); })()"); pg.wait_for_timeout(1600)
        ok(not any(x["channel"] == "class" for x in pg.evaluate("window.__plan")), "turning class reminders off removes them from the plan")
        pg.locator("#nav button").nth(4).click(); pg.wait_for_timeout(600)
        ok("اعلان‌ها" in pg.locator("#view").inner_text() and pg.locator("#view input[type=checkbox]").count() >= 3, "the More tab has the notifications card with its switches")
        if out: pg.screenshot(path=str(out / "more_notifications.png"))
        # the report carries the timetable
        rep = pg.evaluate("(() => { const d = new Date(); const dk = Core.dkey(d); return Report.build(App.db, Core.dkey(Core.addDays(d, -6)), dk, { lang: 'fa' }).html; })()")
        ok("برنامه‌ی هفتگی کلاس‌ها" in rep and "حسابان" in rep and 'class="sched"' in rep, "the phone's report has the weekly timetable")
        b.close()
finally:
    srv.terminate()
ok(not errors, f"no script errors ({errors})")
print("\n%d failure(s)" % len(FAILS) if FAILS else "\nALL PASSED"); sys.exit(1 if FAILS else 0)
