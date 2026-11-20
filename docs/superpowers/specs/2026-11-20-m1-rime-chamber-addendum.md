# M1 implementation addendum — Rime chamber (Rime Pipes + Stone Jagger)

Parent spec: `2026-11-19-ultima-puzzle-depth.md` (PR #149, branch
`spec/ultima-puzzle-depth`). This addendum records what M1 actually ships and
where it deliberately differs from the spec text.

## Scope

One tiny **optional** chamber in **Verdant Hollow** (stage 2, the dungeon
before the Ember Conduit floor). It teaches exactly two things:

1. **Rime Pipes** — a room-local freeze-all charge (Normal 45 beats ≈ 3 s,
   Easy 56 beats). Taken from a pedestal, used from the Pack TOOL row.
2. **Stone Jagger** — an invincible roamer. It never flashes, has no weapon
   exceptions, and must be frozen or routed around.

## Placement

* Cell: `rime_pick_cell()` — the deepest Verdant Hollow cell (scanning
  `size-4 → 1`) that is not the entry, cache, Veil host, a landmark
  (0,2,5,8,11,15,17,23), a `%6==0` Law cell, or a mission role. If an ambient
  Law altar owns that cell the floor has **no** chamber (no fallthrough, so
  `quintra_topology.rime_cell_candidates()` mirrors it exactly).
* Needs a wide 31x31 field; otherwise (or if a non-trivial pickup sits in
  the footprint) the room stays ordinary.
* Geometry: a walled 9x14 pocket at world tiles x21–29, y15–28 (south-east
  corner, away from all four doors). The entrance is a 2-tile gap in the
  chamber's west wall (rows 24–25), always open, with a floor apron and a
  2-tile corridor carved west to the central N–S trail (x9–10), so it can
  never open into a pillar-sealed pocket.

```
#########   vault: goal plates SS, vault pedestal at (1,2)
#.......#
#....SS.#
#.......#
######..#   vault gap
#.......#   Jagger lane (rows 5-6)
#.......#
#..######   foyer gap
#.......#   foyer pedestal at (5,8)
........#   entrance (west, rows 9-10)
........#
#.......#   reset plate at (1,11)
#.......#
#########
```

## Play

The Jagger patrols its lane and, while the hero is inside, shadows the
hero's x at hero speed, so it always blocks whichever gap you approach.
Take the foyer charge, step to the foyer gap, use **PIPES** from the Pack,
walk through the frozen (harmless) statue to the vault and stand on the goal
plates. Reward: one physical Pack tool charge (same formula as other puzzle
rooms) and `dungeon_puzzles` bit 5 (`RUN_RIME_SOLVED_BIT`). The vault
pedestal re-arms, so the vault is never a trap.

## Reset (no softlocks)

* **Pack → TOOL → RESET ROOM** (always listed while the chamber is live,
  works while pinned, never hold-SELECT) and the **entrance plate** both
  call `rime_reset()`.
* Restores floor-local state only: Jagger to lane centre, charge and freeze
  cleared, hero to the entrance with ≥45 i-frames, Jagger held 30 frames.
  HP, MP and run Pack charges spent are never refunded. Walking out of the
  chamber drops a held charge.
* Contact with a thawed Jagger costs one heart but never below ½ heart, and
  shoves the hero back to the last safe spot outside the lane.

## Deviations from the spec text

* The Jagger is a **puzzle actor**, not an enemy id: weapons only scan
  `entities[]`, so it is absolutely invincible; player shots that overlap it
  are absorbed (SFX_TICK). It never counts toward a combat seal.
* Reset feedback is SFX_PORTAL + a short shake + the 30-frame Jagger hold
  (no palette fade).
* The held-charge pip is drawn above the hero rather than in the HUD.
* No closable alcove: the 2-tile gaps act as the doors the Jagger can't use.
* Ordinary enemies are kept out of the chamber and its doorway column
  (`enemy_try_step` guard + an eviction sweep), so nothing that moves can
  rest on the entrance or reset path.
* Code is pinned to cold **bank 30** (`#pragma bank 30`) instead of
  `#pragma bank 255`: autobank placed it in hot banks 1–2 and broke the
  bank-1 256-byte emergency floor. Still BANKED, no home code, no
  initialized globals.

## Art

All sprites (Jagger idle/walk, pipes pedestal, reset plate, pip, glyph) are
GPT Image 2 renders quantized to the GBC palette by
`scripts/gen_rime_art.py` (`scripts/rime_art_grids.json`). Bank-1 OBJ tiles
176–193, shared with basilisks (which are swept from this room).

## Tests

`scripts/test_rime_room.py` (headless PyBoy, ~3 s): layout + BFS reachability
from the room edges, shot absorption, fresh solve by walking, Pack reset while
pinned (HP kept), entrance-plate reset, solve after reset, return trip, Jagger
never leaves its lane, no enemy inside the chamber.
