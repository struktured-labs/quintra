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
marked. Carmelo later corrected the leviathan / lakes / cobweb set
piece (see §4.8). It is inspiration for a causal pattern, not a room
to copy, and it was not pinned to a named FAQ floor.

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
- **Quintra.** A rewrite table with two rules on one floor: "spawn
  blocks" and "convert those blocks into a path the tool-beast can
  travel" (in the showcase, stone cairns to a rift-stream; see
  design spec §5). Do not port cobwebs or lakes. The hero uses a
  dry catwalk, so Tide Raft / Picsean never gates a mandatory route.
- **New system** (M): rewrite table plus a short streamed-path tile.
  Waygear already gates open water; we simply do not use that tile
  for the hero's walking line.

### 4.4 Trapping monsters

- **ROV.** ROV2 Deceit (GameSurge): the two-headed monster is fought
  by opening **one** door and shooting through it, because it usually
  cannot leave. Hydras "cannot walk through a door, so you can shoot
  them from a distance" (ASchultz ROV2). Cheese, sold at the Cat's
  Lair, lures monsters (DX `areas.md`, in-game line).
- **Quintra.** Two related verbs. (1) **Trap:** close a door on a
  body that cannot use door tiles (Jagger / hydra rule). (2) **Avoid
  by not opening:** a closed door hides an optional pack. Walking
  past it is the intended line, as in Hatred L2 (Codex: "do not open
  any doors" if you just want to move on). Opening it is a combat
  tax, never the only way forward. The entrance of every puzzle
  floor stays open (design spec, no-softlock constraint).
- **Feasible** (S) with a "cannot use doors" bit on the enemy
  definition and authored optional-combat doors. `room_doors.c`
  already seals and unseals exits.

### 4.5 Routing around invincible monsters

- **ROV.** Codex and ASchultz, stated as a core rule: if a monster
  does not flash when hit, it is invincible; go around it. Jaggers
  (rock beasts in the DX notes) are the type example: most cannot be
  shot, they stun on contact, they change path after you pick up
  treasure, they cannot move through doors, and a teleport onto them
  crushes them. They **fan out and roam on their own** — Selfishness
  L5, "Follow the Jagger and take out the cobwebs." The fan is the
  point: the floor changes while you are elsewhere on it.
- **Quintra.** A new enemy flag on `enemy_load_def` (the entity
  `flags` byte is full: `EF_RARE` already uses `0x80`). **[FAQ / Rec]**
  It simply does not flash when hit. In the slice this is absolute:
  no special-weapon exceptions, even though a few late ROV Jaggers
  can be dropped by specific late weapons. **[Rec]** A rolling-stone
  lane may still kill it if it is lured or frozen there (hazard as
  a tool, not a weapon). Contact still hurts. Used only in puzzle
  rooms, never as ordinary pack filler. The player routes, traps,
  freezes, or lures them.
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

### 4.8 Spawn, transform, route, tool (the lakes-and-leviathans pattern)

Carmelo later corrected the set piece. This is his account of what
actually happens in ROV, still recollection, not a VOD transcript,
and not pinned to a named FAQ floor:

> There are two lakes, each south of something, and each has a rock
> blocked by a cobweb. One switch spawns blocks. Another switch turns
> a block into water. That lets you build a water bridge between the
> lakes. The leviathans swim across and shoot the far cobweb, which
> frees that rock.

**Do not copy this room.** No twin lakes, no cobwebs, no leviathans
in Quintra's showcase. What we steal is the **causal chain**:

1. Spawn or release a thing.
2. Transform a material (blocks become a path).
3. Build a route with that material.
4. Use a monster as a tool to clear an obstacle on the far side.

Nearby documented cousins, not the same room: Selfishness L5 (Codex)
uses Jaggers, cobwebs, Reaper lanes, a river, and a bridge; Hatred L5
dries a stream with plates; Deceit L3 aims a troll with a lever;
ROV2 Selfishness rewrites boulders and fountains; a TASVideos forum
note mentions a lever that turns barrels into water.

- **Quintra.** An original chain in that spirit, dressed in Quintra
  materials (cairns, a rift-stream, a Cinder Kite, a crystal lock).
  Full layout is design spec §5, working title **Ember Conduit**.
- **New system** (L): composition of rewrite + a puzzle-flagged
  tool-beast + a lock that only that beast can break. Authored
  fixture, not a generator, and not a port of the lakes.

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

#### Matching keys (heart, star, ankh)

- **ROV.** Heart, star, and ankh keys each open only the door with
  the same icon on its face (Codex, items wiki). Hatred L2: two
  heart doors, one heart key, a real choice (treasure vs. Melissa).
  Selfishness uses a star key for a river door and a heart door for
  the exit. ROV2 Pride is a key gauntlet (star keys lead to a heart
  key, then an ankh key). TAS #9404: you may carry only **one key
  of each type** at a time, which made routing awkward. The Ankh
  *item* also teleports you to the castle and **wipes keys,
  hammers, and boots** — a harsh escape hatch.
- **Quintra.** Three types — Heart, Star, Moon — with the same
  matching rule. Moon stands in for ROV's door-ankh so we do not
  collide with other ankh imagery. **[FAQ / Rec]** The hero holds
  one of each type at a time, and a Heart key opens only one of two
  Heart doors (Hatred L2). The unchosen door is optional treasure,
  never the only way out; Pack reset returns the key. We do **not**
  wipe keys as an escape hatch. Full rules: design spec §6.7.
- **New system** (M), taught in M4, combined on the showcase.

#### Fire wand, oil, and the (absent) ice wand

- **ROV.** There is **no ice wand** in ROV1. The Wand of Fireballs
  (Deceit, Codex / TAS) and throwable oil are the only player fire
  that burns **dark black webs**; ordinary webs fall to any weapon.
  Black webs also block a westbound ship on the overworld. Ice in
  this conversation is an FFA verb (snowmen on plates), not an ROV
  one. ROV2's Star Wand creates and destroys force fields — a
  different wand, closer to a rewrite switch than to ice.
- **Quintra.** Do not add an ice-wand puzzle. Blizzard already
  exists as hero magic and must stay shallow in the FFA sense, not
  become the puzzle language. Fire-as-tool belongs to a
  puzzle-flagged beast (the Ember Conduit's Cinder Kite) or to
  existing Wolfkin / Bomb shortcuts, not to a new wand item.

#### Invisible and secret paths; Magic Boots

- **ROV.** Secret walls look slightly different (ASchultz, Codex);
  you can stand in them and shoot the regular floor. Hatred L2: a
  door that "does not look like it is leading anywhere; the wall is
  a boundary." Magic Boots (items wiki, TAS) let you walk through
  walls for one use (1 MP), then vanish.
- **Quintra.** Keep the existing secret-wall language
  (`BGT_WALL_CRACK`, hidden shot/walk/push secrets, Echo Chime).
  Do not add a second "invisible floor" tileset. A Boots-like
  "walk a ghost path once" is a later optional tool, never the
  only escape from a room (no-softlock constraint).

#### Conveyors, arrow floors, one-way pads

- **ROV.** Hatred area `$19` (DX `dungeons.md`) has arrow floors
  that push the player. Arrow *transporters* fling you in a
  direction, sometimes through walls (Codex; TAS). Some pads are
  one-way in feel. Deceit has trap squares that teleport you back
  to the top floor — an intentional gotcha we will not copy.
- **Quintra.** **[ROM / Rec]** A conveyor tile with a vx/vy, and a
  switch that flips its direction using the same rewrite table as
  cairn ↔ stream (M4). Both directions' art must already be on the
  floor before the first flip, and the switch has a two-state
  glyph. Every conveyor lane must still lead to the entrance or a
  reset, and may not rest a body on those paths. Arrow *teleports*
  that fling through walls are closer to existing portals; do not
  mix "push" and "fling" on the same graphic.

#### Pushing blocks onto plates

- **ROV.** `BGT_SWITCH` in Quintra already accepts a player or a
  block; ROV plates are stepped on, and a body on a plate turns it
  into a lever (TAS #9404, a bat). ROV2 (ASchultz): a plate drives
  "grappling arms" that shove jugs, and you push the rest into a
  row. Not always "park a boulder on a switch and leave it," but
  the weight-and-block idea is there.
- **Quintra.** Feasible (S) with the existing plate + `BGT_BLOCK`.
  Useful on later floors (hold a door, hold a rewrite). The
  showcase does not depend on it.

#### Remaining short verbs

| Verb | ROV example | Quintra idea | Cost |
|---|---|---|---|
| Cheese / lure | Cat's Lair; items wiki: drop it, monsters run to it, cannot pick it up again | M3 or M4 B-item: drop, cannot pick up, reset returns it. Design spec §6.8. | S–M, M3/M4 |
| Teleport crush | Codex, TAS: a pad onto a body crushes it, even some invincible ones | Portal kill on a landing cell. | S, later |
| Monster-vs-monster | Selfishness Reapers; Cowardice L5 "let those monsters kill each other" | Authored friendly fire. | Feasible (S) |
| Water-breathing routing | Hatred L5 dries a stream; Abyss / Pride / Dishonor sharks and octopi (DX `monsters.md`); the lakes pattern in §4.8 | Inverse of the Ember Conduit: a body that only travels on the stream you build. Same rewrite table. | Covered by §4.8 / §5 |
| Hourglass / mushroom / crystal ball | ROV2 Selfishness and Pride; Hatred L5 mushroom + plates dry a stream | Same rewrite table, different art. | Parked |
| Pushable teleport pad | ROV2: push a circle one cell at a time | Heavy. Later. | L, parked |
| Two-area floor reset | ASchultz ROV1: leave two other areas, then return | **Do not copy.** Pack reset and the entrance plate work from inside the room. | — (rejected) |
| Ankh escape that wipes keys | Codex / items wiki | **Do not copy.** You can always walk out or reset. | — (rejected) |
| Trap squares to the top floor | Deceit (ASchultz / Codex) | **Do not copy.** | — (rejected) |
| Treasures that vanish when touched | Deceit Wand path | **Do not copy.** | — (rejected) |
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

1. Teach freeze and the invincible roamer in a tiny optional room
   one dungeon earlier (M1). The Ember Conduit wide floor is where
   already-taught verbs combine under pressure (M5).
2. Toggle switches that rewrite materials, using art the player has
   already seen, one meaning per graphic, two-state glyphs, and
   off-camera SFX plus a blink on arrival.
3. An invincible body that simply does not flash, with no weapon
   exceptions in the slice; a rolling-stone hazard may still be a
   tool.
4. One original spawn → transform → route → tool-beast chain, in
   the *spirit* of the lakes-and-leviathans floor, not a copy of it.
5. Authored, solver-checked, and **reset-safe**: Pack reset while
   pinned, no actor resting on the entrance or reset-plate path,
   no Ankh key-wipe, no vanishing treasure, no top-floor trap
   squares, no two-area reset.

Dungeon-wide scattering of the same verbs is a later decision. See
the open question in the design spec. Readability rules, choice
keys, the lure, and flip-conveyors live in design spec §3.1 and
§6.7–6.9.

## 7. Per-dungeon atlas (ROV1, plus ROV2 where it is the clearer source)

Carmelo streamed *Runes of Virtue DX*, which is ROV1 (USA). Each entry
names the cavern, a concrete floor, the verb, and the source. These
are the examples the catalog above is built from, not a walkthrough
to play by.

### 7.1 Cavern of Deceit — Rune of Honesty, Wand of Fireballs

- **L2, Honesty path (Codex, ASchultz):** a corridor of pressure
  plates that reposition granite walls. Zigzag so each plate flips
  the walls out of the way. The floor is the puzzle.
- **L3 (Codex):** a boulder court, then a lever that turns a troll
  90 degrees so you can steer him toward a door.
- **L5 maze (Codex):** three switches in an odd-shaped room, hit in
  order, then the Rune.
- **Fireball Wand path, L2–L5 (Codex, TASVideos #9404):** barrels to
  push, treasures that vanish or trap, trap squares that teleport
  you back to the top floor, secret walls. L5 is a warren of secret
  doors ending at a pressure plate and the Wand. The Wand (and
  throwable oil) is the only fire that burns **dark black webs**;
  ordinary webs fall to any weapon. There is **no ice wand** in
  ROV1. TAS notes you cannot collect both the Rune and the Wand in
  one descent unless you bring a Heart Key from another dungeon.

### 7.2 Cavern of Cowardice — Rune of Valor, Magic Rope

- **L1 (Codex):** cheese in a plant (lure item, first teaching).
- **L2:** push a boulder for health; do not eat the mushrooms.
- **L5:** "Go west and let those monsters kill each other." Then
  ankh and star keys, a star door beside an ankh door, a switch.
- **L6:** Magic Rope — one MP, one water tile of bridge, used twice
  to island-hop (Codex; items wiki).
- **L7:** run past arrow shots; a pressure plate arms; heart door
  plus a switch that opens a passage.
- **L9:** rope to an island; a mushroom makes a new door appear.
- **L10:** teleport pads and secret walls.
- **L11:** the Rune hops to the right when touched — "first fast,
  then slow." A pickup that rewrites its own position.

### 7.3 Cavern of Hatred — Rune of Compassion, Magic Axe

- **L2 (Codex), the dump's exact verb:** "If you just want to move
  on, just follow the pathway and **do not open any doors**."
  Opening a west door is an optional combat-and-treasure branch
  (Sherry, Princess Melissa, a heart key). A heart key opens only
  one of two heart doors — a matching key, spent on a choice.
- **L2 also:** a door that does not look like it leads anywhere;
  the "wall is boundary." Secret / false openings.
- **L3 (Codex):** a long boulder puzzle. If you mess up, leave and
  come back to reset. A lever, then a teleport to a star key, then
  stairs behind the star door.
- **L4 (Codex):** **do not kill the troll** — he opens and closes
  the gates. Dodge him counterclockwise and stay two squares away.
  A monster is the clock. Heart key behind a skeleton; a switch
  opens the SE gate.
- **L5 (Codex, ASchultz):** grab one mushroom and step on floor
  plates to **dry up the stream**, then the Rune. Material rewrite,
  water to floor.
- **Area `$19` (DX `dungeons.md`):** arrow floors that push the
  player (conveyors).

### 7.4 Cavern of Injustice — Rune of Justice, Boomerang, Pan Pipes

- Home of the **Pan Pipes** (Codex item list). Freeze is taught
  here because later bodies and Jaggers cannot be trusted as
  fights.
- TAS #9404: an arrow transporter landing on a body crushes it,
  even some invincible ones. A side room is a hammer-and-barrel
  puzzle that rewards a Boomerang.
- Bring food (Codex). This cavern is why freeze is "incredibly
  important," not a nice-to-have.

### 7.5 Cavern of Dishonor — Rune of Honor, Magic Whip

- Shorter in the public walkthroughs. Codex flags the Whip here.
- DX `monsters.md`: sharks, octopus, and serpents share
  Abyss / Dishonor / Pride — the water-breathing roster.

### 7.6 Cavern of Selfishness — Rune of Sacrifice, Amulet, Chalice

- **L4–L5, Chalice path (Codex):** follow a Jagger (invincible
  roamer, fanning on its own) and cut cobwebs; teleport arrows;
  star key to cross a river; freeze spiders; shoot cobwebs under
  mages; flip a switch; wait for Reaper shots to kill the middle
  one; push boulders so Reapers shoot each other; bridge to a
  heart door. This is the closest documented ROV1 cousin of
  Carmelo's fire-and-web / bridge recollection.
- **L8, Rune path (Codex):** Wand on **black webs**, walk spikes
  to a mushroom that opens a SE door; a lever **flips star doors
  and cobwebs**; smash a barrel to reach the Rune.
- **ROV2 Selfishness (GameSurge FAQ/5865, ASchultz 50769):**
  hourglass turns a fountain into a teleport arrow; a switch
  turns boulders into barrels; push a teleport circle one cell at
  a time to pick a destination; break a barrel so a skeleton
  walks onto a pad, arrives next door, and hits a switch. Hydras
  cannot walk through doors — open one door and shoot through it.

### 7.7 Cavern of Pride — Rune of Humility, Troll Ring, Magic Sword

- Codex calls the path linear and is thin on floors. ROV2 Pride
  (GameSurge) is the clearer "keys and matching doors" gauntlet:
  a diamond room with four stair choices; hoard star keys to find
  a heart key, then an ankh key, then Magic Armor; the Ping-Pong
  Paddle hits levers behind barred doors.

### 7.8 Great Stygian Abyss — Rune of Spirituality, Magic Armor

- The only cavern with dragons (Codex). TAS #9404: lure a
  sentient boulder to kill an otherwise-invincible Warlock; a
  plate that can spawn **infinite rats** if they step on it
  again; you may carry only **one key of each type** at a time
  (a cap that made the TAS route awkward). Forum notes on the
  same run mention a lever that turns barrels in a room into
  water tiles, and reapers around buttons that spawn a barrel.

### 7.9 Overworld and tools that live between caverns

- Black webs also block a westbound ship (Codex, Wand entry).
  Fire is a world verb, not only a dungeon verb.
- Magic Boots (items wiki, TAS): walk through walls for one use
  (MP 1), then they vanish. Closest thing to an "invisible path"
  tool. Secret walls themselves look slightly different (ASchultz,
  Codex) and let you shoot monsters on the regular floor while
  you stand in the wall.
- Cheese: drop it and monsters run to it; you cannot pick it up
  again (items wiki; Cat's Lair line).
- Trumpet: one-shot freeze-all; Pan Pipes: the reusable version,
  3 MP (items wiki). Not potion-ammo.

### 7.10 ROV2-only verbs worth stealing later

- Hourglass / mushroom / crystal ball as whole-room or clue
  toggles (Selfishness, Pride).
- Star Wand: create and destroy force fields (items wiki).
- Friendly horn, monster flags, snake staff: temporary allies.
- Dragonskin boots: lava protection.
- Crystal ball: peek at a neighboring room's shape (hint sheet).

### 7.11 The lakes-and-leviathans floor (Carmelo's correction)

His corrected account is in §4.8: two lakes, cobweb-blocked rocks,
a spawn-blocks switch, a block-to-water switch, a water bridge
between the lakes, leviathans swimming across to shoot the far
web. Public FAQs did not name this floor. It is the inspiration
for the Ember Conduit pattern in the design spec. It is not a
layout to reproduce.
