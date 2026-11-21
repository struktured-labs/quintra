# Max-Will charge levels (Secret of Mana style)

Date: 2026-11-21. Status: **draft, spec only** — no gameplay code in this
PR. Awaiting Carmelo's go-ahead on the open questions before
implementation.

Source: Carmelo (t534u): Picsean's max-Will attack is awesome and should
not be touched except maybe its cooldown; it is the perfect case for
multiple Secret of Mana-style charge levels, "not just one level and it
maxes out." Levels unlock by killing monsters, or by firing max Will at
the current highest level.

This document extends `2026-11-17-max-will-v2.md`,
`2026-11-15-picsean-tide-vortex.md`, and
`2026-11-17-picsean-vortex-cooldown.md`. It does not replace them. The
shipped Tide Vortex, Thunderline Bastion, Royal Stinger, Murderstorm
Eclipse, and Moonfang Cross-Rend remain the **top-level (L4)** arts.

## 1. Goal

Each champion's starter MAX is a four-level charge art, not a single
dump. Holding A after Will is banked climbs Secret of Mana-style tiers
up to the hero's unlocked cap. Releasing fires that level. L4 is the
current authored art, unchanged. L1–L3 are weaker, shorter, cheaper
versions of the same identity. The cap starts at L1 on a new run and
rises through a single XP pool fed by kills and by cap-level casts.

This is an intentional early-game power shift: a fresh Picsean no longer
opens with a full-view Tide Vortex. L2 arrives in the first few rooms so
the hold is taught quickly; the current vortex is the earned L4
spectacle. If that starting nerf is too sharp, see open question 1.

## 2. Shared rules

### 2.1 Four levels, per hero

- Every starter MAX has levels **L1, L2, L3, L4**. The count is the same
  for all five champions (Wolfkin, Sauran, Corvin, Picsean, Vespine).
- L4 is the shipped art from max-Will v2 / Tide Vortex. Looks, hitboxes,
  damage bonuses, heavy cap, shot wash, voices, and lifetimes of L4 do
  not change in this work.
- L1–L3 are scaled-down versions of the same art (fewer arms or beats,
  shorter reach, lower bonuses, less or no shot wash). They reuse the
  existing controllers with parameters, not new hot-loop hooks or a
  second carrier type.
- Will-pip tiers (`player.will_level`, Waygear cap, `+1` damage and
  `+4` px reach per banked tier from v2) stay as a small rider on
  whatever art level is fired. They do not gate art level. **One banked
  pip is enough to fire any unlocked level**, including L4. Firing still
  spends every banked Will pip, as today.
- Only starter MAX arts are in scope. Rift Flail Worldwheel, Farstrike,
  and other pickup weapons stay one-shot dumps.

### 2.2 Hold to charge, release to fire (SoM)

Today a tap of A with `player.will_level >= 1` immediately fires the
full MAX and clears the gauge (`room.c`). After this change:

- Charge may begin only on a **fresh A-press edge**, and only when Will
  is banked (`will_level >= 1`), the hero is not Muted, B is not held,
  dialog is not winning, and the shared recast lock is clear. A mid-
  hold that later becomes legal (Will banks from a pickup, a lock
  expires, Mute ends) does not arm; the player must release and press
  again. After a cancel, A still held does not re-arm.
- Pickup weapons (Rift Flail Worldwheel, Farstrike, and other non-
  starter MAX arts) **bypass** the hold-charge state machine: A fires
  immediately on press as today, and a successful dump arms the flat
  360-frame recast lock regardless of `maxwill_level`.
- A legal A-press starts a short **arm** of 12 frames. Releasing during
  frames 1–11, or at frame 12, fires **L1**. The arm withholds charge
  SFX and HUD pip-fill so a panic tap does not flash a climb. L2
  becomes available at frame 57, L3 at 102, L4 at 147 (12 + 45 × n).
- Each further unlocked level takes **45 frames** (0.75 s) of
  continuous hold. The cadence is fixed, not SPD-scaled, so Speed Ring
  and Swift Fang cannot collapse a L4 hold. Time to L4 when all four
  are unlocked: 147 frames (~2.45 s).
- The hold cannot pass the hero's unlocked cap. Past the cap the last
  pip pulses; release still fires the cap.
- Movement is allowed while charging so the hero is not a sitting duck.
  The charge **cancels** (Will stays banked, nothing is fired) on: a
  hit, pressing B, a successful A+B chord, a room transition or
  stairs, Mute being applied mid-hold, or dialog / cutscene takeover.
- While a charge is live, ordinary A shots (and Wolfkin's held-A melee
  stream) are suppressed. When `will_level` is 0, or the recast lock is
  held, A is unchanged from today (ordinary shot / Fang combo; the lock
  still refuses MAX and does not spend Will).
