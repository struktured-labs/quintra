# Max-Will charge levels

Date: 2026-11-21. Status: **draft, spec only** — no gameplay code in this
PR. Awaiting Carmelo's go-ahead on the remaining open questions before
implementation.

Source: Carmelo (t534u, t535u, t536u, t537u). Picsean's max-Will attack is
awesome and should not be touched except maybe its cooldown. It should
grow through multiple levels, unlocked by killing monsters or by firing
max Will at the current highest level. Will should keep charging **as
it does now, without holding**. The point system should be explained as
real play time. The levels mechanic is agreed; each hero still needs a
good and unique L4, with Tide Vortex as the bar.

This document extends `2026-11-17-max-will-v2.md`,
`2026-11-15-picsean-tide-vortex.md`, and
`2026-11-17-picsean-vortex-cooldown.md`. It does not replace them. The
shipped Tide Vortex, Thunderline Bastion, Royal Stinger, Murderstorm
Eclipse, and Moonfang Cross-Rend remain the **top-level (L4)** arts.

## 1. Goal

Each champion's starter MAX has four power levels. A new run starts at
L1. The cap rises as the hero fights. Whenever Will is banked, a tap of
A fires the **current unlocked level** — same input as today, no hold.
L4 is the current authored art, unchanged. L1–L3 are weaker, shorter,
cheaper versions of the same identity.

Unlock timing is the design target; XP is just the implementation of
that clock. On a typical Normal run (one hero, picked at the start):

| Milestone | What it means | Average time | Typical stage |
| --- | --- | --- | --- |
| L2 | first upgrade | about 10–15 minutes | late stage 1 / start of stage 2 |
| L3 | **halfway** up the ladder | about 30–45 minutes | stage 2–3 |
| L4 | maxed (current shipped art) | about 65–90 minutes | stage 4–5 |

L3 is the halfway point because you start at L1 and max at L4 (two of
the three upgrades). L2 is earlier on purpose, so the first dungeon
already teaches that the art grows.

This is an intentional early-game power shift: a fresh Picsean no longer
opens with a full-view Tide Vortex. The current vortex is the earned L4
spectacle. If that starting nerf is too sharp, see open question 1
(start at L2 instead).

## 2. How long this takes (the measurement)

Heroes are chosen per run, so these times are **per run of that hero**,
not a shared account grind (unless meta persistence is accepted; open
question 2). The same thresholds apply to every champion. Melee vs
ranged may drift by a few minutes, not a whole stage.

### 2.1 What the cartridge actually spawns

From `procgen.c` on Normal (the release target):

- Ordinary dungeon rooms: `11 + rng_range(5)` bodies (11–15, average
  13), plus +2 in stage 1 (opening pressure), +1 after the first
  Colossus, +2 from stage 4 on, and +1 on a large 31x31 court. Typical
  ordinary pack: **about 15 bodies** in stage 1, **14–15** later.
- Stage foyer (stage 2+ entry): **13–14** bodies, no elite.
- Puzzle roles (trial, waystone, deep switch, deep gate): **4**
  guards, or 5 from stage 4.
- Waypoint courts (locals 5 / 11 / 17 / 23): **3**.
- Shop, sanctuary, and town: **0**.
- Waking Riftwild: about one field in four is empty; the rest are a
  3–6 band (about **3.4** average including quiet fields). Hollow adds
  a denser 5–8 band.

Dungeon sizes (including boss) are 20, 21, 22, 23, 24, 25, 26, 28, 30
cells for stages 1–9. Counting those roles, a **critical-path** visit
(mission rooms, a couple of waypoints, foyer when it exists, boss —
not every cell) yields about **111, 119, 119, 143, 143** kills in
stages 1–5. A full clear of every cell is about **192, 184, 198, 228,
231**. Between dungeons, walking ~8 Waking fields adds ~25–30 kills
and a few minutes.

### 2.2 Headless sample

A controller-only PyBoy pilot (`run_pyboy_checkpoints.controller_action`,
no WRAM combat pokes) ran 4 minutes on Normal for each of the five
heroes, on the 2026-11-20 main ROM (`/tmp/q-main`). All five samples
were usable:

| Hero | Kills | MAX fires | Game time | Kills/min | MAX/min | Ended |
| --- | --- | --- | --- | --- | --- | --- |
| Wolfkin | 10 | 3 | 4:00 | 2.5 | 0.75 | time |
| Sauran | 2 | 0 | 4:00 | 0.5 | 0.00 | time |
| Corvin | 7 | 0 | 3:59 | 1.8 | 0.00 | time |
| Picsean | 11 | 1 | 4:00 | 2.8 | 0.25 | time |
| Vespine | 12 | 7 | 2:31 | 4.8 | 2.78 | death |

Average: **2.5 kills/min**, **0.8 MAX/min**. None of the five left the
opening room or recorded a room-clear. This is a **slow-play floor**
(the pilot chews a 15-body foyer inefficiently), not an average
human pace. It does confirm that the first room really is a mid-teen
pack and that MAX does get used in live play.

### 2.3 Average human pace used for the clock

A human who actually clears those packs spends about 45–75 seconds in
an ordinary room (15 bodies) plus travel, and longer in puzzle rooms
and boss fights. Using the critical-path kill counts and **15–20
minutes per early dungeon** plus about **5 minutes** of Riftwild
between stages gives a run-level average of about **6 kills per
minute** (including travel, puzzles, shops, and bosses — not just
in-combat bursts). That is the pacing number this spec uses.

A typical player also fires MAX about **once a minute** (often once
per combat room, not on the 6-second lock). The headless sample's 0.8
MAX/min sits next to that.

Cumulative time and kills for a typical (not full-clear) run:

| After | Time (est.) | Path kills + Riftwild |
| --- | --- | --- |
| Stage 1 | 15–20 min | ~110–130 |
| Stage 2 | 35–45 min | ~250–280 |
| Stage 3 | 55–65 min | ~390–430 |
| Stage 4 | 75–90 min | ~550–600 |
| Stage 5 | 95–115 min | ~720–780 |

## 3. Shared rules

### 3.1 Four levels, per hero

- Every starter MAX has levels **L1, L2, L3, L4**. The count is the
  same for all five champions (Wolfkin, Sauran, Corvin, Picsean,
  Vespine).
- L4 is the shipped art from max-Will v2 / Tide Vortex. Looks,
  hitboxes, damage bonuses, heavy cap, shot wash, voices, and
  lifetimes of L4 do not change in this work.
- L1–L3 are scaled-down versions of the same art (fewer arms or beats,
  shorter reach, lower bonuses, less or no shot wash). They reuse the
  existing controllers with parameters, not new hot-loop hooks or a
  second carrier type.
- Will-pip tiers (`player.will_level`, Waygear cap, `+1` damage and
  `+4` px reach per banked tier from v2) stay as a small rider on
  whatever art level is fired. They do not gate art level. **One
  banked pip is enough to fire the current cap**, including L4.
  Firing still spends every banked Will pip, as today.
- Only starter MAX arts are in scope. Rift Flail Worldwheel, Farstrike,
  and other pickup weapons stay one-shot dumps and still arm the flat
  360-frame recast lock.

### 3.2 Charging stays as it is today (no hold)

Will banks automatically while A is released — no hold-to-climb, no
Secret of Mana charge-up (t535u). A tap of A with `will_level >= 1`
and a clear recast lock fires the **current unlocked art level**
immediately and clears the gauge, exactly as today's MAX dump, except
the art you get depends on `maxwill_level`. The first-pip clock
itself gets slower as the cap rises; see §3.8. The recast lock in
§3.6 is a separate clock.

**Optional, not the default:** once L3 or L4 is unlocked, every dump
is the big art, with the long lock. A later option could let the
player pick a lower level (a Pack toggle, or a short hold that
*downgrades*) for a cheaper, shorter-lock shot in a tight room. Do
not add that unless the always-cap fire feels bad in play.

Wolfkin's held-A melee stream is unchanged when Will is empty or the
lock is held; when a MAX actually fires, the existing dash still plays
on L2–L4 (and the short L1 dash).

Charge arms only on a **fresh A-press edge**, as today (`pressed & J_A`
in `room.c`). Pickup weapons bypass this system and fire on press as
they do now.

### 3.3 Unlock: one XP pool, two sources, timed to the clock above

Progress is **per hero** (per `class_id`). A run only ever has one
champion, so this matters if meta progress carries between runs (open
question 2).

`maxwill_xp` is **intra-tier XP** toward the next cap, not a lifetime
total. Per-tier thresholds are **80 (L1→L2), 160 (L2→L3), 280
(L3→L4)** — cumulative 80 / 240 / 520 from a fresh L1 / 0. Leftover
XP stays in the byte on a cap-up. Starting a run already above L1
(if meta or a start-cap change is accepted) only needs the next
tier's threshold. At L4 the byte is cleared to 0 and further awards
are ignored.

