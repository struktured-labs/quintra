# Stat-up drop tune: maxing ATK/SPD takes the whole run

Date: 2026-11-17. Status: proposed (Carbon review next). Trigger: Carmelo,
Vespine run, maxed attack and speed by stage 2; "those stats drop too
easily in general." Target: on a thorough Normal run, near-max (cap minus
2) should not arrive before stage ~6-7 of 9, without making early game
feel stingy. Caps and per-pickup increments stay the same.

## Current numbers (main `4614675c`)

Caps: ATK 15, SPD 12, DEF 10, LCK 10, HP 30, MP 20. Almost every stat
pickup is +1 (Iron Heart +2 HP, Lucky Coin +2 LCK, Hunter's Eye +3 LCK,
Glass Fang pact +2 ATK / +1 SPD / -2 max HP).

Starting ATK/SPD (Normal, Wolfkin includes the +1 SPD perk):

| Hero    | ATK | SPD | To cap |
|---------|-----|-----|--------|
| Wolfkin | 2   | 6   | +13 / +6 |
| Sauran  | 2   | 4   | +13 / +8 |
| Corvin  | 2   | 4   | +13 / +8 |
| Picsean | 1   | 4   | +14 / +8 |
| Vespine | 4   | 6   | +11 / +6 |

Easy adds +4 ATK and +2 DEF at init, so a Tester-Easy Vespine starts at
ATK 8. LCK is described as "better drops" on Lucky Coin but is not
consulted by `pickup_roll_drop`. Stinger's +3 LCK, if applied, does not
change drop rates today.

### Sources

1. **Enemy deaths** (`pickup_roll_drop` in `powerup.c`, bank 20). Normal
   relic band is 5/256 (~2.0%); Easy 8/256 (~3.1%). The relic is
   `10 + rng_range(10)`, uniform over the ten stacking stat orbs: Iron
   Heart, Speed Ring, Power Stone, Tough Skin, Lucky Coin, Mana Gem, Ward
   Charm, Swift Fang, Hunter's Eye, Blood Sigil. Three of those grant
   ATK (Power, Swift, Blood) and two grant SPD (Speed, Swift).
2. **Class-attuned structured relics** (`pickup_farfold_relic_for_class`
   in `treasure_guard.c`). The same three-item table is used for the
   dungeon shop `WARE_ITEM`, the Farfold cache, the stage-boss relic, and
   both sides of a director boon pair. Current tables:

   - Wolfkin and Vespine: Power, Swift, Blood — **3/3 grant ATK**, 1/3
     also SPD.
   - Corvin: Speed, Power, Swift — 2 ATK, 2 SPD.
   - Sauran: Iron, Ward, Blood — 1 ATK.
   - Picsean: Power, Mana, Ward — 1 ATK.

3. **Secret vaults** (one per dungeon) and the **Riftwild region vault**
   also roll `10 + rng_range(10)`.
4. **Villages** after stages 3 and 6: Forge (+1 ATK) and Vamp Sigil
   (+1 ATK, optional sustain pact).
5. **Featured dungeon build shelf** (1/6 Glass Fang, 1/6 Vamp). Glass is
   a pact, not a free drop.
6. **Wildcards** (10/256, optional): 1/8 of fates is +1 ATK, 4/8 are
   curses. Left alone; they are a gamble, not a reliable curve.
7. **Vespine's Swarm** does not spawn extra drop sources. It only makes a
   thorough clear of optional packs more reliable. A +15% kill-count
   sensitivity does not change the diagnosis: the class table is the leak.

A typical Normal dungeon has on the order of 210–360 first-visit kills
plus ~2 director boons (ELITE / HOLD, 2/8 of eligible large courts).
Because Wolfkin/Vespine structured relics are 100% ATK, a thorough
Vespine who takes shop, Farfold, boss, and ATK-side boons is at or near
both caps by the end of stage 2. Monte Carlo (400 runs, see
`scripts/sim_stat_drop_curve.py`):

| Hero    | S2 mean ATK/SPD (before) | % near-max at S2 |
|---------|--------------------------|------------------|
| Vespine | 15.0 / 11.3              | 100% / 90%       |
| Wolfkin | 14.9 / 11.1              | 100% / 86%       |
| Corvin  | 14.7 / 11.0              | 96% / 85%        |
| Sauran  | 13.7 / 6.3               | 78% / 2%         |
| Picsean | 13.2 / 6.4               | 68% / 2%         |

This matches the report. DEF / LCK / HP / MP are not on this curve:
they only come from the uniform 10-orb roll and a few shops, and they
do not need a nerf.