- `will_charge_tick` still runs only while A is released and no shield
  is up, as today. Holding to climb art levels therefore pauses Will
  banking, which is the existing contract.

### 2.3 Unlock: one XP pool, two sources

Progress is **per hero** (per `class_id`), not shared across champions.
A run only ever has one champion, so this matters if meta progress
carries between runs (open question 2).

Both sources feed the same `maxwill_xp` byte. That byte is **intra-tier
XP** toward the next cap, not a lifetime total. Per-tier thresholds are
20 (L1→L2), 36 (L2→L3), and 64 (L3→L4), which is 20 / 56 / 120
cumulative from a fresh L1 / 0. On a cap-up, leftover XP stays in the
byte (`24` from three +8 cap-casts becomes L2 / 4). Starting a run
already above L1 (if meta or a start-cap change is accepted) only needs
the next tier's threshold, never 120 from zero. At L4 the byte is
cleared to 0 and further awards are ignored.

| Source | XP |
| --- | --- |
| Ordinary hostile kill (the same hook as `run_state_enemies_killed_total`, via `run_state_progress.c`) | +1 |
| Elite / alpha / rare | +2 **instead of** +1 (do not stack) |
| Colossus, large boss, or Hexa | +8 **instead of** +1 (do not stack) |
| Successful MAX fired at the **current unlocked cap** | +8, granted in `will_fire_max` on a committed cast, whether or not a body is hit |
| MAX fired below the cap | 0 use-XP (kills during that room still count) |

| Reach | Intra-tier XP | Cumulative from L1 / 0 | Kills only (approx.) | Cap-casts only |
| --- | --- | --- | --- | --- |
| L2 | 20 | 20 | first few rooms | 3 casts |
| L3 | 36 | 56 | late first dungeon | 7 casts |
| L4 | 64 | 120 | around the second Colossus | 15 casts |

A mix gets there faster: a first-dungeon clear plus a handful of cap
casts should unlock L3 before the second stage, and L4 early in the
second dungeon. Thresholds are identical on Easy and Normal. Easy's
existing +4 ATK / +2 DEF already rides into MAX damage; do not further
retune art levels or XP per difficulty. There is no Hard mode.

On a cap-up, play `SFX_WILL`, flash the new pip, and keep leftover XP.

### 2.4 Save / Continue persistence

- **Required.** `maxwill_level` (1..4) and `maxwill_xp` (intra-tier)
  are appended to the suspend payload (`player_state_t` or
  `run_state_t`, two bytes) so a mid-run quit plus Continue restores
  the same cap and XP. Old saves missing the bytes migrate to L1 / 0
  XP, which is the length-prefixed SRAM contract already used in
  `sram.c`. A migrated or corrupt `maxwill_level` of 0 is clamped to
  1; values above 4 clamp to 4.
- Charge-hold ticks are runtime only; they do not persist.
- Death still wipes the run, including these two bytes, unless meta
  persistence is accepted (open question 2).
- If meta is accepted: SRAM bank 1 stores only the **2-bit cap** per
  hero (plus the usual magic / checksum), not leftover XP. A new run
  of that hero starts at the stored cap with XP 0. A fresh cart is L1
  for every hero. Meta is written only when a threshold is actually
  crossed, and must version cleanly without shifting existing meta
  offsets.

### 2.5 HUD pips

Keep the existing Will digit and 3-segment bank bar (resource). Add a
**4-pip** strip on the same Will window lane (window tiles, no extra
OAM):

- Locked: blank.
- Unlocked and not charged: hollow.
- Charged on this hold: filled, in the Will purple / lavender palette
  already used by `hud_redraw_action_charge`.
- The cap pip pulses when the hold is sitting on the cap.

When not holding, the four pips still show the unlocked cap (hollow)
so the player can see mastery at a glance. A first-time cap-up may
use the existing HUD notice lane (short `WILL LvN` or a pip flash);
do not add a new window row. Confirm the Will window lane has the
tile columns and 2bpp VRAM for blank / hollow / filled / pulse
states. Pip tiles update only on a charge-step, cap pulse, cancel,
or cap-up — not every frame of a hold.

### 2.6 Recast lock (Picsean cooldown, and the shared MAX lock)

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
lengthen to 420 frames (7.00 s) is on the table if, once L1–L3 exist
as the frequent buttons, the full vortex still comes back too often.
Do not take 420 without Carmelo's go-ahead. The lock remains a fixed
frame count, not SPD-scaled, for the same reason as the 2026-11-17
cooldown spec.

During the lock, A is an ordinary shot and does not spend banked Will.

### 2.7 Banks, SRAM, and performance

