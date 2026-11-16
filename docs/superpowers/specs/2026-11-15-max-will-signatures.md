# Max-Will signatures: one overhaul per champion

Date: 2026-11-15. Status: **spec only.** Only Picsean's Tide Vortex is
implemented (`2026-11-15-picsean-tide-vortex.md`). Nothing else here is
built yet.

## Why
Carmelo (2026-11-15): "the special per char needs to be more awesome.
Wolfkin is cool now ... think powerful for each char, or highly defensive."
The full-Will A MAX is the one moment a champion is supposed to feel
outsized. Today Sauran, Corvin and Vespine's MAX arts are wider or longer
versions of their primary, so they read as a bigger bullet. Each overhaul
below is either devastating or a fortress, and no two are alike.

The roster is in `content/` (5 classes): Wolfkin, Sauran, Corvin, Picsean,
Vespine.

| Champion | Today (A MAX) | Overhaul | Role |
|---|---|---|---|
| Wolfkin | Moonfang Rush + Will wave (#63) | **unchanged**, it is the bar | frontal ram + guard |
| Picsean | ~~Moon Tide~~ | **Tide Vortex** (built) | room-wide sweep |
| Sauran | Thunderline lance | **Basalt Bastion** | highly defensive |
| Corvin | Murderstorm fan | **Night of Ravens** | devastating, single-target pressure on every foe |
| Vespine | Queen's Needle | **Venom Bloom** | devastating, chain reaction |

## Shared rules (every overhaul)
- **Trigger.** The class starter weapon's A MAX with full Will, at any tier.
  The Will tier adds to damage exactly as today (`damage += level - 1`).
  B powers, Oaths, ordinary A, the dodge dash, and the alternate weapons'
  MAX arts (Worldwheel, Farstrike, generic three-lane) stay unchanged.
- **Damage path.** All damage goes through `combat_apply_player_shot_hit`
  (a projectile or the vortex-style inert carrier), so weakness, LCK,
  status riders, the Colossus stage cap (3, easy 5), Hexa and return-echo
  filters, boss links and kill rewards apply unchanged.
- **Heavy bodies** (Colossi and Sentinels, Stage Reaper, elites, alphas,
  rares, Bellwardens, the large-boss anchor, Hexa) take at most 6 per hit
  before LCK and weakness, plus the per-move hit limit below. No signature
  may delete a Colossus phase.
- **Mortal Scythe** is never blocked, reflected or washed out.
- **Art budget.** OBJ tiles 200..203 are the per-run signature cels: one
  champion per run, and each art reloads its cels on cast. Moves needing
  more reuse existing projectile tiles. OAM for transient art is 24..35
  (12, multiplexed by alternating frames). It drops to 32..35 while the
  Serpent owns 4..31, and Hexa keeps 4..23. 36..39 stay with the raft and
  the boss overlay.
- **CPU.** No division or 32-bit math per entity per tick. Every move must
  pass the crowded fixture with no fewer logic updates than idle play
  (`scripts/test_picsean_tide_vortex.py` shows the method), and
  `check_rom_layout.py` must pass. Each lives in its own `#pragma bank 255`
  file like `wolfkin_wave.c` and `picsean_vortex.c`.
- **Room exit** cancels any lingering signature on `entity_init_room`.
- Each ships with its own spec, headless test and GIF before merge.

## Sauran: Basalt Bastion (highly defensive)
Sauran plants the tail spike, and eight basalt scales rise and orbit him as
a living wall.
- **Mechanics.** 8 scale pieces orbit at 18px radius (one full turn a
  second) for 240 ticks (4 s). A hostile shot touching a scale is
  **reflected**: its velocity is reversed, it becomes player-owned, and it
  keeps its damage +1. A body touching a scale takes MAX damage +2
  (once per 30 ticks per body) and is shoved out with poise respected.
  Each scale holds 3 blocks, then cracks and falls. Sauran is rooted (no
  walk or dodge) for the first 30 ticks while the wall rises, then moves at
  half speed. Pressing A again, or the timer ending, **detonates** the
  surviving scales outward as 8 piercing basalt lanes (MAX damage +3 each,
  pierce 3).
- **What it isn't.** It is not Stoneskin (B), which is a short timed full
  shield. Bastion leaves gaps between scales: a shot threading a gap still
  hits. No blanket i-frames.
- **Animation.** 2 cels (scale, cracked scale) plus 1 shard cel in
  200..202. On the rise, the BG floor palette darkens to basalt for 8
  frames, there is a 2px shake, and the ROAR plays. Reflected shots flash
  the foam-white of OBJ palette 2.
- **Budget.** 8 OBJ (12 slots allow it without multiplexing). Per tick that
  is 8 sine lookups and an 8-box test per hostile shot or body within 26px
  (a cheap Manhattan pre-check). Shots far from him cost one compare.
- **Fairness.** Reflected shots against heavy bodies count toward the
  per-hit cap of 6 and at most 6 reflected hits per cast. Body contact still
  hurts through the gaps. Rooted start: committing in the wrong place is a
  real risk.
- **Duration.** 4 s of wall plus the detonation. This is the longest-lived
  signature, offset by being mostly defensive.

## Corvin: Night of Ravens (devastating)
The room goes dark, and every foe gets a raven.
- **Mechanics.** On cast, every awake enemy on screen is **marked** (up to
  12, nearest first). Over 120 ticks (2 s) ravens dive from the screen edge
  nearest each mark in three waves (ticks 20, 60, 100). Each dive is one
  hit of MAX damage +2. A marked enemy that falls below 25% of its spawn HP
  is **executed** by the next dive. Corvin's own primary shots against a
  marked foe get the existing Raven Mark bonus for the duration. Hostile
  shots are not touched, so this is pure offense.
- **Animation.** BG palettes dim to a night ramp for the whole 2 s (the
  same halving used by pause and blind), and the ravens and marks stay
  bright. The 2 cels in 200..201 are a raven with folded and open wings.
  Marks reuse the existing impact FX in purple. A screech plays on each
  wave.
- **Budget.** At most 12 ravens in flight per wave, drawn in OAM 24..35 and
  multiplexed when a wave overlaps the next. Ravens are not entities, just a
  table of 12 positions lerped edge-to-target with shift math, so the
  entity pool is untouched. One damage apply per raven arrival.
- **Fairness.** Heavy bodies get one raven per wave (3 total), capped at 6,
  and are never executed. The darkness never hides hostile shots: they keep
  their own bright palettes. If no enemy is on screen, the cast still
  spends Will but only plays the screech (same as the corvin-mark miss today).
- **Duration.** 2 s.

## Vespine: Venom Bloom (devastating, chain reaction)
Vespine's needle plants a pheromone seed, and the room blooms with poison.
- **Mechanics.** The needle flies along the aim and stops at the first body,
  wall, or 56px. After a 30-tick (0.5 s) visible fuse, a **venom bloom**
  expands from the seed to a 48px radius over 24 ticks. Every enemy inside
  takes MAX damage +3 once and is **Poisoned** (the existing status) and
  **Slowed** for 180 ticks. Any enemy that dies while poisoned by the
  bloom **bursts** into a 24px secondary bloom (MAX damage +1, applies
  poison), so a packed room chains. Hostile shots inside the main bloom
  dissolve.
- **What it isn't.** It is not the Tide Vortex, which centres on the hero
  and spans the room. The bloom is placed, local, and pays off on clustering
  and kills.
- **Animation.** 3 cels in 200..202: a seed, a petal and a spore puff. The
  bloom ring is 12 petals in OAM 24..35 on a growing circle, using the same
  sine table as the vortex. Secondary bursts use 4 petals each,
  multiplexed. OBJ palette 2 turns venom green and magenta. There is a short
  BG floor tint at bloom (5 frames) and a 1px shake.
- **Budget.** At most 3 live blooms at once (main plus 2 secondaries); a
  further burst queues until a slot frees. One distance per body per live
  bloom per tick.
- **Fairness.** The chain depth is capped at 4 bursts per cast. Heavy bodies
  take one bloom hit (capped at 6) and poison at the normal heavy duration,
  and they never burst. The fuse is visible, so a fast enemy can walk out.
- **Duration.** 0.5 s fuse, 0.4 s bloom, and poison lasting 3 s.

## Wolfkin: Moonfang Rush (unchanged)
It stays exactly as in `2026-11-12-wolfkin-will-wave.md`: three claw lanes,
a three-piece crescent wave and the frontal guard for the length of the
dash. It is the reference for how big a signature should feel.

## Open questions for Carmelo
1. Should Bastion's reflected shots also damage heavy bodies, or only the
   crowd?
2. Should Night of Ravens executions drop extra coins, so it is a "farm" MAX?
3. Should Venom Bloom's chain be allowed to cross into the next wave of a
   Warden court?
