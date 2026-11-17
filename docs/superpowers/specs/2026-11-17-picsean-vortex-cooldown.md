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

- After a Tide Vortex is successfully begun, the next Will pip accrues
  on every other `will_charge_tick` (exactly 2× the ordinary first-pip
  time at the current SPD). At SPD 4 that is 360 frames, 6.00 s. Speed
  Ring and Swift Fang still shorten it, because the half-rate wraps the
  existing `16+spd` rule rather than replacing it with a fixed timer.
- The Will bar fills the whole time, just more slowly, so the longer
  wait is readable without a new HUD or a change to the vortex visuals.
- Once that first pip banks, the slow rate ends. Later tiers (4 / 5 /
  6 exposed seconds at SPD 5) are unchanged, and every other champion's
  MAX recharge is unchanged.
- Ordinary A still dumps in-progress charge. Undertow, MP, and Oath
  Arts are untouched. Recasting mid-vortex is no longer possible in
  practice, because Will is empty until the delayed pip banks, after
  the 84-tick (1.4 s) cast has already ended.
- Damage, growth, shot wash, heavy/Colossus caps, i-frames, and OAM
  budget stay as specified in `2026-11-15-picsean-tide-vortex.md`.

## Rationale

Doubling only the first pip after a vortex matches the request (~2×
current cooldown) and preserves the spectacle. Waiting to a full
Waygear cap before the next MAX would be a 6× wait (about 18 s) and
would punish a mid-run dump more than a Will-1 dump, even though both
already deal the same early-game damage. A hidden "MAX locked" timer
that let the bar go lavender early would feel like a missed input.

## Code

`picsean_vortex_slow_charge` is set in `picsean_vortex_begin` and
cleared in `will_bank_charge` (and on `player_clear_fields`).
`will_charge_tick` skips every other fraction increment while it is
set. `will_charge_fraction` is zeroed at the start of the vortex so
the 2× refill is deterministic.

## Evidence

`scripts/test_picsean_tide_vortex.py` asserts the post-vortex first pip
takes 360±3 frames at SPD 4, that 180 frames is no longer enough, and
that the following tier returns to the ordinary 240-frame (4.00 s)
cost at SPD 4 with Waygear owned.
