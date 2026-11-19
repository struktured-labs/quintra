# Ultima-depth state-machine puzzles

Date: 2026-11-19 · Status: **proposal for review, nothing implemented**
Ask (Carmelo, 2026-11-19), from a stream of *Ultima: Runes of Virtue DX*.
He has not reviewed the OBS VOD. Treat his examples as recollection, not
a room transcript. Companion study:
`2026-11-19-runes-of-virtue-puzzle-study.md`.

This PR is spec only. No gameplay code.

## North star

Quintra's feel, in Carmelo's words and in this order:

- The adventure feel of Zelda
- The ARPG feel of Final Fantasy Adventure
- The puzzle and animation style of Ultima
- The foundation is Penta Dragon (shmup meets Zelda)

The first three already describe the game we are shipping. This spec is
about the third line: puzzles that have Ultima's *shape*, not another
pass of "hit a switch, push a block, play the notes."

## Relation to earlier puzzle work

`2026-11-15-puzzle-variety-and-dungeon-wide-puzzles.md` is still the
inventory of what is in the tree (Push Seal, Rune Sequence, Deep Phase
Switch / Gate, Sun Lattice, Prism Toggle, Law Lock, hidden secrets,
music plates). This document does not replace it and does not reopen
Prism Toggle or Law Lock.

That work widened the vocabulary. This work changes the *depth*: a
floor or a large room becomes a state machine whose actions have
layered consequences, including monsters you cannot simply fight.

The 2026-11-15 solvability contract still applies until Carmelo says
otherwise: required rooms are solvable with base movement and melee;
class innates, B-items, waygear, Oaths, and the companion are
shortcuts, never requirements. Freeze and invincible bodies put real
pressure on that contract; see §6.3 and §9.

## 1. Goal

1. Teach and then demand Ultima-style depth: isolated floors or large
   rooms that rewrite themselves, where the player has to anticipate
   what a switch, a shot, or a monster will do next.
2. Add an invincible (or otherwise unfightable) monster that exists to
   make the player think: route, trap, or freeze, not DPS.
3. Add a freeze-all-monsters verb that works on those bodies.
4. Ship one **vertical slice** — a single authored showcase floor —
   that uses the new verbs together, including Carmelo's two set-piece
   patterns (fire-and-web with a rock-to-water bridge, and a turret
   whose shots churn the room state).
5. Leave open whether later puzzles live in one big room or are
   scattered across a dungeon. Recommend, do not decide.

## 2. Engine inventory (checked against `origin/main`)

Facts below were taken from headers and the small related sources
named here, plus the 2026-11-15 and 2026-11-18 specs already on main.
No full-repo walk.

### 2.1 Tiles and materials (`src/render/tiles.h`)

We already have floors, walls, pillars, crystals, pushable 16×16
`BGT_BLOCK` crates, `BGT_SWITCH` (commented as a **one-shot** pressure
plate: player or block), `BGT_SWITCH_PRESSED`, `BGT_PORTAL` (intra-stage
rift well), `BGT_SPIKES`, `BGT_POT`, `BGT_ARROW_TRAP` (Farfold cache
face), water as `BGT_WILD_WATER` / `BGT_GATE_WATER` (solid unless
Picsean or Tide Raft), and the Law / Prism barrier pair
(`BGT_PILLAR` / `BGT_CRYSTAL` / `BGT_FLOOR2`).

There is **no cobweb**. There is no general "this switch rewrites
class A to class B across the room" table. Prism Toggle and Dungeon
Law are two-state barrier flippers, which is the closest live writer
to steal from.

### 2.2 Room size and persistence

- Standard room: `ROOM_W` 20 × `ROOM_H` 17 (one screen).
- Wide / scrolling room: 31×31 tiles (248×248 px). A Runes of Virtue
  floor is 16×16 cells, 256×256 px (`ultima-rov-dx` `dungeons.md`).
  A wide Quintra room is the right unit for "the floor IS the puzzle."
- The tilemap is RAM. Suspend SRAM stores `run_state` + `player`, not
  a room bitmap. Rooms are rebuilt from the run seed plus a few
  persisted bits (`dungeon_puzzles`, `dungeon_phase`, `dungeon_law`
  bit 7, visit maps). Any new floor state must be a compact phase
  mask that the prepare step can replay, the same way Law Lock and
  Prism Toggle already work.

