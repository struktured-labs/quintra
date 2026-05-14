#!/usr/bin/env python3
"""
v2.69: STAT-safe viewport BG colorizer - zero flicker on MiSTer

Key changes from v2.68:
- STAT waits RE-ENABLED: AND 0x02 spin before each VRAM access
  Guarantees reads return real tile IDs and writes succeed on MiSTer FPGA.
  v2.68 removed STAT waits for speed → reads returned 0xFF during mode 3
  → wrong palettes written → visible flicker even when stationary.
- ff_filter ON: extra safety layer (skip 0xFF reads → never write wrong palette)
- 5 rows/frame viewport (scroll-insulated)
- BG runs FIRST in combined function (STAT waits handle safety)

Why v2.68 flickered on MiSTer:
  Without STAT waits, ~50% of VRAM ops fail during mode 3 on MiSTer FPGA.
  Reads return 0xFF → palette lookup gives palette 0 → we overwrite
  correct palette with wrong palette → tile flickers between correct/wrong.
  STAT waits eliminate this entirely.

Budget: 160 tiles/frame × ~140T = 22,400T = ~32% (BG only), ~42% total
Convergence: 3.6 frames (0.06s) - fast and flicker-free
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='viewport', rows_per_frame=5, ff_filter=True, stat_safe=True)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")
rom_path = build_rom(config, output)
print(f"Built v2.69: {rom_path}")
print(f"Config: {config.label}")
print(f"Strategy: STAT-safe viewport (5 rows/frame, scroll-insulated)")
print(f"Tiles: 160/frame (5 rows × 32 tiles)")
print(f"STAT safe: YES (mandatory for MiSTer FPGA)")
print(f"0xFF filter: ON (extra safety)")
print(f"Convergence: ~3.6 frames (0.06s)")
print(f"BG budget: ~32%, total ~42%")
