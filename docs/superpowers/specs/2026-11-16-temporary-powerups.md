# Temporary power-ups, roulette capsules, Confusion retune, gem currency (proposal)

Date: 2026-11-16. Status: **proposal for Carmelo's review.** Phase 1
(framework + Aegis, Limitless, Mend) is implemented in a separate PR;
everything else here is spec only. Source request (Carmelo, verbatim):

> more power ups dropped from monsters or pick up able on map one time per
> run like Penta dragon. Ideas: replicates ur attack in parallel formations
> or radially. Larger radius of ur existing attack by 4x. A bomb assist with
> every attack. Two little buddies assisting u from side like life force.
> Random choice items that rotates really fast which it is like Penta
> dragon. Shield or temp def boost with obv indication via sprites etc.
> regen. Infinite mp for 15 seconds. Etc.

Facts below were read from `main @ c8c3bb52`.

## 0. What already exists (do not duplicate)

| Thing | Where | Notes |
|---|---|---|
| **Surge Spark** (`PICKUP_SURGE`, `WARE_SURGE`) | `room.c`, `status.c:room_start_weapon_surge` | 120 beats (~16 s) of +1 A damage, -4 frame cadence, class-shaped bonus (Wolfkin cleave, Sauran reach, Corvin 2nd lane, Picsean broad, Vespine pierce). Also grants Haste. `room_weapon_surge_ticks`. **This is the template:** a power-up is "a Surge with a different body". |
| Status slot | `status.c` | One primary condition per actor (`player_status_kind/ticks`, 8-frame beats). `QSTATUS_REGEN` and `QSTATUS_HASTE` are the only boons. A harm status *replaces* a boon. |
| **Confusion** | `QSTATUS_CONFUSION` | Already exists, see §9. |
| Wildcard fate orb | `pickup_wildcard.c` | 8 fates, boon or curse, violet/red/gold palette cycle. Closest existing thing to a roulette. |
| Echo Prism / Blast Seed / Rift Lens | `relic_runtime.c` | Permanent relics that already fork attacks, add area blooms, beams. Power-ups must read as *temporary, louder* versions, not replace them. |
| Sauran Stoneskin | `player.shield_timer` + `room_spawn_shield_aura()` | Already an aura sprite + hit absorb. Aegis reuses the aura path. |
| Pickup notices | `hud_notice.c` | `HUD_NOTICE_PICKUP_FRAMES = 45 + 60` (1.75 s); #101 "every pickup names what it did". Queue of 6. |
| MP vs Will | `player.mp/mp_max` (blue digits HUD cols 8-9), `player.will_charge/will_level` | **"MP" = `player.mp`** (Oath Arts cost `OATH_MP_COST=1`, A+B Convergence at full MP, Bomb B costs 1). Will is the A-hold charge meter, separate. Carmelo's "infinite MP" maps to `player.mp`; Limitless also covers Will (see P2). |
| Per-run flags | `run_state_t` (appended-byte ABI) | New bytes must be **appended**; suspend loads older layouts. |
| Suspend | `sram.c` | Saves run_state + player on room entry; `status_reset_all()` on load; `room_weapon_surge_ticks` is not saved (Surge is lost on resume). |