### 2.3 Enemies and AI

- 32 entity slots, 28-byte records. The flags byte is full
  (`EF_RARE` is `0x80` in `rare_enemy.h`). An invincible bit cannot
  be a new `EF_*` without breaking that layout.
- `enemy_load_def` (bank 25, with the new-monster AI) is the right
  place for a definition flag.
- Existing cousins: `AI_TURRET` (Sentry), shooters, basilisks, Vault
  Hand. Nothing is currently unkillable on purpose.
- Picsean Blizzard and Sauran Thunder apply `QSTATUS_STOP` for 8–12
  beats (about 1–1.6 s). Stop is a brief combat stagger (default 14
  beats of eight frames; elites cap at 6). One primary condition per
  actor; a later poison would replace a Stop freeze.

### 2.4 Pack tools and B items

| Tool / item | What it does today | Freeze? |
|---|---|---|
| Rift Bomb (`ITEM_ID_RIFT_BOMB` 40) | Pack charge. Breaks crystals, pots, crack walls; 8-way bomb shots; Sun Lattice strike. | No |
| Echo Chime (`ITEM_ID_ECHO_CHIME` 41) | Pack charge. Deletes hostile shots, reveals neighbor cells, pings a hidden secret. | No. Closest "silence the room" verb, but it only clears projectiles. |
| Mirror Shard (`ITEM_ID_MIRROR_SHARD` 42) | Pack charge. Reflects hostile shots and gives short i-frames. | No |
| Antidote (49) | Pack tool, cures DoT. | No |
| Bombs B-item (48) | Combat bombs. | No |
| Hookshot / Boomerang / Morningstar | B weapons. | No |
| Hero magic | B tap / hold when the hero power is selected. Blizzard stops one lane of bodies briefly. | Hero-locked, too short, not floor-wide. |

Do not overload the Chime. Freeze is a new verb.

### 2.5 SRAM, WRAM, banks

- Cart is MBC5 with battery SRAM. Bank 0 holds one suspend:
  `"QS"` + version + two u8 lengths + `run_state` + `player` +
  checksum. `sizeof(run_state_t)` itself is a u8, so the struct must
  stay under 256 bytes. It is currently about 70 (69 before
  `powerup_shrines`, then one appended byte). New fields must append
  and migrate, never shift old offsets.
- `dungeon_puzzles` bit 5 is still the only unused bit in that byte.
  Every `dungeon_phase` bit is in use. The vertical slice should aim
  at **zero new SRAM** and reconstruct from seed + room WRAM, using
  bit 5 only if the showcase floor must stay solved across a leave
  and a later re-entry.
- Home bank is tight and must not grow. `check_rom_layout.py` fails
  the build if home runs past `0x4000`. After recent monster work
  home was reported around `0x3CDB`–`0x3D02`. No new home code, and
  no initialized globals in banked `.c` files (init on first use).
- Put new puzzle logic in a `#pragma bank 255` file, next to Prism
  Toggle (bank 19) and Law Lock (bank 18). New AI stays in bank 25.
  Do not add this to the music / B-item / merchant banks (22, 24).
  Hook the writer and the shot-strike through an **existing**
  room-update or tile-strike banked dispatch (the Prism / Sun Lattice
  path), so home grows by 0 bytes and no new trampoline lands in
  bank 0.
- Performance floor in `test_performance` stays 167/180. A wide
  puzzle floor should be authored under the ordinary body and OAM
  caps (one turret, one fire-breather, one invincible roamer, no
  extra pack). Also check the mid-game biome's BG/OBJ VRAM budget
  before adding cobweb tiles, a gold plate, a pipes pip, and a new
  Jagger sheet.

## 3. Design principles

1. **A floor is a machine.** Each switch, shot, or body has a
   downstream effect the player can learn. No one-and-done plate that
   only opens the seal.
2. **Monsters are pieces, not only threats.** Some are tools (fire,
   weight, a shot that hits a switch). Some cannot be fought.
3. **Readable beats, not noise.** Semi-random churn is allowed only
   with a clear telegraph, a minimum time in each useful state, and a
   freeze that can freeze the churn when the room is in a state the
   player wants to keep.
