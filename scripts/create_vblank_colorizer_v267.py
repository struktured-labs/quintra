#!/usr/bin/env python3
"""
v2.67: Viewport BG colorizer - scroll-insulated architecture

Key changes from v2.66:
- Strategy: 'viewport' - only colors the 18 currently visible rows (from SCY register)
- 5 rows/frame × 32 tiles/row = 160 tiles/frame
- Full visible area sweep in 3.6 frames (0.06s) vs ~10 frames (0.17s) in v2.66
- Scroll-insulated: when screen scrolls, visible rows change → colorizer follows
- All 32 columns colored per row → SCX changes handled for free
- ~23% frame budget (BG only) vs ~46% in v2.66 → game runs faster
- 0xFF filter for mode 3 safety on MiSTer hardware

Why this is scroll-insulated:
- Old approach: sweep tiles 0→1023 linearly. New tiles at scroll edge wait for full sweep.
- New approach: read SCY, compute visible rows, color only those. Scroll changes the
  visible rows → colorizer automatically targets the new area. Max 4 frame latency.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='viewport', rows_per_frame=5, ff_filter=True)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")
rom_path = build_rom(config, output)
print(f"Built v2.67: {rom_path}")
print(f"Config: {config.label}")
print(f"Strategy: viewport (5 visible rows/frame, scroll-insulated)")
print(f"Tiles: 160/frame (5 rows × 32 tiles)")
print(f"Convergence: ~3.6 frames (0.06s)")
print(f"Combined order: Palette -> OBJ -> DMA -> BG")