Enemy drop table today (`pickup_wildcard.c:pickup_roll_drop`, the live one;
the copy in `pickup.c` is `#if`'d out), Normal: half-heart 12%, coin 45%,
relic 2%, Surge 6%, Wildcard 4%, nothing 31%. Easy: 28/42/3/8/2, 17% nothing.

## 1. Goals and non-goals

- Short, loud, readable windows of power (8-20 s), never permanent.
- Every grab is announced by **name + effect**, held ~1 s longer than a
  normal card, with a distinct sound.
- Active power-up and its remaining time are always on the HUD.
- Fun but not boss-trivialising: Colossus rooms clip durations and every
  extra hit source uses the existing `PROJ_FLAG_CONVERGENCE` chord cap.
- Fits the crowded-scene budgets Argon tuned (40-OAM entity window,
  32 entities, status FX cap of 3, `free <= 6` spawn floor).
- Non-goal: changing permanent relics, Will tiers, or B signatures.

## 2. Drop sources

### 2.1 Monster drops ("Capsule")
A new `PICKUP_POWERUP` (kind 27) carries `ai_data[1] = power-up id`.
It takes share from coins and "nothing", not from hearts or Surge.

| Normal roll `r` | Today | Proposed |
|---|---|---|
| 0..30 | heart | heart (12%) |
| 31..145 | coin | coin (45%) |
| 146..150 | relic | relic (2%) |
| 151..165 | Surge | Surge (6%) |
| 166..175 | Wildcard | Wildcard (4%) |
| 176..183 | nothing | **Capsule (3%)** |
| 184..186 | nothing | **Roulette capsule (~1.2%)** |
| 187..255 | nothing | nothing (27%) |

Easy: Capsule 4%, Roulette 2%, from the "nothing" band.

Rarity tiers (rolled once when the Capsule spawns):
- **Common (70%)**: Mend, Aegis, Limitless.
- **Uncommon (25%)**: Formation, Halo, Long Reach, Blast Assist.
- **Rare (5%)**: Wingmates (buddies), and own proposals marked rare.

Gating: no Capsule spawns in Colossus/mini-boss rooms (they already
pay relics), town, or shops. At most **one live Capsule per room**
(prevents carpets in crowded rooms) and a 20 s run-clock cooldown after a
Capsule drops. Elites/alphas/rares double the Capsule chance.
Capsules despawn on the existing pickup lifespan but blink for the last 3 s.

### 2.2 One-time-per-run map pickups ("Shrines")
- **Dungeon:** one Power Shrine per stage, placed by procgen in a
  dead-end non-required cell (same candidate filter as the Farfold Cache:
  not the trial, sigil, warden, waystone, or start cell), sitting on a
  pedestal at room centre. Contents: a guaranteed Uncommon-or-better
  roulette (§3) so a found shrine always feels good.
- **Riftwild:** one per region on a field that is not a den, Riftwell,
  Warden, Waygear grove or gate field (reuse `riftwild_den.c` avoidance
  list). Offers a fixed seed-chosen Rare.
- Seed-stable: chosen from the run seed + stage, so reloading cannot reroll.
- Flags: **append** `u8 powerup_shrines` to `run_state_t`:
  bit 0 = this stage's dungeon shrine claimed (cleared at next dungeon
  start like `shop_bought`), bits 1..3 = region 0..2 Riftwild shrine
  claimed, bits 4..7 reserved. One byte, suspend-compatible (older
  saves read 0 = unclaimed, which is correct).
- Map: a claimed shrine shows as an empty pedestal; unclaimed shows a
  gold "!" on the earned compass map only after the room is visited.

## 3. Roulette capsule (Penta Dragon style)

- Body: 8x8 capsule, icon tile swaps through a seed-shuffled list of 4-6
  faces (never a curse; this is a pure boon, unlike Wildcard).
- **Cycle rate:** 6 frames per face (10 faces/s): fast, readable on
  hardware and in the Tesla browser (60 fps confirmed). Easy: 10 frames.
- Each face also swaps palette (§6 colour per power-up), so it reads by
  colour and shape, not only shape.
- **Lock rule:** the face drawn on the frame of first overlap wins. The
  game latches `ai_data[2]` at render time, so input lag cannot select a
  face the player never saw. On lock: 20-frame freeze with the icon
  flashing white, a "slot stop" click (CH4) then the power-up's fanfare.
- **Skill window:** the roulette drifts slowly toward the player once
  within 24 px (no magnetism before that) so players can time a touch.
- Shrines use a roulette that slows to 12 frames/face when the hero is
  within 16 px (a "drum roll" telegraph).

## 4. Power-up list

Durations are 8-frame beats (status convention); seconds shown at 60 fps.
**Boss** column: duration in Colossus/mini-boss rooms (clipped on entry,
never extended).

