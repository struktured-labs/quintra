#!/usr/bin/env python3
"""Headless Chromium (Playwright) check for the windowed fit layout: the whole
Game Boy screen is visible, 10:9, with no page scrollbars, at Tesla-like
windowed viewports. Usage: test_itch_fit.py BUILT_SITE_DIR SCREENSHOT_DIR"""
import json, sys, threading, functools, http.server, socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve(); out.mkdir(parents=True, exist_ok=True)
Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
Handler.log_message = lambda *a: None
srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

cases = [
    ("1920x960-desktop", 1920, 960, False, ""),
    ("1920x960-touch", 1920, 960, True, ""),
    ("1100x800-touch", 1100, 800, True, ""),
    ("1280x650-touch", 1280, 650, True, ""),
    ("1280x650-integer", 1280, 650, True, "&display=integer"),
    ("1280x650-stretch", 1280, 650, True, "&display=stretch"),
    ("1024x600-touch", 1024, 600, True, ""),
    ("800x480-touch", 800, 480, True, ""),
    ("500x800-portrait-touch", 500, 800, True, ""),
    ("1100x800-paddebug", 1100, 800, True, "&paddebug=1"),
]
results = []; failures = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required"])
    for name, w, h, touch, extra in cases:
        ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=touch)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/index.html?x=1{extra}")
        page.wait_for_function("!document.querySelector('#launch').disabled", timeout=30000)
        page.click("#launch")
        page.wait_for_timeout(3500)
        m = page.evaluate("""() => {
          const r = document.querySelector('#game').getBoundingClientRect();
          const d = document.documentElement;
          return {x: r.x, y: r.y, w: r.width, h: r.height, iw: innerWidth, ih: innerHeight,
            sw: d.scrollWidth, sh: d.scrollHeight, bodySh: document.body.scrollHeight,
            mode: window.QuintraDisplay && window.QuintraDisplay.mode,
            shellClass: document.querySelector('#player-shell').className};
        }""")
        shot = out / f"{name}.png"
        page.screenshot(path=str(shot))
        ok_visible = m["x"] >= -0.5 and m["y"] >= -0.5 and m["x"] + m["w"] <= w + 0.5 and m["y"] + m["h"] <= h + 0.5
        ok_scroll = m["sw"] <= w and m["sh"] <= h
        ratio = m["w"] / m["h"] if m["h"] else 0
        ok_ratio = "stretch" in name or abs(ratio - 10 / 9) < 0.02
        ok_size = m["w"] >= 160 and m["h"] >= 144
        verdict = all([ok_visible, ok_scroll, ok_ratio, ok_size]) and not errors
        m.update(name=name, ratio=round(ratio, 4), visible=ok_visible, noScroll=ok_scroll,
                 aspect=ok_ratio, errors=errors, ok=verdict, screenshot=str(shot))
        results.append(m)
        if not verdict: failures.append(name)
        if name == "1280x650-touch":
            # re-fit on resize
            page.set_viewport_size({"width": 1100, "height": 800})
            page.wait_for_timeout(400)
            r2 = page.evaluate("() => { const r = document.querySelector('#game').getBoundingClientRect(); return [r.width, r.height]; }")
            results.append({"name": "resize 1280x650->1100x800", "game": r2, "ok": r2[0] > m["w"]})
            if not r2[0] > m["w"]: failures.append("resize")
            page.screenshot(path=str(out / "resized-1280x650-to-1100x800.png"))
        if "paddebug" in name:
            txt = page.inner_text("#pad-debug")
            results.append({"name": "paddebug text", "text": txt})
            if "inner=1100x800" not in txt or "dpr=" not in txt or "scale=" not in txt:
                failures.append("paddebug")
        ctx.close()
    browser.close()
srv.shutdown()
print(json.dumps(results, indent=1))
print("FAIL: " + ", ".join(failures) if failures else "ALL FIT CHECKS PASSED")
sys.exit(1 if failures else 0)
