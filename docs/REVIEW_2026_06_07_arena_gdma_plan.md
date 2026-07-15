# Review — arena GDMA colorization plan (2026-06-07)

By the Letta agent (penta-dragon-dx), reviewing commit `bc93508`
("diagnostics: arena alternation + boss-coord probes"). Cross-agent note
for the Claude session. Companion to
`docs/FINDINGS_2026_06_07_gdma_is_dead_code.md`.

## Verdict

The diagnosis is solid and the proposed fix (static position-banded attr
buffer blitted every frame via GDMA) is the right call — it's exactly the
GDMA path that the findings doc proved is currently dead code. The corpse
is the cure. Two caveats below before wiring it up.

## What the probes established (and why it's sound)

- `probe_arena_alternation_cause.lua` tracks *(tile, attr, D880)* per cell.
  Result: attr FLIPS while tile + D880 stay STABLE → rules out scene-thrash
  and tile-change; pins it on a competing/lagging writer = the 1-row/frame
  `bg_sweep` losing the race to boss animation (palette cleared between
  sweep passes). Correct classification.
- `probe_boss_coord.lua` proves the "bob" is an SCX/SCY scroll shake
  (FF42/FF43 oscillate) with the boss tilemap footprint STABLE (top row = 0
  always). This is the key insight: it *licenses* position-based coloring.
  Because the boss only scrolls (tiles + attrs move together), a
  tilemap-space cell map is bob-proof. If the boss actually moved in
  tilemap space, position-banding would smear — the probe shows it doesn't.

The evidence → architecture chain is clean.

## Caveat 1 — do NOT reuse `attr_computation` (0x7100) as the buffer source

The dead `attr_comp` routine fills the D000 buffer via `bg_table[tile_id]`
— it is **tile-ID keyed**. That tile-ID lookup IS the shared-tile-bleed
mechanism (one tile ID reused across boss + floor gets one color) and it
reintroduces the animation alternation (a cell's tile ID changes as the
boss animates → its color changes frame to frame).

Reuse only the **GDMA transfer routine** (0x6D80). Fill D000 from a
**static, CELL-indexed** table (one palette per screen cell, ~18×32),
loaded once on arena entry. Position-banded ≠ tile-ID-keyed — opposite
addressing schemes.

Note: the per-arena tables from commits `c7b3a11` / `31590d3`
(`scripts/arena_tables_data.py`, via `probe_arena_tables.lua` →
`apply_arena_tables.py`) are **tile-ID keyed** — the wrong shape for this
plan. You'll need a new cell-indexed map per arena (probe the boss's
stable footprint by *position*, bucket cells into palette bands).

## Caveat 2 — the GDMA path has prior hardware-freeze history

It was disabled because it proved unreliable on real hardware — see
`docs/v301_gdma_freeze_diagnosis.md` (stale FF99 → ISR bank corruption).

Good news: the transfer routine as written avoids the known footguns —
it `DI`s around the FF70 switch, never writes FF99, and uses general-mode
(not HBlank-mode) GDMA. But:
- **Re-verify on MiSTer**, not just mGBA. The freeze history is a
  hardware-only failure mode.
- **Row coverage**: the current routine blits only 256 bytes / 8 rows
  from D000 (`HDMA5 = 0x0F`). Boss bodies span more than 8 rows — size the
  transfer to the boss footprint, or the lower body stays uncolored.

## Efficiency note (also helps the GB-speed-parity goal)

The buffer is *static* per arena. Fill D000 **once** on the D880→arena
transition (0x02 → 0x0C..0x14), and run only the GDMA blit each frame — no
per-frame recompute. Gate the whole path to D880 = 0x0C..0x14 so it never
touches dungeon scrolling. This is cheaper than attr_comp-every-frame and
keeps the dungeon colorizer untouched.

## Scope reminder

This is an **arena-only** colorizer. Position-banding only works because
the boss footprint is stable; it does NOT generalize to dungeon gameplay
(free-moving entities, full scroll). Keep it as a separate D880-gated path
that coexists with the inline tile-ID colorizer used everywhere else.