| Id | Name (card) | Effect summary | Normal | Boss |
|---|---|---|---|---|
| P1 | **AEGIS** | 3-hit shield bubble + DEF+2; aura ring sprite | 90 (12 s) or 3 hits | 60 (8 s) |
| P2 | **LIMITLESS** | MP never spent; Will refills on release | 112 (15 s) | 75 (10 s) |
| P3 | **MEND** | +1 half-heart every 12 beats | 90 (12 s) = up to 7 half-hearts | 90, 1 per 18 beats |
| P4 | **FORMATION** | A spawns 2 parallel copies ±8 px | 90 (12 s) | 60 |
| P5 | **HALO** | every 3rd A spawns an 8-way ring | 75 (10 s) | 45 |
| P6 | **LONG REACH** | A hit area ~4x (2x per axis), +reach | 75 (10 s) | 45 |
| P7 | **BLAST ASSIST** | each A impact blooms a small bomb | 90 (12 s) | 60 |
| P8 | **WINGMATES** | two flank buddies mirror A, eat shots | 150 (20 s) or both lost | 90 |
| P9 | **CLARITY** *(proposal)* | status immunity + cures current harm | 150 (20 s) | 150 |
| P10 | **LODESTAR** *(proposal)* | coin/heart magnet room-wide, +50% coin drops | 150 (20 s) | n/a |
| P11 | **STILLWATER** *(proposal)* | hostile shots move at half speed | 60 (8 s) | 40 |
| P12 | **NOVA** *(proposal)* | instant: clears hostile shots, 4 dmg to on-screen foes | instant | 2 dmg, convergence |
| P13 | **OVERWILL** *(proposal)* | Will charges 2x | 112 (15 s) | 75 |

### 4.1 Per-class behaviour

**AEGIS (P1).** All classes: `powerup_aegis_hits = 3`; a hostile
contact or projectile that would hurt instead consumes a hit, grants 18
frames of i-frames, plays a glass "tink" (CH4) and flashes the ring.
DEF+2 via `status_player_effective_stat` while active (so a 4th hit, if
the timer remains with 0 hits, does not apply; the bubble is gone when
hits reach 0). Sauran: Stoneskin and Aegis stack (Stoneskin checks
first, so Aegis hits are only spent when Stoneskin is down). Never
blocks Mortal Scythe or boss "unblockable" signatures (same exception
list as `player.shield_timer` checks).

**LIMITLESS (P2).** `player.mp` is not decremented by Oath Arts, Bomb
B, or Convergence while active; HUD MP digits pulse white/blue. Cooldowns
(`active_charge`) still apply, so it is "free", not "spam". Convergence
(which normally drains full MP) is allowed once per 4 s. Will: on A
release, `will_charge` refills to the next tier's threshold at most once
per 2 s (so Max-Will signatures are available roughly every 2 s, gated
by their own cooldowns). Class specifics: Wolfkin Oath dash cooldown
unchanged; Vespine swarm still capped by its own counter.

**MEND (P3).** A dedicated timer (`powerup_ticks`), **not** the status
slot, so a Poison hit does not erase it (Carmelo found statuses too
lethal: Mend should be the antidote of that feeling). Heals every 12
beats; blocked by Curse (`STATUS_PLAYER_HEALING_BLOCKED()`) but the
timer keeps running and the card says NO HEAL once. Sauran: same rate
(his own regen ring is separate). Overflow at full HP: heals nothing,
spends nothing.

**FORMATION (P4).** On every A projectile, spawn two copies offset
perpendicular ±8 px, same kind/direction, damage `(d+1)/2`. Wolfkin
melee: copies become two extra short arcs at ±45°. Sauran spear: copies
are thinner side spears (shorter `state_timer`). Corvin: copies on the
existing Gale lane rule (no 5-way). Picsean: copies are bubbles that pop
after 24 px. Vespine: copies pierce 1. All copies carry
`PROJ_FLAG_CONVERGENCE`. Skipped when `free <= 8` entity slots.

**HALO (P5).** Every 3rd A shot also spawns an 8-way ring of the class
projectile at `(d+1)/2` damage, range 40 px. Wolfkin: ring is a spin
slash (one 0xFF hitbox, 12 frames). Skipped when `free <= 10`.

**LONG REACH (P6).** "4x radius" interpreted as **4x area** (hitbox
nibbles doubled, capped 0xFF; travel +50%). True 4x radius (32 px
melee) is possible only for Wolfkin's neutral sweep and is offered as a
choice for Carmelo. Projectiles also draw a 1-tile "glint" trail every
other frame to show the bigger hit.

