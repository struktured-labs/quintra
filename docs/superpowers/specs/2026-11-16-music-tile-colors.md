# Music puzzle note colours

Status: **specified.** Each rune-sequence plate shows a unique colour for
its pitch so the phrase can be solved with the sound off.

## Rule

Pitch 0..4 (C5, D5, E5, G5, B5 from `sfx_play_rune`) maps to one fixed
CGB colour wherever that pitch appears: the idle plate, the pressed
plate, and any playback of the same note. A rising or falling phrase
keeps the physical plate's colour; only the required walk order
changes.

The voiced plate still flashes near-white for a few frames, then
returns to its pitch colour (idle or pressed). Audio is unchanged:
volume 15, period-3 decay, a 40-frame CH1 hold, and the 20-frame
delayed solve fanfare.

## Colours

Chosen to differ in both hue and luminance so common red-green colour
blindness still separates them:

| Pitch | Note | Colour | Luminance |
|------:|------|--------|-----------|
| 0 | C5 | deep blue | low |
| 1 | D5 | teal / cyan | mid-low |
| 2 | E5 | gold yellow | high |
| 3 | G5 | orange | mid-high |
| 4 | B5 | magenta | mid |

## Palette budget

A room only has five terrain BG palettes (0..4). Floor, wall, and the
amber crack slot stay in place so ordinary walls and locked doors keep
their looks. While a rune-sequence room is loaded, `BGPAL_CRYSTAL` and
`BGPAL_DOOR` hold packed note palettes:

- Crystal: dark outline, blue (0), cyan (1), yellow (2)
- Door: dark outline, orange (3), magenta (4), flash white

Three plate tiles fill with colour index 1, 2, or 3. Pressed plates
use an inset variant of the same fill so the colour stays readable
after a correct step. Doors and crystals in this room temporarily use
the crack palette, because their usual slots are borrowed. Stage
palettes return on the next room load.

## Evidence

`scripts/test_puzzles.py` asserts that every visible plate in a 3-, 4-,
and 5-note room uses a distinct pitch colour from this map, and that a
voiced plate flashes then restores. Existing rune audio and solve
contracts remain.
