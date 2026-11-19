# Ultima-depth state-machine puzzles

Date: 2026-11-19 · Status: **proposal for review, nothing implemented**
Ask (Carmelo / struktured, 2026-11-19), from a stream of *Ultima:
Runes of Virtue DX*. He has not reviewed the OBS VOD. Treat his
examples as recollection, not a room transcript. Companion study:
`2026-11-19-runes-of-virtue-puzzle-study.md`.

This PR is spec only. No gameplay code.

## North star

Quintra's foundation is Penta Dragon (shmup meets Zelda). On top of
that it takes:

- the adventure feel of Zelda
- the ARPG feel of Final Fantasy Adventure
- the puzzle and animation style of Ultima Runes of Virtue

That four-part blend is the design north star. This spec is about the
third line: puzzles with Ultima's *shape*, not another pass of "hit a
switch, push a block, play the notes," and not Final Fantasy
Adventure's shallow "freeze a guy, push him onto a tile."

## Core constraint: no softlocks, ever

This is a hard rule, above every fixture in this document.

Every puzzle room is always recoverable. The player can always leave,
and can always put the room back to a known solvable state. Quintra
will not ship a room that can be bricked by a bad push, a spent key,
a killed tool-beast, or a shut door.

### Reset mechanism (proposal)

**Primary: a Pack menu action, "Reset room."** It is available in any
authored puzzle room, from anywhere on the floor, even if the hero is
boxed in. That matters: a plate you cannot walk to is not a reset.

**Secondary, taught first: a marked reset plate next to the
entrance.** Same function as Pack reset. Players learn it by seeing
it. Pack is the safety net for states where the plate is off-camera
or behind a shut gate.

**Not hold-SELECT.** SELECT already drives the map cache
(`BGT_MAP_CACHE` in `tiles.h`). Do not steal it.

**Cost and the roguelike.** Reset is free of HP, MP, coin, and score
cost. The cost is time (a short fade, about 30 frames, and a clear
SFX) plus whatever you already spent *fighting* in the room. Reset
does not refill hearts, MP, or run-long Pack charges (Bombs, Chime,
Mirror). That keeps it from being a combat-heal exploit. Puzzle state
is what comes back, not your build.

Walking out the entrance and coming back is the same reset. The
entrance of a puzzle floor **never closes**, not for combat seals,
not for turret doors, not for key doors.

**Suspend:** if the hero suspends mid-floor, resume at the entry
stairs with the unsolved floor rebuilt to the entry state (same as
reset). A solved bit, once earned, keeps the exit open.

### What reset restores, and what it does with keys and items

Reset restores the room to how it was on entry:

- tiles, rewrite phase, blocks, switches, doors, cobweb-equivalents
  or crystal locks, tool-beast kennel, turret phase, and monsters

**Room-local pickups** (keys sitting in this floor's chests, the
Rime Pipes charge, a floor tool): if the hero picked them up during
this visit, they are **removed from inventory and placed back on
their pedestals.** Reset cannot duplicate loot. Spent floor-local
keys return to their chests, and the doors they opened relock,
because the phase mask goes back to entry.

**Items brought in from outside** (run-long inventory, keys from
earlier floors, equipped B items) are left alone. Reset does not
invent a Heart Key you did not have, and it does not refund a Rift
Bomb you already used as a shortcut.

**Monsters:** packed optional-combat rooms respawn as on entry.
Kills in that room are undone. This is a puzzle reset, not a farm:
HP is not restored, so grinding a pack by reset-killing is a bad
trade. Tool-beasts return to the kennel.

### Contrast with Runes of Virtue (what we refuse)

ROV *likes* gotchas. ASchultz: you reset a goofed floor only by
visiting two other areas first. The Ankh teleports you to the castle
and **wipes keys, hammers, and boots**. Deceit has trap squares that
send you back to the top of the dungeon, and treasures that vanish
when touched. Some rooms hold a nice item with no exit unless you
already have a specific tool (TAS: a second Fireball Wand that is
impossible to obtain). Failure often means leaving the whole cavern.

Quintra deliberately avoids that. A mistake is a reset, not a
dungeon-eject, not a key-wipe, and never a room with no door out.

### Automated check

Every authored puzzle fixture ships with a solvability-and-reset
test (see M1–M5). From every reachable phase mask: the entrance is
walkable, Pack reset returns the entry state, no item is duplicated,
and either the goal is still reachable or reset makes it reachable
again. The Rust solver and the C↔Rust parity job already used for
Sun Lattice are the right harness.

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
pressure on that contract; see §6.3 and §9. The no-softlock rule is
stricter and is not optional.