Those numbers are the 6-kills-per-minute clock, with cap-casts as a
modest boost rather than the main driver:

| Source | XP | Why this size |
| --- | --- | --- |
| Ordinary hostile kill (same hook as `run_state_enemies_killed_total`, via `run_state_progress.c`) | +1 | One kill is one tick of the clock. |
| Elite / alpha / rare | +2 **instead of** +1 (do not stack) | A little more than a regular body. |
| Colossus, large boss, or Hexa | +8 **instead of** +1 (do not stack) | A real bonus, not a skipped tier. |
| Successful MAX at the **current cap** | +2, granted in `will_fire_max` on a committed cast, even if no body is hit | About one-third of a typical room, so regular MAX use is ~25% faster than kills alone, and cannot rush L4 in a few minutes of cooldown spam. |
| MAX fired below the cap | 0 use-XP | Only relevant if the optional lower-level fire is later added. Until then, every MAX is a cap-level fire and grants +2. |

How that lands for a typical player (~6 kills/min, ~1 MAX/min = about
8 XP/min) vs someone who almost never fires MAX (~6 XP/min):

| Reach | Intra-tier | Cumulative | Typical play | Kills only |
| --- | --- | --- | --- | --- |
| L2 | 80 | 80 | ~10–15 min, late stage 1 | ~13–15 min |
| L3 (halfway) | 160 | 240 | ~30–45 min, stage 2–3 | ~40–45 min |
| L4 (max) | 280 | 520 | ~65–90 min, stage 4–5 | ~85–90 min |

A full-clear completionist, who sees ~190 bodies in stage 1 alone,
reaches each cap about a stage earlier. A very slow run, closer to
the 2.5 kills/min headless floor, can take roughly twice as long;
the targets above are for ordinary human clearing, not that floor.

Thresholds are identical on Easy and Normal. Easy's existing +4 ATK /
+2 DEF already rides into MAX damage; do not further retune art
levels or XP per difficulty. There is no Hard mode.

On a cap-up, play `SFX_WILL`, flash the new pip, and keep leftover XP.

### 3.4 Save / Continue persistence

- **Required.** `maxwill_level` (1..4) and `maxwill_xp` (intra-tier)
  are appended to the suspend payload (`player_state_t` or
  `run_state_t`, two bytes) so a mid-run quit plus Continue restores
  the same cap and XP. Old saves missing the bytes migrate to L1 / 0
  XP, which is the length-prefixed SRAM contract already used in
  `sram.c`. A migrated or corrupt `maxwill_level` of 0 is clamped to
  1; values above 4 clamp to 4.
- Runtime-only state (the recast lock, the current Will bar) does not
  need new persistence beyond what already suspends.
- Death still wipes the run, including these two bytes, unless meta
  persistence is accepted (open question 2).
- If meta is accepted: SRAM bank 1 stores only the **2-bit cap** per
  hero (plus the usual magic / checksum), not leftover XP. A new run
  of that hero starts at the stored cap with XP 0. A fresh cart is L1
  for every hero. Meta is written only when a threshold is actually
  crossed, and must version cleanly without shifting existing meta
  offsets.

### 3.5 HUD pips

Keep the existing Will digit and 3-segment bank bar (resource). Add a
**4-pip** strip on the same Will window lane (window tiles, no extra
OAM):

- Locked: blank.
- Unlocked: filled, in the Will purple / lavender palette already
  used by `hud_redraw_action_charge`.

The pips show mastery (how far the art has grown), not a hold meter.
A first-time cap-up may use the existing HUD notice lane (short
`WILL LvN` or a pip flash); do not add a new window row. Confirm the
Will window lane has the tile columns and 2bpp VRAM for blank /
filled states. Pip tiles update only on a cap-up or Continue restore,
not every frame.

### 3.6 Recast lock (Picsean cooldown, and the shared MAX lock)

Every starter MAX already shares Tide Vortex's 360-frame recast lock
(`PICSEAN_VORTEX_RECAST_FRAMES`, `picsean_vortex_slow_charge` /
`ready_at`, checked at the top of `will_fire_max`). Keep that
mechanism. Scale only the duration by the **level just fired**:

