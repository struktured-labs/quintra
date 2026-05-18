# v3.01 GDMA Freeze Diagnosis (2026-05-17, incomplete)

## Status: BLOCKED on FF70 freeze. Production stays on v3.00.

## What v3.01 was trying to do

Replace v3.00's dual-STAT-wait inline hook (which doubled tile-copy time ->
~2x game slowdown) with:

1. **Tile-only inline hook** (single STAT wait, vanilla speed) at bank 1:0x42A7
2. **VBlank attr_computation**: read tiles from `0xC1A0`, look up `bg_table`,
   write 1024-byte attr buffer to **WRAM bank 2** (`0xD000-0xD3FF`)
3. **GDMA transfer**: hardware DMA from WRAM bank 2 to VRAM tilemap VBK=1

## What worked

- Tile-only inline hook (56 bytes, down from 117) — proven booting via
  `scripts/build_v301_minimal.py` (just inline-hook swap, v3.00 colorize handler).
  Game runs, but BG colors regress because nothing writes attrs inline anymore.
- bg_sweep with the internal FFC1 gate stripped — fills title-screen attrs
  slowly (~18 frames for full coverage). Yellow gold items show up correctly.
- GDMA register programming verified static-correct (HDMA1-5 writes,
  LCDC bit 3 check for `0x9800` vs `0x9C00` tilemap target).
- All 31 vanilla CALL/JP targets inside `0x42A8-0x436D` confirmed dead-code
  paths — wiping them with NOPs doesn't affect boot.

## What freezes (the blocker)

**Any FF70 write to 0x02 in our code freezes the game.** Specifically:

1. **Cold-boot bank-2 zeroing** (originally `DI; FF70=2; zero 1024 bytes; FF70=1; EI`):
   100% white screen from boot, regardless of whether the DI window is one
   24K-T-cycle block or chunked into 4 × 6K-T windows.
2. **attr_computation outside FFC1 gate** (FF70=2 every frame): 100% white
   screen from boot.
3. **attr_computation inside FFC1 gate** (FF70=2 only during gameplay):
   game boots OK, title shows colors via bg_sweep, but freezes at the
   high-score-screen → first-level transition (the moment `FFC1=0 → 1`).

Removing all FF70 writes from attr_computation (so it writes directly to
bank 1 `0xD000-0xD3FF`, corrupting game data) **also** white-screens,
but that's expected — bank 1 in that range holds game state.

## What we ruled out

- **DF05 collision**: vanilla has zero accesses to `0xDF05`. Safe.
- **Game writing FF70**: zero static `LDH [FF70], A` or `LD [FF70], A`
  instructions in vanilla code. All 12 `E0 70` byte hits are in tile-graphics
  data in banks 8-12, not in executable code.
- **Game reading FF70**: 2 `F0 70` hits in bank 0 (`0x2743`, `0x2758`)
  are inside what looks like graphics data being misinterpreted as code.
- **Stack leak in attr_computation**: original implementation had an extra
  outer `PUSH AF` per chunk that was never popped (8 bytes/frame leak).
  Fixed — the leak alone wasn't the cause anyway, because the freeze
  manifests even on the FIRST FFC1=1 frame.
- **JR/JP offset bugs**: verified all forward and back jumps in the
  colorize handler, GDMA, and attr_computation by hex-tracing the ROM.
- **DI window length**: per-chunk DI window in attr_computation is ~6100T
  (under 7000T Timer-ISR ceiling), 8 chunks per call. Cold-boot zero
  windows are similar after chunking.

## Hypotheses for the FF70 freeze (next session)

1. **mGBA bug**: emulator might not correctly maintain FF70=2 state across
   DI/EI boundaries, or might not handle GDMA source through bank 2.
   Test: hardware verification on MiSTer.
2. **CGB hardware quirk**: writing FF70=2 might affect some hidden register
   or have a timing requirement we're missing. Pan Docs doesn't mention any.
3. **STAT interrupt vector**: the game has a STAT handler at `0x0853` (via
   `0x0048: JP 0x0853`). If our DI windows block STAT and the game's main
   loop depends on STAT firing at specific scanlines, init might stall.
   But this wouldn't explain instant freeze at FFC1=1 transition.
4. **Self-modifying timing**: when FFC1=0 → 1, the game might do specific
   work that's sensitive to VBlank handler runtime. Our attr_computation
   adds ~50K T-cycles to the VBlank handler vs ~3K previously.

## Suggested debugging path

1. Build a v3.01 that writes FF70=2, immediately FF70=1 (no other work)
   in the warm path, and check if THAT freezes. Isolates the FF70 op itself.
2. If FF70 freezes alone, suspect mGBA or CGB hardware quirk. Test on MiSTer.
3. If FF70 alone doesn't freeze, the issue is in the work between FF70=2
   and FF70=1 (i.e., something in attr_computation, even though it only
   touches bank 2 D000-D2FF + bank 0 C1A0 + ROM 0x7000).
4. Consider abandoning bank 2: find a 1KB region in bank 1 that's truly
   unused. Static analysis shows max 306-byte free gap in `0xCAE9-0xCC07`
   and `0xCECE-0xD000`. A more thorough dynamic-trace analysis on a
   long gameplay session might reveal a larger safe region.

## Current production

- **`rom/working/penta_dragon_dx_FIXED.gb`** = v3.00 (tag `colorize-v3.00-inline-hook`).
  2x slow tile-copy, but correct attrs and no freeze.
- **`scripts/build_v301_gdma.py`** = current state. Inline hook simplified
  (tile-only, vanilla speed), bg_sweep ungated for title, attr_computation
  + GDMA built but SKIPPED in the colorize handler pending the FF70 freeze
  fix. Boots, but scroll-edge artifacts return during gameplay because
  bg_sweep alone is too slow (1 row/frame, ~18 frames for full coverage).
