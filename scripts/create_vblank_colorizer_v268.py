#!/usr/bin/env python3
"""
v2.68: Fast viewport BG colorizer - 2-frame visible sweep

Key changes from v2.67:
- 9 rows/frame (was 5) → full visible area in 2 frames (33ms, imperceptible)
- ff_filter OFF: STAT-wait-free reads may return 0xFF during mode 3,
  but writes also fail during mode 3, so no corruption. Tile 0xFF maps
  to palette 0 (floor), which is the correct default. Removing the filter
  saves 16T per tile (5 bytes less code).
- Combined order: Palette -> OBJ -> DMA -> BG (BG extends into rendering)

Budget: 288 tiles/frame × ~92T = 26,496T = ~37.7% (BG only)
Convergence: 2 frames (0.033s) - below human visual perception threshold
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='viewport', rows_per_frame=9, ff_filter=False)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")
rom_path = build_rom(config, output)
print(f"Built v2.68: {rom_path}")
print(f"Config: {config.label}")
print(f"Strategy: viewport (9 visible rows/frame, 2-frame sweep)")
print(f"Tiles: 288/frame (9 rows × 32 tiles)")
print(f"Convergence: ~2 frames (0.033s)")
print(f"0xFF filter: OFF (saves 16T/tile, no corruption risk)")
