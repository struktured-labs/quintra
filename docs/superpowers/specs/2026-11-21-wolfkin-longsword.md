# Wolfkin longsword (wielded slash and stab)

Date: 2026-11-21.

Carmelo (t547u): Wolfkin's normal attack should be a wielded longsword, not
a thrown sprite. Offer slash and stab; stab has more range and about 2x
damage; slash reaches diagonals. At full hearts he fires a Zelda-style
sword beam. Projectile-type power-ups also grant him projectiles. Right
now the kit feels weak: short, sad, and not hard-hitting.

Follow-ups:
- Input mapping matches Final Fantasy Adventure (t548u): A with no d-pad
  held is the wide slash; A while holding a d-pad direction is the stab.
  FFA only stabs in cardinals; Quintra has 8-dir aim (#26). This spec
  prefers diagonal stabs when a diagonal is held, if the art reads.
- Wolfkin maps to Hornisse in the Penta Dragon series, not Sara W
  (t550u / t552u). Identity and feel stay close-range steel, not a
  starter projectile stream. Max Will stays Moonfang Cross-Rend.
- Wolfkin gets a bleed resistance: he can still bleed, but it is less
  likely (t552u).

Spec first; implementation follows in the same PR after a Carbon review
of balance and feel. No merge or deploy in this work.

## 1. Current kit (measured on main, `b8125c30`)

Wolfkin (`class_id` 0) starts with Fang Forms (`ITEM_CLAW_COMBO`):
`PROJ_SPIKE`, fire rate 20, weapon damage 1, ATK 2, SPD 5. The +20%
move-speed perk is already baked into SPD and is not treated as an
attack-speed relic (`player_fire_delay`).

Live A-button path in `room.c` always sets `g_fang_claw = 1` and adds
+2 damage. `projectile.c` then builds a 6-frame contact arc: speed 1,
lead 10 px, pierce 3, hitbox `0xAA`. Neutral A (no d-pad) only widens
the same single hitbox to `0xCC`. The blade is an 8x8 `SPR_FX_SWING`
entity that still has velocity, so it slides off the hand and reads as
a thrown tile.

| Hero | Shot damage | Cadence | Travel | Practical reach | Pierce | Ideal DPS |
|---|---|---|---|---|---|---|
| Wolfkin | 5 (1+2+2) | 20 f | speed 1, ttl 6 | ~16 px past the body | 3 | 15.0, melee only |
| Sauran | 6 (4+2) | 28 f | speed 4, ttl 12 | ~48 px | 1 | 12.9 |
| Vespine | 6 (2+4) | 20 f | speed 4, ttl 12 | ~48 px | 1 | 18.0 |
| Corvin | 3 (1+2) | 22 f | speed 3, ttl 60 | ~180 px | 2 | 8.2, full-room |
| Picsean | 3 (2+1) | 30 f | speed 2, ttl 80 | ~160 px | 2 | 6.0, full-room |

Wolfkin's raw DPS is fine on paper, but Vespine matches his cadence with
more damage and triple the reach, and Sauran also out-reaches him. The
hurt is the 16 px lane plus the detached tile. `scripts/test_wolfkin_forms.py`
still asserts the older traveling stab (ttl 18, hitbox `0x88`, 3 damage,
~60 px lane). That contract is stale against current main; this work
replaces it.

8-dir aim (#26): `room_input_dir8` plus `player_aim_dir` / Hold Aim.
Releasing the pad keeps the last 8-way heading when Hold Aim is on.
This kit uses a **currently held** d-pad to choose slash vs stab, so
Hold Aim never turns a neutral A into a stab. Slash and stab both aim
with `room_input_dir8` for facing, including a remembered diagonal
when no pad is held.

Projectile-type power-ups today special-case Wolfkin into more melee:

- Formation: two extra short arcs at ±45°, 12 frames.
- Halo (every 3rd A): one stationary spin-slash hitbox, 12 frames,
  instead of the other heroes' 8-way projectile ring.
- Longreach: bigger hitbox; travel bonus is skipped when `vx`/`vy`
  are 0, so a parked claw cannot become a lingering wall.
- Blast / Wingmates: copy or bloom the primary shot as-is.

Max Will is Moonfang Cross-Rend (`wolfkin_wave.c`). Unchanged.

Bleed today: default duration 60 status ticks (8 seconds; ticks fall
every 8 frames). Damage is 1 half-heart per 128 frames spent moving
(`STATUS_BLEED_STRIDE`); standing still costs nothing. Hostile proc
chance is 42% normally, 16% on Easy, 100% on rare/special shots.
`status_player_apply` has no class resist. Facet Ram and Rope apply
Bleed, and heavy physical player shots can inflict it on enemies.
There is no Wolfkin-specific player resist.

## 1b. Carbon review (2026-11-21)

Carbon reviewed this spec for balance and feel (one call, $0.16 logged).
Verdict: ship with the changes below, which this document now uses.

- Slash reach is measured **past the body edge**, not from centre (a
  16x16 hero's half-extent is 8 px; "20 px from centre" was shorter
  than today's 16 px claw).
- Stab is 9 damage / 26 frames / 32 px, not 10 / 24 / 36. Any held
  d-pad is a stab, so moving DPS had to stay only a little above
  Vespine. 9 still one-taps 8 HP trash.
- Sword beam is 3 damage, ttl 36 (~108 px), 1 OAM, and shares the
  melee swing's no-rehit latch so blade and beam cannot stack on the
  same body.
- Diagonal stabs stay 8-dir, drawn as a 3-tile 8x8 45° chain with a
  two-box (mid + tip) hit check.
- Bleed keeps the 50% shrug; duration cut is -25% (45 ticks) with a
  24-tick floor on Easy, so a landed bleed can still cost a half-heart.
- Formation / Halo / Wingmates beams are fixed at half-slash damage
  (2), ttl 28, 1 OAM each. Halo is a 4-way ring that alternates
  cardinals and diagonals. The 6-OAM cap is the unbuffed starter kit
  only (sword + full-HP beam).
- Hold Aim: pad up vs held still chooses slash vs stab, but facing
  comes from `player_aim_dir` while Hold Aim is on, so a retreat
  still stabs forward.

## 2. Input mapping (Final Fantasy Adventure)

- **A, no d-pad held:** wide slash. Covers the front arc and both
  adjacent diagonals (three 45° sectors around the aim heading).
  One swing, not three overlapping blender hitboxes on a boss.
- **A, d-pad held:** stab / thrust in that direction. Longer reach,
  about 1.8x slash damage (9 vs 5), narrow lane.
- **Diagonal stabs:** allowed. A held diagonal (`room_input_dir8` in
  {1,3,5,7}) stabs on that diagonal. Art is a three-tile 8x8 chain
  on a 1:1 slope, not a cardinal blade with a sideways box. Hit
  check uses two stepped narrow boxes (mid-blade and tip) that share
  the swing's no-rehit latch.
- **Hold Aim:** a currently held d-pad still selects stab vs slash.
  While Hold Aim is on, facing is `player_aim_dir`, even if the
  player is walking the opposite way (retreat and stab forward).
  With Hold Aim off, facing is `room_input_dir8`. Neutral A (pad
  released) is always a slash, aimed with the remembered heading
  when Hold Aim is on.
- **Held A:** repeats the same move at its cadence (slash if the pad
  is up, stab if it is held). This is a deliberate combo, not a
  ranged fire stream. No hold-to-charge on the sword; Will MAX stays
  on the shared full-Will tap.
- **Talk / Max Will / A+B / Oath / weapon swap:** unchanged. A swapped
  starter (Tail Spike, etc.) uses that weapon's authored projectile,
  not the longsword.

Buttons stay on A. There is no second attack button. Direction vs
neutral is the whole split, matching FFA and Carmelo's mapping.

## 3. Feel and numbers

The sword is parented to Wolfkin for its whole life. It does not
keep a velocity that carries it off the hand. Each frame the hitbox
and the OAM are re-anchored to the hero, so a step mid-swing carries
the blade with him.

**Slash**

- Damage: 5 (same as today's contact hit: weapon 1 + ATK 2 + 2).
  Crowd tool, not a nerf. Two-taps 8 HP trash.
- Reach: 22 px past the body edge (30 px from the 16x16 centre),
  covering front + both adjacent diagonals.
- Pierce: 3 ordinary bodies. One swing still cannot re-hit the same
  body. Blade and beam share one swing latch (see §4).
- Life: 8 frames, 3 animation frames (wind-up 2f, contact 4f, follow
  2f). Damage is live only on the contact frames.
- Cadence: 20 frames, same baseline, still shortened only by
  run-earned SPD.
- Hitbox: one arc, wide enough to catch a diagonal neighbor. Not
  three independent shots.

**Stab**

- Damage: 9 (~1.8x slash). One-taps typical 8 HP opening trash;
  10–12 HP early bodies stay two-taps. Carbon rejected 10 / 24 f
  because a held d-pad makes stab the default moving attack, and
  25 DPS would beat Vespine by 39% while walking forward.
- Reach: 32 px past the body edge along the aim vector (2x today's
  16 px claw). Fits a four-tile 8x8 strip with no gap; 36 px would
  overflow. On a diagonal, about 24 px per axis (~34 px Euclidean)
  via a three-tile 45° chain.
- Pierce: 2 ordinary bodies, same shared swing latch.
- Life: 10 frames, 2 animation frames (extend 3f, hold 7f). Damage
  is live while extended.
- Cadence: 26 frames. Ideal single-target DPS if every stab
  connects: 9 * 60 / 26 = 20.8, a little above Vespine (18.0), at
  melee risk and shorter reach (32 vs 48 px).
- Hitbox: narrow lane on cardinals (about 8x32 in the aim axis).
  Diagonals use two stepped boxes (mid + tip), not one fat AABB.

**Low-HP / crit / weakness / Surge** keep their existing additives
on top of these base damages.

Item copy: rename Fang Forms to **Longblade** (12-character name
cap). Description: "Slash wide, stab deep. Full hearts fire a beam."

## 4. Sword beam (full hearts)

When `player.hp == player.hp_max` and the longsword is the starter,
every slash or stab also fires a sword beam in the attack heading.

- Damage: 3, pierce 1. Three-taps 8 HP trash from afar, so closing
  to steel is always faster (slash 15.0 DPS, beam-only 9.0).
- Travel: speed 3, ttl 36 (~108 px). This is a real projectile, not
  a second melee arc.
- Art: one 8x8 beam tile (1 OAM), not `SPR_BULLET` and not the
  melee sword. GPT Image 2, quantized.
- Cadence: rides the sword's own cooldown. No extra beam cooldown.
- **Shared latch:** blade and beam of the same swing cannot both
  damage the same body. A small per-swing hit list (or a swing-id
  stamp on the enemy) is cleared on each new fire.
- Does not fire when HP is below max, even by one half-heart.
- Does not fire during Max Will, Convergence, Oath, or a swapped
  weapon.
- Longreach may extend beam travel (+50% ttl). Aegis / Limitless /
  Mend do not create beams.

## 5. Projectile-type power-ups

"Projection" power-ups grant Wolfkin real shots, even when he is
not at full hearts. Melee-only substitutes are removed. All of
these beams use **fixed half-slash damage (2)**, pierce 1, speed 3,
ttl 28 (~84 px), and 1 OAM, regardless of whether the fire was a
slash or a stab (a moving stab must not double power-up output).

| Power-up | Wolfkin now | Wolfkin after |
|---|---|---|
| Formation | two ±45° melee arcs | two 2-damage beams at ±45° from the attack heading, ttl 28 |
| Halo | one 12-frame spin-slash every 3rd A | a 4-way ring every 3rd A, alternating cardinals then diagonals on the next proc |
| Wingmates | copy the melee primary from each buddy | each buddy fires a 2-damage beam in the attack heading, ttl 28 |
| Blast | splash flag on the melee hit | splash also marks the sword beam / power-up beams |
| Longreach | bigger melee box; no travel if parked | melee growth capped at +4 px slash / +8 px stab so an anchored slash never becomes a mid-range wall; beam travel +50% as with other moving shots |

Relic traits (`ATTACK_TRAIT_BEAM`, Swift, Power, Blood, Splash,
Ricochet) apply to the beam the same way they apply to other
champions' primaries. They do not turn the melee slash itself into
a traveling shot.

The "never more than 6 extra OAM" cap is the **unbuffed starter
kit** only (sword + full-HP beam). Power-up beams are 1 OAM each
and are budgeted separately; Halo is 4-way up front so a full-HP
buffed swing cannot dump 8–16 extra sprites plus the blade.

## 6. Per-hero ailment resistance

Every champion has a partial resistance to **one** hostile ailment
that fits their identity. None of these is immunity: the shrug is
never 100%, and a landed proc still hurts. Beneficial statuses
(Regen, Haste) are never resisted. Curse stays on its own
`curse_apply` path and is not in this table. Stop and Confusion
are also left unassigned: a 50% shrug on a hard disable would
distort encounter design more than it would express identity.

Hook: `status_player_apply` in `src/game/status.c`. A five-entry
table keyed by `player.class_id` names the resisted kind. Same
math for every hero. Enemy-applied statuses (a hero's own shots
inflicting bleed, poison, etc.) are unchanged.

| Hero | Resists | Why |
|---|---|---|
| Wolfkin | Bleed | Hornisse toughness. Close-range steel; he can still be cut, just less often and for less time. |
| Sauran | Brittle | Scaled Hide and Stoneskin. Armor can still crack, but the tank shrugs or shortens it. |
| Corvin | Blind | See-HP perk and crow eyes. A seer can still be blinded, but not reliably. |
| Picsean | Burn | Ice/water vessel against fire. Water does not make him flame-proof. |
| Vespine | Poison | Poison Synergy and a venomous wasp. She can still be poisoned, but it sticks less. |

Shared rules (identical for all five):

- **Chance:** 50% shrug after the ordinary hostile proc has already
  succeeded. `rng_range(100) < 50` returns without applying. The
  player still sees the hit. Combined with the 42% hostile proc,
  net land rate for that ailment is about 21% (Easy: 8%). Rare
  100% procs still go through this shrug, so a marked rare hit is
  50%, not guaranteed.
- **Duration:** if the resisted ailment lands, ticks are cut by 25%
  (Bleed/Burn 60 → 45; Blind/Brittle 75 → 56; Poison 120 → 90).
  Easy already halves duration; after both cuts, enforce a
  **minimum of 24 ticks (192 frames)** so an Easy landed proc can
  still do work (for Bleed, that is one half-heart if the hero
  sprints). Other DoT strides and periods are unchanged.
- **Re-apply:** a shrug does not refresh or clear an existing
  matching status. A landed re-apply takes `max(current_ticks, new_ticks)`.
- Other ailments on that hero, and every ailment on a hero who does
  not resist it, use the stock apply path.
- Antidote, Filter Mask, and the floor HP net work as they do now.

Tests apply the hook directly with a fixed seed, once per hero:
shrug rate on their resisted kind is about half, landed duration
matches the cut, and a different ailment (for example Wolfkin +
Burn, Picsean + Bleed) is applied at full duration with no shrug.

## 7. Art (GPT Image 2)

All serious sword, swing, stab, and beam frames use GPT Image 2
(`gpt-image-2.6-sunburst`), quantized to the 4-colour GBC sprite
format (0 transparent, 1 steel, 2 outline/dark, 3 highlight). The
OpenAI key is sourced from `/home/struktured/projects/cowir-sprites/setenv.sh`
on blackmage and is never printed, logged, or committed. Raw
renders stay out of the repo; quantized grids are committed.

Frames (minimum), built from shared 8x8 blade segments where
possible (GBC OAM can flip X/Y but cannot rotate 90°, so a unique
horizontal and vertical strip is required; 45° is a third master):

1. Slash wind-up, contact, follow-through, as 8x8 segments composing
   a 16x16 arc.
2. Stab extend and hold: a 4-tile 8x8 cardinal strip (32 px) or a
   3-tile 45° chain, planted at the hand.
3. Sword beam: one 8x8 tile.

Palette: steel with a warm Hornisse edge (OBJ pal 2 / 4), not a
fireball. Target ≤ 16 unique 8x8 tiles, streaming into a small OBJ
window if a setpiece would otherwise overflow the budget. If
horizontal scanline flicker appears (hero + long stab + beam on one
Y row), drop the visible blade to a 2–3 tile strip.

A 4x preview GIF of slash, stab, and beam is written to
`/workspace/quintra-wolfkin/` for review. It is not committed.

## 8. GBC budget

- **OAM (unbuffed kit).** Hero is already a 16x16 (4 sprites). The
  sword is at most four 8x8 tiles (cardinal stab) or three (diagonal
  chain) plus 1 OAM for the full-HP beam: ≤ 6 extra OAM. Prefer a
  2–3 tile visible blade if a horizontal stab plus beam plus hero
  crowds the 10-sprites-per-scanline limit.
- **Power-up OAM.** Each Formation / Halo / Wingmates / Blast beam
  is 1 OAM. Halo is 4-way alternating, not 8-way.
- **Tiles.** Small bank-0 or bank-1 OBJ window, free in ordinary
  rooms (not a basilisk/boss range). Reload on room entry if a
  setpiece overwrites the slots. Target: ≤ 16 unique 8x8 tiles.
- **Banks / RAM.** New logic stays in the existing projectile,
  room, powerup, and status banks if `check_rom_layout` allows.
  Slash vs stab is computed from the current pad on the fire frame.
  Shared swing latch is a few bytes of existing BSS, not a new
  save field. The beam uses a new aux tag (`PROJ_AUX_SWORD_BEAM`).
- **Perf.** `test_performance` fixed-roster floor 167/180 must
  pass. Slash is a stationary re-anchored hitbox (cheaper than a
  traveling shot).

## 9. Tests

Headless, one script, logs to a file, short pass/fail summary.

- Slash with no d-pad hits a diagonal enemy in the front arc and
  does not spawn a traveling melee shot (`vx`/`vy` stay 0; the
  sprite stays parented).
- Stab with a held direction reaches farther than the slash
  (~32 px vs ~22 px past the body edge) and deals 9 vs 5 damage.
- Held diagonal stabs on the diagonal (3-tile chain, mid + tip).
- Sword beam fires only when `hp == hp_max`, does not fire at
  `hp_max - 1`, deals 3, and does not double-hit a body the blade
  already struck.
- Formation / Halo grant actual projectiles to Wolfkin (2 damage,
  ttl 28; Halo 4-way).
- Ailment resist, once per hero, fixed seed: each champion shrugs
  about half of forced `status_player_apply` calls for their table
  kind, and a landed proc has the 25% duration cut (Easy floor 24
  ticks). A non-resisted ailment on the same hero applies at full
  duration with no shrug.
- No regressions: weapon swap still restores Tail Spike's lunge;
  Max Will is still Moonfang Cross-Rend; New Game and Continue
  (`scripts/test_new_game_start.py`); `check_rom_layout`;
  `test_performance` fixed floor 167/180.
- Replace the stale contracts in `scripts/test_wolfkin_forms.py`
  and the Wolfkin ttl 18 path in `scripts/test_melee_visual.py`.
- Audit other full-HP Wolfkin boots so an unexpected sword beam
  does not break projectile-count or room-clear tests.

If the token cannot edit `.github/workflows/ci.yml`, the two-line
CI step for any new script goes in the PR body.

## 10. Out of scope

- Max Will redesign (Moonfang Cross-Rend stays).
- Changing other heroes' starters.
- Default CLASS_SELECT hero (Wolfkin is Hornisse, not Sara W). That
  is a separate change: the constant is one line, but many headless
  boots press A on the first highlighted row and assume Wolfkin.
  Recommendation is recorded in the PR, not mixed into this patch.
- Publishing, itch, Pocket, or MiSTer.
