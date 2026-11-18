# New monster types: Veil Magus, Hex Walker, Vault Hand, Bane Brute, Zag Dart, Leybeam

Date: 2026-11-17. Requested from playtest: Zelda-style wizrobes, a Wallmaster-style
grabber, a knockback bruiser that groups with status casters, a zig-zag burster,
and a wide laser-beam caster. Confusion (D-pad remap) audit is included.

No hero kits are changed in this work. A Max-Will laser proposal is recorded at
the end for a later pass only.

## 1. Roster audit (do not duplicate)

Existing casters / teleporters / shooters on `origin/main` (`4614675c`):

| Enemy | AI | Role |
|---|---|---|
| Shade | `AI_TELEPORT` | Vanishes, reappears *beside* the hero, melee ambush. No shot. |
| Warlock | `AI_SHOOTER` fan | Tanky walking fan-caster (HP 28). Stays on screen. |
| Wisp / Cinder Maw / Kite / Rune Lantern / Dread Bell / Rift Warden / Dusk Midge | `AI_SHOOTER` | Drift or harass and fire. Never blink off-screen to recast. |
| Sentry | `AI_TURRET` | Stationary rotating cross. |
| Rift Cantor | `AI_SUMMONER` | Chants, then calls escorts. Does not shoot a bolt or teleport. |
| Prism Skitter, Sunwheel, Vine Coil, Bramble, Void Halo | `AI_SPINNER` | Orbit + lanes. |
| Mirror Moth | `AI_MIRROR` | Reverse-step, then a slow reflected bolt. |

There is **no** Zelda red-Wizrobe (blink in, telegraph, shoot, vanish, reappear
elsewhere), **no** Zelda-1 blue-Wizrobe (walk, stop, shoot, walk), **no**
Wallmaster, **no** long-shove bruiser that is authored to travel with status
allies, **no** zig-zag burst body, and **no** sustained wide beam.

Confusion already exists as `QSTATUS_CONFUSION` (see §7). It is not a new
status; this work only fills the missing tell / test / antidote proof.

## 2. The six new bodies

IDs append after `ENEMY_STAGE_REAPER` (34). Symbols stay under 10 letters in
the bestiary name field.

### 2.1 Veil Magus (Wizrobe A) — `ENEMY_VEIL_MAGUS` = 35

Zelda red-Wizrobe cycle, clearly not a Shade:

1. **Vanish** (~20 frames). Body parks off-screen like Shade (`y=200`,
   `EF_ON_SCREEN` cleared) with a puff. Unhittable, uncollidable.
2. **Reappear** on a walkable tile at least 24 px from the hero and 16 px from
   any wall corner that would trap a shot. Never on the hero, never in a wall,
   never off the room. Materialize shimmer (`ai_data[7]`) + puff.
3. **Telegraph** 24 frames (Normal) / 32 Easy: palette flash and a short aim
   line (one 8x8 spark between Magus and hero). Audible `SFX_TICK`.
4. **Shoot** one aimed magic bolt (speed 2, damage = table). Then hold 16
   frames so the bolt is readable.
5. Repeat from vanish. If eight placement tries fail, stay vanished and retry
   in 30 frames (same safety valve as Shade).

- HP 12, damage 2, speed 32, score 40, weakness lightning (`0x04`), poise 0.
- Inflicts nothing on contact (the bolt is the threat).
- Max 2 per room. Not in foyer, boss, town, or Riftwild field rooms.
- Stages: Frost Vault (weight 8), Shadow Keep (8), Bloodmoon (7), Void Sanctum (6).
  Mid-late only, so Crystal/Verdant keep teaching Shade later rather than
  mixing two blinkers early.

### 2.2 Hex Walker (Wizrobe B) — `ENEMY_HEX_WALKER` = 36

Zelda-1 blue-Wizrobe: stays on screen, walks, then casts.

- Cardinal walk for 40–64 frames, then stop.
- 16-frame glow tell, then one aimed bolt (speed 2, damage 1).
- Resume walking in a new cardinal drawn from the current heading ±90°.
- Does not pass walls. Does not vanish. Faster cadence than Warlock, one bolt
  instead of a fan, much less HP.

- HP 10, damage 1 (contact 1, bolt 1), speed 56, score 28, weakness fire
  (`0x01`), poise 0.
