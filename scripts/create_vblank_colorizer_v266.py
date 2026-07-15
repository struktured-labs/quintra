#!/usr/bin/env python3
"""
v2.66: Fast convergence BG colorizer with palette-first ordering

Key changes from v2.65:
- Strategy: 'none' (no LY gate) with 0xFF filter for hardware-level mode 3 safety
- 255 tiles/frame iteration count (vs 40 in v2.65)
  - VBlank: ~25 tiles write successfully (always safe)
  - HBlank: ~70+ tiles write successfully (0xFF filter skips mode 3)
  - Full tilemap sweep in ~6-10 frames (0.1-0.17s) vs 41 frames (0.68s) in v2.65
- Combined order: Palette -> OBJ -> DMA -> BG (palette writes safe in VBlank)

Why this is hardware-safe despite no LY gate:
- VRAM reads during mode 3 return 0xFF on real GBC hardware
- ROM lookup table maps 0xFF -> 0xFF (skip marker)
- 0xFF filter skips the entire write block (including VBK switches)
- VBK only switches to 1 during HBlank/VBlank/OAM scan = safe
- VBK=1 window is only 7 machine cycles, fits in any safe window

Convergence comparison (emulator test, visible tiles):
  v2.65 ly_40t_ff:  frame 70 = 46 wrong, frame 200 = 8 wrong (NEVER settles)
  v2.66 none_255t:  frame 70 = 1 wrong,  frame 140 = 0 wrong (perfect)
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='none', tiles=255, ff_filter=True)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")
rom_path = build_rom(config, output)
print(f"Built v2.66: {rom_path}")
print(f"Config: {config.label}")
print(f"Strategy: none (0xFF filter for mode 3 safety)")
print(f"Tiles: 255/frame (auto-calibrates via 0xFF filter)")
print(f"Combined order: Palette -> OBJ -> DMA -> BG")
