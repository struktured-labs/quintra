# Basilisk tiers and bigger bombs

Date: 2026-11-18. Follows `2026-11-17-new-monster-types.md` (#144).

Carmelo, after playing #144: the bombs should explode more; the laser
monster's sprite is weak, so make it a larger basilisk, and add variations
with increasing laser widths.

## 1. Fuse Hurler blast

**Goal.** A bomb burst that reads as an explosion and stays fair.

- **Art.** A 4-frame GPT Image (gpt-image-2.6-sunburst) burst sheet is
  quantized to one 16x16 quadrant per frame. It is drawn as a 32x32 sprite,
  the quadrant mirrored four ways (16 OAM). The frames are:
  1. flash star (t 0-2)
  2. fireball (t 3-7)
  3. fire-and-smoke ring (t 8-13)
  4. embers (t 14-21)
- **Debris.** At t 2, four FX chunks (a GPT-derived debris tile) spawn at the
  corners of the damage square and live for 12 frames.
- **Shake and sound.**
  - `room_shake(3, 14)`, up from `(1, 6)`.
  - A new `boom_sfx`: a CH4 noise thump (NR42 0xF7, NR43 0x71) plus a falling
    CH1 growl, with both channels claimed through `sfx_claim_channels` so the
    score cannot swallow it.
  - A quieter crackle tail plays at t 7.
- **Fair hitbox.**
  - Damage is a Chebyshev square of radius 18 from the blast centre to the
    hero centre (x+8, y+12). That is the fireball's 16-px reach plus the
    half-hurtbox.
  - Damage is live only for t < 10, which is the flash and fireball frames.
    The smoke ring is harmless.
  - The blast does 1 heart, at most once per 24 iframes, and never kills
    (HP floor 1). This is unchanged.
- **Tell.**
  - The fuse is unchanged at 40 frames.
  - Eight markers sit on the exact edge of the damage square: corners and edge
    midpoints alternate every 4 frames. In the last 16 frames they flash gold.
  - The tick SFX doubles its rate at the end.
- **Self-burst.** The close-range wind-up (28 frames of body flashing) now uses
  the same full blast, centred on the Hurler. It shows the same eight
  blast-edge markers around the Hurler during the wind-up.
- **Two blasts.** If two blasts overlap in time, they alternate frames, so
  neither burst is ever invisible.

## 2. Basilisk family (AI_BEAM_CASTER)

| Tier | ID | Name | Lanes | Beam | HP | Tell / beam / cooldown | Pal | Stage |
|---|---|---|---|---|---|---|---|---|
| 1 | 40 | Ley Basilisk | 2 | 16 px | 14 | 40 / 36 / 100 | 7 green | Ember Depths (w 6) |
| 2 | 42 | Sun Basilisk | 3 | 24 px | 20 | 44 / 40 / 96 | 4 red | Golden Temple (w 8, replaces 40) |
| 3 | 43 | Nox Basilisk | 4 | 32 px | 26 | 48 / 44 / 90 | 6 Void stage | Void Sanctum (w 8, replaces 40) |

Notes on the table:
- Names are capped at 12 characters by content validation, which is why they
  are not "Glare" or "Void" Basilisk.
- Symbol `LEYBEAM` is kept for id 40.
- Every stage pool still sums to 100.

**Body.**
- A 32x32 coiled serpent-king in three GPT Image poses per tier (idle, walk,
  charge/fire with open jaws and an energy orb), quantized to the 4-colour
  sprite format.
- Only one tier is resident at a time, in bank-1 OBJ:
  - 176..191 idle, 192..207 walk, 10..25 fire.
  - Blast 26..39, 214..215; debris 216.
- These ranges sit in the free gaps of the bank-1 OBJ map. Vignettes and bosses
  may overwrite them, so the art reloads on room entry. It also reloads lazily
  the first time a basilisk ticks or a blast starts.
- The entity keeps an 8x8 core at bank-0 OBJ 219, now blank (removed from the
  enemy anim atlas). `new_monsters_draw` appends the 16 body OAM after the
  allocator's entities and mirrors the columns when the basilisk faces left.
- The body is at x-8..x+23, y-16..y+15. The 15x15 hitbox is the coil.
- Drift checks the whole body footprint, so the head never pokes through a
  wall. Spawn nudges the body onto open floor.
- **Poses.**
  - The fire pose (open jaws, orb) shows from frame 16 of the charge.
  - Walk and idle alternate every 16 frames.
  - The body strobes gold during the charge.
  - The status tint and hit flash match other enemies.

**Beam.**
- **Lock.** At charge start the basilisk turns, then locks the cardinal
  direction nearest the hero, measured from its mouth.
  - Lanes are centred on the mouth: 2, 3 or 4 tile lanes.
  - Each lane runs to its own first non-floor cell, up to 24 tiles, so a
    pillar shadows only the lanes it blocks. Every live cell can carry the
    stamp, so there is never invisible damage.
- **Telegraph.**
  - Every lane cell is stamped with BG tile 63, which shows ghost dots. The
    stamp is written right after VBlank at 16 cells per frame, so even the
    widest lane (4 x 24) is fully marked within 6 frames of a 48-frame tell.
    Easy adds 25% to the tell.
  - At fire, a single 16-byte upload swaps tile 63's art to the glowing beam,
    so the whole lane flips on one frame however wide it is.
  - The beam shimmers between two frames every 4 frames.
- **Damage.**
  - The hit test uses the stamped lane table with a 1-px hurtbox inset.
  - 1 heart, 20 iframes, never lethal.
- **Limits.**
  - One beam on the map at a time, and one basilisk per room (they share the
    beam state and the art slot).
  - The restore is one `room_draw_tilemap()` from the RAM map, which gives
    exact tiles and attributes. It keeps `new_monsters_in_room` up until the
    floor is back.
  - Room entry forces the tile-63 art to re-upload, because bosses and
    vignettes may have replaced it.

## 3. OAM

- The extras (blast 16, fuse markers 4, basilisk body 16) are written after
  the allocator's entities and below the fixed specialist slots 35..39. A
  blast is written before a body, so the hazard wins any shortfall.
- Fully visible blocks take a u8 fast path.
- When a crowded room leaves no room, the extras borrow the top of the entity
  range on alternate frames.
- The extras never raise `entity_oam_high`. They park their own leftovers, so
  a frame that overruns VBlank cannot DMA a half-parked burst.

## 4. Budgets

- No home code. No initialized globals in banked files.
- The AI changes are in bank 25 (`enemy_new_ai.c`, 2442 bytes free).
- The appended-OAM drawing is split into `src/game/enemy_new_draw.c`
  (`#pragma bank 255`, autobanked to 23). It shares the bomb state through
  `game/enemy_new_draw.h`.
- The art is `src/render/basilisk_art.c` (`#pragma bank 255`), generated by
  `scripts/gen_basilisk_art.py` from `scripts/basilisk_art_grids.json`. The
  raw 1 MB renders stay out of the repo; `--from-gpt DIR` re-quantizes them.
- `check_rom_layout` passes, with home ending at 0x3D02 (unchanged).
- `test_performance`: generated 180, fixed 172, dense 169 out of 180. These
  match main.

## 5. Tests

- **`test_leybeam.py`.** For each tier, the hero sits at six rows. The test
  asserts:
  - a hit if and only if the hurtbox overlaps the expected 16 / 24 / 32-px band
  - the tell is at least 40 / 44 / 48 frames.
- **`test_fuse_hurler.py`.** In addition to the existing checks, the blast
  hits at dx 12, 16 and 18 and misses at 20 and 24.
- **`test_enemy_identity.py`.** Sprite and palette entries for 40, 42 and 43.
- **`record_basilisk_gifs.py`.** 4x GIFs of each tier firing and of a blast.
- **Fixture.** The specialist fixture now raises `new_monsters_in_room` the
  way a real spawn does. Without it, bombs never ticked in these tests.

## 6. Carbon review (gemini-4-carbon), applied

The verdict was "ship with fixes". Applied:
- Re-upload the lane art and reset the OAM high mark on room entry.
- Restore the lane with one exact redraw.
- Lanes stop at non-floor cells, so no live cell is unstamped.
- Bomb sprites park when off-screen in scrolling rooms.
- Twin blasts alternate.
- Show the self-burst edge markers.
- Fix the spec text: fire pose timing and stamp latency.

Not applied:
- Per-row `set_bkg_tiles` batching. The stamp is the #144 path, and perf is
  unchanged.
- Vault Hand slot-39 parking. This is pre-existing and outside this change.
