# Hexa Dragmar — hidden giant after Void Lord

Status: **build spec, verified against main `5f61dc7`.** Owner decisions are
closed in §0. Line citations below were re-checked; where the draft cited a
stale line, the current symbol is named.

Hexa Dragmar is a hidden colossus fought after the ninth boss. It is not a
rename of Void Lord, it does not change `BOSSES_TO_WIN`, and killing it does
not increment the SRAM win counter.

## 0. Closed owner decisions

1. **Naming.** The in-game name of stage 8 stays **Void Lord**. There is no
   `"Penta Dragon"` string in gameplay C or Rust content. Stage 8 is
   `VOID SANCTUM` (`content/src/stages.rs`), dispatched as
   `ENEMY_STONE_SENTINEL` with `ai_data[2] == 8` and giant bit
   `ai_data[3] & 1`. Hexa Dragmar is a new encounter, `ai_data[2] == 9`.
2. **Unlock.** The post-Void-Lord results screen offers the fight on the
   **first clear** when this run has cleared the Stage Reaper and discovered
   the companion. A prior SRAM win is not required.
3. **Wins.** A Hexa kill sets `META_FLAG_HEXA_BEATEN` and may update best
   score. It does **not** increment `wins` or `runs`. `BOSSES_TO_WIN` stays
   9. The three-card epilogue (`THE RIFT IS BOUND` / `THE SPIRITS WAKE` /
   `THE ROADS REMEMBER`) still plays only for `bosses_beaten == 9`.
4. **Audio.** Boss music keeps CH2 and CH3. Hexa SFX may claim only CH1 and
   CH4, and only briefly. No limb waits on an audio channel.

## 1. What the current cart actually does

Verified symbols, not the draft's line numbers:

| Draft claim | Current code |
| --- | --- |
| Giant kill increments `bosses_beaten` and sets `victory` at 9 | `combat_defeat_enemy` in `src/game/combat.c`. Score is doubled when `bosses_beaten >= BOSSES_TO_WIN` **before** the increment. `pending_unseal` and `victory` are set when the post-increment count is `>= 9`. |
| `room_tick` returns `SCREEN_VICTORY` | `src/game/room.c`, `pending_unseal` handling then `if (run_state.victory) return SCREEN_VICTORY`. The draft's 1989–1998 range is the rubble/portal block, not this check. |
| Canonical win records SRAM only at exactly 9 bosses | `victory_enter` in `src/game/victory.c`. Later colossi skip the epilogue (`ending_beat = 3`). Results prompt is `START=END A=DESCEND`. |
| Meta record is 12 bytes, checksum at `[11]` | `src/game/sram_meta.c`. Magic `QM`, version 2, best/runs/wins/best-time, checksum = sum of bytes `[3..10]` stored at `[11]`. |
| Reaper flag | `RUN_REAPER_CLEARED_BIT` is `dungeon_puzzles` bit 2 (`src/game/run_state.h`). |
| Companion discovery | Not a `companion_intro` field. `companion_intro` in `room.c` is a local. Persistence is `companion_cooldown & COMPANION_DISCOVERED_BIT` (`src/game/companion.h`). |
| `dungeon_puzzles` bit 7 | `RUN_WAYSTONE_BIT`. It is not free. Bit 4 and bit 5 are unused. |
| Colossus BG tiles | `BGT_COLOSSUS_VOID..BGT_COLOSSUS_HORN` is **9 tiles** (55–63), and those indices are walkable (`room_tile_walkable`). |
| `boss_voice(stage)` | Returns immediately when `stage >= 9` (`src/audio/boss_voice.c`). |
| `boss_phase_motion` | Already returns 0 for stages 1, 2, and 5. Stage 9 must do the same. |
| SFX channel use | `sfx_play` writes only NR1x and NR4x (`src/audio/sfx.c`). CH2/CH3 stay with music. |
| Projectile motion | `boss_projectile_update` integrates a 32-step sine, not a raw px/tick. `state` 1 / 0 / 3 is slow / medium / fast. |

