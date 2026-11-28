# Stage perk items: distinct, compounding Farfold rewards (#256)

Date: 2026-11-27. Status: **proposal for the owner's review.** Spec only;
no ROM, content, or test change in this PR.

Source (issue #256, struktured's 3DS playtest of main `0ed13b1`):

> each stage has an optional item. The raise-it-overhead presentation is
> good, but the reward is a tiny stat +1, about the same as random monster
> drops, so it feels like a letdown.

Direction from the owner: each stage item should give something different
from a stat drop (an ability, perk, or mechanic change); the rewards should
compound across stages; collecting all of them gives an extra bonus.

Everything in §1 was read from `origin/main @ 0ed13b15`. File and line
references are to that commit. Nothing was built or run for this spec, so
sizes and byte costs are hand counts and estimates, and are marked as such.

## 1. What exists today

### 1.1 Which system the owner means: the Farfold Cache

The "optional per-stage item with the raise-overhead presentation" is the
**Farfold Cache**. It is the only reward that is all three of: one per
dungeon stage, optional, and shown with the raised-arm ceremony while
paying a stat relic.

- **Placement.** One cache per dungeon, in a generated dead-end cell that
  is not a mission role or service room
  (`run_state_dungeon_cache_cell`, `src/game/mission_graph.c:182-202`;
  contract comment at `src/game/run_state.h:256-258`). The room gets a
  south-east reliquary (`src/game/room_dungeon_world.c:317-325`).
- **Spawn.** On entering that cell, if this dungeon's cache is unclaimed,
  `procgen.c` spawns a `PICKUP_FARFOLD_RELIC` at a fixed spot and tops the
  room up to four guards (`src/game/procgen.c:1848-1863`,
  `treasure_cache_prepare` at `src/game/treasure_guard.c:58-73`). The orb
  never expires (`src/game/pickup_cold.c:62-74`).
- **Guard rule.** The orb is red and refuses pickup while any enemy in the
  room lives, with a GUARD notice (`src/game/treasure_guard.c:30-56`,
  `src/game/pickup.c:516-519`, `src/render/hud_notice.c:419-423`).
- **Claim.** `src/game/pickup.c:881-901`: refuse if the stat is already at
  its cap (`refuse_capped_item`, `pickup.c:777-782`), otherwise
  `apply_item_effects`, play the relic jingle, set
  `RUN_FARFOLD_CACHE_BIT` in `run_state.dungeon_phase`, and start the
  ceremony.
- **Ceremony.** `room_start_major_reward` (`src/game/room_rewards.c:38-58`)
  loads the class "claim" pose (`tiles_load_class_claim_sprite`, art
  `sprite_class_*_claim` at `src/render/sprites_motion_gen.c:17-21`), locks
  the pose, gives 90 iframes, and runs for 120 frames. `room_tick` freezes
  the room for that time and then opens a dialog page
  (`src/game/room.c:1251-1264`). `room_draw_major_reward_tableau`
  (`room.c:969-981`) draws one 8x8 icon above the hero with OBJ palette 6.
- **Pickup text.** The dialog title is the item name
  (`src/game/dialog.c:101-103`). The body is "TREASURE WON", "PACK SHOWS
  STATS", and one stat line such as "ATK +1" (`dialog.c:211-224`).
- **Compass and labels.** The cache has its own Compass node
  (`BGT_MAP_BIG_CACHE`, `src/render/tiles.h:256`; `src/game/map.c:248-250`)
  and an arrival directive while unclaimed
  (`src/game/room_render.c:67-70`).

The other users of the same ceremony are not this system:

| Reward | Why it is not the one in the issue |
|---|---|
| Rift Sigil (`pickup.c:999-1004`) | Required stage key ("FIND SIGIL KEY", `src/game/inventory_goal.c:21-23`). Gives no stat. |
| Waygear (`pickup.c:1005-1017`) | Riftwild Warden reward, first region only (`src/game/combat.c:256-272`). A traversal tool, not a stat. |
| Hollow relics (`pickup.c:1018-1027`) | Three per Riftwild region (`run_state.h:70-73`). Already behaviour relics or a tool. |
| Riftwild island Mana Gem (`src/game/riftwild_discovery.c:36-44`, `pickup.c:876-879`) | One authored +2 max MP orb in region 0, screen 0. Same ceremony and the same kind of letdown, but once per run, not per stage. See open question 7. |

### 1.2 What the cache gives, per stage

There is no per-stage item. Every stage's cache pays one of three stat
relics chosen by class (`pickup_farfold_relic_for_class`,
`src/game/treasure_guard.c:18-28`). The values in that table are `items[]`
indices; the stat lines in `dialog.c:213-221` confirm the mapping.

| Hero | Slot 0 | Slot 1 | Slot 2 |
|---|---|---|---|
| Wolfkin | Power Stone: ATK +1 | Iron Heart: max HP +2 | Ward Charm: DEF +1, LCK +1 |
| Sauran | Iron Heart: max HP +2 | Ward Charm: DEF +1, LCK +1 | Vamp Sigil: ATK +1, max HP +1, heal every 5th kill |
| Corvin | Power Stone: ATK +1 | Mana Gem: max MP +2 | Tough Skin: DEF +1 |
| Picsean | Power Stone: ATK +1 | Mana Gem: max MP +2 | Ward Charm: DEF +1, LCK +1 |
| Vespine | Power Stone: ATK +1 | Tough Skin: DEF +1 | Mana Gem: max MP +2 |

Item numbers come from `content/src/items.rs:112-200`.

The slot is `((u8)run_seed + bosses_beaten + class_id) mod 3`
(`procgen.c:1856-1861`), so it steps by one each stage. With `k` the slot
for stage 1:

| Stage | Slot | Example: Wolfkin, k = 0 |
|---|---|---|
| 1 Crystal Caverns | k | ATK +1 |
| 2 Verdant Hollow | k+1 | max HP +2 |
| 3 Ember Depths | k+2 | DEF +1, LCK +1 |
| 4 Frost Vault | k | ATK +1 |
| 5 Toxic Mire | k+1 | max HP +2 |
| 6 Shadow Keep | k+2 | DEF +1, LCK +1 |
| 7 Golden Temple | k | ATK +1 |
| 8 Bloodmoon | k+1 | max HP +2 |
| 9 Void Sanctum | k+2 | DEF +1, LCK +1 |

(The sum is a `u8`. A seed low byte of 243 or more wraps during the run
and shifts the cycle by one. Stage names: `content/src/stages.rs:12-168`.)

Three things make the cache weaker than it looks:

- The same three-item table is also the dungeon shop's 25-coin random stat
  item (`src/game/shop.c:45`) and the guaranteed boss relic
  (`treasure_guard.c:14-16`, dropped at `src/game/combat.c:217-220`). The
  cache is the third copy of one reward per stage.
- If the hero's stat is already capped, the cache refuses and pays nothing
  (`pickup.c:889-892`).
- For Tough Skin (Corvin, Vespine) the dialog prints no stat line at all:
  `dialog.c:213-221` has no case for item 13. This looks like an existing
  bug, separate from this spec.

### 1.3 How it is stored

- Claimed flag: bit 1 of `run_state.dungeon_phase`
  (`RUN_FARFOLD_CACHE_BIT`, `src/game/run_state.h:225`). The whole byte is
  zeroed when the next dungeon begins
  (`src/game/regional_riftwild.c:149`). **Nothing records which stages'
  caches were claimed earlier in the run.**
- Effect: the stat moves in `player` (`hp_max`, `mp_max`, `atk`, `def`,
  `spd`, `lck`; `src/game/player.h:31-36`) and the item id is added once
  to `player.inventory[16]` (`pickup.c:613-620`). Vamp Sigil's heal is
  read from that inventory entry (`src/game/relic_runtime.c:37-38`).
- Suspend save: SRAM bank 0 holds a 5-byte header, the raw `run_state_t`,
  the raw `player_state_t`, and a checksum (`src/game/sram.c:2-5`). Both
  lengths are stored as one byte each, and a shorter saved length loads
  with the tail zeroed (`sram.c:72-77`). Accepted older lengths are listed
  in `src/game/sram_write.c:59-99`. By hand count `run_state_t` is 93
  bytes (74 at `PRE_RESPAWN_RS_SIZE` plus the 19-byte respawn ring,
  `run_state.h:188-195`) and `player_state_t` is 49 bytes, so the record
  is 148 bytes. Not verified by a build.
- The save dies with the run: `sram_clear_run` on death, victory, and new
  run (`src/game/gameover.c:29`, `src/game/victory.c:91`,
  `src/game/run_init.c:72`).
- Across runs only SRAM bank 1 "trophies" persist
  (`src/game/sram.h:15-29`). `meta_flags` uses bits `0x01`, `0x02`, `0x04`.

### 1.4 What random monster drops give

`pickup_roll_drop` (`src/game/powerup.c:154-173`), one RNG byte per kill:

| Band (Normal) | Chance | Easy |
|---|---|---|
| Half-heart | 31/256 = 12.1% | 28.1% |
| Coin | 115/256 = 44.9% | 41.8% |
| **Stat relic** | **5/256 = 2.0%** | **3.1%** |
| Surge Spark | 15/256 = 5.9% | 7.8% |
| Wildcard | 10/256 = 3.9% | 2.0% |
| Capsule | 8/256 = 3.1% | 3.9% |
| Roulette | 3/256 = 1.2% | 2.0% |
| Nothing | 69/256 = 27.0% | 11.3% |

(Capsule and Roulette are also gated by a cooldown, `powerup.c:142-150`.)

The stat relic is `pickup_roll_stat_relic`
(`src/game/pickup_stat_relic.c:41-80`): one of the ten stat orbs, items
10-19, with tapering weights. It goes through the same
`apply_item_effects` as the cache (`pickup.c:862-880`). That pool includes
Lucky Coin (LCK +2), Hunter's Eye (LCK +3), and Swift Fang (SPD +1,
ATK +1), which are larger than anything in the cache tables. A dropped orb
lasts 4 seconds (`pickup.c:98`); the cache orb waits. So the owner's
comparison is exact: the cache pays an item from the same family as a 2%
monster drop, and sometimes a smaller one.

