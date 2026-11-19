# Runes of Virtue puzzle study

Date: 2026-11-19. Companion to `2026-11-19-ultima-puzzle-depth.md`.
Research only. No gameplay code.

Carmelo streamed *Ultima: Runes of Virtue DX* and asked for Quintra
puzzles with that depth. He has not reviewed the OBS VOD, so his
examples are recollection, not a transcript. This study catalogs the
public record and the lab's own DX notes, then maps each archetype onto
Quintra.

## 1. What he was playing

[struktured-labs/ultima-rov-dx](https://github.com/struktured-labs/ultima-rov-dx)
is a GBC colorization of *Ultima: Runes of Virtue* (USA, Origin / FCI
1992), the first Game Boy game. It keeps the original movement, maps,
music, and timing. It is **not** *Runes of Virtue II* (GB 1993 / SNES).

A narrow search of `struktured-labs/quintra` found no Runes of Virtue
or Ultima references. The DX repo's notes are about colorization and
memory, not a puzzle design catalog, but they do confirm how floors
are stored. This study uses those notes read-only.

*Runes of Virtue II* is included where it is the clearer source for a
verb Carmelo remembered (hourglass / boulder-to-other-material, hydras,
web rooms). Those cases are marked ROV2.

## 2. How an ROV floor is built

From `ultima-rov-dx/reverse_engineering/notes/dungeons.md` and
`bg_tiles.md` (PyBoy probes of the original ROM):

- Every area is one **16×16-cell** map (256×256 px) at `$C600`. The
  camera scrolls over it. That is almost the same size as a Quintra
  wide room (31×31 tiles, 248×248 px). A normal Quintra room is one
  screen (20×17 tiles).
- Sixteen metatile graphics are loaded on entry and do not change
  while you stay in the area. A switch that "rewrites the room" has to
  retarget cells to graphics already in that set, or swap flags on the
  cell bytes.
- Stairs isolate floors. ASchultz's ROV2 FAQ calls a "room" an area
  you can leave only by stairs. That is the "whole floor IS the puzzle"
  unit Carmelo wants.
- Object lists live with the area. Monsters, chests, and missiles are
  9-byte templates. Most Jaggers (rock beasts) and some other
  templates are effectively invincible; the manuals and FAQs say a
  monster that does not flash when hit cannot be killed. A few later
  Jaggers can be dropped by specific late weapons; "most" is the rule
  the player is taught to trust.

## 3. Sources

| Source | What it is |
|---|---|
| Codex wiki, *Runes of Virtue walkthrough* | Floor-by-floor ROV1 solutions and combat rules |
| ASchultz, GameFAQs FAQ/29762 (ROV1) and FAQ/50769 (ROV2 GB) | Mechanics notes, room maps, material-change puzzles |
| Official-style hint sheet (GameSurge / GameFAQs FAQ/5865, ROV2) | Hourglass, boulder-to-barrel, skeleton-hits-switch, hydra-in-door |
| young_flip, GameFAQs FAQ/12810 (ROV2 SNES) | Webs, mushrooms that erase boulders, hydras |
| TASVideos #9404 (ROV1) | Buttons act as levers if occupied; a bat can press a plate |
| Cat's Lair in-game line, DX `areas.md` | "You can use cheese to lure monsters" |
| Play Critically and FFA wiki walkthroughs | FFA ice-snowman pressure-plate puzzles, for contrast |
| `ultima-rov-dx` notes: `dungeons.md`, `bg_tiles.md`, `monsters.md`, `areas.md` | Floor size, arrow floors, monster templates |

Caveat: public walkthroughs are incomplete and sometimes vague about
*which* floor a trick lives on. Where an example is uncertain, it is
marked. Carmelo's combined "leviathan / cobweb / rock-to-water bridge"
set piece was not found as a single documented room in ROV1; the
nearest confirmed verbs are listed under that archetype.

## 4. Archetype catalog

For each archetype: a concrete ROV example, a Quintra implementation
idea that fits GBDK, the current top-down action-roguelike, and the
existing input model (A attack, B item / magic, A+B special, Pack
tools), then **feasible** (current systems stretch to it) or **new
system**, with a rough cost.

Rough cost key: **S** = a few hundred bytes and no new SRAM;
**M** = about 1 KB ROM, a handful of WRAM bytes, maybe new tiles;
**L** = a new fixture kind plus solvability work, possibly +1 SRAM
byte if the state has to survive a room leave.

### 4.1 Floor-as-puzzle

- **ROV.** Cavern of Deceit, Honesty path, levels 2–5: a pressure-plate
  corridor that repositions granite walls, a boulder court, a lever
  that turns a troll, then a maze whose three switches have to be hit
  in order (Codex walkthrough; ASchultz). The floor, not a single
  switch, is the puzzle. Stairs cut it off from the floors above and
  below.
- **Quintra.** Author one **wide room** (existing 31×31 scrolling
  fixture) or a short isolated chain of standard rooms that share a
  compact state machine. Rebuild the floor from seed + a small phase
  mask on entry. Do not store a tilemap in SRAM.
- **New system** (M): a puzzle kind and a live tile rewriter. The wide
  room and seed-rebuild pattern already exist (Sun Lattice, Prism
  Toggle, Law Lock).

### 4.2 Switches that rewrite tiles

- **ROV.** ASchultz (ROV1): some plates "change the entire makeup of a
  room; half the wall squares will vanish." Plates and levers also
  toggle gates. Many must be used more than once, in both positions
  (Codex, Interaction). Deceit level 2 is the early teaching case:
  zigzag so each plate flips the granite walls out of your way.
- **Quintra.** A switch (step, block, or shot) runs a **rewrite rule**:
  in a region or the whole room, tile class A becomes class B. Rules
  are data, not per-room code. Live draw can reuse the Law Lock / Prism
  Toggle tile writer.
- **New system** (M): today's `BGT_SWITCH` is a one-shot pressure
  plate. Ultima needs toggles, repeatable use, and a rewrite table.
  Prism Toggle and Dungeon Law already flip two barrier states; this
  generalizes that idea to arbitrary material pairs.

### 4.3 Blocks that change material (rock, water, and so on)

- **ROV.** Clearest in **ROV2** Cavern of Selfishness (GameSurge hint
  sheet): an hourglass and later a switch turn fountains into teleport
  arrows and boulders into barrels you can smash. young_flip (SNES): a
  mushroom makes boulders disappear. ROV1 has pushable boulders and
  water / bridges (Selfishness level 5 uses a star key to cross a
  river, then a bridge to a heart door) but the documented
  rock-to-water *switch* is a ROV2 verb.
- **Quintra.** Two rewrite rules on one floor: "spawn rock blocks" and
  "convert rock to water." Water is walkable for some bodies and for
  the hero only with Tide Raft or Picsean, matching `BGT_GATE_WATER` /
  `BGT_WILD_WATER`. A new cobweb material is needed (none exists;
  `BGT_WILD_REEDS` is solid wetland growth, not a burnable web).
- **New system** (M): rewrite table plus two or three new tiles
  (cobweb, maybe a distinct water-bridge floor). Waygear already
  gates water. Do not make the Raft required on a mandatory route
  unless the contract in the 2026-11-15 puzzle spec is explicitly
  relaxed.

### 4.4 Trapping monsters

- **ROV.** ROV2 Deceit (GameSurge): the two-headed monster is fought
  by opening **one** door and shooting through it, because it usually
  cannot leave. Hydras "cannot walk through a door, so you can shoot
  them from a distance" (ASchultz ROV2). Cheese, sold at the Cat's
  Lair, lures monsters (DX `areas.md`, in-game line).
- **Quintra.** Doors the hero can close (or never open). Some puzzle
  bodies refuse door tiles, like Jaggers / hydras. Optional lure is a
  later extra, not the vertical slice.
- **Feasible** (S) if we add a "cannot use doors" bit on the enemy
  definition and let puzzle doors be closed by a switch or by walking
  out. The door-seal path already exists (`room_doors.c`).

### 4.5 Routing around invincible monsters

- **ROV.** Codex and ASchultz, stated as a core rule: if a monster
  does not flash when hit, it is invincible; go around it. Jaggers
  (rock beasts in the DX notes) are the type example: most cannot be
  shot, they stun on contact, they change path after you pick up
  treasure, they cannot move through doors, and a teleport onto them
  crushes them. They fan out and roam. Selfishness level 5: "Follow
  the Jagger and take out the cobwebs."
- **Quintra.** A new enemy flag on `enemy_load_def` (the entity
  `flags` byte is full: `EF_RARE` already uses `0x80`). No HP flash,
  no damage. Contact still hurts. Used only in puzzle rooms, never as
  ordinary pack filler. The player routes, traps, or freezes them.
- **New system** (S–M): the flag and AI roam are small; the design
  work is placement and fairness. Do not drop invincible bodies into
  random combat rooms.

### 4.6 Pressure plates that spawn packs, plus a teleport skip

- **ROV.** ASchultz (ROV1) warns that some floor items / plates do
  more harm than good. Plates that reshape a room or gate a corridor
  are well documented; plates that *spawn a pack*, with a teleport
  that skips the trigger, match Carmelo's recollection and the ROV
  habit of mixing plates with teleport arrows. A exact "spawn pack,
  skip with a pad" room was not pinned to a named floor in the public
  FAQs, so treat the skip as a design request inspired by those verbs
  (Deceit plates + Injustice / Selfishness teleport arrows).
- **Quintra.** A plate actor: step-on (hero, block, or monster)
  either rewrites tiles, opens a door, or spawns a small pack once.
  A `BGT_PORTAL` cousin warps the hero onto the far side of the plate
  so the trigger is never armed. The plate stays visible and
  readable. Teleport pads already exist as rift wells.
- **New system** (M): spawn-on-plate is new. The portal skip can
  reuse `BGT_PORTAL` with a short, same-room destination.

### 4.7 Wall traps triggered by picking up an item

- **ROV.** Standard "grab the chest / key and the walls shoot" feeling
  appears throughout the FAQs (narrow corridors, timing shots,
  motion-sensor arrows in ROV2 per young_flip). DX notes record
  **arrow floors** in Hatred area `$19` that push the player (a
  related hazard, not a pickup trap).
- **Quintra.** `BGT_ARROW_TRAP` (tile 125) already exists for Farfold
  cache faces. When a marked pickup is taken, those tiles fire a
  volley. Mouths are visible before the pickup; a short flash is the
  tell. Damage matches ordinary hostile shots, never lethal.
- **Feasible** (S): extend the existing trap tile and the pickup path.
  No new SRAM.

### 4.8 Leviathan spawn, angled fire, cobweb, rock-to-water bridge

Carmelo's recollection, treated as a **complexity target**, not a
verified transcript:

> One button spawns fire-breathing creatures. You angle them so their
> fire burns away a cobweb blocking a rock you need to push. One
> switch creates rock blocks, and another turns rock into water tiles,
> building a water bridge so the creatures can cross and repeat the
> web-clearing.

Confirmed nearby verbs, not the same room:

- ROV1 Selfishness, Magic Chalice, level 5 (Codex): freeze spiders,
  shoot cobwebs under mages, flip a switch, wait for Reaper shots to
  kill the middle one, push boulders so Reapers shoot each other,
  star key to cross a river, bridge to a heart door.
- ROV1 Deceit level 3: a lever turns a troll 90 degrees so you can
  steer him toward a door.
- ROV2 Selfishness: hourglass / switch rewrites boulders and
  fountains; hydras; webs.

- **Quintra.** The vertical slice should *author this exact machine*
  (or a slightly simpler first teaching version) as one wide-room
  fixture: spawn-or-release a fire-breather, let the hero bait its
  facing, have fire clear cobweb, and use two rewrite switches for
  rock and water. Fire-breathers can be a puzzle skin of an existing
  shooter (Seesill / dragon in ROV; we already have Cinder Maw and
  basilisks). They should ignore water once the bridge exists, and
  they should not be required kills.
- **New system** (L): this is the composition of 4.2, 4.3, 4.4, and a
  fire-clears-web rule. Worth one authored fixture, not a procedural
  generator, for the first slice.

### 4.9 Turret that hits a switch (semi-random state churn)

Carmelo's later example, also recollection:

A monster is stuck in or near the room. It fires at random or at the
player. Its shots can hit a switch, and each hit changes the room
(releases certain monsters, or opens doors you must cross before the
next hit flips them back). The player tracks this churn while solving
the rest of the floor.

Confirmed nearby verbs:

- ROV1 Deceit level 3: lever aims a troll.
- ROV1 Selfishness level 5: wait for Reaper shots to hit the middle
  Reaper; later, push boulders so their lanes overlap.
- ROV2 Selfishness (GameSurge): break a barrel so a skeleton walks
  onto a teleport arrow, arrives in the next room, and hits a switch
  that opens a door behind you.
- TASVideos #9404: a bat flying over a button presses it.

- **Quintra.** A parked turret (we already have `AI_TURRET` / Sentry)
  fires on a readable cadence. Shots use the same path as player
  shots for "this projectile may strike a puzzle switch." Full rules
  live in the design spec §6.6.
- **New system** (M): shot-hits-switch is a small extension of Sun
  Lattice / Prism orb strikes. The state machine and fairness timing
  are the real work.

### 4.10 Freeze-all-monsters item

- **ROV.** **Pan Pipes** (ROV1, found in the Cavern of Injustice per
  the Codex item list): freeze monsters in their tracks for a short
  time. FAQs call them essential against invincible or awkward
  bodies. In ROV1 the Pipes are reusable, with a short duration, not
  an ammo tax; potions heal and are unrelated. ROV2 still has a
  freeze verb used the same way (ASchultz: freeze hydras and Dark
  Knights).
- **Quintra.** See the design spec §6.3. Closest existing verbs:
  Echo Chime clears *shots* but not bodies; Mirror Shard reflects
  shots; Rift Bomb breaks terrain; Picsean Blizzard and Sauran
  Thunder apply `QSTATUS_STOP` for 8–12 beats (~1–1.6 s), and STOP
  is a short combat stagger (default 14 beats, shorter on elites).
  None of those is a floor-wide, class-agnostic freeze.
- **New system** (S–M): a floor-local charge (promoted to a Pack tool
  only later) that sets a **room freeze timer**, so it does not fight
  the one-status-per-actor rule and it also halts invincible bodies.

### 4.11 Other ROV verbs Carmelo did not mention

| Verb | ROV example | Quintra idea | Cost |
|---|---|---|---|
| Cheese / lure | Cat's Lair line; bait a body onto a plate or into a trap | Optional later. A dropped bait pickup. | S, later |
| Conveyor / arrow floors | Hatred area `$19` (DX notes): arrow floors push the player | New floor tile that adds a fixed vx/vy while you stand on it. Easy to read, easy to softlock if used with pits. | M, later |
| Teleport crush | Codex: an arrow pad onto a monster crushes it; pads are walls to monsters | Portal kill if a body occupies the landing cell. Nice against invincible roamers. | S, later |
| Monster-vs-monster | Selfishness Reapers; "let those monsters kill each other" (Cowardice L5) | Already possible if friendly fire is on. Puzzle rooms can author it. | Feasible (S) |
| Occupied plate is a lever | TASVideos #9404 | If a body or block already sits on a plate, bump / shoot it to toggle. | S |
| Secret walls | Codex: they look *slightly* different; hide and shoot through them | We already have `BGT_WALL_CRACK` and hidden secrets. Keep using those, do not make a second secret language. | Feasible |
| Keyed doors (heart / star / ankh) | Selfishness river and heart door | Skip as a new key type. We already have Law Lock, seals, and mission tools. | Parked |
| Hourglass / crystal ball / mushroom as global toggles | ROV2 Selfishness and Pride | Same rewrite table, different art. Not needed in the first slice if two ordinary switches already teach the rule. | Parked |
| Pushable teleport pad | ROV2: push a teleport circle one cell at a time to choose a destination | Heavy. Hookshot / block push could fake a simpler version later. | L, parked |
| Floor reset | ASchultz ROV1: leave two other areas, then return, to reset a goofed floor | For authored fixtures, a clearly marked "reset plate" or leaving and re-entering the floor is enough. Do not copy the two-area rule. | S |
| Ships / overworld routes | ASchultz ROV1 | Out of scope (Riftwild is a different language). | — |

## 5. Contrast with Final Fantasy Adventure

FFA is the right comparison because it is already in Quintra's north
star (the ARPG feel) and because Carmelo called out its shallow
puzzles.

FFA's signature dungeon trick is the Ice spell: a steered shard turns
one enemy into a snowman, and you push that snowman onto a pressure
tile (Medusa Cave, Davias's mansion; FFA wiki and Play Critically).
It is one verb, in one room, with no downstream state. Random enemy
walks, no pull, and one-hit snowman deaths make it frustrating rather
than deep. Walk off, respawn, try again.

Runes of Virtue is the opposite shape. A floor is a state machine.
The same lever is used in both positions. A troll's facing, a
Reaper's lane, a boulder, a cobweb, and a river crossing are all the
same puzzle. Actions have consequences you have to plan for, including
consequences that run while you are somewhere else on the floor.

Quintra should steal ROV's *shape* (layered cause and effect on an
isolated floor) and keep FFA's *feel* only in the action RPG layer
(elemental magic, steered Blizzard, MP). Do not "add depth" by making
more FFA snowman rooms.

## 6. What this means for Quintra

The first slice should prove the shape, not port Britannia:

1. One isolated wide floor (or one large room plus a tiny anteroom).
2. Toggle switches that rewrite materials.
3. At least one invincible or otherwise unfightable body, plus a
   freeze that works on it.
4. One monster-as-tool moment (angled fire, or a turret that hits a
   switch).
5. Authored and solver-checked, in the Sun Lattice / Prism Toggle
   tradition, not a full procedural generator of state machines.

Dungeon-wide scattering of the same verbs is a later decision. See
the open question in the design spec.