`RUN_HEXA_SANCTUM_BIT` is therefore **bit 4 (`0x10`)** of `dungeon_puzzles`.

## 2. Unlock and SRAM

### Offer

On the results page (`victory_ending_beat == 3`) after a canonical clear
(`bosses_beaten == BOSSES_TO_WIN`):

- If `RUN_REAPER_CLEARED_BIT` is set and `companion_discovered()` is true,
  the prompt is `START=END A=DRAGMAR`.
- Otherwise the prompt stays `START=END A=DESCEND`.

`A` during a tableau does nothing, matching the current skip contract.
`A` on the Dragmar prompt clears `victory`, sets `RUN_HEXA_SANCTUM_BIT`, and
enters `SCREEN_ROOM`. `room_enter` builds the sanctum instead of calling
procgen when that bit is set and `bosses_beaten` is still 9.

`START` still ends the run from the results page.

### Meta layout (version stays 2)

```
[0..2]   'Q' 'M' version 2
[3..4]   best score
[5..6]   runs
[7..8]   wins
[9..10]  best win time (0xFFFF = none)
[11]     meta_flags
[12]     checksum = sum of bytes [0..11]
```

- Bit 0 `META_FLAG_VOID_LORD_CLEARED` is set when `sram_meta_record` records
  `won == 1`.
- Bit 1 `META_FLAG_HEXA_BEATEN` is set by `sram_meta_note_hexa`. That call
  may raise best score. It does not change runs or wins.

### Migration

If the header is `QM` v2 and byte `[12]` matches the new checksum, the
record is current. Else if byte `[11]` equals the legacy sum of `[3..10]`,
migrate in place:

- `flags = (wins > 0) ? META_FLAG_VOID_LORD_CLEARED : 0`
- rewrite the checksum at `[12]`

A version bump would wipe carts. Do not bump `META_VERSION`.

### Hexa death

The shared defeat path still increments `bosses_beaten` (9 → 10) and sets
`victory`, so the results screen returns. Because the count is not exactly
9, `sram_meta_record(..., won=1)` does not run. `victory_enter` calls
`sram_meta_note_hexa` instead and shows one card, `SIX SPARKS UNBOUND` /
`DRAGMAR FALLS` (`victory_ending_beat == 4`), then the results page.
Results after that card keep `A=DESCEND`. The bit is cleared so a later
room entry is not another sanctum. The score paid for the kill is already
the endless-descent double (`pts << 1`) because `bosses_beaten` was 9
before the increment.

## 3. Arena and body

Playfield above the HUD is 160×128. The sanctum locks the camera:

- `room_world_width = 160`
- `room_world_height = 128`
- `room_camera_x = room_camera_y = 0`
- `room_bg_origin_x = room_bg_origin_y = 0`

The carapace occupies tiles `x = 2..17`, `y = 1..13` (pixels 16..143 by
8..111): **128×104**, which is 80% of the screen width and 81% of the
playable height. The draft's "≥ 75% area" product is 65%; the gate is the
axis span, which is the figure that matches "about 80% of the screen."

`BGT_COLOSSUS_*` tiles are walkable, so the silhouette is not a wall. Only
the five 16×16 limb heads and the 16×16 core have body collision. Border
tiles stay walls. The player starts in the bottom lane.

Limb sockets (pixel anchors of the 16×16 OBJ head):

| Limb | Class | Anchor | 4×4 BG socket (tile x, y) |
| --- | --- | --- | --- |
| 0 | Wolfkin | (32, 72) | (3, 8) |
| 1 | Sauran | (112, 72) | (13, 8) |
| 2 | Corvin | (24, 32) | (2, 3) |
| 3 | Picsean | (120, 32) | (14, 3) |
| 4 | Vespine | (72, 16) | (7, 1) |

OBJ heads move at most ±12 px from those anchors so the scanline bands in
§4 stay inside budget. The draft's ±16 px lunge is clamped for that reason.

## 4. OAM, scanline, VRAM, banks

