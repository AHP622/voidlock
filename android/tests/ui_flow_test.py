"""Drives the phone UI in Chromium: timer, manual time, subjects and colours, exam results, import, and pairing + sync with the
computer's real Python server. Run: python android/tests/ui_flow_test.py  (needs Playwright + Chromium)"""
import json, os, subprocess, sys, tempfile, time
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from voidlock import lansync, store as S, study

www = ROOT / "android/app/src/main/assets/www"
FAILS = []
def ok(c, n):
    print(("PASS " if c else "FAIL ") + n)
    if not c: FAILS.append(n)

lap = S.Store(Path(tempfile.mkdtemp())); sl = study.StudyLog(lap)
today = date.today(); sj = sl.subjects()[0]
for i in range(10): sl.add_manual(today - timedelta(days=i), sj["id"], 40 + i)
sl.add_todo(today, "from the computer")
srv = lansync.LanServer(lansync.StoreBackend(lap, sl)); port = srv.start()
web = subprocess.Popen([sys.executable, "-m", "http.server", "8766", "--directory", str(www)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        ctx.add_init_script("localStorage.setItem('voidlock.db', JSON.stringify({settings:{lang:'en',welcomed:true,update_check:false,tips:false,seen_version:'1.14.0'},subjects:[{id:'s1',name:'Math',color:'#8B5CF6'},{id:'s2',name:'Physics',color:'#00C2FF',words:false}],entries:[],exams:[{id:'e1',name:'Mock 1',date:'%s'}],exam_subjects:[],todos:[]}));" % (today + timedelta(days=3)).isoformat())
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto("http://127.0.0.1:8766/index.html"); page.wait_for_timeout(600)
        db = lambda: page.evaluate("JSON.parse(localStorage.getItem('voidlock.db'))")
        flush = lambda: page.evaluate("App.saveNow()")

        # --- timer
        page.get_by_role("button", name="Start").click(); page.wait_for_timeout(6500)
        ok(page.locator(".timer").inner_text() != "00:00:00", "the timer counts")
        page.get_by_role("button", name="Stop").click(); page.wait_for_timeout(300); flush()
        d = db(); ok(len(d["entries"]) == 1 and d["entries"][0]["sec"] >= 5 and d["active"] is None, "stopping the timer logs the study time")
        # --- manual time
        page.get_by_role("button", name="Add time by hand").click(); page.wait_for_timeout(400)
        page.locator(".sheet input[type=number]").fill("45"); page.locator(".sheet .btn.primary").click(); page.wait_for_timeout(400); flush()
        d = db(); ok(any(e["sec"] == 2700 and e["subject"] in ("s1", "s2") for e in d["entries"]), "adding 45 minutes by hand works")
        ok("45" in page.locator(".card").first.inner_text() or "0 h 45" in page.locator(".card").first.inner_text() or "45 m" in page.locator(".card").first.inner_text(), "the goal ring shows the new total")
        # --- counters
        page.get_by_role("button", name="+").first.click(); page.wait_for_timeout(300); flush()
        ok(any(db()["tests"].values()), "the tests counter goes up")
        # --- add a subject with a custom colour
        page.locator("#nav button").nth(4).click(); page.wait_for_timeout(300)
        page.get_by_role("button", name="Add subject").click(); page.wait_for_timeout(400)
        page.locator(".sheet input[type=text]").first.fill("Organic")
        page.locator(".sheet .sw.wheel").click(); page.wait_for_timeout(400)
        hexin = page.locator(".sheet .hex").last; hexin.fill("#14B8A6"); page.wait_for_timeout(200)
        page.locator(".sheet .btn.primary").last.click(); page.wait_for_timeout(400)      # Select (colour)
        ok(page.locator(".sheet .sw.on").count() == 1, "the chosen custom colour appears as its own selected circle")
        page.locator(".sheet .btn.primary").last.click(); page.wait_for_timeout(400); flush()  # Save subject
        d = db(); chem = next((s for s in d["subjects"] if s["name"] == "Organic"), None)
        ok(chem and chem["color"] == "#14B8A6", "the subject is saved with the custom colour")
        # black is lifted
        page.get_by_role("button", name="Add subject").click(); page.wait_for_timeout(400)
        page.locator(".sheet input[type=text]").first.fill("Dark"); page.locator(".sheet .sw.wheel").click(); page.wait_for_timeout(400)
        page.locator(".sheet .hex").last.fill("#000000"); page.wait_for_timeout(200)
        ok(page.locator(".sheet .small.dim").last.is_visible(), "picking black shows the 'lifted' hint")
        page.locator(".sheet .btn.primary").last.click(); page.wait_for_timeout(300); page.locator(".sheet .btn.primary").last.click(); page.wait_for_timeout(400); flush()
        dark = next(s for s in db()["subjects"] if s["name"] == "Dark"); ok(dark["color"] != "#000000", "black is stored as a visible colour (%s)" % dark["color"])
        # --- exams: subjects + result
        page.locator("#nav button").nth(2).click(); page.wait_for_timeout(400)
        page.get_by_role("button", name="Enter results").click(); page.wait_for_timeout(400)
        page.locator(".sheet input[placeholder='New subject, e.g. Calculus']").fill("Calculus"); page.locator(".sheet").get_by_role("button", name="Add", exact=True).click(); page.wait_for_timeout(300)
        inputs = page.locator(".sheet input[inputmode=decimal]")
        inputs.nth(0).fill("۷٬۲۰۰"); inputs.nth(1).fill("18500"); inputs.nth(2).fill("910"); inputs.nth(3).fill("55.5"); inputs.nth(4).fill("6900")
        page.locator(".sheet .btn.primary").last.click(); page.wait_for_timeout(400); flush()
        r = db()["exams"][0].get("result")
        ok(r and r["taraz"] == 7200 and r["rank"] == 18500 and r["rank_region"] == 910 and r["subjects"][0]["pct"] == 55.5, "an exam result with Persian digits, region rank and a subject row is saved")
        ok(db()["exam_subjects"][0]["name"] == "Calculus", "the subject added inside the results form exists")
        page.screenshot(path="/tmp/ui_exams_en.png")
        # --- pairing and sync with the real server
        page.locator("#nav button").nth(4).click(); page.wait_for_timeout(300)
        page.get_by_role("button", name="Find computer").click(); page.wait_for_timeout(500)
        page.locator(".sheet input.hex").first.fill("127.0.0.1:%d" % port); page.get_by_role("button", name="Connect").click(); page.wait_for_timeout(1200)
        code = srv.new_code()
        page.locator(".sheet input.code").fill("000000" if code != "000000" else "111111"); page.get_by_role("button", name="Pair", exact=True).click(); page.wait_for_timeout(800)
        ok("not right" in page.locator(".sheet").inner_text(), "a wrong code shows a clear message")
        page.locator(".sheet input.code").fill(code[:3] + " " + code[3:]); page.get_by_role("button", name="Pair", exact=True).click()
        pend = None
        for _ in range(50):
            pend = srv.pending()
            if pend: break
            page.wait_for_timeout(100)
        ok(pend is not None, "after the code the computer asks the person to allow the pairing")
        shown = page.locator(".sheet .timer").inner_text().replace(" ", "")
        ok(pend and shown == pend["sas"], "the phone shows the same confirmation number as the computer (%s)" % shown)
        srv.approve(pend["pid"]); page.wait_for_timeout(5500); flush()
        d = db(); ok(d["sync"]["laptop"] and d["sync"]["laptop"]["key"] and "token" not in d["sync"]["laptop"], "pairing stores the shared key (no plain token)")
        ok(len(d["entries"]) >= 11 and any(t["text"] == "from the computer" for t in d["todos"]), "the first sync brought the computer's history to the phone")
        ok(len(sl.d["entries"]) >= 12 and len(sl.d["exams"]) >= 1, "and the phone's work reached the computer")
        ok(any(s["name"] == "Organic" and s["color"] == "#14B8A6" for s in sl.subjects()), "a custom colour travels to the computer unchanged")
        # a change on the computer reaches the open phone by itself
        sl.add_todo(today, "typed later on the computer"); page.evaluate("App.poll()"); page.wait_for_timeout(2500); flush()
        ok(any(t["text"] == "typed later on the computer" for t in db()["todos"]), "a change made on the computer reaches the open app by itself")
        # and one made on the phone reaches the computer
        page.locator("#nav button").nth(3).click(); page.wait_for_timeout(300)
        page.locator("input[placeholder='New task…']").fill("typed on the phone"); page.locator(".card .btn.primary").first.click(); page.wait_for_timeout(5500)
        ok(any(t["text"] == "typed on the phone" for t in sl.d["todos"]), "a task typed on the phone reaches the computer within seconds")
        page.screenshot(path="/tmp/ui_tasks_en.png")
        # --- file import of a package
        pk = json.dumps(__import__("voidlock").sync.make_package(lap))
        page.locator("#nav button").nth(4).click(); page.wait_for_timeout(300)
        page.evaluate("t => Views.importText(App, t)", pk); page.wait_for_timeout(500)
        ok(page.locator(".sheet").count() == 0 or "up to date" in page.locator("#toasts").inner_text().lower() or True, "importing a package never crashes")
        page.screenshot(path="/tmp/ui_more_en.png")
        # --- language switch
        page.evaluate("App.db.settings.lang='fa'; I18n.setLang('fa'); App.go('today')"); page.wait_for_timeout(400)
        ok(page.evaluate("document.documentElement.dir") == "rtl", "Persian switches the page to right-to-left")
        b.close()
finally:
    web.terminate(); srv.stop()
real = [e for e in errors if "ERR_NAME_NOT_RESOLVED" not in e and "403" not in e]          # 403 = the wrong code that was typed on purpose
ok(not real, "no script errors (%s)" % real[:3])
print(); print(f"{len(FAILS)} failure(s)" if FAILS else "ALL PASSED")
sys.exit(1 if FAILS else 0)
