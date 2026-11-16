# Max-Will signatures for the other champions (Argon, proposal)

Date: 2026-11-15. Status: **proposal — for Carmelo's review, not
implemented.** Picsean's Tide Vortex is implemented (see
`2026-11-15-picsean-tide-vortex.md`). Wolfkin's Moonfang Rush (#63)
is unchanged and remains the bar.

These three arts replace the earlier Basalt Bastion / Night of Ravens /
Venom Bloom sketches. They come from Argon's review of `main @ 1c522cfc`
(`/workspace/quintra-argon/round4/maxwill.md`), fact-checked against
the live kit: A-button full-Will (`will_fire_max`) when
`player.will_level > 0`, B-button signatures unchanged, OBJ tiles
200..203 reused per cast (one champion per run), `PROJ_FLAG_CONVERGENCE`
plus a per-cast Colossus hit cap, and no blanket i-frames.

## Sauran: Thunderline Bastion (proposal)

Highly defensive. Current Thunderline is a fat spear plus parallel
side spears at higher tiers, which leaves slow-recovery Sauran exposed
and eats up to 7 entity slots. **Thunderline Bastion** keeps the
central piercing fault spear and replaces the broom of side spears
with two slow-marching monolith pylons that form a narrow corridor
ahead of him.

- **Hook.** New banked module (or a shared `will_max_fx.c`), from
  `will_fire_max` when the equipped weapon is Tail Spike, ticked from
  `combat_resolve`.
