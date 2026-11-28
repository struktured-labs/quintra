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
`weapon + ATK + (will_level - 1)` rider, except Picsean (and any other
art that must hit a 25–35% L1 target) which also scales the **whole
pre-LCK hit** — see §4.1. Heavy bodies keep the listed per-hit cap.
Lifetimes are combat ticks.

t554u: L2 and L3 sit evenly between L1 and L4 in size, range, and
power (no back-loaded jump at the cap). t557u: Picsean L1 must feel
clearly modest in the pocket, because the shipped vortex is already
the full L4 and is too strong at the start of a run.

### Picsean — Tide Vortex (class 3, BubbleBolt)

L4 is the **top-level reference**. Do not change its look, growth,
front/arm bonuses, heavy cap, shot wash, crest sound, or 84-tick
lifetime. The current cartridge art **is** L4; L1–L3 are smaller
editions of that same vortex, not a new spell.

**L1 damage is 30% of L4 pre-LCK front/arm** (mid of the 25–35%
band), then 53 / 77 / 100. Damage is a percent of the unchanged L4
formula (`MAX + 4` / `MAX + 2`), not only of the bonus: scaling only
the +4 would leave L1 around half of L4 once weapon + ATK are
included, which is not modest.

Reach is **viewport-scaled**, not 30% of the L4 overscan radius.
`MAX_R = 240` is a corner-to-corner overscan (screen diagonal ≈ 215);
30% of 240 is 72 px, a 144 px diameter that already covers ~70% of a
160×144 view from mid-room, and L2 at 128 px would fill the screen,
leaving L2–L4 indistinguishable except on corner casts. Carbon
(2026-11-21, spell-levels pass) required pulling L1–L3 down: **48 /
112 / 176 / 240** (+64 px a level). L1 (48 px, 96 px diameter) covers
about **31% of the 160×144 screen** from mid-room, inside the 25–35%
effective-area target. L2 just reaches corners from center, L3 clears
off-center casts, L4 stays the shipped full view.

On GBC, implement L1–L3 damage with `/256` fixed-point, not `/100`:
multipliers **77 / 136 / 197** via `(raw * mul + 128) >> 8`, minimum
1. **L4 bypasses the scale completely** (no multiply) so the shipped
hit is bit-identical. At very low MAX, L1 front and arm may round to
the same integer; that is acceptable.

| Lv | Name | Shape | Max R | Ticks (grow) | Damage vs L4 | Wash | Heavy cap | OAM |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Tide Pulse | 1 crest around Picsean | **48 px** | 24 (18) | **30%** of L4 front/arm, min 1 | no | 2 | 4 cels in 32–35 |
| L2 | Tide Ring | 2 arms | **112 px** | 44 (36) | **53%** | no | 3 | 6 cels |
| L3 | Tide Coil | 3 arms | **176 px** | 64 (54) | **77%** | no | 5 | 8 cels |
| L4 | Tide Vortex | 4 arms, full view (current) | **240 px** | 84 (72) | 100% (front +4, arm +2, unchanged) | yes | 6 | 12 cels in 24–35 (current) |

Implementation must keep the L4 path bitwise in feel: same ease table
endpoint, same wash, same crest. L1–L3 cap `picsean_vortex_radius` at
the level's max R, use fewer arms/cels, skip the shot wash, and apply
the damage percent before LCK/weakness. Recast lock and first-pip
charge still follow §3.6 and §3.8 (L1 72 f / 1.20 s charge, 180 f /
3.00 s lock; L4 180 f / 3.00 s charge, 360 f / 6.00 s lock).

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

Other heroes keep the L1–L4 mechanical sketches below, but size,
range, and pre-LCK damage should also sit evenly between that hero's
L1 and L4 (~30% of that L4 at L1, then 53 / 77 / 100). Do not leave
a large jump only at the cap. Shipped v2 arts stay the listed L3 or
L4 anchors (Bastion = Sauran L3, Aftershock = Sauran L4, Stinger =
Vespine L3, Eclipse and Cross-Rend = L4).

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

