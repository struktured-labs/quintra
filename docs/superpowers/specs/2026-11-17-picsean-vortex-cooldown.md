# Picsean Tide Vortex cooldown

Date: 2026-11-17. Status: **implemented.**

## Problem

Carmelo (2026-11-17): "the maxed attack from psicean is awesome but too
powerful needs a longer cool down I think or something." Tide Vortex
itself should stay as it looks and feels. The problem is how often it
can come back.

A-button MAX spends every banked Will pip and can be fired again as
soon as the first pip refills. At Picsean's starting SPD 4 that is 180
frames (3.00 s), measured 179 frames (2.98 s) after a real cast because
of a leftover charge fraction. The first pip is enough: the art is the
same at every tier, and without Waygear the damage bonus is clamped to
Will 1 anyway (front `MAX+4`, arm `MAX+2`).

Measured on `main @ c7219ae3`, LCK 0, one body to the east of the
cast point:

| Hero (starter MAX) | Time to next Will 1 after a Will-1 MAX | Normal loss (hits) | Elite loss (hits) |
| --- | --- | --- | --- |
| Wolfkin Moonfang Rush (SPD 5) | 177 f / 2.95 s | 29 (2) | 29 (2) |
| Sauran Thunderline (SPD 4) | 176 f / 2.93 s | 64 (6) | 12 (1, heavy cap) |
| Corvin Murderstorm (SPD 4) | 175 f / 2.92 s | 20 (4) | 20 (4) |
| **Picsean Tide Vortex (SPD 4)** | **179 f / 2.98 s** | **12 (2)** | **11 (2, heavy cap)** |
| Vespine Queen's Needle (SPD 6) | 159 f / 2.65 s | 53 (5) | 49 (5) |

Picsean's 12 damage in one 1.4 s room-wide sweep already drops typical
stage bodies (6–12 HP) and most mid-stage ones (12–18 HP), washes
hostile shots, and knocks survivors back. The other MAXes can score
more on a single lined-up target, but none of them clear every body in
the view. Firing Tide Vortex on cooldown therefore yields about 4.0
DPS to every ordinary enemy at once (3.7 on a heavy). That is the
overtune. A modest damage trim would make the art feel weaker without
fixing the repeat rate, so this pass leaves front/arm bonuses and the
heavy cap alone.

## Behavior

- After a Tide Vortex is successfully begun, the next Tide Vortex is
  locked for 360 frames (6.00 s) on `loop_frame_counter`. This is
  exactly 2× the ordinary first-pip time at SPD 4. The lock is a
  recast gate in `will_fire_max`, not a change to the shared Will
  charge tick, so other champions, idle frames, and crowded Serpent
  rooms pay nothing.
- Will still banks on its ordinary clock (180 frames / 3.00 s at
  SPD 4). During the remaining lock an A press is a normal BubbleBolt
  and does not spend the banked pip, so the charge is not wasted.
  Speed Ring and Swift Fang still shorten the time to that first pip;
  the recast lock itself is a fixed 360 frames so the 2× wait cannot
  shrink back to a 3 s room-clear on a stacked-SPD run.
- Later tiers, Undertow, MP, and Oath Arts are unchanged. Damage,
  growth, shot wash, heavy/Colossus caps, i-frames, and OAM budget
  stay as specified in `2026-11-15-picsean-tide-vortex.md`. Vortex
  visuals are unchanged.

## Rationale

Doubling the recast wait matches the request (~2× current cooldown)
and preserves the spectacle. A shared-tick half-rate or a doubled
first-pip cost was rejected: either change sits on the Will charge
or HUD path, and even a few extra cycles there made the Serpent
plated-tail fixture miss its Tide Vortex pass-through by one pixel
(max_x 83 vs 84) in a crowded boss room already on the CPU edge.
Gating only `will_fire_max` keeps that path idle-cost-free.
Waiting to a full Waygear cap before the next MAX would be a 6× wait
(about 18 s) and would punish a mid-run dump more than a Will-1 dump,
even though both already deal the same early-game damage.

## Code

`picsean_vortex_slow_charge` and `picsean_vortex_ready_at` are set in
`picsean_vortex_begin` (`ready_at = loop_frame_counter + 360`) and
cleared on `player_clear_fields`. `will_fire_max` (BubbleBolt branch)
returns 0 while the lock is held (wrap-safe unsigned compare). A
successful recast starts a new 360-frame lock. `will_charge_tick` is
unchanged.

## Evidence
## Evidence

`scripts/test_picsean_tide_vortex.py` asserts the post-vortex first pip
takes 360±3 frames at SPD 4, that 180 frames is no longer enough, and
that the following tier returns to the ordinary 240-frame (4.00 s)
cost at SPD 4 with Waygear owned.