**BLAST ASSIST (P7).** Each A projectile's first impact (enemy or wall)
spawns a Blast Seed bloom (reuse `ITEM_ID_BLAST_SEED` code path) at
`max(1, d/2)` damage, max one bloom per 20 frames. If the player owns
Blast Seed, the bloom is bigger instead of doubled. Corvin/Vespine get a
lobbed bomb on every 2nd shot instead (they fire faster).

**WINGMATES (P8).** Two `ENT_FX`-type buddies (new `ENT_BUDDY` not
needed: reuse companion follow code) hover ±16 px to the hero's sides
(Life Force options), trailing 4 frames behind. Each fires a copy of
every 2nd A shot at half damage and absorbs one hostile projectile
(then pops). Coexists with the Road Echo companion. Buddy colour is the
class tier palette. Corvin buddies are ravens, Vespine are hornets,
others are glowing orbs (1 tile each).

### 4.2 Stacking and replacement
- **One timed slot** (`powerup_id`, `powerup_ticks`) plus Aegis's hit
  counter. Same power-up again: refresh to full duration plus 25%, capped
  at 1.5x base. A different power-up replaces the current one, with a
  card "AEGIS -> HALO". Instants (NOVA) never occupy the slot.
- Independent of Surge (Surge keeps `room_weapon_surge_ticks`) and of the
  status slot. Surge + Formation stack; damage of copies uses the
  surge-boosted base.
- Decision for Carmelo: a 2-slot variant (one offence, one defence) is
  feasible for +2 bytes but crowds the HUD lane.

## 5. Balance
- Colossus and mini-boss rooms: on entry, `powerup_ticks` is clipped to
  the Boss column; all extra projectiles carry `PROJ_FLAG_CONVERGENCE`
  so the existing per-cast chord cap limits boss damage; Aegis capped at
  2 hits in boss rooms; NOVA deals 2 and never interrupts a boss phase.
- No Capsule drops in boss rooms; the Roulette never shows NOVA there.
- Easy: durations +25%, drop rates above.
- Power-ups do not affect score multipliers.
- Deaths during a power-up are logged in the telemetry trace so the
  balance bot (`scripts/quintra_balance_bot.lua`) can flag a power-up
  that makes runs trivial (target: no power-up raises the bot's boss
  clear rate by more than 10 points).

## 6. Visuals and audio

| Id | Icon (8x8, OBJ pal) | On-hero indication | Grab SFX |
|---|---|---|---|
| AEGIS | blue round shield, pal 3 | `room_spawn_shield_aura()` ring every 8 frames + hero palette flash every 32 frames; ring flickers fast when 1 hit left | CH1 rising fifth + CH4 shimmer |
| LIMITLESS | blue droplet with ∞, pal 6 violet | HUD MP digits pulse; small sparkle above head every 2 s | CH1 rising arpeggio |
| MEND | green heart+cross, pal 7 | green "+" FX rising each heal (status glyph 224+REGEN) | `SFX_HEART` doubled |
| FORMATION | three arrows, pal 2 | copies themselves | `SFX_REWARD_SURGE` |
| HALO | ring of dots, pal 5 gold | gold ring flash at each ring cast | bell |
| LONG REACH | big fist/arc, pal 4 | glint trail | low whoomp |
| BLAST ASSIST | bomb + spark, pal 4 | blooms | fuse fizz |
| WINGMATES | two dots, class pal | buddies | two-note chime |

Expiry: 3 s before end the HUD icon blinks and a soft `SFX_TICK` plays
once per second (accessibility: visible and audible). On expiry a
"fade" card names it ("AEGIS ENDS").

Tiles: 8 power-up icons + 1 capsule shell + 1 aura frame. The OBJ tile
map is full (status glyphs 224..237, antidote 238, waygear 204..207,
town residents 208..). Icons go in the room-swapped range used by
`SPR_SURGE_ORB`-style overlays: load only the icons needed by the live
pickups in the current room (max 2 distinct per room by the one-capsule
rule) into 2 reserved slots, plus 1 HUD BG tile. Phase 1 reuses existing
tiles (shield aura, heart, MP wisp, Surge orb) and adds no OBJ tiles.

## 7. HUD
- The contextual lane (cols 12..15) already arbitrates boss HP, shop
  offers, loot timer, and action charge. Power-up uses the same lane with
  priority **below boss HP and shop offer, above action charge**: col 12
  = power-up icon (BG tile), cols 13..14 = seconds left (2 digits),
  col 15 = Aegis hits (pips) or blank.
