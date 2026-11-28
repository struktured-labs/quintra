# Fractal tendril variants (Fold Star) and a tendril-parallel laser

Date: 2026-11-27. Issue #263. Docs only: nothing here is built or measured.

Carmelo, from a hardware playtest: the regular monster that contracts and
expands its tendrils should get harder variants that expand recursively. Each
tendril expands into its own smaller fractal of tendrils, N levels deep (N up
to about 3). N grows with difficulty and stage. Base stays N=1 early, harder
variants from about stage 3, N=3 late. Two follow-ups the same day: it "isn't
annoying enough as it is", so add a ranged attack, ideally a laser parallel to
the tendrils; and the laser alternates every attack between diagonal and
perpendicular, with a telegraph that shows which is coming.

Conventions in this document:

- Stages are numbered 1..9 as the player sees them. Source uses 0..8
  (`content/src/stages.rs:9-182`). "Stage 3" is Ember Depths, source id 2.
- Every statement about current behaviour cites file:line. Anything I could
  not confirm in source says **not verified**.
- Every new number is a **proposal** unless it carries a citation.

## 1. Which monster, and how it works today

### 1.1 Identification (my inference)

I think Carmelo means the **Fold Star** (enemy id 11, symbol `FOLD_STAR`,
`content/src/ids.rs:60`, `content/src/enemies.rs:173-188`). Reasons:

- It is the only regular enemy whose authored description is "expands ...
  then contracts": `AiScriptId::Replicator`, "Expands into diagonal echoes on
  an irregular cadence, then contracts into a short vulnerable phase"
  (`tools/crates/quintra-content/src/enemy.rs:40-42`).
- Its art is "contracted diamond with four false rays"
  (`tools/crates/quintra-assets/src/grids.rs:349-358`), and its expanded
  phase throws four copies of itself outward on the diagonals
  (`src/game/enemy_foldstar.c:70-77`). On a real screen that reads as four
  arms going out and coming back.
- It first appears in Ember Depths, which is stage 3
  (`content/src/stages.rs:75`). That matches "harder variants from about
  stage 3".

No source file calls anything on this enemy a "tendril". The word is
Carmelo's. This identification is an inference and is open question 1.

Other candidates I looked at and rejected:

| Candidate | Why it could fit | Why I think it is not it |
|---|---|---|
| Mire Heart floor roots (`src/game/mire_roots.c:1-3`) | Branching roots that grow and wither, with forks (`mire_roots.c:29-73`) | Stage-5 boss attack, not a regular monster |
| Hexa Dragmar limbs (`src/game/enemy_hexa.c:50`) | Limbs | Hidden boss |
| Vine Coil, id 29 (`content/src/enemies.rs:413-425`) | Name | It is a `Spinner`: orbits and fires seed pairs (`src/game/enemy_spinner.c:18-71`). Nothing extends or retracts. Stage 2 only (`stages.rs:52`) |
| Bramble Sprite 27, Void Halo 31, Sunwheel 24 | "Orbiting thorn pair" and similar (`content/src/ids.rs:73-80`) | Orbiters, no expand/contract cycle. AI not read line by line: **not verified** beyond their id comments |
| Mire Spore 17 | Radial burst then "regrowing" (`enemy.rs:46-48`) | A mine with a fuse, not arms |
| Rift Ooze 15 | Splits and reforms (`stages.rs:70-73`) | Splits into bodies, no arms |

### 1.2 Stats and rosters

- HP 18, contact damage 2 half-hearts, speed 56, score 60, weakness 0x08
  (Shadow), poise 2 (`content/src/enemies.rs:182`). `fold_star_update` never
  reads `stats.speed` (`src/game/enemy_foldstar.c:17-84`), so the speed stat
  has no effect on its movement.
- Sprite tile 72, `SPR_ENEMY_FOLD_STAR` (`src/render/tiles.h:303`), two
  animation frames (`grids.rs:2176`, frame B at `grids.rs:1608-1617`).
  Authored palette is `OBJ_PAL_GOLD` (`enemies.rs:178`), but the AI
  overwrites the palette on every phase flip (below).
- Hitbox 6x6 (`src/game/enemy_spawn.c:62`).
- Pools, as (stage, weight out of 100):

| Stage | Name | Fold Star weight | Source |
|---|---|---|---|
| 1 | Crystal Caverns | not in pool | `stages.rs:33` |
| 2 | Verdant Hollow | not in pool | `stages.rs:52` |
| 3 | Ember Depths | 8 | `stages.rs:75` |
| 4 | Frost Vault | not in pool | `stages.rs:96` |
| 5 | Toxic Mire | not in pool | `stages.rs:114` |
| 6 | Shadow Keep | 12 | `stages.rs:133` |
| 7 | Golden Temple | not in pool | `stages.rs:148` |
| 8 | Bloodmoon | 17 | `stages.rs:164` |
| 9 | Void Sanctum | 13 | `stages.rs:180` |

- It is also on the Bane Brute's status-ally list
  (`src/game/enemy_new_ai.c:875-883`, `904-915`), so a Brute room can convert
  a slot into a Fold Star in a stage whose pool has one. The conversion path
  itself (`convert_slot_to`) is **not verified**.
- A hit from it can apply STOP (`src/game/status.c:344`).

### 1.3 State machine