1. **Starting cap.** This draft starts every new run at L1. t557u:
   early Picsean must be clearly modest (~30% of the shipped vortex),
   so do **not** start at L2 by default. Alternative, only if L1 feels
   too small in play: start at L2 (53% reach). L4 itself stays the
   current art either way.
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

## 9. Spell levels (t553u / t554u): same Will cap, linear size and range

Carmelo (t553u): magic spells must also use the Will charge + level
system. Per level, the spell animation gets larger / fancier and the
attack range and area widen. t554u: mid levels are roughly linear —
L2 and L3 sit evenly between L1 and L4 in size, range, and power.

This section is **spec only** (the first code PR implements MAX
levels, Picsean first). It does not change the 2026-11-17 elemental
magic input contract.

### 9.1 Shared cap, current kit is L1

Spells share `maxwill_level` (the same 1–4 cap, the same XP pool in
§3.3, the same HUD pips in §3.5). There is **no second grind**. **No magic cast** awards cap-cast XP: not a 1 MP tap, not a 2 MP
ward, and not Cure. Only a committed MAX at the current cap does
(plus kills, as already specified). Otherwise Moonfire or safe-room
wards would replace combat as the unlock clock. Kills scored *by* a
spell still award normal kill XP under §3.3. If the cap goes up
mid-ward, snapshot ward charges at cast; orbit radius may follow the
live cap.

The **shipped spells are L1**, not L4. Higher levels widen and
embellish them. This is the opposite of Tide Vortex, whose shipped
art is L4 and whose early levels shrink it. Do not nerf today's taps
or wards at run start.

### 9.2 Charge times: MAX table stays on MAX

Tap B / hold B / A+B-wins stay exactly as shipped (`MAGIC_HOLD_FRAMES`
24, MP costs 1 / 2 / Cure 5, per-class tap cooldowns 36 / 45 / 30 /
30 / 40). A 1.20–3.00 s Will-style windup on every Moonfire would
fight the 24-frame ward hold and the Carbon-balanced "no spell beats
A's sustained DPS" rule.

The §3.8 first-pip table and the §3.6 recast lock apply to **MAX
arts**. They do not gate spell taps. If a later charged-spell
(a hold-to-empower that is not the ward) is added, it must use the
same gentler 72 / 108 / 144 / 180 frame spend table and must not
collide with the ward hold.

### 9.3 Linear multipliers

From the shipped L1 values:

| Cap | Range / area | Damage (pre-LCK base) | Animation |
| --- | --- | --- | --- |
| L1 | 1.00× (current) | 1.00× (current) | current cels |
| L2 | **1.25×** | **1.15×** | trail / extra mote |
| L3 | **1.50×** | **1.30×** | larger flash or one extra cel |
| L4 | **1.75×** | **1.45×** | fullest ring / column / trail |

Damage steps stay shallower than range so A still wins sustained DPS
at L4. Round to the nearest integer, minimum 1. Status durations may
follow the range row when they are a reach (STOP/POISON windows,
ward radius) and the damage row when they are a hit weight.

**§9.4's explicit byte tables are authoritative** over the 1.25 /
1.50 / 1.75× heuristic above. Some ramps (Blizzard/Moonfire TTL,
Stoneskin and Veil i-frames, Blizzard STOP) are intentionally
shallower than a raw multiply.

### 9.4 Per-spell L1–L4 (from the shipped 2026-11-17 kit)

Numbers in the L1 column are what `magic.c` does today. L2–L4 are
the linear steps above.

**Wolfkin — Moonfire** (1 MP, 36 f). Homing fire orb.

| Lv | Home range | Burst r | Base / burst dmg | TTL | Tell |
| --- | --- | --- | --- | --- | --- |
| L1 | 96 px | 14 px | 4 / 3 | 80 | one orb, 14 px flash |
| L2 | 120 | 18 | 5 / 3 | 90 | mote trail |
| L3 | 144 | 21 | 5 / 4 | 100 | larger flash |
| L4 | 168 | 25 | 6 / 4 | 110 | two-cel burst + extra wisps |