- OAM 0..3: player.
- OAM 4..23: five limb heads, 4 sprites each, drawn by `hexa_boss_draw`.
- OAM 24..39: projectiles and FX through the existing rotator.
- No extra crown OBJ. A 2×2 crown on the core scanline would push band B
  over the limb cap. The spotlight is BG palette 6 plus OBJ palette 6 on
  that limb only.
- Limb sprites per scanline ≤ 6. Bands: Vespine y≈16 (2), Corvin+Picsean
  y≈32 (4), Wolfkin+Sauran y≈72 (4).
- Hostile projectile cap stays `boss_projectile_has_room` (12 shots). A
  limb that cannot spawn reclaims one hostile shot with `state_timer < 20`
  and still leaves `LIMB_ACTIVE` on schedule.
- VRAM bank 1 tiles 88..127: 5 limbs × 2 poses × 4 tiles, generated at
  sanctum entry. Bank 1 tiles 40..87 stay with the animated Spider, Mire,
  and Hydra poses, and 208..213 stay free for vertical shot glyphs.
  Bank 0 projectile tiles 208..223 are untouched.
- BG palette 5 is the downplayed body. BG palette 6 is the spotlight
  socket only. BG palette 0 is never rewritten by the spotlight.
- OBJ 5 downplayed heads, OBJ 6 spotlight head, OBJ 7 telegraph flash,
  OBJ 0 a 6-frame hit flash that does **not** hide the sprite.
- New gameplay C is `#pragma bank 255` and `BANKED`. The draft's fixed
  bank 9 / 13 / 15 assignments are not followed; autobank is the cart rule.
- `hexa_boss_tick` returns before `boss_phase_tick`, so the generic area
  attack and the 40-tick phase freeze do not run. `boss_phase_motion`
  returns 0 for stage 9.

## 5. Limb FSMs

Each limb ticks every frame except while `g_hitstop` is freezing the room
(the room loop already skips `entity_update_all`). No limb writes another
limb's `state` or `timer`, except the fairness shunt in §6, which only
lengthens a telegraph.

States: `IDLE 0`, `TELEGRAPH 1`, `ACTIVE 2`, `RECOVERY 3`, `BROKEN 4`.

Spawn idle timers: Wolfkin 19, Sauran 43, Corvin 11, Picsean 53, Vespine 31.
After each recovery the idle reload is 37 / 43 / 35 / 41 / 29. Telegraph /
active / recovery for the short attack:

| Limb | Telegraph | Active (A) | Recovery |
| --- | --- | --- | --- |
| Wolfkin | 20 | 18 | 34 |
| Sauran | 24 | 20 | 32 |
| Corvin | 18 | 16 | 30 |
| Picsean | 22 | 14 | 36 |
| Vespine | 16 | 10 | 28 |

Those totals (109, 127, 99, 113, 83) are pairwise coprime, so the limbs
drift. Every third cycle, or the next idle→telegraph while that limb is
spotlighted, selects the signature instead.

Attacks are exaggerated class signatures. Motion uses the existing
`boss_projectile` integrator (`state` 1/0/3), aimed with `dir8 * 4` as the
32-step angle. Bolts and crescents swap `0xE6` / `0x6E` and set
`S_FLIPX` / `S_FLIPY` from the octant.

1. **Wolfkin — Dire Fang / Alpha Howl.** Three parallel spikes on the
   aimed octant (A). Eight-way ring plus a 32 px clear of non-piercing
   player shots around the socket (B). Evidence: Fang Forms
   (`projectile.c` spike lane) and Howl's 8-way ring plus
   `will_howl_clear_nearby_shots`.
2. **Sauran — Longtail / Stoneskin.** Heavy bolt, then three forward
   splinters (A). Signature guard, **28 ticks**: that limb takes 0 damage
   and deflects the shot; the core takes half damage. A hit on Wolfkin or
   Corvin ends the guard. The draft's 72/96 window, plus the fairness shunt
   stretching telegraphs, drops Sauran below four full cycles in 600 frames,
   so the guard is 28 and recovery is 32. Evidence: Tail Spike and Stoneskin.
