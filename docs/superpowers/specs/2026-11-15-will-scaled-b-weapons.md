# Will-scaled B weapons

Date: 2026-11-15 · Status: **proposal for review, nothing implemented**
Verified against `origin/main` at `7cd4d08f` (Sun Lattice PR A, #87).
Argon was not consulted for this draft. The last Argon pass (Sun Lattice)
needed a code fact-check for VRAM and save-bit claims; this spec is mostly
an inventory of live B verbs and budgets, which is safer to pull from the
tree. A later Argon or Carbon pass would still help when art-directing the
Morningstar trail cels, after the questions below are settled.

## Goal

Carmelo (2026-11-15): the Morningstar should gain power from how full the
Will gauge is — bigger radius, a crazier animation as it fills — and the
same treatment should apply to every B weapon.

B weapons should feel like they are drinking from the same meter the player
is already watching, without becoming a second MAX art and without making
Stage 2 bosses even softer. Carmelo is already "destroying" those bosses
and a Stage 2 ATK-cap / DEF / enemy-HP pass is still waiting on an OK.

## What exists in code today (verified on `7cd4d08f`)

### Controls

| Input | Verb | Spends |
|---|---|---|
| A, no banked Will | Primary weapon. A successful shot also **clears the unbanked bar** (`player.will_charge = 0` in `room.c`, Wolfkin and ranged paths). Banked `will_level` is kept. | Unbanked charge only |
| A, `will_level >= 1` | `will_fire_max`: the equipped A weapon's MAX art, then both `will_level` and `will_charge` go to 0 | The whole meter |
| B, no A | `secondary_fire` in `hookshot.c` | See below; **Will is not spent** |
| A+B, full MP | Spirit Convergence (shared 8-way burst, empties MP) | All MP |
| A+B, MP below max | Selected Oath Art | `OATH_MP_COST` MP |
| SELECT+B in Riftwild | Worldglass shear, if owned | Nothing (not a weapon) |
| START, Aim page, Up/Down | `secondary_cycle`: walk Boomerang → Hookshot → Morningstar → Bomb Bag, then back to the class signature | — |

Will charges only while A is not held, `shield_timer == 0`, and the hero is
not Muted (`will_charge_tick` in `room.c`). Stoneskin and Undertow therefore
cannot farm a risk-free MAX during their ward.

### The Will gauge

Defined in `src/game/will.h`, ticked in `src/game/will_support.c`, drawn by
`hud_redraw_action_charge` in `src/render/hud.c`.

- Bar units: `WILL_MAX = 90`. Next bank costs `WILL_MAX + 30 * will_level`
  (90, then 120, 150, 180).
- Fill rule, at SPD `s` (clamped 0..10): every frame adds `15 + s` to a
  fraction; every 40 fraction units grant one `will_charge`. At SPD 5 that
  is **3 / 4 / 5 / 6 exposed seconds** per bank, matching
  `scripts/test_will_tiers.py`.
- Cap: `WILL_LEVEL_CAP = 1 + glove + raft + hook` (the first three Waygear
  bits). Worldglass does not raise the cap. With no Waygear the cap is 1.
- On reaching the cap, `will_charge` is forced to `WILL_MAX` and charging
  stops. The HUD flips to the full-Will violet palette and plays `SFX_WILL`.
- The HUD already shows a **level digit** plus a **3-segment bar**. Segment
  edges are thirds of the current `WILL_NEXT_MAX`. At cap-full all three
  segments are lit.

MAX arts (`will_fire_max`) already scale with banked `will_level`: bonus
damage `+(level - 1)`, extra lanes at levels 2–4, and Wolfkin's Moonfang
Rush throws the Will wave from the 2026-11-12 spec (`#63`). That A-side
scaling stays out of scope here.

### B inventory

`secondary_fire` is the only B dispatcher. It is not a second Will spender.
Class signatures are the default B when no shop tool is equipped
(`active_item = 10 + class_id`).

#### Equippable B tools (Aim-page cycle)

| Item | ID | Shop | Today |
|---|---|---|---|
| Boomerang | `ITEM_ID_BOOMERANG` (45) | 30 | One returning shot. Outbound 28 frames at speed 3, then home at speed 4. Hitbox `0x77`. **No damage.** Stuns ordinary bodies (`QSTATUS_STOP`, 14 ticks); elites, alphas, rares, the Sentinel, the Reaper, and the Bellwarden are immune. Fetches hearts, coins, MP, Surge, and loose relics. Can turn a Sun Lattice vane (`sun_lattice_strike`). The manual says it "cuts shots"; **the live code does not.** One in the air at a time; no `active_charge`. A second B press is a no-op until it returns. |
| Hookshot | `ITEM_ID_HOOKSHOT` (46) | 35 | Distinct from Waygear **Rift Hook** (chasm walk). Tip travels 4 px per frame for 24 frames, so a cardinal shot reaches **96 px (~6 tiles)**; diagonals are the same axis speed. Latches walls, pillars, trees, crystals, and cracked walls, then pulls the body in. A foe is stunned for 4 ticks and is not damaged. 4 OAM (tip + 3 chain links). Retracting B cancels it. Sun Lattice spec (Q3, approved): rotatable vanes are snag-and-spin, then retract; that hook lands in a follow-up PR and today every lattice fixture is treated as a pillar. No `active_charge`. |
| Morningstar | `ITEM_ID_MORNINGSTAR` (47) | 30 | Orbiting flail, the request that started this spec. 16-point radius table peaks at **24 px**. Hitbox `0xAA` (10×10). Damage `player.atk + 3`. Lifetime 40 frames (~1.25 turns, one step every 2 frames). Pierce `hp = 8`. Cooldown `active_charge = 56` (~0.93 s). Sprite tile **237**, palette 13. Dies early if the current orbit cell is not walkable. **No per-target i-frames** on enemies, so eight hits can land on one body in a single swing — already a Stage 2 problem if ATK is high. |
| Bomb Bag | `ITEM_ID_BOMBS` (48) | 30 | Reusable. Costs **1 MP**. Still = drop; held direction = throw (16 frames at 2 px/frame, then it sits). 48-frame fuse, last 16 flash + tick SFX. No contact damage on the fuse (`PROJ_AUX_FUSE_BOMB` is rejected in `combat_shot_hit`). On detonation: 3×3-tile crack/secret open, one 15×15 splash (`hitbox 0xFF`, damage `atk + 8`, pierce 8, 3 frames), 4 impact FX, `room_shake(2, 10)`. Cooldown 72 frames. One live morningstar or fuse-bomb at a time. |

Tile 237 aliases `SPR_CLASS_ASCENDED_STEP_BASE` (232..241). During Spirit
Convergence the star can show an ascended stride cel. The Morningstar
implementation PR should give it a dedicated tile; see budget below.

#### Default B: class signatures (`will_fire_signature`)

These are B weapons. They live in `will.c` but **do not read or spend
Will**. Cooldowns (`will_begin_signature`) are class-shaped and shortened
by SPD, floored at 36 frames. Surge Spark lengthens several of them. War
Drum (every fifth kill) zeros `active_charge` and refunds 1 MP — it readies
B, it does not fill Will.

| Class | Signature | Cooldown (frames) | Today |
|---|---|---|---|
| Wolfkin | Howl | 72 | 8-way spikes, nearby hostile shots cleared in a diamond of 52, 30 i-frames (42 during Surge). A Colossus takes at most 3 Howl lanes (`WILL_HOWL_GIANT_HIT_CAP`). |
| Sauran | Stoneskin | 90 | Ward `shield_timer = 60` (90 during Surge), 8 i-frames. Pauses Will charging while the ward is up. |
| Corvin | Raven Mark | 54 | Marks one aimed foe for 180 ticks. Opening dart (pierce 1). Later A hits on the mark deal `+1`. |
| Picsean | Undertow | 120 | Three bubbles (forward + both sides) plus ward 100 (112 during Surge), 8 i-frames. Also pauses Will charging during the ward. |
| Vespine | Swarm | 72 | Six rotating stings over 97 ticks (~1.6 s) at `damage - 2` (min 1). 18 i-frames (28 during Surge). |

If a signature cannot fire (Muted, or still cooling down) and a Boomerang is
owned, B falls back to a Boomerang throw.

#### Not B weapons (out of scope)

- **Waygear**, always on, never equipped to B: Titan Glove, Tide Raft, Rift
  Hook, Worldglass. The first three only raise `WILL_LEVEL_CAP`.
- **Pack-screen dungeon tools**, used with A on the Pack, consumed from
  inventory: Rift Bomb (7×7 break + 8-way burst), Echo Chime (clear hostile
  shots, reveal neighbors / secrets), Mirror Shard (reflect hostile shots).
  These are not on the Aim-page B cycle.
- **A weapons and their MAX arts**, including Rift Flail and Astral Spear.
  Those already scale with `will_level`.
- Oath Arts and Spirit Convergence (MP ladder, A+B).

## Design

### Will is read, not spent

Using a B weapon **does not consume Will**. The weapon reads a 4-tier heat
value at the moment B is pressed (or, for a long-lived tool, at spawn) and
keeps that tier for the swing / flight / fuse.

The trade-off against MAX arts is temporal, not a second spend:

- Juiced B is available only while you are holding the gauge.
- Firing a MAX empties every bank and the bar, so the next B is tier 0.
- A regular A shot, if no bank is stored, dumps the unbanked bar and can
  drop you from tier 1 back to tier 0.
- Hookshot and Boomerang stay safe to use in puzzles and on fetches while a
  MAX is banked. A consume rule would punish exactly the skillful "hold
  the meter and still traverse" play this feature is meant to reward.

Bombs still cost 1 MP. Signatures and the heavy tools still pay their
existing cooldowns. Will fullness must not shorten those cooldowns — that
would raise B DPS and fight the Stage 2 balance pass.

### Four tiers, aligned to the HUD

`will_b_tier()` returns 0..3 from the same values the HUD already shows:

| Tier | Condition | What the player sees |
|---|---|---|
| 0 | `will_level == 0` and bar below one third | Digit 0, empty or nearly empty bar |
| 1 | `will_level == 0` and bar at least one third, not yet banked | Digit 0, 1 or 2 segments lit |
| 2 | `will_level >= 1` but not cap-full | Digit 1+ ; a MAX is ready, bar may still be filling toward a higher cap |
| 3 | `will_level >= WILL_LEVEL_CAP` (bar forced full, violet palette) | The full-Will chime state |

Early game (cap 1): banking the first — and only — level jumps straight
from tier 1 to tier 3, which is the "the meter is full and the star goes
wild" beat Carmelo asked for. Later, once Glove / Raft / Hook have raised
the cap, tier 2 covers the "I am holding a MAX but the gauge is not yet
capped" window, and tier 3 is the true full-meter spectacle.

Helper lives next to the existing Will bank (`will.h` / `will_support.c`),
so every B path can ask once and not reimplement the table.

### Balance rule (Stage 2)

Carmelo is already too strong in Stage 2. These tiers must reward holding
the gauge with **reach, duration, and spectacle**, not with a damage
multiplier.

Shared caps, for every B verb:

- Damage bonus is at most **+0 / +0 / +1 / +2** across the four tiers.
  Never a multiplier, never extra pierce on a tool that already hits the
  same body more than once.
- Do not add a second damaging hitbox to the Morningstar. Enemies have no
  per-target i-frames; the star already has pierce 8. A second head would
  delete a Stage 2 colossus.
- Do not add more Howl / Undertow / Swarm projectiles at high Will. Howl
  already has a 3-hit Colossus cap; keep it.
- Secret-opening geometry (Bomb Bag 3×3 crack, Hookshot latch set) does not
  grow with Will. Combat splash and animation may grow. Will is not a better
  dungeon key.
- Cooldowns and MP costs do not shrink with Will.
- The pending ATK cap (9), unstacking duplicate relics, DEF pool adds, and
  Stage 2/3 HP bumps should land in the same window as the first weapon PR,
  so juiced B is not playtested on already-soft bosses.

## Per-weapon tiers

Numbers below are the current value at tier 0, then the proposed 1/2/3
steps. Animation is listed separately so it can be cut independently if
OAM is tight in a given room.

### Morningstar (first to build)

| | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|
| Peak radius | 24 px (live) | 28 px | 34 px | 40 px (~2.5 tiles) |
| Hitbox | `0xAA` 10×10 | `0xAA` | `0xCC` 12×12 | `0xDD` 13×13 |
| Damage | `atk + 3` | `atk + 3` | `atk + 4` | `atk + 5` |
| Lifetime | 40 frames | 40 | 44 | 48 |
| Pierce | 8 | 8 | 8 | 8 |
| Cooldown | 56 | 56 | 56 | 56 |
| Animation | Current single head, palette 13 | Afterimage 1: same tile, dimmer palette, 2 steps behind | Afterimage 2, Will-violet flash on the head (reuse the Moonfang `will_flash_palette`) | Two trailing sparks, faster readable spin (still one damaging head), `room_shake(1, 8)` on press, a slightly higher FLAIL / short roar |

The 16-point orbit table is multiplied by a 8.8 fixed scale (24, 28, 34, 40
are close to 24 × 8/8, 9/8, 11/8, 13/8). Trails are **visual only** and
must not call `combat_apply_player_shot_hit`.

### Hookshot

| | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|
| Outbound timer (range) | 24 frames / 96 px | 28 / 112 px | 32 / 128 px | 40 / 160 px (~10 tiles) |
| Damage | none | none | none | none |
| Foe stun | 4 ticks | 4 | 6 | 8 |
| OAM | 4 (tip + 3 links) | 4 | 4, links spaced to the new length | 4, tip spark on latch |
| Animation | Current | Palette tick toward Will violet | Tip flash on latch | Latch spark + a single-frame chain gleam |

Range may make optional Sun Lattice vanes easier to snag; required rooms
stay melee-solvable, which is already the approved lattice rule. Traversal
and cancel-on-B are unchanged. No consume.

### Boomerang

| | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|
| Outbound frames | 28 | 32 | 36 | 44 |
| Stun on ordinary bodies | 14 ticks | 16 | 20 | 24 |
| Damage | none | none | none | none |
| Animation | Current 4-flip spin | 1 afterimage | 1 afterimage + Will-violet flick | 2 afterimages, and **finally cuts one hostile shot** on overlap (the manual already claims this; make it the capstone, not a baseline) |

Fetch set and the "one in the air" rule do not change. Elites and bosses
stay stun-immune at every tier.

### Bomb Bag

| | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|
| MP cost / fuse / throw | 1 MP, 48 frames, 16×2 px | same | same | same |
| Crack / secret radius | 3×3 tiles | 3×3 | 3×3 | 3×3 |
| Combat splash | one 15×15, `atk + 8` | same | same splash + `atk + 9`; 2 extra corner FX | plus-shape: 5 splashes (centre + 4 at ±10 px), `atk + 10`; 8 FX; `room_shake(2, 14)` |
| Cooldown | 72 | 72 | 72 | 72 |
| Animation | Current flash and 4 impacts | Faster fuse flash (same 16-frame window, more palette toggles) | Brighter fuse, Will-violet at detonation | A one-frame white pop on the bomb sprite, then the plus burst |

Splash entities already use the maximum 15×15 hitbox, so a bigger radius
has to be multiple splashes, not a wider nibble. Cap the plus-shape with
the existing `PROJ_FLAG_CONVERGENCE` limiter on the four arms so a Colossus
is not hit five times by one detonation. The centre splash is the only one
that damages a giant; the arms are for crowds.

### Class signatures

Scale duration and utility, not volley size.

**Howl.** Shot-clear diamond 52 / 56 / 64 / 80. I-frames 30 / 30 / 36 / 42.
Lane count stays 8, Colossus cap stays 3, damage stays as authored. Tier 2+
flashes the hero to the Will violet ramp for the burst, same restore path
as Moonfang.

**Stoneskin.** Ward 60 / 60 / 75 / 90. I-frames stay 8. Aura spawn is
denser at tier 2+ (every 6 frames instead of 8), palette ticks violet.
Still pauses Will charging: a longer ward is a real hold-or-spend choice
against a MAX.

**Raven Mark.** Duration 180 / 180 / 210 / 240. Mark bonus stays +1. Opening
dart unchanged. At tier 3 the mark FX is a two-cel pulse for the whole
timer (1 extra OAM, reused impact tile) so the lock is readable across a
full room.

**Undertow.** Ward 100 / 100 / 112 / 120. Bubble pierce `hp` +0 / +0 / +1 /
+1. Still three bubbles. Same Will-pause as Stoneskin.

**Swarm.** Timer 97 / 97 / 113 / 129 ticks (still one sting every 16 frames
after the opener, so 6 / 6 / 7 / 8 stings). Per-sting damage unchanged.
Tier 3 adds a short Will-violet flick on each launch.

## OAM / VRAM / bank budget

Live use today:

- Morningstar: 1 OAM, tile 237 (collides with ascended stride 232..241).
- Hookshot: 4 OAM, tile `SPR_WAYGEAR_HOOK` (206) plus `SPR_BULLET` links.
- Boomerang: 1 OAM, tile 128.
- Bomb Bag: 1 fuse OAM (tile `SPR_ITEM_RIFT_BOMB` 152) plus 1 splash entity
  and 4 short FX.
- Howl: 8 player-shot entities. Stoneskin aura is already periodic FX.
  Swarm is one sting at a time.

Proposed standing budget, not to be exceeded without a new review:

- **+2 visual-only OAM** for Morningstar or Boomerang afterimages, only
  while that weapon is live. Hookshot stays at 4.
- **+0 to +4 splash / FX entities** on a tier-3 bomb, plus the convergence
  cap above.
- **+1 OAM** for a tier-3 Raven Mark pulse, only while the mark timer is
  live.
- **Zero new standing OBJ tiles by default.** Afterimages reuse the
  weapon's own tile with a dimmer or Will-violet palette. Sparks and
  fuse pops reuse `SPR_FX_IMPACT` (33), which sits in the low OBJ block
  and is already the detonation / hit flash.
- Do **not** spend bank-0 OBJ 129 and 130. They look like a gap between
  `SPR_ITEM_BOOMERANG` (128) and `SPR_ITEM_IRON_HEART` (131), but they
  are `HUD_OFFER_DRUM` and `HUD_OFFER_FLASK` on the WINDOW layer, and
  with 0x8800 addressing they alias the same VRAM as OBJ 129–130. The
  Boomerang tile (128) already aliases `HUD_OFFER_THORN` the same way.
  Boss pose loaders also call `set_sprite_data(128, …)` with 8–16 tiles
  (`serpent_jaw_b.c`, `crystal_pose_b.c`, `cinder_rex_pose_b.c`,
  `void_pose_b.c`, `golem_pose_b.c`), so that whole item-atlas window is
  occupied during those fights.
- Morningstar tile 237 stays in this pass as a documented alias of
  `SPR_CLASS_ASCENDED_STEP_BASE` (232..241). The implementation PR should
  move the head to a swing-local `set_sprite_data` overlay, restored when
  the swing ends and on `room_enter`, the same way Moonfang reloads
  200..203 because the 0x8800 block is shared with menus. Do not touch
  those four wave tiles. A later audit can pick one truly free standing
  index; this spec does not claim one.
- Palette: borrow the existing 4-color Will-violet ramp already used by
  the Moonfang wave (`will_flash_palette` in `wolfkin_wave.c`) on the
  weapon's object palette, then restore through
  `room_refresh_player_appearance`. No new OBJ palette slot.
- ROM: one shared `will_b_tier` helper and a 4-byte table per verb. Expect
  on the order of **1–2 KB** including any swing-local overlay cels and the Morningstar
  scale path. No new SRAM, no new save version. Bank 16 already hosts
  `hookshot.c`, `secondary_heavy.c`, and `combat_shot_hit.c`; keep the
  per-weapon scale next to those fire/update functions. The helper itself
  can stay in bank 11 with `will_support.c`.

A crowded boss room (Hexa, Reaper, plus Hookshot chain) is the OAM
stress case. Afterimages must hide, not steal, if `oam >= 40`.

## Implementation order

Docs only in this PR. When building, ship in this order so each step is
playable and testable on its own:

1. **`will_b_tier()` + `scripts/test_will_b_tier.py`.** Table-driven cases
   for cap 1 and cap 4, including "A dumps unbanked charge drops tier 1 to
   0" and "MAX drops every tier to 0". No gameplay change yet.
2. **Morningstar** (radius, hitbox, modest damage, trails, and a swing-local head tile if no standing index is free).
   The request that started this. GIFs at tiers 0, 2, and 3.
3. **Bomb Bag** (splash plus-shape and animation only; crack stays 3×3).
4. **Hookshot** (range, stun, tip spark). Re-check Sun Lattice snag-and-spin
   once that PR has landed, so a longer shot cannot soft-lock a vane room.
5. **Boomerang** (range, stun, afterimages, tier-3 shot cut).
6. **Class signatures**, Howl first, then Stoneskin / Undertow (the two
   that pause Will charging — their longer wards need a feel pass), then
   Raven Mark and Swarm.

Do not start step 2 until the pending Stage 2 ATK / DEF / HP pass has an
answer, or land that pass in the same window. Tests to extend or keep
green: `test_will_max.py`, `test_will_tiers.py`, `test_dungeon_tools.py`,
and any existing hookshot / boomerang / morningstar / bomb scripts.

## Questions for Carmelo

1. **Should using a B weapon consume Will, or only read it?**
   **Recommendation: read only.** Hookshot and Boomerang are traversal and
   fetch tools. Spending the meter on them would punish using them while
   holding a MAX, which is the opposite of the "the fuller the gauge, the
   juicier the weapon" fantasy. The trade-off is already there: fire the
   MAX (or a regular A that dumps the bar) and the next B is small again.

2. **Four HUD-aligned tiers, or a continuous scale off the raw bar?**
   **Recommendation: the four HUD-aligned tiers above.** They match the
   digit + 3-segment bar the player already has, and they give a clear
   early-game jump from "filling" to "full and wild" when the cap is still
   1.

3. **Do the five class signatures scale too, or only the four shop tools?**
   **Recommendation: yes, signatures too.** "All B weapons" includes the
   free class B. Scale duration and utility, never volley size. Howl's
   3-hit Colossus cap stays.

4. **Do Pack-screen tools (Rift Bomb, Echo Chime, Mirror Shard) scale?**
   **Recommendation: no, not in this pass.** They are consumed with A from
   the Pack, not equipped to B. A later pass can pick them up if the
   Morningstar feel is right.

5. **A second damaging Morningstar head at tier 3?**
   **Recommendation: no.** Visual trails only. The live flail already has
   pierce 8 and enemies have no per-target i-frames, so a second head is
   how Stage 2 bosses disappear.

6. **Should the Bomb Bag's 3×3 crack grow with Will?**
   **Recommendation: no.** Combat splash and the detonation animation grow;
   secret-opening geometry stays 3×3 so Will cannot become a better
   dungeon key.

7. **May a longer Hookshot be a Sun Lattice shortcut?**
   **Recommendation: yes, as a shortcut only.** Required rooms stay
   melee-solvable, which is already the approved lattice rule. The hook
   still does not spend Will.

8. **Build now, or wait for the Stage 2 ATK cap / enemy HP pass?**
   **Recommendation: approve this spec now, but start the Morningstar PR
   only once that balance pass has an answer, or land both in the same
   window.** Juiced B on already-soft Stage 2 bosses would hide whether
   the radius-and-spectacle plan is actually fair.