- **Pylons.** Two `PROJ_SPEAR`/`PROJ_SPIKE` bodies spawn 10px ahead
  and ±8px off the aim line, crawl at 1px/tick for `28 + level * 6`
  ticks (`34..52`, 0.56–0.86 s), hitbox `0xAA`. They crush hostile
  shots (not the Reaper's Mortal Scythe) in a 32×22px frontal corridor
  between Sauran and the pylons, and stall frontal bodies. Flanks and
  rear are open. Never writes `player.shield_timer` or `iframes`, so
  B's Stoneskin stays a personal bubble he can still pop if flanked.
- **Central fault.** Existing `max_spawn` spear, `damage + 4`, pierce
  `6 + level`, duration `54 + level * 8`. Pylons deal
  `damage + 2 + (level >> 1)`. At Will 3–4, expired or wall-stopped
  pylons leave a Blast Seed splash at their terminal tile.
- **Budget.** 3 entity slots + 1 short `ENT_FX` (down from 7 at Will
  4). OBJ 200..203: jagged amber obelisk (E/W) and a fault slab
  (N/S). Palette 2 flashes amber/granite for 18 ticks. Peak 3 OBJ
  on one scanline. `room_shake(2, 12)` on cast.
- **Colossus.** All three pieces carry `PROJ_FLAG_CONVERGENCE` and the
  pylons also carry `PROJ_FLAG_WILL_WAVE`, so a stationary boss takes
  one chord on contact, not a multi-tick shred.
- **Spawn failure.** If the central spear cannot spawn, `will_fire_max`
  returns 0 and keeps the Will charge. If a pylon fails, the corridor
  check still runs from the cast pose.

## Corvin: Murderstorm Eclipse (proposal)

Devastating single-target execution with a short evasive veil. Current
Murderstorm is a wider boomerang fan, which B (Raven Mark) was already
redesigned not to duplicate. **Murderstorm Eclipse** pays off the
mark: four diagonal blades sweep out, then cross-converge on the
marked body (or a point 44px ahead if nothing is marked).

- **Cast.** A 14-tick shadow decoy (`ENT_FX`, tile 202) stays at the
  departure tile. Hostile shots within 24px of that tile are erased.
  Corvin gets a 12-tick projectile slip-veil (`corvin_veil_ticks`);
  shots pass through him, but enemy body contact still hurts. No
  blanket i-frames.
- **Blades.** 4 `PROJ_SHURIKEN` on the diagonals (`dir+1,3,5,7`),
  `damage + 3` (tuning: `damage + 2` at the live `will_level` bonus,
  `hp = 4 + level`). Ticks 24..15: outward 2px/tick X-sweep. On tick
  14, all four re-aim at 3px/tick toward the focal point: the active
  `will_corvin_mark_slot` if `will_corvin_mark_ticks > 0`, else 44px
  ahead of the cast facing. If the marked body dies mid-flight, the
  blades keep the last known tile.
- **Mark payoff.** A blade that hits the marked body deals an extra
  +2 once per cast and refreshes the mark by +30 ticks instead of
  consuming it.
- **Tiers.** Will 2: veil 16 ticks. Will 3+: a 5th central piercing
  feather (`damage + 4`) down the aim line. Will 4: on the first
  convergence tick the blades pulse outward for 8 more ticks (a
  pinwheel).
- **Budget.** 4 blades + 1 decoy FX (5 at Will 3+), down from 8 at
  Will 4 today. OBJ 200..203: eclipse talon and a shadow plume.
  Palettes 1 and 2 flash indigo/bone for 16 ticks. Peak 2 OBJ per
  scanline, 4 only on the two convergence frames. Re-aim happens once,
  with `dir_toward`; no per-frame trig. Total window 28 ticks.
- **Colossus.** All blades carry `PROJ_FLAG_CONVERGENCE`, plus a
  per-cast 2-blade boss cap (`corvin_eclipse_boss_hits <= 2`, same
  idea as `WILL_HOWL_GIANT_HIT_CAP`). A marked Colossus takes a
  chunky 2-hit chord plus the mark bonus, never 5 simultaneous hits.

## Vespine: Queen's Royal Decree (proposal)

Aggressive parry-thrust plus a delayed venom burst. Current Queen's
Needle is a 3-shot trident with no poison interaction and no mobility.
**Queen's Royal Decree** is a 6-tick forward dart with a 7-tick
frontal wing-parry, a poison lance, and a Venom Sac that ruptures
about 14 ticks later.

- **Dart and parry.** `dash_timer = 6` (same collision-checked step
  Wolfkin uses, so she cannot tunnel into walls or vents she cannot
  pass). Any hostile shot in a forward 90° cone, reach 24px, is sliced
  into a 1-tick acid spark. Frontal body contact is parried for those
  7 ticks. Sides and back stay open; no blanket i-frames. At 6.5
  hearts she has to time the window.
- **Lance.** Central `PROJ_SPEAR` (`damage + 4`, pierce `5 + level`,
  36 ticks, hitbox `0xAA`) tagged so it applies Poison and trips
  `PERK_POISON_SYNERGY`, plus two inward pincer `PROJ_SPIKE`s
  (`damage + 2`) that converge 32px ahead rather than flying off at
  45°.
- **Venom Sac.** When the central lance hits a body, a wall, or tick
  18, it stops and becomes a pulsing sac (tiles 202/203, 14-tick
  countdown). On expiry it detonates with `projectile_spawn_splash`
  (`damage + 2 + level`). Will 2+: also 4 short diagonal spore
  needles (10 ticks, `damage + 1`). Will 3, if Swarm (B) is already
  running: +32 Swarm ticks and +1 Swarm damage. Will 4: a mini-splash
  at tick 7 of the sac, then the full rupture at tick 14.
- **Budget.** Staggered: 3 projectiles + 1 FX on the lunge, 1 sac
  while it pulses, then 1 splash (or 5 at Will 2+). Peak 5 slots,
  even with Swarm still firing its 16-frame stinger. OBJ 200..203:
  barbed stinger tip and the throbbing sac. Palettes 1 and 2 flash
  acid-green / royal-gold for 14 ticks. Peak 3 OBJ per scanline.
  Total lifecycle about 42 ticks.
- **Colossus.** The three lance pieces share `PROJ_FLAG_CONVERGENCE`
  (one chord on the thrust). The delayed sac splash is a separate
  event, and Will 2+ rupture needles also converge. A Colossus takes
  at most one impale chord plus one delayed rupture chord, plus
  poison ticks — not an instant delete despite `atk: 4`.

## What stays the same

- Wolfkin's Moonfang Rush is the reference and is not being revisited.
- Picsean's Tide Vortex is already shipped: a room-filling spiral from
  10px out to the farthest visible corner, hostile shots washed out,
  OBJ 200..203, heavy/Colossus caps, zero i-frames, anchored at the
  cast point. See that spec for what was kept vs. Argon's 84px
  4-satellite sketch (review name: Abyssal Maelstrom).
- These three arts should fire from each champion's starter weapon,
  matching Wolfkin, unless Carmelo answers open question 5 the other
  way.

## Open questions for Carmelo

1. **Shared bank-255 module vs. per-hero files.** Wolfkin's wave lives
   in `wolfkin_wave.c` (`#pragma bank 255`) and claims OBJ 200..203.
   Since `class_id` is fixed per run and those four tiles are reloaded
   on every cast, should all five MAX ticks/tiles live in one banked
   `will_max_fx.c` with a shared WRAM state struct, or stay as
   separate modules?
2. **Picsean vortex centre.** Implemented as **anchored at the cast
   point** (Argon's default, and the one that lets a fragile
   control-mage swim away). The other option is a following eye locked
   to `(player.x, player.y)`. Say if it should follow instead.
3. **Corvin unmarked fallback.** If Murderstorm Eclipse is fired with
   no active Raven Mark, the four blades converge 44px (~5.5 tiles)
   ahead of the cast facing. Prefer that, or should they auto-acquire
   the nearest on-screen enemy when one exists?
4. **Vespine dart direction.** Should the 6-frame Queen's Royal Decree
   dart always lunge forward (`+dir8_dx/dy`, a shorter, faster cousin
   of Wolfkin's rush), or should holding away on the D-pad during the
   A press do a wasp back-sting hop while the lance still fires
   forward?
5. **Non-starter weapons.** `will_fire_max` currently branches on
   `weapon_index == classes[i].starter_weapon`. Should these four
   bespoke MAX effects trigger only on each champion's starter
   (matching Wolfkin's `class_id == 0 && starter_weapon` check), or
   should the class half (Sauran's pylons, Corvin's veil, Picsean's
   vortex, Vespine's wing-parry) also ride on a mid-run weapon such as
   the Rift Flail or Astral Spear?
