# Readable hero colour changes (#254)

Date: 2026-11-27. Design only: no code, no build. Line numbers are against
`origin/main` at `0ed13b15`.

## Problem

Owner's hardware playtest: "When the hero changes color, it isn't obvious
what triggered it or what the new color means. The gimmick is a good idea,
but the current design and implementation don't communicate it yet."

Questions to settle: what each colour state means mechanically, what
feedback accompanies the change, whether the first occurrence should teach
it, and whether the trigger is something the player can see and control.

## How it works today

The hero is OAM sprites 0-3, drawn with OBJ palette 1. Every write to those
four sprites' attributes is in `place_player_sprite` (`src/game/room.c:924-964`),
its Convergence helper (`src/game/player_ascended_draw.c:14-27`), room setup
(`room.c:1049-1052`), class select (`class_select.c:138-139`) and the
vignette (`vignette.c:349-350`). So the hero's colour can change in exactly
three ways: OBJ palette 1 is reloaded, the sprites are pointed at a
different palette slot, or the sprites are hidden. Each mechanism below is
one of those.

### 1. Equipment tier (persistent recolour of OBJ palette 1)

- **State.** `room_appearance_tier`, "0 base, 1 blue, 2 red, 3 pearl-gold"
  (`src/game/room.h:80-82`).
- **Rule.** `progression_tier` (`src/game/appearance.c:20-30`) counts
  occupied inventory slots other than Antidote, and reads
  `run_state.bosses_beaten`. Tier 1 at 1 boss or 1 slot, tier 2 at 3 or 3,
  tier 3 at 6 or 6. Whichever is higher wins.
- **What counts as a "relic".** Any occupied slot except Antidote. That
  includes single-use tools: Rift Bomb, Echo Chime and Mirror Shard are
  `Consumable` (`content/src/items.rs:234-256`) and each copy takes its own
  slot (`src/game/pickup.c:594-602`). Duplicate passive relics share one
  slot (`pickup.c:612-622`), so they count once.
- **Palettes.** `class_obj_upgrade_palettes[class][tier-1]`
  (`src/render/class_palettes.c:28-54`). Body colour 1 goes blue, red, then
  near-white; colour 3 keeps the class accent on tiers 1-2 and turns gold on
  tier 3. Tier 0 is `class_obj_palettes` (`class_palettes.c:11-22`).
- **Where it is applied.** `room_refresh_player_appearance(celebrate)`
  (`appearance.c:41-61`) recomputes the tier and reloads OBJ palettes 1
  (hero) and 2 (weapon). Callers with `celebrate = 1`: passive relic pickup
  (`pickup.c:669`), special item grant (`pickup.c:710`), weapon orb swap
  (`pickup.c:1044`), shop weapon (`pickup.c:1206`), Colossus kill
  (`combat.c:231`, after `bosses_beaten++` at `combat.c:174`), Waygear grant
  (`waygear.c:32`), Riftwild shadow item (`riftwild_phase.c:273`). Callers
  with `celebrate = 0`: every room/door/portal/resume identity load
  (`room_music.c:108`, reached through `room_load_dynamic_fx_identity`,
  `room.c:1068, 1113, 1135, 1184, 2193, 2481, 2579`) and the ends of the
  Picsean vortex, Will MAX effects and Wolfkin wave
  (`picsean_vortex.c:321`, `will_maxfx.c:370`, `wolfkin_wave.c:162`).
- **Mechanical effect.** One: the shield catch radius and the shield aura
  orbit grow 2 px per tier (`combat.c:72-73`, `appearance.c:64-65`). Nothing
  else reads `room_appearance_tier` (exhaustive `grep` of `src/`). Stats come
  from the items themselves, not from the tier.
- **Duration.** Until the count changes. It is not monotonic: see gaps.
- **What the player sees and hears.** Only when `celebrate` is set and the
  tier or weapon actually changed: two `SPR_FX_IMPACT` sparks for 14 and 18
  frames and `sfx_play_equip`, a short ping (`appearance.c:54-60`,
  `src/audio/weapon_sfx.c:54-61`). The ping is skipped while a melody lock
  is active (`weapon_sfx.c:57`). No HUD word, no flash, no pose, no pause.
  The identical sparks and ping play for a weapon swap with no tier change.
- **Player control.** Indirect. The player chooses to pick things up and
  kill bosses, but nothing says those are the inputs.

### 2. Status pulse (hero sprites borrow another palette slot)

