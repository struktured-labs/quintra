#!/usr/bin/env python3
"""
v2.70: STAT-safe viewport, speed-optimized

Changes from v2.69:
- 4 rows/frame (was 5) → ~23% BG budget (was 32%)
- ff_filter OFF: redundant when STAT waits guarantee valid reads.
  Saves 16T per tile (INC+JR Z+DEC removed from inner loop).
- Total budget: ~33% (BG 23% + OBJ/pal/DMA ~10%)
  v2.67 at ~33% had no game speed complaints.

Settling: 4.5 frames (0.075s) - still fast, no perceptible delay
Flicker: ZERO (STAT waits guarantee all VRAM ops succeed on MiSTer)
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='viewport', rows_per_frame=4, ff_filter=False, stat_safe=True)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")
rom_path = build_rom(config, output)
print(f"Built v2.70: {rom_path}")
print(f"Config: {config.label}")
print(f"STAT safe: YES | ff_filter: OFF (redundant with STAT)")
print(f"Tiles: 128/frame (4 rows × 32) | Settling: 4.5 frames (0.075s)")
print(f"Budget: ~23% BG + ~10% OBJ = ~33% total")