- New controller (hold cadence, XP, cap-up, pip state): a new file
  such as `src/game/will_levels.c`, `#pragma bank 255` + `BANKED`.
  Bank 25 (`enemy_new_ai.c`, about 2.4 KB free as of the 2026-11-18
  basilisk spec) is the fallback if the file must sit in a fixed
  bank. Re-measure at implementation time.
- Bank 8 (`will.c`) is tight (~290 B). `will_fire_max` may take a
  short hook (read the fired level, arm a scaled lock) but no new
  tables or level logic. Prefer a trampoline into the new file.
- Home bank: no new code. It ends at 0x3D04 and must stay there.
- Bank 30 (`will_maxfx.c`) and the Picsean vortex bank keep their
  controllers and gain a level parameter (arms, radius, beat count).
  Still one `PROJ_AUX_VORTEX` carrier, still the existing vortex
  dispatch (`picsean_vortex_ticks`, `room_draw_overlays`,
  `picsean_vortex_abort`). No new `combat_tick` hook: v2 already
  showed that an extra branch can cost the Serpent fight a logic
  frame.
- WRAM: a handful of `u8`s (hold ticks, current charge level, cap,
  XP). File-scope variables in the new banked file stay
  **uninitialized** and are set from banked run-init; a non-zero C
  initializer would emit `GSINIT` bytes into the home bank, which
  has no headroom. SRAM: two appended suspend bytes, plus optional
  meta cap bits.
- Performance floor: `scripts/test_performance.py` must stay at
  **167/180** fixed-roster and 135/180 dense. The hold tick rides the
  existing room A-hold path, not the crowded combat loop. L1–L3 must
  be cheaper than L4 (fewer OAM, shorter lifetime). L4 cost stays
  exactly today's vortex / maxfx cost.

## 3. Per-hero level sketches

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

### Sauran — Thunderline Bastion (class 1, Tail Spike)

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Short fault crack, no pylons | 18 | spear travels 6 ticks, MAX+1, no slam |
| L2 | Fault spear only (no pylons, no slam) | 28 | spear as current, MAX+2 |
| L3 | Spear + one pylon, smaller slam (18 px) | 40 | slam MAX+1, one shot-eating pylon |
| L4 | Current Bastion: spear, two pylons, 24 px slam | 52 | MAX+4 spear, MAX+2 slam (unchanged) |

### Vespine — Royal Stinger and Venom Sac (class 4, Stinger)

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Short poison dart, no lodge, no pincers | 18 | MAX+1, poison, no sac |
| L2 | Flying stinger lodges, no sac, no pincers | 28 | MAX+2, poison |
| L3 | Stinger + pincers + smaller sac burst (18 px), no Swarm add | 42 | MAX+3 lodge / burst |
| L4 | Current Royal Stinger + Venom Sac rupture, +45 Swarm ticks | 54 | MAX+4 (unchanged) |

### Corvin — Murderstorm Eclipse + Night Veil (class 2, Featherbarb)

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Two shadow feathers, no veil, no eclipse | 20 | MAX+1, no Effigy |
| L2 | Four feathers fan, no eclipse slam, no Effigy | 28 | MAX+2 |
| L3 | Room dim + four feathers + smaller eclipse (14 px), Effigy until f24 | 40 | MAX+3 feathers, MAX+4 eclipse; no Mark extension |
| L4 | Current Eclipse + Night Veil, Mark +45 ticks | 48 | MAX+3 / MAX+7 / +3 marked (unchanged) |

### Wolfkin — Moonfang Cross-Rend (class 0, Fang Forms)

| Lv | Shape | Ticks | Notes |
| --- | --- | --- | --- |
| L1 | Short guarded dash, single claw lane, no crescent | 16 | MAX+1, frontal guard for the short dash only |
| L2 | Moonfang Rush only (dash, three lanes, Will wave); no beat two | 24 | current beat one, no Cross-Rend |
| L3 | Rush + weaker shear (14 px, no eclipse flash) | 34 | shear MAX+0 |
| L4 | Current Rush + Cross-Rend X-shear | 42 | beat-one damage and MAX+1 shear (unchanged) |

Wolfkin control: when Will is banked and the lock is clear, A-down
starts the MAX charge and suppresses the 24-frame held-A melee stream
until release or cancel. The body dash on fire remains part of L2–L4
(and the short L1 dash). When Will is empty or locked, Fang Stab /
Sweep / held combo are unchanged.

## 4. Test plan

New headless PyBoy script `scripts/test_will_max_levels.py`, plus
fixture updates so existing `test_will_max`, `test_will_max_v2`,
`test_will_tiers`, `test_wolfkin_will_wave`, `test_picsean_tide_vortex`,
and `test_will_sfx` keep passing.

The new script must show:

