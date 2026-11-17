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

**Goal.** Exactly one hidden merchant — a **Veil Trader** — in each of the
nine stages. Finding one should feel like a Zelda secret: a fair, biome-native
tell, a verb you already have, a quiet stall behind the mouth, and stock you
cannot get on the public counter.

**Non-goals.**

- No second public merchant, and no change to public / village / Riftwell stock
  or prices.
- No secret merchant in a village (those already have four civic shops).
- No secret merchant in Riftwild in this version (the wayside trader and the
  dens already pay tools, coins, a mend, and a chart). A per-region peddler is
  an open question, §11.
- No stat-cap relics (Iron Heart, Mana Gem, Power Stone, and the rest of the
  dens' excluded list). The stall is for rare power, consumables, and one
  signature charm.
- No new SRAM migration story beyond appended bytes; older suspends load as
  "not found, nothing bought."

## 2. Placement

One **host cell** per stage, chosen from the run seed, stable for the whole
run, and never on the required spine.

**Excluded cells:** start (local 0), public shop (`size-3`), sanctuary
(`size-2`), colossus (`size-1`), Farfold cache cell, mini-boss cells, and
every mission-graph role (trial, sigil, warden, waystone, deep warden / switch
/ gate). If Power Shrines have shipped, also exclude that stage's shrine cell:
hash the Veil host first (`run_seed ^ stage * 0x9E3779B9 ^ 'VEIL'`), then let
the shrine pick from what remains, so the two specs cannot collide.

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

The host room may still be a quieter combat room. The trader is not standing
in the open. Opening the tell paints a vault mouth (`room_open_secret` / the
existing 16 px `BGT_DOOR` pair). Walking in enters a **compact overlay stall**
(no enemies, no graph exit), then returns to the host at the mouth. Opened
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

- Quiet overlay. No enemies. One Veil Trader behind a short counter of
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

## 6. Persistence and save

Append two fields to `run_state_t` (suspend-compatible, older layouts
read as zero). Append `u8 secret_shop` then `u16 veil_charms` with **no
padding**. SDCC/gbz80 is byte-aligned; host-side Python in
`test_sram_compat.py` must unpack with an explicit little-endian layout
(for example `<...BH`), never native alignment.

| Field | Size | Lifetime |
|---|---|---|
| `secret_shop` | `u8` | Cleared when the next dungeon begins, at the same moment as `shop_bought`. Bit layout is fixed: |
| `veil_charms` | `u16` | Bits 0–8 = signatures 1–9 owned this run. Cleared only on run end / death. |

`secret_shop` bits:

| Bit | Name | Meaning |
|---|---|---|
| 0 | `shelf_b_bought` | Shelf B sold out this stage. |
| 1 | `shelf_c_bought` | Shelf C sold out this stage (also implied by the matching `veil_charms` bit). |
| 2 | `mouth_open` | The vault mouth stays open across leaves and suspends. Do not reuse `dungeon_phase` hidden-secret slots. |
| 3 | `chime_hinted` | Echo Chime was rung in this unfound host; Compass draws the dim small coin until found. |
| 4 | `bottle_armed` | Shelf B is paid for and waiting to uncork on the next combat-room entry. Cleared on uncork, and also when `secret_shop` is cleared at the next dungeon. |
| 5–6 | reserved | Must read as zero. |
| 7 | `found` | The player entered the stall. Compass draws the bright small coin. |

Shelf A has no bit (it restocks). Shelf C also consults `veil_charms`, so
a later stall never offers a duplicate and a mid-dungeon re-entry does
not restock a sold signature.

Death wipes the run as usual. Suspend on room entry already covers being
inside the overlay; the stall rebuilds deterministically from
`(run_seed, stage, secret_shop, veil_charms)`.

## 7. Sprite, tile, and bank budget

| Budget | Plan |
|---|---|
| Keeper | Reuse `SPR_MERCHANT` + veil palette. 0 new combat OBJ tiles. Optional hooded variant later, shop-atlas only. |
| Host-room tells | Intra-palette shading or 1–2 biome BG tiles. At most one tell OBJ, or a 2-frame BG anim. No new CGB BG palette. |
| Ware icons | Stall is a no-enemy overlay, so it may load a **shop-only atlas** (the public stall already does this). Tonics can share one flask tile with per-stage palettes. Power-up bottles use the PR #120 icons when those exist, otherwise the Surge spark. Charm icons: one 8×8 loaded for the highlighted Pack pip; the stall shows the current stage’s charm only. Target: ≤12 shop-atlas tiles, 0 crowded-room OAM pressure. |
| Pack `VEIL` row | Two shared pip tiles + one dynamic 8×8. Pause/menu VRAM only. |
| Map | No new tiles. Found = `BGT_MAP_SHOP`. Chime hint = same tile, dim palette. Public merchant stays `BGT_MAP_BIG_SHOP`. |
| Code | Do not grow scarce bank 4 or bank 0. Pin placement + stall build to a free bank (dens already took 18; pick the next free one at implement time). Reuse `shop.c` price/configure hooks, `pickup_spawn_merchant`, `shop_write_live_stock`, and counter reach. |
| Audio | Opening the mouth: existing secret / vault sting. Purchase: existing buy cue (or the matching Shard arpeggio if Shards have shipped). Uncork: the power-up’s own fanfare. No new music. |
| SRAM | +3 bytes (`u8` + `u16`), packed with no padding. `test_sram_compat.py` must pass. |
| RNG | Placement hash is isolated. Ordinary rooms, including their hidden secrets, do not drift. Only the one host cell is rewritten by the post-pass. |

## 8. What does not change

- Public dungeon, village, and Riftwell stock, prices, and restock rules.
- Ordinary hidden secrets in other rooms (shot / walk / push / cracked
  walls) still pay their current vault rewards. Only the reserved host
  cell is stripped of a colliding ordinary secret and given a Veil mouth.
- Sigils, charts, and waygear stay off this counter.
- Den rewards and Power Shrines stay as specified in their own docs.

## 9. Test plan

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
   `bottle_armed`. Buying B and then finishing the dungeon without a fight
   leaves the bottle uncorked and spent. Nova, if sold, deals its damage
   in that combat room, not in the stall.
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
   SRAM unpack uses explicit little-endian `u8` + `u16` with no padding.
10. **Regressions.** `test_merchant_stock`, `test_merchant_counter`,
    `test_hidden_secrets`, `test_secret_door_seal`, `test_riftwild_dens`,
    `test_sram_compat` remain green.

## 10. Implementation phases

1. Spec (this PR).
2. Placement hash, host post-pass (strip ordinary secrets, stamp tell),
   vault overlay, empty stall, Compass / Chime marks, mouth_open
   persistence, tests 1–3, 6, and 8. Palette-only keeper.
3. Stock: tonics, Grand Surge stand-in or real bottles with the combat
   latch, signatures, Pack `VEIL` pips, tests 4, 5, and 7.
4. Manual page (a short addendum to `docs/manual/content/merchants.md`)
   and, if Carmelo wants art, a hooded GPT Image keeper.

## 11. Open questions for Carmelo

1. **Scope.** This proposal is nine dungeon stalls only. Do you also want
   one secret peddler per Riftwild region (a fourth den-like find), or is
   the wayside trader plus dens enough there? Villages are left without a
   secret stall on purpose.
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

## 12. Carbon review (folded)

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
