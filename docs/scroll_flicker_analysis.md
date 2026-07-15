# Scroll Flicker — Root Cause Analysis

User reports "little bit of flickering when scrolling" on real MiSTer
hardware in both v3.00 and v3.01. This document captures the
investigation.

## Phenomenon

During dungeon scrolling, occasional brief flashes of incorrect colors
(typically appearing as blue/colored splotches where floor should be
white, or floor where wall should be gray).

## Root cause: tilemap double-buffering vs bg_sweep coverage

The original game uses both VRAM tilemap regions (0x9800 and 0x9C00)
in a double-buffering scheme for smooth scrolling. LCDC bit 3 selects
which is currently displayed.

mGBA Lua trace during gameplay (LCDC value over time):
```
f981:  LCDC=0x83 bit3=0  →  displayed tilemap = 0x9800
f987:  LCDC=0x8B bit3=1  →  displayed tilemap = 0x9C00
f993:  LCDC=0x83 bit3=0  →  displayed tilemap = 0x9800
...repeats every ~6 frames...
```

The game switches displayed tilemap every ~5-6 frames during normal
gameplay. Each tilemap holds one "page" of the scrolling world.

## bg_sweep targets only the DISPLAYED tilemap

`create_bg_sweep_viewport_gated` computes target base from LCDC bit 3:
```
LDH A,[LCDC]; AND 0x08; RRCA; ADD 0x98
```
- bit 3 clear → target 0x98 (= 0x9800)
- bit 3 set   → target 0x9C (= 0x9C00)

So bg_sweep only covers ONE tilemap per call. The non-displayed
tilemap is left untouched.

## Measured impact

mGBA probe at f1500 (mid-gameplay, normal scrolling):

| Tilemap | Status | Uninit (0xFF) attrs | Non-zero attrs |
|---|---|---|---|
| 0x9800 | Not displayed (LCDC bit 3 = 1) | 34 / 1024 | 120 / 1024 |
| 0x9C00 | DISPLAYED | 4 / 1024 | 77 / 1024 |

The displayed tilemap has 0-4 uninit attrs (bg_sweep keeps it fresh).
The non-displayed one accumulates 28-34 uninit attrs (0xFF = pal 7
default = blue when rendered).

When the game flips LCDC bit 3, the non-displayed tilemap (with
uninit attrs) becomes displayed. For one frame (until bg_sweep catches
up), those uninit tiles render with pal 7 attributes → BLUE.

## Both ROMs have this issue

| ROM | Uninit attrs in non-displayed tilemap |
|---|---|
| v3.01 production | 34 |
| v3.00 FIXED.gb baseline | 28 |

The flicker is a pre-existing characteristic of the bg_sweep
architecture in both ROMs, not a v3.01 regression.

## Potential fix (NOT YET IMPLEMENTED — risk vs reward)

bg_sweep could alternate between the two tilemaps each frame, OR
sweep both per frame. Trade-offs:

**Option A: Alternating sweep (low cost, slower coverage)**
- Each frame: sweep ONE row of either 0x9800 or 0x9C00 (toggle)
- Per-frame cost: same as current (~3K T)
- Full coverage of both tilemaps: 36 frames (~600ms vs current 300ms
  for single tilemap)
- Trade-off: each tilemap gets half the update rate, but neither
  accumulates uninit attrs

**Option B: Dual sweep (high cost, fast coverage)**
- Each frame: sweep one row of 0x9800 AND one row of 0x9C00
- Per-frame cost: ~6K T (double)
- Full coverage of both: 18 frames (same as current)
- Risk: doubles bg_sweep cycle cost — may push handler past VBlank
  on hardware

**Option C: Detect tilemap switch and force re-sweep**
- Track LCDC bit 3 state across frames
- On switch: prioritize the newly-displayed tilemap for accelerated sweep
- Complex; might still leave brief flicker on switch

Recommend deferring this work — it's a pre-existing limitation that
affects both ROMs equally, and any fix has risk of regressing the
recently-stabilized CRAM write timing.

## Self-verification infrastructure used

- `/tmp/scroll_offscreen.lua` — full tilemap attr dump
- `/tmp/lcdc_trace.lua` — LCDC bit 3 transitions over time
- `/tmp/scroll_diff.lua` — per-frame tilemap diff during scroll
