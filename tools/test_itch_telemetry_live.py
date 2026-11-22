#!/usr/bin/env python3
"""Check the opt-in telemetry reads real game state in Firefox (headless).

    python3 tools/test_itch_telemetry_live.py http://127.0.0.1:8000/

Opens the page with ?telemetry=1, starts the cartridge, taps START/A on the
touch pad until a run is live, and checks the sampled fields (screen, hero,
HP, seed) are sane, the Export stats button is shown, and a run was logged.
"""
from __future__ import annotations

import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait

TAP = """
const b = document.querySelector('[data-touch-input="' + arguments[0] + '"]');
const o = {bubbles: true, cancelable: true, pointerId: 7, pointerType: 'touch'};
b.dispatchEvent(new PointerEvent('pointerdown', o));
setTimeout(() => b.dispatchEvent(new PointerEvent('pointerup', o)), 120);
"""


def main() -> None:
    url = sys.argv[1].rstrip("/") + "/?telemetry=1"
    options = Options()
    options.add_argument("-headless")
    options.set_preference("media.autoplay.default", 0)
    driver = webdriver.Firefox(options=options)
    try:
        driver.set_window_size(1200, 900)
        driver.get(url)
        WebDriverWait(driver, 30).until(
            lambda d: d.find_element(By.ID, "status").text.startswith("Ready"))
        driver.find_element(By.ID, "launch").click()
        seen = []
        deadline = time.time() + 90
        last = {}
        while time.time() < deadline:
            last = driver.execute_script("return (window.QuintraTelemetry || {}).last || {}") or {}
            seen.append(last.get("screen"))
            if last.get("screen") == 5 and last.get("seed"):
                break
            driver.execute_script(TAP, "START" if last.get("screen") in (None, 0, 1, 4) else "A")
            time.sleep(0.7)
        time.sleep(3)
        last = driver.execute_script("return window.QuintraTelemetry.last")
        data = driver.execute_script("return window.QuintraTelemetry.live.data")
        shown = driver.execute_script("return !document.getElementById('export-stats').hidden")
        print(json.dumps({"last": last, "runs": len(data.get("runs", [])),
                          "screens": sorted({s for s in seen if s is not None}),
                          "export_button": shown}, indent=1))
        assert shown, "Export stats button not shown"
        assert last["screen"] == 5, f"never reached a room: {last}"
        assert last["hero"] in ("wolfkin", "sauran", "corvin", "picsean", "vespine"), last
        assert 4 <= last["hpMax"] <= 60 and 0 < last["hp"] <= last["hpMax"], last
        assert last["seed"] != 0 and last["runTimer"] >= 1, last
        assert data["runs"] and data["runs"][-1]["hero"] == last["hero"], data
        print("[telemetry-live] OK")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