3. **Corvin — Featherbarb / Raven Mark.** Two `BOSS_SHOT_RETURN` arcs (A).
   A reticle locks `hexa_mark_x/y`, then three bolts converge on it (B).
   The mark is pushed away from a live Undertow shot so its center is not
   within 24 px of that wall. Evidence: Featherbarb return and Raven Mark.
4. **Picsean — Bubble stream / Undertow.** Two staggered slow wave shots
   with a 14×14 hitbox drawn as one orb (A). Four-lane bubble wall; the
   limb absorbs the next player shot (B, 36 ticks). A 4-sprite seed would
   spend the projectile OAM pool on two bubbles, so the hitbox is wide and
   the sprite is the existing 8×8 wave orb. Evidence: BubbleBolt and
   TidalWave's 3-way wall.
5. **Vespine — Stinger / Swarm.** Two fast aimed bolts 10 ticks apart (A).
   Six bolts at 16-tick steps, rotating clockwise from the aimed octant
   (B, 80 ticks). Evidence: Stinger cadence and `will_vespine_swarm_ticks`.

Shared HP is 255. Per-hit cap is 3, or 5 on the spotlighted limb. Each
limb tracks stagger to 60, then breaks for 360 frames (180 decrements on
every other tick), deals 15 bonus HP, clears its tagged shots, and
regenerates. Phase from current HP, using the same thresholds as
`boss_phase_tick` (`<= half`, `<= quarter` of the 255 max stored in
`ai_data[6]`):

- Phase 0 (HP ≥ 128): base cadences. Spotlight 150 on / 90 off.
- Phase 1 (HP ≤ 127): 40-tick roar that clears hostile shots and does
  **not** freeze limbs. Idle reloads shrink by 6. Spotlight gap becomes
  45. The core accepts shots.
- Phase 2 (HP ≤ 63): every 256 ticks the core warns for 48 ticks (markers
  at ±64 px, clamped to the arena) and fires six radial bolts with a short
  life so they expire before the outer lane `y >= 104` or `x <= 24` or
  `x >= 136`.

## 6. Spotlight and the fairness shunt

Spotlight is its own timer. `0xFF` means none. The next limb is
`(last + 1 + (room_counter & 1)) % 5`, skipping `BROKEN`. Expiry restores
palettes even if that limb is mid-attack. The highlighted limb's next
idle→telegraph is its signature. Other limbs' timers are not written.

If three or more limbs are in `TELEGRAPH` and their timers sit within 6
ticks, the third and later limbs in index order gain +10, +20, +30 ticks.
Two limbs may still resolve together. A third does not. This is the only
cross-limb write, and it never shortens or pauses a timer.

## 7. Tests

Headless PyBoy, no mGBA GUI:

1. Unlock preserves the 9-boss win, sets the Void Lord flag, and `A` on
   results enters `ai_data[2] == 9` with the sanctum bit. Without the
   reaper and companion flags, `A` does not.
2. Five limbs each pass IDLE→TELEGRAPH→ACTIVE→RECOVERY at least four times
   in 600 frames, and all five are never `ACTIVE` on the same frame.
3. A spotlight change does not freeze other limb timers.
4. Forcing three telegraphs to timer 10 shunts the third to ≥ 19.
5. Across 600 frames, live OAM ≤ 40, limbs occupy 4..23, and limb sprites
   on any playfield scanline ≤ 6. The non-floor BG box spans at least
   128×104.
6. Phase 2 with all limbs firing reports peak hostile shots and the
   longest gap between `entity_anim_counter` updates. The fight must keep
   advancing.
7. Legacy meta checksums migrate. A Hexa kill sets bit 1 and does not
   change the win count.
8. Spotlight paints only that socket with BG palette 6 and only that head
   with OBJ palette 6. `hexa_audio_ch2_claims` and `hexa_audio_ch3_claims`
   stay 0 while CH1 and CH4 cues fire.

`scripts/check_rom_layout.py` still gates the link.