- Stages: Verdant Hollow (8), Frost Vault (8), Golden Temple (8). Early-mid
  caster that is not a Wisp (Wisp drifts randomly) and not a Warlock (Warlock
  is a late tanky fan).

### 2.3 Vault Hand (Wallmaster) — `ENEMY_VAULT_HAND` = 37

Ceiling grabber. Destination is the **dungeon foyer**:
`run_state_dungeon_entry_cell()` plus the existing `room_enter` path, the same
way a door into that cell works. Inventory, relics, keys, map knowledge,
puzzles, and mission flags are untouched. HP is not reset. The Hand itself
does not travel with the hero.

**Cycle**

1. **Hunt, hidden.** No body. A shadow (dark 8x8, growing to 16x16 over 48
   frames) tracks under/above the hero, then locks for 16 frames. `SFX_TICK`
   at lock. This is the whole tell.
2. **Drop** (12 frames). The hand falls onto the locked tile. Contact during
   the drop or the following 20-frame grab window starts a grab.
3. **Grab, escapable.** Hero is held 48 frames. Mash: 8 D-pad or A/B edges
   break free. Any damaging player shot or melee that hits the Hand also
   breaks free and deals normal damage. Clear palette strobe + “STRUGGLE”
   is unnecessary; the growing shake and a rising `SFX_HIT` tick on each mash
   are enough. On escape the Hand vanishes and waits a 160-frame cooldown.
4. **Carry.** If the window expires, a short 20-frame carry animation plays
   (hero sprite hidden against the Hand, `SFX_PORTAL`), then the room is
   rebuilt as the foyer. The hero is placed on a walkable foyer tile, with 60
   iframes so a foyer pack cannot instantly re-grab or chew them. The Hand
   does not spawn in the foyer on that entry.

**Softlock and fairness gates (must all be true to spawn or to finish a carry)**

- Current room is a dungeon combat room, not a town, shop, sanctuary rest
  court, Riftwild field, den, or village.
- `run_state_is_boss_room()` is false, and no giant / Colossus / Cinder pack
  / Hexa / Reaper encounter is live.
- No vignette, dialog, death, victory, or pack/map overlay is active.
- Foyer cell is resolvable and walkable.
- If a grab starts and a boss or cutscene flag later becomes true, abort the
  grab, release the hero in place, no warp.

- HP 16, damage 1 (the grab is the punishment, not the hit), speed 40,
  score 50, weakness lightning, poise 2.
- One per room, mid-late: Shadow Keep (6), Golden Temple (5), Bloodmoon (5).
  Never in the foyer itself.

### 2.4 Bane Brute (knockback bruiser) — `ENEMY_BANE_BRUTE` = 38

A heavy body whose contact knockback is 18 px (three times the shared 6 px
nudge), wall-checked one pixel at a time with the existing
`room_player_position_clear` contract. Contact damage stays 2. The point is
to shove the hero into status allies, not to be a second Orc charger.

**Spawn grouping (hard rule)**

- A Bane Brute is never placed alone. The generator, after rolling the room
  pool, does the following when a Brute is selected:
  1. Keep the Brute.
  2. Guarantee **at least two** status-inflicting allies in the same room,
     chosen from this room's stage pool when possible. Status sources already
     on main: Shade (Blind), Rune Lantern / Dusk Midge (Confusion), Frost
     Lancer (Slow), Mire Spore / Bramble Sprite (Poison), Gloam Leech (Curse),
     Cinder Maw / Kite (Burn), Bog Toad (Brittle), Mirror Moth (Inversion),
     Fold Star (Stop), Warlock / Dread Bell (Mute).
  3. If the rolled room has fewer than two of those, inject the missing
     allies from the stage's status subset (do not invent a status enemy the
     stage does not already own). If the stage pool has fewer than two status
     species, do not spawn the Brute in that room.
  4. Placement: the two allies sit 20–36 px behind the Brute along a cardinal
     lane that is open at generation time, so a shove from the hero's likely
     approach carries into them. The Brute never spawns in a one-tile alcove
     that would cancel knockback against a wall.
- Max one Brute per room. Not in foyer or boss rooms.
- Stages: Toxic Mire (8, with Spore + Toad), Shadow Keep (6, with Shade +
  Bramble / Lantern), Bloodmoon (5, with Shade + Midge / Warlock).

