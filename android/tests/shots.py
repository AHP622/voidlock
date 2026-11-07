"""Screenshots of the phone UI in Chromium (phone-sized): python tests/shots.py <db.json> <outdir> [lang]"""
import json, subprocess, sys, time, os
from pathlib import Path
from playwright.sync_api import sync_playwright
www = Path(__file__).resolve().parents[1] / "app/src/main/assets/www"
db = open(sys.argv[1], encoding="utf-8").read(); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
lang = sys.argv[3] if len(sys.argv) > 3 else "fa"
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8765", "--directory", str(www)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
errors = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="fa-IR" if lang == "fa" else "en-GB")
        ctx.add_init_script("localStorage.setItem('voidlock.db', %s);" % json.dumps(db))
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type in ("error",) else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("http://127.0.0.1:8765/index.html"); page.wait_for_timeout(900)
        for view, label in (("today", 0), ("stats", 1), ("exams", 2), ("tasks", 3), ("more", 4)):
            page.locator("#nav button").nth(label).click(); page.wait_for_timeout(500)
            page.screenshot(path=str(out / f"{lang}_{view}.png"))
            page.evaluate("document.getElementById('view').scrollTop = 99999"); page.wait_for_timeout(300)
            page.screenshot(path=str(out / f"{lang}_{view}_bottom.png"))
        b.close()
finally:
    srv.terminate()
print("console errors:", errors or "none")
