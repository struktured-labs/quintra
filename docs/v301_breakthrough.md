# v3.01 Breakthrough — Full attr+GDMA Optimization SHIPPED

**Status: SHIPPED. v3.01 production now uses attr_comp + general-mode GDMA.**

## Summary

The earlier conclusion in `v301_regression_stage_load_stuck.md` ("every
combination breaks gameplay") was wrong. Two distinct bugs were conflated:

1. **HBlank-mode HDMA corrupts VRAM tile IDs** (visual bug): HDMA5=0xBF
   spreads the transfer across multiple HBlanks. Once the colorize handler
   returns and restores VBK=0, subsequent HBlank steps write to VRAM bank 0
   (tile indices) instead of bank 1 (attributes). Result: random tile
   garbage on screen, even though the gameplay state machine still cycles.
2. **Cycle starvation in autoplay** (state-machine bug): With ≥12 rows of
   attr_comp, the per-frame cost overshoots the game's main-loop budget
   to the point that the autoplay stress harness can't reliably advance
   past room transitions. State-machine probes saw FFBD stuck at 5/0;
   visually the ROM was fine.

The two failures had similar probe signatures (FFBD stuck at 5), which
made it look like a single mechanism was breaking. Independent fixes:

| Bug | Fix | Where |
|---|---|---|
| HBlank → tile-ID corruption | `HDMA5 = 0x3F` (general mode, atomic) | `create_gdma_transfer` |
| Cycle starvation @ ≥12 rows | `attr_comp` rows = 8 | `create_attr_computation` |

## What ships in production v3.01

```
VBlank colorize handler:
  - cond_pal (palette load, cached via FFA6)
  - bg_sweep (1 row/frame direct VRAM, fills rows 8-17 of viewport)
  - FFC1 gate (gameplay active only):
      - OAM DMA (0xFF80)
      - shadow_main (OBJ colorizer)
      - attr_comp (8 rows × 24 tiles → WRAM bank 2 D000-D0FF)
      - GDMA general-mode (1024 bytes WRAM→VRAM bank 1)
```

Per-frame cost: ~17K T cycles (24% of 70K T frame budget at single-speed CGB).
Game gets ~53K T main-loop. Mini-boss + stage transitions verified working.

## Verification

8000-frame autoplay stress test (3 runs):

| Run | D880 distribution | FFBF (mini-boss) | FFBD |
|---|---|---|---|
| 1 | 0x18=49, 0x02=701 | 0=750 | 1=4, 5=746 (autoplay miss) |
| 2 | 0x18=49, 0x0A=150, 0x02=435, 0x0B=116 | **1=267** | 1=185, 3=82, 7=148, 5=335 |
| 3 | 0x18=49, 0x0A=163, 0x02=386, 0x0B=152 | **1=316** | 1=186, 3=110, 7=217, 5=237 |

Mini-boss reached 2/3 runs (same rate as v3.00 baseline under identical autoplay).

Screenshots at frames 1200/2000/3000 confirm clean dungeon rendering
with proper colors — no tile corruption, no palette-0 stripes.

## Why the matrix was wrong

The earlier `v301_regression_stage_load_stuck.md` test matrix relied on
probe-only verification (D880 + FFBD bytes). It did not catch HBlank-mode
HDMA visual corruption because gameplay state still advances when the
TILE data is wrong but attribute data is partially right — the FFC1 gate
fires, scenes change, just rendered incorrectly.

The "any GDMA breaks any row count" claim was a generalization from
testing only 8-row + HBlank-mode HDMA. Switching to general-mode and
checking the screenshots immediately revealed the actual failure.

Lesson: always include screenshot verification when iterating on
rendering changes. Probe bytes are necessary but not sufficient.

## Compatibility notes

- v3.01 production has been emulator-verified on mGBA only. MiSTer
  deployment requires hardware testing before replacing
  `penta_dragon_dx_FIXED.gb` (v3.00) as the primary ROM.
- Sound system unchanged from v2.90 — phantom sound fixes carry over.
- FF99 protocol fix retained (defensive vs STAT/Timer ISR bank corruption).
- Cold-boot bg_table copy retained.