Code: `src/game/enemy_foldstar.c` (bank 6), entered from
`src/game/enemy_ai.c:636` without a definition pointer.

Scratch bytes: `state` 0 = contracted, 1 = expanded; `ai_data[1]` phase
clock; `ai_data[2]` beat selector; `ai_data[3]` diagonal rotation counter
(`enemy_foldstar.c:18-20`); `ai_data[7]` is the shared hit-flash timer
(`src/game/entity_draw_run.c:94`).

| Phase | Length | What happens | Source |
|---|---|---|---|
| Contracted (`state` 0) | 60 frames (`closed_ticks`) | Palette 5, `SFX_WEAK` on entry. Vulnerable. One `enemy_try_step` diagonally toward the player every 4 frames | `enemies.rs:186`, `enemy_foldstar.c:31-36`, `40-48` |
| Expanded (`state` 1) | 83 frames (`open_ticks`) | Palette 0. Shots are rejected. On an uneven 7 / 13 / 9-frame beat it sheds four echoes and the core takes one diagonal step | `enemies.rs:186`, `enemy_foldstar.c:27-30`, `58-83` |

- Spawn sets `state` to a random 0..7 with the clock at 0
  (`enemy_spawn.c:42`), so 7 in 8 Fold Stars start contracted and 1 in 8
  start expanded (`enemy_foldstar.c:22-37`).
- **Telegraph today.** The only tell is the palette flip and the `SFX_WEAK`
  on contraction. Nothing announces the expansion in advance. The step size
  of `enemy_try_step` is **not verified**.
- **The "tendrils" today.** Each beat spawns four `ENT_FX` entities at
  (x±d, y±d) with d = 6, 8, 10 or 12 px, cycling with `ai_data[3]`, each
  living 16 frames, drawn with the core's own tile in palette 5
  (`enemy_foldstar.c:71-76`). The spawn is skipped when fewer than 10 entity
  slots are free (`enemy_foldstar.c:65-70`).
- They are drawn as **OAM sprites**, one 8x8 sprite per echo, through the
  ordinary per-frame allocator (`src/game/entity_draw_fast.h:14-15`,
  `33-41`). They have no fixed OAM slots. Each one also takes one of the 32
  entity slots.
- By my arithmetic (beats 7 to 13 frames apart, 16-frame life) two rings are
  alive most of the time, so about 8 echo sprites, briefly 12. That count is
  not measured.
- **The tendrils do not hit.** `fx_spawn` sets hitbox 0 and damage 0
  (`src/game/entity.c:242-243`) and the hostile scan only considers
  `ENT_ENEMY` and non-player `ENT_PROJECTILE` (`src/game/combat.c:644-647`).
  Only the 6x6 core hurts, by contact, in both phases; the contact loop has
  no Fold Star state check (`combat.c:650-659`). Easy clamps every hit to 1
  half-heart (`combat.c:693`).
- **How it is damaged.** While expanded, `enemy_special_reject_hit` eats the
  shot with an impact spark and `SFX_HIT` (`src/game/enemy_patrol.c:186-193`,
  routed from `src/game/combat_shot_hit.c:83-92`). Contracted, it takes
  damage like any enemy.

So "hitbox per tendril" in the issue is new behaviour, not a tuning of
something that exists.

### 1.4 Existing tests

- `scripts/test_ember_movement_roster.py` asserts Ember generates a Fold
  Star (lines 21-40).
- `scripts/test_enemy_identity.py:41` pins its tile and name.
- `scripts/quintra_balance_bot.lua` has Fold Star routing
  (`fold_star_guard`, line 1451; `fold_star_shot_lane`, line 2231).
- I found no test of its timing, echoes or damage window.

## 2. Engine budgets

### 2.1 OAM

- 40 hardware sprites. The player metasprite owns OAM 0..3
  (`src/game/entity.c:101-102`, `275-277`).
- Everything else is laid out fresh each frame from a cursor that starts at
  4: 16 sprites for a giant, 4 for a 16x16 body, 1 otherwise
  (`entity.c:275-283`). That leaves **36** slots.
- The HUD is the window layer, not OAM (`src/render/hud.c:140-151`).
- Bosses take fixed blocks out of the 36: Serpent starts the cursor at 16
  (`entity.c:283`), Cinder Rex owns 16..39 (`src/game/cinder_big.h:12-13`),
  Hexa limbs own 4..23 (`src/game/entity_draw_core.h:18-20`). None of these
  share a room with regular Fold Stars as far as I can tell (**not
  verified** for mini-boss rooms).
- The newer specialists append OAM after the allocator, capped at slot 35,
  and borrow the top of the entity range on alternate frames when the scene
  is full (`src/game/enemy_new_draw.c:37-43`, `58-62`). Slots 36..38 are
  used by the raft / champion priority case (`src/game/room.c:2630`,
  `src/game/water_ride.c:82`).

### 2.2 Ten sprites per scanline

Hardware shows the first 10 sprites on a line. The existing answer is
rotation: the logical start index advances every second frame
(`entity_anim_counter >> 1`), so overflow becomes flicker instead of a
permanently missing sprite (`entity_draw_core.h:33-40`, `entity.c:275-280`).
There is no per-scanline counting anywhere; nothing in source knows how many
sprites share a line. The player contributes 2 per line across its 16 rows.

### 2.3 Entity table