- HP 22, damage 2, speed 40, score 45, weakness poison (`0x10`), poise 3.
- AI is a slow walker that turns toward the hero every 32 frames. No charge
  tell (Orc / Toad / Lancer already own that). No projectile.

### 2.5 Zag Dart — `ENEMY_ZAG_DART` = 39

A small burster. **Touch damage during the zig-zag is the main threat.**

- Idle / cooldown walk (slow, 80–120 frames).
- **Tell** 18 frames: body flashes, a two-segment zig preview (tiny sparks
  along the first jog).
- **Burst** 28 frames: dashes in a zig-zag toward the hero's position at
  tell-lock (not tracked mid-burst). Each 7-frame leg is 8 px along the
  locked axis, then 8 px perpendicular, then the main axis again. Wall-safe:
  a blocked leg aborts that leg and continues with the next, or ends the
  burst if both axes are blocked. Contact damage 2 while bursting, 1 while
  idle.
- **Cooldown.** After the burst, 90 frames idle. During cooldown, a **rare**
  single slow bolt may fire: 1-in-4 chance, only once per cooldown, speed 1,
  damage 1, no fan. The bolt is flavour and chip, never the encounter's
  centre.

- HP 8, damage 2 (burst) / 1 (idle), speed 96, score 22, weakness ice-adjacent
  use water/ice bit if present else lightning `0x04`, poise 0.
- Stages: Crystal Caverns (8), Verdant Hollow (6), Ember Depths (6), Void
  Sanctum (6). Early enough to teach the tell, late enough to mix with beams.
- Max 2 per room.

### 2.6 Leybeam — `ENEMY_LEYBEAM` = 40

A stationary-enough caster with a **wide, continuous laser**.

- Slow cardinal drift while on cooldown (8-tick step, like a classic shooter).
- **Charge tell** 40 frames Normal / 52 Easy: body glows (palette strobe) and
  a *thin* aim line locks to the **nearest cardinal** toward the hero at the
  start of the charge (4-way only; walk onto an axis first if needed). The
  line does **not** track after lock. Diagonals are rejected: an 8x8 BG
  stamp cannot make a clean 16-px diagonal ray. `SFX_TICK` at start and at 8 frames before fire.
- **Beam** 36 frames: a 16-px-wide sustained band along the locked aim,
  running to the first solid wall (or the room edge). The hero must sidestep.
  Damage is 1, applied at most once per 20-frame iframe window so a worst-case
  stand-in-it costs two hearts, not a death in three frames. The beam does
  not pass walls. It does not turn mid-fire.
- **Cooldown** 100 frames. One Leybeam per room.

**GBC budget for the beam.** Do not spend a row of OBJ on the shaft.

- **BG tiles only, cardinal rays.** Stamp a reserved 2–4 tile beam strip
  (horizontal or vertical, 16 px / 2 tiles wide, grid-aligned) along the
  locked ray through the existing VBlank tile path, at most one row or
  column per frame, finishing during the last two charge frames. Restore
  from the RAM room-map when the beam ends, the caster dies or is Stopped,
  or the room exits. Palette: a bright colour already in the stage BG set
  (Temple gold, Ember red, Sanctum violet). Do **not** use the Window layer
  (it covers everything right/below WX,WY and fights the HUD).
- The Leybeam body itself is an 8x8 two-frame walker (glow frame B).

- HP 14, damage 1 (beam and contact), speed 32, score 48, weakness shadow
  (`0x08`), poise 1.
- Stages: Ember Depths (6), Golden Temple (8), Void Sanctum (8). Only in
  rooms with at least 48 px of sidestep space along the cross-axis (skip
  cramped puzzle closets; the visible-puzzle guard path already knows this
  kind of rejection).

## 3. Shared rules

- Telegraph timings above are Normal. Easy adds ~25% to every tell and does
  not shorten cooldowns. No new Easy-only patterns.
- All six respect `enemy_try_step` / walkable tests. Teleports and drops use
  `room_tile_walkable` and stay 8 px inside the room bounds.
- Contact still goes through the shared combat path, then status procs, so
  Bane Brute shoves *and* a status ally can still apply on the resulting
  overlap on a later frame (not the same frame as the shove, to keep the
  read honest).
