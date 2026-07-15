#!/usr/bin/env python3
"""Small, deterministic ROM/home-bank budget gate for conference builds."""
import re, sys
from pathlib import Path

stem = Path(sys.argv[1] if len(sys.argv) > 1 else "rom/working/quintra")
rom = stem.with_suffix(".gbc").read_bytes()
text = stem.with_suffix(".map").read_text()
areas = []
for m in re.finditer(r"^(_CODE|_HOME|_GSINIT|_GSFINAL|_INITIALIZER|_LIT|_BASE)\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s+=", text, re.M):
    areas.append((m.group(1), int(m.group(2), 16), int(m.group(3), 16)))
home_end = max((addr + size for _, addr, size in areas), default=0)
headroom = 0x4000 - home_end
banks = len(rom) // 0x4000
enemy_match = re.search(r"#define N_ENEMIES\s+(\d+)", Path("src/generated/enemies.h").read_text())
stage_match = re.search(r"#define N_STAGES\s+(\d+)", Path("src/generated/stages.h").read_text())
enemies = int(enemy_match.group(1)) if enemy_match else "?"
stages = int(stage_match.group(1)) if stage_match else "?"
print(f"[budget] ROM={len(rom)//1024} KiB ({banks} banks), home_end=0x{home_end:04X}, home_headroom={headroom} bytes")
print(f"[budget] gameplay caps: 32 entities, {enemies} enemies, boss HP <=255, {stages} stage themes")
if home_end > 0x3E00:
    raise SystemExit("[budget] FAIL: less than 512 bytes remain in always-mapped bank 0")
if banks > 8:
    raise SystemExit("[budget] FAIL: ROM grew beyond 128 KiB conference target")
print("[budget] OK")