| Level fired | Lock | Seconds |
| --- | --- | --- |
| L1 | 180 frames | 3.00 s (one first-pip at SPD 4) |
| L2 | 240 frames | 4.00 s |
| L3 | 300 frames | 5.00 s |
| L4 | **360 frames** | **6.00 s (current, default)** |

L4 stays at 360. The art itself is not retuned. An **optional** L4
lengthen to 420 frames (7.00 s) is on the table if the full vortex
still comes back too often once it is unlocked. Do not take 420
without Carmelo's go-ahead. The lock remains a fixed frame count, not
SPD-scaled, for the same reason as the 2026-11-17 cooldown spec.

During the lock, A is an ordinary shot and does not spend banked Will.

### 3.7 Banks, SRAM, and performance

- New controller (XP, cap-up, pip state): a new file such as
  `src/game/will_levels.c`, `#pragma bank 255` + `BANKED`. Bank 25
  (`enemy_new_ai.c`, about 2.4 KB free as of the 2026-11-18 basilisk
  spec) is the fallback if the file must sit in a fixed bank.
  Re-measure at implementation time.
- Bank 8 (`will.c`) is tight (~290 B). `will_fire_max` may take a
  short hook (read the fired level, arm a scaled lock, grant +2
  use-XP) but no new tables or level logic. Prefer a trampoline into
  the new file.
- Home bank: no new code. It ends at 0x3D04 and must stay there.
  File-scope variables in the new banked file stay **uninitialized**
  and are set from banked run-init; a non-zero C initializer would
  emit `GSINIT` bytes into the home bank, which has no headroom.
- Bank 30 (`will_maxfx.c`) and the Picsean vortex bank keep their
  controllers and gain a level parameter (arms, radius, beat count).
  Still one `PROJ_AUX_VORTEX` carrier, still the existing vortex
  dispatch (`picsean_vortex_ticks`, `room_draw_overlays`,
  `picsean_vortex_abort`). No new `combat_tick` hook: v2 already
  showed that an extra branch can cost the Serpent fight a logic
  frame.
- WRAM: a handful of `u8`s (cap, XP). SRAM: two appended suspend
  bytes, plus optional meta cap bits.
- Performance floor: `scripts/test_performance.py` must stay at
  **167/180** fixed-roster and 135/180 dense. L1–L3 must be cheaper
  than L4 (fewer OAM, shorter lifetime). L4 cost stays exactly
  today's vortex / maxfx cost.

### 3.8 Charge time scales with the unlocked level

Carmelo (t537u): charging should be slower at higher unlocked levels;
proportional is a candidate. This scales the **first-pip Will bank**
(`will_charge_tick`), not the recast lock in §3.6. The two clocks run
together; the next MAX is ready when both have elapsed.

Today, at the SPD 4 baseline (Sauran, Corvin, Picsean), the first pip
takes exactly **180 frames (3.00 s)**: `will_charge_fraction` gains
`(16 + SPD)` per frame, spends 40 to add one point, and the first pip
needs `WILL_MAX` (90) points. Wolfkin (SPD 5) is 172 frames (2.87 s).
Vespine (SPD 6) is 164 frames (2.73 s). Speed Ring and Swift Fang
still add to the per-frame gain. The 360-frame (6.00 s) recast lock,
not this 3.00 s pip, is what currently stops a Tide Vortex from
coming back sooner.

**L4 is calibrated to that 180-frame / 3.00 s SPD 4 first pip**, so a
maxed hero does not charge faster than today. Lower caps charge
faster. Times below are SPD 4; SPD 5/6 stay proportionally quicker
(about 0.96× / 0.91×).

| Cap | Proportional (n × L1) | **Gentler (default)** 1 / 1.5 / 2 / 2.5 | Recast lock | Felt cycle (max of charge, lock) |
| --- | --- | --- | --- | --- |
| L1 | 45 f / 0.75 s | 72 f / **1.20 s** | 3.00 s | 3.00 s either way |
| L2 | 90 f / 1.50 s | 108 f / **1.80 s** | 4.00 s | 4.00 s either way |
| L3 | 135 f / 2.25 s | 144 f / **2.40 s** | 5.00 s | 5.00 s either way |
| L4 | 180 f / 3.00 s | 180 f / **3.00 s** | 6.00 s | 6.00 s (same as today) |

