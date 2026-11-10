"""Welcome, tour, tab tips and "What's new" in Chromium (phone-sized). Run:  python android/tests/intro_test.py [outdir]"""
import json, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

www = Path(__file__).resolve().parents[1] / "app/src/main/assets/www"
out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if out: out.mkdir(parents=True, exist_ok=True)
import re
VERSION = re.search(r'version: "([^"]+)"', (www / "config.js").read_text(encoding="utf-8")).group(1)
VERSION_FA = ''.join('۰۱۲۳۴۵۶۷۸۹'[int(c)] if c.isdigit() else c for c in VERSION)
FAILS = []


def ok(c, n):
    print(("PASS " if c else "FAIL ") + n)
    if not c: FAILS.append(n)


srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766", "--directory", str(www)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        def new(db=None, lang="fa"):
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            if db is not None: ctx.add_init_script("localStorage.setItem('voidlock.db', %s);" % json.dumps(json.dumps(db)))
            else: ctx.add_init_script("localStorage.setItem('voidlock.lang_boot','%s');" % lang)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto("http://127.0.0.1:8766/index.html"); pg.wait_for_timeout(1300)
            return ctx, pg

        def shot(pg, name):
            if out: pg.screenshot(path=str(out / (name + ".png")))

        # ---- a brand-new install: welcome (greeting, wish, signature) -> tour -> tips are not repeated
        ctx, pg = new()
        txt = pg.locator("#layer").inner_text()
        ok("Novum" in txt, "the welcome carries the signature Novum")
        ok("آرزو" in txt or "Wishing" in txt, "the welcome wishes the person success")
        shot(pg, "welcome")
        pg.get_by_text("تور کوتاه برنامه").click(); pg.wait_for_timeout(900)
        shot(pg, "tour_1")
        layer = pg.locator("#layer").inner_text()
        ok("امروز" in layer and "مرحله ۱ از ۵" in layer, "the tour starts with Today, step 1 of 5")
        for k in range(4):
            pg.get_by_text("بعدی").click(); pg.wait_for_timeout(500)
        shot(pg, "tour_5")
        ok("بیشتر" in pg.locator("#layer").inner_text(), "the last step is the More tab")
        pg.get_by_text("تمام").click(); pg.wait_for_timeout(700)
        ok(pg.locator(".card.tip").count() == 0, "after the tour no tip cards are shown")
        db = pg.evaluate("JSON.parse(localStorage.getItem('voidlock.db'))")
        ok(db["settings"].get("welcomed") and db["settings"].get("seen_version") == VERSION, "the welcome is remembered together with the version")
        ctx.close()

        # ---- an existing user: tips on first visit of every tab, once
        demo = json.load(open("/tmp/demo_fa.json", encoding="utf-8")) if Path("/tmp/demo_fa.json").exists() else None
        if demo:
            demo["settings"].pop("tips_seen", None); demo["settings"]["seen_version"] = VERSION
            ctx, pg = new(demo)
            ok(pg.locator(".card.tip").count() == 1, "the first tab shows one tip card")
            shot(pg, "tip_today")
            pg.get_by_text("فهمیدم").click(); pg.wait_for_timeout(300)
            ok(pg.locator(".card.tip").count() == 0, "'Got it' closes it")
            pg.locator("#nav button").nth(2).click(); pg.wait_for_timeout(500)
            ok("رتبه‌ی منطقه" in pg.locator(".card.tip").inner_text(), "the Exams tip mentions the region rank")
            shot(pg, "tip_exams")
            pg.get_by_text("نمایش ندادن راهنما").click(); pg.wait_for_timeout(300)
            pg.locator("#nav button").nth(3).click(); pg.wait_for_timeout(500)
            ok(pg.locator(".card.tip").count() == 0, "'Hide tips' stops all tips")
            pg.locator("#nav button").nth(4).click(); pg.wait_for_timeout(500)
            ok("Novum" in pg.locator("#view").inner_text(), "the signature is in the More tab")
            ctx.close()
            # ---- after an update: What's new once
            old = json.loads(json.dumps(demo)); old["settings"]["seen_version"] = "1.11.0"; old["settings"]["tips_seen"] = {"today": 1, "stats": 1, "exams": 1, "tasks": 1, "more": 1}
            ctx, pg = new(old)
            lt = pg.locator("#layer").inner_text()
            ok("تازه‌های نسخه‌ی" in lt and VERSION_FA in lt, "after an update the What's new sheet opens")
            shot(pg, "whatsnew")
            pg.get_by_text("باشه").click(); pg.wait_for_timeout(500)
            pg.wait_for_timeout(300)
            ok(pg.evaluate("JSON.parse(localStorage.getItem('voidlock.db')).settings.seen_version") == VERSION and pg.locator("#layer .sheet").count() == 0,
               "it is remembered, so it does not open again at the next start")
            ctx.close()
        b.close()
finally:
    srv.terminate()
ok(not errors, f"no script errors ({errors})")
print("\n%d failure(s)" % len(FAILS) if FAILS else "\nALL PASSED"); sys.exit(1 if FAILS else 0)
