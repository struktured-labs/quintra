# Combat variety and guarded treasure — requested 2026-09-19

Implemented locally; do not deploy or interrupt the player's active Rivalmage run.

## Current implementation and qualification

- Spinners pause for a tell, cast eight slow shots in rotating directions, then
  resume their orbit. These are coarse eight-direction spirals, not smooth
  arbitrary-angle bullet curves.
- Sweeping blue crawlers plant their feet, lock their aim and fire five sequential
  fan lanes. Existing cardinal/diagonal viral rings remain separate patterns.
- Return champions cycle through 24x24 Reaper, Weaver and Maw silhouettes.
  Weaver orbits and casts; Maw telegraphs a committed charge with side shots and
  a recovery window. Entrance armor and one bounded escort wave remain intact.
- New pattern emissions stop at 12 hostile projectiles or four remaining free
  entity slots. This is not a global cap on legacy attacks.
- The mapped Farfold Cache now requires clearing its guards, tops its roster up
  toward four enemies where safe placement permits, and displays WARDED on entry.
  Its persistent relic changes palette when available. Claiming it gives the
  two-second overhead pose followed by its actual name and effects. Timed secret
  rooms are unchanged.
- Fixed reward-topic clamping that otherwise mislabeled item IDs above 12.

Native PyBoy checks cover spiral/fan timing, locked aim, movement phases, guarded
claim, persistence, celebration, Normal/Easy armor and escorts, menu restoration,
automatic traversal, all five heroes' Will tiers, and save compatibility. Asset
generator tests pass. The dense performance fixture recorded 135 updates in 180
video frames (generated room 175; fixed roster 172); slowdown is still possible.
OAM rotates under load; art checks sample a complete rotation rather than assuming
each arbitrary video frame contains a completed game-loop render.

Candidate ROM SHA-256:
`f7f51118ebc0bd341d7762fc440fc3d4edccef88476e8f908707103bbbab9ef3`.
Raw pattern traces: `/tmp/quintra-enemy-patterns.json`; known-broken parent trace:
`/tmp/quintra-patterns-before.json`. Fresh generated treasure fixture:
`scripts/test_farfold_cache.py`; native card: `/tmp/quintra-treasure-claim.png`.

Hardware balance, every-seed guard placement, and full runs with each hero remain
unqualified. No reload, upload, or deployment was performed.

## Design targets

## Projectile patterns

- Spiral emitter: slow rotating streams, a visible windup, a finite firing window,
  and a recovery window. Rotation direction stays fixed for the cast.
- Sweeping fan: aim once during the tell, then sweep across predictable lanes;
  no mid-flight player tracking.
- Alternating rings: cardinal/diagonal or offset rings with an obvious escape gap.
- Consider fractional velocity for smoother angles rather than simply increasing
  integer bullet speed. Bound concurrent projectiles to preserve entity slots,
  visible OAM, and cartridge frame pacing.

## Enemy movement

- Orbit-and-cast for spiral emitters, stopping during their warning.
- Telegraph, commit to a straight dash, then recover for chargers.
- Distinct weave/strafe cycles for ranged enemies; collision-checked movement must
  not strand them in pillars or inaccessible pockets.

## Miniboss variety

- Larger, authored silhouettes rather than just enlarging collision boxes.
- At least three distinguishable encounters: spiral/orbit caster, charging
  bruiser, and summoner with bounded escorts.
- Preserve readable name cards, music changes, arrival protection, and punishable
  recovery. Avoid merely increasing HP or filling the screen continuously.

## Map-marked treasure

The dungeon chest icon marks `run_state_dungeon_cache_cell()`. Its reward is
`PICKUP_FARFOLD_RELIC`, authored at (216, 208) and safety-adjusted onto floor.
Its effects now apply only after all guards are defeated.

- Require a strong guardian or a deliberate guard pack before claiming the relic.
- Make the locked/guarded state visible; do not present an unexplained uncollectable pickup.
- After victory, show the actual relic overhead for about two seconds, play the
  reward phrase, and display its name and effect. Persist the claim once.
- Distinguish this mapped combat reward from timed hidden secret rooms; do not
  silently replace the existing secret-room timer mechanic.

## Acceptance

Fresh short replays must measure windups, shot trajectories, gaps, finite burst
counts, movement cycles, walls, and entity pressure. Capture native-size examples.
Verify treasure cannot be stolen, becomes claimable after the guards die, survives
menu/suspend boundaries, and produces one celebration without duplicating the reward.
Test all five heroes and slow heroes specifically. Hardware remains unqualified
until the current run ends and the user authorizes deployment.