## 1. Goal

1. Teach and then demand Ultima-style depth: isolated floors or large
   rooms that rewrite themselves, where the player has to anticipate
   what a switch, a shot, or a monster will do next.
2. Add an invincible (or otherwise unfightable) monster that exists to
   make the player think: route, trap, or freeze, not DPS.
3. Add a freeze-all-monsters verb that works on those bodies. The
   existing Chime, Bomb, and Mirror **do not** do this (§2.4).
4. Ship one **vertical slice** — a single authored showcase floor —
   that uses an original spawn → transform → route → tool-beast chain
   (inspired by, **not copied from**, the lakes-and-leviathans floor)
   plus a turret whose shots churn room state, matching keys, and a
   guaranteed reset.
5. Leave open whether later puzzles live in one big room or are
   scattered across a dungeon. Recommend, do not decide.

## 1.1 Carmelo's dump, mapped

Everything from the verbal dump, and where it lives in this spec:

| Dump item | Where | Notes |
|---|---|---|
| North star (Zelda / FFA / Ultima / Penta Dragon) | Top of this document | Verbatim in spirit |
| Floor or room as a state machine | §3, §5, study §4.1–4.3 | Isolated wide floor first |
| Switches rewrite tiles / materials | §6.1 | Cairns → rift-stream in the slice, not lakes |
| Invincible monster that forces thought | §6.2 | Route, trap, freeze; never DPS |
| Freeze-all item; do Chime / Bomb / Mirror already freeze? | §2.4, §6.3 | **No. None of them freeze bodies.** New verb. |
| Pressure plates that spawn packs, teleport skip | §6.4, M4 / M5 annex | Kept, not in M1 |
| Turret shots hit a switch, semi-random churn | §6.6 | Fair cadence, on-camera tell, freeze pauses it |
| Lakes / leviathans / cobwebs / water bridge | Study §4.8; slice is §5 | **Inspiration only. Do not copy.** Pattern: spawn, transform, route, tool. |
| Trap monsters in rooms | §6.2, M1 | Closable door, bodies that cannot use doors |
| Avoid monsters by not opening doors | §5 beat 2, M1 / M4 | Optional-combat door; intended line is to walk past |
| Monsters fanning out on their own | §6.2, study §4.5 | Invincible roamer spreads after entry or a trigger |
| Item-grab wall traps | §6.5, M4 | Extend `BGT_ARROW_TRAP` |
| Water- and fire-breathing creature routing | §5, study §4.8 | Same pattern, Quintra dressing (Cinder Kite on a rift-stream) |
| Matching keys (heart, star, moon, …) | §6.7 | 3 types; showcase uses 2–3 |
| One room vs scattered across a dungeon | §4 | Open. Recommend isolated floor first. |
| Iterations in the game, not only a spec | §7 | Milestones M1–M5; start at M1 |

## 2. Engine inventory (checked against `origin/main`)

Facts below were taken from headers and the small related sources
named here, plus the 2026-11-15 and 2026-11-18 specs already on main.
No full-repo walk.

### 2.1 Tiles and materials (`src/render/tiles.h`)

We already have floors, walls, pillars, crystals, pushable 16×16
`BGT_BLOCK` crates, `BGT_SWITCH` (commented as a **one-shot** pressure
plate: player or block), `BGT_SWITCH_PRESSED`, `BGT_PORTAL` (intra-stage
rift well), `BGT_SPIKES`, `BGT_POT`, `BGT_ARROW_TRAP` (Farfold cache
face), `BGT_DOOR_LOCKED` (126), water as `BGT_WILD_WATER` /
`BGT_GATE_WATER` (solid unless Picsean or Tide Raft), and the Law /
Prism barrier pair (`BGT_PILLAR` / `BGT_CRYSTAL` / `BGT_FLOOR2`).

There is no general "this switch rewrites class A to class B" table.
Prism Toggle and Dungeon Law are two-state barrier flippers, which is
the closest live writer to steal from. The showcase does not need a
new cobweb tile; it uses a crystal lock and a rift-stream (see §5).

### 2.2 Room size and persistence

- Standard room: `ROOM_W` 20 × `ROOM_H` 17 (one screen).
- Wide / scrolling room: 31×31 tiles (248×248 px). A Runes of Virtue
  floor is 16×16 cells, 256×256 px (`ultima-rov-dx` `dungeons.md`).
  A wide Quintra room is the right unit for "the floor IS the puzzle."