`MAX_ENTITIES` is 32 and `entity_t` is 28 bytes with a compile-time assert
(`src/game/entity.h:9`, `60-61`). Test scripts hard-code the 28-byte stride
(`scripts/test_performance.py:121`), so the struct cannot grow.

### 2.4 BG-tile precedents

| Effect | How it draws | Tile slots | Source |
|---|---|---|---|
| Leybeam (basilisk beam) | Stamps one shared BG tile along cardinal lanes; ghost dots during the charge, then a single 16-byte art upload flips every cell to solid beam on one frame. At most 16 units of work per VBlank. One beam on the map at a time; a second caster waits. Ends with a full `room_draw_tilemap()` | VRAM bank 1, BG 63 | `enemy_new_ai.c:38`, `45-58`, `318-352`, `485-486`; `tiles.h:327-330` |
| Mire Heart roots | Up to 24 cells, four branches of six steps with an outer fork. Ghost preview, then one step hot every 4 frames, then wither. Includes diagonal vein tiles. Hit test is five hurtbox samples against a per-pixel "on the vein" rule. `room_tilemap` stays floor, so shots pass over | Bank 0, BG 55..63 (the nine colossus slots) | `mire_roots.c:1-3`, `24-73`, `250-289`, `291-345` |
| Cinder Rex fire pools | Painted into BG with a warning ring first, saved floor restored afterwards | Bank 1, BG 64..71 | `cinder_big.h:7-15`, `cinder_big.c:22-48`, `106-131` |
| Sun Lattice beams | Horizontal, vertical and crossing beam tiles; one fixture uses an h-flipped tile for the other diagonal | Bank 1, BG 56..62 | `tiles.h:104-108` |

The Mire roots are close to a one-enemy, one-level version of what #263
asks for, including the fork.

The colossus slots 55..63 are loaded only on boss rooms
(`src/game/room.c:1024-1027`) and source calls them "combat-unused"
elsewhere (`room.c:2538-2539`).

### 2.5 Performance test

`scripts/test_performance.py` counts game-loop iterations
(`_loop_frame_counter`) completed in a 180-LCD-frame window in CGB double
speed. 180 means every frame was on time.

- **generated**: the real opening room. Floor is 165 minus 3 per body above
  14 (lines 183-208).
- **dense**: 12 long-lived hostile projectiles on open floor, no enemies.
  Floor **175** (lines 215-244, 276-281).
- **fixed-roster**: a planted 16-crawler room, 3 on camera and 13 off.
  Floor **174** (lines 99-174, 251-255, 272-274).

None of the three fixtures contains a Fold Star. They protect the shared hot
paths (entity update, draw allocator, combat scan), not this enemy. Two
consequences:

- Anything added to those shared paths has to be free when no fractal enemy
  is in the room. `new_monsters_in_room` is the existing pattern: one byte
  tested once per frame (`entity.c:293-295`).
- This feature needs its own perf fixture (section 6).

One more trap: uploads that happen before the run seed is mixed shift boot
timing and desync the fixed-roster fixture (`stages.rs:26-33`,
`test_performance.py:247-250`). Nothing in this design may upload at boot.

## 3. Design (all numbers are proposals)

### 3.1 N per stage

N depends on stage and difficulty, not on a new enemy id. Stages whose pool
has no Fold Star are listed so the table is complete if a pool changes; this
spec does not change any pool.

| Stage | Name | In pool today | Normal N | Easy N |
|---|---|---|---|---|
| 1 | Crystal Caverns | no | 1 | 1 |
| 2 | Verdant Hollow | no | 1 | 1 |
| 3 | Ember Depths | yes (8) | 1; elite or alpha = 2 | 1 |
| 4 | Frost Vault | no | 2 | 1 |
| 5 | Toxic Mire | no | 2 | 1 |
| 6 | Shadow Keep | yes (12) | 2 | 1 |
| 7 | Golden Temple | no | 2 | 2 |
| 8 | Bloodmoon | yes (17) | 3 | 2 |
| 9 | Void Sanctum | yes (13) | 3 | 2 |

- Stage 3 keeps the base lesson for the first sighting. Only elite or alpha
  Fold Stars (`EF_ELITE`, `EF_ALPHA`, `entity.h:25-26`) show N=2 there.
- Easy is one level behind and never reaches 3.
- Endless loops after stage 9: N=3 on Normal, 2 on Easy.
- N is read once at spawn and kept in the entity.

### 3.2 Geometry

N=1 stays exactly as it is today: the four pulsing echo sprites, harmless.
The fractal form is used only when N is 2 or 3.

For N >= 2 the tendrils live on the 8-px tile lattice, measured in cells
from the core cell (0,0). Each level is a smaller, rotated copy of the one
before:

- **Level 1**: 4 arms on the diagonals, 3 cells each.
  NE arm: (1,-1), (2,-2), (3,-3).
- **Level 2**: at each level-1 tip, 2 branches at right angles to the arm,
  2 cells each. From (3,-3): (2,-4), (1,-5) and (4,-2), (5,-1).
- **Level 3**: at each level-2 tip, 2 branches at right angles again, 1 cell
  each. From (1,-5): (2,-6) and (0,-4). From (5,-1): (6,-2) and (4,0).

