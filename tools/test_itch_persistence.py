#!/usr/bin/env python3
"""Verify Quintra cartridge RAM persistence in a real browser."""

from __future__ import annotations

import argparse
import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait


def wait_ready(driver: webdriver.Firefox) -> None:
    WebDriverWait(driver, 30).until(
        lambda browser: browser.find_element(By.ID, "status").text.startswith("Ready")
    )


def main() -> None:
    logical_ram_bytes = 32 * 1024
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--firefox-binary")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    options = Options()
    if not args.headed:
        options.add_argument("-headless")
    if args.firefox_binary:
        options.binary_location = args.firefox_binary

    driver = webdriver.Firefox(options=options)
    driver.set_script_timeout(30)
    try:
        driver.get(args.url)
        wait_ready(driver)
        seeded = driver.execute_async_script(
            """
            const logicalSize = arguments[0];
            const done = arguments[arguments.length - 1];
            (async () => {
              const api = window.WasmBoy.WasmBoy;
              const state = await api.saveState();
              const ram = new Uint8Array(state.wasmboyMemory.cartridgeRam);
              const marker = [81, 85, 73, 78, 84, 82, 65, 23];
              if (ram.length < logicalSize) throw new Error('cartridge RAM is smaller than Quintra SRAM');
              const offset = logicalSize - marker.length;
              const original = Array.from(ram.slice(offset));
              if (original.every((value, index) => value === marker[index])) marker[7] ^= 255;
              ram.set(marker, offset);
              state.wasmboyMemory.cartridgeRam = ram;
              await api.loadState(state);
              await api.saveLoadedCartridge({ title: 'Quintra' });
              done({ offset, original, marker, size: ram.length });
            })().catch(error => done({ error: String(error.stack || error) }));
            """,
            logical_ram_bytes,
        )
        if seeded.get("error"):
            raise RuntimeError(seeded["error"])

        driver.refresh()
        wait_ready(driver)
        restored = driver.execute_async_script(
            """
            const offset = arguments[0];
            const original = arguments[1];
            const marker = arguments[2];
            const done = arguments[arguments.length - 1];
            (async () => {
              const api = window.WasmBoy.WasmBoy;
              const state = await api.saveState();
              const ram = new Uint8Array(state.wasmboyMemory.cartridgeRam);
              const observed = Array.from(ram.slice(offset, offset + marker.length));
              ram.set(original, offset);
              state.wasmboyMemory.cartridgeRam = ram;
              await api.loadState(state);
              await api.saveLoadedCartridge({ title: 'Quintra' });
              done({ observed, size: ram.length });
            })().catch(error => done({ error: String(error.stack || error) }));
            """,
            seeded["offset"],
            seeded["original"],
            seeded["marker"],
        )
        if restored.get("error"):
            raise RuntimeError(restored["error"])

        driver.refresh()
        wait_ready(driver)
        cleaned = driver.execute_async_script(
            """
            const offset = arguments[0];
            const length = arguments[1];
            const done = arguments[arguments.length - 1];
            (async () => {
              const state = await window.WasmBoy.WasmBoy.saveState();
              const ram = new Uint8Array(state.wasmboyMemory.cartridgeRam);
              done({ observed: Array.from(ram.slice(offset, offset + length)), size: ram.length });
            })().catch(error => done({ error: String(error.stack || error) }));
            """,
            seeded["offset"],
            len(seeded["original"]),
        )
        if cleaned.get("error"):
            raise RuntimeError(cleaned["error"])
    finally:
        driver.quit()

    report = {
        "backingRamBytes": seeded["size"],
        "logicalRamBytes": logical_ram_bytes,
        "sentinelRestored": restored["observed"] == seeded["marker"],
        "originalRestored": cleaned["observed"] == seeded["original"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if (
        seeded["size"] < logical_ram_bytes
        or restored["size"] != seeded["size"]
        or cleaned["size"] != seeded["size"]
    ):
        raise SystemExit("Persistence gate failed: cartridge RAM size changed")
    if not report["sentinelRestored"]:
        raise SystemExit("Persistence gate failed: saved cartridge RAM did not survive reload")
    if not report["originalRestored"]:
        raise SystemExit("Persistence gate failed: original cartridge RAM was not restored")
    print("Persistence gate passed")


if __name__ == "__main__":
    main()