4. **Authored first, procedural later.** Sun Lattice and Prism Toggle
   already prove a seeded, backwards-generated, solver-checked
   fixture. The first Ultima-depth floor should be authored the same
   way, not a generator of arbitrary state machines.
5. **Rebuild, do not snapshot.** Phase bits plus the seed replay the
   floor. Leaving and re-entering is a fair reset unless a "solved"
   bit has been earned.

## 4. Open question: one big room, or a puzzle scattered across a dungeon?

Carmelo asked and did not decide. This section lays out the trade and
a recommendation. It is not a decision.

| | One isolated floor / large room | Scattered across the dungeon's rooms |
|---|---|---|
| Feel | Closest to ROV: stairs cut the machine off. You see the whole state. | Closest to "the dungeon is one machine" from the 2026-11-15 spec (Law Lock, Deep Phase). |
| Memory | Almost free: WRAM only, rebuild on entry. | Needs a compact dungeon-wide mask, likely +1 SRAM byte, or a fight for leftover bits. |
| Fairness | A reset is "leave and come back" or a marked reset plate. Softlocks stay local. | A wrong flip in room A can trap you in room C. The director and Compass have to route over (cell × state), as Law Lock already does. |
| Readability | High. The web, the water, and the turret are on the same camera. | Lower. The player has to remember a door two rooms ago. |
| Production | One fixture, one solver, one GIF. Right for a vertical slice. | More rooms, more validation, easy to ship shallow again if we only sprinkle switches. |
| Risk | A 31×31 authored floor is a lot of on-screen work, but we already scroll those rooms. | We already have dungeon-wide Law Lock. A second dungeon-wide machine can collide with it. |

**Recommendation, not a decision:** ship the vertical slice as **one
isolated wide floor** (with at most a tiny anteroom for the freeze
pickup and the exit stairs). That matches Runes of Virtue, keeps SRAM
at zero, and is the honest test of depth. If the floor feels as good
as Carmelo remembers, a later pass can scatter the same verbs —
especially the turret-and-switch and Law-style material state —
across a dungeon, using the Law Lock validator as the template.

A hybrid is also on the table: the showcase stays one floor, and a
later dungeon uses a single two-state material law (already designed)
plus one invincible roamer in the halls. That is still not a decision.

## 5. Vertical slice (the thing to build first)

**One authored wide floor, mid-game (Frost Vault or Golden Temple),
optional or tool-reward, never on the only path to a Colossus until
the contract in §9 is settled.**

The floor, in one sentence: a parked fire-breather and two rewrite
switches let you burn a cobweb off a crate and build a water bridge
those creatures can cross, while an invincible roamer and a
switch-hitting turret force you to freeze, route, and time the
churn.

Beats, in teaching order:

1. **Anteroom:** a freeze **pedestal** that always dispenses one local
   charge when the hero holds none and the room timer is at 0. A
   marked **reset plate** next to the entrance restores the floor
   (and the crate) without forcing a stair exit. The player does not
   need a run-long Pack tool.
2. **Invincible roamer** on the first lane. Hits do not flash. The
   freeze stops it long enough to cross. A side alcove can also trap
   it if the player closes a door instead.
3. **Rewrite switches.** Switch A raises rock barriers in a fixed
   region (not the pushable crate). Switch B turns those barriers
   into water. A short dead-end teaches the pair before they matter.
4. **Cobweb and crate.** A crate the player needs is behind a cobweb.
   A button or plate releases (or aims) a fire-breather. Bait its
   facing so the fire burns the web, then push the crate. The
   fire-breather is a puzzle tool: same invincible flag as the
   roamer, or it respawns from a kennel if its slot dies. The
   companion holds fire and ignores puzzle-tool bodies. Wolfkin
   fire, Rift Bomb, and combat Bombs may burn a web as a shortcut;
   they must not skip a trigger that the fire-breather's release
   is supposed to set.
5. **Water bridge.** A second web sits across a gap the fire-breather
   must cross. Switch A then B lays a short water path **for the
   creature only**. The hero walks a parallel dry catwalk, so the
   existing Picsean / Raft rule is never involved and the floor is
   not class-gated. This is the default layout; §9.3 is recorded
   only if Carmelo wants the hero in the water instead.
