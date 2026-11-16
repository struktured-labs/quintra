# Music puzzle note colours

Status: **implemented.** Each rune-sequence plate shows a unique colour for
its pitch so the phrase can be solved with the sound off. A pressed plate
stays visually distinct after the play flash until the phrase resets or
the room is solved.

## Rule

Pitch 0..4 (C5, D5, E5, G5, B5 from `sfx_play_rune`) maps to one fixed
CGB colour wherever that pitch appears: the idle plate, the pressed
plate, and any playback of the same note. A rising or falling phrase
keeps the physical plate's colour; only the required walk order
changes.

The voiced plate still flashes near-white for a few frames, then
returns to its pitch colour — idle if the phrase reset, or the
pressed/latched look if the note was accepted. The pressed look is a
sunken (down-right inset) texture plus a brighter variant of that same
pitch colour, and it persists through later correct steps, revisits,
pause, blindness, and the stage fade. A wrong note restores every
plate to its idle tile and idle colour. After the phrase is solved,
every accepted plate keeps the pressed look.

Audio is unchanged: volume 15, period-3 decay, a 40-frame CH1 hold,
and the 20-frame delayed solve fanfare.

## Colours

Chosen to differ in both hue and luminance so common red-green colour
blindness still separates them. Pressed colours keep the same hue and
move 60% of the way toward white:

| Pitch | Note | Idle colour | Pressed colour |
|------:|------|-------------|----------------|
| 0 | C5 | deep blue | brighter blue |
| 1 | D5 | teal / cyan | brighter cyan |
| 2 | E5 | gold yellow | paler gold |
| 3 | G5 | orange | brighter orange |
| 4 | B5 | magenta | brighter magenta |

## Palette budget

A room only has five terrain BG palettes (0..4). Floor, wall, and the
amber crack slot stay in place so ordinary walls and locked doors keep
their looks. HUD lanes 5..7 are left alone. While a rune-sequence room
is loaded, `BGPAL_CRYSTAL` and `BGPAL_DOOR` hold packed note palettes:

- Crystal: dark outline, blue (0), cyan (1), yellow (2)
- Door: dark outline, orange (3), magenta (4), flash white

Three plate tiles fill with colour index 1, 2, or 3. Pressed plates
use a sunken inset of the same fill, and `puzzle_apply_note_palettes`
brightens only the packed colours whose plates are currently latched.
Doors and crystals in this room temporarily use the crack palette,
because their usual slots are borrowed. Stage palettes return on the
next room load.

Note plate graphics and palettes load only in a rune-sequence room,
and only after the dungeon atlas, so pack resume in any other room
does not spend extra VBlank-bound tile uploads.

## Evidence

`scripts/test_puzzles.py` asserts that every visible plate in a live
3-note (Stage 1) and 4-note (Stage 2) room uses a distinct pitch colour
from this map, that all five packed pitch colours stay unique, that a
voiced plate flashes then restores, and that a correct step stays on
the pressed tile and brighter packed colour until a wrong note resets
the court to idle. Existing rune audio and solve contracts remain.
Five-note layouts are still authored in `prepare_sequence` for Ember
and later, but Stages 3+ currently assign Sun Lattice or Prism Toggle
instead of a rune phrase.