The other three arms are mirror images. Lengths go 3, 2, 1; branch count is
2 per tip; every segment is diagonal; the angle between parent and child is
90 degrees.

Worked counts:

| N | Cells per arm | Total cells | Unique cells | Bounding box |
|---|---|---|---|---|
| 1 (lattice form, not used) | 3 | 12 | 12 | 7x7 cells, 56 px |
| 2 | 3 + 4 = 7 | 28 | 28 | 11x11 cells, 88 px |
| 3 | 3 + 4 + 4 = 11 | 44 | 40 | 13x13 cells, 104 px |

At N=3, neighbouring arms share four cells on the axes: (0,±4) and (±4,0).

A cell that is not plain floor stops its tendril there, and everything
downstream of it does not grow. This is the Leybeam lane rule
(`enemy_new_ai.c:386-398`).

The screen is 160x144, so an N=3 bloom is a 104-px square. That is large on
purpose (it is the late-game version) but it is open question 4.

### 3.3 Rendering options

Sprites per scanline, one enemy, if every cell were an 8x8 sprite. All cells
of one enemy sit on one 8-px lattice, so rows never straddle.

| N | Sprites incl. core | Worst row | Which row |
|---|---|---|---|
| 1 (today, about 8 echoes) | about 9, briefly 13 | 4 to 6, not measured | two rings' upper or lower pairs |
| 2 | 29 | 4 | rows ±1 and ±2 |
| 3 | 41 | 6 | rows ±2: cells x = ±2, ±4, ±6 |

Add 2 for the player when it stands on the same rows. A single N=3 enemy
plus the player is 8 of 10 on the worst line, leaving 2 for every shot and
every other enemy on that line. Two N=3 enemies on the same rows is 12 plus
the player.

**Option A: all OAM, with a cap and flicker rotation.**

- As entities it does not fit: 40 FX entities exceed the 32-slot table.
- As appended OAM (the `enemy_new_draw.c` pattern) N=3 needs 41 of the 36
  available slots before a single shot is drawn. It would flicker at half
  rate at best, on hardware where Carmelo already found readability
  problems.
- A tips-only version (draw just the end of each segment) is 25 sprites at
  N=3 with a worst row of 3. It fits, but the "arm" is then implied dots, and
  25 of 36 slots is still most of the frame.
- Cost per frame: 29 to 41 OAM writes per enemy, every frame.
- Good: tendrils can follow a moving core at pixel precision.

**Option B: BG tiles for every tendril cell.**

- 0 OAM and 0 scanline cost at any N. The core stays one sprite.
- Cost is VRAM writes only when a cell changes: 2 writes per cell (tile and
  attribute, as in `mire_roots.c:310-314`).
- The core must sit still on the lattice while expanded. Today it steps on
  every beat (`enemy_foldstar.c:79-82`); the fractal form drops that step.
- Tendrils cannot overlap walls, which is fine: they stop at them.
- Risk: anything that redraws the map erases the stamps. Section 3.8.

**Option C: hybrid, level 1 as sprites, outer levels as BG.**

- 4 to 12 sprites for level 1, BG for levels 2 and 3.
- Sprites move at pixel precision and BG cells are on the lattice, so the
  two halves only line up if the core is lattice-locked anyway. At that
  point the sprites buy nothing over option B and cost OAM.

**Recommendation: option B for N >= 2, today's sprites for N=1,** plus one
small sprite touch: while a level is growing, up to 4 short-lived spark FX on
the newest cells (existing `SPR_FX_IMPACT`, tile 33, `tiles.h:290`), skipped
when fewer than 10 entity slots are free, same rule as today
(`enemy_foldstar.c:70`).

Worst-case sprites on one scanline under the recommendation:

| Case | Sprites on the worst line |
|---|---|
| One fractal enemy, any N, not growing | 1 (core) |
| Growing, sparks on | 1 + 2 sparks = 3 |
| Laser telegraph pips (section 3.9) | core + 2 pips = 3 |
| Same, player on that row | 5 |

### 3.4 Telegraph timing and reverse contraction

The expanded phase of a fractal Fold Star replaces the 83-frame beat phase
with a scripted clock. Per level: ghost first (dotted cells, harmless), then
grow one cell every 4 frames from the base outward, each cell hot as it is
drawn. This is the Mire root shape (`mire_roots.c:250-254`, `283-289`).

| Step | Frames | Notes |
|---|---|---|
| Root | 4 | Core snaps to the lattice. `SFX_TICK` |
| L1 ghost | 24 | Dotted on all 12 L1 cells |
| L1 grow | 12 | 3 cells x 4 frames |
| L2 ghost | 20 | Starts only when L1 is fully out. `SFX_TICK` |
| L2 grow | 8 | 2 cells x 4 frames |
| L3 ghost | 20 | N=3 only. `SFX_TICK` |
| L3 grow | 4 | 1 cell |
| Hold | 24 | Everything hot |
| L3 retract | 8 | Goes harmless at once, erased after 8 frames |
| L2 retract | 8 | Tip inward, 4 frames per cell |
| L1 retract | 12 | Tip inward, 4 frames per cell |

- Totals: N=2 expanded for 112 frames, N=3 for 144. Both fit the u8 clock.
- Contraction is strictly reverse order: the outermost live level goes
  first, and within a level the tip goes first.
- A retracting cell is harmless from the first frame of its retract step.
  The player is never hit by something that is visibly leaving.
