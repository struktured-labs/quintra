#!/usr/bin/env python3
"""Prove cartridge RAM migration across real Quintra web releases."""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import shutil
import tempfile
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait


STABLE_KEY = "quintra:mbc5:sram:v1"
LOGICAL_RAM_BYTES = 32 * 1024
MARKER_OFFSET = 32760
MARKER = [0x51, 0x55, 0x49, 0x4E, 0x54, 0x52, 0x41, 0xA5]


class PackageServer(http.server.ThreadingHTTPServer):
    package_dir: Path


class PackageHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        server = args[2]
        super().__init__(*args, directory=str(server.package_dir), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        pass


def wait_ready(driver: webdriver.Firefox) -> None:
    WebDriverWait(driver, 30).until(
        lambda browser: browser.find_element(By.ID, "status").text.startswith("Ready")
    )


def firefox_options(binary: str | None) -> Options:
    options = Options()
    options.add_argument("-headless")
    if binary:
        options.binary_location = binary
    return options


def execute_async(driver: webdriver.Firefox, script: str, *args: object) -> dict:
    result = driver.execute_async_script(script, *args)
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result


def seed_legacy_save(driver: webdriver.Firefox) -> dict:
    return execute_async(
        driver,
        """
        const offset = arguments[0];
        const marker = arguments[1];
        const done = arguments[arguments.length - 1];
        (async () => {
          const api = window.WasmBoy.WasmBoy;
          const state = await api.saveState();
          const ram = new Uint8Array(state.wasmboyMemory.cartridgeRam);
          if (ram.length < offset + marker.length) throw new Error(`RAM is only ${ram.length} bytes`);
          ram.set(marker, offset);
          state.wasmboyMemory.cartridgeRam = ram;
          await api.loadState(state);
          await api.saveLoadedCartridge({ title: 'Quintra migration gate' });
          await api.saveState();
          const states = await api.getSaveStates();
          done({ backingBytes: ram.length, saveStates: Array.isArray(states) ? states.length : 0 });
        })().catch(error => done({ error: String(error.stack || error) }));
        """,
        MARKER_OFFSET,
        MARKER,
    )


def strip_legacy_metadata(driver: webdriver.Firefox) -> dict:
    return execute_async(
        driver,
        """
        const done = arguments[arguments.length - 1];
        const request = indexedDB.open('wasmboy', 1);
        request.onerror = () => done({ error: `IndexedDB open failed: ${request.error}` });
        request.onsuccess = () => {
          const db = request.result;
          const tx = db.transaction('keyval', 'readwrite');
          const store = tx.objectStore('keyval');
          let stripped = 0;
          let preservedStates = 0;
          let header = null;
          const cursorRequest = store.openCursor();
          cursorRequest.onerror = () => done({ error: `cursor failed: ${cursorRequest.error}` });
          cursorRequest.onsuccess = event => {
            const cursor = event.target.result;
            if (!cursor) return;
            const value = cursor.value;
            if (typeof cursor.key !== 'string' && value && value.cartridgeRam !== undefined) {
              const tag = Object.prototype.toString.call(cursor.key);
              const key = Array.isArray(cursor.key)
                ? Uint8Array.from(cursor.key)
                : tag === '[object ArrayBuffer]'
                  ? new Uint8Array(cursor.key)
                  : new Uint8Array(cursor.key.buffer, cursor.key.byteOffset, cursor.key.byteLength);
              header = Array.from(key);
              preservedStates = Array.isArray(value.saveStates) ? value.saveStates.length : 0;
              delete value.cartridgeRom;
              delete value.cartridgeInfo;
              cursor.update(value);
              stripped += 1;
            }
            cursor.continue();
          };
          tx.oncomplete = () => {
            db.close();
            done({ stripped, preservedStates, header });
          };
          tx.onerror = () => done({ error: `transaction failed: ${tx.error}` });
        };
        """,
    )


def inspect_current_release(driver: webdriver.Firefox) -> dict:
    return execute_async(
        driver,
        """
        const stableKey = arguments[0];
        const offset = arguments[1];
        const markerLength = arguments[2];
        const done = arguments[arguments.length - 1];
        (async () => {
          const api = window.WasmBoy.WasmBoy;
          const statesBeforeProbe = await api.getSaveStates();
          const state = await api.saveState();
          const ram = new Uint8Array(state.wasmboyMemory.cartridgeRam);
          const observed = Array.from(ram.slice(offset, offset + markerLength));

          const db = await new Promise((resolve, reject) => {
            const request = indexedDB.open('wasmboy', 1);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
          });
          const inspected = await new Promise((resolve, reject) => {
            const tx = db.transaction('keyval');
            const store = tx.objectStore('keyval');
            const stableRequest = store.get(stableKey);
            const keysRequest = store.getAllKeys();
            const recordsRequest = store.getAll();
            tx.oncomplete = () => resolve({
              stable: stableRequest.result,
              keys: keysRequest.result,
              records: recordsRequest.result
            });
            tx.onerror = () => reject(tx.error);
          });
          db.close();

          const stable = inspected.stable;
          const stableRam = stable && stable.cartridgeRam !== undefined
            ? new Uint8Array(stable.cartridgeRam) : null;
          const binary = [];
          inspected.keys.forEach((key, index) => {
            if (typeof key === 'string') return;
            const tag = Object.prototype.toString.call(key);
            const bytes = Array.isArray(key)
              ? Uint8Array.from(key)
              : tag === '[object ArrayBuffer]'
                ? new Uint8Array(key)
                : new Uint8Array(key.buffer, key.byteOffset, key.byteLength);
            const record = inspected.records[index] || {};
            const recordRam = record.cartridgeRam !== undefined
              ? new Uint8Array(record.cartridgeRam) : null;
            binary.push({
              header: Array.from(bytes),
              fields: Object.keys(record).sort(),
              marker: recordRam ? Array.from(recordRam.slice(offset, offset + markerLength)) : null,
              saveStates: Array.isArray(record.saveStates) ? record.saveStates.length : 0
            });
          });

          done({
            observed,
            backingBytes: ram.length,
            saveStatesBeforeProbe: Array.isArray(statesBeforeProbe) ? statesBeforeProbe.length : 0,
            stablePresent: Boolean(stable),
            stableFields: stable ? Object.keys(stable).sort() : [],
            stableBytes: stableRam ? stableRam.length : 0,
            stableMarker: stableRam ? Array.from(stableRam.slice(offset, offset + markerLength)) : null,
            stableSavedAt: stable ? stable.cartridgeRamSavedAt : null,
            binary,
            unloadStoragePresent: localStorage.getItem('WASMBOY_UNLOAD_STORAGE') !== null
          });
        })().catch(error => done({ error: String(error.stack || error) }));
        """,
        STABLE_KEY,
        MARKER_OFFSET,
        len(MARKER),
    )


def run_transition(
    server: PackageServer,
    url: str,
    previous: Path,
    current: Path,
    binary: str | None,
) -> tuple[dict, dict, dict]:
    driver = webdriver.Firefox(options=firefox_options(binary))
    driver.set_script_timeout(30)
    try:
        server.package_dir = previous
        driver.get(url)
        wait_ready(driver)
        seeded = seed_legacy_save(driver)
        driver.refresh()
        wait_ready(driver)
        stripped = strip_legacy_metadata(driver)
        server.package_dir = current
        driver.refresh()
        wait_ready(driver)
        inspected = inspect_current_release(driver)
        return seeded, stripped, inspected
    finally:
        driver.quit()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("previous_package", type=Path)
    parser.add_argument("current_package", type=Path)
    parser.add_argument("--firefox-binary")
    args = parser.parse_args()

    previous = args.previous_package.resolve()
    current = args.current_package.resolve()
    for package in (previous, current):
        for relative in ("index.html", "emulator/quintra-player.js", "emulator/wasmboy.js", "quintra.gbc"):
            if not (package / relative).is_file():
                parser.error(f"missing {relative} in {package}")

    old_rom = (previous / "quintra.gbc").read_bytes()
    new_rom = (current / "quintra.gbc").read_bytes()
    old_header = old_rom[0x134:0x14F]
    new_header = new_rom[0x134:0x14F]
    if old_header[:16] != new_header[:16] or old_header == new_header:
        raise SystemExit("Expected the same cartridge title with a changed full header")

    with tempfile.TemporaryDirectory(prefix="quintra-sram-negative-") as temp:
        negative = Path(temp) / "current-default-storage"
        shutil.copytree(current, negative)
        player_path = negative / "emulator/quintra-player.js"
        player = player_path.read_text()
        for line in (
            '      cartridgeRamStorageKey: "quintra:mbc5:sram:v1",\n',
            "      cartridgeRamStorageSize: 32 * 1024,\n",
        ):
            if line not in player:
                raise SystemExit(f"Current player is missing expected line: {line.strip()}")
            player = player.replace(line, "", 1)
        player_path.write_text(player)

        server = PackageServer(("127.0.0.1", 0), PackageHandler)
        server.package_dir = previous
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/index.html"
        try:
            seeded, stripped, migrated = run_transition(
                server, url, previous, current, args.firefox_binary
            )
            _, negative_stripped, negative_result = run_transition(
                server, url, previous, negative, args.firefox_binary
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    failures = []
    if seeded["backingBytes"] < LOGICAL_RAM_BYTES or seeded["saveStates"] < 1:
        failures.append("beta24 did not seed RAM and a revision-specific save state")
    if stripped["stripped"] != 1 or stripped["preservedStates"] < 1:
        failures.append("beta24 record was not reduced to metadata-less RAM plus save states")
    if migrated["observed"] != MARKER or migrated["stableMarker"] != MARKER:
        failures.append("beta25 did not restore beta24 cartridge RAM")
    if migrated["saveStatesBeforeProbe"] != 0:
        failures.append("beta24 save states leaked into the beta25 ROM revision")
    if not migrated["stablePresent"]:
        failures.append("beta25 did not create the stable SRAM record")
    if migrated["stableFields"] != ["cartridgeRam", "cartridgeRamSavedAt"]:
        failures.append("stable SRAM record contains fields beyond RAM and capture time")
    if migrated["stableBytes"] != LOGICAL_RAM_BYTES:
        failures.append(f"stable SRAM record is {migrated['stableBytes']} bytes, expected {LOGICAL_RAM_BYTES}")
    if not isinstance(migrated["stableSavedAt"], (int, float)) or migrated["stableSavedAt"] < 0:
        failures.append("stable SRAM record has no valid capture timestamp")
    if migrated["unloadStoragePresent"]:
        failures.append("beta24 unload recovery was not consumed")
    if negative_stripped["stripped"] != 1:
        failures.append("negative control did not create the same metadata-less beta24 record")
    if negative_result["observed"] == MARKER or negative_result["stablePresent"]:
        failures.append("default header-keyed configuration unexpectedly migrated cross-ROM RAM")

    migrated_headers = [entry["header"] for entry in migrated["binary"]]
    if list(old_header) not in migrated_headers or list(new_header) not in migrated_headers:
        failures.append("IndexedDB does not contain distinct old and current header records")

    report = {
        "previousRomSha256": sha256(previous / "quintra.gbc"),
        "currentRomSha256": sha256(current / "quintra.gbc"),
        "headersDiffer": old_header != new_header,
        "seeded": seeded,
        "metadataLessLegacy": stripped,
        "migration": migrated,
        "defaultConfigNegativeControl": {
            "metadataLessLegacy": negative_stripped,
            "markerMigrated": negative_result["observed"] == MARKER,
            "stableRecordPresent": negative_result["stablePresent"],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit("Cross-ROM persistence gate failed: " + "; ".join(failures))
    print("Cross-ROM persistence gate passed")


if __name__ == "__main__":
    main()