- Vault Hand and Leybeam are muted (no shot, no beam, no drop) while
  `STATUS_PLAYER_*` Stop is on them, and while the hero is in a death or
  reward fanfare.
- One new banked AI file if bank 2 / bank 5 / bank 6 cannot hold the new
  ticks (`enemy_new_ai.c`, next free behaviour bank). Do not blow the 256-
  byte emergency floor on a hot bank. `scripts/check_rom_layout.py` must
  stay green.
- `test_new_game_start` must keep passing for every hero and every start
  path.

## 4. Sprite budget

Two-frame walks are the default, generated into `enemy_anim_atlas` the same
way as the 2026-11-15 monster pass. GPT Image 2.6 Sunburst
(`gpt-image-2.6-sunburst`) provides candidates; hand-quantize to the existing
3-colour OBJ palettes. Key is sourced from
`/home/struktured/projects/cowir-sprites/setenv.sh` and is never printed,
logged, or committed. Spend alert at $100; prior spend about $6.6.

| Body | Size | Palette | Frame B | Slot plan |
|---|---|---|---|---|
| Veil Magus | 8x8 | 6 magic / violet | cloak flare, staff raised (cast pose reused as tell) | New high OBJ slot, or stage-safe multiplex. Never share a slot with Shade in the same room. |
| Hex Walker | 8x8 | 3 blue | stride / staff tip | Same. Never share with Warlock or Wisp in one room. |
| Vault Hand | 16x16 (2x2) or 8x8 growing via shadow + body | 0 bone | open / clenched | Shadow is a dark 8x8/16x16 FX tile. Body can reuse a mid-scale slot in Shadow/Temple/Bloodmoon only. |
| Bane Brute | 16x16 bruiser class (same as Orc/Bomber) | 7 green or 4 red | step / shoulder down | Mid-scale 4-tile block, Mire/Shadow/Bloodmoon only so it does not collide with Orc's Temple slot. |
| Zag Dart | 8x8 | 5 gold or 4 red | lean into the zig | Slot-79 style stage multiplex is fine in Crystal/Verdant/Ember/Sanctum if those rooms do not already use 79 for another specialist. Crystal already has Shard Crab on 79 — give Zag its own small slot or share only in stages without a 79 specialist. |
| Leybeam | 8x8 body | 5 gold (Temple), 4 red (Ember), 6 violet (Sanctum) | glow | Body is one slot. Beam shaft is BG, not OBJ. |
| Confusion swirl | 8x8 FX, two-frame star swirl | 6 violet | rotate | One FX tile, drawn over the hero while `QSTATUS_CONFUSION` is live. Recycle `SPR_FX_IMPACT` only if a second FX slot cannot be spared; prefer a distinct swirl. |

Magic bolt for both wizrobes reuses the hostile bullet sprite (possibly
recoloured with palette 6). No new projectile tile is required.

## 5. Content and AI wiring

- Add IDs in `content/src/ids.rs`, entries and `register` in
  `content/src/enemies.rs`, weights in `content/src/stages.rs`.
- Extend `AiScriptId` in `tools/crates/quintra-content/src/enemy.rs` and the
  emit arm in `quintra-codegen` with:

  - `BlinkCaster { vanish_ticks, tell_ticks }`
  - `WalkCaster { walk_ticks, tell_ticks }`
  - `Grabber { shadow_ticks, grab_ticks }`
  - `Shover` (no params; knockback distance is a C constant)
  - `ZigZag { tell_ticks, burst_ticks, cooldown_ticks }`
  - `BeamCaster { tell_ticks, beam_ticks, cooldown_ticks }`