Proportional is the clean n× rule Carmelo asked about. After a fire,
though, the lock — not the bar — is the felt recast gate at every
level, so a 0.75 s L1 bar would slam full and then sit unusable for
the rest of the 3.00 s lock (worse on Vespine / Speed Ring, down to
about 0.6 s). Carbon recommended going straight to the **gentler**
ramp: L1 is still 2.5× faster than today, the HUD can be read, and
L4 still matches the current 3.00 s pip. That is the default.

Implementation (not in the Aftershock code PR): keep the 90-point pip
target fixed and look up a 4-byte spend threshold that ends at 40
(16 / 24 / 32 / 40). Do not multiply 90 or 40 by the cap — that would
make L4 *slower* than today (up to 12 s) and 90 is not divisible by 4.
The charge tick must **drain the fraction accumulator repeatedly in
one frame** whenever `(16 + SPD)` exceeds the spend (true for every
hero at L1, and for SPD 5+ at proportional L2). Clamp pip points at
90; do not test equality, because one frame can add more than one
point. On a mid-pip cap-up the 90-point bar does not jump backward
(only the remaining points slow down). Put the table in `will_levels.c`
(bank 255), not bank 8. While the recast lock still holds, the Will
HUD must look dimmed / locked so a full bar is not mistaken for a
dropped input.

A short Carbon pass (2026-11-21, $0.07; running total $7.14 logged)
caught the spend-math trap, the single-subtract overflow, the locked
HUD cue, and the mid-pip jump. Folded in above.

## 4. Per-hero level sketches

Damage numbers below are the art bonuses on top of the usual
`weapon + ATK + (will_level - 1)` rider. Heavy bodies keep the listed
per-hit cap. Lifetimes are combat ticks.

### Picsean — Tide Vortex (class 3, BubbleBolt)

L4 is the **top-level reference**. Do not change its look, growth,
front/arm bonuses, heavy cap, shot wash, crest sound, or 84-tick
lifetime.

| Lv | Name | Shape | Max R | Ticks (grow) | Bonuses | Wash | Heavy cap |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Tide Pulse | 1 crest around Picsean | 48 px | 24 (18) | front +1 | no | 3 |
| L2 | Tide Ring | 2 arms | 96 px | 36 (28) | front +2 | no | 4 |
| L3 | Tide Coil | 3 arms | 160 px | 56 (44) | front +3, arm +1 | no | 5 |
| L4 | Tide Vortex | 4 arms, full view (current) | 240 px | 84 (72) | front +4, arm +2 | yes | 6 |

### Sauran — Thunderline Bastion / Aftershock (class 1, Tail Spike)

The shipped Bastion (max-Will v2) becomes **L3**. L4 adds a lateral
aftershock; see §8. This is an upgrade of the shipped art, not a
replacement.

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Short fault crack, no pylons | 18 | spear travels 6 ticks, MAX+1, no slam |
| L2 | Fault spear only (no pylons, no slam) | 28 | spear as current, MAX+2 |
| L3 | Shipped Bastion: spear, two pylons, 24 px slam | 52 | MAX+4 spear, MAX+2 slam (unchanged v2) |
| L4 | Bastion + lateral T-fault aftershock | 64 | after the slam, a perpendicular ground wall ±36–40 px off the pylons, MAX+1 once on bodies the slam missed; pylons keep eating shots until they sink. Not a forward chevron (the slam already reaches ~64 px ahead). |

### Vespine — Royal Stinger / Brood Rupture (class 4, Stinger)

The shipped Stinger + Sac (max-Will v2) becomes **L3**, except L3
already ruptures (the current 28 px burst and visual-only droplets).
L4 makes those droplets real; see §8.

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Short poison dart, no lodge, no pincers | 18 | MAX+1, poison, no sac |
| L2 | Flying stinger lodges, no sac, no pincers | 28 | MAX+2, poison |
| L3 | Shipped Royal Stinger + Venom Sac rupture, +45 Swarm ticks | 54 | MAX+4 lodge / burst (unchanged v2); droplets stay visual |
| L4 | Brood Rupture: sac burst plus four damaging droplet pops | 54 | droplets at fixed ±24 px X/Y (~34 px diagonal) from the rupture, each a 16 px MAX+1 pop with poison / Swarm refresh, no extra shot wash. A miss already plants a ground sac and ruptures (keep that full burst); L4 still adds the ring. Stagger the four hit-checks over two frames. |

### Corvin — Murderstorm Eclipse + Night Veil (class 2, Featherbarb)