- In boss rooms, where the boss bar owns the lane, the remaining time is
  shown by the hero blink cadence and the 3 s warning ticks; the Pack
  screen (`inventory_waygear.c`, like Surge's `write_beat_seconds`) lists
  the active power-up and seconds.
- **Announcement:** grab shows a name card ("AEGIS") then an effect card
  ("SHIELD x3") through the existing queue. Power-up cards use
  `HUD_NOTICE_POWERUP_FRAMES = HUD_NOTICE_PICKUP_FRAMES + 60` (~2.75 s),
  i.e. 1 s longer than ordinary pickups, per Carmelo.

## 8. Budgets
- **RAM (WRAM):** `powerup_id` 1, `powerup_ticks` 1, `powerup_aux` 1
  (Aegis hits / Halo counter / Limitless refill clock), `powerup_flags` 1
  (boss-clipped, warned), buddy state 4 (2x pos offset/hp) = **8 bytes**
  plus `run_state.powerup_shrines` 1 byte (also saved in SRAM).
- **ROM:** new `#pragma bank 255` file `src/game/powerup.c` (autobank)
  for apply/tick/HUD; hot-path hooks are one `if (powerup_id)` byte test
  in ROM0 call sites (`room.c` fire path, `combat.c` hurt path), so
  ordinary frames pay a load+branch. Bank 0 headroom must stay above the
  `report_budget` 384-byte floor (pre-existing fail on main: do not
  worsen). Estimated 1.5-2.5 KB banked for Phase 1, ~6 KB total.
- **OAM:** Aegis ring and Mend FX are `ENT_FX` entities (count against the
  32-entity pool and the 40-OAM window), max 1 aura FX live at a time.
  Buddies: 2 OBJ, on the hero's scanline band, which already carries the
  hero (2x2 = 2 per line) + weapon: worst case 2+1+2 = 5 of 10 per line.
  Formation/Halo copies obey `free <= 8/10` floors; status FX keep their
  cap of 3. The crowded-scene benchmark
  (`scripts/bench_crowded_baseline.py`, `test_crowded_equivalence.py`)
  must not regress.

## 9. Confusion retune (existing status)

Confusion already exists (`QSTATUS_CONFUSION`):
- Sources: **Rune Lantern** and **Dusk Midge** contacts and their
  projectiles (42% chance per hit Normal, 16% Easy); the player's Shadow
  element also confuses enemies (their shots then hurt other enemies).
- Duration: **90 beats = 12 s Normal, 6 s Easy.**
- Mapping: random of 4 modes (quarter-turn, horizontal mirror,
  half-turn, axis swap), and it **reshuffles** after 36 frames of
  sustained input ("adaptive"). Only D-pad bits change; A/B/Start/Select
  untouched; menus, map and Pack never remapped.
- Visuals: violet hero palette (6), status glyph FX every 4 beats, HUD
  card "CONFUSE" re-shown every ~2 s, Pack label "CONFUSE".
- Damage: none (non-DOT). Good.

Carmelo finds statuses too lethal; 12 s of reshuffling controls in a
crowded room is exactly that. Proposed:

1. Duration **24 beats (3.2 s) Normal, 16 (2.1 s) Easy.**
2. **No reshuffle.** One mode per application, and only the two most
   readable: **horizontal mirror** or **full reverse** (half-turn).
   Quarter-turn/axis swap removed.
3. Chance 42% -> **25%** (Easy 10%); after it ends, **4 s immunity**
   (`confusion_immune` byte) so it cannot chain-lock.
4. Visual: **two orbiting star sprites** above the head (status glyph
   tile 229, alternating palette 6/5), orbit 8 px every 32 frames, plus
   the existing violet tint. Cost: 2 OBJ near the hero band, drawn only
   while confused; uses the status FX lane so it respects its cap.
5. HUD icon: swirl BG tile in the contextual lane col 12 with seconds
   left (same widget as power-ups), and the existing CONFUSE card.
6. Audio: woozy two-note wobble on apply (CH1 duty sweep down/up), a
   clear "pop" on recovery.
7. Counters: **CLARITY** (P9) gives immunity and cures; **AEGIS**
   absorbing a hit also blocks that hit's status; **Antidote** cures
   Confusion as well (tool already exists; one-line extension); standing
   still for 1 s while confused shortens it by 8 beats (proposal).
8. **Controller interaction:** the web player's A/B swap and per-pad
   calibration remap physical buttons to GB buttons *before* the ROM;
   Confusion remaps GB D-pad bits *inside* the ROM after
   `status_player_filter_input`, so it never touches A/B and is identical
   for keyboard, touch, D-pad and stick (the stick becomes D-pad bits).
   Persistent aim (#26) reads the remapped direction, so shots follow the
   felt direction.

Tests (`scripts/test_status_effects.py`, new `test_confusion`):
- apply -> duration 24 beats Normal / 16 Easy; mode in {mirror, reverse};
  holding RIGHT for 120 frames never changes the mode.
- A/B/Start bits pass through unchanged under every mode.
- immunity: re-hit within 4 s does not reapply.
- star FX entity present while confused, gone after; HUD lane shows swirl.
- Antidote and Clarity cure it.

## 10. Gem currency (OPTIONAL, Carmelo undecided)

Replace the gold coin sprite with rupee-like gems whose colour and shape
state their value.

| Gem | Value | OBJ pal (existing) | Shape tell (colour-blind safe) | Sparkle |
|---|---|---|---|---|
| Green | 1 | 7 (green, orc pal) | small 4x6 diamond | none |
| Blue | 5 | 3 (blue, crawler pal) | 6x8 diamond with centre line | 1 glint/s |
| Red | 20 | 4 (heart red) | 8x8 faceted hexagon | 2 glints/s |
| Gold/violet | 50 | 5 (gold) / 6 | 8x8 star-cut + outline | constant twinkle |

**Palette feasibility.** All 8 CGB OBJ palettes are already assigned per
room (0 skeleton, 1 hero tier, 2 bullets/weapon, 3 crawler, 4 heart, 5
coin, 6 boss stage, 7 orc). Gems must borrow existing palettes, so their
exact hue varies slightly by room/stage (pal 6 is the boss stage colour;
pal 7 is reloaded by Hexa). Hence the **shape and sparkle rate carry the
value**, colour is a bonus. No new palettes needed.

**Drops.** Today: coin 1 (45% of drops), coin 5 in Riftwild setpieces/dens.
Proposed: enemy drop band stays 45%, split green 85% / blue 13% / red 2%;
elites: blue 60% / red 35% / gold 5%; dens and setpieces keep their
`COIN_5` spots as blue; boss rewards add one red. Expected coins per
room rises ~10%, offset by +10% shop prices or left as a gift.

**HUD.** cols 16..19 keep the 3-digit counter; the coin glyph becomes a
green gem glyph. `COIN_CAP = 999` unchanged.

**Merchant prices.** Unchanged in numbers (10/25/40...). Shop tags could
show price as gems (e.g. 25 = 1 red + 1 blue) but that is harder to read;
recommended: keep numerals.

**Save format.** `player.coins` is a u16 value; gems are only a
presentation of drop value, so **no save change**. Old suspends load.

**Tiles.** 4 OBJ tiles (replacing `SPR_COIN` 31 plus 3 slots), 1 HUD BG
tile. OBJ tile pressure is the main cost (§6).

**SFX (rupee-like).** Bright rising arpeggio on **CH1** (pulse, 12.5%
duty, short decay), the channel SFX already own; music keeps CH2/CH3 and
only borrows CH1/CH4 between effects (`sfx_claim_channels`).
- Green: 2 notes B5-E6 (today's `SFX_COIN`, ~12 frames).
- Blue: 3 notes E6-G#6-B6, ~16 frames.
- Red: 4 notes B5-E6-G#6-B6, ~22 frames, plus a CH4 high-noise sparkle tail.
- Gold: 5-note run to E7, ~30 frames, CH4 shimmer layer, brief
  `melody_lock(CLEAR)` so a nearby coin pickup cannot cut it off.
- Priority: below `SFX_SIGIL`/`SFX_PORTAL`/`SFX_PUZZLE`/`SFX_CLEAR`
  melody locks (they already block coin cues), above `SFX_FIRE`; a gem
  pickup during an active gem cue upgrades to the higher-value cue
  rather than restarting (prevents machine-gun chirps when 5 drop at once).

Pros: instantly readable value, more satisfying pickups, Zelda/Penta
feel, audible value is good for low-vision play. Cons: OBJ tile pressure,
hue drift from borrowed palettes, "rupee" is strongly Zelda-coded
(trademark-safe as long as the name is not used: call them **Shards**),
4 new SFX in banked audio (~200 bytes).

**Recommendation:** do it as presentation only (Shards), after power-up
Phase 2, because it touches no save data and little logic. Keep numeric
prices.

## 11. Suspend/save
- Power-up timers are **not saved** (same as Surge): suspends happen on
  room entry; on resume the power-up is gone and the card "POWER FADED"
  explains it. Alternative (Carmelo decision): append 2 player bytes to
  keep `powerup_id/ticks`.
- Shrine flags are saved (`run_state.powerup_shrines`), so a shrine can
  never be claimed twice.
- `test_suspend.py` and `test_sram_compat.py` must pass with the
  appended byte.

## 12. Test plan (headless PyBoy, like `test_surge.py`)
- `test_powerups.py`:
  - each Phase 1 power-up: poke `_powerup_id/_powerup_ticks` or spawn a
    `PICKUP_POWERUP`, assert effect (Aegis absorbs 3 hostile hits with no
    HP loss, 4th hurts; Limitless keeps MP across an Oath cast; Mend
    heals N half-hearts in its window, none under Curse).
  - timer ticks down, HUD lane shows icon + seconds, expires cleanly.
  - announcement: notice queue holds name then effect; frames =
    `HUD_NOTICE_POWERUP_FRAMES`.
  - boss-room clip on entry.
  - drop table: 10k seeded `pickup_roll_drop` rolls in a test hook
    within ±1% of the table.
  - one-live-capsule-per-room cap.
- `test_powerup_roulette.py`: cycle 6 frames/face, lock = face shown on
  overlap frame.
- `test_powerup_shrine.py`: shrine cell seed-stable, flag set on claim,
  survives suspend, not respawned.
- Perf: `test_crowded_equivalence.py`, `test_firing_performance.py`
  with Formation/Halo active in the crowded fixture.
- Budget: `scripts/report_budget.py`, `scripts/check_rom_layout.py`.

## 13. Phased implementation
1. **Phase 1:** framework (`powerup.c`, `PICKUP_POWERUP`, drop band,
   HUD lane widget, long announcement), AEGIS, LIMITLESS, MEND. Tests.
2. **Phase 2:** Roulette capsule; Confusion retune (§9).
3. **Phase 3:** FORMATION, HALO, LONG REACH, BLAST ASSIST (+ perf runs).
4. **Phase 4:** WINGMATES; shrines in procgen and Riftwild.
5. **Phase 5:** proposals P9-P13 that Carmelo picks; gem Shards (§10).

## 14. Decisions for Carmelo
1. One timed slot (proposed) or two (offence + defence)?
2. "4x radius": 4x area (proposed, safe) or literal 4x radius?
3. Power-ups lost on resume (proposed, like Surge) or saved?
4. Confusion: 3 s, fixed mirror/reverse, no reshuffle (proposed)?

## 15. Questions for Argon
1. OAM/scanline: with Wingmates (2 OBJ) beside the hero, Formation copies
   and the crowded-room fixture, where does the 10-per-line limit bite,
   and should copies skip spawning or flicker?
2. OBJ tile VRAM: best place for 2 room-swapped icon slots + capsule
   shell without colliding with status glyphs (224..238) or the
   per-room big-resident overlays?
3. Is a one-byte `if (powerup_id)` test in the ROM0 fire and hurt paths
   cheap enough vs the bank-0 headroom floor, or should the hooks live
   entirely in the banked fire path?
4. Boss fairness: is `PROJ_FLAG_CONVERGENCE` on all copies + duration
   clip enough to keep each power-up from deleting a Colossus phase
   (especially Halo vs. Hexa limbs and Wingmates vs. Serpent)?
5. Roulette readability at 6 frames/face on GBC LCD ghosting and Pocket:
   too fast? Should faces alternate palette and shape every frame?
