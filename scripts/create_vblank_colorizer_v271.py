#!/usr/bin/env python3
"""
v2.71: STAT-safe viewport, 2 rows/frame - speed-matched to v2.62

Key insight: v2.62 empirically ran 71 STAT tiles at 35% total budget.
That means ~348T per STAT tile (including wait overhead).
v2.69/v2.70 used 128-160 STAT tiles → 45-56% BG → way too slow.

This version: 2 rows/frame = 64 tiles × 348T ≈ 22,272T + overhead ≈ 33% total.
Same speed tier as v2.62, but viewport-focused for faster settling.

Settling: 18 rows / 2 = 9 frames (0.15s) visible area only
  vs v2.62: 1024 tiles / 71 = 14.4 frames (0.24s) full tilemap
  → 38% faster settling at same game speed

No ff_filter needed (STAT waits guarantee valid reads).
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='viewport', rows_per_frame=2, ff_filter=False, stat_safe=True)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")
rom_path = build_rom(config, output)
print(f"Built v2.71: {rom_path}")
print(f"Config: {config.label}")
print(f"Tiles: 64/frame (2 rows × 32) | ~33% total budget (matches v2.62)")
print(f"STAT safe: YES | Settling: 9 frames (0.15s)")