**Flame Ward** (2 MP). Three wisps. L1 orbit 20 px, 2 charges each,
up to 180 f. L2 orbit 25, L3 orbit 30 and 3 charges, L4 orbit 35 and
3 charges. Same 24 f sear cadence; no new entity slots.

**Sauran — Thunder** (1 MP, 45 f). Aim half-plane, then a column.

| Lv | Aim range | Floor ahead | Chain r | Floor splash | Base dmg | Tell |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | 104 px | 40 px | 48 px | 10 px | 5 | 6 f column |
| L2 | 130 | 50 | 60 | 13 | 6 | taller bolt |
| L3 | 156 | 60 | 72 | 15 | 7 | bolt + flash |
| L4 | 182 | 70 | 84 | 18 | 7 | full column + shake already shipped |

**Stoneskin + Static** (2 MP). L1: shield 90 f, pulse r 28, pulse 2.
L2: 105 f / 35 px / 2. L3: 120 f / 42 px / 3. L4: 135 f / 49 px / 3.

**Corvin — Hex** (1 MP, 30 f). Orb at 2 px/f.

| Lv | Travel | Burst r | Base dmg | TTL | Tell |
| --- | --- | --- | --- | --- | --- |
| L1 | 64 px | 18 px | 3 | 32 | one orb, 18 px burst |
| L2 | 80 | 23 | 3 | 40 | extra burst cels |
| L3 | 96 | 27 | 4 | 48 | wider ring |
| L4 | 112 | 32 | 4 | 56 | fullest hex ring |

**Shadow Veil** (2 MP). L1: HASTE / i-frames 20, eat r 20. L2: 24 / 25.
L3: 28 / 30. L4: 32 / 35.

**Picsean — Blizzard** (1 MP, 30 f). Steerable icicle, up to 2 hits.

| Lv | TTL (range @ 3 px/f) | Hits | Base dmg | STOP | Tell |
| --- | --- | --- | --- | --- | --- |
| L1 | 70 f (~210 px) | 2 | 3 | 12 | one icicle, occasional mote |
| L2 | 80 | 2 | 3 | 14 | denser flake trail |
| L3 | 90 | 3 | 4 | 16 | wider icicle |
| L4 | 100 | 3 | 4 | 18 | two-cel shaft + trail |

Steer rate stays one dir8 step per 4 frames. TTL is already long at
L1; L4 is a longer, fancier shaft, not a new screen-filler.

**Per-target rehit lockout:** L3–L4 may hit 3 bodies, but one steered
icicle must not land all three hits (and 54 frames of STOP) on a
single boss every 30 f. Keep a per-target mask for the icicle, same
idea as Bramble's `br_mask`. Distinct targets only.

**Cure** (5 MP, once per room). Keep the once-per-room and "refuse if
it would do nothing" rules (including when HP is already at max and
there is no status to cleanse). Heal clamps at `max_hp`. Do not turn
Cure into a second max-heal.

| Lv | Heal | i-frames | Tell (reuse tiles 160–175) |
| --- | --- | --- | --- |
| L1 | +2 HP | 20 f | current chime + cure cel |
| L2 | +2 HP | 24 f | extra rising motes (L2 must be visible; +4 f of i-frames alone is not) |
| L3 | +3 HP | 24 f | wider cure ring |
| L4 | +3 HP | 30 f | full sparkle column |

**Vespine — Bramble** (1 MP, 40 f). Four eruptions, 12 px each.
The existing per-cast `br_mask` stays: each body is hit at most
once even when L4's 21 px splashes overlap on a large hitbox. The
5th eruption at L3–L4 is the same single cursor (`br_step` 0..N-1),
not a wider WRAM array. Solid tiles still **stop the chain** as they
do today (a 128 px vine will usually hit a wall first). Recast is
already refused while `br_t` is live; that stays, so the stagger
cannot overlap a second vine.

| Lv | Eruptions (px along aim) | Splash r | Base dmg | Tell |
| --- | --- | --- | --- | --- |
| L1 | 16 / 30 / 44 / 58 | 12 | 3 | four thorn pairs |
| L2 | 20 / 38 / 56 / 74 | 15 | 3 | slightly longer vine |
| L3 | 24 / 45 / 66 / 87 / 108 (five) | 18 | 4 | one extra eruption |
| L4 | 28 / 53 / 78 / 103 / 128 (five) | 21 | 4 | fullest vine + extra thorn cels |