- The existing 60-frame vulnerable window follows (84 with the laser,
  section 3.9).
- Easy: every ghost step is 25% longer, the same rule Leybeam uses
  (`enemy_new_ai.c:468`).
- Fairness check. Stepping off a ghosted cell needs about 6 px. The slowest
  hero moves 0.8 px/frame (`src/game/player.h:12-19`), so 8 frames. The
  shortest ghost is 20 frames, 2.5 times that.
- Pockets. At N=3 the arms enclose diamond-shaped areas with one-cell exits.
  A player standing in one when it blooms is not hit; they are fenced in for
  the hold. I think this is a feature. It is open question 5.

### 3.5 Hitboxes and collision

Three ways to test the player against up to 40 cells:

| Plan | Cost per frame | Accuracy |
|---|---|---|
| One AABB per cell | up to 40 box tests per enemy | Good, but the cost scales with N |
| One AABB per tendril | 4 to 28 tests | Bad: a box around a diagonal arm is mostly empty floor |
| Tile-grid lookup | 5 lookups per enemy, constant | Exact per cell |

**Recommendation: tile-grid lookup.**

- Take the five hurtbox sample points the roots already use: centre and four
  corners of the 6x6 hurtbox (`mire_roots.c:338-345`; hurtbox at
  `entity.c:142-157`).
- For each sample, compute its cell offset from the core. If either axis is
  beyond 6, stop.
- Look up |dx|, |dy| in a 7x7 ROM table (49 bytes; the pattern is mirror
  symmetric on both axes). The entry gives level, step within the level, and
  a cell index.
- The cell hits if its (level, step) is inside the current growth frontier,
  its bit is set in this enemy's wall-clip mask, and the sample is within
  1 px of the diagonal line through the cell. The last rule is the roots'
  `on_vein` test (`mire_roots.c:256-270`), so grazing a cell's empty corner
  is free.
- The wall-clip mask is 6 bytes per fractal enemy (one bit per cell, 44
  cells), built once at the Root step by walking each tendril outward.

Damage: 1 half-heart per touch, ordinary i-frames, and it cannot take the
last half-heart. That is the Leybeam rule (`enemy_new_ai.c:515-518`). Open
question 6.

How it is damaged does not change: only while contracted. Shots pass over
tendril cells because `room_tilemap` is untouched.

### 3.6 Per-frame cost and the perf floors

Estimates, none measured:

| Work | When | Estimate |
|---|---|---|
| Grid hit test | Every frame while any cell is hot | 5 lookups, low hundreds of cycles per enemy |
| Cell stamping | Only on a grow or retract step | 4, 8 or 16 cells per step, 2 VRAM writes each |
| Clip-mask build | Once per bloom | 44 tile reads, spread over the 4-frame Root step |
| Rooms with no fractal enemy | Always | One byte test per frame |

Rules that keep the floors:

1. **One writer.** A single stamp queue for the whole room, flushed right
   after VBlank at no more than 8 cells per frame. Leybeam's limit is 16
   units (`enemy_new_ai.c:38`, `336`). A 16-cell L3 step takes 2 frames.
2. **One level change at a time.** A fractal enemy may start a ghost, grow
   or retract step only when the queue is empty; otherwise its clock holds.
   Leybeam does the same (`enemy_new_ai.c:485-486`).
3. **Staggered clocks.** Fractal enemies in one room start their expanded
   phase at least 32 frames apart.
4. **Cap per room.** At most 2 Fold Stars run the fractal form, and at most
   1 of those at N=3. Extras are demoted to N=1 at room population. They are
   not despawned, so room population and room-clear counts do not change.
   (Existing caps do despawn: `enemy_new_ai.c:893-902`, `1062-1068`.)
5. **Nothing in the shared hot loops.** The hit test and clocks run inside
   the Fold Star's own update, reached through one far call from
   `enemy_foldstar.c`. The flush hook is gated on one byte, like
   `leybeam_flush_pending` (`src/render/palette_bg_commit.c:75`).
6. **No boot-time upload.** Tendril art is uploaded at room entry, and only
   when the room holds a fractal enemy.

With these, the 174 and 175 fixtures should not move, because they contain
no Fold Star and the only shared cost is byte tests. That is a prediction,
not a measurement.

### 3.7 Recommendation and build order

Recommended: BG-tile fractal for N >= 2 (option B), tile-grid collision,
runtime N from a per-stage table, laser option 1 (section 3.9).

Slices, each shippable and testable alone:

1. **Depth plumbing.** Per-stage N table in content, emitted to C. N stored
   on the entity at spawn. Per-room cap and demotion. No visible change.
   Test: N per stage and difficulty.
2. **N=2, harmless.** New file, art upload at room entry, lattice lock,
   ghost / grow / hold / reverse retract for levels 1 and 2. Wall clipping.
   Test: stamp order and reverse order.
3. **Collision.** Grid lookup, damage, i-frames. Test: hit on a hot cell, no
   hit on ghost or retracting cells.
4. **N=3.** Level 3, the queue's two-frame split, the N=3 cap.
5. **Perf fixture** for a fractal room, and re-run the three existing
   floors.
6. **Laser, diagonal only**, with telegraph.
7. **Laser alternation** and the cardinal direction.
8. **Balance pass** on hardware: ghost lengths, bloom size, laser cadence.