**Keep** the shipped Eclipse as L4. No chain, no flock. Modest L4
presence only; see §8.

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Two shadow feathers, no veil, no eclipse | 20 | MAX+1, no Effigy |
| L2 | Four feathers fan, no eclipse slam, no Effigy | 28 | MAX+2 |
| L3 | Room dim + four feathers + smaller eclipse (14 px), Effigy until f24 | 40 | MAX+3 feathers, MAX+4 eclipse; no Mark extension |
| L4 | Shipped Eclipse + Night Veil, plus a readability pass | 48 | mechanics unchanged (mark seek already ships). L4 eclipse floor 20→26 px before the Will-pip bonus; a tall shadow pillar / 4-way corona at the snap point using L4 OAM 24–31 (dropped during Serpent). Effigy stays until f48. |

### Wolfkin — Moonfang Cross-Rend (class 0, Fang Forms)

**Keep** the shipped Cross-Rend as L4. Do not grow a half-room
crescent. Modest L4 presence only; see §8.

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Short guarded dash, single claw lane, no crescent | 16 | MAX+1, frontal guard for the short dash only |
| L2 | Moonfang Rush only (dash, three lanes, Will wave); no beat two | 24 | current beat one, no Cross-Rend |
| L3 | Rush + weaker shear (14 px, no eclipse flash) | 34 | shear MAX+0 |
| L4 | Shipped Rush + Cross-Rend, larger X and lingering scars | 42 | shear 20→32 px, 3-tick local shake / hit-stop on connect, scars linger through f42 on L4 OAM 24–35 (32×32 X at the 44 px apex). Mechanics and two-beat timing stay. |

## 5. Test plan

New headless PyBoy script `scripts/test_will_max_levels.py`, plus
fixture updates so existing `test_will_max`, `test_will_max_v2`,
`test_will_tiers`, `test_wolfkin_will_wave`, `test_picsean_tide_vortex`,
and `test_will_sfx` keep passing.

The new script must show:

1. **Unlock by kills.** A L1 / 0 hero who records 80 ordinary kill
   credits (the same hook as `run_state_enemies_killed_total`) reaches
   L2 with leftover 0. A further 160 ordinary kills reach L3; 280 more
   reach L4 (520 cumulative from L1 / 0). Below-threshold kills do
   not bump the cap. Elite credit is +2 and boss credit is +8, each
   replacing the ordinary +1, not stacking with it.
2. **Unlock by cap-level use.** Forty successful cap-level MAX casts
   from L1 / 0 XP reach L2 (80 XP) if awarded at +2 each, granted on
   a committed `will_fire_max` even if no body is hit. Mix: 60
   ordinary kills + 10 cap-casts reach L2.
3. **Level select is automatic.** With cap L2 and Will banked, a
   single A press (no hold) fires L2. After a cap-up to L3, the next
   successful MAX is L3. The hero cannot fire above the cap, and
   (unless the optional lower-level fire is added) cannot fire below
   it either.
4. **Persistence.** Suspend mid-run at L3 / leftover XP, cold Continue
   (the `test_suspend.py` / `test_difficulty_persist.py` battery
   pattern) restores the same cap and XP. A pre-feature save migrates
   to L1 / 0, and a stored level of 0 is clamped to 1. If meta is
   accepted, a second new run of the same hero starts at the stored
   cap with XP 0; a different hero starts at L1; death does not wipe
   meta.
5. **Picsean L4 identity.** Once the cap is L4, telemetry matches the
   current Tide Vortex (84 ticks, grow 72, max radius 240, front +4 /
   arm +2, heavy cap 6, shot wash, crest voice, 360±3 frame lock at
   SPD 4). L1–L3 match the radius / arm / wash / lock table. A during
   the lock is an ordinary BubbleBolt and does not spend Will.
6. **Difficulty and performance.** Unlock thresholds are the same on
   Easy and Normal. `test_performance.py` stays at 167/180
   fixed-roster and 135/180 dense. No new `combat_tick` hook.

Existing `test_will_max`, `test_will_max_v2`, `test_will_tiers`,
`test_wolfkin_will_wave`, `test_picsean_tide_vortex`, and
`test_will_sfx` seed `maxwill_level` to L4 in setup so L4 regression
coverage stays intact (a tap, not a hold, fires the shipped art).

## 6. Open questions for Carmelo