- **Rule.** While `player_status_kind != QSTATUS_NONE`, the hero alternates
  between palette 1 and a status palette on bit 3 of `entity_anim_counter`
  (`room.c:939-946`). The counter's rate is not verified here.
- **Mapping** (`status_player_palette_prop`, `src/game/status.c:86-101`):
  Poison/Regen slot 7, Burn/Bleed/Brittle slot 4, Slow/Stop slot 3,
  Confusion/Curse/Inversion slot 6, Haste slot 5, Blind/Mute slot 0.
- **These slots are not status palettes.** They are whatever the room
  loaded: 0 skeleton, 3 crawler, 4 heart, 5 coin, 7 orc (`room.c:1008-1013`)
  and 6 the stage's boss palette (`room_music.c:40`, replaced by a return
  palette at `room_music.c:60`). The comments in `status_palette`
  (`status.c:171-186`) call them green/red/blue/violet/gold. Slot 6 differs
  per stage, and the Hexa fight overwrites slots 3-7
  (`src/game/enemy_hexa.c:222-226`, `src/render/hexa_bg.c:113-115`), so the
  "violet" for Curse/Confusion is not guaranteed. Actual on-screen colours
  per stage: not verified.
- **Triggers.** Hostile procs (`status.c:392`), and three the player causes:
  Surge Spark gives Haste for 90 beats (`status.c:103-110`), rest/heal
  fixtures give Regen (`pickup.c:1307`, `pickup.c:1342`), Shadow Veil gives
  Haste for 20 (`magic.c:856`).
- **Effects and durations.** `status_duration` (`status.c:152-169`), in
  8-frame beats; effects are in `status_player_filter_input`
  (`status.c:458-481`), `status_player_effective_stat` (`status.c:483-508`)
  and `status_tick` (`status.c:576-635`).
- **Feedback.** Good. A status FX and SFX on apply (`status.c:193-197, 295`),
  a named HUD notice (`status.c:296`, `src/render/hud_notice.c:372-382`),
  a repeat about every two seconds for harmful kinds (`status.c:609-614`),
  `CURED` on expiry (`status.c:633`), and the Pack names it
  (`status.c:140-150`).
- **`status_player_refresh_visual`** (`status.c:235-238`) does not touch the
  hero. It only re-applies the Blind background dimming.

### 3. Spirit Convergence (tile swap, not a palette change)

- **Trigger.** A+B with full MP and no cooldown (`room.c:1775-1776`).
- **Effect.** Eight spike shots, MP to 0, 45 i-frames, 180-frame cooldown,
  `room_transform_ticks = 135` (about 18 s), screen shake, `SFX_ROAR`
  (`room.c:1777-1795`). The timer counts down at `room.c:1915-1924`.
- **Visual.** The hero switches to the ascended tile set
  (`SPR_CLASS_ASCENDED_BASE`, `room.c:1790-1792`, `src/render/tiles.h:279`).
  Palette slot stays 1. Different art uses the palette's colours in
  different proportions, so the hero can look recoloured without any palette
  write. The Pack shows `ASCEND` seconds
  (`src/game/inventory_waygear.c:175-177`) and `BOOSTED`
  (`src/game/inventory.c:189-193`).
- **Player control.** Full. Deliberate chord.

### 4. Wolfkin Will wave (brief violet load into OBJ palette 1)

`wolfkin_wave.c:105-106` loads `will_flash_palette` into slots 1 and 2 for
`WOLFKIN_WAVE_FX_FRAMES` = 14 frames (`wolfkin_wave.h:16`), then restores
through `room_refresh_player_appearance(0)` (`wolfkin_wave.c:162`).
Wolfkin only, triggered by the player's own MAX attack.

### 5. Hurt and i-frame blink (hide, not recolour)

With i-frames active the hero is hidden on alternating 4-frame windows
(`room.c:926-932`), except during arrival grace and reward ceremonies. HP
loss also sets a 12-frame hurt pose (`src/render/hud.c:160-164`). No palette
change.

### 6. Things that do not recolour the hero

- **Will charge levels.** `will_bank_charge` plays `SFX_COIN` or `SFX_WILL`
  and one spark (`src/game/will_support.c:32-41`). No hero palette write.
- **Power-ups.** HUD word pair, HUD icon/timer and SFX
  (`src/game/powerup.c:188-189, 215-234, 395`). No hero palette write.
