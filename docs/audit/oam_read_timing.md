# mGBA Lua OAM read timing — resolved (and the real bug it uncovered)

**Resolution 2026-06-18:** the "per-byte drift in 40-slot loop" theory was
WRONG. Switched dump_oam to `emu:readRange(0xFE00, 0xA0)` (atomic block
read returning a string). That eliminated my probe-vs-runner discrepancy,
which then revealed a **real game-side issue**: Sara's HW OAM slot 1 attr
ALTERNATES between pal 2 (Sara W, correct) and pal 6 (Gargoyle, wrong)
every few frames during the gargoyle_miniboss save.

**Hard evidence:** dump-every-frame trace on
`level1_sara_w_gargoyle_mini_boss.ss0` over 1166 frames showed slot 1 attr
= 0x02 in 490 frames and 0x06 in 676 frames (≈42/58 split). Slot 0/2/3
all stayed at pal 2. Only slot 1 alternates.

This is the same kind of alternation pattern we documented for boss arena
BG attrs (`project_arena_position_sweep.md` — Sara's right-half OBJ slot
gets the boss palette written by ??? mid-frame). The screenshot still
shows Sara as predominantly peach/pink because:
1. LCD renders one specific frame's HW OAM; ~42% chance that snapshot is
   the correct pal2 frame.
2. Persistence-of-vision averages the alternating sprite colours, so the
   user perceives "slightly purple-tinged peach" rather than "flickering
   between peach and blue-gray".

## What's confirmed

1. **Visual = correct.** Screenshot-pixel sampling of `gargoyle_miniboss.png`
   at game coords (72,64)-(88,80) shows (247, 173, 90) peach + (74, 8, 0)
   dark red + (16, 16, 0) near-black. Those match Sara W's OBJ palette
   (`OBP2 = 0000 2EBE 511F 0842`). They do NOT match BGP6/OBP6 (blue-gray
   ~165,165,181).

2. **Single-slot probe = correct.** A focused probe reading ONLY slot 0
   and slot 1 attr at frame 60 (via `-t` state load + same Lua "frame"
   callback timing as the test runner) reports `slot0=0x02 slot1=0x02`
   consistently across f60/62/65 (`/tmp/match_test_runner.log`).

3. **40-slot dump = WRONG.** The test runner reads ALL 40 OAM slots in a
   loop (160 sequential `emu:read8` calls per sample). At frame 60+ in
   gargoyle save, slot 1 attr comes back as `0x06` (boss palette).

## Hypothesis

`emu:read8` is not atomic relative to the emulator core's frame loop —
between iterations of the OAM dump, the core may advance scanlines, and
the game's main-loop OAM rebuild can update HW OAM mid-dump. Slot 0 gets
read at LY=144 (post-recolor), slot 1 gets read at LY=145+ where the game
has had time to overwrite slot 1's attr.

The consensus filter (5 samples in frames 58–68) does NOT fix this because
each sample suffers the same mid-dump drift in the same way — majority
vote across 5 identical-bias samples still loses.

A pre-read busy-loop also doesn't help (the drift is during the dump,
not before it).

## What we ruled out

- Lua `emu:loadStateFile` vs `-t` state-load: both produce the same OAM
  behaviour at frame 60+ in single-byte probes.
- Frame-callback timing relative to VBlank IRQ: LY=144 at callback fire,
  which is post-IRQ — single reads are clean.
- The colorizer logic: trace through `bg_experiment.py.create_tile_based_colorizer`
  for tile 0x25 goes `CP 0x30 carry → low_tiles → CP 0x20 NC → sara_palette`
  → A = D (Sara form palette) = 2 for Sara W. No path produces pal 6 for
  this tile sequence.

## What was fixed (test harness)

- `dump_oam` in `scripts/run_color_regression.py` switched from a 40-slot
  loop of `emu:read8` calls to a single `emu:readRange(0xFE00, 0xA0)`
  block read + Lua string indexing. This is the **atomic block-read
  primitive** mGBA Lua exposes; eliminated the per-byte drift hypothesis
  and made probe results reproducible.

## What's NOT fixed (real game bug — future iteration)

Sara's OAM slot 1 alternation in boss fights. Root cause: somewhere in
the boss-fight path, slot 1's attr gets written to pal 6 (the gargoyle
boss palette E value) when it should stay pal 2 (Sara W form's D value).

Hypotheses to investigate next:
1. **Game writes HW OAM directly.** Even though `rom[0x06D5]` was NOP'd
   to disable the game's OAM DMA, the game's main loop may still write
   attr bytes to `0xFE07` directly (LD [HL], A) for some sprite-management
   reason. Trace WRAM-routine writes to `0xFE07` to find the source.
2. **shadow_main's colorizer is processing only slot 0 from one shadow
   pass and slot 1 from another — a 1-cycle phase issue.** If both
   shadows have slot 1 = pal 6 from the game, then colorizer paints to
   pal 2 in shadow A but DMA copies shadow B (which still has pal 6).
3. **The boss_palette branch fires unexpectedly.** Could happen if
   `tile=0x25` is somehow promoted to >=0x30 in the colorizer's path
   for slot 1 specifically. Trace E/D registers AT EACH OAM SLOT inside
   the colorizer.

Until fixed, the 9 boss-save OBJ tests stay out of the pre-commit hook
because their YAML expectations (Sara=pal2) are objectively correct and
the game IS wrong — but the test would flicker pass/fail with the
alternation. Mark them as `known_flaky_until_alternation_fixed: true`
when widening the hook.

## What's in the hook now

- 6 BG-table tests (banner/cutscene/splash/postboss/2 arena dispatches)
- 6 OBJ tests on STABLE scenes (non-boss `sara_w_alone`/`sara_d_alone`/
  `crow`/`sara_d_hornet_or_moth`/`jet_form_secret_stage`/
  `spiral_power_active`)
- 12 tests total, ~25-30s wall-clock.
