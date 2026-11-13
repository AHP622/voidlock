"""The phone's motion layer (js/motion.js + app.css tokens): the segmented-control thumb tracks the selected option, the view fades in on
every tab switch, and Reduced Motion (the app's own switch) collapses every duration to ~0 without breaking the UI.
python android/tests/motion_test.py"""
import subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

www = Path(__file__).resolve().parents[1] / "app/src/main/assets/www"
FAILS = []


def ok(c, n):
    print(("PASS " if c else "FAIL ") + n)
    if not c: FAILS.append(n)


srv = subprocess.Popen([sys.executable, "-m", "http.server", "8768", "--directory", str(www)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto("http://127.0.0.1:8768/index.html"); pg.wait_for_timeout(1200)
        if pg.locator("#layer .sheet").count():                                  # dismiss the first-run welcome sheet
            pg.evaluate("document.querySelectorAll('#layer .scrim').forEach((s) => s.click())")
            pg.wait_for_timeout(500)
        pg.locator("#nav button").nth(4).click(); pg.wait_for_timeout(600)       # More -> Settings has a seg (language)
        pg.wait_for_timeout(50)
        thumb = pg.evaluate("""() => { const seg = document.querySelector('.seg'); const on = seg.querySelector('button.on'); const th = seg.querySelector(':scope > .thumb');
          const sx = seg.getBoundingClientRect(), bx = on.getBoundingClientRect(), tx = th.getBoundingClientRect();
          return { segFound: !!seg, thumbFound: !!th, dx: Math.abs(tx.left - bx.left), dw: Math.abs(tx.width - bx.width) }; }""")
        ok(thumb["segFound"] and thumb["thumbFound"], "a sliding thumb is added behind the segmented control")
        ok(thumb["dx"] < 1.5 and thumb["dw"] < 1.5, f"and it sits exactly under the selected option (dx={thumb['dx']:.2f} dw={thumb['dw']:.2f})")
        other = pg.locator(".seg button").nth(1)
        other.click(); pg.wait_for_timeout(500)
        thumb2 = pg.evaluate("""() => { const seg = document.querySelector('.seg'); const on = seg.querySelector('button.on'); const th = seg.querySelector(':scope > .thumb');
          const sx = seg.getBoundingClientRect(), bx = on.getBoundingClientRect(), tx = th.getBoundingClientRect(); return Math.abs(tx.left - bx.left); }""")
        ok(thumb2 < 1.5, "and follows it to the newly selected option")
        dur_before = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--d-normal').trim()")
        ok(dur_before not in ("", "1ms"), "motion is on by default here (" + dur_before + ")")
        row = pg.locator("#view label.row.sb", has_text="انیمیشن" ).or_(pg.locator("#view label.row.sb", has_text="Reduce animations"))
        if row.count() == 0: row = pg.locator("#view label.row.sb", has_text="کاهش انیمیشن").or_(pg.locator("#view label.row.sb", has_text="Motion effects"))
        row.locator("input[type=checkbox]").first.click(); pg.wait_for_timeout(400)
        reduced_attr = pg.evaluate("document.documentElement.getAttribute('data-motion')")
        dur_after = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--d-normal').trim()")
        ok(reduced_attr == "off" and dur_after == "1ms", f"Reduced Motion sets data-motion=off and collapses durations ({dur_after})")
        pg.locator("#nav button").nth(0).click(); pg.wait_for_timeout(300)
        ok(pg.locator("#view").evaluate("(el) => el.classList.contains('v-in')"), "switching tabs still applies the view-entrance class with Reduced Motion on (just instant)")
        db = pg.evaluate("JSON.parse(localStorage.getItem('voidlock.db'))")
        ok(db["settings"]["reduce_motion"] is True, "the choice is saved")
        pg.reload(); pg.wait_for_timeout(1200)
        ok(pg.evaluate("document.documentElement.getAttribute('data-motion')") == "off", "and still applied after a restart")
        b.close()
finally:
    srv.terminate()
ok(not errors, f"no script errors ({errors})")
print("\n%d failure(s)" % len(FAILS) if FAILS else "\nALL PASSED")
sys.exit(1 if FAILS else 0)