### 1.5 Mechanics already in the ROM that perks can reuse

| Mechanic | Where | Knob |
|---|---|---|
| Room clear: +1 MP | `src/game/room.c:2109-2114` | amount, extra effect |
| Dodge-dash | `room.c:1491-1498` | 6 frames, 30-frame cooldown, 14 iframes |
| Will charge | `src/game/will_support.c:16-30` | `16 + SPD` per frame |
| B signature cooldown | `will_support.c:43-58`, `src/game/will.h:20-25` | per-class base, floor 36 |
| Class B verbs | `will.h:27-45` | Howl giant-hit cap 3, Corvin mark bonus 1, Vespine swarm ticks, Sauran `shield_timer` (`player.h:43`) |
| Oath Arts (one unlocked per stage beaten) | `src/game/oath_arts.h:7-9`, `room.c:1796-1806` | 1 MP, 96-frame cooldown |
| Spirit Convergence | `room.c:1768-1791` | drains all MP, 18 s |
| Surge Spark | `src/game/status.c:103-110` | 120 beats |
| Capsule durations | `powerup.c:180-185` | per power-up table |
| Lethal-hit revive (Phoenix Thread, then Last Light) | `src/game/phoenix_runtime.c:15-30` | once |
| Cached attack traits | `src/game/relic_runtime.c:26-44`, `src/game/projectile.h:31-35` | one WRAM byte tested in hot code |
| Reveal a Compass cell | `run_state_reveal_dungeon_cell`, `run_state.h:272` | |

