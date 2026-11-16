# Puzzle variety and dungeon-wide puzzles

Date: 2026-11-15 · Status: **proposal for review, nothing implemented**
Ask (Carmelo, 2026-11-15): "we need more types of puzzles, and some puzzles
which span the entire dungeon, but it's getting to a legit great GBC game if
we make a few more tweaks."
Facts below were checked against `origin/main` at `da905c92` (after #98, #99,
#100). Gemini Argon was not consulted for this draft; it can review the
proposals before implementation if wanted.

## Goal

1. Give every dungeon a wider puzzle vocabulary than "push the crate, step on
   the notes, aim the light", in the GBC Zelda tradition (Oracle / Link's
   Awakening DX), without breaking the repo rules: required rooms solvable
   with base movement and melee; class innates, B-items, waygear, Oaths and
   the companion are shortcuts, never requirements.
2. Add two or three **dungeon-wide** puzzles whose state spans several rooms,
   so a dungeon reads as one machine instead of 20–30 independent courts.
3. Keep every new room procedural, seeded, and provably solvable, using the
   same "generate backwards from a solved state + Rust mirror + solver +
   C↔Rust parity" method that Sun Lattice shipped with (#87, #91, #93).

## 1. Inventory: what exists today

### 1.1 Mandatory puzzle kinds (`src/game/puzzle.h`, `puzzle.c`)

| Kind | Mechanic | Where it appears | Notes from the code |
|---|---|---|---|
| `PUZZLE_PUSH_SEAL` | One 2x2 `BGT_BLOCK` crate in a cleared 8x6 apron; pushing it opens the seal | Trial / Waystone cells, Stages 1–2 only | `puzzle_on_block_moved` solves on **any** move of the crate, so it is a discovery beat, not a puzzle. |
| `PUZZLE_RUNE_SEQUENCE` | Step on `BGT_SWITCH` rune plates in a seeded order; each plate has a stable pitch, a wrong plate resets, rising or falling phrase per seed | Trial / Waystone cells, Stages 1–2 only (3 plates in Stage 1, 4 in Stage 2) | The 5-plate "center pivot" variant (`bosses_beaten >= 2`) is now dead code for the mandatory slots, because Stage 3+ uses Sun Lattice in both. Notes were made louder in #97. |
| `PUZZLE_PHASE_SWITCH` + `PUZZLE_PHASE_GATE` | A four-switch "lights out" row (`phase_switch_mask`, generated backwards from solved, unique solution); solving lowers a pillar wall in the **next graph cell** | `mission_deep_switch_cell` / `mission_deep_gate_cell`, every full-size dungeon, all stages | The only existing multi-room puzzle. Bit `RUN_DEEP_PHASE_OPEN_BIT` in `dungeon_phase`. The gate has body-width detours, so it is a shortcut wall, not a hard lock. |
| `PUZZLE_SUN_LATTICE` | Sun Brazier beam steered by rotating Helio Vanes (and Bifrost Wedges from Stage 4) onto Solar Obelisks | Trial **and** Waystone cells, Stages 3–9 (`bosses_beaten >= 2`) | Seeded, generated backwards, Rust solver + 3000-seed parity. Strikes from shots, boomerang, bombs, Morningstar, Hookshot. VRAM bank 1 BG 56–62. |

Solved state for Trial / Waystone rooms lives in `dungeon_puzzles`
(`RUN_TRIAL_BIT`, `RUN_WAYSTONE_BIT`). Solving pays one dungeon-tool charge
(Rift Bomb / Echo Chime / Mirror Shard). `dungeon_puzzles` bit 5 is the only
unused bit in that byte; every `dungeon_phase` bit is in use.

### 1.2 Dungeon-wide and ambient systems

| System | What it does | Where |
|---|---|---|
| **Dungeon Law** (`dungeon_law.c`) | Seeded per stage: PRISM (crystal), THORN (spikes) or STONE (pillars). A two-state WAX/WANE flag (`run_state.dungeon_law` bit 7) moves body-wide openings in two architecture runs in the far-east and southern aprons of **large** rooms. Altars (`BGT_SWITCH` at 3,8) in every cell with `local % 6 == 0`. | All dungeons, optional: never touches a puzzle room, never gates the main route. Pack screen shows e.g. `PRISM/WAX`. |
| Optional hidden secrets | Shot / walk-through / push secrets in ordinary wall or cairn art, about 3 rooms in 32, Echo Chime reveals | All dungeons, never on reserved cells 2, 5, 8, 11, 15, 17, 23 |
| Amber cracked walls | Shoot to open a treasure room | All dungeons |
| Stage events | Mire roots (Stage 2, cut crystal knots), Furnace (Stage 3, gold plates telegraph hot lanes, survival reward), Arrow traps (Stage 4), Fading floor (Stage 6) | `local >= 5`, `(local & 3) == 1`, not the foyer |