- The tilemap is RAM. Suspend SRAM stores `run_state` + `player`, not
  a room bitmap. Rooms are rebuilt from the run seed plus a few
  persisted bits. Any new floor state must be a compact phase mask
  that the prepare step can replay. Reset and suspend both replay
  the entry mask, not a mid-puzzle snapshot.

### 2.3 Enemies and AI

- 32 entity slots, 28-byte records. The flags byte is full
  (`EF_RARE` is `0x80` in `rare_enemy.h`). An invincible bit cannot
  be a new `EF_*` without breaking that layout.
- `enemy_load_def` (bank 25, with the new-monster AI) is the right
  place for a definition flag.
- Existing cousins: `AI_TURRET` (Sentry), shooters, Cinder Kite /
  Cinder Maw, basilisks. Nothing is currently unkillable on purpose.
- Picsean Blizzard and Sauran Thunder apply `QSTATUS_STOP` for 8–12
  beats (about 1–1.6 s). Stop is a brief combat stagger (default 14
  beats of eight frames; elites cap at 6). One primary condition per
  actor; a later poison would replace a Stop freeze. This is not a
  floor-wide freeze.

### 2.4 Pack tools and B items: Chime, Bomb, and Mirror are not freeze

Carmelo asked whether we already have a freeze. **We do not.**

| Tool / item | What it does today | Freeze? |
|---|---|---|
| Rift Bomb (`ITEM_ID_RIFT_BOMB` 40) | Pack charge. Breaks crystals, pots, crack walls; 8-way bomb shots; Sun Lattice strike. | **No.** Terrain and damage, not a halt. |
| Echo Chime (`ITEM_ID_ECHO_CHIME` 41) | Pack charge. Deletes hostile shots, reveals neighbor cells, pings a hidden secret. | **No.** Closest "silence the room" verb, but it only clears projectiles. Bodies keep walking. |
| Mirror Shard (`ITEM_ID_MIRROR_SHARD` 42) | Pack charge. Reflects hostile shots and gives short i-frames. | **No.** |
| Antidote (49) | Pack tool, cures DoT. | No |
| Bombs B-item (48) | Combat bombs. | No |
| Hookshot / Boomerang / Morningstar | B weapons. | No |
| Hero magic | B tap / hold when the hero power is selected. Blizzard or Thunder applies `QSTATUS_STOP` to a lane for ~1–1.6 s. | **No.** Hero-locked, too short, not floor-wide, and a later poison replaces it. |

Do not overload the Chime. Freeze is a new verb (§6.3).

### 2.5 SRAM, WRAM, banks

- Cart is MBC5 with battery SRAM. Bank 0 holds one suspend:
  `"QS"` + version + two u8 lengths + `run_state` + `player` +
  checksum. `sizeof(run_state_t)` itself is a u8, so the struct must
  stay under 256 bytes. It is currently about 70 (69 before
  `powerup_shrines`, then one appended byte). New fields must append
  and migrate, never shift old offsets.
- `dungeon_puzzles` bit 5 is still the only unused bit in that byte.
  Every `dungeon_phase` bit is in use. Milestones M1–M5 should aim
  at **zero new SRAM** and reconstruct from seed + room WRAM, using
  bit 5 only if a showcase floor must stay solved across a leave.
  Matching keys stay floor-local in the slice (§6.7). If keys later
  become run-long, append 2 bytes to `player_t` (three 4-bit counts,
  cap 15) and migrate.
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
  caps (one turret, one tool-beast, one invincible roamer, no extra
  pack on the turret). Also check the mid-game biome's BG/OBJ VRAM
  budget before adding cairn / stream / crystal-lock tiles, a gold
  plate, a pipes pip, key-bow icons, and a new Jagger sheet.

## 3. Design principles

1. **A floor is a machine.** Each switch, shot, or body has a
   downstream effect the player can learn. No one-and-done plate that
   only opens the seal.
2. **Monsters are pieces, not only threats.** Some are tools. Some
   cannot be fought.
3. **Readable beats, not noise.** Semi-random churn is allowed only
   with a clear telegraph, a minimum time in each useful state, and a
   freeze that can hold a state the player wants to keep.
4. **Authored first, procedural later.** The first Ultima-depth floor
   is authored and solver-checked, like Sun Lattice and Prism Toggle,
   not a generator of arbitrary state machines.
5. **Pattern, not port.** Steal ROV's causal shape. Do not reproduce
   its lakes, cobwebs, leviathans, key-wipe Ankh, or no-exit treasure
   rooms.
