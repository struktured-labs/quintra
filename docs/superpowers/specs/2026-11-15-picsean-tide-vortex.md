# Picsean Tide Vortex (full-Will Moon Tide)

Date: 2026-11-15. Status: **implemented.**

## Problem
Carmelo (2026-11-15): the per-champion full-Will specials need to be more
awesome. Wolfkin's Will wave (#63) is now the bar. "The water guy's attack
should be wilder: imagine a spiral attack that gets bigger and radially
wider and spans the entire room. Think powerful for each char, or highly
defensive." Moon Tide, Picsean's old A MAX, was a five-lane forward bubble
fan: competent, but it looked like a bigger primary.

## Behavior
- Applies only to Picsean's BubbleBolt MAX (A with a full Will meter, any
  tier). Undertow (B), the ordinary BubbleBolt and every other champion's
  MAX are unchanged. Other classes' MAX overhauls are spec-only in
  `2026-11-15-max-will-signatures.md`.
- **Shape.** Four spiral arms leave the hero and rotate (2/64 turn a tick,
  about 2.6 turns over the cast). Each arm twists more the farther out it
  goes (angle += radius/4 in 64ths), so it reads as a whirlpool, not spokes.
- **Growth.** The front radius rises from 10px on a smoothstep over 72
  ticks (1.2 s): a slow wind-up at the hero, a fast sweep through the room,
  then a settling crest. Its maximum is the distance from the cast point to
  the farthest corner of the visible room plus 12px (cap 240), so it always
  spans the whole screen wherever Picsean stands. A 12-tick crest at full
  size follows (84 ticks, 1.4 s in all). The vortex is centred on Picsean
  and follows him.
- **Arms widen.** Arm points use three cels (drop, curl, crest). Outer
  points use the bigger cels, and every 28 ticks all points step up one cel.
  An arm's hit band is ±4/64 of a turn around the spiral curve, widening to
  ±6/64 by the crest.
- **Hits.** Every awake enemy is hit once when the front reaches it
  (MAX damage +4) and once more when a sweeping arm crosses it afterwards
  (MAX damage +2). The arm test uses the body's bearing and distance from
  the moment the front reached it, compared with the arm's spiral angle at
  that distance. Arms turn 8/64 between visits, so a ±4 band never skips a
  body; bodies the front reaches in the last few ticks can miss the arm. MAX damage already includes the Will tier. Survivors are
  shoved outward through the ordinary knockback, which respects poise.
- **Shots.** Hostile shots inside the front are washed out (at most two
  impact puffs a tick). The Reaper's warned Mortal Scythe is exempt, as it is
  for every guard.
- **Fairness.** Heavy bodies (Colossi and Sentinels, the Stage Reaper,
  elites, alphas, rares, Bellwardens, the large-boss anchor, everything in
  the Hexa sanctum) take at most 6 per vortex hit before LCK and weakness,
  and at most two hits per cast. Colossus hits are also convergence-limited
  (four per cast) and keep the stage 3 (easy 5) per-hit cap and the Hexa and
  return-echo filters, because all damage goes through
  `combat_apply_player_shot_hit`. No i-frames and no body guard: contact
  still hurts, so the defence is the shot wash and the knockback.
- **Room exit.** Leaving the room ends the vortex on the next tick and
  restores palettes there.

## Animation and budget
- Four new 8x8 OBJ cels reuse Wolfkin's free slots 200..203 (one champion
  per run; both arts reload their tiles on every cast).
- 24 arm points are computed per cast tick, alternating 12 per frame in OAM
  24..35 (GB-style multiplex flicker). The entity pass keeps 4..23, and the
  raft and boss overlay keep 36..39. With the Serpent (which owns 4..31) the
  arms shrink to 32..35. Entities that the rotating allocator puts in 24..35
  during the 1.4 s cast flicker; most are dead or washed out by then.
- The centre eye is the carrier projectile's own sprite.
- OBJ palette 2 (player weapon) becomes a deep-blue, aqua and foam ramp, and
  goes white-hot at the crest. BG floor and wall slots surge to a water ramp
  for 6 frames at the cast, 4 at mid-sweep (tick 34) and 6 at the crest, then
  `room_status_blind_visual` restores them (blind-aware). The mid-room BG heal
  re-commits any write dropped in mode 3. The Hexa sanctum skips the
  flashes. There is a screen shake at the cast and at the crest.
- CPU cost per tick: 12 arm points from 3 base points (quarter-turn
  rotations, 8-bit clipping, quarter-square multiply table, no `__mulint`).
  The hit loop visits a quarter of the entity table per tick
  (`slot & 3 == tick & 3`). The front moves at most ~6px a tick, so that
  delays a hit by at most 3 ticks. Each visited body costs one octagonal
  distance, plus one bearing (a single division) when the front first
  reaches it. The arm draw is a 48-byte `memcpy` into shadow OAM.
- **Measured** (`scripts/test_picsean_tide_vortex.py`, a 14-body room with
  STOP-frozen bodies and HP refilled each frame; logic updates per 96
  frames): idle 94, **Tide Vortex 80**. In the same fixture on main, the old
  Moon Tide scored 65, Wolfkin's Moonfang 58 and Corvin's Murderstorm 66.
  This room has only a few scanlines of slack when idle, so it is the worst
  case. The vortex is the cheapest of the multi-hit MAX arts there and
  faster than the Moon Tide it replaces. The test fails below 70 or below
  75% of idle.

## Code
`src/game/picsean_vortex.c` is a new file, pinned to bank 18 (`#pragma bank
18`, BANKED), because bank 17 has no headroom left. The hooks are:
`will_fire_max` (BubbleBolt branch), `combat_resolve` (tick),
`combat_player_shots` (skips the `PROJ_AUX_VORTEX` carrier), `room_draw`
(arm OAM via `room_draw_overlays()`, which also hosts the Serpent and
Cinder draws so bank 1 keeps its 256-byte floor), and `entity_init_room`
(abort on room change). A recast while a vortex is still running reuses
its carrier, and cleanup kills any stray carrier.

## Evidence
`scripts/test_picsean_tide_vortex.py` (in CI). `test_will_max.py` now checks
the vortex instead of the Moon Tide fan, and `test_will_tiers.py` expects
one carrier per Picsean MAX. GIF:
`evidence/2026-11-15-picsean-tide-vortex/tide-vortex.gif` (recorded by the
test with `QUINTRA_VORTEX_GIF=<path>`).
