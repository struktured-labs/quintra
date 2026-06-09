# Findings — arena alternation root cause #1: sweep/inline-hook table disagreement (2026-06-08)

Branch `wip-arena-position-sweep`. First concrete win on the "no alternation"
goal, found by reading the two arena attr-writers and confirmed by an A/B probe.

## Root cause

Two routines write BG attributes in a boss arena, and they were reading
**different palette tables**:

- **Inline hook @ bank1:0x42A7** — `LD B,0xDA` then `[BC]` → reads WRAM
  `0xDA00[tile]`. `scene_detect` (teleport build) copies the *per-arena* table
  into `0xDA00` on every scene change, so the hook colors the boss correctly.
- **bg_sweep @ bank13:0x6CD0** — built by `create_bg_sweep_viewport_gated(bg_table_addr=0x7000, …)`
  → reads the **ROM dungeon table** `0x7000[tile]`, *always*, even in arenas.

In an arena, for a boss tile, the hook writes the arena-band palette while the
sweep writes the dungeon palette. The sweep cycles one row per frame (DF04
0..17, an 18-frame cycle), so every boss cell got overwritten with the dungeon
value once per cycle and re-colored by the hook in between → a steady
frame-to-frame palette flip. This is the "attr flips while tile stays stable"
the earlier `probe_arena_alternation_cause.lua` saw.

## Fix (Phase 0)

`build_v301_teleport.py` re-patches `0x6CD0` after the base build, rebuilding
the sweep with `bg_table_addr = 0xDA00` so it reads the **same per-scene WRAM
table** the inline hook uses. `scene_detect` keeps `0xDA00` current in every
scene, so the dungeon is unaffected (there `0xDA00` == the dungeon table).

Isolated to the teleport build; the production base ROM is untouched.

## A/B evidence (full-screen probe, Shalamar, 400 collected frames)

`scripts/diagnostics/probe_arena_alt_fullscan.lua` scans all 360 boss-region
cells (rows 0..17, cols 0..19) every frame and counts `flip_stable` (attr
palette changed while tile ID stayed the same).

| build    | flip_stable | tile_changed | distinct flip cells |
|----------|-------------|--------------|---------------------|
| baseline |     606     |     948      |        137          |
| fixed    |     210     |    1170      |         71          |

Baseline top flippers (r1-2 c13-18) flipped exactly **18×/400 frames** = once
per sweep cycle — the smoking gun. (`tile_changed` delta is run-to-run
animation-phase variance; the fix only touches attr writes, not tiles.)

## Interpretation

Halving alternation by unifying the table proves the disagreement was a major
source. The **residual 210 flips / 71 cells** are at boss-body edges at
animation cadence (~8-11×/400 frames), not the sweep beat. They are inherent to
**tile-ID keying**: a cell's tile flips between boss-part and background as the
boss animates (and the hook reads the C1A0 tile shadow while the sweep reads the
VRAM tile, so the two can disagree for a frame even on the same table).

Tile-ID keying cannot reach zero. The next step is the **position map**
(fixed per-cell palette, tile-independent) — see the handoff doc. Phase 0 is a
standalone improvement worth keeping regardless.