### 1.3 Riftwild

| System | What it does |
|---|---|
| **Worldglass** (waygear) | Shifts the Riftwild between Waking and Hollow (`riftwild_shift_execute`); three Hollow-only relics per region. Carmelo singled this out as "really cool". |
| Waygear gates | Boulder (Glove / Sauran), water (Tide Raft / Picsean), chasm (Rift Hook), thorns (Wolfkin), vent (Vespine) |
| Hidden dens | Spec #79, proposal only, not implemented |

### 1.4 Takeaways

- Stages 1–2 have two real puzzle types, and one of them (Push Seal) is a
  single push. Stages 3–9 have **one** type (Sun Lattice) twice per dungeon.
  That is why the game feels repetitive between fights.
- The only cross-room puzzle is the deep switch/gate pair, and its gate is a
  shortcut.
- Dungeon Law already gives us dungeon-wide two-state architecture, persistent
  state, altars and a Pack readout, but it is purely optional scenery today.
  It is the cheapest foundation for a real dungeon-wide puzzle.

## 2. Shared framework (needed by every new kind)

### 2.1 A per-stage puzzle pool instead of a hard-coded pair

Today `puzzle_prepare_room` picks Push Seal / Rune for Stages 1–2 and Sun
Lattice for 3–9. Replace that with a small const table, one row per stage,
listing the kinds allowed in the Trial slot and the Waystone slot. The seed
picks one from each list, with the rule that the two slots of one dungeon
never repeat a kind. Sun Lattice stays guaranteed in one slot from Stage 3 on,
so nothing already built is lost.

Optional third beat: one **optional** puzzle room per dungeon (reward: a
cache, not a route) on a non-reserved, non-mission cell, persisted in the
unused `dungeon_puzzles` bit 5. This is where tool-gated puzzles (Snag
Gallery, §3.5) live, so B-items get puzzle value without breaking the
"required rooms need only base kit" rule.

### 2.2 Solvability contract (same as Sun Lattice)

For every new kind:

- **C generator** builds the room backwards from a solved state with the
  room seed, so it is solvable by construction.
- **Rust mirror** in `quintra-procgen` reproduces the generator and adds a
  `solve()` that never reads the solved state.
- **CI parity**: host-compiled C vs Rust for 3000 seeds × every stage the
  kind appears in × both slots; the solver must find a solution within the
  stage's budget (min/max moves). The PyBoy test drives one live solve per
  kind from the solver's move list.
- **Body-width lanes**: every required plate, block path and exit is reachable
  by a 12 px hero, checked by the existing reachability scratch pass.
- **Reset**: leaving and re-entering regenerates an unsolved room from its
  seed (rooms already rebuild on entry), and solved rooms read their bit and
  draw solved. No in-room reset switch is needed for most kinds; kinds that
  can dead-end in-room (Rime Slide) also get a reset rune.

### 2.3 Speed calibration

#98 lowered starting SPD to 4 (6 for Wolfkin and Vespine) and raised the cap
to 12. Any timed puzzle (Ember Vigil) is calibrated against the **slowest
base hero at SPD 4 with no items**, with at least 40% slack, and the Rust
solver checks the time window using the per-SPD movement table from
`player.c`.

## 3. New single-room puzzle types

Each entry: mechanic, existing tools it uses, procgen fit, stage band,
budgets. Budget columns: ROM is banked code + data (all new code goes in a
`#pragma bank 255` file per the banking spec); WRAM is runtime scratch;
SRAM is new save bytes (all six need **zero**, because they reuse the
Trial / Waystone bits or optional bit 5).

### 3.1 Rime Slide (ice sliding blocks)

- **Mechanic:** The room's floor is ice. A pushed 2x2 crate slides until it
  hits a wall, pillar or another crate. Slide one or two crates onto
  matching rune sockets (`BGT_SWITCH`) to open the seal. The hero walks
  normally (sliding heroes is a stretch goal, not v1). A reset rune by the
  entrance restores the arrival layout.