## Design

Keep early finds generous. Cut the guaranteed ATK/SPD firehose, then
taper random ATK/SPD as the hero rises, without spending extra RNG
(vault and secret generation must stay seed-length stable).

### 1. Retune class-attuned tables

Each hero's shop / Farfold / boss pool has **at most one ATK-granting
relic and at most one SPD-granting relic**. Swift Fang counts as both,
so it is removed from these tables (it can still drop from the 10-orb
roll). Boons no longer use this table (see 2).

| Hero    | Before            | After                         | Identity |
|---------|-------------------|-------------------------------|----------|
| Wolfkin | Power, Swift, Blood | Power, Iron Heart, Ward Charm | offense + sustain |
| Sauran  | Iron, Ward, Blood | unchanged                     | already mixed |
| Corvin  | Speed, Power, Swift | Power, Speed, Mana Gem      | offense, mobility, MP |
| Picsean | Power, Mana, Ward | unchanged                     | already mixed |
| Vespine | Power, Swift, Blood | Power, Iron Heart, Lucky Coin | offense, the HP she lacks, crit/luck |

Wolfkin and Vespine do **not** have Speed Ring in the structured pool:
they already start at SPD 6, and one Speed per dungeon would cap them
by mid-run. They still find Speed Rings from enemy and vault rolls.

### 2. Director boons become sustain / utility

`pickup_spawn_boon_pair` currently offers two class-attuned combat
relics, so a Vespine boon was ATK vs ATK. About two of these fire per
dungeon. The boon pair now rolls from a six-item sustain table, two
adjacent entries, no stacking ATK/SPD:

Iron Heart, Tough Skin, Lucky Coin, Mana Gem, Ward Charm, Hunter's Eye.

The directive still feels like a reward and a build fork (HP vs DEF vs
LCK vs MP). Shop, Farfold, and the colossus keep the "guaranteed power
curve."

### 3. Diminishing weights on random 10-orb rolls

New BANKED helper `pickup_roll_stat_relic()` (one `rng_next_u8()`, same
call count as today's `10 + rng_range(10)`). Used by enemy deaths,
secret vaults, and Riftwild vaults. When every weight is full this is
exactly `10 + (r % 10)`, so a low-stat roll is seed-identical to main.

Weights start at 4. ATK-granting orbs (Power, Blood; Swift uses
`min(atk, spd)`) and SPD-granting orbs (Speed Ring; Swift) drop to 2
once the hero has earned `+2 ATK` or `+1 SPD` from their Normal
starting line (Wolfkin perk and Easy bonuses are part of the baseline,
not "earned"), then to 1 once they have earned `+5 ATK` or `+4 SPD`.
HP, DEF, MP, and LCK orbs keep weight 4 for the whole run, so late
rooms stay generous in other ways.

### 4. Left alone

Caps, +1 increments, village Forge / Vamp, Glass Fang, wildcards, Surge
/ Capsule bands (and the upcoming Phase 2 Roulette band in `/tmp/q-pow2`,
which sits after the relic band and should keep calling this helper if
it ever rolls a 10-orb). `/tmp/q-magic` does not touch drop code.

## After-curve (explorer: free loot + shop WARE_ITEM + Farfold + boss +
vaults + enemy drops; no village ATK, no Glass). 400 Normal thorough
runs, `scripts/sim_stat_drop_curve.py`:

| Hero    | S2 ATK/SPD | S2 near-max | S6 ATK/SPD | S6 near-max | First near-max |
|---------|------------|-------------|------------|-------------|----------------|
| Vespine | 8.5 / 7.7  | 1% / 7%     | 14.4 / 10.4| 91% / 77%   | 4.8 / 5.2      |
| Wolfkin | 6.5 / 7.8  | 0% / 8%     | 13.5 / 10.5| 74% / 79%   | 5.8 / 4.9      |
| Corvin  | 6.5 / 7.4  | 0% / 6%     | 13.4 / 11.7| 70% / 97%   | 5.9 / 4.0      |
| Sauran  | 6.4 / 5.7  | 0% / 0%     | 13.4 / 8.7 | 72% / 30%   | 5.9 / 7.9      |
| Picsean | 5.4 / 5.7  | 0% / 0%     | 12.6 / 8.7 | 56% / 30%   | 6.5 / 7.8      |