- Dispatch from `enemy_update` into banked ticks. **Narrow the existing
  `if (id >= ENEMY_FACET_RAM)` patrol intercept to
  `id >= ENEMY_FACET_RAM && id <= ENEMY_STAGE_REAPER`**, or the new IDs 35–40
  will never reach their `ai_kind` cases. Put the new ticks in a fresh bank
  (`enemy_new_ai.c`, **bank 25** — bank 31 is now `powerup_extra.c` after PR #136) from day one. Grouping logic lives in
  the room population path (procgen / spawn), not in the per-frame AI.
- Bane Brute knockback: a special case in the existing contact knockback
  loop (the 6 px shove in `combat.c`) when `ai_data[0] == ENEMY_BANE_BRUTE`.
- Vault Hand warp: do **not** call `room_enter` from inside `enemy_update`.
  Set a deferred flag (`pending_foyer_warp`) handled at the top of the main
  room loop after the entity tick. That handler sets `run_state.room_counter`
  to `run_state_stage_start(bosses_beaten) + run_state_dungeon_entry_cell()`,
  picks an `entered_from` that lands on a walkable foyer tile, clears live
  projectiles and FX, then takes the ordinary `room_enter` rebuild. Do not
  call `run_state_place_at_entry()` (that function clears dungeon seen/
  visited bits and would wipe map progress).
- Leybeam BG stamp must restore on beam end, room exit, and death.

## 6. Tests (headless PyBoy, no GUI)

New scripts under `scripts/`, plus hook them into the existing make/CI
lists beside the other enemy tests.

- `test_veil_magus.py`: spawn; vanish parks off-screen; reappear never in a
  wall or on the hero (fuzz 50 teleports); telegraph then exactly one bolt;
  bolt damages the hero; Magus is hittable only while present.
- `test_hex_walker.py`: walks, tells, fires one bolt, walks again; no vanish.
- `test_vault_hand.py`: shadow grows then body drops; mash escapes; a player
  shot escapes and deals damage; an unescaped grab restores the foyer cell
  (`run_state_dungeon_entry_cell`) and keeps inventory / hearts / map bits;
  forced flags (`run_state_is_boss_room`, vignette, dialog) refuse spawn and
  abort a live grab with no warp.
- `test_bane_brute.py`: a room that rolls a Brute always contains ≥2 status
  allies; contact knockback travels ~18 px on an open floor; a wall stops
  the shove; Brute never appears alone.
- `test_zag_dart.py`: tell then zig-zag burst; contact during burst; cooldown
  bolt is optional and at most one; burst never steps into a wall.
- `test_leybeam.py`: charge line locks and does not track; beam is 16 px wide
  and stops at a wall; standing in it damages; a sidestep one tile off the
  band takes no damage; cooldown elapses before the next tell; tiles restore.
- `test_confusion_fx.py` (see §7).
- `test_performance.py` must still pass on a crowded screen that includes at
  least one new specialist (Magus + Walker + a Leybeam is the stress case;
  skip Vault Hand carry and beam-BG restore mid-bench).
- `test_new_game_start` remains required and green.
- Update `test_enemy_identity` / bestiary copy / `docs/manual/content/bestiary.md`.

## 7. Confusion status — audit and leftover work

**Did the 2026-11-16 “D-pad sends the hero the wrong way” request land on
main?**

**Yes. The core effect and the 2026-11-16 retune are both on main.** The
core D-pad remap landed in `a7b2daa5` ("feat: add rift conditions and
inverted hunt"). The retune (3.2 s / 24 beats, horizontal mirror or
half-turn only, no mid-effect reshuffle, 4 s `confusion_immune`, standing
still shortens the effect) merged in
[PR #136](https://github.com/struktured-labs/quintra/pull/136) at `f830836f`.
Rune Lantern and Dusk Midge inflict it; `scripts/test_confusion.py` is on
main. **Do not re-implement the retune.**

**What is still missing on main**

- No persistent swirl-star sprite over the confused hero.
- Pack Antidote already calls `status_player_cure()`, which clears
  Confusion. Auto-rescue (`antidote_try_rescue`) stays DoT-only
  (Poison / Burn / Bleed).

**This PR will not touch the retune, `status.c` cadence, or
`scripts/test_confusion.py`.** It only adds the missing tell:

- A two-frame swirl-star FX over the hero for the whole Confusion duration,
  gone on expiry or cure.
- Pack Antidote remains the cure; document and test that using the Antidote
  tool clears Confusion and removes the swirl. Auto-rescue stays DoT-only
  (a control effect is not lethal by itself).
- `scripts/test_confusion_fx.py` on *current* main behaviour: apply Confusion,
  hold RIGHT, assert the hero does not travel the un-remapped direction;
  assert the swirl is present then gone after cure / expiry; assert Pack
  Antidote clears the kind and the FX. Do not assert reshuffle-or-not, so
  #136 can still retune cadence later.

## 8. Previews

Headless GIFs, 4x scale, written to `/workspace/quintra-monsters/`:

1. Veil Magus: blink, tell, bolt, vanish, reappear.
2. Vault Hand: shadow grow, drop, mash escape, and a second take that carries
   to the foyer.
3. Bane Brute + two status allies: shove into a status body.
4. Leybeam: charge line, wide beam, hero sidestep, cooldown.
   (Zag Dart and Hex Walker still get GIFs in the same folder if a fifth and
   sixth file fit; the required four are the ones above.)

## 9. Proposal only — which starter MAX should own a wide laser? (no code)

Do **not** change any champion in this PR.

Current Max-Will v2 kits (`will_maxfx.c`, PR #137):

- Sauran: Thunderline Bastion — fault-line spear, two shot-eating pylons, slam.
- Vespine: Royal Stinger — lodging poison stinger, pincers, Venom Sac burst.
- Corvin: Murderstorm Eclipse — Night Veil, shadow decoy, four feathers to a
  white X, eclipse flash.
- Wolfkin: Moonfang Cross-Rend — rush, then hanging claws that shear shut.
- Picsean: Tide Vortex — already the bar; v2 only replaced the late roar
  with a surf-crash crest.

**Recommendation: Picsean.** A wide, locked tide-beam (a compressed water
cutter held across a lane) would give the only dedicated magic starter a
straight “I own this line” Max that is visually distinct from the Vortex's
area swirl, and it would match the Leybeam read the player just learned
from the monster. It does not fight Carmelo's “Wolfkin is melee” rule, and
it does not overlap Sauran's already-linear fault spear plus pylon gate.

Runner-up: Sauran, only if a future kit wants a thunder-lance instead of the
pylon slam — but that would compete with the spear that Bastion already
fires. Vespine (venom), Corvin (eclipse burst), and Wolfkin (melee shear)
are worse fits.

## 10. Out of scope

- No deploys, no SD-card copy, no Steam/itch upload.
- No hero kit edits, no Max-Will number changes.
- No Confusion duration / immunity retune (that remains PR #136).
- No new status kinds.

## 11. Review fixes (Carbon, 2026-11-17)

Carbon verdict: ship-with-changes. Cost $0.0578; running logged total $6.5113.
Agreed and applied to the body above, plus:

- Vault Hand also gates on `!run_state_is_miniboss()` and
  `!run_state_was_cleared_boss()`. Mash reads **raw** joypad edges, before
  `status_player_filter_input`. `QSTATUS_STOP` auto-breaks or forbids a grab
  (Stop zeroes D-pad and A/B). Pause `confusion_streak` while grabbed so a
  mid-grab remap does not land as the hero escapes. Killing the Hand mid-grab
  releases the hero and clears hidden/lock flags. Test both.
- Bane Brute grouping **replaces** existing non-status rolled slots rather
  than appending past the room/OAM budget. Ally tiles must be walkable. If
  two status allies cannot be placed, despawn the Brute. Diagonal knockback
  caps at 13 steps (~18 px of diagonal travel) and tries axis slides when a
  corner blocks.
- `ai_data[0]` remains the content id, `ai_data[7]` the materialize shimmer.
  Phase and timers live in `ai_data[1..6]`. `BeamCaster` parameters fit in
  `ai_p0..p2` as (tell, beam, cooldown).
- Confusion swirl is drawn in the hero/HUD overlay OAM path, not via
  `fx_spawn`. Hide it during a Vault Hand carry and during death. Keep it
  across room transitions via `status_player_refresh_visual`. Pack Antidote
  must be usable while confused (pack menu bypasses the D-pad filter, or a
  test proves the tool can still be activated). Auto-rescue stays DoT-only.
  Name the test `test_confusion_fx.py` so it does not collide with PR #136's
  `test_confusion.py`.
- Leybeam stays out of rooms that also roll Slow sources. Restore stamped BG
  immediately if the caster dies or is Stopped mid-beam. Test that restore.
- Max-Will proposal: Carbon agrees Picsean is the right starter for a future
  wide tide-beam. No hero code in this PR.
- Confusion retune merged in PR #136 (`f830836f`) after the first draft of
  this spec. The retune, `confusion_immune`, and `test_confusion.py` are
  now on main and must not be re-implemented. Bank 31 is `powerup_extra.c`;
  new AI is pinned to unused bank 25.