6. **Turret churn,** once the player has the verbs. A stuck shooter,
   its gold plate, and the exit door all share **one camera
   quadrant** so the tell is never off-screen. The turret pings the
   plate and cycles the exit doors. Freeze it when the door is
   open, then leave. No pack is spawned on shut (the floor already
   has enough bodies).

Success is: the floor is solvable without a FAQ, the state is always
visible, a softlock is reset by the entrance plate or by leaving, and
`test_performance` does not drop below 167/180 on this fixture.

**Suspend:** if the hero suspends mid-floor, resume places them at
the entry stairs with the unsolved floor rebuilt from the seed
(phase 0). A solved bit, if set, keeps the exit open. This avoids
rebuilding rock or cobweb on top of a mid-puzzle position, because
SRAM does not store the live tilemap.

## 6. New systems (spec only)

### 6.1 Material rewrite

A packed rule: `{ from_class, to_class, region or room }`. A toggle
switch, a shot-switch, or a scripted button applies one rule. The
writer paints tiles immediately, like Prism Toggle. Rules must be
reversible enough that the prepare step can replay the current phase
from the seed.

First materials:

- Rock / crate (`BGT_BLOCK` or a pillar-sized rock).
- Water (walkable for puzzle creatures; hero follows the existing
  Raft / Picsean rule unless the slice marks a short "anyone may
  wade" bridge explicitly).
- Cobweb (new tile): blocks walking and crate-push; cleared by fire
  (enemy fire, Bomb, or Wolfkin fire). Ordinary melee does not cut
  it, so the fire-breather stays necessary. Shots from non-fire
  heroes do not clear it.

Collision: if Switch A would raise rock on a cell the hero, crate,
roamer, or fire-breather occupies, the switch **refuses** (dud clunk)
instead of embedding a body in a wall. Closing doors use the same
rule, and also nudge an overlapping actor one tile out if they stand
in the doorway. Switch B only converts the **fixed rock-barrier
region**, never a crate the player has pushed off its home cell.

Budget: a rewrite touches at most **8–12 tiles** and is amortized
over 2–3 frames, in the Law Lock / Prism Toggle style. No full 31×31
`set_bkg_tiles` blast in one frame.

Cost: M. New tiles + a banked writer. 0 SRAM. A few WRAM bytes for
the live phase mask (2–4 bits is enough for the slice).

### 6.2 Invincible monster

A definition flag, not an `EF_*`. Provisional name: **Stone Jagger**
(ROV's rock beast), or a Quintra name if Carmelo prefers something
less on the nose. Mid-size, slow roam, cardinal or slightly drunk
walk, **cannot use doors**, contact damage 1 heart, never lethal,
**no HP flash, no damage, no status except the room-level freeze.**

Used only in authored puzzle rooms. The procgen pack roller must not
select it. Max one on the showcase floor.

Neutralize by: freeze, closing a door on it, routing around, or
(later) a teleport crush. Not by DPS, Bombs, or Oaths.

Cost: S–M. One enemy id, simple roam AI in bank 25, art via GPT
Image 2.6 when we implement, not in this PR.

### 6.3 Freeze-all item

A floor-local freeze verb, working name **Rime Pipes** (Pan Pipes, in
Quintra words). Not a Chime variant, not a hero spell, not a
B-weapon. For the vertical slice it is **not** a new Pack item id
and it does not touch `player` inventory or save migration. It is a
room-local charge with a small HUD pip. A later PR can promote it
to a Pack tool (`ITEM_ID` after Antidote 49) once Carmelo wants it
run-long.

- On use: set `room_freeze_beats` (WRAM, one u8), ticked every
  **four frames** like other timed status clocks, clamped at 255
  with no relic or shrine scalar in this slice. All enemy bodies
  and parked turrets skip AI and do not start new shots until it
  reaches 0. In-flight shots keep moving, so a freeze is not a
  free "delete the volley" (that remains the Chime's job).
- Duration: **45 beats** (180 frames, 3 s) on Normal, **56 beats**
  (224 frames, just under 4 s) on Easy, **38 beats** (152 frames)
  on Hard. Visible ice tint (reuse Stop's blue) and a short chime
  so it does not look like a crash.
- Invincible bodies freeze too. That is the point.
- Does not spend or replace `QSTATUS_STOP`, so a poisoned hero or a
  burning enemy stays readable.
- Charges: the pedestal in §5.1 is infinite-dispense (one charge
  whenever the hero holds none and the timer is at 0). The reset
  plate also restores a spent charge. The player cannot run out.

Cost: S–M. Room timer + local pickup. 0 SRAM, 0 `player_t` growth.

### 6.4 Pressure plates and the teleport skip (Phase 3)

Parked. The slice's plates only toggle rewrite rules and doors.
Spawn-on-plate plus a same-room `BGT_PORTAL` skip is a later floor,
so Phase 1–2 do not spend ROM or tests on a verb the showcase never
uses.

### 6.5 Pickup wall traps (Phase 3)

Parked. `BGT_ARROW_TRAP` already exists and can fire a volley when a
tagged pickup is taken, with visible mouths and a 20-frame flash.
Not built until a later floor actually uses it.

### 6.6 Turret that hits a switch (state churn)

This is Carmelo's second set-piece, specified so it stays fair.

**Body.** One parked shooter, stuck in an alcove or just off the
main floor, using the turret AI. It may be ordinary or invincible
(if invincible, freeze is the only way to pause the churn). It does
not walk.

**Cadence.** Base period **96 frames** on Normal (about 1.6 s),
**120** on Easy, **80** on Hard, plus a jitter of ±16 frames so the
rhythm is not a metronome. After a hit that actually flips the
state, a **lockout pauses the fire timer** for 64 frames (80 on
Easy). Minimum time in a state is therefore lockout plus the next
period (144 frames / ~2.4 s on Normal), which is enough to cross
the door after the tell. The lockout is not a shorter window that
expires before the next shot. If playtests still feel streaky, drop
the 30% random lane and alternate switch-lane / hero-lane
deterministically.

**Aim.** 70% of shots use the cardinal or 8-way heading nearest the
hero (so standing on a switch is a real risk). 30% pick a random
cardinal from a short authored list that always includes the switch
lane, so the churn continues even if the hero hides. Never fire in
an untelegraphed diagonal through a one-tile gap.

**Telegraph.** 24 frames (32 Easy) before each shot: body flash,
a one-tile aim spark, and if that shot's lane crosses the switch,
the switch plate flashes gold. Audible tick. This is the same
language as Veil Magus / basilisk tells, not a new one.

**Switch hitbox.** A 16×16 gold plate (the Push Seal socket size),
not an 8×8 pixel-perfect tile. In the slice, **only this turret's
shots** count. Player shots, Bombs, and reflected volleys do not
flip it, so Beat 6 cannot be sniped from off the plate. A later
floor may allow player shots as a shortcut. The plate has a
one-frame cooldown so a wide blast cannot flip the state twice.

**Layout.** The turret alcove, the gold plate, and the exit door
share one camera quadrant (all three visible at once on the 160×144
viewport). The tell is never off-screen during Beat 6.

**States it may flip,** authored, not a generic bitfield. The
showcase uses a two-state cycle: **Doors Open** and **Doors Shut**.
No pack is released on shut. No third state in the slice. It must
not rewrite the rock / water / cobweb machine; that machine stays
player-driven. The turret is a clock you have to watch, not a
random material scrambler.

**Death and crush fail-safes.** If the (vulnerable) turret dies,
in-flight turret shots lose switch-flip authority and the doors
fail-safe to **Open**. Closing doors never embed the hero: they
nudge an overlapping actor out, or they refuse to shut on that
cell (same rule as §6.1).

**Freeze and invincible.** Freeze pauses the turret's cadence and
holds the current state. In-flight shots still fly and can still
hit the plate, so freeze just after a telegraph is a skill shot,
not an undo. An invincible turret cannot be killed to stop the
clock; a vulnerable one can, which is the easier teaching version.
Recommend a **vulnerable turret for the slice**, and an invincible
variant as a later harder floor.

**RAM and state cost.** WRAM: 1 byte timer, 1 byte phase, 1 bit
"pack already released." 0 SRAM. On leave, the floor resets unless
the solved bit is set. The turret does not run while the room is
unloaded, so there is no off-screen flip.

**Cost:** M. Shot-hits-switch extends the existing strike path used
by Sun Lattice and Prism orbs.

## 7. Phases

0. **This PR.** Spec + study, Carbon review, Carmelo's answers on
   §4 and §9.
1. **Primitives, still behind a fixture flag.** Rewrite writer
   (capped region, refuse-if-occupied), toggle plates, cobweb tile,
   room freeze timer and local Rime Pipes pedestal, invincible def
   flag, shot-hits-switch. Headless unit tests, no dungeon placement
   yet. No pack-spawn plates, no pickup wall traps, no Pack item id.
2. **Vertical slice.** The wide floor in §5, backwards-authored,
   Rust mirror + solver + C↔Rust parity in the Sun Lattice style,
   GIF evidence, `test_new_game_start.py` and `test_performance`
   still green.
3. **Only after the slice feels right:** decide §4, then either
   scatter the verbs or build a second isolated floor (invincible
   turret, pack-spawn + portal skip, pickup wall traps, lure /
   teleport-crush).
4. **Art.** GPT Image 2.6 for the invincible body, cobweb, and
   pipes icon, at implementation time, not in this PR.

## 8. Tests (when we implement, not now)

- Rewrite rules replay from a phase mask after a leave / re-enter.
- Cobweb blocks a crate, fire clears it, melee does not.
- Invincible body: no HP change, no flash, freeze holds it, a closed
  door stops it.
- Rime Pipes freezes every body including the invincible one, does
  not delete in-flight shots, and does not clear `QSTATUS_POISON`.
  The pedestal refills when the hero holds none and the timer is 0.
- Turret: tell lasts at least 24 frames and is on-camera with the
  door; lockout pauses the fire timer; a 16×16 plate hit from the
  turret flips once; player shots do not flip; freeze holds the
  door state; turret death opens the doors; leaving or the reset
  plate restores an unsolved floor; suspend resume is at entry.
- Fire-breather death respawns it (or it is invincible). Rewrite
  refuses if a body occupies a target cell.
- `check_rom_layout` (home unchanged), performance ≥ 167/180,
  `test_new_game_start.py`.

## 9. Questions for Carmelo

1. **The open question in §4.** One isolated floor, scattered across
   a dungeon, or the hybrid? The recommendation is "isolated floor
   first."
2. **Required-route contract.** May a mandatory room demand the
   freeze item, or must freeze always sit on that floor (or stay in
   optional / tool-reward rooms)?
3. **Water and the Raft.** The slice default is "creature wades, hero
   uses a dry catwalk," so no class gate. Do you want the hero in
   the water instead?
4. **Names.** Stone Jagger and Rime Pipes, or different copy?
5. **Turret in the slice:** vulnerable (can be killed to stop the
   clock) or invincible (freeze only)? Recommendation: vulnerable
   first.
6. After you watch the VOD, does the fire-and-web floor still match
   what you played, or should the slice be rewritten to a specific
   Cavern (Selfishness level 5 is the closest documented ROV1
   cousin)?

## 10. Carbon review (gemini-4-carbon, 2026-11-19)

Verdict: **ship with fixes.** Call cost $0.0547; running logged total
$6.7746. Adopted:

- Freeze uses 4-frame beats in a u8, clamped, no scalars. An
  infinite-dispense pedestal plus a reset plate, so one missed freeze
  cannot brick the floor.
- Fire-breather is a puzzle tool (invincible or kennel respawn);
  companion holds fire.
- Rewrite refuses if a body occupies the cell; pushed crates are not
  the rock-barrier region; 8–12 tiles, amortized over 2–3 frames.
- Mid-floor suspend resumes at the entry stairs.
- Water default: the creature crosses, the hero walks a dry catwalk.
- Pack-spawn plates and pickup wall traps moved to Phase 3.
- Turret, plate, and door share one camera quadrant. Only turret
  shots flip the plate. Lockout pauses the fire timer (144-frame
  minimum hold). No pack on shut. Turret death fail-safes doors
  open and strips flip authority from in-flight shots.
- Rime Pipes stays a room-local charge in the slice (no Pack id, no
  `player_t` growth). New logic hooks an existing banked dispatch so
  home stays at 0 added bytes.
- Study: Pan Pipes are not potion-ammo in ROV1; Jaggers are *mostly*
  unshootable.

Not adopted as a change of direction: the isolated-floor
recommendation, room-level freeze vs `QSTATUS_STOP`, the def-flag
(not `EF_*`), and treating Carmelo's leviathan room as a complexity
target rather than a verified transcript.
