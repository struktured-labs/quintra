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
  ticks (1.2 s): a slow wind-up at the eye, a fast sweep through the room,
  then a settling crest. Its maximum is the distance from the cast point to
  the farthest corner of the visible room plus 12px (cap 240), so it always
  spans the whole screen wherever Picsean stood. A 12-tick crest at full
  size follows (84 ticks, 1.4 s in all).
- **Anchor.** The vortex is centred on the tile where Picsean spent Will
  and stays there, so she can swim away while it fills the room. This is
  Argon's Abyssal Maelstrom default: she is a fragile control-mage, and
  personal protection already belongs to B's Undertow. A following eye
  would force her to stand in the storm. The eye sprite parks at that
  same origin.
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

## Argon review (2026-11-15, main @ 1c522cfc)

Argon named this art **Abyssal Maelstrom** and proposed a 4–6 satellite
entity spiral growing from 10px to 84px, OBJ tiles 200..203, a bullet
squeegee, zero i-frames, and a 3-hit Colossus cap. What we adopted or
kept:

- **Adopted:** the cast-point anchor (see above). The room-wide shot
  wash, OBJ 200..203, zero i-frames, and Colossus/heavy caps were
  already in the first implementation.
- **Kept, on purpose:** the multiplexed 24-point OAM arms and a front
  that grows to the farthest visible corner (cap 240), not Argon's 84px
  radius. 84px was a budget for a 4-satellite entity design and would
  not fill a 160x136 room from a corner (or even quite from the centre,
  where a corner is ~105px away). Carmelo asked for a spiral that
  "spans the entire room"; the OAM-arm approach can actually do that
  without spending 4–6 entity slots. The natural hit structure is one
  front hit plus one arm hit, so the heavy/Colossus cap stays at two
  hits per cast (capped at 6 damage each) rather than Argon's 3.
- The shipped name stays **Tide Vortex**. Abyssal Maelstrom is the
  review name.

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

## Swirl variant (prototype, not the default)

Carmelo (2026-11-15), on the shipped GIF: the vortex "looks really cool but
not what I meant, I meant more like a swirlly thing but it looks pretty
cool as is." Later: "can have droplets near edges of it?" This variant
keeps the #105 gameplay (anchored at the cast point, room-filling front,
shot wash, heavy/Colossus caps, OBJ 200..203, 12 OAM) and only changes
the look:

- The body is one continuous water stream: ten overlapping stroke cels
  (`\\`, `--`, `|`) packed at a 4px step along a curling spiral, so
  they read as a connected ribbon rather than a ring of dots or a
  dashed arc. It spins at `3/64` of a turn a tick.
- A light spray of droplets breaks off along the outer edge and ahead
  of the leading tip (two decorative sprites, plus mist pixels baked
  into the stroke cels). Droplets are visual only; hit bands stay #105.
- Tile 203 is a compact water drop, used for the eye and the loose
  spray. Same budget: OBJ 200..203, 12 OAM (24..35).

Build with `make VORTEX_SWIRL=1` (`-DPICSEAN_VORTEX_SWIRL=1`). The
default build is the shipped #105 vortex, unchanged. Carmelo will pick.

## Cooldown (2026-11-17)

Carmelo: the art is awesome but too powerful and needs a longer
cooldown. After a successful Tide Vortex the next Will pip takes twice
as long (360 frames / 6.00 s at SPD 4, still SPD-scaled). Damage,
visuals, and later tiers are unchanged. See
`2026-11-17-picsean-vortex-cooldown.md`.