- **Run curses.** Spark, shake, `SFX_WEAK`, HUD words
  (`src/game/curse.c:50-55`). The persistent curse flags do not tint the
  hero. Only the short `QSTATUS_CURSE` status does, through mechanism 2.
- **Will MAX effects and Picsean vortex** load OBJ palette 2 (weapon), not 1
  (`will_maxfx.c:406-777`, `picsean_vortex.c:296-348`).
- **Pack screen** forces the base class palette into slot 1
  (`src/game/inventory_visual.c:37`), so the Pack portrait never shows the
  earned tier. It is restored on resume.

### Which one did the owner hit?

Inference, not confirmed: the equipment tier. It is the only change that
persists, it fires on the first relic or first Colossus of every run, and it
is the only one with no words attached. Status pulses name themselves on the
HUD, and Convergence is a deliberate chord. The second candidate is the
status pulse from a self-caused boon (Surge Spark's Haste, a well's Regen),
where the hero flickers to a borrowed palette.

## Gaps

1. **No name.** The tier change shows two sparks and a ping. Statuses,
   curses, power-ups and item pickups all put a word on the HUD notice lane;
   this does not.
2. **Shares its cue.** The same sparks and ping mean "weapon swapped".
3. **Worst possible moment.** The most common trigger is a Colossus kill,
   which already has hit-stop, shake, five explosion sparks, heart SFX and
   drops in the same frame (`combat.c:172-231`). The ping can also be
   swallowed by a melody lock.
4. **Silent changes.** Picking up a consumable returns before the refresh
   (`pickup.c:596-602`), so the recolour lands at the next door with
   `celebrate = 0`: no sparks, no sound.
5. **Silent downgrades.** Using a tool or burning a Phoenix Thread frees a
   slot (`src/game/dungeon_tools.c:97-102`, `phoenix_runtime.c:17-19`). If
   bosses beaten do not hold the tier, the hero drops a colour at the next
   door. Derived from the code; not reproduced in an emulator.
6. **Colour means almost nothing.** +2 px shield radius per tier, undisclosed.
   Blue and red read as "ring upgrades" (the code comment says so,
   `class_palettes.c:24-27`) but grant no defence.
7. **No reference.** Neither HUD nor Pack shows the tier or the next
   threshold, and the Pack portrait reverts to base colours.
8. **Colour collisions.** Tier 1 blue is close to the Slow/Stop pulse
   (crawler blue), tier 2 red to the Burn/Bleed pulse (heart red), tier 3
   gold to the Haste pulse (coin gold). A permanent colour and a 15-second
   warning use the same hues.

## Options

Costs are estimates from reading source; nothing was built or measured.
BG/OBJ tile slots are nearly full and several banks sit near the 256-byte
floor (`scripts/check_rom_layout.py:65-67`), so every option reuses existing
glyphs and systems.

### A. Name it, and make the rule honest

- On a tier change, queue one HUD word through `hud_show_word`
  (`src/game/pickup_notice.c:125-127`): `GEAR 1`, `GEAR 2`, `GEAR 3`. The
  notice alphabet already has G, E, A, R and digits
  (`pickup_notice.c:22-44`). Words placed before `NW_AEGIS` hold 105 frames
  (`hud_notice.c:302-313`).
- Stop sharing the weapon-swap ping. Use an existing reward cue instead,
  e.g. `sfx_play_reward(SFX_REWARD_SIGIL)`, which is exempt from the melody
  lock (`src/audio/reward_sfx.c:28`). Waygear grants already use it
  (`waygear.c:31`), so it is not unique, only different from the ping.
- Rule fixes: consumables stop counting, and the tier never drops within a
  run. Call the refresh from the consumable pickup path so nothing changes
  silently at a door.
- Pack: load the tier palette instead of the base one, and print one line,
  e.g. `GEAR BLUE  NEXT 3`.
- **Player sees.** Kill the first Colossus: hero turns blue, `GEAR 1` on the
  HUD, a distinct chime. Pack explains where they stand.
- **Cost.** 3 words x 6 bytes + 3 palette bytes in bank 17; roughly 30-60
  bytes of logic in bank 7; one text line in the inventory bank. 0 tiles,
  0 palette slots, 0 SRAM. Keeping the tier monotonic needs the high-water
  tier stored: 2 bits in `run_state` (changes the suspend payload) or
  recomputed from a rule that cannot fall.