6. **Rebuild, do not snapshot.** Phase bits plus the seed replay the
   floor. Reset, leave, and mid-floor suspend all return to entry
   until a solved bit is earned.
7. **No softlocks, ever.** The constraint at the top of this spec.

## 4. Open question: one big room, or a puzzle scattered across a dungeon?

Carmelo asked and did not decide. This section lays out the trade and
a recommendation. It is not a decision.

| | One isolated floor / large room | Scattered across the dungeon's rooms |
|---|---|---|
| Feel | Closest to ROV: stairs cut the machine off. You see the whole state. | Closest to "the dungeon is one machine" from the 2026-11-15 spec (Law Lock, Deep Phase). |
| Memory | Almost free: WRAM only, rebuild on entry. | Needs a compact dungeon-wide mask, likely +1 SRAM byte, or a fight for leftover bits. |
| Fairness | A reset is Pack or the entrance plate. Softlocks stay local — and must still be impossible. | A wrong flip in room A can trap you in room C unless the same reset rule applies per room and the Compass routes over (cell × state), as Law Lock already does. |
| Readability | High. The conduit, the lock, and the turret are on the same camera. | Lower. The player has to remember a door two rooms ago. |
| Production | One fixture, one solver, one GIF. Right for a vertical slice. | More rooms, more validation, easy to ship shallow again if we only sprinkle switches. |
| Risk | A 31×31 authored floor is a lot of on-screen work, but we already scroll those rooms. | We already have dungeon-wide Law Lock. A second dungeon-wide machine can collide with it. |

**Recommendation, not a decision:** ship the vertical slice as **one
isolated wide floor** (with at most a tiny anteroom). That matches
Runes of Virtue, keeps SRAM at zero, and is the honest test of depth.
If the floor feels as good as Carmelo remembers, a later pass can
scatter the same verbs across a dungeon, using the Law Lock validator
as the template.

A hybrid is also on the table: the showcase stays one floor, and a
later dungeon uses a single two-state material law plus one invincible
roamer in the halls. That is still not a decision.

## 5. Vertical slice — Ember Conduit (original, not a port)

**One authored wide floor, mid-game (Frost Vault or Ember Depths),
optional or tool-reward, never on the only path to a Colossus until
the contract in §9 is settled.**

Inspiration, which we will **not** build: two lakes, each south of a
landmark, each with a cobweb-blocked rock; one switch spawns blocks,
another turns a block into water; a water bridge joins the lakes;
leviathans swim across and shoot the far cobweb, freeing that rock
(study §4.8). The pattern we keep is spawn → transform → route →
use a monster as a tool.

The floor, in one sentence: you release a Cinder Kite, raise cairns
and turn them into a rift-stream so the Kite can cross a gap and
shatter a crystal lock, while an invincible roamer, matching keys,
and a switch-hitting turret make you freeze, route, and time the
churn — and a Pack reset or the entrance plate can always unwind a
mistake.

Beats, in teaching order:

1. **Anteroom.** A freeze **pedestal** that dispenses one local charge
   whenever the hero holds none and the room timer is at 0. The
   **reset plate** sits next to the always-open entrance. Pack
   "Reset room" is already live. The player does not need a run-long
   Pack tool to try the machine.
2. **Invincible roamer (fan + avoid).** A Stone Jagger fans out along
   the first lane. Hits do not flash. Freeze holds it long enough to
   cross. A side door hides an optional pack: the intended line is
   **not to open it**. A closable alcove can also trap the Jagger.
3. **Rewrite switches, in a dead-end first.** Switch A raises a short
   run of stone cairns in a fixed region (not the pushable crate).
   Switch B turns those cairns into a rift-stream. The hero walks a
   parallel dry catwalk. No Picsean / Raft gate.
4. **Spawn, transform, route, tool.** A plate releases a **Cinder
   Kite** from a kennel (puzzle-flagged, invincible or kennel-respawn;
   the companion holds fire and ignores it). Build the conduit across
   a gap. The Kite will only travel the stream. Once it crosses, its
   fire shatters a **crystal lock** on a crate or a Star-door plaque.
   Wolfkin fire, Rift Bomb, and combat Bombs may break the lock as a
   shortcut; they must not skip a trigger the Kite's release is
   supposed to set. A second lock further along may reuse the same
   verbs with new geometry — not a second lake and web.
5. **Matching keys.** Two types on the mandatory line (Heart in a
   visible chest for a side cache that holds a rewrite switch or a
   second freeze pip; Star for the mid-floor gate the Kite unlocks
   or that leads to the turret court). A third type, Moon, may sit
   on an optional alcove on the same floor if the layout still
   reads; otherwise Moon waits for a later floor. See §6.7.
