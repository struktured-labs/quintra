# Room status-effect harness (non-boss combat rooms)

Date: 2026-11-22. Follows `2026-11-22-balance-harness.md` (#201).

## Why

struktured's runs die to status effects in ordinary stage rooms, not boss
fights. The #201 sweep measured statuses inside the stage 3 Colossus fight
(540 fights, no harmful status landed) and its room runs mostly timed out
(79%) because the pilot wandered, so it could not answer the question.

## What

1. **Per-room scenario fixtures** (`scripts/balance_rooms.py fixtures`).
   For each stage, hero and difficulty, boot once with the
   progression-matched loadout (`boot_to_stage` + `apply_prior_progression`:
   the HP, gear and relics a player has on reaching that stage), then
   generate real combat rooms through the game's own room generator (the
   same RAM writes as `test_stage_archetypes.generated_room`), step the
   champion off the threshold and save a state. Only rooms with live
   enemies are kept. Default quota: 4 rooms per hero, 8 for stages 1-3,
   plus 8 Ember Depths (stage 3) rooms per hero that contain Cinder Maw
   (14) or Cinder Kite (25). Manifest: `fixtures.json` (seed, cell, room id,
   enemy kinds, focus).
2. **Room fights** (`balance_rooms.py fight`): every tier (bot, skilled,
   average, nonexpert; the #201 human filter) x seeds per fixture, 2 min
   cap. Fixes for the wandering:
   - only hostiles the champion can walk to count (flood fill of champion
     poses; same walkability rules as the pilot's BFS);
   - far targets are reached by walking the flood fill to the nearest cell
     with a cardinal firing lane (Quintra attacks are four-way), then the
     #201 pilot fights and dodges;
   - no damage dealt for 3 s, or no movement for 0.5 s, forces a 1.5 s
     committed walk and rotates the target; cells the champion fails to
     enter are learned as blocked;
   - the champion never walks out through a door (combat rooms act sealed);
     a room change ends the fight as `left_room` (excluded).
   Outcomes: `cleared` (no reachable hostile for 0.5 s), `died`, `timeout`,
   `left_room`.
3. **Events** per fight: every status landing (kind, HP, replaced status,
   crowd within 48 px, spike tile nearby), every hit taken (attacker, the
   status its attack carries, whether it procced), DoT ticks, and the death
   with its chain labels.
4. **Report** (`scripts/balance_rooms_report.py`), per difficulty, stage and
   tier, all recomputed from the event log:
   - landings per hit taken, overall and per status; carrier proc rate
     (hits from an enemy whose attack carries X that landed X);
   - HP at landing (hearts) and share landing at <= 1 heart;
   - share of deaths within 5 s / 10 s after a harmful landing vs the share
     of fight time inside such windows (lift); a status that procs on the
     killing blow itself is not counted; plus a **control lift** computed
     the same way after hits that landed no status, and the ratio
     (status windows vs plain-hit windows), because any hit predicts death;
   - chained patterns at death (Stop then a hit, Confusion near spikes,
     Blind with >= 3 enemies within 48 px, DoT pinning HP at half a heart
     then a hit, a new status replacing an active one) and how often each
     setup occurs at all;
   - the Ember Depths Cinder subset vs other Ember rooms; Normal vs Easy.
5. **CI**: a "Room status smoke" step (stage 3, 5 heroes, 2 rooms + 2
   Cinder rooms, average tier, 3 seeds) gates `rooms.lift10_max_normal` and
   `rooms.lands_per_hit_max_normal` in `scripts/balance_thresholds.json`
   (only when at least `min_deaths` / `min_hits` are seen).

## Definitions

- Statuses: burn, poison, bleed, slow, stop, confusion, blind, mute,
  brittle, curse, inversion (player status slot kinds 1-10 and 13).
  Gloam Leech's curse uses the separate curse system, so curse shows
  carrier hits but no slot landings.
- Windows: 5 s = 299 frames, 10 s = 597 frames (59.73 fps).
- Hazards: spike tiles (BGT_SPIKES); generated rooms have no pits.
- Hearts: 1 HP = half a heart.

## Caveats

- Tiers are modelled humans driving a scripted pilot; the pilot is not a
  human and fights every enemy in the room at once (it does not kite or
  use doors). Absolute death rates are therefore pessimistic for crowded
  rooms; the lift and per-hit rates are the comparable quantities.
- The harness row's `death_kind` / `death_age` treat inversion as
  harmless (the #201 status set); the report recomputes both from events
  with inversion included.
- Fixture generation uses the game's generator with sampled seeds, not the
  exact rooms of a particular run.

## Out of scope

No tuning changes. Candidate levers and expected effect sizes are in the
PR / report only.