Two neighbours to stay clear of:

- **Veil charms** are already nine run-long flag perks, one per stage,
  bought from the hidden Veil Trader (`src/game/secret_merchant.h:19-36`,
  `run_state.veil_charms`, `run_state.h:175-179`). They are mostly
  awareness and status-resist perks. The perks below avoid their effects.
  In particular Last Light is already "survive one lethal hit".
- **Behaviour wares** in shops (Echo Prism, Ricochet Rune, Thorn Crown,
  War Drum, Moon Flask, Blast Seed, Phoenix Thread;
  `src/game/pickup.h:57-64`). The perks below do not copy them, so the
  shop shelf stays worth buying.

Constraints: the content `Effect` enum has unused variants
(`tools/crates/quintra-content/src/effects.rs:38-49`), but
`apply_item_effects` only applies `StatBoost` (`pickup.c:629`). The main
Pack page is full: rows 14, 15, 16, 17 hold the goal, tool, Oath, and key
hint (`src/game/inventory_goal.c:11`, `src/game/dungeon_tools.c:60-61`,
`src/game/oath_arts.c:41`, `src/game/inventory.c:183`). The Status page
has two static legend rows (`src/game/inventory_waygear.c:189-190`). Each
fixed bank must keep 256 bytes of headroom or the link fails
(`scripts/check_rom_layout.py:19-23`), and source comments call banks 13
and 10 full (`src/game/pickup_wildcard.c:35`,
`src/game/sram_write.c:2`). Current free bytes per bank: not verified
(needs a build).

