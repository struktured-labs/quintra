# Secret merchants: one Veil Trader per stage (proposal)

Date: 2026-11-16. Status: **proposal for Carmelo's review.** Spec only;
no ROM change in this PR. Carbon reviewed the first draft (2026-11-16,
ship-with-changes); the numbered fixes in §12 are folded in here.

Source request (Carmelo, verbatim):

> The game also needs one secret merchant per stage

Facts below were read from `main @ c8c3bb52`, plus the open power-up /
gem-currency proposal (`docs/superpowers/specs/2026-11-16-temporary-powerups.md`,
PR #120) and the implemented hidden-den and merchant-stock work.

## 0. What already exists (do not duplicate)

| Thing | Where | Notes |
|---|---|---|
| **Public dungeon merchant** | `run_state_is_shop()`, cell `size-3`; `shop.c`, `procgen.c` | Five shelves, no enemies. Heart 10, random stat 25, two featured build/tactic shelves (15–35), Antidote 12 that **restocks every visit**. Talk across the counter (`2026-11-12-merchant-counter-reach.md`). |
| **Village civic shops** | market, forge, apothecary, chartwright | Heart 5, weapon 30, Iron Heart 35, Surge 20, Power Stone 30, Vampiric Sigil 35, Mana Gem 30, Chart 15, Antidote 12. |
| **Riftwild wayside trader** | Riftwell crossing | Antidotes at 12. Not a secret. |
| **Stock persistence** | `run_state.shop_bought` / `shop_civic`; `#24`, `2026-11-09-merchant-stock.md` | Four dungeon bits + four market bits. Unique wares stay sold; they are not replaced mid-visit. Both bytes clear when the next dungeon begins. Antidote is the fifth shelf and is not bit-backed, so it returns. |
| **Compass coin** | `map_marks.c`, `BGT_MAP_BIG_SHOP` / `BGT_MAP_SHOP` | Gold coin only after a real visit. A Chart can reveal the room without the coin. Same small coin on the Riftwell trader and the village Market. |
| **Hidden dungeon verbs** | `puzzle.c` `HIDDEN_SECRET_SHOT/WALK/PUSH`; `room_open_secret`; bombs / Morningstar already burst cracked walls | Ordinary secrets already pay vault overlays. Opened mouths stay enterable (`2026-11-09-secret-door-seal.md`). |
| **Riftwild dens** | `2026-11-15-riftwild-hidden-dungeons.md`, PR #110 | 3 dens/region, subtle tells, tool gates, 0 new SRAM, no stat rewards. Echo Chime marks a faint chest. |
| **Farfold cache** | `run_state_dungeon_cache_cell()` | Class relic in a dead-end. Claimed in `dungeon_phase`. |
| **Power Shrines** (proposed) | PR #120 §2.2 | One shrine per stage in a dead-end, plus one per Riftwild region. Secret merchants must not share that cell. |
| **Currency** | `player.coins`, `COIN_CAP = 999` | Gold coins today. PR #120 §10 optionally restyles the same value as rupee-like **Shards** (green 1 / blue 5 / red 20 / gold 50) with value-based SFX. Prices stay numerals. Carmelo has not decided. This spec prices in the existing integer unit and stays compatible with Shards. |
| **Temporary power-ups** (proposed) | PR #120 | Capsules and shrines: Aegis, Limitless, Mend, Formation, Halo, Long Reach, Blast Assist, Wingmates, plus optional Clarity / Lodestar / Stillwater / Nova / Overwill. Short (8–20 s). One timed slot. |
| **Waypoint wayfarers** | `procgen.c` (is_waypoint) | Peaceful witnesses already spawn in dungeon turn courts. The Veil rumour uses one of these, not a new NPC class. |

Campaign stages (nine dungeons; a village and a Riftwild visit punctuate the
road). Sizes from `run_state.c` (`stage_start` / `stage_boss_room`):

| Stage | Name | Cells | Public shop cell |
|---|---|---|---|
| 1 | Crystal Caverns | 20 | 17 |
| 2 | Verdant Hollow | 21 | 18 |
| 3 | Ember Depths | 22 | 19 |
| 4 | Frost Vault | 23 | 20 |
| 5 | Toxic Mire | 24 | 21 |
| 6 | Shadow Keep | 25 | 22 |
| 7 | Golden Temple | 26 | 23 |
| 8 | Bloodmoon | 28 | 25 |
| 9 | Void Sanctum | 30 | 27 |

Public shop is always `size-3`; sanctuary is `size-2`; the colossus is `size-1`.

## 1. Goal and non-goals

**Goal.** Exactly one hidden **Veil Trader** in each of the nine stages,
and a few hidden **cave merchants** in each Riftwild region (§6). Finding
one should feel like a Zelda 1 secret: a fair, biome-native tell, a verb
you already have, a quiet stall *inside a cave or vault*, and stock you
cannot get on the public counter.

**Cave rule (Zelda 1).** Every secret merchant — Veil Trader and Riftwild
cave merchant alike — lives *inside* a hidden cave or vault. The overworld
field and the dungeon host room never show the keeper or the shelves in
the open. Only a concealed entrance is visible outside. Carmelo
(2026-11-16): "But merchants are hidden in caves like Zelda 1 not out in
open." The one exception is the existing **Riftwell wayside trader**,
already a known open-air Antidote stall; this spec does not move or hide
it, and it is not a secret merchant.

**Non-goals.**

- No second public merchant, and no change to public / village / Riftwell stock
  or prices.
- No secret merchant in a village (those already have four civic shops).
- No open-air secret stall in Riftwild or in a dungeon host room. Secret
  merchants are cave interiors only (§6).
- No stat-cap relics (Iron Heart, Mana Gem, Power Stone, and the rest of the
  dens' excluded list). The stall is for rare power, consumables, and one
  signature charm.
- No new SRAM migration story beyond appended bytes; older suspends load as
  "not found, nothing bought."
- No burnable-bush entrance in v1: the cartridge still has no fire tool
  (see the dens spec). If one ships, a bush tell can be added as an
  alternate for CAVE-THICKET.

## 2. Placement

One **host cell** per stage, chosen from the run seed, stable for the whole
run, and never on the required spine.

**Excluded cells:** start (local 0), public shop (`size-3`), sanctuary
(`size-2`), colossus (`size-1`), Farfold cache cell, mini-boss cells, and
every mission-graph role (trial, sigil, warden, waystone, deep warden / switch
/ gate). If Power Shrines have shipped, also exclude that stage's shrine cell:
hash the Veil host first (`run_seed ^ stage * 0x9E3779B9 ^ 'VEIL'`), then let
the shrine pick from what remains, so the two specs cannot collide.
Riftwild shrine cells are reserved after dens and after the cave merchants
in §6.2, never the other way around.

**Prefer** a dead-end or off-path room with a wall or water edge that can hold
the tell (same instinct as the Farfold filter). If the first candidate has no
legal tell edge, walk the hash. Every current stage has 20–30 cells and only
about a dozen reserved, so a host always exists.

**Stage 7 extra filter:** prefer a host that already rolled a Sun Lattice
fixture off the spine. If none of the legal candidates has one, the Veil
post-pass stamps a self-contained mini-lattice (one emitter + one turnable
vane + the gold-rim plate) so the gate is always completable in that room.

The hash is a standalone xorshift32 chain. It must **not** consume the room
RNG, so `test_procgen_parity.py` stays green for ordinary rooms.

**Host-cell post-pass.** `procgen` runs unmodified first (parity holds for
every non-host room). Then a post-pass on the *single* Veil host cell:

1. Strips any ordinary `HIDDEN_SECRET_*` or amber-crack vault that landed
   there, so the room never has two overlay mouths (`room_open_secret` is
   one pair; Echo Chime and Cave Light must not have two targets).
2. Stamps the stage’s Veil tell, gate fixtures (braziers, mini-lattice,
   reed island, hook gap, and so on), and, once `mouth_open` is set, the
   16 px vault mouth.

The host room may still be a quieter combat room. **The trader is never
standing in that room.** Opening the tell paints a vault mouth
(`room_open_secret` / the existing 16 px `BGT_DOOR` pair). Walking in
enters a **compact cave-vault stall** (no enemies, no graph exit), then
returns to the host at the mouth. Until the mouth is open, the host
contains only the tell; after it is open, only the mouth. The shelves
exist solely inside the vault, same as a Zelda 1 dungeon cave. Opened
mouths stay enterable after a leave and a return, same contract as
`2026-11-09-secret-door-seal.md`, keyed on `secret_shop` bit 2 (`mouth_open`),
not on `dungeon_phase` hidden-secret slots.

**Stage 5 return.** The overlay exit must land the hero on a dry reed tile of
the 3×3 island, never in the mire. Tide Raft is still usable from that shore,
so a non-Picsean champion is not soft-locked.

## 3. Per-stage concealment

Each stage uses a different verb so a player who finds one does not
auto-solve the next. Tells are **never** the ordinary amber crack
(`BGPAL_CRACK`): that crack is the dungeon’s public secret language. A Veil
tell matches the biome art except for one quiet difference, the same rule
dens use for the standing stone.

**Palette rule.** Tells use intra-palette index shading or 1–2 biome BG
tile swaps (for example colour index 1 instead of 2 in the existing wall
ramp). They never spend a new CGB BG palette. Sparkles, smoke puffs, bank
bubbles, and the Void star-dot are either a 2-frame BG tile anim or **at
most one OBJ**, so a host room that still has enemies does not blow the
10-sprites-per-scanline limit.

Gates use verbs the campaign has already taught, or a class innate, by the
time that stage begins. Region 1 Riftwild awards the Glove, then the Raft,
then the Hook on the three post-boss visits, so stages 5–9 may ask for Raft
or Hook; stages 1–4 may not *require* them. Stage 4 also accepts the Glove
as an alternate so every Region 1 waygear shows up somewhere.

| Stage | Tell (always visible from the floor) | Gate | Hint extras |
|---|---|---|---|
| 1 Crystal Caverns | A hairline crack in a crystal wall, **biome-coloured**, not amber. A single paler shard sits in the floor pointing at it. | Primary shot **or** a bomb / Rift Bomb / Morningstar. Stage 1 is always solvable without a B-item. | The shard faintly sparkles every 2 s. |
| 2 Verdant Hollow | A curtain of ivy that matches the grove wall, except one leaf tile is flipped. | Walk into the ivy (`HIDDEN_SECRET_WALK`). No item. | A short trail of fallen leaves leads into the curtain. |
| 3 Ember Depths | A dark kiln vent, unlit among lit ones, with a thin smoke puff every 3 s. | Shoot the vent (`HIDDEN_SECRET_SHOT`). Bombs also count. | The puff is the tell; the vent is one intra-palette step darker, not a new palette. |
| 4 Frost Vault | One ice block is a half-shade paler and sits one tile off a wall socket. | Push the block into the socket (`HIDDEN_SECRET_PUSH`), **or** lift it with Titan Glove / Sauran and set it in the socket. Push always works, so Stage 4 is never Glove-gated. | A faint scrape already marks the socket. |
| 5 Toxic Mire | A 3×3 reed island in the mire with a dark stair, visible but dry-path unreachable. | Tide Raft or Picsean swim (taught in region 1 Riftwild). | Bubbles rise on the near bank, pointing at the island. |
| 6 Shadow Keep | Four unlit braziers in a side alcove; one is already smoking. | Light all four (existing shot / strike on the brazier fixtures, or the stage’s lamp verb). The mouth opens as the puzzle reward. Combat seals do not block this mouth once it is open. | A soot trail runs from the smoking brazier along the floor to the blank wall. |
| 7 Golden Temple | A blank wall plate where a Sun Lattice beam can rest; the plate has a faint gold rim. | Bounce or turn a beam onto the plate (Sun Lattice is already in Stage 3+). Host selection / post-pass guarantee a live emitter in this room (§2). | The rim glints only when any beam is live in the room. |
| 8 Bloodmoon | A gargoyle ring or blood-iron sconce on a far ledge, across a narrow crimson gap, with a dried drip trail to the near edge. | Rift Hook or Corvin innate: latch the ring and pull across. Primary shots and bombs do **not** open it — Stages 1 and 3 already taught shoot-the-odd-wall. Hook is guaranteed by region 1 Riftwild before this stage. | The drip points at the gap; the ring is one intra-palette step brighter. |
| 9 Void Sanctum | A floor pit that looks lethal but is one tile paler than a real void hole, with a tiny high-contrast star-dot in its centre. | Walk into the pit (`HIDDEN_SECRET_WALK`). It becomes a stair, not a fall. | The star-dot twinkles. Echo Chime makes the pit flash as a stair for 2 s. The Stage 9 wayfarer rumour is placed so it is reachable **before** the host cell, so nobody has to trial-and-error pits on a low-contrast screen. |

**Shared hint rules (fairness):**

1. The tell is in the room even if the player never uses a tool. No
   fully invisible walls.
2. **Echo Chime** in the host room flashes the tell and, if the stall is
   still unfound, sets `chime_hinted` and marks a **faint small coin** on
   that cell of the Compass (reuse the dens’ “dim chest” pattern, but with
   `BGT_MAP_SHOP` at a dim palette, no new map tile). The bit survives
   suspend and leaving the room.
3. One seeded **wayfarer rumour** in the same dungeon, spoken by an
   existing waypoint wayfarer (not a new NPC), names the *method*, never
   the cell, e.g. `A WALL IN THE ICE / ANSWERS A PUSH`. In Stage 9 the
   rumour is on a waypoint that graph-reaches from the start without
   crossing the host cell.
4. A Chart does **not** print the coin. Companion ASK does not volunteer
   the cell. Knowledge is earned by eye, Chime, or rumour.
5. After the player actually enters the stall, the host cell wears the
   ordinary small gold coin (`BGT_MAP_SHOP`). The public merchant keeps the
   **big** gold coin (`BGT_MAP_BIG_SHOP`), so the two are distinct on the
   same map with no new tiles.

## 4. The stall

- Quiet cave-vault overlay. No enemies. The keeper is only here, never
  in the host room. One Veil Trader behind a short counter of
  **three shelves**. Reuse counter-reach (56 px vertical, 24 px sideways,
  must face the keeper) and “standing on a ware never talks.”
- Talk first: a one-line biome greeting, then the existing `TODAYS WARES / COST`
  catalog (`shop_write_live_stock`) with icon, effect, and numeric price.
- Touch buys. Unaffordable wares refuse by name (`#101`, no silent refusal).
- The keeper reuses `SPR_MERCHANT` with a **veil palette** (violet / dusk,
  pal 6 when the room atlas allows it) so the public merchant and the Veil
  Trader read as kin, not twins. No new combat tiles. A hooded 16×16 variant
  is optional later (GPT Image), not required to ship the stall.

## 5. Stock and prices

Three shelves, unique per stage.

| Shelf | Role | Persistence |
|---|---|---|
| A | Stage tonic (consumable), drunk at the counter | **Restocks** every visit, like the public Antidote. No bought bit. |
| B | Bottled power-up. **Does not activate in the stall.** Buying it sets `bottle_armed` and spends the coins. The bottle **uncorks on the next combat-room entry** (any hostile room, including a mini-boss or colossus, but not the host if it has already been cleared, and never the stall itself). The HUD notice fires at uncork, not at the counter. | Sold out for the rest of this dungeon. If the player suspends or finishes the dungeon with the bottle still armed, it uncorks on the next combat entry that still belongs to this run and dungeon; a new dungeon clears `secret_shop` and the arm is lost (the coins stay spent — this is the same “power faded on resume / stage change” instinct as Surge). Prefer to uncork before that: the notice on purchase says `ARMED - NEXT FIGHT`. |
| C | One signature veil charm | Sold out for the rest of the **run** once owned. If already owned, the shelf is empty; it is not replaced by a lesser relic. |

Shelf B is deferred because PR #120 durations are 8–20 s and Nova is an
instant combat effect. Activating inside a peaceful overlay would spend the
purse on a buff that expires in the corridor, or on a Nova that hits no one.
The latch uses `secret_shop` bit 4 and no pack slot.

Prices sit above the public counter so the secret is a discovery *and* a
spend decision, not a free upgrade. Public reference: heart 10, Antidote 12,
Chart 15, Surge 20, featured 18–35, village heart 5. Mid-dungeon purses are
often in the 30–80 range if the player has been exploring; late-run purses
can sit much higher under `COIN_CAP` 999. Stage 1 is priced so an explorer
can realistically afford Cave Light without a village or a Riftwild purse.

| Band | Price | Notes |
|---|---|---|
| Tonic | 16–20 | Always at least a heart plus a small rider. Never a plain 16-coin heart (public hearts are 10). Never cheaper than Antidote. |
| Common power-up (Mend, Aegis, Limitless) | 24 | Public Surge is 20. |
| Uncommon (Formation, Halo, Long Reach, Blast Assist) | 36 | |
| Rare (Wingmates, Clarity, Lodestar, Stillwater, Nova, Overwill) | 48 | Stillwater and Nova are safe on Shelf B only because of the combat-entry latch. |
| Signature charm | 32–70, rising with the campaign | Cave Light is 32 so Stage 1 is payable. |

If PR #120’s gem Shards ship, **do not rewrite these numbers**. The HUD
glyph may become a green Shard; the tag still prints `36` (or `36G` as the
catalog does today). A 50-cost charm equals one gold Shard, or two red and
two blue, but the stall does not show a gem recipe — numerals stay more
readable (§10 of the power-up spec).

If temporary power-ups have not shipped yet, shelf B sells a **Grand Surge**
(the existing Surge effect at 24 coins, 20 s instead of 15) as a stand-in,
then swaps to the staged bottle once Phase 2+ is in. The stand-in also uses
the combat-entry latch, not a stall-side activation. The secret-merchant
spec does not block on PR #120, and it does not implement power-ups itself.

### 5.1 Per-stage shelves

Power-up bottles match the biome. Durations, boss clipping, and the single
timed slot are whatever PR #120 ships; the stall only sells them and arms
the latch.

| Stage | A. Tonic (restocks) | B. Bottle (once / dungeon, uncorks in next fight) | C. Signature charm (once / run) | Charm price |
|---|---|---|---|---|
| 1 Crystal Caverns | Crystal Tonic: heal 1 heart and restore 1 MP, 16 | Aegis (common, 24) | **Cave Light** — on entering a room, cracked walls and Veil tells glint for 1 s, once per room. Teaches secret-hunting for the rest of the run. | 32 |
| 2 Verdant Hollow | Bloom Salve: heal 1 heart and clear Poison, 18 | Mend (common, 24) | **Honeycomb Charm** — hearts and coins inside 24 px drift to the hero (a small, permanent Lodestar; does not extend drop rate). | 45 |
| 3 Ember Depths | Ash Draught: heal 1 heart and clear Burn, 18 | Blast Assist (uncommon, 36) | **Cinder Veil** — the first Burn that would apply in a room is ignored. | 40 |
| 4 Frost Vault | Rime Tonic: heal 1 heart and restore 1 MP, 16 | Stillwater if shipped, else Aegis (rare/common, 48/24) | **Rime Skates** — ignore ice slow, and gain 20 extra frames of warning on fading floors. | 45 |
| 5 Toxic Mire | Filter Flask: Antidote effect + 1 heart, 20 (drunk at the counter; does not add a fourth Antidote to the pack) | Clarity if shipped, else Limitless (rare/common, 48/24) | **Filter Mask** — Poison ticks half as often, and a lethal Poison tick cannot land while an Antidote is in the pack (the existing auto-break still fires first). | 50 |
| 6 Shadow Keep | Shade Tea: 1 heart + 2 MP, 20 | Formation (uncommon, 36) | **Gloam Lamp** — fading and collapsing floors flash 20 frames earlier; unlit braziers, hidden floor switches, and mimic / ambush tiles glint on entry. It does **not** also glint Veil tells (that is Cave Light’s job; owning both just stacks the longer floor warning with the secret glint). | 50 |
| 7 Golden Temple | Sun Wine: full MP, 24 | Limitless (common, 24) | **Sun Seal** — in a Sun Lattice room, the next correct vane or plate glints once when the puzzle becomes live. | 55 |
| 8 Bloodmoon | Crimson Draught: 1 heart and clear Bleed, 18. No timed ATK buff, so it cannot collide with the single power-up slot or with an armed Shelf B bottle. | Wingmates (rare, 48) | **Crimson Pact** — while at half health or less, ATK +1 with a visible red aura. Not a cap raise; it drops when health rises. | 60 |
| 9 Void Sanctum | Void Dew: 1 heart + 2 MP, 20 | Nova if shipped, else Wingmates (rare, 48). Nova uncorks on the next combat entry, where it can actually clear shots and hit foes. | **Last Light** — the first lethal hit of the run instead leaves 1 half-heart and 2 s of iframes, once. Phoenix Thread, if carried, still has priority and does not consume Last Light. | 70 |

A full Stage 1 buy is 16 + 24 + 32 = 72, and Cave Light alone is payable
from a careful first-dungeon purse. Sun Wine is 24, above the public Spirit
Draught’s 18, because it is a full MP top-up with no Surge attached.

**Charm rules.**

- They are **run-long, always-on flag charms**, not inventory TOOL slots
  (same idea as Waygear: owned, never equipped). They appear as a compact
  `VEIL` row on the Pack page so the player can read what they have. This
  avoids filling the 16-slot pack late in a run.
- **Pack art:** a 9-pip glyph strip from two shared tiles (lit vs unlit
  pip). The cursor inspects a pip and the existing text window prints the
  name and effect; only the *highlighted* charm loads its 8×8 icon (one
  dynamic tile). Do not try to show nine distinct icons at once by
  swapping one or two tiles.
- They never raise permanent stat caps.
- They never invent a new verb the cartridge does not already have a hook
  for: glints reuse Echo Chime / secret flash, the honeycomb magnet reuses
  the Boomerang fetch radius idea at a shorter range, floor warning reuses
  the existing fade flash, Sun Seal is a one-shot glint on fixtures that
  already exist, Crimson Pact is a conditional ATK flag, Last Light is a
  one-shot lethal intercept next to Phoenix.
- Buying a charm prints a named notice (`#101`).

Shelf A tonics are drunk immediately; they do not occupy the power-up
slot and they do not add a fourth Antidote to the pack.

## 6. Riftwild cave merchants

Carmelo (2026-11-16): "Rift wild should definitely have a few merchants."
And, separately: "But merchants are hidden in caves like Zelda 1 not out
in open." This section is the answer. The existing Riftwell wayside
trader and the three dens per region stay as they are.

### 6.1 Count and role

**Three hidden cave merchants per Riftwild region** (the middle of
"about 2–4"), one in each two-row band, plus the open Riftwell trader
(unchanged). A full run therefore has nine cave stalls in the wild, on
top of the nine Veil Traders. If a band has no legal field after the
exclusions below, that band is skipped; a region always places **at
least two** caves, so the count stays inside 2–4. When only two caves
place, the permutation is applied to the *placed* bands and must
include **CAVE-STONE** (so the region Wild charm is obtainable) and
at least one no-item kind (STONE or THICKET) whose Hollow-only flag
is off, so visit-1 Waking still has a cave that opens without the
Warden’s Glove.

They are not dens. A merchant cave is a **single-room shop** with no
keeper-boss, no reward chest, and no stat relics. Dens keep their chest
or trial payoff; these caves only sell.

### 6.2 Placement

**Candidates** are the same no-fixture fields dens use, minus fields
that already hold a den, minus Hollow relic fields {22, 35}, and minus
the Riftwell (the open trader is already there). Power Shrines, if PR
#120 has shipped, pick from what remains *after* caves, and must not
be subtracted first — otherwise they would shift the `'CAVE'` hash.
On today’s fixed layout the dens’ 20 candidates split 7 / 7 / 6 per
band; after three dens that leaves 6 / 6 / 5, so all three bands place.
A future seeded layout may still trip the two-cave fallback in §6.1.

**Hash order**, all isolated xorshift32 chains that never consume the
room RNG:

1. Dens (already shipped): `run_seed ^ region * 0x9E3779B9 ^ 'RIFT'`.
2. Cave merchants (this spec): `run_seed ^ region * 0x9E3779B9 ^ 'CAVE'`,
   picking from what dens left.
3. Power Shrines (PR #120): pick from what remains.

**Spread:** one cave per two-row band (rows 0–1, 2–3, 4–5), always a
different field from that band’s den, so a biome slice never hides a
den and a shop in the same screen.

**Tell spot** inside the field: a quadrant 4–8 tiles from the central
trail cross, visible from the cross, not on the cross, not in a
six-tile edge mouth, not in the return landing apron, and not inside an
existing setpiece stamp. Same instinct as dens, different tell art
(§6.3), so a shop cave is never mistaken for a cairn, island stair, or
chasm scar.

### 6.3 Hidden entrances

The merchant is **never** in the field. The field shows only a
concealed cave mouth, Zelda 1 style (bombable wall, pushable rock,
walk-into thicket). There is no burnable-bush tell in v1, because
Quintra still has no fire tool; if one ships, it becomes an alternate
for CAVE-THICKET.

A seeded permutation of the three kinds below is laid over the three
bands. **One of the three is Hollow-only.** Worldglass is required to
even see a usable tell; it does **not** skip the cave’s gate verb:

- In **Waking**, that field always shows a dead ring with no mouth,
  even after `mouth_open[i]` is set. Re-entering still needs Worldglass.
- In **Hollow**, while `mouth_open[i] == 0`, the field shows the
  concealed STONE / BLAST / THICKET tell and still needs that verb.
- In **Hollow**, once `mouth_open[i] == 1`, the mouth stays open for
  the rest of the region’s Hollow visits.

Echo Chime and Wayfarer’s Bell **do** react to the Waking dead ring
(flash / 24 px hum). That cues Worldglass without spoiling the verb.
The Hollow-only flag may land on any kind, except as restricted by
the two-cave fallback above, because two of the three kinds need no
item, so visit-1 Waking still has at least one no-item cave.

| Kind | Tell (not a den tell, not amber) | Gate | Availability |
|---|---|---|---|
| **CAVE-STONE** | A field rock one intra-palette step paler, with a coin-scratch (not the den cairn’s carved standing stone), one tile off a shallow socket. | Push into the socket, or lift with Titan Glove / Sauran. Push always works, so this cave is never Glove-gated. | Visit 1, no item. |
| **CAVE-BLAST** | A boarded or cracked cliff face, biome-coloured, not amber, at the end of a short 3-tile accent line. | Bomb, Rift Bomb, Morningstar, or a Titan Glove / Sauran touch (same verb set as a den cairn, different art). Primary shots do **not** open it. | Glove is on this region’s first Warden, so the cave may wait until after that fight on region 1 visit 1. The STONE and THICKET caves still exist. |
| **CAVE-THICKET** | A bush, ivy, or reed curtain that matches the field, except one leaf tile is flipped. | Walk into the curtain. | Visit 1, no item. |

On opening, the tell becomes a `BGT_WILD_STAIR` or cave-mouth pair.
Stepping on it enters a **one-room stall cave**. Prefer the same portal
path dens use, with `world_screen = 48 + i` for cave `i` in 0..2 (dens
already own 36..47). A shared helper (`world_effective_field(ws)` or
equivalent) must test `ws >= 48` (parent = cave field `i`) *before*
any existing `ws >= 36` den guard. A den index of
`(ws - 36) >> 2` would otherwise become 3 on screens 48..50 and read
off the end of a 3-den table. The helper also suppresses field-entry
effects (Cache Lure, Wayfarer's Bell, Hollow Wick, Worldglass) for
every `ws >= 36`. Suspend inside 48..50 must rebuild the parent field
and the safe exit tile before the player can walk out. Worldglass is
disabled inside, as in dens. Leaving lands on a safe tile at the
mouth, never in water or a hole (same softlock rule as the Stage 5
Veil island).

**CAVE-BLAST terrain.** The tell sits in an open quadrant 4–8 tiles
from the trail cross, which may have no natural cliff. The post-pass
stamps a self-contained bluff of existing biome rock tiles plus one
crack, so the boarded face is never a detached wall on flat grass.

**CAVE-STONE lift.** If Titan Glove / Sauran lifts the rock, `mouth_open`
fires on the lift itself, not on a later throw into the socket, so
tossing the rock off-socket cannot break the gate until a reload.

The mouth stays open for the rest of the region (`rift_caves`
`mouth_open`, §7). Echo Chime in the parent field flashes the tell and,
if the cave is still unfound, sets `chime_hinted` and a **dim small
coin** on that field (dens keep the chest glyph, so the two secrets
read apart on the Compass). A Chart never prints the coin. A seeded
Riftwild wayfarer rumour names the *method*, never the field, e.g.
`A ROCK WITH A COIN SCRATCH / HIDES A DOOR`.

### 6.4 Stock

Three shelves, same A / B / C rules as the Veil stall (A restocks, B is
a bottle that **arms at the counter and uncorks on the next combat
entry**, C is unique), but the goods are **Riftwild-flavoured** and must
not duplicate a Veil signature, a stage tonic, or the open Riftwell’s
role as the cheap Antidote stop. Shelf B still uses the combat-entry
latch: next hostile Riftwild field, den keeper room, or, if the bottle
is still armed when the champion enters a dungeon, that dungeon’s next
combat room. The latch lives in `rift_caves`, not in `secret_shop`, so
`run_state_begin_dungeon` does not erase it.

If temporary power-ups have not shipped at all, every cave’s shelf B
uses the same Grand Surge stand-in as the Veil stall (24 coins, 20 s),
also latched. If Phase 1 of PR #120 has shipped (Aegis, Limitless,
Mend) but not the later bottles, use those named commons where the
table asks for them, and Grand Surge where it asks for an uncommon or
rare that is not in yet. Do not write “else Limitless” in one row and
“else Grand Surge” in the prose.

Prices stay numerals if Shards ship. Public reference is unchanged:
Riftwell Antidote 12, dungeon Chart 15, Surge 20, Bomb Bag 30.

| Cave kind | A. Tonic (restocks) | B. Bottle (once / region, uncorks in next fight) | C. Unique (once / run or once / region, see below) |
|---|---|---|---|
| CAVE-STONE | Rift Tonic: 1 heart + 1 MP, 16 | Mend or Aegis, 24 | The **region Wild charm** (table below), 40 / 45 / 55 in regions 1 / 2 / 3. If already owned, the shelf is empty. |
| CAVE-BLAST | Rift Tonic, 16. Not an Antidote shelf — the open Riftwell keeps that job. | Uncommon bottle (Formation, Halo, or Blast Assist, seeded), 36 | Bomb Bag at 30 if unowned, else a Rift Bomb at 20. Bomb Bag is once per run; a bought Rift Bomb does not restock this region. |
| CAVE-THICKET | Rift Tonic, 16 | Rare bottle (Wingmates, Clarity, or Lodestar) at 48 if that bottle has shipped, else the §6.4 fallback (Grand Surge at 24 until the named rare exists). | Echo Chime at 20 if the pack has none, else a **Riftwell re-arm** at 25 (clears `RIFT_REGION_WELL_USED_BIT`). Re-arm is once per region and is not offered if the well is already fresh. If both are unavailable, the shelf is empty. |

If the Hollow-only flag lands on a cave, shelf B upgrades to a rare
bottle when the rare list has shipped (Stillwater, Nova, or Wingmates
at 48), uncorking in the next fight — including a Hollow field. Shelf C
does not start selling Blast Seed or Rift Lens; those stay Hollow-cache
rewards so the caves do not undercut Hollow exploration.

**Region Wild charms** (flag charms, same always-on rule as Veil
charms, stored in `veil_charms` bits 9–11, shown as pips 10–12 on the
Pack `VEIL` row):

| Region | Charm | Effect | Price |
|---|---|---|---|
| 1 | **Wayfarer's Bell** | While owned, an unfound merchant-cave tell in the current field hums when the hero is within 24 px (reuse an existing SFX, the optional proximity hum from the dens spec). Echo Chime already flashes a cave tell; the Bell does not repeat that, it is a close-range tell without spending the Chime. | 40 |
| 2 | **Cache Lure** | On field entry, setpiece coin caches and loose den coin piles glint for 1 s (Cave Light’s cousin, for wild loot, not cracks). | 45 |
| 3 | **Hollow Wick** | In Hollow, on field entry, Hollow-only den and cave tells *and* any still-unclaimed Hollow relic cache in that field glint for 1 s. The cache glint keeps the charm useful late in region 3, when few Hollow-only dens or caves may remain. | 55 |

These three must not copy a Veil effect (no secret-wall glint, no
conditional ATK, no lethal save). Buying one prints a named notice.

### 6.5 Map, return, and region lifetime

- Unopened caves are never drawn. Charts never reveal them.
- Chime hint: dim `BGT_MAP_SHOP` on the parent field, persisted in
  `chime_hinted`. Found: bright small coin. The Riftwell trader keeps
  its existing small coin after a meeting. Dens keep the chest.
- Stock, mouth, and found flags **persist across the three dungeon
  trips of the region** and clear only when a *new* Riftwild region
  begins (`run_state_begin_world` for a fresh region, not on each
  return to the same map). Death wipes the run as usual.

## 7. Persistence and save

Append three fields to `run_state_t` (suspend-compatible, older layouts
read as zero), packed with **no padding**, in this order: `u8
secret_shop`, `u16 veil_charms`, `u32 rift_caves`. SDCC/gbz80 is
byte-aligned; host-side Python in `test_sram_compat.py` must unpack
with an explicit little-endian layout (for example `<...BHL`), never
native alignment.

| Field | Size | Lifetime |
|---|---|---|
| `secret_shop` | `u8` | Cleared when the next dungeon begins, at the same moment as `shop_bought`. Bit layout is fixed below. |
| `veil_charms` | `u16` | Bits 0–8 = Veil signatures 1–9; bits 9–11 = region Wild charms 1–3. Cleared only on run end / death. Bits 12–15 reserved, must read as zero. |
| `rift_caves` | `u32` | The three cave merchants of the *current* region. Cleared when a new Riftwild region begins, **not** when a dungeon begins. |

`secret_shop` bits (dungeon Veil stall only):

| Bit | Name | Meaning |
|---|---|---|
| 0 | `shelf_b_bought` | Shelf B sold out this stage. |
| 1 | `shelf_c_bought` | Shelf C sold out this stage (also implied by the matching `veil_charms` bit). |
| 2 | `mouth_open` | The vault mouth stays open across leaves and suspends. Do not reuse `dungeon_phase` hidden-secret slots. |
| 3 | `chime_hinted` | Echo Chime was rung in this unfound host; Compass draws the dim small coin until found. |
| 4 | `bottle_armed` | Shelf B is paid for and waiting to uncork on the next combat-room entry. Cleared on uncork, and also when `secret_shop` is cleared at the next dungeon. A Riftwild-armed bottle is *not* stored here. |
| 5–6 | reserved | Must read as zero. |
| 7 | `found` | The player entered the stall. Compass draws the bright small coin. |

`rift_caves` bits, for cave `i` in 0..2:

| Bits | Name | Meaning |
|---|---|---|
| 0–2 | `found[i]` | The player entered cave `i`. |
| 3–5 | `mouth_open[i]` | The cave mouth stays open for the rest of the region. |
| 6–8 | `chime_hinted[i]` | Echo Chime was rung in that unfound field. |
| 9–11 | `shelf_b_bought[i]` | Cave `i` shelf B sold out this region. |
| 12–14 | `shelf_c_bought[i]` | Cave `i` shelf C sold out this region (also implied by a Wild-charm bit when that is what C sells). |
| 15 | `bottle_armed` | A Riftwild bottle is paid for and waiting to uncork. One latch, because there is only one timed power-up slot. |
| 16–17 | `bottle_from` | Which cave’s bottle is armed (0..2). Ignored unless bit 15 is set. |
| 18–31 | reserved | Must read as zero. |

There is only one timed power-up slot, so the two armed bits are
mutually exclusive in play. **Either** `secret_shop.bottle_armed` **or**
`rift_caves.bottle_armed` may be set, never both. Every Veil and
Riftwild shelf B refuses with `A BOTTLE IS ARMED` if either bit is
set.

A Riftwild `bottle_armed` survives `run_state_begin_dungeon` and uncorks
in the first dungeon combat room if it is still armed. It clears on
uncork, and also when `rift_caves` is cleared at a new region (the
coins stay spent). A Veil `secret_shop.bottle_armed` clears on uncork,
when the next dungeon begins, **and** when the current dungeon is
exited or completed, so a leftover dungeon bottle cannot follow the
champion back into Riftwild and sit alongside a new wild latch.

Shelf A has no bit (it restocks). Death wipes the run as usual. Suspend
on room entry already covers being inside a vault or a cave; the stall
rebuilds from `(run_seed, stage or region, secret_shop, veil_charms,
rift_caves)` plus the live flags a shelf C already consults (Bomb Bag
ownership, Echo Chime count, `RIFT_REGION_WELL_USED_BIT`). A
CAVE-THICKET shelf C that was empty because the well was fresh or a
Chime was in the pack may fill later in the region if `shelf_c_bought`
is still 0. A dungeon Veil vault that is suspended and resumed must
rebuild as the overlay, never as the host room with
`pickup_spawn_merchant` standing in the open.

`run_state_t` must be packed (or these three fields kept at the tail
with an explicit pack pragma). Host-side C that includes the struct
natively would otherwise insert a padding byte after `u8 secret_shop`
before the `u16`. SRAM tests use `<...BHL` and do not rely on host
alignment.

## 8. Sprite, tile, and bank budget

| Budget | Plan |
|---|---|
| Keeper | Reuse `SPR_MERCHANT`. Veil stalls use a violet / dusk palette; Riftwild cave stalls use a travel / cloak palette, distinct from the public town merchant and from the Veil. 0 new combat OBJ tiles. Optional hooded variant later, shop-atlas only. |
| Host-room and field tells | Intra-palette shading or 1–2 biome BG tiles. At most one tell OBJ, or a 2-frame BG anim. No new CGB BG palette. Cave tells must not reuse den cairn / island-stair / scar art. CAVE-THICKET’s flipped leaf should use CGB VRAM1 X/Y flip on an existing bush or reed tile (0 new BG tiles), leaving the 1–2 tile budget for the STONE socket and the BLAST bluff stamp. |
| Ware icons | Stall is a no-enemy overlay, so it may load a **shop-only atlas** (the public stall already does this). Tonics can share one flask tile with per-stage palettes. Power-up bottles use the PR #120 icons when those exist, otherwise the Surge spark. Charm icons: one 8×8 loaded for the highlighted Pack pip; the stall shows the current stage’s charm only. Target: ≤12 shop-atlas tiles, 0 crowded-room OAM pressure. |
| Pack `VEIL` row | Two shared pip tiles + one dynamic 8×8. Split across two Pack rows so it fits a 20-tile screen: `VEIL` (4 tiles) + 9 pips on one row (13), and `WILD` (4) + 3 pips on the next (7). Both sit inside an 18-tile inner width with room to spare. Pause/menu VRAM only. |
| Map | No new tiles. Found Veil host or found cave field = `BGT_MAP_SHOP`. Chime hint = same tile, dim palette. Public dungeon merchant stays `BGT_MAP_BIG_SHOP`. Dens keep the chest. Riftwell keeps its existing coin after a meeting. |
| Code | Do not grow scarce bank 4 or bank 0. Pin placement + stall build to a free bank (dens already took 18; pick the next free one at implement time). Reuse `shop.c` price/configure hooks, `pickup_spawn_merchant`, `shop_write_live_stock`, and counter reach. Cave travel reuses the den portal path. A shared helper must dispatch `world_screen >= 48` *before* any `>= 36` den index, and must suppress field-entry effects inside both dens and caves. |
| Audio | Opening the mouth: existing secret / vault sting. Purchase: existing buy cue (or the matching Shard arpeggio if Shards have shipped). Uncork: the power-up’s own fanfare. No new music. |
| SRAM | +7 bytes (`u8` + `u16` + `u32`), packed with no padding. `test_sram_compat.py` must pass. |
| RNG | Placement hashes are isolated (`'VEIL'`, `'CAVE'`, and the shipped den `'RIFT'`). Ordinary rooms and ordinary Riftwild fields do not drift. Only the Veil host cell and the cave fields are rewritten by their post-passes. |

## 9. What does not change

- Public dungeon, village, and Riftwell stock, prices, and restock rules.
  The Riftwell trader stays in the open, selling Antidotes at 12.
- Ordinary hidden secrets in other rooms (shot / walk / push / cracked
  walls) still pay their current vault rewards. Only the reserved host
  cell is stripped of a colliding ordinary secret and given a Veil mouth.
- Sigils, dungeon Charts, and waygear stay off this counter. Cave
  shelf C may *sell* an Echo Chime, a Bomb Bag, a Rift Bomb, or a
  Riftwell re-arm; it does not grant waygear and it does not sell a
  Chart (dens remain the Wild Chart source).
- Den placement, tells, rewards, and Power Shrines stay as specified in
  their own docs. Caves hash after dens and never share a field.

## 10. Test plan

Headless PyBoy, in the style of `test_merchant_stock.py`,
`test_hidden_secrets.py`, and `test_riftwild_dens.py`. One script
`scripts/test_secret_merchants.py`, plus a layout/SRAM check.

For every stage (loop the nine, with a fixture seed that lands a legal host):

1. **Placement.** The host is never a reserved cell. Two boots of the same
   seed agree. A third boot with a different seed may move the host.
   `test_procgen_parity.py` still passes for every non-host room. The host
   has no ordinary `HIDDEN_SECRET_*` / amber-crack vault alongside the
   Veil mouth. Stage 7’s host always contains a completable lattice path
   to the plate.
2. **Tell and gate.** The tell tile is distinct from an ordinary amber
   crack and does not allocate a new BG palette. The declared verb opens
   the mouth; a verb that should not (for example a push on the Crystal
   crack, a shot on the Bloodmoon gap, or walking the Mire water without
   Raft / Picsean) does not. Stage 1 opens with a shot and also with a
   bomb. Stage 4 opens with a push and also with the Glove. Stage 8 opens
   with Hook / Corvin and not with a shot. Stage 9’s pale pit is a stair,
   not a lethal fall, and the rumour room is reachable without entering
   the host.
3. **Stall.** The overlay has no enemies, three shelves (or two if the
   signature is already owned), correct prices, and counter-reach talk.
   Standing on a ware never talks; with coins it buys; without coins it
   refuses by name.
4. **Shelf B latch.** Buying B does not start a power-up inside the stall.
   Entering the next combat room uncorks it, plays the notice, and clears
   `bottle_armed`. Buying a Veil B and then finishing or leaving the
   dungeon without a fight leaves the bottle still corked; the dungeon
   armed bit clears on that exit so it cannot follow the champion into
   Riftwild. Nova, if sold, deals its damage in that combat room, not
   in the stall. Buying a second bottle while either latch is armed
   refuses with `A BOTTLE IS ARMED`, including across the
   wild / dungeon boundary.
5. **Persistence.** Buy B and C, leave the overlay, leave the host cell,
   return: B and C stay empty, A is back, the mouth is still open.
   Suspend in the stall and resume: same stock. Chime, leave, suspend,
   resume: the dim coin is still on the Compass. Start the next dungeon:
   `secret_shop` is clear, a new host exists, `veil_charms` still carries
   the earlier signature, and that later stall’s shelf C is empty if it
   would have been a duplicate (it will not — signatures are 1:1 with
   stages — but the skip path is still tested by setting the bit).
6. **Map.** Chart-only reveal of the host shows no coin. Entering the
   stall writes the small coin. Echo Chime in an unfound host writes the
   dim coin. The public shop cell still gets the big coin after a visit.
7. **Economy and charms.** A purchase deducts the listed price and never
   drops `player.coins` below 0 or above `COIN_CAP`. Charm notices name
   the effect. Crimson Pact’s ATK flag is gone again above half health.
   Last Light fires once, then stays spent; a carried Phoenix Thread still
   wins a lethal hit without spending Last Light. The Pack `VEIL` row
   shows the right pips; inspecting a pip names the charm.
8. **Stage 5 exit.** After buying, the hero lands on dry reed; walking
   off the island without Raft / Picsean is impossible, and with Raft it
   is possible.
9. **Budgets.** `scripts/check_rom_layout.py` and `scripts/report_budget.py`
   stay green. No new always-mapped bank-0 growth for the stall path.
   SRAM unpack uses explicit little-endian `u8` + `u16` + `u32` with no
    padding.
10. **Cave rule.** In every Veil host and every Riftwild cave field, no
    merchant sprite and no shop ware is present in the open room or
    field. The keeper and shelves exist only after entering the mouth.
11. **Riftwild caves.** For a fixture seed in each region: three caves
    land in three bands, never on a den, the Riftwell, a shrine, a relic
    field, or a reserved fixture; or, if a band is empty, at least two
    caves still place, including CAVE-STONE and one no-item cave in
    Waking. The same seed boots twice agree. `'CAVE'` placement is
    unchanged if a Power Shrine is also present. `test_procgen_parity.py`
    still passes for fields that are not cave hosts. Each kind opens
    only with its verb (push or lift opens STONE; a shot does not open
    BLAST; walking the flipped-leaf tile opens THICKET, while a shot or
    bomb does not, and walking an ordinary bush does nothing). One cave
    is Hollow-only: Waking shows a dead ring with no mouth, even after
    it has been opened in Hollow; Hollow still requires the kind’s verb
    before the mouth opens. Echo Chime and Wayfarer’s Bell react to the
    dead ring in Waking. Echo Chime marks a dim coin, not a chest.
    Entering writes a small coin. Buy B and C, visit a dungeon, return
    to the same Riftwild: stock, mouth, and found bits remain; start a
    *new* region and they clear. A bottle bought in a cave and still
    armed uncorks in the first dungeon combat room, and does not occupy
    `secret_shop` bit 4. Suspend inside `world_screen` 48..50, resume,
    and exit onto the parent field’s safe landing tile. Leaving a cave
    always lands on safe ground. Shelf C never sells a Veil signature,
    a Chart, or a Blast Seed / Rift Lens. CAVE-THICKET’s re-arm clears
    `RIFT_REGION_WELL_USED_BIT` and is hidden while the well is fresh;
    CAVE-BLAST swaps Bomb Bag (30) for a Rift Bomb (20) once the Bag is
    owned. Wayfarer's Bell hums within 24 px of an unfound cave tell and
    is silent once found; Cache Lure glints caches for 1 s on field
    entry; Hollow Wick glints Hollow-only tells and unclaimed Hollow
    caches. Pack pips 10–12 match the three Wild charms.
12. **Regressions.** `test_merchant_stock`, `test_merchant_counter`,
    `test_hidden_secrets`, `test_secret_door_seal`, `test_riftwild_dens`,
    `test_sram_compat` remain green.

## 11. Implementation phases

1. Spec (this PR).
2. Veil placement hash, host post-pass (strip ordinary secrets, stamp
   tell), cave-vault overlay, empty stall, Compass / Chime marks,
   mouth_open persistence, tests 1–3, 6, 8, and 10. Palette-only keeper.
3. Veil stock: tonics, Grand Surge stand-in or real bottles with the
   combat latch, signatures, Pack `VEIL` pips, tests 4, 5, and 7.
4. Riftwild cave placement (after dens), hidden entrances, one-room
   cave screens 48..50, tests 10–11. Still no open-air keeper.
5. Riftwild stock, region Wild charms, region-lifetime `rift_caves`,
   bottle latch that survives a dungeon trip.
6. Manual page (a short addendum to `docs/manual/content/merchants.md`)
   and, if Carmelo wants art, a hooded GPT Image keeper.

## 12. Open questions for Carmelo

1. **Scope (answered).** Carmelo: Riftwild should definitely have a few
   merchants, and they must be hidden in caves like Zelda 1, not out in
   the open. This spec places three cave merchants per region (at least
   two if a band is full), never in the open field. The Riftwell trader
   stays the one open-air stall. Villages still have no secret stall.
2. **Last Light** (Void signature) is a once-per-run lethal save, with
   Phoenix still first in line. Want that insurance, or a less
   safety-net charm (for example a run-long secret-glint upgrade of Cave
   Light)?
3. **Shelf B** is written against PR #120’s power-up list, with a Grand
   Surge stand-in if that work is not in yet, and with a combat-entry
   latch in either case. Prefer to wait and only sell real bottles, or
   ship the stand-in?
4. **Keeper art.** Palette-only reuse of the public merchant for v1, with
   an optional hooded sprite later, or should the hooded art block the
   stall?
5. **Shard prices.** If gem Shards ship, this spec keeps numeric tags.
   Any wish to show a gem recipe on secret wares only?
6. **Crimson Pact** gives conditional ATK +1 at low health. Acceptable as
   a signature, or too close to a cap raise?

## 13. Carbon review (folded)

Carbon’s verdict on the first draft was **ship-with-changes**. The five
required changes are in this text:

1. Shelf B no longer activates in the stall; it arms a combat-entry latch
   (Nova included).
2. Stage 8 is a Hook gap, not a third shoot/bomb wall. Stage 4 also
   accepts the Glove as an alternate, so all three Region 1 waygear verbs
   appear.
3. A host-cell post-pass strips ordinary hidden secrets and stamps Veil
   fixtures; Stage 7 guarantees a mini-lattice if the room has none.
4. `secret_shop` now has a fixed bit layout, including `mouth_open`,
   `chime_hinted`, and `bottle_armed`.
5. Stage 1 and 4 tonics have a heart-plus-MP rider; Stage 1’s bottle is
   Aegis at 24 and Cave Light is 32, so the teaching charm is payable
   early. Sun Wine moved to 24. Crimson Draught no longer carries a timed
   ATK buff.

Risks called out and adopted: intra-palette tells and a one-OBJ cap;
Stage 9 rumour-before-host and a high-contrast star-dot; Pack `VEIL` as a
9-pip strip plus one highlighted icon; explicit SRAM packing for Python
tests; Stage 5 dry-island return; wayfarer rumours come from existing
waypoint witnesses; Gloam Lamp no longer duplicates Cave Light’s Veil
glint.

A second Carbon pass (2026-11-16) reviewed the Riftwild cave section
and the cave rule. Verdict: **ship-with-changes.** The fixes folded
into this text:

1. Veil and Riftwild bottle latches are mutually exclusive; either
   stall refuses with `A BOTTLE IS ARMED`, and a Veil armed bit also
   clears when the dungeon is exited, not only when the next one begins.
2. Hollow-only caves still need their gate verb in Hollow; Waking
   always shows a dead ring, even after `mouth_open`; Chime and
   Wayfarer’s Bell react to that ring.
3. `world_screen` 48..50 is dispatched before any `>= 36` den index,
   field-entry effects are suppressed inside caves, and a suspend
   inside a cave or a Veil vault cannot rebuild a keeper in the open.
4. Hash order is dens, then caves, then shrines (prose no longer
   subtracts the shrine first). A two-cave fallback always keeps
   CAVE-STONE and one no-item Waking cave.
5. §9 no longer says caves sell a Chart. Shelf B’s pre-#120 fallback
   is one rule (Grand Surge, or a shipped Phase 1 common). Hollow Wick
   also glints unclaimed Hollow caches so it stays useful in region 3.
6. The Pack row is a VEIL 9-pip row plus a WILD 3-pip row, which fits
   the 20-tile screen.
7. Tests cover the latch collision, Hollow Waking re-entry, cave
   suspend, THICKET’s real verb (not “walking water”), and the three
   Wild charms.

Risks adopted: a self-contained BLAST bluff stamp; STONE opens on
Glove lift, not only on a socket throw; packed `run_state_t` so host
C does not insert padding; stall rebuild reads live Chime / Bomb Bag /
well flags. CAVE-THICKET’s flipped leaf uses a CGB attribute flip.
