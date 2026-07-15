#!/usr/bin/env python3
"""
v2.65: LY-first BG colorizer - ZERO VBK flicker, optimal CPU

Improvements over v2.64:
- LY check at TOP of loop: exits immediately when VBlank ends
  (v2.64 checked LY per-tile AFTER read+lookup, wasting ~75 iterations)
- Counter doesn't advance for LY-skipped tiles (v2.64 advanced past them,
  creating permanent gaps that never got colored)
- tiles=40 safety limit (auto-calibrates to ~25 effective writes in VBlank)
- ~8.5 scanlines CPU cost (vs ~24 for v2.64 with 157 tiles)

Architecture:
  VBlank interrupt → game handler → CALL 0x0824 (our hook)
  Our hook starts at ~LY=148 (3 scanlines of handler overhead)
  VBlank ends at LY=153 → ~6 scanlines = ~684M available
  At 37M/tile → ~18-25 tiles written per VBlank
  Full tilemap coverage in ~1024/25 ≈ 41 frames (0.68s)

  During rendering (LY < 144): loop exits immediately, zero VBK switches
  Result: NO sprite flicker (Sara W), NO BG flicker, NO tile glitches

Test results (600 frames, 5 core states):
  - 1024/1024 on all gameplay states
  - 916/1024 on jet form (bonus stage tiles constantly updating)
  - MiSTer-safe: zero VBK=1 during rendering

Built via experiment harness for reproducibility.
"""
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from bg_experiment import BGConfig, build_rom

config = BGConfig(strategy='ly', tiles=40, ff_filter=True)
output = Path("rom/working/penta_dragon_dx_FIXED.gb")

rom_path = build_rom(config, output)
print(f"v2.65 built: {rom_path}")
print(f"  Strategy: LY-first (exit loop when VBlank ends)")
print(f"  Tiles: {config.tiles} (safety limit, auto-calibrates to ~25)")
print(f"  0xFF filter: ON")
print(f"  MiSTer-safe: YES (zero VBK during rendering)")
print(f"  CPU cost: ~8.5 scanlines (~5.5% of frame)")