## 2. Shared plumbing (both options)

- **The cache stops paying a stat relic.** The class table stays for the
  shop and the boss. The cap-refusal check is dropped for the cache: a
  perk can always be claimed.
- **New file** `src/game/stage_perk.c` with `#pragma bank 255`: claim,
  derived-state sync, hook bodies, dialog and Pack text. Callers in fixed
  banks make one `BANKED` call each and, in per-frame paths, test one
  cached WRAM byte first (the existing pattern, `powerup.h:70`).
- **Claim path.** `pickup.c:881-901` calls `stage_perk_claim()` instead of
  `apply_item_effects`. The guard rule, the jingle,
  `RUN_FARFOLD_CACHE_BIT`, and the 120-frame ceremony are unchanged.
- **Icon.** The tableau draws one 8x8 OBJ tile. To add no VRAM tiles, each
  perk reuses an existing item glyph (see open question 5).
- **Text source.** Perk names and dialog lines live in typed Rust content
  (a nine-entry table next to `content/src/stages.rs`) and are emitted to
  `src/generated/`. Validation: exactly nine entries, one per stage, name
  at most 12 characters, each dialog line at most 18. The effects
  themselves are C.
- **Pure roguelike.** All perk state is in `run_state`, so it is saved by
  the suspend record and wiped with it. The only cross-run trace is one
  trophy bit, in the same class as the existing Void Lord and Hexa bits.
- **Stat curve.** The cache was one of three structured relic sources per
  stage in `2026-11-17-stat-drop-tune.md`. Removing it slows ATK/DEF/HP
  growth a little. `scripts/sim_stat_drop_curve.py` must be re-run.

## 3. Option A: nine named relics with set tiers

Each stage's cache holds a fixed, named relic with its own small mechanic
change. Owning any 3, 6, and 9 of them unlocks a tier bonus. What you get
depends on which stages you explored.

### 3.1 Perk table

All nine base perks are the same for every class. Class variation is in
tier II (§3.2).

| Stage | Relic | Perk | Hook |
|---|---|---|---|
| 1 Crystal Caverns | Prism Shard | Clearing a room restores 2 MP instead of 1. | `room.c:2111-2114` |
| 2 Verdant Hollow | Bloom Seed | Clearing a room at half HP or less heals one half-heart. Blocked by the same statuses that block other healing. | `room.c:2109` |
| 3 Ember Depths | Cinder Spur | Dash cooldown 30 to 20 frames; dash iframes 14 to 20. | `room.c:1496-1498` |
| 4 Frost Vault | Still Heart | Will charges 25% faster. | `will_support.c:26` |
| 5 Toxic Mire | Mire Gland | B signature cooldown 18 frames shorter. The floor of 36 stays. | `will_support.c:55-57` |
| 6 Shadow Keep | Gloam Thread | Oath Art cooldown 96 to 64 frames. | `room.c:1806` |
| 7 Golden Temple | Sun Censer | Surge Sparks and Capsules last 25% longer. | `status.c:104`, `powerup.c:180` |
| 8 Bloodmoon | Red Tithe | 13/256 of the "nothing" drop band becomes a half-heart (12.1% to 17.2% on Normal). Same single RNG byte; existing bands do not move. | `powerup.c:164-171` |
| 9 Void Sanctum | Rift Core | Oath Arts cost 0 MP. | `room.c:1802-1804` |

