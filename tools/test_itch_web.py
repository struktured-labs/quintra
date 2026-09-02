#!/usr/bin/env python3
"""Static acceptance gates for the generated itch.io HTML package."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"itch package check failed: {message}")


root = Path(sys.argv[1]).resolve()
required = (
    "index.html",
    "quintra.gbc",
    "quintra.sha256",
    "build.json",
    "emulator/wasmboy.js",
    "emulator/quintra-player.js",
    "emulator/quintra-player.css",
    "licenses/GPL-3.0-or-later.txt",
    "licenses/WASMBOY-LICENSE.txt",
    "licenses/QUINTRA-LICENSE-MAP.md",
    "licenses/THIRD-PARTY-NOTICES.md",
    "media/cover.png",
)

for relative in required:
    if not (root / relative).is_file():
        fail(f"missing {relative}")

files = [path for path in root.rglob("*") if path.is_file()]
if len(files) >= 1000:
    fail(f"too many files ({len(files)})")

total_size = sum(path.stat().st_size for path in files)
if total_size >= 450 * 1024 * 1024:
    fail(f"extracted package is too large ({total_size} bytes)")

for path in files:
    relative = path.relative_to(root).as_posix()
    if path.stat().st_size >= 180 * 1024 * 1024:
        fail(f"file is too large: {relative}")
    if len(relative) >= 220:
        fail(f"path is too long: {relative}")

build = json.loads((root / "build.json").read_text())
rom_hash = hashlib.sha256((root / "quintra.gbc").read_bytes()).hexdigest()
if build["romSha256"] != rom_hash:
    fail("build.json ROM hash does not match packaged ROM")

emulator_hash = hashlib.sha256((root / "emulator/wasmboy.js").read_bytes()).hexdigest()
if build["emulatorSha256"] != emulator_hash:
    fail("build.json emulator hash does not match packaged emulator")

sha_record = (root / "quintra.sha256").read_text().split()[0]
if sha_record != rom_hash:
    fail("quintra.sha256 does not match packaged ROM")

index = (root / "index.html").read_text()
if "__QUINTRA_WEB_VERSION__" in index:
    fail("web version placeholder was not replaced")
if f'emulator/quintra-player.js?v={build["version"]}' not in index:
    fail("player script URL is not cache-busted with the build version")
if f'emulator/wasmboy.js?v={build["version"]}' not in index:
    fail("emulator script URL is not cache-busted with the build version")
if f'emulator/quintra-player.css?v={build["version"]}' not in index:
    fail("player stylesheet URL is not cache-busted with the build version")
references = re.findall(r'(?:src|href)="([^"]+)"', index)
for reference in references:
    if reference.startswith(("http://", "https://", "//")):
        fail(f"remote asset reference in index.html: {reference}")
    target = reference.split("#", 1)[0].split("?", 1)[0]
    if target and not (root / target).is_file():
        fail(f"missing referenced asset: {reference}")

for relative in ("index.html", "emulator/quintra-player.js", "emulator/quintra-player.css"):
    text = (root / relative).read_text()
    if re.search(r'(?:src|href)=["\'](?:https?:)?//', text):
        fail(f"remote executable asset in {relative}")

if "width=\"160\" height=\"144\"" not in index:
    fail("canvas does not declare native 160x144 dimensions")

print(f"itch package checks passed: {len(files)} files, {total_size} bytes")