1. **Starting cap.** This draft starts every new run at L1, so early
   Picsean is weaker than the shipped vortex until L4 (stage 4–5 on a
   typical run). Alternative: start at L2 so the first rooms already
   have a respectable ring, and only L3–L4 are earned. L4 itself
   stays the current art either way.
2. **Meta vs run-only.** Continue/suspend persistence is required.
   Should caps also live in SRAM bank 1 as per-hero knowledge that
   survives death, or does a new run always start at L1 (or L2, per
   question 1)? Full L4 meta carry would retire the unlock loop after
   one deep run per hero; if knowledge-carry is wanted, consider
   capping the head-start at L2.
3. **Optional L4 lock.** Default keeps the current 360-frame (6.00 s)
   lock for L4. Lengthen to 420 (7.00 s) only if you want the full
   vortex to come back slower once it is unlocked.

The previous hold-to-climb question is **resolved**: no hold, tap
fires the current cap, same as today's charge.

## 7. Carbon review and t535u follow-up

A short Carbon pass on the first draft (2026-11-21) was **ship with
nits**. The nits that still apply are folded in: intra-tier XP,
exclusive elite/boss credit, use-XP on a committed cast, GSINIT /
home-bank safety, pickup-weapon bypass, and seeding existing tests at
L4. Hold-to-climb nits are dropped because Carmelo wants charging to
stay as it is now.

## 8. L4 audit (t536u): good and unique vs Tide Vortex