Numbers are starting points for tuning, not final.

### 3.2 Compounding: tiers at 3, 6, 9

Tiers count relics owned, in any order. Three per tier matches the
three-dungeon region (`run_state.h:24-28`), so a region explored in full
is exactly one tier. The owner's 2/4/all is a one-table change (open
question 2).

| Tier | Needs | Bonus |
|---|---|---|
| I, Seeker | 3 | From now on, each dungeon's Farfold Cache cell is shown on the Compass on entry (`run_state_reveal_dungeon_cell`). |
| II, Attuned | 6 | The hero's own B verb improves (below). |
| III, Crowned | 9 | The all-collected bonus (§3.3). |

Tier II by class, using constants that already exist in `will.h`:

| Hero | Tier II |
|---|---|
| Wolfkin | Howl may land 4 blades on one Colossus instead of 3 (`WILL_HOWL_GIANT_HIT_CAP`). |
| Sauran | B guard lasts 25% longer (`player.shield_timer`). |
| Corvin | Marked-target bonus damage 1 to 2 (`WILL_CORVIN_MARK_BONUS`). |
| Picsean | B cooldown base 120 to 96 (`SIGNATURE_CD_PICSEAN`). |
| Vespine | Swarm lasts 25% longer (`will_vespine_swarm_ticks`). |

### 3.3 All-collected bonus

Rift Core is in stage 9, so the bonus is live for the rest of Void Sanctum
and the last Colossus.

- **Farfold Crown.** Once, a lethal hit instead leaves the hero at half HP
  with 120 iframes, through the existing revive path. Order: Phoenix
  Thread, then Last Light, then the Crown, so nothing is wasted.
- **Trophy.** `META_FLAG_FARFOLD_CROWN = 0x08` is set in `meta_flags` when
  a crowned run ends. Where it is shown (title or victory screen) is open
  question 4.
- No new art: the Pack tracker reads CROWNED.

### 3.4 UI

- **Pickup.** Same raised-arm ceremony. Dialog page, for example:

  ```
  CINDER SPUR
  FARFOLD RELIC 3/9
  DASH RECOVERS FAST
  LONGER DASH GUARD
  SEEKER TIER WOKEN
  ```

  The last line appears only when the claim completes a tier.
- **Pack tracker.** On the Status page, replace the two legend rows
  (`inventory_waygear.c:189-190`) with:

  ```
  FARFOLD 12-45----
  TIER I   NEXT AT 6
  ```

  Digits are the stages whose relic is owned; a dash is a missed or future
  stage. It uses the existing font, so it costs no tiles. The main Pack
  page is unchanged.
- **Compass.** The cache node already exists. Tier I reveals it on entry.

### 3.5 Cost

| Where | Cost |
|---|---|
| `run_state_t` | +2 bytes: `u16 stage_perks`. Bits 0-8 owned, bit 9 Crown spent, 10-15 spare. Appended; 93 to 95 bytes. |
| Suspend SRAM | +2 bytes (148 to 150). Add `PRE_PERK_RS_SIZE 93` to the accepted lengths in `sram.c` and `sram_write.c`. Older suspends load with no relics. |
| Meta SRAM | 0 bytes; 1 bit in the existing `meta_flags` byte. |
| WRAM outside `run_state` | 2 bytes: cached low perk mask and tier, rebuilt on load and on claim. |
| VRAM | 0 tiles. |
| ROM, new autobanked file | Estimate 0.9-1.2 KB: logic 450-600 bytes, text about 450 bytes. |
| ROM, fixed banks | Estimate 8-12 bytes per call site. Bank 1 (`room.c`) has four sites (room clear, dash, Oath cost, Oath cooldown), about 40-50 bytes. Banks 5, 11, 12, 13, 20, 24 get one or two sites each. |

The bank 1 and bank 13 sites are the risk. If either has no room, the
perk moves to a hook in a roomier bank or is swapped for another.

## 4. Option B: Farfold Facets, a rank track

Every cache holds the same object, a Farfold Facet. The Nth Facet you
claim, whatever the stage, unlocks rank N of a nine-rank track. The track
has three lines (Arm, Sign, Spirit) and visits each line three times, so
each new Facet raises the level of a line an earlier Facet opened. What
you get depends on how many you have and who you are.