### 3.8 Risks found while reading

- **Leybeam wipes the map.** A basilisk beam ends with a full
  `room_draw_tilemap()` (`enemy_new_ai.c:331-334`). Ember has ids 11 and 40
  in one pool and Void has 11 and 43 (`stages.rs:75`, `180`), so a basilisk
  beam ending would erase live tendril cells. Fix proposal: tendrils, the
  laser and Leybeam share one "map effect" token, or the fractal code
  restamps after any full redraw.
- **Camera streaming.** Rooms wider than the view stream the BG as the
  camera moves (`entity.c:208-220` shows the wide-room path exists). Whether
  streaming rewrites cells a tendril has stamped is **not verified**.
- **Colossus slot ownership.** Section 4 reuses BG 55..63 in regular rooms.
  Mini-boss rooms, vignettes and the SELECT map are **not verified** as
  leaving those slots alone.
- **Free scratch bytes.** The design needs one byte of `ai_data`.
  `ai_data[4]` is written for elites in return-echo rooms
  (`src/game/enemy_weak_pattern.c:83-87`, reached from `enemy_ai.c:619-622`).
  `ai_data[5]` and `[6]` look free for a Fold Star but I did not check every
  writer (rare-enemy and status code): **not verified**.

### 3.9 Ranged attack: tendril-parallel laser

**What exists to reuse.**

- Leybeam: BG-tile floor beam, cardinal only, 2 to 4 lanes wide, ghost-dot
  tell then a one-frame art swap (`enemy_new_ai.c:45-58`, `318-352`,
  `463-528`). Timings 40 tell / 36 beam / 100 cooldown by default
  (`enemy_new_ai.c:464-466`). Its statics are single-instance and bank 25 is
  described as full (`enemy_new_draw.c:4`), so the code is a pattern to
  copy, not something to call.
- `SPR_FX_BEAM_HEAD` / `SPR_FX_BEAM_TAIL`, OBJ 158 / 159
  (`tiles.h:447-448`): a head sprite plus one trailing FX sprite, used for
  the player's beam shots (`src/game/projectile_relic.c:79-95`). It is a fat
  bullet, two sprites long. Whether the art reads on a diagonal is **not
  verified**.
- Boss projectile art is drawn through `boss_projectile_draw`
  (`entity_draw_core.h:65-68`). I did not find a diagonal beam in it:
  **not verified**.
- Enemy shots: `projectile_spawn_enemy_v(x, y, vx, vy, damage)`
  (`enemy_patrol.c:263-264`).

**When it fires.** In the contracted phase, when no tendril is out. That
gives "no unavoidable overlap with the tendril expansion" by construction:
the two attacks are never live together, and they never compete for the
stamp queue. It also puts a threat into the window where the player is
attacking, which is the "more annoying" part.

For Fold Stars with the laser the contracted phase becomes 84 frames
(today 60):