- **Existing tools:** the current crate push (`BGT_BLOCK` 2x2,
  `puzzle_on_block_moved`, hold-to-push), Titan Glove / Sauran push, Frost
  Vault's look. Rift Bomb or fuse bombs can shatter a decoy crate
  (shortcut, never required).
- **Procgen fit:** Generate backwards: place the sockets, then run "reverse
  slides" from the solved state for N seeded steps and keep the layout only
  if the forward BFS (state = crate positions on an 18x15 grid, at most 2
  crates, so at most about 70k states, host-side only) finds a solution in
  the target band. Reject layouts where a crate can be pushed into a
  corner that leaves the puzzle unsolvable *without* the reset rune being
  reachable.
- **Stage band:** Stage 4 Frost Vault (intro, 1 crate, 3–4 slides),
  Stage 5+ (2 crates, 5–8 slides). Never in Stages 1–3.
- **Budgets:** ROM ≈ 1.2 KB. WRAM 8 B (crate positions, socket mask). 0 OAM
  (crates are BG). 1–2 new BG tiles (ice floor, socket) or a palette swap of
  `BGT_FLOOR2`. SRAM 0.

### 3.2 Prism Toggle (color-switch barriers)

- **Mechanic:** Two barrier colors, red pillars and blue pillars. One is
  raised and one is lowered. Striking a crystal orb (any player hit: melee,
  shot, boomerang, bomb) flips both sets. Orbs sit in different pockets, so
  the hero must work out which side of which barrier to be standing on when
  flipping. This is the Oracle / LA crystal-switch room.
- **Existing tools:** `BGT_CRYSTAL` and `BGT_PILLAR` tiles with two CGB
  palettes, the Dungeon Law live-tile writer (`law_set`), the existing shot
  → tile hook in `projectile.c`. Boomerang and Hookshot let you hit an orb
  from across a barrier (shortcut).
- **Procgen fit:** State = (hero region, color). Generate a room as a small
  graph of pockets separated by colored barriers; BFS over (pocket, color)
  must reach the exit pocket; reject layouts solvable in fewer than 2 flips.
  Easy and cheap to verify. This kind is also the building block for the
  dungeon-wide Law Lock (§4.1).
- **Stage band:** Stage 1 (2 pockets, 1 orb), Stage 2–3 (3 pockets, 2
  orbs), Stage 5+ (4 pockets with a melee-only orb behind a barrier).
- **Budgets:** ROM ≈ 0.9 KB. WRAM 4 B. 0 OAM. 2 BG tiles (raised/lowered
  barrier) + 1 orb tile, or reuse `BGT_CRYSTAL` / `BGT_FLOOR2` with palette
  only. SRAM 0.

### 3.3 Ember Vigil (timed brazier lighting)

- **Mechanic:** Three or four cold braziers. Touching or striking one lights
  it, and it burns for a fixed time. All lit at once opens the seal. The
  flame shortens visibly (two-frame BG tile cycle plus a tick SFX in the last
  second). In later stages a cold wind vent snuffs the nearest brazier when
  you pass it.
- **Existing tools:** Sun Brazier art from Sun Lattice (reuse, lit/unlit
  palette), Ember Depths furnace telegraph, `sfx_play_rune` ticks.
  Projectiles, the boomerang (one throw can light two in a line) and
  Wolfkin's Will wave are shortcuts.
- **Procgen fit:** Place braziers from a seeded template; the Rust solver
  computes the shortest tour over BFS path lengths (at most 4! orders) at
  SPD 4 with no items, and the burn time is set to tour time × 1.4, clamped
  to a stage band. Rejected if the tour needs a dodge-dash.
- **Stage band:** Stage 3 Ember Depths (3 braziers, generous), Stages 5–8
  (4 braziers, tighter, wind vents from Stage 7).
- **Budgets:** ROM ≈ 1.0 KB. WRAM 6 B (4 timers + lit mask). 0 OAM (BG
  flames). Shares Sun Lattice brazier tiles; 1 extra cold-brazier tile.
  SRAM 0.

### 3.4 Kindred Weight (two-plate room with the companion)

- **Mechanic:** Two heavy plates must be held at once. The hero stands on one;
  the other needs a weight. ASK the companion to STAY on a plate (new ASK
  verb), or push a crate onto it. Later rooms add a third plate and a
  crate that must be routed around a pillar maze.
- **Existing tools:** Companion (Hearth / Aether / Way roles,
  `companion_ask.c`), crate push, plates (`BGT_SWITCH`).
