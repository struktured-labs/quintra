# Findings for the Claude session — "v3.01 GDMA" is a misnomer (2026-06-07)

Written by the Letta agent (penta-dragon-dx) while absorbing this repo.
Cross-session note so the Claude session and I share the same ground truth.

## TL;DR

The production build `scripts/build_v301_gdma.py` does **NOT** use GDMA.
It compiles a GDMA routine and a 1024-byte `attr_computation` routine into
bank-13 ROM, but **neither is ever called**. They are dead code. What
actually colorizes the screen is the v3.00-style inline tile+attr hook at
`bank1:0x42A7`, plus `cond_pal`, an attr-cleaner, an ungated `bg_sweep`,
and the OBJ colorizer. The "GDMA" name is historical/aspirational.

## How to verify it yourself (reproducible)

```bash
cd /home/struktured/projects/penta-dragon-dx-claude
python3 scripts/build_v301_gdma.py                 # reproduces FIXED.gb
md5sum rom/working/penta_dragon_dx_v301.gb rom/working/penta_dragon_dx_FIXED.gb
# both == dd617b7e83d1fef30b07d70be0a13586

python3 - <<'PY'
rom = open('rom/working/penta_dragon_dx_v301.gb','rb').read()
for name, patt in [('CALL gdma 0x6D80', b'\xCD\x80\x6D'),
                   ('CALL attr_comp 0x7100', b'\xCD\x00\x71')]:
    i = rom.find(patt)
    print(name, '->', hex(i) if i >= 0 else 'NOT FOUND')
PY
# CALL gdma 0x6D80 -> NOT FOUND
# CALL attr_comp 0x7100 -> NOT FOUND
```

In the source: `build_v301_gdma.py` only ever does `w(gdma_addr, ...)` and
`w(attr_comp_addr, ...)` (writes the bytes into ROM). There is no
`CALL gdma_addr` / `CALL attr_comp_addr` emitted in the colorize handler
(lines ~515-595). The in-source comments already admit it, e.g. line ~494:
"Since attr_comp + GDMA aren't called in the warm path, WRAM bank 2 is
never read."

## What actually ships (the real warm path, colorize handler @ bank13:0x6E00)

Each VBlank:
1. save VBK, VBK=0
2. cold-boot init once (DF02 magic byte): copy `bg_table` ROM→WRAM 0xDA00
3. `cond_pal` — cached palette load (~200T, skips when hash unchanged)
4. attr-cleaner — clears uninit `0xFF` attrs in BOTH 0x9800/0x9C00 tilemaps,
   one row/frame for 32 frames after boot, then a ~12T no-op
5. FFC1 gate (gameplay only): `bg_sweep` (1 row/frame, ungated so it also
   runs on title) → `shadow_main` (OBJ colorizer) → OAM DMA at FF80
6. restore VBK, RET

Plus, inside the game's own tilemap copy (NOT the VBlank handler), the
inline hook at `bank1:0x42A7` (117 bytes) writes:
- tile phase: VBK=0, STAT wait for mode 0, 4 tile writes `[DE]->[HL+]`
- attr phase: VBK=1, **its own** STAT wait for mode 0, 4 attr writes via
  `[BC]` lookup (`LD A,[DE]; INC DE; LD C,A; LD A,[BC]; LD [HL+],A`)
  where B=0xDA (WRAM bg_table high), so attr = `bg_table[tile_id]`.
- 24 rows × 6 groups = 144 groups, each paying TWO STAT mode-0 waits.

So: **shipping build == v3.00 inline hook + ungated bg_sweep + attr-cleaner.**

## Performance implication (relevant to "run as fast as the GB version")

`docs/v301_performance.md` claimed ~53,000 T-cycles / 76% of the frame
budget, dominated by `attr_computation` (24 rows × ~2000T). **That figure
is for the disabled path and is wrong for what ships.** The real handler is
much lighter. The dominant cost-over-vanilla is the inline hook's **second
(attr-phase) STAT mode-0 wait per group** — vanilla waits once per group
(tiles only); we wait twice. That dual-wait is the main GB-speed-parity
lever, not attr_computation.

Suggested perf approach (measure first):
1. Build a precise mGBA cycle probe around the `0x42A7` tile-copy (the
   existing `scripts/probes/vblank_cycles.lua` is crude DIV/LY sampling).
2. Then target the attr-phase STAT wait: e.g. interleave attr writes into
   the existing tile-phase mode-0 window, or write attrs without a second
   wait where the mode-0 budget allows. Re-verify with the 5 probes.

## Docs corrected in this pass

- `CLAUDE.md` — "Current production" now says v3.01 (was v3.00) + a naming
  caveat; build-pipeline section now names `build_v301_gdma.py` as current.
- `docs/v301_performance.md` — correction banner at top + the 53K T table
  is now marked "DISABLED attr_comp+GDMA path — NOT shipping".

## Not touched / still true

- The 5 probes in `scripts/probes/` and the phantom-sound / DI-window rules
  remain the law. Don't write FF99 from hooks; keep DI windows short.
- Per-arena bg_table work lives in `scripts/build_v301_teleport.py`
  (separate teleport ROM, not the production build).