| Step | Frames (N=1 / 2 / 3) | What the player sees and hears |
|---|---|---|
| Hunt | 24 | As today: bright core, steps toward the player |
| Tell | 36 / 32 / 30 | Core stops and snaps to the lattice. Ghost dots appear on the exact lane cells. Four pip sprites sit 6 px from the core on the firing directions. Ticks at start, 16 and 8 frames before firing (Leybeam's rhythm, `enemy_new_ai.c:493`, `498`) |
| Beam | 12 / 16 / 20 | Lanes flip to solid on one frame. `SFX_ROAR`, small shake (`enemy_new_ai.c:505-506`) |
| Recover | remainder | Lanes fade to ghost for 4 frames, then clear |

The core stays vulnerable for all 84 frames.

**Scaling with N.**

| N | Beams | Length | Fires |
|---|---|---|---|
| 1 | 4 | 5 cells (40 px) | every second contraction |
| 2 | 4 | 8 cells (64 px) | every contraction |
| 3 | 4 | to the first wall, at most 12 cells (96 px) | every contraction |

- Beams are one cell wide and stop at the first non-floor cell.
- Damage 1 half-heart, 20 i-frames, cannot take the last half-heart
  (Leybeam's rule).
- Easy: no laser at N=1. At N=2 the tell is 25% longer and it fires every
  second contraction.

**Alternation.** Each attack flips direction: diagonal, then perpendicular,
then diagonal.

- State: one bit, bit 0 of `ai_data[5]` (0 = diagonal next). It flips when a
  beam ends. A new Fold Star starts at 0, so its first laser is diagonal.
  Bits 1..2 of the same byte hold N. Subject to the scratch-byte check in
  section 3.8.
- What "perpendicular" means here is ambiguous, and I am flagging it. The
  tendrils occupy **both** diagonal axes at once: today's echoes go to all
  four diagonals (`enemy_foldstar.c:73-76`), and every segment of the
  proposed fractal is diagonal too. The line at 90 degrees to a NE-SW
  tendril is NW-SE, which is also a tendril direction. Two readings:
  - **Reading 1 (proposed):** diagonal attack = the four diagonals (an X).
    Perpendicular attack = the four cardinals (a +). Strictly that is 45
    degrees off, not 90, but the cardinals are the only directions not
    parallel to any tendril, and it gives two clearly different attacks.
  - **Reading 2:** two beams per attack. Attack A fires NE and SW, attack B
    fires NW and SE. That is a true 90 degrees, but both attacks are
    diagonal and each is parallel to half the tendrils.
  - Open question 7.

**Telegraph per direction (not colour alone).**

| | Diagonal attack | Cardinal attack |
|---|---|---|
| Ghost dots | On the X lanes | On the + lanes |
| Pips | Four at the core's corners | Four at the core's edge midpoints |
| Sound | Single ticks | Double ticks, 4 frames apart |

The ghost dots are stamped on the same cells the beam will use, from the
same lane table, so the tell cannot disagree with the beam.

**Dodge fairness.**

- Leaving a one-cell lane from its centre takes about 5 px sideways for the
  cardinal attack and about 7 px of cardinal travel for the diagonal one. At
  0.8 px/frame that is 7 and 9 frames. The shortest tell is 30 frames.
- Safe lanes. During the diagonal attack all four cardinal approaches are
  clear, so a melee hero attacks from N, E, S or W. During the cardinal
  attack the diagonals are clear. Each attack therefore closes the lanes
  the previous one left open, which is the point of the alternation; the
  tell is what keeps that fair.
- The beam and the tendrils never overlap in time. The Root step of the next
  bloom starts only after the lanes are cleared.
- Two laser Fold Stars in one room cannot fire together (the shared token),
  so the player never faces an X and a + at once.

**Drawing options.**

| | Option 1: BG-tile beam | Option 2: fast projectile stream |
|---|---|---|
| What it is | Lane cells stamped as ghost, flipped to beam by one art upload | 3 shots per direction, 4 frames apart, existing hostile projectiles |
| OAM | 4 pips during the tell, 0 during the beam | 12 sprites. A horizontal stream is 3 on one line, two of them 6, plus core |
| Entity slots | 0 | 12 of 32. That is exactly the dense fixture's load (`test_performance.py:225`) |
| VRAM | Up to 48 cells ghosted over 6 frames; 1 art upload to fire; cells cleared over 6 frames | none |
| Tile slots | 2 BG slots (section 4) | none |
| Reads as | A laser. The tell is the lane itself | Bullets. Needs a separate tell |
| Existing interactions | New hit test. Shield and Wolfkin wave do not block it unless coded | Shield, wave and vortex already eat hostile shots (`combat.c:619-636`) |
| Dodge | Leave the lane during the tell | Leave the lane, or time the gaps |
| Perf | Hit test is a few compares, only while the beam is live | 12 more entities in update, draw and the combat scan every frame |

**Recommendation: option 1.** It costs no sprites on the lines where the
budget is tightest, the tell is the lane itself, and it matches the request
for a laser. Option 2 is the fallback if the BG conflicts in section 3.8
turn out to be worse than expected; it needs no VRAM work at all.

Perf against the floors: same argument as section 3.6. Nothing runs in a
room with no Fold Star. In a room with one, the laser adds at most 8 cell
writes per frame during the tell and the clear, and a handful of compares
during the 12 to 20 beam frames.

## 4. Costs

Rough. No build was run, so no bank headroom was read from a map file.

**ROM (estimates).**

| Item | Bytes | Where |
|---|---|---|
| Fractal clock, stamp queue, clip mask, hit test | 1,600 to 2,200 | new `src/game/enemy_fractal.c`, `#pragma bank 255` |
| Tables: 7x7 lookup, cell list, timings | about 130 | same file |
| Laser: lanes, tell, alternation, hit test | 700 to 900 | new `src/game/enemy_fractal_laser.c`, `#pragma bank 255` |
| Laser art: diagonal ghost, beam, beam2 | 48 | same file |
| Call site in `enemy_foldstar.c` | 20 to 40 | bank 6 (fixed `#pragma bank 6`, `enemy_foldstar.c:1`) |
| VBlank flush hook | about 12 | beside `palette_bg_commit.c:75` |
| Per-stage N table | 18 | generated |

Bank 6's free space is **not verified**. If it is one of the banks with
about 300 bytes left, the call site still fits, but nothing else should go
there. `scripts/check_rom_layout.py:61-67` fails the link under 256 free
bytes.

**VRAM. No new slot is claimed; these existing ones are reused:**

| Use | Slot | Today's owner | Why it is free in a regular room |
|---|---|---|---|
| Tendril cells: ghost bud, two diagonal veins, junctions | Bank 0, BG 55..63 (`BGT_COLOSSUS_VOID`..`BGT_COLOSSUS_HORN`, `tiles.h:81-89`) | Boss projections; Mire roots | Loaded only on boss rooms (`room.c:1024-1027`). The Mire root set already has the dotted bud and both diagonals (`mire_roots.c:256-270`, `301-308`), so the art is reused as well as the slots |
| Cardinal laser | Bank 1, BG 63 (`LEYBEAM_BG_TILE`, `tiles.h:330`) | Leybeam | Same ghost and beam art (`enemy_new_ai.c:50-58`). Shared through the one-effect token |
| Diagonal laser | Bank 1, BG 64 (`CINDER_FIRE_TILE`, `cinder_big.h:14`) | Cinder Rex fire pools | Uploaded by the Ember boss load (`cinder_big.c:43-47`). The other diagonal is the same tile with the BG x-flip attribute, as Sun Lattice does (`tiles.h:105`) |
| Core | OBJ 72 | Fold Star | unchanged |
| Tell pips | OBJ 28 (`SPR_BULLET`, `tiles.h:285`) | bullets | always resident |
| Growth sparks | OBJ 33 (`SPR_FX_IMPACT`, `tiles.h:290`) | impact FX | always resident |

The tile-loading function that holds the Mire root art is
`tiles_load_colossus_bg(4)` (`src/render/tiles_colossus.c:369-370`, `455`).
Whether all nine root tiles come from that one call is **not verified**.

**WRAM (estimates).** About 34 bytes: two fractal instances at 13 bytes
(6-byte clip mask, 4 lane lengths, core cell, stamp cursor) plus about 8
bytes of queue and token state. `entity_t` stays 28 bytes.

**Content and schema.**

- `StageTheme` gains `fold_depth: [u8; 2]` (Normal, Easy), validated 1..=3
  and non-decreasing by stage. Emitted as a 9x2 table.
- No new enemy ids, no pool changes, no change to procgen's RNG draws. That
  is the reason for runtime N over the basilisk-style tier ids
  (`content/src/ids.rs:89-92`): new ids would need pool slices, 12-character
  names (`enemy.rs:99`) and identity-test rows.
- `Replicator { open_ticks, closed_ticks }` is unchanged. Fractal and laser
  timings live in the new C file's table for now; moving them into content
  is a follow-up.

## 5. Open questions

1. Is the Fold Star the monster you meant? If it was something else, most of
   section 1 changes and the design may not transfer.
2. Should N=1 stay exactly as it is (harmless echo sprites), or should even
   the base tendrils hurt?
3. Stage 3: base only, with N=2 on elites (proposed), or N=2 for every Fold
   Star from Ember on?
4. Bloom size. N=3 covers 104 px of a 160-px screen with lengths 3, 2, 1.
   Too big? A 2, 1, 1 version is 72 px but the levels are harder to tell
   apart.
5. Pockets: is fencing the player in for the 24-frame hold fun or cheap?
6. May a tendril or the laser take the last half-heart? Proposed: no, same
   as the basilisk beam.
7. "Perpendicular": cardinals (X then +, proposed) or the other diagonal
   pair (two beams per attack)?
8. Laser on the base N=1 Fold Star on Normal (proposed, every second
   contraction), or only on N >= 2?
9. The laser stretches the vulnerable window from 60 to 84 frames while the
   bloom gets longer too. Is a longer, more dangerous window the right
   trade, or should the window stay 60?
10. Fold Star is absent from stages 4, 5 and 7. Add it there, or leave the
    gaps?
11. Should the Bane Brute's ally conversion be allowed to create fractal
    Fold Stars?

## 6. Test plan

Headless PyBoy scripts, same harness as `scripts/test_stage_archetypes.py`
(`generated_room`) and the WRAM symbol lookup in
`scripts/test_performance.py:17-21`. Existing coverage to keep green:
`scripts/test_ember_movement_roster.py`, `scripts/test_enemy_identity.py`,
`scripts/test_performance.py`.

| Script (new) | Asserts |
|---|---|
| `scripts/test_fold_star_base.py` | Regression for today's behaviour before anything changes: 60 contracted / 83 expanded, shots rejected only while expanded, echoes are `ENT_FX` with hitbox 0 |
| `scripts/test_fractal_depth.py` | Plant a Fold Star in each stage on Normal and Easy; stored N equals the table in 3.1. A third fractal Fold Star in a room is demoted to N=1, and the enemy count is unchanged |
| `scripts/test_fractal_growth.py` | Read the BG map each frame. Level k cells appear only after level k-1 is complete; ghost lasts at least the table value; retract order is L3, L2, L1, tip first. After the cycle every cell matches the RAM tilemap again |
| `scripts/test_fractal_walls.py` | Fold Star beside a wall: no cell is stamped on or beyond the wall, and no hit registers there |
| `scripts/test_fractal_hit.py` | Hero on a hot cell loses exactly 1 half-heart and gains i-frames; on a ghost cell, a retracting cell or a cell's empty corner, no damage; at 1 half-heart, no death |
| `scripts/test_fractal_oam.py` | With an N=3 bloom fully out, count OAM entries per scanline from the shadow OAM: the enemy contributes at most 3 on any line, and total OAM in use does not rise with N |
| `scripts/test_fractal_laser.py` | Three consecutive attacks are diagonal, cardinal, diagonal. For each: the ghost cells during the tell equal the hot cells during the beam; pips are at corners for diagonal and edge midpoints for cardinal; tell length is at least the table value (25% more on Easy); hero in a lane is hit, hero one cell off is not; no tendril cell is live while a beam is; two laser Fold Stars never have beams live on the same frame |
| `scripts/test_fractal_basilisk_coexist.py` | Ember room with a basilisk and a fractal Fold Star: a basilisk beam ending does not erase live tendril cells, and neither effect leaves stale tiles |
| `scripts/test_fractal_performance.py` | New fixture: 1 N=3 and 1 N=2 Fold Star plus 6 crawlers, 180-frame window covering a full bloom and a laser. Proposed floor 165/180, to be set from the first measurement |

`scripts/test_performance.py` must still report fixed-roster >= 174 and
dense >= 175 after every slice. Run
`scripts/test_procgen_parity.py` as well, to confirm no RNG draw moved.