6. **Turret churn,** once the player has the verbs. A stuck shooter,
   its gold plate, and a *side* exit door (never the entrance) share
   **one camera quadrant**. The turret pings the plate and cycles
   that door. Freeze it when the door is open, then leave. No pack
   is spawned on shut.

Success is: the floor is solvable without a FAQ, the state is always
visible, a softlock is impossible (Pack reset, entrance plate, or
walking out), and `test_performance` does not drop below 167/180.

## 6. New systems (spec only)

### 6.1 Material rewrite

A packed rule: `{ from_class, to_class, region or room }`. A toggle
switch, a shot-switch, or a scripted button applies one rule. The
writer paints tiles immediately, like Prism Toggle. Rules must be
reversible enough that the prepare step can replay the current phase
from the seed, including after a reset.

First materials for the slice:

- Stone cairns (pillar-sized, fixed region, not a pushed crate).
- Rift-stream (walkable for the Cinder Kite and other puzzle
  tool-beasts; the hero uses the dry catwalk).
- Crystal lock (blocks a crate or a door plaque; shattered by the
  Kite's fire, or by fire/Bomb as a shortcut).

Collision: if Switch A would raise a cairn on a cell the hero, crate,
roamer, or Kite occupies, the switch **refuses** (dud clunk). Closing
doors use the same rule, and also nudge an overlapping actor one tile
out. Switch B only converts the **fixed cairn region**, never a crate
the player has pushed off its home cell.

Budget: a rewrite touches at most **8–12 tiles** and is amortized
over 2–3 frames, in the Law Lock / Prism Toggle style. No full 31×31
`set_bkg_tiles` blast in one frame.

Cost: M. New tiles + a banked writer. 0 SRAM. A few WRAM bytes for
the live phase mask (2–4 bits is enough for the slice).

### 6.2 Invincible monster

A definition flag, not an `EF_*`. Provisional name: **Stone Jagger**
(ROV's rock beast), or a Quintra name if Carmelo prefers something
less on the nose. Mid-size, slow roam, cardinal or slightly drunk
walk, **fans out on its own** after entry or after a trigger (a
picked-up key, a opened side door), **cannot use doors**, contact
damage 1 heart, never lethal, **no HP flash, no damage, no status
except the room-level freeze.**

Used only in authored puzzle rooms. The procgen pack roller must not
select it. Max one on the showcase floor.

Neutralize by: freeze, closing a door on it, routing around, or
(later) a teleport crush. Not by DPS, Bombs, or Oaths.

Cost: S–M. One enemy id, simple roam AI in bank 25, art via GPT
Image 2.6 when we implement, not in this PR.

### 6.3 Freeze-all item (Rime Pipes)

A floor-local freeze verb, working name **Rime Pipes** (Pan Pipes, in
Quintra words). Not a Chime variant, not a hero spell, not a
B-weapon. For M1–M5 it is **not** a new Pack item id and it does not
touch `player` inventory or save migration. It is a room-local charge
with a small HUD pip. A later PR can promote it to a Pack tool
(`ITEM_ID` after Antidote 49) once Carmelo wants it run-long.

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
- Invincible bodies and the Cinder Kite freeze too. That is the point.
- Does not spend or replace `QSTATUS_STOP`.
- The pedestal is infinite-dispense (one charge whenever the hero
  holds none and the timer is at 0). Reset also returns the local
  charge to the pedestal if it was picked up.

Cost: S–M. Room timer + local pickup. 0 SRAM, 0 `player_t` growth.

### 6.4 Pressure plates and the teleport skip (M4)

Plates in puzzle rooms are **toggles or triggers**, not the current
one-shot `BGT_SWITCH` unless we explicitly want a one-shot spawn.

A later beat or annex: a plate that spawns a small pack once, and a
same-room `BGT_PORTAL` that lands the hero past the plate so the
spawn is never armed. The plate stays visible from both sides. The
entrance still cannot be blocked by the pack. Reset puts the pack
back untriggered and refunds nothing of run-long items.

Cost: M. 0 SRAM. Keep the authored pack tiny (two bodies).

### 6.5 Pickup wall traps (M4)

When a pickup tagged in the fixture is collected, every
`BGT_ARROW_TRAP` in the room fires one volley along its facing.
Mouths are visible the whole time and flash for 20 frames as the
pickup is taken. Damage and i-frames match ordinary hostile shots,
never lethal. Reset puts the pickup back (if it was room-local) and
disarms the volley.

Cost: S. Extends a tile we already have.

### 6.6 Turret that hits a switch (state churn)

Carmelo's second set-piece, specified so it stays fair.

**Body.** One parked shooter, stuck in an alcove, using the turret
AI. It may be ordinary or invincible (if invincible, freeze is the
only way to pause the churn). It does not walk. Recommend a
**vulnerable turret for the slice**.

**Cadence.** Base period **96 frames** on Normal (about 1.6 s),
**120** on Easy, **80** on Hard, plus a jitter of ±16 frames. After
a hit that actually flips the state, a **lockout pauses the fire
timer** for 64 frames (80 on Easy). Minimum time in a state is
lockout plus the next period (144 frames / ~2.4 s on Normal). If
playtests still feel streaky, drop the 30% random lane and alternate
switch-lane / hero-lane deterministically.

**Aim.** 70% of shots use the heading nearest the hero. 30% pick a
random cardinal from a short authored list that always includes the
switch lane. Never fire in an untelegraphed diagonal through a
one-tile gap.

**Telegraph.** 24 frames (32 Easy) before each shot: body flash, a
one-tile aim spark, and if that shot's lane crosses the switch, the
switch plate flashes gold. Audible tick. Same language as Veil Magus
/ basilisk tells.

**Switch hitbox.** A 16×16 gold plate. In the slice, **only this
turret's shots** count. Player shots, Bombs, and reflected volleys
do not flip it. One-frame cooldown so a wide blast cannot flip twice.

**Layout.** The turret alcove, the gold plate, and the *side* door
it controls share one camera quadrant. The tell is never off-screen
during Beat 6. The entrance is not this door.

**States.** A two-state cycle: **Side-door Open** and **Side-door
Shut**. No pack on shut. No third state in the slice. The turret
must not rewrite the cairn / stream / lock machine.

**Death and crush fail-safes.** If the turret dies, in-flight turret
shots lose switch-flip authority and the side door fail-safes to
**Open**. Closing doors never embed the hero (nudge, or refuse).
Pack reset and the entrance plate also clear the churn back to entry.

**Freeze.** Freeze pauses the cadence and holds the current state.
In-flight shots still fly and can still hit the plate.

**RAM.** WRAM: 1 byte timer, 1 byte phase. 0 SRAM.

Cost: M. Shot-hits-switch extends the existing Sun Lattice / Prism
orb strike path.

### 6.7 Matching keys (Heart, Star, Moon)

A collection-and-matching layer on top of the puzzle gauntlet, in
the ROV language: the bow of the key carries an icon, and the door
carries the same icon. A key opens only its match.

**How many types.** **Three** for the game vocabulary: **Heart,
Star, and Moon.** That matches ROV's three-way set (heart, star,
ankh) without reusing ankh, which in ROV is also the "teleport home
and wipe your keys" item — a verb we are rejecting. More types
later would need more HUD and SRAM; do not add a fourth in M1–M5.

**Icon tiles.** Each type has an 8×8 bow icon and a matching 8×8
door plaque (or a two-tile lintel). Art is **GPT Image 2.6** at
implementation time, not in this PR, quantized to the 4-colour
sprite / BG format. Shapes must read in monochrome, not by palette
alone (Heart, six-point Star, crescent Moon). Palette can still
help: Heart uses the fire/heart red, Star the coin gold, Moon a
cool grey.

**HUD and Pack.** While the hero holds any floor-local key, a slim
row of up to three bow icons plus a count (1–3) sits in the Pack
and as a small HUD pip (reuse the tool-icon slot language, not a
new home-bank draw path). Empty types are dim or absent. The
showcase never needs more than one of each type at a time, but the
display should show a count so a later floor can hold two Stars.

**SRAM.** For M1–M5, keys are **floor-local**: 3 bits "chest still
has its key" and 3 bits "hero is holding this type" plus 3 bits
"this door is open" live in the room phase mask (WRAM). 0 new SRAM,
0 `player_t` growth. Reset clears held floor-local keys back onto
their pedestals and relocks the doors. If a later milestone wants
run-long keys, append **2 bytes** to `player_t` (three 4-bit
counts, cap 15 each, one nibble reserved) and migrate; that is not
required to prove the pattern.

**How doors read.** A locked matching door uses `BGT_DOOR_LOCKED`
(or a pair) plus the plaque tile on the lintel, facing the approach.
The plaque is visible before the hero has the key. Wrong-type keys
do not consume and play `SFX_REFUSE`. The **entrance is never a
matching door.**

**Consumption.** Spending a matching key unlocks that door and the
door stays open in the phase mask for the rest of this visit (and
after the floor is solved). The key is consumed on a successful
unlock, not on a refused bump. Two doors of the same type with only
one key is a *choice*, as in Hatred L2; the "wrong" room may be
optional treasure, never the only way out.

**Softlocks.** In addition to the top-of-spec rule:

- Every key the floor requires sits on that floor, on the mandatory
  line, before its door.
- Reset returns held floor-local keys to chests and relocks unsolved
  doors, with no duplicates.
- A key from outside the floor (if we ever have run-long keys) is
  not consumed by reset and not refunded if already spent on a
  *different* floor.
- We do not copy ROV's "carry only one of each type" cap as a hard
  limit that bricks a route; the slice cap is 3 per type, which is
  more than the floor uses.
- We do not wipe keys as an escape hatch.

**Showcase use.** Beat 5: **two types on the mandatory line**
(Heart, Star) and an optional **Moon** alcove if the layout still
reads. If Moon makes the camera or HUD busy, drop it from this
floor and teach it on the next one. Three types is the ceiling, not
the goal of the first painting.

Cost: M. Plaque tiles, a tiny key state machine, Pack/HUD pips.
0 SRAM in the slice. Art later, GPT Image 2.6.

## 7. Iteration milestones (M1–M5)

These are small **playable** builds, not just engine chores. Each
one can go on a password-gated itch build and a card once Carmelo
approves the scope. Each one includes the no-softlock test. No
gameplay code until he says go, starting with **M1**.

### M1 — Think, don't fight (recommended first build)

**Scope.** A small authored room (standard 20×17 is enough). One
Stone Jagger that fans out. One closable alcove. One optional-combat
door the player is meant to walk past. Rime Pipes pedestal.
Entrance always open. Pack "Reset room" and the entrance reset
plate both live.

**Engine cost.** S. Def flag in bank 25, room freeze timer, Pack
entry, no new SRAM, no new Pack item id, no rewrite table yet.

**Acceptance.**

- Hits on the Jagger do no damage and do not flash; freeze holds it;
  a closed door stops it.
- Walking past the optional door is a complete solution; opening it
  is a combat tax, not a requirement.
- Pack reset and the plate restore the entry state from any legal
  position, including inside the alcove. Room-local freeze charge
  returns to the pedestal; HP is not refilled; no duplicated
  pickups.
- Entrance is walkable in every state. Suspend mid-room resumes at
  entry.
- Headless solvability-and-reset test over the phase mask.
  `test_new_game_start.py`, `check_rom_layout` (home unchanged),
  `test_performance` ≥ 167/180.

### M2 — The room rewrites itself

**Scope.** A small room that teaches Switch A (raise cairns) and
Switch B (cairns become a rift-stream) in a dead-end, with the same
reset tools as M1. Hero stays on a dry catwalk.

**Engine cost.** M. Banked rewrite writer, 8–12 tile cap, refuse-if-
occupied, 2–4 bit phase mask, 0 SRAM.

**Acceptance.**

- A then B is reversible and replays from the phase mask after
  reset, leave, or suspend.
- Switch A refuses if a body occupies a target cell.
- Solvability-and-reset test; performance and layout as in M1.

### M3 — Spawn, transform, route, tool

**Scope.** The Ember Conduit teaching beat: kennel-released Cinder
Kite, cairn-to-stream conduit across a gap, crystal lock shattered
only by the Kite (shortcuts may exist, but the release trigger still
counts). Still a modest room, not the full showcase. Reset-safe
kennel respawn if the Kite's slot dies.

**Engine cost.** M. Puzzle-flag the existing Cinder Kite, crystal-lock
tile, kennel. 0 SRAM.

**Acceptance.**

- The lock does not break to melee. The Kite, once the stream is
  built, crosses and breaks it. A dead Kite respawns in the kennel.
- Companion does not kill the Kite. Shortcuts do not skip the
  release trigger.
- Solvability-and-reset test includes "Kite dead," "stream half-
  built," and "lock already broken, crate wedged" — all recoverable.

### M4 — Keys, and one more dump verb

**Scope.** Teach Heart and Star matching doors on a short floor.
Add **one** of: item-grab wall traps, a spawn-plate plus teleport
skip, or the optional "do not open this door" pack if it was not
already clear in M1. Moon may appear as an optional alcove.

**Engine cost.** M. Plaques, floor-local key mask, `BGT_ARROW_TRAP`
or portal skip. 0 SRAM.

**Acceptance.**

- A Heart key will not open a Star door (no consume, refuse SFX).
- Reset returns floor-local keys to chests and relocks unsolved
  doors, with no duplicates.
- The only exit is never behind a missable key. Entrance stays open.
- Solvability-and-reset test covers "spent the Heart on the optional
  door" and still escaping.

### M5 — The showcase floor

**Scope.** The full Ember Conduit wide floor in §5: M1–M4 verbs
together, plus the turret churn of §6.6, two or three key types,
always-open entrance, Pack reset and plate. Optional or tool-reward
placement, not the only Colossus path.

**Engine cost.** L. Authored 31×31 fixture, Rust mirror + solver +
C↔Rust parity, GIF evidence. 0 new SRAM if the solved bit can use
`dungeon_puzzles` bit 5.

**Acceptance.**

- All §8 tests, including the solvability-and-reset sweep over the
  full phase mask.
- Turret rules from §6.6 (on-camera tell, 144-frame hold, death
  fail-safe, player shots do not flip).
- `test_new_game_start.py`, `check_rom_layout`, performance ≥ 167/180.

**Recommend starting with M1.** It is the smallest playable proof of
"think, don't fight," it ships the reset guarantee first, and it
does not wait on new tiles or the conduit art.

## 8. Tests (when we implement, not now)

Shared across M1–M5:

- Solvability-and-reset: from every reachable phase, the entrance is
  open, Pack reset and the plate restore the entry state, no room-
  local item is duplicated, and the goal is reachable after at most
  one reset.
- Freeze: holds every body including invincible ones and the Kite;
  does not delete in-flight shots; does not clear `QSTATUS_POISON`;
  the pedestal refills when the hero holds none and the timer is 0.
- Jagger: no HP change, no flash, freeze holds it, a closed door
  stops it.
- Rewrite: refuses if a body occupies a target cell; replays from
  the mask after reset / leave / suspend.
- Kite (M3+): lock breaks from Kite fire, not melee; kennel respawn.
- Keys (M4+): matching only; refused keys are not consumed; reset
  returns floor-local keys; two same-type doors with one key cannot
  be the only exit.
- Turret (M5): tell at least 24 frames and on-camera with its door;
  lockout pauses the fire timer; only turret shots flip the plate;
  death opens the side door; entrance is not that door.
- `check_rom_layout` (home unchanged), performance ≥ 167/180,
  `test_new_game_start.py`.

## 9. Questions for Carmelo

1. **The open question in §4.** One isolated floor, scattered across
   a dungeon, or the hybrid? The recommendation is "isolated floor
   first."
2. **Required-route contract.** May a mandatory room demand freeze,
   or must freeze always sit on that floor (or stay in optional /
   tool-reward rooms)?
3. **Reset.** Pack "Reset room" plus an entrance plate, free of HP
   cost, no loot refund of run-long items, floor-local keys returned
   to chests. Is that the rule you want, or do you want a small
   roguelike tax (for example a coin fee) so reset is felt?
4. **Names.** Ember Conduit, Stone Jagger, Rime Pipes, Heart / Star /
   Moon keys — or different copy?
5. **Turret in the slice:** vulnerable (can be killed to stop the
   clock) or invincible (freeze only)? Recommendation: vulnerable
   first.
6. **Moon key on the showcase**, or only Heart and Star there?
7. After you watch the VOD, does the lakes-and-leviathans memory
   still match, and are you happy with Ember Conduit as an original
   chain in that *spirit* rather than a copy of the lakes?

## 10. Carbon review (gemini-4-carbon, 2026-11-19)

First-pass verdict on an earlier draft: **ship with fixes.** Call
cost $0.0547; running logged total $6.7746 at that time. Adopted
then, and still in this text: 4-frame freeze beats, infinite-
dispense pedestal, tool-beast kennel respawn, refuse-if-occupied
rewrites, mid-floor suspend at entry, dry catwalk, turret lockout
math, no home-bank growth, no Pack item id in the slice, study
fixes for Pan Pipes and Jaggers.

This revision also answers later notes that Carbon had flagged as
risks: Pack reset plus a plate (a plate alone was not enough if the
hero is boxed in), a formal no-softlock constraint, and a
solvability-and-reset test in every milestone.

Not a change of direction: the isolated-floor recommendation, room-
level freeze vs `QSTATUS_STOP`, the def-flag (not `EF_*`).

**Changed after that review, on Carmelo's correction:** the
showcase is no longer a cobweb / lake / leviathan reproduction. It
is the Ember Conduit, an original spawn → transform → route → tool
chain. Carbon did not re-review this dressing.