Carmelo (t536u): the levels mechanic is reasonable; now make sure each
hero actually has a good and unique max-Will attack. This section
audits the **shipped** max-Will v2 arts (merged after the 2026-11-17
walkthrough Page and Carbon's picks). It does **not** re-propose
Thunderline Bastion, Royal Stinger and Venom Sac, Murderstorm Eclipse,
or Moonfang Cross-Rend — those already replaced the old stock spear,
trident, boomerang fan, and 14-frame rush.

The verb identities are already distinct. The remaining gap is
**presence and pack coverage**, not a missing hook. Picsean's Tide
Vortex uses 12 OAM (slots 24–35) and fills the view for 84 ticks
(1.40 s), 12 damage on every body, and a room-wide shot wash. The
other four use 4 OAM (32–35) and resolve in 42–54 ticks, with 20–28 px
payoffs, so a spread pack does not feel a MAX the way the vortex does.
Lane test bands at Will 1, LCK 0, from `test_will_max_v2.py`: Wolfkin
18–34 (keeps ~29), Sauran 14–24, Corvin 12–22 unmarked (≥15 marked),
Vespine 16–26 plus poison. Tide Vortex is 12 / 11 on every body in
the room.

Shared tropes to keep honest: every hero has some shot-eat beat and a
palette wash; several have a delayed second beat (Sauran slam f44,
Vespine rupture f45, Corvin snap f40, Wolfkin shear f34). Upgrades
must stay architecturally different, and **only Picsean** may wash
shots across the whole view.

### Verdict per hero

**Picsean — KEEP.** Tide Vortex is the gold standard. No change to
look, growth, damage, wash, crest audio, or lifetime. The only open
tune is the optional 360 vs 420 frame lock already in §3.6. The
compile-flag swirl art stays off unless Carmelo asks. No new art
required, and none should be generated in this pass.

**Sauran — UPGRADE L4 to Thunderline Aftershock.** The shipped Bastion
is a good lightning/stone gate (fault spear, two shot-eating pylons,
24 px slam) and becomes L3. It is still the most lane-locked MAX: the
slam around the far pylon already reaches about 64 px *ahead*, so a
forward chevron would re-sweep dead space and miss the real hole —
packs walking *around* the corridor. L4 keeps the shipped Bastion
beats, then at about f48–64 a **perpendicular ground fault** branches
left and right from the two pylons (±36–40 px off-axis, about 16 px
deep), one MAX+1 hit on bodies the slam missed. Pylons keep eating
shots until they sink; the aftershock itself does **not** eat shots.
About 64 ticks, still under 84. This is a wall across the lane, not a
radial swirl and not Howl rings. Evaluate the fault as one wide AABB
on a single tick (a `missed_slam` mask), not per-sprite collision.

**Vespine — UPGRADE L4 to Brood Rupture.** The shipped Stinger + Sac
is a good wasp identity (lodge, poison, pincers, delayed 28 px
rupture, Swarm feed) and becomes L3. The four diagonal acid droplets
already draw at f45–54 and deal no damage — that is the hook. L4
makes them a cluster ring at fixed ±24 px X/Y (~34 px diagonal) from
the rupture: each pop is 16 px, MAX+1 once, applies poison and
refreshes Swarm ticks, and does **not** wash shots. Stagger the four
hit-checks across two frames (NE/SW, then NW/SE) for perf and for a
readable pop-pop. A miss already plants a ground sac and ruptures at
that tile in the shipped art; keep that full burst and still add the
ring (do not halve a planted miss). Still a planted burst, not a room
vortex.

**Corvin — KEEP the shipped Eclipse, with an L4 readability pass.**
Night Veil already owns the room's mood; unmarked casts already seek
the nearest body ahead within 96 px. No second-target chain and no
flock (both rejected on the walkthrough for uniqueness / OAM). L4
only: eclipse floor 20→26 px before the Will-pip bonus, so a tight
cluster catches the edge, and a tall shadow pillar / 4-way corona at
the snap point on OAM 24–31 (omitted during Serpent). The Effigy stays
visible until f48. Only the Effigy eats shots, not the flash.

**Wolfkin — KEEP the shipped Cross-Rend, with an L4 readability pass.**
The two-beat melee hook was already the best close-range feel; do not
grow a half-room crescent (that turns him into a wave mage and copies
the vortex). L4 only: shear 20→32 px, 3 ticks of local shake /
hit-stop on connect, scars linger through f42. With L4 OAM 24–35, six
scar sprites can hold the dash lane while a 4-sprite 32×32 X flashes
at the 44 px apex (fallback to 32–35 during Serpent). Timing stays 42
ticks.

### Shared L4 budget, art, and perf

- **OAM.** L4 for all four non-Picsean heroes may use Picsean's window
  (24–35), falling back to 32–35 while the Serpent owns 4–31. This is
  allowed because only one champion is in a run. Slots 24–31 are
  **cosmetic amplifiers only**; hit detection stays on the single
  `PROJ_AUX_VORTEX` carrier's timer and anchors, so a Serpent fight
  can drop 24–31 without changing damage.
- **Tiles.** OBJ 200–203 remain the only FX VRAM. GPT Image 2 cels
  (gpt-image-2.6-sunburst), quantized to GBC, should be authored for
  X/Y flip symmetry so two 8×8 tiles can build a 16×16 or hollow
  32×32 shape, and/or DMA-swapped at beat boundaries (Vespine stinger
  / sac for f0–44, rupture / droplet at f45). Current FX is four hand
  8×8 tiles per hero; new GPT art is wanted for Sauran aftershock /
  pylons, Vespine sac / droplets, Corvin feathers / corona, and
  Wolfkin scars / X. Picsean needs no new art. **Do not generate
  images in this spec pass.**
- **Banks / perf.** Aftershock and Brood Rupture logic stay in bank 30
  (`will_maxfx.c`) or a bank-255 helper; no new `combat_tick` hook, no
  home-bank growth, bank 8 only the existing thin hook. Heavy caps
  stay. `test_performance.py` must remain 167/180 fixed-roster and
  135/180 dense. Sauran L4 (two live pylons, one AABB aftershock, 12
  OAM) is the heaviest non-Picsean tick and is the first
  implementation on purpose, so it proves the shared L4 OAM allocator
  and the perf floor before Vespine / Corvin / Wolfkin reuse it.

### Build first

**Sauran Aftershock first**, then Vespine Brood Rupture (the droplets
already exist visually), then Corvin and Wolfkin readability in one
polish pass. Carbon agreed: Aftershock also forces the shared L4 OAM
24–35 allocator and is the worst-case perf test.

### Carbon review (2026-11-21, second pass)

Short Carbon pass on this audit: the diagnosis (presence, not
identity) and the keep / upgrade split are right. Folded in above:
Sauran's fault must go *lateral*, not forward; Vespine's ring is
fixed-offset and does not wash shots, and a miss already plants a
sac; Corvin and Wolfkin keep their mechanics but get the same L4 12-
OAM window plus a small radius / shear bump; 24–31 is cosmetic during
Serpent; droplet hit-checks are staggered; GPT cels use flip symmetry
or beat-swapped tiles. Carbon call $0.06; running total $7.07 logged.

No images, no deploy, and no implementation until the open questions
in §6 are settled and Carmelo gives an explicit go-ahead on scope.