### 4.1 Perk table

Rows are by claim order. The stage column assumes no cache was skipped;
skipping one shifts every later row down by a stage.

| Facet | Stage if none skipped | Unlocks | Effect at that level |
|---|---|---|---|
| 1 | Crystal Caverns | Arm I | Every 8th primary attack also fires a half-damage forked pair (the existing fork, `relic_runtime.c:66-69`, on its own counter). |
| 2 | Verdant Hollow | Sign I | Class B verb, level 1 (below). |
| 3 | Ember Depths | Spirit I | Will charges 15% faster; Oath cooldown 96 to 84. |
| 4 | Frost Vault | Arm II | Fork every 6th attack. |
| 5 | Toxic Mire | Sign II | Class B verb, level 2. |
| 6 | Shadow Keep | Spirit II | Will +30%; Oath cooldown 72. |
| 7 | Golden Temple | Arm III | Fork every 4th attack. |
| 8 | Bloodmoon | Sign III | Class B verb, level 3. |
| 9 | Void Sanctum | Spirit III | Will +45%; Oath cooldown 60; plus the capstone (§4.3). |

Sign line by class:

| Hero | Level 1 / 2 / 3 |
|---|---|
| Wolfkin | Howl Colossus hit cap 4 / 5 / 6. |
| Sauran | B guard duration +20% / +40% / +60%. |
| Corvin | Mark bonus damage 2 / 3 / 4. |
| Picsean | B cooldown base 108 / 96 / 84. |
| Vespine | Swarm duration +20% / +40% / +60%. |

Arm I-III overlaps the Echo Prism ware (fork every 4th attack,
`relic_runtime.c:63-65`). With both owned the two counters run
independently. This is the one place either option leans on a ware's
effect.

### 4.2 Compounding

There are no thresholds. Each Facet amplifies an earlier one: Facet 4
makes Facet 1's fork more frequent, Facet 5 strengthens Facet 2's verb,
and so on. A missed cache costs exactly one rank and nothing is locked
out.

### 4.3 All-collected bonus

- **Unbroken Convergence.** Spirit Convergence leaves half of max MP
  instead of draining to 0 (`room.c:1785`).
- The same trophy bit as Option A.

### 4.4 UI

- **Pickup.** Same ceremony. Dialog, for example:

  ```
  FARFOLD FACET
  RANK 4/9   ARM II
  FORK EVERY 6TH HIT
  NEXT: SIGN II
  ```

- **Pack tracker.** Same two Status-page rows:

  ```
  FACETS 4/9
  ARM 2  SIGN 1  SPI 1
  ```

### 4.5 Cost

| Where | Cost |
|---|---|
| `run_state_t` | +1 byte (`u8 facet_rank`, 0-9), or 0 bytes if packed into the unused bits 12-15 of `rift_sigils` (`run_state.h:106` uses bits 0-8; `run_init.c:65` writes only low bits). The appended byte is cleaner. |
| Suspend SRAM | +1 byte, same `PRE_PERK_RS_SIZE 93` step; or 0. |
| Meta SRAM | 1 bit. |
| WRAM outside `run_state` | 3 bytes: cached level per line. |
| VRAM | 0 tiles; one shared glyph for all nine pickups. |
| ROM, new autobanked file | Estimate 0.6-0.8 KB. One 5x3 class table and three level tables instead of nine separate effects; fewer text lines. |
| ROM, fixed banks | Bank 1: one site (Oath cooldown), plus one for the capstone. Banks 11 and 29: the Will, signature, and fork sites. Fewer bank-1 bytes than Option A. |

## 5. Recommendation

**Option A**, with one idea borrowed from B.

- It matches the request most directly: each stage has its own named
  thing, and "what did Frost Vault's relic do?" has an answer the player
  can remember between runs. That is the knowledge a pure roguelike is
  supposed to keep.
- A missed cache is felt as a missing digit in the tracker, which gives a
  reason to go back for it. In B a miss is only "one rank lower".
- Nine separate small hooks are easy to tune or replace one at a time.
  B's Sign line needs all five classes balanced at three levels at once.