1. **Unlock by kills.** A L1 / 0 hero who records 20 ordinary kill
   credits (the same hook as `run_state_enemies_killed_total`) reaches
   L2 with leftover 0. A further 36 ordinary kills reach L3; 64 more
   reach L4 (120 cumulative from L1 / 0). Below-threshold kills do
   not bump the cap. Elite credit is +2 and boss credit is +8, each
   replacing the ordinary +1, not stacking with it.
2. **Unlock by cap-level use.** Three successful cap-level MAX casts
   from L1 / 0 XP reach L2 (24 XP, remainder 4), granted on committed
   `will_fire_max` even if no body is hit. A below-cap cast grants 0
   use-XP. Mix: 12 ordinary kills + 1 cap-cast reaches L2.
3. **Level select.** With cap L4 and Will banked, holds of 12 / 57 /
   102 / 147 frames fire L1 / L2 / L3 / L4. Also check the
   boundary-minus-one releases at 1, 56, 101, and 146 (still L1 / L1 /
   L2 / L3). A hold past 147 still fires L4. With cap L2, a long hold
   still fires L2. Cancel (B, hit, room exit, Mute) leaves Will
   banked and fires nothing. A mid-hold that is not a fresh A-press
   edge does not arm.
4. **Persistence.** Suspend mid-run at L3 / leftover XP, cold Continue
   (the `test_suspend.py` / `test_difficulty_persist.py` battery
   pattern) restores the same cap and XP. A pre-feature save migrates
   to L1 / 0, and a stored level of 0 is clamped to 1. If meta is
   accepted, a second new run of the same hero starts at the stored
   cap with XP 0; a different hero starts at L1; death does not wipe
   meta.
5. **Picsean L4 identity.** L4 telemetry matches the current Tide
   Vortex (84 ticks, grow 72, max radius 240, front +4 / arm +2,
   heavy cap 6, shot wash, crest voice, 360±3 frame lock at SPD 4).
   L1–L3 match the radius / arm / wash / lock table. A during the
   lock is an ordinary BubbleBolt and does not spend Will.
6. **Difficulty and performance.** Unlock thresholds are the same on
   Easy and Normal. `test_performance.py` stays at 167/180
   fixed-roster and 135/180 dense. No new `combat_tick` hook.

Existing `test_will_max`, `test_will_max_v2`, `test_will_tiers`,
`test_wolfkin_will_wave`, `test_picsean_tide_vortex`, and
`test_will_sfx` seed `maxwill_level` to L4 in setup and share a
147-frame hold helper so L4 regression coverage stays intact.

## 5. Open questions for Carmelo

1. **Starting cap.** This draft starts every new run at L1, so early
   Picsean is weaker than the shipped vortex until L4 (about the
   second dungeon if the player is only killing, faster with cap
   casts). Alternative: start at L2 so the first rooms still have a
   respectable ring, and only L3–L4 are earned. L4 itself stays the
   current art either way.
2. **Meta vs run-only.** Continue/suspend persistence is required.
   Should caps also live in SRAM bank 1 as per-hero knowledge that
   survives death ("only knowledge persists"), or does a new run
   always start at L1 (or L2, per question 1)?
3. **Optional L4 lock.** Default keeps the current 360-frame (6.00 s)
   lock for L4. Lengthen to 420 (7.00 s) only if you want the full
   vortex to come back slower once L1–L3 exist.
4. **Tap habit.** After L4 is unlocked, a tap fires L1 and a hold is
   required for the current vortex. That is the SoM rule. The
   alternative — tap fires the cap, hold lets you stop early for a
   shorter lock — preserves today's reflex but inverts SoM. This
   draft uses SoM (hold longer = higher level).

## 6. Carbon review (2026-11-21)

Short Carbon pass (`gemini-review -m carbon`) on this draft: **ship
with nits**, now folded in above. Kept as-is: untouched L4 arts, no
new `combat_tick` hook, fixed (not SPD-scaled) hold and lock timings,
Will preserved on cancel, one XP pool on Easy and Normal, window-only
pips.

Carbon's advice on the open questions, for Carmelo to accept or
override:

1. Start at L1; fall back to L2 only if room 1 playtests feel broken.
2. Prefer run-only persistence. Full L4 meta carry would retire the
   unlock loop after one deep run per hero. If knowledge-carry is
   wanted, cap the head-start at L2 rather than L4.
3. Keep the L4 lock at 360 frames. The 147-frame hold already
   stretches the L4 cycle; 420 risks double-nerfing uptime before
   playtest.
4. Keep SoM hold-to-climb. If accidental L1 taps waste stacked Will
   pips, a later safety valve is to spend only one pip on a sub-cap
   cast, not to invert the hold rule.

No images, no deploy, and no implementation until the open questions
are settled and Carmelo gives an explicit go-ahead on scope.