**Thorn Mirror** (2 MP). Reflect radius L1 14, L2 18, L3 21, L4 25.
No second reflector entity; the sparkle can travel farther.

### 9.5 GBC budget

All of this is table-driven in bank 31 (`magic.c` already lives
there). Four-byte (or 5×4) range / damage / radius tables, looked up
by a **clamped** `maxwill_level` (init/load clamp 1..4 so
`maxwill_level - 1` never underflows to 255). No new WRAM if existing
shot / ward / bramble state just reads a wider radius or a higher
step count on the same cursor. L2–L3 reuse the 16 shipped magic OBJ
tiles (160–175); L4 may add motes from that same set, not a new
sheet. Do not add a second entity walk.

Magic's OAM stays in its existing slot range; L4 trails multiplex or
alternate frames rather than allocating new slots. Do not align five
horizontal Bramble thorn pairs (10 sprites) on one scanline without
stagger or flicker — the 10-sprite/line cap is already tight when a
ward, a MAX art, and the hero share the line. `will_levels.c` is
`#pragma bank 255`; confirm on the link map that it never packs into
bank 8 and that the home bank still ends at 0x3D04.
`test_performance` floors (167 fixed-roster, 135 dense) stay hard
gates.

### 9.6 Tests (when this ships)

Extend `scripts/test_magic.py` (or a sibling) so each class at L1
matches today's numbers, and at L4 the range / area / damage match
the L4 column, with L2 / L3 on the even steps. Existing magic tests
seed `maxwill_level = 1` so the shipped kit stays the baseline.
Existing Tide Vortex and perf tests must seed `maxwill_level = 4`
once run-start defaults to L1, so L4 regression coverage is not
silently lost.

**First code PR (Picsean MAX levels only):** wire §3.6 / §3.8 charge
and recast clocks **per class**. Until Wolfkin, Sauran, Corvin, and
Vespine have their own L1–L3 MAX scaling, pin those four classes to
the L4 clocks (180 f charge / 360 f lock) so they cannot fire today's
full arts twice as often at run start. HUD pips may light while
spell scaling is still deferred; that is acceptable if QA knows.

## 10. Spirit Convergence takes the equipped element (t563u / t564u)

Carmelo: the A+B attack should take on the equipped elemental magic
in spirit and visually — one shared effect per element, colorized
through OBJ palettes (fire red/orange, ice pale blue, lightning
yellow, and the other class colors), with element behavior (burn
trail, shatter shards, chain), scaling with the Will levels, and a
stated GBC palette / OAM budget.

This section is **spec only**.

### 10.1 What A+B does today (narrow read, main)

The chord in `room.c` is two different verbs on one input:

- **A+B at full MP, `active_charge == 0`: Spirit Convergence.** Shared
  across all five champions. Spawns an eight-way `PROJ_SPIKE` burst
  at `weapon.p1 + ATK + 2`, tagged `PROJ_FLAG_CONVERGENCE` (Colossus
  chord cap). Empties MP, sets `mp_regen = 0`, 45 i-frames,
  `active_charge = 180`, and `room_transform_ticks = 135` (counts
  down every 8 frames, about 18 s at 60 Hz). The hero locks to
  `SPR_CLASS_ASCENDED_BASE` (per-class 16×16 ascended tiles, 102–121,
  with a two-tile walk cycle on the feet). Shake + `SFX_ROAR`. Mute
  seals the chord.
- **A+B below full MP:** the selected Oath Art (`oath_arts_fire`,
  1 MP, 96 f cooldown). Shard Wake is known from run start; further
  arts unlock per Colossus. Those arts already have their own
  elements (Wake is crystal-cold, Cinderstep is fire, and so on).
  This section does **not** retune the Oath ladder.

Convergence already writes `g_shot_element` from the class element
(`fire 1 / lightning 4 / shadow 8 / ice 2 / poison 16`) so weakness
math applies. Visually the burst is still a generic steel spike
(`SPR_FX_SWING` / blade pal). The ascended body keeps the ordinary
class OBJ palette (`prop = 0x01`); it does not read as a fire, ice,
or lightning super. That is the gap.

