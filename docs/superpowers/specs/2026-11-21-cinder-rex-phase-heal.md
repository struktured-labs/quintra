# Cinder Rex phase-transition heal

Date: 2026-11-21. Tuning for Ember Depths (stage 3) Cinder Rex.

Phase 1 (the five-husk Kilnback pack) can chip the champion down, and the
64-tick metamorphosis in `cinder_transform_tick` currently heals nothing
before Rex unfolds. Carmelo: the fight is fair but hard; phase 1 spends a
lot of energy, and a late phase-2 loss often starts from that deficit.

## Drops

On the first frame of the pack-to-Rex transform (`cinder_phase == 1`,
`cinder_timer == 0`), spawn two `PICKUP_HEART_HALF` pickups (one full
heart total) through the existing `pickup_spawn` helper.

- Same drops on Easy and Normal. No difficulty branch.
- Preferred seats are the lower flanks of the arena, (72, 96) and
  (144, 96). Those sit inside both camera windows of the 224-px-wide
  arena, and below the authored transform fire band (`cinder_hazard_add`
  at x = 96 + (timer & 31), y = 66) and the 48x32 Rex unfold at (88, 50).
- If a preferred seat overlaps a live floor brand, a wall, or the
  transform corridor, the spawn walks a short 16-px neighborhood until it
  finds a walkable, brand-free tile. After `pickup_spawn` snaps for
  walkability, the real position is re-checked and rejected if it landed
  in a hazard.
- The hearts are marked persistent so a 4-second ordinary-drop timer
  cannot vanish them mid-dodge; they stay until collected.
- This fires only from `cinder_transform_tick` (the first metamorphosis).
  The late 40-HP husk reprise is phase 3 and does not drop another pair.
- The placement helpers live in bank 25 (`src/game/cinder_heal.c`) so
  bank 9 (`enemy_cinder.c`) only makes a one-shot far call.

## Brand lifetime (trivial fairness trim)

Phase-1 Brandwalk / Fire-pack pool TTL goes from 92/64 frames to 80/56.
The warning floor in `cinder_fire_add_fair` is unchanged. This is only a
slightly shorter burn so leftover brands are less likely to still cover
the floor when the hearts appear, not a pattern redesign.

## Tests

`scripts/test_cinder_phase_heal.py` drives the live transform and asserts
that both hearts spawn, sit on reachable floor, and do not overlap a live
fire pool. Easy mode is the same code path.
