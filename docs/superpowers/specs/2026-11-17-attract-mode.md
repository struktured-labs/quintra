# Lore intro and attract mode (addendum to the 2026-11-16 spec)

Status: **implemented** (branch `feat/intro-attract`). This covers the intro half of
`2026-11-16-intro-and-stage-vignettes.md` and adds the attract mode it left open
(section 6, decision 1).

Requests (2026-11-16/17):
- "There should be an intro animation too (maybe weaved between the attract mode which we don't yet have)."
- "btw start should skip them."

## Flow

```
power-on -> INTRO (7 shots, ~24.6 s) -> TITLE
TITLE idle 12 s (720 frames, no key held, no records/warp page)
   -> demo run (recorded input) -> TITLE
TITLE idle 12 s -> INTRO replay -> TITLE
TITLE idle 12 s -> next demo -> TITLE ...
```

- After the power-on intro the first attract item is a demo, so the intro does not play twice in a row. When the power-on intro did not play (CUTSCENES OFF), the first attract item is the intro.
- Attract items alternate between intro and demo. Demos rotate: Wolfkin in the Crystal Caverns foyer, then Picsean warped to Verdant Hollow.
- The title idle timer resets on any held key and while the records page or stage-warp page is open.

## Controls
- Power-on intro: A, B or START skips it to the title at any frame. The owner asked for START to skip, so the 20-frame START guard from the original spec was dropped.
- Intro replay and demo: **any** button (including the D-pad and SELECT) returns to the title. The press is consumed, so it does not also start a game.
- During a demo, any *held* real button ends it. The edge in `input_pressed` would miss a press of a button that the demo itself is holding, because `input_prev` holds the demo's keys. At hand-back, `input_keys` is set to the real buttons, so a button held through the switch is not a fresh press on the title.
- On the title, START starts a game as before.

## CUTSCENES setting
- CUTSCENES OFF (meta flag `0x04`, toggled on the AIM page) skips the power-on intro.
- Attract still plays the intro replay with CUTSCENES OFF. It only runs when nobody is playing.

## Demo runs
- Data: `assets/attract/demo_*.json` (class, stage warp, run seed, RLE joypad pairs, position trace). `scripts/record_attract_demo.py --emit` turns them into `src/game/attract_demo_data.h`.
- Recording: a small bot plays an ordinary run in headless PyBoy. The joypad and the player position are sampled at every `input_poll` entry through a PyBoy hook. PyBoy frames and loop iterations do not line up one to one, because busy rooms run below 60 Hz and one frame can hold two iterations. Per-tick sampling drifted after about 50 iterations; per-poll sampling replays exactly.
- Playback: `attract_begin()` sets the class (`player_init_from_class`), `title_stage_warp` and `loop_frame_counter` (the New Game seed), then enters `SCREEN_RUN_INIT` as New Game does. `input_poll()` calls `attract_demo_frame()`, which replaces `input_keys/pressed/released` with the recording on ROOM and DIALOG iterations.
- The demo ends after 900 loop iterations (`ATTRACT_DEMO_FRAMES`, about 15-25 s), on a real button press, or if the run leaves ROOM/DIALOG (for example a death or a map screen). The title then comes back, with the frame counter advanced so the next New Game seed still varies.
- The foyer vignette is muted in demos, since the intro already shows the art.
- **No SRAM writes.** `attract_demo` gates `sram_save_run`, `sram_clear_run`, `sram_meta_record`, `sram_meta_note_hexa`, `sram_meta_set_flag` and the legacy meta migration. A demo leaves the suspend save and the trophies byte-identical.
- Rerecord after gameplay changes that alter the stage 1 or Verdant Hollow opening. `test_attract_mode.py` reports the first iteration where playback leaves the recorded trace.
- A Riftwild stroll was dropped. A stage warp lands at a dungeon entry, and world mode needs a cleared dungeon, so a Riftwild demo would need a crafted mid-run state rather than a seed and inputs.

## Engine
- `SCREEN_INTRO` takes the unused `SCREEN_PROCGEN` slot. `main()` boots into it.
- `src/game/intro.c` (bank 26) holds the shot player and the attract logic.
- Intro art is in `assets/intro/*.png`. `scripts/gen_intro.py` makes `src/render/intro_*.c` in banks 27-29:
  - up to 512 tiles per scene in both VRAM banks, with flip dedup;
  - palettes merged lossily to 7, plus a font palette;
  - text bands drawn on the window layer;
  - data streamed in 32-tile and 4-row steps.
- `loop_switch()` (home) is the screen change, shared by `loop_run` and the demo hand-back in `input_poll`. Home cost is +35 B.
- Moved to bank 26 to keep the 256 B floor in banks 10 and 12: `sram_write.c` and `title_cheat.c`.
- Palette commits wait for a fresh VBlank every time. Starting inside VBlank near LY 153 would spill CRAM writes into line 0. `loop_run` then skips its own wait, because the VBlank epoch moved.
- ROM size is unchanged at 512 KiB, since banks 24-31 were empty.
- `main()` calls `intro_boot_screen()`. It returns the title directly when the intro is muted or CUTSCENES is OFF, and the intro otherwise.
- Test harnesses mute the intro by setting `_attract_mute = 1`:
  - PyBoy (`scripts/quintra_sitecustomize`) sets it from a hook at `main()`'s entry, after crt0 clears WRAM, and then every frame. A muted boot is frame-identical to a build without the intro, with the same title frame, the same `loop_frame_counter` and so the same fixed-frame New Game seeds.
  - The mGBA smoke script has no hook. It writes the byte every boot frame, and the intro's two settle frames catch the write. That path hands the two frames back to `loop_frame_counter`.
  - `attract_mute` also disables the title idle timer.

## Tests
`scripts/test_attract_mode.py` (CI):
- power-on intro plays and hands to the title by itself;
- A, B and START skip at intro frames 0, 20, 500 and 900;
- CUTSCENES OFF skips the power-on intro;
- 12 s idle starts attract, and the order over five cycles is demo, intro, demo, intro, demo;
- A, B, START, SELECT or LEFT each return to the title without starting a game;
- START on the title still starts a game;
- each demo follows its recorded trace exactly (898 iterations), ends on the title by itself, and leaves all 32 KiB of cart RAM and the battery file unchanged;
- pressing A while the demo holds A still exits;
- Continue after a full demo restores the saved hero and run state byte for byte.

`gen_intro.py --check` (CI) keeps the generated intro data current.

## Review
Carbon review 1 (`gemini-4-carbon`, $0.05 logged) was verdict "ship with fixes". Disposition:
- Applied:
  - the exit on a demo-held key, plus keeping the real keys at hand-back;
  - CRAM commits in a fresh VBlank;
  - tests for the demo-held key exit and for Continue after a demo.
- Checked, no change needed:
  - Continue reloads SRAM when it is selected (`title.c` `sram_load_run`);
  - New Game resets `run_state.vignette_seen` (`run_state_init`);
  - meta flags only drive CUTSCENES, not gameplay, so the trophies cannot desync a demo.
- Not changed:
  - **Legacy (v1) meta read during a demo.** Migration runs at the first meta read on boot or on the title, long before attract, so a demo never sees an unmigrated record.
  - **CUTSCENES OFF attract order.** It is documented above as intended.