Early game still pays: Vespine climbs from 4/6 to about 8.5/7.7 by the
end of stage 2. Nobody is near-max there. Vespine (highest starting
ATK) reaches ATK near-max around stage 5–6; the rest around 6–7. Sauran
and Picsean have no class Speed, so their SPD line trickles in through
the late run (weight 1 after +4) and near-maxes at the end, which fits
the slow-mage / tank identities. Buying both village ATK wares after
stages 3 and 6 pulls a thorough shopper about one stage ahead; it still
does not max them in stage 2. Glass Fang can pull a dedicated pact
shopper earlier still, and costs max HP.

## Tests

- `scripts/sim_stat_drop_curve.py` is the oracle for weights, tables, and
  the explorer curve, imported by `scripts/test_stat_drop_curve.py`.
- The live-ROM test asserts the new class tables (shop `WARE_ITEM` and
  boss relic) and, when a ROM is present, that a low-stat
  `pickup_roll_stat_relic` roll matches `10 + (r % 10)`.
- `test_boss_rewards.py` and `test_shop_surge.py` update their hardcoded
  Wolfkin/Vespine/Corvin pools.
- `test_new_game_start` and `test_watch_intro` must keep passing; this
  work does not touch start or intro flow.
- `test_stat_max_pickup.py` and `test_speed_cap.py` are unchanged (caps
  and refuse notices stay).

## Banks

The class table edit is a same-size swap in `treasure_guard.c` (bank 13,
already tight — do not grow it). The new roll helper lives in its own
file in a free bank and is declared in `pickup.h`.

## Out of scope

LCK-influenced drops, Easy-mode starting bonuses, changing Glass Fang,
per-stage hard caps, and any deploy / SD-card copy.

## Carbon review (2026-11-17)

Verdict: **approve with changes**. Carbon call $0.1782; running total
$6.4536 logged. Taken:

1. Corvin also loses structured Speed Ring (pool is now Power, Mana Gem,
   Tough Skin). Structured SPD for any hero was putting Corvin near-max
   at stage 4.
2. SPD high-taper is now an absolute `SPD >= 8` (so it fires before
   near-max for the SPD-6 starters). Swift Fang weight drops to 0 once
   either ATK or SPD is in the high taper.
3. Vespine's structured pool is Power, Tough Skin, Mana Gem — not Lucky
   Coin or Iron Heart — so LCK and her low-HP identity are not overwritten.
   Boons are a 5-item table `{Iron, Tough, Lucky, Mana, Ward}` (Hunter's
   Eye removed). Lucky/Hunter orbs taper to weight 1 once `LCK >= 6`.
4. `pickup_boon_relic(roll)` wraps the full 0..4 table; the director's
   seed-sized roll is no longer reduced mod 3.
5. `pickup_map_stat_relic` has an explicit `total == 40` fast path that
   returns `10 + (r % 10)`, matching historical `10 + rng_range(10)`.
6. Earned-stat subtraction is guarded so a value below the baseline
   cannot wrap a `u8` and lock the taper.

### Final class tables

| Hero    | Shop / Farfold / boss        |
|---------|------------------------------|
| Wolfkin | Power, Iron Heart, Ward Charm |
| Sauran  | Iron Heart, Ward Charm, Blood Sigil (unchanged) |
| Corvin  | Power, Mana Gem, Tough Skin  |
| Picsean | Power, Mana Gem, Ward Charm (unchanged) |
| Vespine | Power, Tough Skin, Mana Gem  |

### Final explorer curve (400 Normal thorough runs)

| Hero    | S2 ATK/SPD | S2 near-max | S6 ATK/SPD | S6 near-max | First near-max |
|---------|------------|-------------|------------|-------------|----------------|
| Vespine | 8.4 / 7.5  | 0% / 2%     | 14.2 / 9.4 | 86% / 41%   | 5.0 / 7.2      |
| Wolfkin | 6.4 / 7.6  | 0% / 2%     | 13.1 / 9.4 | 66% / 44%   | 6.1 / 7.0      |
| Corvin  | 6.5 / 5.9  | 0% / 0%     | 13.2 / 8.2 | 69% / 18%   | 6.0 / 8.6      |
| Sauran  | 6.6 / 5.8  | 0% / 0%     | 13.2 / 8.4 | 68% / 20%   | 6.0 / 8.4      |
| Picsean | 5.5 / 5.7  | 0% / 0%     | 12.5 / 8.2 | 52% / 16%   | 6.6 / 8.6      |

Nobody is near-max at stage 2. Early game still pays (Vespine 4/6 to
8.4/7.5). ATK near-max clusters at stage 6 for four of five heroes;
Vespine, the highest starter, arrives a little earlier (mean first 5.0)
because she starts four points closer to the cap. Buying both village
ATK wares after stages 3 and 6 pulls a shopper about one stage ahead
and still does not max anyone in stage 2.
