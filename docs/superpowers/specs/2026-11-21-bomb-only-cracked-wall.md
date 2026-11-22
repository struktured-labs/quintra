# Bomb-only cracked wall (Zelda-style subtle tell)

Date: 2026-11-21. Status: **implementation spec for #173.** Split from #171.
Carbon reviews this draft before ROM work; art is generated with GPT Image 2
and also reviewed by Carbon. This PR stays a draft; it is not merged here.

Source request (Carmelo, via #173 / the 2026-11-21 voice call):

> a new Zelda-style subtle cracked wall that only bombs can open — distinct
> from the existing gold cracked wall that any shot opens, with its own more
> subtle visual.

## 0. What already exists (do not duplicate)

| Thing | Where | Notes |
|---|---|---|
| **Gold cracked wall** `BGT_WALL_CRACK` (24) | `tiles.h`, `procgen.c` (~half of rooms, one border tile, never on a door lane), `BGPAL_CRACK` amber | Any player shot (`projectile.c`), Bomb Bag blast (`secondary_heavy.c`), Rift Bomb (`dungeon_tools.c` `tool_bomb`), and a heavy/morning-star-adjacent path that already calls `room_open_secret` for cracks, open it. Hookshot snags but does not open. Becomes a 2-tile `BGT_DOOR` via `room_open_secret`. Walking through sets `secret_pending` and enters an optional treasure vault. **Not restored** on room re-entry: procgen stamps a closed crack again. Echo Chime does **not** open gold cracks (only hidden `BGT_WALL` secrets and Veil tells). |
| **Hidden wall secrets** | `puzzle.c` `HIDDEN_SECRET_SHOT/WALK/PUSH`; `puzzle_try_hidden_shot`; `puzzle_chime_reveal` | Look like ordinary `BGT_WALL`, with a floor tell. Any shot or bomb that hits the wall can open SHOT secrets. **Echo Chime opens them.** Persistence: `run_state.dungeon_phase` bits `RUN_HIDDEN_SECRET_BIT`. |
| **Veil / secret merchant mouths** | `secret_merchant.c`; `2026-11-16-secret-merchants.md` | Host cell is a dead-end / off-role room. Kinds include BLAST (floor cracks + rubble) and others. Echo Chime **glints, does not open.** Persistence in `secret_shop`. |
| **Farfold Cache** | `run_state_dungeon_cache_cell()` | One optional dead-end per dungeon. Not a bomb-wall problem. |
| **Bomb Bag (B item)** | `secondary_heavy.c` `PROJ_AUX_FUSE_BOMB` | 3x3 tile blast on fuse expiry. Currently opens gold cracks, pots/lattice/dens, and hidden `BGT_WALL` shot secrets. **PR #169 (`fix/bomb-mp-cost`) and `fix/bomb-will-scale` edit the fire/cost half of this file, not the blast tile loop.** This work only adds one `else if` in that loop. |
| **Rift Bomb (dungeon tool)** | `dungeon_tools.c` `tool_bomb` | 7x7 tile burst around the hero, then 8-way `PROJ_BOMB` shots. Already opens gold cracks and hidden walls. `PROJ_BOMB` shots would also open gold cracks via `projectile.c`; they must **not** open the new tile. |
| **Echo Chime** | `dungeon_tools.c` `tool_chime` | If the Veil host is here, `secret_merchant_chime()` glints the tell. Otherwise `puzzle_chime_reveal()` **opens** every remaining hidden secret in the room. No per-frame cost. |
| **Tile budget** | `tiles.h` | Every index 0–127 is named. 128–163 share sprite VRAM (item icons, beams). `room_tile_walkable()` treats 40–63 as walkable (Hexa / colossus / map glyph range), so a bomb wall must **not** use 40–63 without a hot-path exclusion. |

## 1. Goal and non-goals

**Goal.** Add one new dungeon wall tile that careful players can spot and casual
players can miss. Only a bomb blast (Bomb Bag or Rift Bomb) opens it. It must
never be mistaken for the gold `BGT_WALL_CRACK`, never block required progress,
and stay open for the rest of the current dungeon (including Continue).

**Non-goals.**

- No change to gold `BGT_WALL_CRACK` art, palette, shot-open rules, or the
  fact that gold cracks do not persist across room re-entry.
- No change to hidden-secret Chime behavior (`puzzle_chime_reveal` still opens
  `HIDDEN_SECRET_*`).
- No change to Veil merchant entrance verbs in v1 (BLAST / STONE / THICKET
  stay). A bomb wall may appear **in** the Veil host room as a second, optional
  vault mouth; it is not the only way into the stall.
- No Riftwild bomb walls in v1 (dungeon only).
- No per-frame shimmer, sparkle, or proximity scan (slowdown is the top
  priority). Chime and one-shot open FX only.
- No merge, no itch/MiSTer/rivalmage deploy.

## 2. Art

One 8x8 BG tile, 4 GBC colors, **plain wall palette** (`BGPAL_WALL`,
`stage_pal[stage][1]`), never `BGPAL_CRACK`.

- Start from `bgt_wall_brick` (slot `BGT_WALL` 2): running-bond brick with
  mortar lines. The new tile must be nearly that wall.
- Add **one faint hairline crack** (a 1-pixel, slightly darker seam, not a
  second material) and a slightly darker mortar joint so a careful player can
  catch it in a still frame. No gold, no glow, no rune, no hole, no missing
  brick.
- Casual players should walk past it; it must still be findable once the
  player knows to look, and must not vanish on later stage palettes (test at
  least Stage 1 stone and one warmer later wall pal).
- Quantize with GPT Image 2 (`gpt-image-2.6-sunburst`). Key is sourced on
  blackmage via `source /home/struktured/projects/cowir-sprites/setenv.sh` and
  is never printed, logged, or committed. Log spend.
- Carbon reviews 8x (and 3x) crops of: normal brick, new bomb wall, and gold
  `bgt_wall_crack` side by side, and rejects the art if it is invisible **or**
  confusable with the gold crack (palette or silhouette).

Stored as `const u8 bgt_wall_bomb[16]` next to `bgt_wall_brick` in
`src/render/sprites_gen.c` / `.h`.

## 3. Tile index

`#define BGT_WALL_BOMB 71`, aliased with the Compass-only legend letter
`BGT_MAP_LABEL_B`.

Why 71:

- **Solid by default.** `room_tile_walkable()` does not include 64–71, so the
  tile is a wall without a new comparison on the collision hot path.
- **Free during play.** 71 is only loaded as the SELECT-map letter "B".
  `tiles_load_dungeon_bg()` already runs on every `room_enter`, including
  pack/Compass resume, so the bomb-wall pattern is restored automatically
  once it is added to that loader.
- **Not in the #172 boulder range.** Rune-boulder work is expected to add a
  tile near `BGT_GATE_BOULDER` 100–104. This work does not touch those
  defines or `waygear.h`.
- **Not 128+.** Those indices share sprite VRAM with item icons (`SPR_ITEM_*`
  starts at 128) and would glitch whenever a pickup is on screen.
- **Not 40–63.** That range is walkable (Hexa / colossus / map glyphs).

Comment in `tiles.h` must spell out the alias and the resume restore.

`attr_for_tile` / `tiles_area.c` return `BGPAL_WALL` (same as `BGT_WALL`),
never `BGPAL_CRACK`.

## 4. Opening rules

A `BGT_WALL_BOMB` is solid until a **bomb blast** opens it, then it uses the
existing `room_open_secret(tx, ty)` path (2-tile doorway, `SFX_DOOR`, vault
mouth). Walking through the opened mouth sets `secret_pending` and enters
an optional treasure vault, exactly like a shot-open gold crack. This is
intentional: the reward is optional loot, not a graph shortcut.

**Opens (bomb blast only):**

1. Bomb Bag fuse expiry in `secondary_heavy_update` — add
   `else if (t == BGT_WALL_BOMB) room_open_secret(...)` next to the existing
   `BGT_WALL_CRACK` branch in the 3x3 blast loop. Do not touch MP cost,
   fuse length, or Will scaling in this file.
2. Rift Bomb `tool_bomb` — the same one-line `else if` in the 7x7 tile scan.

**Does not open:**

- Player shots, enemy shots, `PROJ_BOMB` fragments after the Rift burst
  (those go through `projectile.c`, which must treat `BGT_WALL_BOMB` as
  solid and must **not** call `room_open_secret`).
- Morning star / hookshot / boomerang / heavy swing. Hookshot snags it like
  a wall (`hookshot.c` solid list). Morning star does not gain a new open.
- Echo Chime (see §5).
- `puzzle_try_hidden_shot` (that stays `BGT_WALL`-only).

**Solid lists.** Add `BGT_WALL_BOMB` wherever `BGT_WALL` or `BGT_WALL_CRACK`
is already treated as a blocking surface in the projectile / hookshot /
hostile-shot tails, so shots die on it instead of passing through. This is
a correctness fix, not a new per-frame system.

Opening also sets the persistence bit (§6) and may `sram_save_run()` the
same way other one-shot room events do.

## 5. Echo Chime

`tool_chime` keeps today's order: Veil tell glints without opening; otherwise
`puzzle_chime_reveal()` still opens hidden secrets.

Additionally, after that existing work, scan the **room border only**
(the only legal placement) for `BGT_WALL_BOMB`. Each hit gets the existing
`glint()` FX used by Cave Light / Veil Chime (no new sprite, no per-frame
timer). Play `SFX_TICK` if at least one bomb wall was found. **Do not** call
`room_open_secret`.

Cave Light (`do_glints`) may also glint a bomb wall once per room, the same
way it already glints gold cracks. Still no open.

## 6. Placement

Dungeon only. **Two rooms in stages 1–3, three rooms in stages 4–9**,
seed-stable.

Eligible local cells, all of which must pass:

- Not the entry cell, not a town, not Riftwild.
- Not a mission role (`mission_graph_cell_is_role`: trial, sigil, warden,
  waystone, deep warden / switch / gate).
- Not the public shop (`size-3`), sanctuary (`size-2`), or boss (`size-1`).
- Prefer degree-1 dead-ends, including the Farfold cache cell and the Veil
  host cell when those are legal. Then any other off-role cell. This is the
  same instinct as `secret_merchant_host_cell()`.

In a chosen room, stamp **one** 2-adjacent-friendly border tile (the same
"never on a door lane" rule as gold cracks: skip north/south cols 9–10 and
east/west rows 8–9). Prefer a `BGT_WALL`. If a gold `BGT_WALL_CRACK` landed
on that tile, **replace it** — that room keeps one optional vault, and it
becomes bomb-only. Never stamp on `BGT_DOOR`.

**Required progress is never behind one.** The mouth is a vault overlay, not
a graph exit, and the host room is never a required lore/service cell. A
player who never finds a bomb can still finish the dungeon.

Precompute the 2–3 host cells once per dungeon from `run_seed` +
`bosses_beaten` (a small helper, banked, not in the room hot bank). Procgen
only asks "is this local cell a host?" after the existing gold-crack stamp
so RNG streams for crates, spikes, and pots stay unchanged.

## 7. Save and room-state persistence

Append `u32 bomb_walls_open;` to `run_state_t` (bit `local` for cells 0–29).
Current `run_state_t` is ~70 bytes; SRAM stores `sizeof` in a `u8`, so four
more bytes fit. Older suspends load with the new field zeroed
(`sram_migrate` / size-prefixed copy already used by `powerup_shrines`).

- Set the local-cell bit when the wall is opened.
- On room enter, after procgen stamps a closed bomb wall, if the bit is set,
  call `room_open_secret` on that tile before `room_draw_tilemap` so the
  doorway is already there (and a re-entry into the vault still works).
- Clear the field in `run_state_init` and `run_state_begin_dungeon` (same
  lifetime as `dungeon_puzzles` / `dungeon_phase`). Continue mid-dungeon
  keeps the bits.
- Gold cracks are unchanged and still do not persist.

## 8. Performance

Slowdown is the top priority. This feature adds:

- No per-frame scan.
- One extra `else if` in two already-rare blast loops.
- One extra case in `attr_for_tile` (room draw, not the 60 Hz entity path).
- One extra comparison in projectile solid tails that already switch on
  wall-class tiles.
- Chime / Cave Light border scans only when those tools fire.

`scripts/test_performance.py` floors must not regress: fixed-roster **167**,
dense **135** (per 180 loop frames).

## 9. Coordination

- Base on current `main`. Keep the `secondary_heavy.c` edit to the blast
  tile loop only. Expect a trivial merge with PR #169 / `fix/bomb-will-scale`.
- `#172` boulder readability may add its own tile and touch `tiles.h`. Do
  not edit gate tiles 100–104, `waygear.h`, or adjacent boulder comments.
  If both land, rebase and keep 71.
- Do not edit the gold-crack procgen RNG block except to optionally replace
  a crack that landed on a bomb-wall host tile *after* that block.

## 10. Tests and previews

- New `scripts/test_bomb_wall.py`: seed-stable placement count and
  eligibility (never on a required cell or door lane); shots / morning star
  / hookshot do not open; Bomb Bag and Rift Bomb do; Chime glints and leaves
  the tile closed; leaving and re-entering the room (and a Continue
  suspend/resume) keeps it open; a new dungeon clears the bits.
- Existing `scripts/test_new_game_start.py` (including Continue) must pass.
- Existing secret / tool tests (`test_hidden_secrets.py`,
  `test_dungeon_tools.py`, `test_secret_merchants.py`, `test_sram_compat.py`)
  must stay green. Extend SRAM size expectations if they hard-code the
  current `sizeof`.
- Headless build+test on blackmage, one script, log to a file, short
  pass/fail summary.
- Previews at 3x in `/workspace/quintra-bombwall/`: a room PNG before
  (closed bomb wall in context), after (opened door), and a side-by-side
  strip of normal brick / bomb wall / gold crack.

## 11. Implementation sequence

1. Land this spec. Carbon review (chunked, capped, spend logged). Fold any
   required fixes back into the spec before ROM changes.
2. GPT Image 2 tile; quantize to 4 colors in the wall palette; Carbon art
   check against the brick and gold-crack references.
3. Code: define + loader + art, solid/attr cases, blast open, Chime/Cave
   Light glint, procgen placement, persist/restore, tests, previews.
4. Carbon review of the final diff.
5. Draft PR linked to #173. Do not merge.
