# Sun Lattice light-reflection puzzles

Date: 2026-11-15 · Status: **proposal for review, nothing implemented**
Design source: Argon (Gemini Bridge, 2026-11-15), fact-checked against
`origin/main` at `284ca170` (newer than `4290c169`). The Argon draft targeted
an older HEAD (`bcd18c6`); claims below were re-verified on current main.

## Goal

Add a light-reflection puzzle kind, `PUZZLE_SUN_LATTICE`, to later dungeons
(Stage 3 `EMBER DEPTHS` through Stage 9 `VOID SANCTUM`). A Sun Brazier fires a
cardinal beam; the player rotates 8x8 Helio Vanes to steer it onto one or more
Solar Obelisks. Required rooms stay solvable with base movement and melee.
Class innates, B-items, waygear, and Oaths are shortcuts, never requirements.

## Design summary

- New puzzle kind only. The four existing kinds stay in the enum.
- Default reflector is a rotating 8x8 Helio Vane (`/` and `\`), not a pushed
  16x16 mirror crate. Rotation is always undoable. Existing `BGT_BLOCK` crates
  can act as opaque shutters or as pressure-plate weights in later rooms.
- Beams deal no damage, ignore bodies and projectiles, and are drawn with BG
  tiles (zero OAM).
- Bifrost Wedge splitters start in Stage 4 (`FROST VAULT`). At most two
  wedges per room, so the tracer stays within 3 branches × 32 steps.
- Solved state uses the **existing Trial / Waystone bits** (or the Deep Switch
  bit if that slot is chosen). No new save bytes.
- Seven authored teaching layouts, one per later-stage beat, are preserved
  below. Procedural rooms are generated backwards from a solved beam path.

## What exists in code today (verified on `284ca170`)

### Puzzle kinds (`src/game/puzzle.h`)

```
PUZZLE_NONE = 0,
PUZZLE_PUSH_SEAL,
PUZZLE_RUNE_SEQUENCE,
PUZZLE_PHASE_SWITCH,
PUZZLE_PHASE_GATE,
```

Assignment in `puzzle_prepare_room` (`puzzle.c:291-321`):

| Mission cell | Kind |
|---|---|
| `mission_deep_switch_cell` | `PUZZLE_PHASE_SWITCH` (bit `RUN_DEEP_PHASE_OPEN_BIT`) |
| `mission_deep_gate_cell` | `PUZZLE_PHASE_GATE` (same bit) |
| `mission_waystone_cell` | `((family + seed) & 1) ? PUSH_SEAL : RUNE_SEQUENCE` |
| `mission_trial_cell` | `(family & 1) ? RUNE_SEQUENCE : PUSH_SEAL` |

`family = bosses_beaten % 3`. There is no 3-way rotation today.

### Persistence bits (not a generic per-room mask)

`run_state.h` still comments `dungeon_puzzles` as "bit 0..7: solved procedural
puzzle rooms". That comment is stale. The live bits are named route flags:

**`dungeon_puzzles`**

| Bit | Macro | Meaning |
|---|---|---|
| 0 | `RUN_TRIAL_BIT` | Trial cell solved |
| 1 | *(legacy)* | Old fixed room-one Trial; `sram.c` migrates it into bit 0 |
| 2 | `RUN_REAPER_CLEARED_BIT` | Reaper cleared |
| 3 | `RUN_WARDEN_BOON_BIT` | Warden boon |
| 4 | `RUN_HEXA_SANCTUM_BIT` | Hexa sanctum |
| 5 | *unused* | Do not spend lightly |
| 6 | `RUN_DEEP_GATE_BIT` | Deep gate opened |
| 7 | `RUN_WAYSTONE_BIT` | Waystone cell solved |

`RUN_REAPER_HUNT_BIT` is also `(1u << 7)`, but it lives on
`return_echo_flags`, not `dungeon_puzzles`.

**`dungeon_phase`**

| Bit | Macro | Meaning |
|---|---|---|
| 0 | `RUN_PHASE_OPEN_BIT` | Default `room_puzzle_phase_bit`; not a Trial/Waystone solved flag |
| 1 | `RUN_FARFOLD_CACHE_BIT` | Farfold Cache |
| 2 | `RUN_DEEP_PHASE_OPEN_BIT` | Deep switch / gate |
| 3–6 | `RUN_HIDDEN_SECRET_BIT(0..3)` | Optional disguised secrets (`mask 0x78`) |
| 7 | `RUN_DEEP_WARDEN_BIT` | Deep Warden |

`mark_puzzle_solved()` writes **only** `RUN_TRIAL_BIT` or `RUN_WAYSTONE_BIT`,
then spawns one dungeon-tool charge (`Rift Bomb` / `Echo Chime` /
`Mirror Shard`, item ids 40–42). Both fields are cleared on
`run_state_begin_world` / `run_state_begin_dungeon`.

A Sun Lattice room can stay solved with **zero new SRAM** if it occupies the
Trial and/or Waystone slot (or, if chosen, the Deep Switch slot). It cannot
claim "the room's bit" for an arbitrary cell: there is no general per-room
puzzle mask.

### Tools and names (Hookshot is not Rift Hook)

| Name | Source | Role |
|---|---|---|
| Hookshot | `ITEM_ID_HOOKSHOT 46u`, pack label `HOOKSHOT` | B-item. Latches `BGT_WALL`, `BGT_PILLAR`, `BGT_TREE`, `BGT_CRYSTAL`, `BGT_WALL_CRACK`, or an enemy, then pulls the **player** toward the latch (`hookshot.c:88-119`). Pull stops when `room_player_position_clear` fails (water, chasm, etc.). |
| Rift Hook | `WAYGEAR_HOOK`, not an item id | Traversal waygear. Passes `BGT_GATE_CHASM` (102) and `BGT_WILD_HOLE` (108). |
| Mirror Shard | `ITEM_ID_MIRROR_SHARD 42u`, pack label `MIRROR` | Single-use dungeon tool. Reflects hostile shots back at attackers (`dungeon_tools.c` `tool_mirror`). |
| Echo Prism | `ITEM_ID_ECHO_PRISM 34u` | Every fourth primary `A` attack forks. |
| Rift Lens | `ITEM_ID_RIFT_LENS 44u` | Every third primary `A` attack becomes a heavy beam (`ATTACK_TRAIT_BEAM`, `SPR_FX_BEAM_HEAD 158`, `SPR_FX_BEAM_TAIL 159`). |
| Echo Chime | `ITEM_ID_ECHO_CHIME 41u` | Reveals nearby map cells and disguised secrets. |
| Tide Raft | `WAYGEAR_RAFT` | Passes `BGT_GATE_WATER` (101) and `BGT_WILD_WATER` (97). |

### Stages (`content/src/stages.rs`)

| Player stage | Id | Name |
|---|---|---|
| 1 | 0 | `CRYSTAL CAVERNS` |
| 2 | 1 | `VERDANT HOLLOW` |
| 3 | 2 | `EMBER DEPTHS` |
| 4 | 3 | `FROST VAULT` |
| 5 | 4 | `TOXIC MIRE` |
| 6 | 5 | `SHADOW KEEP` |
| 7 | 6 | `GOLDEN TEMPLE` |
| 8 | 7 | `BLOODMOON` |
| 9 | 8 | `VOID SANCTUM` |

Oath unlocks: `unlocked_count = min(bosses_beaten, 9)` (`oath_arts.c`). Names
in order: `SHARD WAKE`, `ROOT CALL`, `CINDERSTEP`, `STILL WAVE`, `MIASMA`,
`GLOAM SHIFT`, `SUN TURN`, `RED HARVEST`, `RIFT EXCHANGE`.

- Entering Stage 7 (`GOLDEN TEMPLE`): `bosses_beaten == 6`, so `GLOAM SHIFT`
  is unlocked and `SUN TURN` is not.
- `SUN TURN` (index 6, element bit 4) unlocks after Stage 7's Colossus, and is
  available in Stages 8–9 (`BLOODMOON`, `VOID SANCTUM`).
- `room_elemental_tile(..., element & 4)` already toggles `BGT_SWITCH`
  (phase-switch or dungeon-law plates). It does not touch any lattice fixture,
  because those tiles do not exist yet.

### Other grounded facts that stand

- Crates are 16x16 (`BGT_BLOCK` 25 + TR/BL/BR 28–30). A cardinal hold of 10
  frames slides the crate one 8x8 tile (`room.c:1588`). No pull verb.
- `BGT_CRYSTAL` (22) is a solid glowing obstacle. Player shots shatter it with
  a chance of an MP pickup (`rng_next_u8() < 64` in `room_break_crystal`).
- Mirror Moth (`SPR_ENEMY_MIRROR_MOTH 77`) is a Frost Vault enemy that applies
  `QSTATUS_INVERSION`.
- Room grid is `ROOM_W 20` × `ROOM_H 17`. Standard doors are 2 tiles: N/S at
  columns 9–10, E/W at rows 8–9 (`procgen.c:637-644`). HUD is the window
  strip at WY=136, outside the 20×17 playfield.
- `MAX_ENTITIES` is 32. `entity_t.oam_slot` is documented as `1..32`, with 0
  reserved for the player. Hardware OAM is 40 sprites at `$FE00–$FE9F`.
  Hookshot draw uses up to 4 OAM entries (`hook + 3 chain dots`, `oam < 40`).
- `scripts/test_puzzles.py` exists and is the right place to extend coverage.
- Riftwild hidden dens are **docs only**
  ([`2026-11-15-riftwild-hidden-dungeons.md`](2026-11-15-riftwild-hidden-dungeons.md),
  PR #79). They are not in the shipping cartridge.

## Corrections to the Argon draft

These claims were wrong or overstated and are **not** used as facts below.

1. **`dungeon_puzzles` is not a general per-room solved mask.** Only Trial
   (bit 0) and Waystone (bit 7) record a solved puzzle room. A new kind must
   occupy one of those slots (or Deep Switch's `dungeon_phase` bit) or spend
   a rare unused bit.
2. **Bank 0 indices `35..54` are not free**, and neither is `105..127`.
   `35–39` are outdoor `BGT_GRASS/PATH/ROOF/FENCE/TREE`; `40–48` are
   `HUD_OFFER_HEAL..WEAPON`; `49–54` are compass tiles (`BGT_MAP_ROOM` through
   `BGT_MAP_PATH_V`). `105–110` are wild climate tiles; `125–126` are the
   arrow trap and locked door; `127+` are more HUD offers.
3. **Bank 1 indices `48..54` overlap Hexa Dragmar.** `HEXA_BG_TILE` is 40
   with `HEXA_BG_COUNT` 16, so Hexa's sanctum BG occupies **bank 1 tiles
   40–55** (commented in `tiles.h` as living at `0x9000`, clear of bank-1 OBJ
   `64..87`, `88..127`, and `208..213`). Argon reused that comment but picked
   indices inside Hexa's range. Hexa only loads in the Hexa encounter, so
   `48–54` can be reused in ordinary dungeon rooms if lattice tiles are
   reloaded after Hexa, but it is a poorer default than **bank 1 tiles
   `56–62`**, which sit after Hexa and before bank-1 OBJ at 64. Bank 1 tiles
   `0–39` are also unused today and are the natural place for #79's 2–3 den
   tell tiles, if those land.
4. **Hexa does not own all of bank 1 `0..127`.** Only tiles 40–55. Mire roots
   stay in **bank 0** tiles 55–63.
5. **`PUZZLE_RUNE_SEQUENCE` has no 12-frame hold.** Stepping on the last
   correct rune solves immediately (`update_sequence` → `mark_puzzle_solved(1)`).
   The 12-frame figure is the post-solve fanfare delay from the puzzle-note
   work (issue #22 / `sfx_play_puzzle_after_note`) and the phase-switch shake.
   A 12-frame simultaneous-illumination dwell for Obelisks is still a good
   proposed rule; it just does not match a rune hold.
6. **Hardware OAM is `$FE00–$FE9F`, not `$C800–$C89F`.** The latter is the
   size of a 40-sprite shadow-OAM buffer in WRAM (GBDK's `shadow_OAM` is often
   placed there). The 40-sprite cap and the 10-sprites-per-scanline limit
   still apply, so a BG-tile beam remains the right call.
7. **`oam_slot 0..32` is slightly off.** The entity header says `1..32`, with
   0 reserved for the player. Drawing starts at OAM index 4 in
   `entity_draw_core.h` after the player metasprite.
8. **Fixture constant names were inconsistent** in the draft
   (`BGT_VANE_NE_SW` vs `BGT_VANE_SLASH`, `BGT_SOLAR_OBELISK_*` vs
   `BGT_OBELISK_*`, directional `BGT_BIFROST_N/E/S/W` vs a single
   `BGT_BIFROST`). This spec uses one set, below.
9. **Several ASCII teaching rooms were left mid-revision**: the intended
   beam trace does not always match the diagram (Layouts 2, 3, 4, 5, 6, 7).
   The diagrams are kept verbatim; each layout notes the mismatch so
   implementation can reconcile them.
10. **Dens do not already load a stage atlas.** That is a #79 proposal, not
    current code. Sun Lattice inside dens is contingent on #79 being approved
    and implemented.

## Naming

To avoid colliding with Mirror Shard, Echo Prism, Mirror Moth, Rift Lens, or
shatterable `BGT_CRYSTAL`:

| Role | Player-facing name | Tile constants |
|---|---|---|
| Puzzle kind | Sun Lattice | `PUZZLE_SUN_LATTICE` (append to the `puzzle.h` enum) |
| Beam source | Sun Brazier | `BGT_SUN_EMITTER` |
| Rotating reflector | Helio Vane | `BGT_VANE_SLASH` (`/`), `BGT_VANE_BACKSLASH` (`\`) |
| Beam splitter | Bifrost Wedge | `BGT_BIFROST` (fixed T-splitter; one tile, not four facings) |
| Target | Solar Obelisk | `BGT_OBELISK_OFF`, `BGT_OBELISK_LIT` |
| Beam art | — | `BGT_BEAM_H`, `BGT_BEAM_V`, `BGT_BEAM_CROSS` (plus emitter/obelisk lit faces if they share the 7-pattern budget) |

## 1. Mechanics

### 1.1 Rotating vanes, not mirror crates

A 16x16 crate straddles four tiles, so an 8x8 beam has an ambiguous bounce
face; a crate pushed into a corner cannot be pulled back. An 8x8 vane sits on
one tile, toggles `/` ↔ `\` invertibly, and costs two BG patterns.

**Default: rotating 8x8 Helio Vanes.** Existing 16x16 `BGT_BLOCK` crates may
block a beam or sit on a `BGT_SWITCH` to drop a `BGT_PILLAR` in a later room.
They are never the primary mirror.

### 1.2 Fixtures

1. **Sun Brazier.** 8x8 solid BG tile, usually in the inner perimeter
   (`x=1` or `18`, `y=1` or `15`) or as a freestanding pedestal. Always on
   when the room loads. Emits one authored cardinal ray (`N/E/S/W`).
2. **Helio Vane.** 8x8 solid tile, movement-blocked like `BGT_PILLAR`.
   Double-sided 90° bounce:
   - `/` (`BGT_VANE_SLASH`): `N ↔ E`, `S ↔ W`
   - `\` (`BGT_VANE_BACKSLASH`): `N ↔ W`, `S ↔ E`
   Striking a vane with any primary `A` attack (Fang Forms, Tail Spike,
   Featherbarb, BubbleBolt, Stinger), a damaging `B` power, Boomerang,
   Morningstar, Bomb, or Hookshot toggles `/` ↔ `\` and retraces the beam.
   An 8-frame per-vane debounce stops multi-hit arts (Vespine Swarm, Picsean
   Tidal Wave) from double-toggling on one press.
   In Stages 6–9, a **Fixed Vane** may use `BGPAL_WALL` instead of
   `BGPAL_CRYSTAL`: it still reflects, but a strike does not rotate it.
3. **Bifrost Wedge** (from Stage 4 `FROST VAULT`). 8x8 solid, fixed T-splitter.
   A beam entering on one cardinal axis leaves on the two perpendicular axes
   (`N/S` in → `E+W` out; `E/W` in → `N+S` out). At most **two** wedges per
   room (3 live branches).
4. **Solar Obelisk.** 8x8 solid. Accepts a beam on any cardinal face. When
   every Obelisk in the room is `BGT_OBELISK_LIT` for **12 continuous frames**,
   the puzzle solves. The dwell avoids one-frame flicker clears; it is a new
   rule, not a copy of rune-sequence input.

### 1.3 Occlusion, damage, persistence, reset

| Rule | Spec |
|---|---|
| Stops a beam | `BGT_WALL`, `BGT_DOOR`, `BGT_PILLAR`, `BGT_CRYSTAL` (until the player shatters it), `BGT_RUBBLE`, `BGT_BLOCK` / TR / BL / BR, `BGT_GATE_BOULDER` (100), and a Solar Obelisk (absorbs the ray it receives). |
| Passes over | `BGT_FLOOR`, `BGT_FLOOR2`, `BGT_FLOOR3`, `BGT_SPIKES`, `BGT_SWITCH`, `BGT_GATE_WATER` (101), `BGT_GATE_CHASM` (102), `BGT_GATE_THORNS` (103), `BGT_GATE_VENT` (104), `BGT_WILD_WATER` (97), `BGT_WILD_HOLE` (108). |
| Bodies | Beams do **not** clip the player or enemies. The beam lives in the BG tilemap; retracing it every time a body crosses a lane would thrash VBlank. Treat it as passing at chest height. |
| Projectiles | Shots do not collide with the ray. A player shot that hits a **rotatable** vane rotates it and dies, except piercing shots (Picsean BubbleBolt), which rotate and continue under the 8-frame debounce. |
| Damage | **None.** Puzzle rooms already keep a live procedural guard pack and hostile bullets. A damage laser in an 18×15 interior would punish melee classes and fight the traversal-first rule. |
| Persistence | Solving sets `RUN_TRIAL_BIT` or `RUN_WAYSTONE_BIT` via the existing `mark_puzzle_solved()` path (or `RUN_DEEP_PHASE_OPEN_BIT` if this kind ever occupies Deep Switch). That also spawns the mandatory tool charge. Vanes and beams then stay locked in the solved / lit state for the rest of the stage. |
| Reset | Rotating a vane cannot soft-lock. If a room also has a 16x16 crate shutter: (1) leaving and re-entering an unsolved room restores crate positions and vane angles to the seed state; (2) an authored `BGT_SWITCH` reset plate, or a melee hit on the Sun Brazier with no directional hold, flashes the room and resets unsolved crates and vanes. |

## 2. Stage 3+ progression and seven teaching layouts

Grid: columns `0..19`, rows `0..16`. Perimeter walls on row 0, row 16, col 0,
and col 19 leave an 18×15 interior. HUD is the 160×8 window under the
playfield.

**Legend**

- `#` = `BGT_WALL` (2) · `D` = `BGT_DOOR` (3) · `.` = `BGT_FLOOR` (1)
- `E` = Sun Brazier · `/` `\` = Helio Vane starting state · `T` = Bifrost Wedge
- `O` = Solar Obelisk (off) · `C` = `BGT_CRYSTAL` (22) · `P` = `BGT_PILLAR` (21)
- `B` / `BB` = 16x16 crate (`BGT_BLOCK` 25, 28–30)
- `^` = `BGT_SPIKES` (31) · `~` = water / poison (`BGT_GATE_WATER`) · `=` = chasm (`BGT_GATE_CHASM`)
- `S` = `BGT_SWITCH` (33) · `F/` `F\` = Fixed Vane (in the Layout 7 notes)

Oath-on-entry counts in the titles match `unlocked_count` on current main.

The ASCII blocks are Argon's, kept verbatim. Where the beam trace disagrees
with the diagram, the intended solution is the trace, and the mismatch is
called out for the implementer.

### Layout 1 — Stage 3: Ember Depths (id `2`, Trial cell)

**Title:** *The Shattered Conduit*
**Oaths on entry:** 2 (`Shard Wake`, `Root Call` — neither required).
**Teaching goal:** Introduce the Brazier, rotate one vane with a basic `A`
attack, and shatter a `BGT_CRYSTAL` that blocks the lane.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #..E.....C.....\...#
03 #..................#
04 #....^^......^^....#
05 #....^^......^^....#
06 #..................#
07 #..................#
08 D..................D
09 D..................D
10 #..................#
11 #....^^......^^....#
12 #....^^......^^....#
13 #..................#
14 #..O.........../...#
15 #..................#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Initial state:** `E(3,2)` fires East and is blocked at `(9,2)` by `C`.
  Vane `(15,2)` starts as `\` (solved angle). Vane `(15,14)` starts as `/`
  (wrong: a South beam on `/` would go West; as drawn it starts `/`, but the
  intended unsolved state is `\`, which would dump South → East into the wall).
- **Intended solution:**
  1. Shoot or strike `C(9,2)`. The beam reaches `(15,2)` (`\`) and turns South
     to `(15,14)`.
  2. Strike `(15,14)` once, `\` → `/`, sending the beam West into `O(3,14)`.
- **Reconcile on implement:** seed `(15,14)` as `\` so one strike produces `/`.

### Layout 2 — Stage 3: Ember Depths (id `2`, Waystone cell)

**Title:** *The Slag Shutter*
**Oaths on entry:** 2 (none required).
**Teaching goal:** 16x16 crates are opaque shutters. Slide the crate off the
beam and turn a vane, while reading Ember spike seams.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #..E............\..#
03 #..................#
04 #......^^^^^^......#
05 #...............BB.#
06 #...............BB.#
07 #..................#
08 D..O...............D
09 D..................D
10 #..................#
11 #......^^^^^^......#
12 #..................#
13 #..P............/..#
14 #..................#
15 #..................#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Intended solution (author's revised trace):**
  1. `E(3,2)` fires East into `\(16,2)`, which sends the beam South down
     column 16. The crate at `(16..17, 5..6)` blocks that column. Hold West or
     South for 10 frames from `(16,4)` or `(15,5)` and slide `BB` off column 16
     (for example to `(14..15, 5..6)`).
  2. A vane at `(16,8)` (starts `\`, needs `/`) turns the South beam West along
     the door row into `O(3,8)`.
- **Mismatch:** the ASCII places the second vane at `(16,13)` as `/` and a
  pillar at `(3,13)`, and leaves `(16,8)` as floor (also an east door cell).
  Implementation should put the turning vane on the dry interior, not on the
  door tile: prefer `(16,7)` or `(16,10)` if `(16,8)` collides with the door.

### Layout 3 — Stage 4: Frost Vault (id `3`)

**Title:** *Crystalline Bifrost*
**Oaths on entry:** 3 (`Shard Wake`, `Root Call`, `Cinderstep` — none required).
**Teaching goal:** Introduce the Bifrost Wedge and two Obelisks that must light
together, in Frost Vault's four-entry ring.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #...O..........O...#
03 #..................#
04 #......P....P......#
05 #..................#
06 #...E....T.....\...#
07 #..................#
08 D..................D
09 D..................D
10 #..................#
11 #......P....P......#
12 #..................#
13 #.../....\...../...#
14 #..................#
15 #..................#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Intended solution (author's revised trace):** Move the emitter to `E(9,14)`
  firing North into `T(9,6)`. The wedge splits West to `(4,6)` and East to
  `(14,6)`.
  1. Strike `(4,6)` `/` → `\` so the West branch turns North into `O(4,2)`.
  2. Leave `(14,6)` as `\` (South to `(14,13)`). Strike `(14,13)` `/` → `\` so
     the beam turns East into a second Obelisk at `(16,13)`.
- **Mismatch:** the ASCII puts `E` at `(4,6)`, both Obelisks on row 2, and no
  Obelisk at `(16,13)`. Implementation should follow the split-from-the-south
  trace and place `O2` at `(16,13)` (or adjust the ASCII to match a cleaner
  two-Obelisk path that keeps both targets on row 2).

### Layout 4 — Stage 5: Toxic Mire (id `4`)

**Title:** *Ranged Optics Across the Mire*
**Oaths on entry:** 4 (adds `Still Wave` — not required).
**Teaching goal:** Beams cross water that non-Picsean champions without Tide
Raft cannot walk. Teach ranged vane toggles (Corvin Featherbarb, Picsean
BubbleBolt, Boomerang, Hookshot, Shard Wake, Wolfkin Howl) **or** a fully dry
melee route, so mandatory seeds never lock a class out.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #..~~~~..E...~~~~..#
03 #..~/~~......~~\~..#
04 #..~~~~......~~~~..#
05 #..~~~~......~~~~..#
06 #..................#
07 #.../...P..P...\...#
08 D..................D
09 D..................D
10 #..................#
11 #..~~~~......~~~~..#
12 #..~~~~......~~~~..#
13 #..~\~~......~~O~..#
14 #..~~~~.../..~~~~..#
15 #..................#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Dry-land solution (all classes, base kit):**
  1. `E(9,2)` fires **South** to a vane on the dry cross at `(9,7)`.
  2. Flip `(9,7)` to `\` so the beam goes East along `y=7` to `(15,7)`.
  3. Flip `(15,7)` to `\` so the beam goes South across the SE pool into
     `O(15,13)`.
- **Optional shortcut:** Picsean / Tide Raft, or a ranged shot across the NW
  pool, can use island vanes `(4,3)` and `(4,13)` for a bonus
  `HIDDEN_SECRET_SHOT`-style crystal or switch. Not required.
- **Mismatch:** `(9,7)` is floor in the ASCII (between the two pillars on row
  7). Implementation must stamp a vane there for the dry route. Island vanes
  stay optional.

### Layout 5 — Stage 6: Shadow Keep (id `5`)

**Title:** *The Portcullis Switchback*
**Oaths on entry:** 5 (adds `Miasma` — not required).
**Teaching goal:** A `BGT_SWITCH` drops a portcullis pillar, then a
multi-bounce path weaves around keep pillars and chasm seams.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #..E....P.....\....#
03 #..................#
04 #..===........===..#
05 #..................#
06 #../....\...../....#
07 #..................#
08 D.......P..P.......D
09 D..................D
10 #..................#
11 #..\....S.....\....#
12 #..................#
13 #..===........===..#
14 #..................#
15 #.......O........../#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Intended solution:**
  1. Step on `S(8,11)` to drop portcullis `P(8,2)` to `BGT_FLOOR2`.
  2. Beam: `E(3,2)` East to `\(14,2)` → South to `/(14,6)` → West to `(8,6)`.
  3. `(8,6)` should be `/` so the Westward beam turns South along `x=8`,
     through `S(8,11)`, into `O(8,15)`.
- **Mismatch:** the ASCII already draws `(8,6)` as `\`, and the mid-row
  pillars are at `(8,8)` and `(11,8)`, so column 8 is blocked at the door row.
  Implementation should either move those pillars to `(7,8)` and `(11,8)` as
  the author later suggested, or route around `(8,8)`. Count is 1 switch plus
  about 2 vane strikes once the diagram is reconciled.

### Layout 6 — Stage 7: Golden Temple (id `6`)

**Title:** *Colonnade of the Twin Suns*
**Oaths on entry:** 6 (`Gloam Shift` unlocked; `Sun Turn` is not, until after
this stage's Colossus).
**Teaching goal:** Two emitters, a central Bifrost Wedge, and three Obelisks,
with orthogonal beams sharing `BGT_BEAM_CROSS` floor tiles.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #..E...../.....O...#
03 #..................#
04 #....P........P....#
05 #..................#
06 #..\.....T...../...#
07 #..................#
08 D........O.........D
09 D..................D
10 #..................#
11 #....P........P....#
12 #..................#
13 #../.....\.....E...#
14 #..................#
15 #........O.........#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Intended solution:**
  1. `E(3,2)` fires East into `(9,2)`. Set `(9,2)` to `\` so the beam turns
     South into `T(9,6)`.
  2. `T(9,6)` splits West to `(3,6)` and East to `(15,6)`.
  3. Set `(3,6)` to `/` (West branch South to `(3,13)`), `(3,13)` to `\` (East
     to `(9,13)`), `(9,13)` to `\` (South into `O(9,15)`).
  4. Set `(15,6)` to `/` so the East branch turns North into `O(15,2)`.
  5. For `O(9,8)`, do not fire `E(15,13)` West into the back of `(9,13)`.
     Prefer `E(15,13)` North through a vane at `(15,8)` (`\`) that turns West
     into `O(9,8)`, or move emitter 2 to `(15,8)` firing West, with an optional
     crate or crystal shutter on that row.
- **Mismatch:** the ASCII already draws some of those vanes in the opposite
  starting state, and emitter 2 sits at `(15,13)`. Implementation should seed
  the unsolved angles from a backwards-from-solved scramble of this tree.

### Layout 7 — Stage 9: Void Sanctum (id `8`, final stage)

**Title:** *The Sanctum Lattice*
**Oaths on entry:** 8 (includes `Sun Turn` [6], `Gloam Shift` [5],
`Cinderstep` [2]). `Rift Exchange` is still locked until this Colossus falls.
There is no separate Stage 8 (`BLOODMOON`) teaching layout; Bloodmoon uses the
procedural generator with the Stage 6–9 rules (fixed vanes, optional shutters).
**Teaching goal:** Two Bifrost Wedges, Fixed Vanes (`BGPAL_WALL`), a 16x16
crate shutter, and three Obelisks. `Sun Turn` may toggle the remote `S` from
across the chasm as a shortcut; any champion can still walk the apron or use
Rift Hook / Corvin, which the late-game route already requires.

```text
   01234567890123456789
00 #########DD#########
01 #..................#
02 #..E....T......\...#
03 #..................#
04 #..===......===....#
05 #..=S=..BB..=O=....#
06 #..===..BB..===....#
07 #..................#
08 D../....P....../...D
09 D..................D
10 #..................#
11 #.......T..........\#
12 #..................#
13 #..O..../......O...#
14 #..................#
15 #..................#
16 #########DD#########
   [HUD WINDOW 160x8px]
```

- **Intended solution (author's revised tree, 2 splitters, 3 Obelisks):**
  1. Clear the crate at `(8..9, 5..6)` off column 8 (push West onto
     `(6..7, 5..6)`, or North/South off the lane).
  2. Trigger `S(4,5)` to drop `P(8,8)`:
     - Path A: Corvin or Rift Hook walks the chasm. By Stage 9 the regional
       Warden route has already granted the Hook.
     - Path B: `Sun Turn` remotely hits the switch (`element & 4` →
       `room_elemental_tile`), or `Gloam Shift` teleports onto `(4,5)`.
  3. Reconcile the splitter tree so all three Obelisks (`O(13,5)`, `O(3,13)`,
     `O(15,13)`) light together. The author's last trace: treat `T1` as a
     South send into `T2`, which splits West to `O(3,13)` and East into a
     further split that covers `O(13,5)` and `O(15,13)`.
- **Mismatch:** the ASCII's `T` positions, the spare vanes, and the "add a
  vane at `(3,11)`" notes do not yet form one closed tree. Implementation
  must author a single backwards-from-solved layout and stamp that, not try
  to execute every mid-revision sentence at once.

## 3. Beam rendering (VRAM, palettes, VBlank)

### 3.1 BG tiles, not OAM

A multi-bounce beam across an 18×15 interior spans roughly 12–28 tiles. Doing
that with 8x8 sprites would fight the remaining OAM (player metasprite,
guards, bullets, Hookshot's 4 entries) and the 10-sprites-per-scanline cap on
horizontal runs. **Draw the beam in the BG tilemap. Zero OAM.**

### 3.2 Seven new 8x8 patterns

Proposed set: emitter, vane `/`, vane `\`, bifrost, obelisk off, beam
horizontal, beam vertical. A lit obelisk and a cross beam can share palettes
or reuse floor variants if the budget must stay at 7.

**Recommended placement: VRAM bank 1, BG indices `56–62`.**

- In 8800 BG addressing (the addressing assumed by the Hexa comment in
  `tiles.h`), those tiles live at `0x9380–0x93EF` in bank 1, still inside the
  `0x9000–0x93FF` region that is disjoint from bank-1 OBJ tiles `64+` at
  `0x8400+`.
- They do not overlap Hexa (`40–55`) or Mire roots (bank 0 `55–63`).
- Load them when preparing a Stage 3+ dungeon (and when entering a den that
  uses this kind). Hexa already reloads its own bank-1 atlas for the sanctum
  fight, so the two never have to share a room.

Reject bank 0 `35–54` and bank 0 `105–127`; those ranges are occupied (see
Corrections). Bank 1 `48–54` is a workable fallback only if lattice tiles are
reloaded after every Hexa visit.

Set CGB BG attribute bit 3 (`0x08`, VRAM bank 1) on fixture and beam cells.

### 3.3 Floor preservation and VBlank redraw

Store the underlying floor tile under each beam cell (a small 32-entry side
buffer is enough for 3×32 tracer steps) so a retrace can restore floor,
spikes, or water when the beam leaves. Patch dirty cells incrementally during
VBlank with `room_set_tile_vbl` / the existing VBK 0 data + VBK 1 attribute
pattern. Do not rewrite the whole 20×17 map on every vane hit.

### 3.4 Tracer budget

Cap the solver at **3 branches × 32 steps**, with a visited-tile mark so a
loop cannot run forever. A compact 20×17 room is well inside 32 steps. Do not
place this kind on a wide 31-tile dungeon field unless the cap is raised;
mandatory Trial / Waystone cells should stay compact.

CPU cost must leave room for the live guard pack and projectiles. Trace only
when a vane, crate, crystal, or switch changes, not every frame, except for
the 12-frame lit dwell counter.

## 4. Tool and class interactions

### 4.1 Hookshot (B-item, `ITEM_ID_HOOKSHOT`) vs Rift Hook (waygear)

These are different verbs. Hookshot is the latch-and-pull B-item. Rift Hook
is the chasm-crossing waygear. Do not conflate them.

**Proposed Hookshot rules:**

- **Rotatable Helio Vane: snag-and-spin 90°, then retract.** Do not pull the
  player onto the vane. The vane is solid like a pillar, so pull-and-spin
  would drag melee champions into the fixture or into a hazard the beam is
  crossing. This is what makes Hookshot a ranged optical wrench.
- **Fixed Vane or Bifrost Wedge:** keep today's latch-and-pull (same as
  `BGT_PILLAR`), still stopping at water/chasm unless #79's Hookshot-over-water
  question is answered yes.

### 4.2 Waygear and innates

Picsean / Tide Raft may walk water. Corvin / Rift Hook may walk chasms.
Those are shortcuts onto optional island vanes or remote switches. Mandatory
seeds always have a dry-floor melee route (see question 4).

### 4.3 Oaths

All Oath interactions are optional speed/routing aids, never required.

- Arts already unlocked by the stage (Shard Wake as a ranged poke, Gloam
  Shift as a reposition) may hit vanes or reach a plate the way any other
  strike or step would.
- `Sun Turn` already toggles `BGT_SWITCH` through `room_elemental_tile`.
  That existing behavior may apply to shutter / portcullis / reset plates
  inside a lattice room. No new "energize an Obelisk for 5 seconds" or
  "auto-align struck vanes" rule is recommended (see question 5).

## 5. Optional tie-in with Riftwild dens (PR #79)

Dens are still a proposal. If #79 is approved and built:

- Use Sun Lattice only in Region 2–3 **SCAR** and **Hollow** dens, which are
  the longer, chasm/rift-themed interiors. Leave CAIRN dens on Push Seal.
- Reuse the Stage 3+ lattice tiles. That costs no extra den-tile budget
  *once both systems are implemented and share the bank-1 atlas*. It is not
  true in current code.
- While the player is inside the 2–4 room den, use the same transient
  Trial/room flags a normal dungeon visit would. Cross-visit "already
  cleared" must use #79's reserved den bits, not new SRAM, and not leftover
  `dungeon_puzzles` bits (those reset on `begin_world` / `begin_dungeon`).
- This spec does not answer #79's own owner questions (count, early access,
  Hookshot over water, keepers, rewards). A den lattice room still gets a
  dry apron so it stays solvable regardless of those answers.

## 6. Soft-locks, procgen, and tests

- Vane rotation is invertible. Crate shutters used here never have to be
  pushed into a corner; they either leave a beam lane (one tile off the
  emitter row/column) or sit on a `BGT_SWITCH` that has a 1-tile floor border
  on all four sides. Unsolved crate rooms reset on re-entry and from the
  brazier / reset plate.
- Generate procedural rooms **backwards from a solved optical tree**, then
  scramble vane angles (and optional shutter positions) the way
  `PUZZLE_PHASE_SWITCH` already generates backwards from a solved state.
- Headless coverage: extend `scripts/test_puzzles.py` (and a Rust parity
  solver in `quintra-procgen`) to boot Stages 2–8, walk the mission graph to
  `mission_trial_cell` / `mission_waystone_cell`, assert
  `room_puzzle_kind == PUZZLE_SUN_LATTICE`, read the 20-wide tilemap, solve
  with the same BFS the ROM uses, toggle the needed vanes with an 8-frame
  debounce, wait 12 frames of full illumination, and assert
  `room_puzzle_locked == 0` plus the appropriate `dungeon_puzzles` bit.

## Questions for Carmelo

1. **Mission-graph slot (Stage 3+):** Should Sun Lattice take the Trial /
   Waystone slot, or replace Push Seal in the themed stages?
   **Recommendation: In Stage 3+ only, both Trial and Waystone cells use
   `PUZZLE_SUN_LATTICE`, replacing the Push Seal / Rune Sequence coin-flip in
   those rooms.** Keep Push Seal and Rune Sequence as the Stage 1–2 Trial /
   Waystone kinds. Do not delete `PUZZLE_PUSH_SEAL`. Do not add a third
   mandatory puzzle room, and do not turn this into a 3-way rotation (some
   Stage 3+ seeds would then roll a non-lattice room and the new kind would
   feel optional). Leave Deep Switch / Deep Gate on the existing phase pair,
   which already owns `RUN_DEEP_PHASE_OPEN_BIT`. This is the only slot
   pattern that uses the existing `mark_puzzle_solved()` bits with no new
   SRAM and still guarantees a light puzzle in every later dungeon.

2. **VRAM bank 1 or bank 0?**
   **Recommendation: Bank 1, indices `56–62`, not `48–54` and not bank 0
   `35–54`.** `48–54` overlap Hexa's bank-1 tiles `40–55`. Bank 0 `35–54` and
   `105–127` are already used by outdoor tiles, HUD offers, the compass, wild
   climate, and dungeon cues. `56–62` is a clean 7-tile gap after Hexa and
   before bank-1 OBJ 64, and it leaves bank 1 `0–39` free for #79 den tells.

3. **Hookshot on a rotatable vane: snag-and-spin, or pull-and-spin?**
   **Recommendation: snag-and-spin 90°, then retract.** Pull-and-spin fights
   the vane's solid footprint and can drag the player into a fixture or a
   hazard. Fixed vanes and Bifrost pedestals keep the current latch-and-pull.

4. **Must Mire / Keep vanes stay melee-reachable from dry floor?**
   **Recommendation: yes, for every mandatory Trial / Waystone seed.** Island
   or chasm-separated vanes are only for optional chests or post-Rift Hook /
   Tide Raft shortcuts. That matches the "base kit always works" rule already
   in the layouts.

5. **Should Sun Turn interact with the lattice itself?**
   **Recommendation: no new lattice interaction.** Keep the existing
   `BGT_SWITCH` behavior, including shutter / portcullis / reset plates inside
   these rooms. Auto-aligning vanes or temporarily lighting an Obelisk would
   let an Oath skip the puzzle in the two stages where the kind is at full
   complexity.

6. **Should the dens use this kind?**
   **Recommendation: yes, but only Region 2–3 SCAR / Hollow dens, and only
   after #79 is approved.** Reuse the Stage 3+ tiles (0 extra den art once
   both are built). Persist only for the den visit with ordinary dungeon
   flags; cross-visit clears use #79's reserved bits. CAIRN dens stay on the
   original four kinds. #79's own questions remain open.

## Implementation notes (owner approved "yes to all", 2026-11-15)

Runtime: `src/game/sun_lattice.c` (VRAM overlay, strikes, dwell) and
`src/game/sun_lattice_gen.c` (generator + tracer, host-compilable). Decisions
taken while building:

- **Slot:** Stage 3+ (`bosses_beaten >= 2`) Trial and Waystone cells are
  always `PUZZLE_SUN_LATTICE`; Stages 1-2 keep Push Seal / Rune Sequence.
  Solving uses `mark_puzzle_solved()` (`RUN_TRIAL_BIT` / `RUN_WAYSTONE_BIT`);
  no new SRAM. Re-entering a solved room regenerates it from the seed in
  the solved, lit, frozen state.
- **Collision:** fixtures are `BGT_PILLAR` in `room_tilemap`; beams are
  display-only. The lattice layer paints both from VRAM bank 1 tiles 56..62
  (Brazier, Vane, Wedge, Obelisk, beam H, beam V, beam crossing; `\` is the
  `/` tile with the CGB H-flip attribute). The overlay is repainted at the end
  of `room_draw_tilemap()` (room entry, slides, Pack/compass return) and after
  a wide seam stream. Beams are drawn only over plain floor; over spikes,
  plates, water or chasm the ray continues but stays submerged so hazard art
  is never hidden.
- **Generation:** a seeded xorshift16 lays a solved optical tree (emitter,
  vanes, up to two Wedges, one Obelisk per leaf) inside x 3..16, y 3..13 with
  fixtures 3+ tiles apart, then scrambles the solved path's rotatable vanes
  (half of them, rounded up, in the Stage 3 teaching rooms; all of them from
  Stage 4) and proves the result is unlit. Decoys keep their random angle and
  never count toward the scramble. Per-stage shape: vanes 2/2/3/3/3/3/3, Wedges
  0/1/1/1/1/2/2, Fixed Vanes 0/0/0/1/1/2/2, decoys 0/0/1/1/2/2/2 (+1 in
  Waystones) for Ember..Void. Stage 3 Trials always add a shatterable
  `BGT_CRYSTAL` on the first run (1 in 4 rooms from Stage 6). After 64
  failed attempts (about 1% of late seeds) the hand-checked Layout 1 is used.
  The seven teaching layouts above are not stamped verbatim.
- **Reachability (Q4):** the solved path is carved as a 3-wide floor road,
  every fixture gets a 5x5 floor apron, and the body-width cross joins all
  four doors, so every mandatory vane is melee-reachable from dry floor in
  every stage, Mire and Keep included.
- **Solver parity (PR B):** `quintra-procgen::sun_lattice` mirrors the
  generator and tracer and adds `solve()`, a fewest-turn search over the
  rotatable vanes that never reads `solved_ang`. CI's Rust job diffs the
  host-compiled C against Rust for 3000 seeds x 7 stages x 2 roles and checks
  the Rust solver against the Python BFS that drives the PyBoy strikes;
  `test_puzzles.py` also checks that the SDCC-built cart generates exactly
  the Rust room for its live room seed. Fewest turns from the arrival state
  (3000 seeds each): Stage 3 1-2 (mean 1.2), Stage 4 4, Stage 5 2-5 (5.0),
  Stages 6-7 2-5 (4.0), Stages 8-9 2-3 (2.1). Stages 8-9 lean on three
  Obelisks, Fixed Vanes and decoys rather than turn count.
- **Tracer:** at most 5 queued rays (emitter + 2 per Wedge) x 32 steps,
  traced only when a vane turns or a crystal shatters (the spec sketch said
  3 rays; two Wedges need 5); the 12-frame lit
  dwell runs per frame.
- **Strikes:** any player shot that reaches a vane turns it and is
  consumed (8-frame per-vane debounce; spread shots can graze a neighbour);
  boomerangs, bombs, the Morningstar and the Hookshot do too. Hostile
  shots do not. Crate shutters are not implemented. Sun Turn has no lattice interaction (Q5).
  Dens are deferred until #79 (Q6).
- **Hookshot (Q3, PR C):** a Hookshot tip that reaches a rotatable Helio
  Vane in an unsolved room turns it 90 degrees (same 8-frame debounce) and
  retracts without pulling. Braziers, Obelisks, Wedges, Fixed Vanes and a
  solved room's frozen vanes keep latch-and-pull.
- **Morningstar and fuse bombs (PR C):** the Morningstar ball turns the vane it
  sweeps into; a fuse bomb turns every vane in its 3x3 blast, like the
  Rift bomb's 7x7.
- **Known gaps:** during a room slide the incoming lattice briefly shows as
  plain pillars until the final redraw; the Lua balance bot cannot solve
  Sun Lattice rooms yet.

## Visual pass (issue #250, 2026-11-27)

Display only. Layouts, the trace, solvability and tile indices are unchanged.

- **Mirrors.** The Helio Vane tile (bank 1, 57) is a framed pane on a dark
  socket: frame lines either side of a bright glass face, mounts at both
  ends, a darker back edge. hflip still gives the other angle. Rotatable
  mirrors use `BGPAL_CRYSTAL`; fixed ones use `BGPAL_WALL` and look dull.
- **Beam.** Beam cells (60..62) now use `BGPAL_CRYSTAL` instead of
  `BGPAL_FLOOR`: white core, bright halo, saturated edge, dark outline.
- **Animation.** `sun_lattice_animate()` (`sun_lattice_art.c`, bank 30)
  re-uploads tile data only: the three beam tiles every 6th frame and the
  mirror tile 3 frames later, four frames each. No map cell is rewritten.
- **Glint.** Every 16 frames one `SPR_FX_IMPACT` spark (5 frames) lands on
  the next mirror or Wedge that has a beam cell beside it. One sprite at
  a time.
- Art source: `scripts/gen_sun_lattice_art.py` (hand-pixeled, `--preview`).
- Test: `scripts/test_sun_lattice_anim.py`.