- B is cheaper in bank 1 and in text. If the build shows bank 1 cannot
  take four call sites, B is the fallback.

Borrowed from B: Gloam Thread (stage 6) and Rift Core (stage 9) both act
on Oath Arts on purpose, so two of A's relics amplify each other, not
only the tiers.

**Build first** (one PR, playable on hardware):

1. `stage_perks` in `run_state`, the save-length step, the claim path, and
   the Pack tracker row.
2. The three region-1 relics (Prism Shard, Bloom Seed, Cinder Spur) and
   tier I. Stages 4-9 keep paying today's stat relic until their relic
   ships, so nothing gets worse in the meantime.
3. Tests from §7 for those pieces.

Then stages 4-6 with tier II, then stages 7-9 with the Crown and trophy.

## 6. Open questions for the owner

1. Is the Farfold Cache the item you meant? §1.1 says why I think so.
2. Tiers at 3/6/9 (one per region) or 2/4/all as in the issue?
3. Should the cache pay the perk **instead of** the stat relic
   (recommended; the boss and shop still pay it) or **as well as** it?
4. Is a cross-run trophy bit for a crowned run acceptable under "only
   knowledge persists", and where should it show?
5. Icons: reuse existing item glyphs for the nine relics (0 tiles, but a
   glyph then means two things), or find one free OBJ slot for a shared
   Farfold glyph?
6. Rift Core arrives in the last stage and is used for one dungeon and
   one boss. Fine as a finale, or should stage 9's relic be something
   that only matters for the Crown?
7. The Riftwild island Mana Gem (§1.1) has the same big-ceremony, small
   reward problem. Fold it into this work, or leave it?
8. Starting a run at a later stage (`run_init.c:65`) cannot reach nine
   relics. Acceptable?
9. Should Easy change any perk numbers, or only Normal be tuned first?

## 7. Test plan

Headless PyBoy, following `scripts/test_farfold_cache.py` (symbol lookup
from the `.noi`, WRAM pokes to set stage and class).

- **New `scripts/test_stage_perks.py`.**
  - For each stage 0-8 and at least two classes: enter the cache cell,
    clear the guards, touch the orb. Assert the stage's bit is set in
    `run_state.stage_perks`, `RUN_FARFOLD_CACHE_BIT` is set, no `player`
    stat changed, `room_major_reward_pending` counts down from 120, and
    the dialog opens.
  - A capped stat no longer refuses the cache.
  - One behaviour assertion per relic, by poking the bit and reading the
    knob: MP after a room clear, heal at half HP, dash cooldown value,
    Will charge over N frames, signature cooldown after B, Oath cooldown
    and MP after an Oath, Surge ticks, the drop band for a forced RNG
    byte.
  - Tiers: poke 2, 3, 5, 6, 8, 9 bits and assert the tier byte; tier I
    reveals the cache cell on dungeon entry; tier II changes the class
    knob for all five classes.
  - Crown: a lethal hit with nine bits revives once, sets the spent bit,
    and does not fire while Phoenix Thread or Last Light is available.
  - Pack: open the Status page and read the tracker row from the BG map.
- **Update** `scripts/test_farfold_cache.py` and
  `scripts/test_farfold_guard_notice.py` (the cache no longer applies an
  item), `scripts/test_sram_compat.py` and `scripts/test_suspend.py` (a
  93-byte suspend loads with zero relics; a 95-byte one round-trips the
  bits; death clears them).
- **Unchanged and must still pass:** `scripts/test_boss_rewards.py` (boss
  relic table), `scripts/test_stat_drop_curve.py` after the sim is re-run
  without the cache source, and the procgen parity check (the claim path
  spends no RNG).
- **Cargo tests** for the new content table: nine entries, unique stage
  ids, name and line length limits, and a codegen golden test for the
  emitted strings.
- **Layout gate:** `scripts/check_rom_layout.py` on every link, with the
  per-bank headroom of banks 1, 5, 11, 12, 13, 20, 24 noted in the PR.
- Hardware: one owner pass on the 3DS for the feel of the first three
  relics before the rest are built.

## Out of scope

Changing the boss relic or shop stat item, Veil charms, the cache room's
layout or guards, new art, and the Tough Skin dialog line bug noted in
§1.2.