"Equipped elemental magic" here is the champion's class element (the
same element as their B spells). There is no mid-run element swap.

### 10.2 One shared skeleton, five colorways

Keep the shipped skeleton: full-MP chord, eight-way burst,
convergence cap, MP dump, 45 i-frames, 180 f charge lock, 18 s
ascended pose, per-class crown tiles. Do not invent five unique A+B
ultras.

Color and residue ride on that skeleton:

| Class | Element | OBJ pal (reuse magic slots) | Color | Behavior |
| --- | --- | --- | --- | --- |
| Wolfkin | Fire (1) | 4, red / gold | red-orange | Burst cels leave a short **burn trail** (motes on the 8 lanes). Direct hit guaranteed BURN. Trail may ignite trees / cracked walls per ordinary fire tile rules. |
| Sauran | Lightning (4) | 5, amber / pale yellow | yellow | After the burst lands, **one chain** to the nearest other body in range (half damage + SLOW), same idea as Thunder's follow-up, one hop only. |
| Corvin | Shadow (8) | **slot 4 or 5**, violet (never pal 1) | violet-black | Burst cels are a darker slash; struck bodies get a short CONFUSION (heavies MUTE), no second orb. |
| Picsean | Ice (2) | **slot 4 or 5**, pale blue (never pal 1) | pale blue | On death or wall, a spike may shatter into shards (see cap below). Direct hit guaranteed STOP. May bridge spike beds per ice tile rules. |
| Vespine | Poison (16) | 7, acid green / amber | green | Burst leaves a brief poison mote at each lane; direct hit guaranteed POISON. No lingering puddle entity. |

Palette loads reuse the **already-shipped magic element palettes** in
`magic.c` (`class_pal[]`, VRAM bank 1). Do not add an 8th unique OBJ
palette or steal the hero body slot (pal 1) for the whole 18 s
ascended walk — the champion must stay readable as themselves. The
ascended body is `prop = 0x01`, so pal 1 is **unconditionally busy**.
Corvin (shadow) and Picsean (ice) therefore **always** load their
burst colorway into slot **4 or 5** (whichever is freer; if both are
in use by enemies, borrow slot 4 and accept a brief enemy FX tint)
for the life of the burst / shards, then restore the room's prior
palette when the last cel clears. Tint the burst cels and residual
motes only. A one-frame elemental flash on the ascended sprite at
the dump is allowed; a full-duration body recolor is not.

**Fire and poison lane motes are purely visual** (0 damage, no
per-frame AABB). Tree ignition, cracked walls, and ice bridging are
triggered by the **moving spike's** tile-probe as it travels, not by
lingering ground entities. Stagger those tile probes across even/odd
frames (or cap conversions per frame) so eight L3–L4 lanes cannot
mutate a whole ring of tiles in one tick.

**Ice shards:** do not spawn 8×2 = 16 live projectiles. Cap total
live shards at **4** (L2) / **8** (L4), prefer cardinal or
alternating lanes, and skip a shatter if the pool is full. **Sauran
chains once per cast**, not once per landed spike. Ice shards and
the lightning chain **inherit `PROJ_FLAG_CONVERGENCE`** so a
point-blank wall shatter or chain hop cannot bypass the Colossus
chord cap. Shards must not spawn with out-of-bounds `x/y`.

### 10.3 Linear Will-level scaling

Shipped Convergence is **L1 of this chord**, not a nerf of the
current dump. Higher `maxwill_level` widens and embellishes it, with
even mid steps, using the same shallow damage ramp as §9.3 (range /
presence 1.00 / 1.25 / 1.50 / 1.75×, damage 1.00 / 1.15 / 1.30 /
1.45×). L4 must not become a second Tide Vortex.

Reach and damage use `/256` fixed-point, not floats. Reach
multipliers **256 / 320 / 384 / 448** (1.00–1.75×) scale spike
**lifetime frames**, not velocity, so faster shots cannot tunnel
thin walls. Damage multipliers **256 / 294 / 333 / 371**
(1.00–1.45×) via `(raw * mul + 128) >> 8`. L1 bypasses the scale so
today's `p1 + ATK + 2` is bit-identical.