- **Procgen fit:** The crate path is always present and solvable (BFS over
  crate position), so the companion is a shortcut, never required, which
  matters because the companion is optional and can be on cooldown. Solver
  checks the crate-only solution.
- **Stage band:** Stage 2 Verdant Hollow (1 plate + crate), Stages 4–7
  (2 plates, crate + companion shortcut).
- **Budgets:** ROM ≈ 0.8 KB plus about 0.3 KB for the companion STAY verb.
  WRAM 3 B. 0 new OAM (companion already drawn). SRAM 0.

### 3.5 Snag Gallery (boomerang and hookshot targets), optional rooms only

- **Mechanic:** A cache room behind a chasm or water. Gold target studs on the
  far side. Hookshot targets pull you across; boomerang targets must be
  struck in one throw (the boomerang's curve hits 2–3 in a row) to lower a
  bridge.
- **Existing tools:** Boomerang (`projectile_throw_boomerang`), Hookshot
  latch-and-pull (`hookshot.c`), `BGT_GATE_CHASM` / water gates.
- **Procgen fit:** Tool-gated, so it is only ever the optional third beat
  (§2.1) and only spawns when the hero owns the matching tool. The solver
  just checks target lines of sight and pull lanes.
- **Stage band:** Any stage after the Boomerang or Hookshot is found.
- **Budgets:** ROM ≈ 0.7 KB. WRAM 3 B. 1 target BG tile. SRAM: optional bit 5
  of `dungeon_puzzles`.

### 3.6 Hollow Mirror (mirror-room mimic)

- **Mechanic:** A Worldglass reflection of the hero (the "Hollow twin")
  moves mirrored left-right. Both the hero and the twin must stand on their
  plates at once. Pillars block the twin differently from the hero, so you
  use walls to "park" the twin while you keep moving. It ties the Riftwild
  glass that Carmelo liked into the dungeons.
- **Existing tools:** the hero's own metasprite drawn with a Hollow
  (Worldglass) palette in one entity slot, plates. (`enemy_mirror.c` is the
  Mirror Moth enemy, not a hero mirror, so the twin is new movement code.)
- **Procgen fit:** State = (hero cell, twin cell) on an 8x8 px coarse grid,
  BFS on host (≤ about 50k states). Generate by placing both plates, then
  pillar sets, keeping layouts with a solution in band and no zero-move
  start.
- **Stage band:** Stage 6 Shadow Keep (intro), Stages 7–9.
- **Budgets:** ROM ≈ 1.1 KB. WRAM 4 B (+1 entity slot). OAM: one 16x16
  metasprite (4 objects) for the twin; the room's guard pack is reduced
  by one body to stay under the per-line sprite limit. SRAM 0.

## 4. Dungeon-wide puzzles

All three use the existing per-stage lifecycle: state is in `run_state`,
cleared by `run_state_begin_dungeon`, written to SRAM bank 0 on every room
entry with the rest of the suspend save, and wiped on death. Any new byte is
**appended** to `run_state_t` with a new `PRE_*_RS_SIZE` constant in
`sram.c`. `sram_load_run` already zero-fills `run_state` before copying the
saved length, so older suspends load with the new state at zero.

### 4.1 Law Lock (crystal-switch color state across the dungeon)

- **What:** Promote Dungeon Law from scenery to a real dungeon-wide puzzle.
  Its WAX/WANE state already persists dungeon-wide. Law Lock adds **two or
  three mandatory route rooms** whose doorways or a body-wide corridor
  are blocked in one state and open in the other (same PRISM / THORN /
  STONE materials). Altars that flip the state are in a few rooms. The
  player has to plan which altar to visit and in what order, Oracle of Ages
  style.
- **State:** zero new SRAM. Reuses `run_state.dungeon_law` bit 7 (state)
  and the existing ready bit. The gated cells are derived from the seed and
  the mission graph at entry (not saved).
- **Map hints (Compass):** visited Law-gated rooms get a two-color barrier
  mark showing which state opens them; altars get an altar mark once seen.
  The Pack line (`PRISM/WAX`) stays. The Spirit Compass GOAL arrow takes
  state into account ("go flip first").
- **No-softlock guarantee:** Build the product graph (cell × state, at most
  30 × 2 nodes); an altar cell connects (c, 0) ↔ (c, 1). Accept a layout
  only if, from every (cell, state) reachable from (entry, initial state),
  the boss is reachable. In practice this means every Law-gated region has
  an altar on both sides, and no altar sits only behind a barrier of its
  own color. Altars are never placed in rooms that seal for combat
  until cleared. Thorn barriers stay crossable at a health cost, as today.
- **Procgen check:** Rust `law_lock::validate(seed, stage)` runs the
  product-graph BFS for 3000 seeds × 9 stages in CI, plus C↔Rust parity on
  the chosen gated cells and altars.
- **Start ≥ 7 rooms from the boss:** The gated cells are chosen from the
  mission graph's middle and deep thirds (never the foyer, never within 2
  cells of the entry, never the shop, sanctuary or boss). The required
  route length (BFS over the product graph from entry to boss) must stay
  ≤ 1.5× the plain maze distance, so the ≥ 7 rule doesn't turn into a
  20-room trek.