- **Risks.** The notice queue holds 6 and drops silently when full
  (`hud_notice.c:344-351`); a boss kill is a busy moment. `GEAR 1` names the
  event but not the cause. Bank 7 and 17 headroom not measured.

### B. A plus a visible beat

- Everything in A, plus a white flash of OBJ palette 1 for about 12 frames
  before the new palette lands, using the load-then-restore pattern the
  Wolfkin wave already uses (`wolfkin_wave.c:105-106, 162`), and a short
  hit-stop (`g_hitstop`, as at `combat.c:172`).
- On a Colossus kill, delay the beat until the death explosion ends so it
  is the last thing that happens, not the sixth.
- **Player sees.** Hero flashes white, settles into the new colour, word
  and chime land together.
- **Cost.** A + one 8-byte palette, a frame counter and tick hook: roughly
  80-150 bytes, placement to be chosen by headroom. 0 tiles, 0 SRAM.
- **Risks.** A new per-frame hook near the room hot path (bank 1 has no
  headroom per `powerup.c:278-279`), so it must live in a cold bank behind
  a counter check. The flash must not fight the Wolfkin wave or a status
  pulse for palette 1. Delayed timing adds a state that suspend-resume and
  room exits must clear.

### C. A plus a first-time one-line teach

- The first time a save file reaches tier 1, show one dialog line through
  the existing reward dialog path (`dialog_prepare_reward`, as used at
  `room.c:1271`): "Relics and Colossus kills temper your gear. Blue, red,
  then gold."
- **Cost.** One string (about 60 bytes) plus about 40 bytes of logic, and
  one bit in `meta_flags` (bits 0x08-0x80 look unused,
  `src/game/sram.h:26-29`).
- **Risks.** A dialog pauses play, and on a boss kill it collides with the
  major-reward ceremony that already ends in `SCREEN_DIALOG`
  (`room.c:1251-1261`). Whether the dialog path accepts free text or only
  reward ids: not verified. A new meta bit touches the SRAM checksum path.

### Recommendation

Ship A first. It fixes the two real defects (no name, dishonest rule) for
tens of bytes and no VRAM. Add B's flash only if A still reads weak on
hardware; skip B's delayed timing unless the boss-kill moment proves too
crowded. Hold C until the owner decides whether tier should mean something
mechanically, because the teaching line depends on that answer.

Separate from all three: move status pulses off borrowed palettes, or
accept the collision in gap 8. That is its own spec.

## Open questions for the owner

1. Which change did you see: a permanent recolour after a pickup or boss,
   or a flicker during a status or boost?
2. Should tier mean something mechanical (for example +1 DEF per tier), or
   stay a cosmetic record of the run and say so?
3. Should consumables count? Should the colour ever go down?
4. Are both inputs (relics and Colossus kills) wanted, or should one be the
   rule so the trigger is a single visible event?
5. `GEAR 1/2/3`, or colour names (`BLUE`, `RED`, `GOLD`)?
6. Is a one-time pause for a teaching line acceptable in a roguelike you
   replay, and should it be once per save or once per run?
7. Is the 2 px shield growth intended design or a leftover?

## Test plan

Headless PyBoy, same pattern as `scripts/test_visual_progression.py`
(symbols from the `.noi`, stage states under `tmp/stage-states`).

- `scripts/test_hero_color_readability.py`:
  - Load a stage-1 state at tier 0. Poke one relic into `player.inventory`
    and drive a real pickup; assert `room_appearance_tier == 1`, OBJ
    palette 1 changed, and the window tiles at columns 10-15 of row 0 spell
    the tier word within 2 frames.
  - Kill a Colossus from a boss state; assert the same word appears while
    `hud_notice_ticks` is non-zero, even with the notice lane busy.
  - Pick up a Rift Bomb at tier 0; assert the tier stays 0 across a door.
  - At tier 1 from one relic and no boss, consume the item; assert the tier
    is still 1 after a door and a START resume.
  - Swap a weapon with no tier change; assert no tier word is shown.
  - Open the Pack at tier 2; assert OBJ palette 1 equals the tier-2 palette.
- Extend `test_visual_progression.py` so its four tier palettes stay
  distinct after the change.
- Suspend-save round trip at tier 2: reload, assert tier and palette.
- Layout: `scripts/check_rom_layout.py` must still pass with every touched
  bank above the 256-byte floor.
- Hardware: one owner pass on a real GBC, since palette contrast on the
  panel is what the issue is about.