| Lv | Reach | Damage vs L1 | Per-class residue / tell |
| --- | --- | --- | --- |
| L1 | 256 (current lifetime) | 256, exact `p1 + ATK + 2` | element pal on the 8 spikes only; weakness already applies; no extra cels, no new CC |
| L2 | 320 | 294 | **Fire:** short visual burn motes. **Lightning:** spark flash, no chain hop. **Shadow:** brief dark slash trail, no CONFUSION/MUTE. **Ice:** up to 4 shards (cap), no STOP on the shards themselves. **Poison:** 2-frame visual puff, no POISON status. |
| L3 | 384 | 333 | Fuller trail; guaranteed status and tile rules as in §10.2 (BURN / one chain / CONFUSION or MUTE / STOP + shatter / POISON). |
| L4 | 448 | 371 | Fullest trail + chain / shatter / extra motes; still 8 lanes; still one Colossus chord; shard cap 8. |

The 18 s ascended duration, 45 i-frames, MP dump, and 180 f
`active_charge` stay **constant across levels** — this is a full
meter spend either way. Do not award cap-cast XP for Convergence (it
is a magic-meter dump, not a MAX).

### 10.4 GBC palette and OAM budget

- **OBJ palettes:** 8 slots, already busy (hero, enemies, items,
  bullets). Convergence must not allocate a new slot. Use the magic
  element pal already loaded for B spells in VRAM bank 1. Fire uses
  slot 4, lightning slot 5, poison slot 7. **Shadow and ice always
  use slot 4 or 5** (never pal 1; see §10.2) and restore the prior
  palette when the last cel clears.
- **Tiles:** prefer recoloring existing spike / magic tiles
  (160–175 and the swing/spike set). New shard / spark tiles only if
  a recolor is unreadable; if so, GPT Image 2 (`gpt-image-2.6-sunburst`)
  only, quantized into the same 16-tile magic sheet, no raw 1024s in
  the repo.
- **OAM:** the 8 burst lanes already exist. Residues (burn motes,
  shards, chain bolt, poison motes) multiplex inside the existing
  magic / FX slot range — at most **4 extra cels** at L4, alternating
  if a ward or MAX is also live. No 10-sprite line of horizontal
  residues. Hits stay on the spike / shard AABB, not on a dropped
  cosmetic.
- **Banks / perf:** no new home-bank code (stay at 0x3D04). Pin any
  new Convergence tables in **bank 31** (`magic.c`), not in
  autobank 255, so they cannot pack into bank 8. The 18 s pose
  already runs; do not add a per-frame entity walk.
  `test_performance` floors 167 / 135 stay hard gates. Seed
  Convergence tests at L1 for the shipped burst and at L4 for the
  elemental residue.

### 10.5 What not to change

Oath Arts, the full-MP requirement, Mute sealing the chord, the
Colossus convergence cap, pickup-weapon bypass, and A+B-wins over a
B-hold stay as they are. Tide Vortex L4 is unchanged. Spell tap/hold
input is unchanged.


### Carbon review (2026-11-21, spell-levels pass)

Verdict: **ship with nits** ($0.1261; running logged total $8.3402).
Folded above: viewport-scaled Picsean radii 48 / 112 / 176 / 240;
`/256` damage; Blizzard per-target lockout; Bramble single cursor +
existing `br_mask` + wall stop; Cure visible L2 tell; no magic-cast
XP; §9.4 tables authoritative; OAM / bank-8 / underflow clamps;
first code PR pins unscaled classes to L4 clocks and seeds existing
vortex tests at L4. A+B elemental Convergence (§10) had its own Carbon pass
(2026-11-21, $0.0247; running logged total $8.3649): **ship with
nits**, folded above (unconditional pal 4/5 for Corvin/Picsean,
shard/chain caps + convergence inheritance, cosmetic motes, `/256`
lifetime scaling, explicit L2 tells, tables pinned to bank 31).