- **Stage band:** Stage 2 (one gated room, two altars), Stages 3–6 (two
  gated rooms), Stages 7–9 (three).
- **Budgets:** ROM ≈ 1.5 KB (validator + gate drawing), WRAM 60 B scratch
  for the product BFS (shared with the existing entry-cell BFS buffers
  in `run_state_entry.c`, only during room entry), SRAM 0, VRAM 0 (existing
  Law materials).

### 4.2 Colossus Cipher (clues scattered across rooms, answer at the boss door)

- **What:** Three to five Glyph Stones are scattered across the dungeon.
  Each one shows one rune and its position ("3rd: ◇"), and plays that rune's
  pitch when read. The sanctuary in front of the boss has a matching rune
  plate lock (the existing Rune Sequence code and pitches). Step them in
  the gathered order to open the boss gate. It reuses Carmelo's
  favorite musical plates and makes exploring pay off.
- **State:** one new appended byte, `dungeon_cipher`: bits 0–4 = stones
  read, bit 7 = gate opened. The order itself is derived from the seed, not
  saved.
- **Map hints (Compass):** read stones show a glyph mark on their cell
  (same bank-14 helper as #100's gold coin). The sanctuary's Compass mark
  shows `n/5`. Echo Chime pings the direction of the nearest unread stone;
  the companion's ASK can name the next missing position.
- **No-softlock guarantee:** The boss door is never a hard dead end. A wrong
  plate resets like today, but the **correct prefix chimes** (already how
  Rune Sequence gives feedback), so even with zero clues the worst case is
  n(n+1)/2 attempts (15 for 5 plates). Stones are on cells reachable
  without passing the sanctuary, never on the boss, sanctuary, shop or
  entry, and never inside an optional cache or secret.
- **Procgen check:** Rust validator confirms each stone cell is reachable
  from the entry in the plain maze **and** in every Law Lock state product
  (if both are active in one stage), and that stones are spread across at
  least two of the mission graph's thirds.
- **Start ≥ 7 rooms from the boss:** At least one stone is placed on a cell
  at distance ≥ 4 from the boss but off the shortest entry→boss route, so
  the run asks for one deliberate detour. Stones prefer existing mission
  cells (Warden, Sigil, Trial, Waystone) so they add almost no new route
  length.
- **Stage band:** Stage 4 (3 stones), Stages 5–7 (4), Stages 8–9 (5).
- **Budgets:** ROM ≈ 1.3 KB, WRAM 2 B, SRAM +1 B, VRAM 1 BG tile (glyph
  stone) + reuse rune plates.

### 4.3 Sunline Relay (light beam relayed room to room)

- **What:** Late-game set piece. A Sun Brazier in one room fires a beam that
  must leave through a doorway, cross 2–3 rooms of Sun Lattice vanes, and
  hit the Solar Obelisk beside the boss sanctuary. Each relay room is a
  normal Sun Lattice room whose target is a **door** instead of an obelisk.
  When a room's segment is correct, its exit door glows and the next room's
  entry door emits the beam.
- **State:** one new appended byte, `dungeon_relay`: bits 0–2 = which relay
  segments are solved. Segments freeze when solved, like solved Sun Lattice
  rooms. (If 4.2 and 4.3 ship together they can share one byte: cipher bits
  0–4 and relay bits 5–7.)
- **Map hints (Compass):** visited relay rooms show a sun mark, and the
  corridor between two solved segments is drawn lit, so the chain's
  progress is visible on the map.
- **No-softlock guarantee:** Segments can be solved in any order (each
  room's incoming beam is drawn even if the previous segment is unsolved,
  dimmed, so the player can set the vanes early). The relay opens a
  **shortcut and reward** (Sun Key that skips the Law Lock or a guaranteed
  rare item) in Stages 7–8, and only becomes the mandatory boss-door
  gate in Stage 9 after one more round of playtesting. Relay rooms are never
  combat-sealed after the room is cleared.
- **Procgen check:** Extends the Sun Lattice Rust generator with a
  door-target mode; CI runs the same 3000-seed parity and the per-segment
  solver. A chain is only placed along a path of 3–4 adjacent maze cells
  whose shared doorways are straight (no 90° wall seam to cross).
- **Start ≥ 7 rooms from the boss:** The chain ends at the sanctuary, so it
  naturally sits on the deep third of the route and does not add to the
  foyer distance.
- **Stage band:** Stage 7 Golden Temple (2 segments), Stages 8–9 (3).
- **Budgets:** ROM ≈ 1.0 KB on top of Sun Lattice, WRAM 3 B, SRAM +1 B
  (or shared), VRAM 0 (Sun Lattice tiles).

### 4.4 Considered and parked: dungeon-wide water level

A three-level cistern (valves raise/lower water in all rooms) is the classic
choice, but in Quintra Picsean swims and the Tide Raft crosses water, so
flooded rooms would be trivial for two of five heroes. It also needs
per-room flood redraws on entry and a 3-state product graph. Park it until
there is a water-only mechanic (floating crates that rise with the water)
that swimming does not bypass.

## 5. Rollout order

Each step is its own PR with its own short spec addendum, tests and a
playtest build; implementation waits for Carmelo's go-ahead.

1. **Framework + Prism Toggle.** Per-stage puzzle pool table, slot
   no-repeat rule, Rust mirror skeleton, Prism Toggle in Stages 1–3. Also
   upgrade Push Seal so the crate must reach a socket (it is currently one
   push). Cheapest visible variety.
2. **Law Lock** (dungeon-wide, zero SRAM). Builds directly on Prism Toggle
   and existing Dungeon Law.
3. **Rime Slide** for Frost Vault onward.
4. **Colossus Cipher** (dungeon-wide, +1 SRAM byte), reusing the rune
   plates and #97's louder notes.
5. **Ember Vigil** and **Kindred Weight** (with companion STAY).
6. **Hollow Mirror** for Shadow Keep onward.
7. **Sunline Relay** for Golden Temple onward.
8. **Snag Gallery** as the optional third beat once items 1–3 are in.

Resulting vocabulary (two mandatory slots + dungeon-wide):

| Stage | Mandatory room kinds in pool | Dungeon-wide |
|---|---|---|
| 1 Crystal Caverns | Push Seal (socket), Rune Sequence, Prism Toggle | — |
| 2 Verdant Hollow | Rune Sequence, Prism Toggle, Kindred Weight | Law Lock (1 gate) |
| 3 Ember Depths | Sun Lattice, Ember Vigil, Prism Toggle | Law Lock |
| 4 Frost Vault | Sun Lattice, Rime Slide, Kindred Weight | Law Lock + Cipher (3) |
| 5 Toxic Mire | Sun Lattice, Rime Slide, Ember Vigil, Prism Toggle | Law Lock + Cipher (4) |
| 6 Shadow Keep | Sun Lattice, Hollow Mirror, Kindred Weight | Law Lock + Cipher (4) |
| 7 Golden Temple | Sun Lattice, Hollow Mirror, Ember Vigil | Cipher (4) + Relay (2) |
| 8 Bloodmoon | Sun Lattice, Rime Slide, Hollow Mirror, Ember Vigil | Law Lock + Relay (3) |
| 9 Void Sanctum | any two, no repeats | Cipher (5) + Relay (3) |

Stages 7–9 run at most two dungeon-wide systems at once to keep the
product-graph checks and the player's head small.

## 6. Recommendation

Start with **Prism Toggle + Law Lock** (rollout steps 1–2). Together they give
the clearest "this dungeon is one machine" feeling for the least risk: no
new SRAM, no new OAM, reuse of the Law tiles and live-tile writer, and a
tiny product-graph validator that's easy to prove. Then **Colossus Cipher**
as the second dungeon-wide puzzle, because it turns exploration into the
boss-door answer and reuses the music plates. Rime Slide is the best
single-room addition for the Frost Vault identity. Hold Sunline Relay until
the Lua balance bot can solve Sun Lattice rooms (a known gap today).

## 7. Questions for Carmelo

1. Is **Prism Toggle + Law Lock** the right first pair, or would you rather
   start with Rime Slide (ice) or the boss-door Cipher?
2. Should the Colossus Cipher be a **hard** boss-door gate (with prefix
   chimes so it can never softlock) or only a shortcut/reward?
3. Is it OK for Dungeon Law to stop being optional scenery and gate the
   route in 1–3 rooms per dungeon?
4. Companion: may Kindred Weight add an ASK "STAY on plate" command, given
   the crate always works as a fallback?
5. Timed puzzles (Ember Vigil): fine at the new slower starting speed with
   about 40% slack, or skip timers entirely?
6. Hollow Mirror uses Worldglass's look in dungeons. Do you want that tie-in,
   or keep Worldglass Riftwild-only?
7. Water-level cistern: parked because Picsean and the Tide Raft bypass
   water. Agree, or do you want it anyway with a swim-proof twist?
8. More puzzles per dungeon: keep two mandatory slots and add the optional
   third beat, or go to three mandatory puzzle rooms in Stages 5+?

## 8. Batch 1: decisions and as-built (Prism Toggle, Law Lock, Push Seal socket)

Carmelo's answers to §7: (1) Prism Toggle + Law Lock first, Push Seal gets a
real socket; (2) Colossus Cipher is a shortcut only, later; (3) Law Lock may
gate 1–3 required rooms; (4) companion STAY approved but later; (5) timed
puzzles OK with generous windows, none in this batch; (8) keep two mandatory
slots plus an optional third beat (bit 5, not in this batch).

### 8.1 Puzzle pool (`puzzle_slot_kind`, mirrored in `quintra_topology.py`)

`mix = xor(run_seed bytes) + stage * 51`. Stage 1 picks from
{Push Seal, Rune, Prism} and Stage 2 from {Rune, Prism, Push Seal}; slot 0
(Trial) takes `mix % 3`, slot 1 (Waystone) a different entry, so one dungeon
never repeats a kind. Stages 3–6: Waystone becomes Prism Toggle on
`(mix >> 3) & 1`, else Sun Lattice; Trial stays Sun Lattice from Stage 3 on,
so Sun Lattice is still guaranteed every dungeon. Stages 7–9 are unchanged.

### 8.2 Prism Toggle as built (`src/game/prism_toggle.c`, bank 255)

- Five hand-authored 12×11 chamber templates in tiers (Stage 1: tier 0,
  2 flips; Stages 2–3: tier 1, 3 flips; Stages 4–6: tier 2, 4 flips), with
  a seeded mirror and colour swap. Chamber sits in a walkable floor ring;
  the goal is a 2×2 gold seal inside the chamber.
- Amber barriers use the CRACK palette, azure the CRYSTAL palette. Raised =
  solid `BGT_PILLAR`, lowered = tinted `BGT_FLOOR2`, so both states read by
  colour. The orb glows in the colour that is currently raised.
- Any player hit flips: melee, shot, boomerang, bomb blast, Hookshot (hook
  retracts). 20-frame cooldown; orbs never shatter; hostile shots never flip.
- A barrier that would rise under the hero waits (up to 6 pending tiles)
  until the hero steps clear, so a flip can never entomb the player.
- Feet on the seal opens the room, persists the slot bit and lowers every
  barrier. Leaving re-generates the unsolved chamber from the room seed.
- Proof: `quintra-procgen::prism_toggle` parses the C templates, models
  melee, ranged (range 3 + line of sight) and deferred raises, and proves for
  every template × mirror × swap that the goal is reachable by melee alone
  from every state reachable by any tool, and that each tier needs at least
  its flip budget. `scripts/test_prism_toggle.py` checks ROM == Rust tile for
  tile on Stages 1/2/3/6, colour clarity, a live melee flip, the unbreakable
  orb and the seal.

### 8.3 Push Seal socket

The crate no longer solves by moving one tile. Each room places a 2×2 gold
socket on an L route (2–3 horizontal + 2–3 vertical shoves) inside a cleared
apron; only seating the crate on the socket opens the seal. The socket glows
DOOR-gold and repaints after the crate passes over it.
`quintra-procgen::push_seal` mirrors the layout and runs a sokoban BFS from
every apron start; the live test seats the crate with real pushes.

### 8.4 Law Lock as built (`src/game/law_lock.c`, `law_lock_gen.c`, bank 255)

- Stage 1 is Law-free. Stages 2–3 try 1 gate, Stages 4–6 try 2, Stages 7–9
  try 3, falling back to fewer when no placement passes the caps below.
  Over 3000 seeds a Law Lock is generated in 41% of Stage 2, 71% of
  Stage 3 and 78–99% of Stage 4–9 dungeons.
- A gate is one maze **doorway** on the required tour (never a mid-room
  divider), drawn as a solid two-tile `BGT_PILLAR` pair while closed and an
  ordinary door while open. The pillar wears the colour of the state that
  opens it: cyan (Crystal palette) = opens in WAX, warm (Crack palette) =
  opens in WANE. Prism/Thorn/Stone ambient aprons are untouched, so nothing
  can shatter or damage-boost through a gate.
- Gates never touch the entry, the first three cells, the last three cells,
  or the Deep Switch / Deep Phase Gate cells. Altars never sit in a gate
  room, a mission-role room, the cache, the rift-portal rooms (2, 8) or 15;
  so the state never changes while you stand in a gated room, and a suspend
  (the Law bit saves on every flip) always reloads into one connected court.
- An altar (`BGT_SWITCH`) stands three tiles inside the room's first real
  doorway on a carved 2×4 apron; contextual A or a melee hit flips it. It
  replaces the ambient every-sixth-cell Law altar in Law Lock dungeons.
- Zero new SRAM: gates and altars are a pure function of (run seed, stage);
  the WAX/WANE state is the existing `dungeon_law` bit 7. WRAM: ~0.4 KB of
  generator scratch.
- Compass: a gate corridor wears its opening colour, a charted altar shows
  the active colour, `LAW` in the legend is drawn in the active colour, and
  when the route must flip first the GOAL marker points at that altar. The
  director/Compass route is a BFS over (cell × Law state).
- Proof: `quintra-procgen::law_lock` mirrors the C generator; the
  `law_lock_parity` cargo test compiles `law_lock_gen.c` on the host and
  compares it for all 9 stages × 3000 seeds. The validator BFSes the
  (cell × state) product graph (every cell reachable, undirected, so no
  state can strand you), checks the 1.5× and +4/+6/+7 direct-route caps,
  and a bitmask BFS over (cell × state × objectives) caps the full
  mission-tour overhead at +6/+10/+12 (worst seen: 4, 6, 6, 6, 6, 8, 6, 9).
  `scripts/test_law_lock.py` checks on the cartridge (Stages 2/5/8) that
  the gates and altars equal Rust (so the cart's maze and roles match
  `topology.rs`), both states of a gated doorway, the altar flip and its
  save byte, and the Compass legend colour.

### 8.5 Known gaps

- `scripts/quintra_balance_bot.lua` has no Prism, socket or Law Lock policy
  (not in CI).
- Argon's tighter per-band ratios (1.35× Stages 2–3, 1.45× Stages 4–6) are
  not applied: they cut Law Lock frequency to 34% / 59% in Stages 2–3. The
  absolute tour caps (24/32/38) are below many plain mission tours, so they
  are not enforced either.
- Optional third puzzle (bit 5) is a later PR.

## 9. Argon review (round 4, against main @ 1c522cfc)

Full text: Gemini Bridge `round4/puzzles.md`. Adopted:

- **A. Law Lock.** Barriers only on doorway aprons (mid-room dividers
  softlock on suspend); mandatory gates are solid pillars, never Crystal or
  Spikes; Law Lock stays off Deep Phase Gate cells; altars never in gated
  rooms; the director routes over (cell × state) so the Compass never points
  into a closed gate. No-softlock validator over the product graph across
  many seeds in `cargo test`.
- **B. Colossus Cipher** (later batch, shortcut only): a resonance lock —
  k−1 stones energise the room and the last rune is deduced; the Compass
  shows dim glyphs on visited stones and a GOAL marker after you enter the
  Sanctuary.
- **C. Sunline Relay is replaced by Solar Conduit:** a single hub in the
  Sanctuary (Solar Obelisk plus 2–3 wall Conduit Prisms), each lit by a
  self-contained Sun Lattice receptor room. No cross-room beam steering.
- **D. New proposal: Worldglass Echo.** Rift Mirrors in 2–3 rooms shift the
  whole dungeon between Waking and Hollow (0 new SRAM, maybe `dungeon_law`
  bit 2). Not scheduled.
- **E. Route caps.** Keep the 1.5× entry-to-boss cap and add a
  mission-tour overhead check (bitmask BFS) in `quintra-procgen` — done in
  §8.4.
- **F. Roster.** Ship Prism Toggle first (this batch), then Rime Slide.
  Ember Vigil without wind vents; keep Hollow Mirror. **Snag Gallery is
  deferred. Kindred Weight is cut.** Required rooms stay solvable with base
  movement and melee.
