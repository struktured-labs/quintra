# Difficulty select labels (2026-11-06)

## Problem

Playtester Brandon (v0.20.20-beta32, itch web, likely Safari) reported
selecting NORMAL on the start / hero-select screen, then playing an EASY
run. He had the same suspicion on 11/4 after beating the first Colossus
in about four hits.

There is no HARD mode. The cartridge only has `DIFFICULTY_NORMAL` (0) and
`DIFFICULTY_EASY` (1). Title has no difficulty row: START opens class
select, A continues a suspend. Difficulty is chosen on class select with
SELECT and applied in `run_init` from `class_select_easy_mode`.

## Root cause

The class-select copy advertised the *next* SELECT target, not the current
mode, and used a `>` glyph that `font_min` cannot draw (it becomes a blank):

- Default (Normal): `SEL EASY MORE HEARTS` and `SPEED 6 SEL EASY`
- After one SELECT (Easy): `EASY MORE HP FEW HEX` and `SPEED 6 SEL NORMAL`

A player who presses SELECT until the screen says `SEL NORMAL` is actually
on Easy. Confirming with A then starts an Easy run. The Pack screen later
shows `EASY`, which reads as the game "reverting" to Easy.

This is a label bug, not a WRAM / SRAM / continue overwrite. `run_init`
stores the toggle correctly, suspend persists `run_state.difficulty`, and
old pre-difficulty saves migrate to Normal (the appended byte is zero).
The web wrapper has no separate difficulty control. The Pack `QUEST` row
sits beside a read-only `EASY`/`NORMAL` label and cannot change the run.

## Contract

- Class select must name the *current* mode with letters the font can draw.
  Default page: a visible `NORMAL`. After one SELECT: a visible `EASY`,
  and not a `SEL NORMAL` string that reads as the current choice.
- SELECT still toggles Easy on and off. A still confirms the visible mode.
- A new run with no SELECT stays Normal (canonical HP/ATK/DEF).
- A new run after one SELECT is Easy (tester HP/ATK/DEF).
- Suspend plus cold CONTINUE must restore the same difficulty byte.
- Do not invent a HARD mode.

## Tests

`scripts/test_difficulty_persist.py` boots through real title/class-select
input, reads the class-select tilemap and `run_state.difficulty`, then
power-cycles the battery image like `test_suspend.py`.
`scripts/test_title_version.py` pins the Wolfkin class-select rows.
