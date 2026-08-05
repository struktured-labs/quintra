# Quintra music worksheet

Quintra's cartridge sequencer is intentionally small: one pulse-channel melody
and one wave-channel bass loop. You can compose any replacement in note names;
I will translate it to the Game Boy frequency table and install it without
changing the audio engine.

## What to send

For one track, send:

- Track name and destination (for example `Golden Temple exploration` or
  `Void Lord boss`).
- Tempo in **frames per row**: `3` is intense, `6–8` is normal action,
  `9–10` is spacious. The Game Boy advances at 60 frames/second.
- 64 melody rows, using notes such as `D5`, `F#5`, `A5`, or `-` for a rest.
- 16 bass rows, using notes such as `D3`, `A3`, or `-` for a rest. Each bass
  row lasts four melody rows.

Copy this block for a draft:

```text
TRACK: ______________________________
DESTINATION: ________________________
TEMPO (frames/row): ___

MELODY (64 rows; octave 5–6 is the usual register)
01 __  02 __  03 __  04 __
05 __  06 __  07 __  08 __
09 __  10 __  11 __  12 __
13 __  14 __  15 __  16 __
17 __  18 __  19 __  20 __
21 __  22 __  23 __  24 __
25 __  26 __  27 __  28 __
29 __  30 __  31 __  32 __
33 __  34 __  35 __  36 __
37 __  38 __  39 __  40 __
41 __  42 __  43 __  44 __
45 __  46 __  47 __  48 __
49 __  50 __  51 __  52 __
53 __  54 __  55 __  56 __
57 __  58 __  59 __  60 __
61 __  62 __  63 __  64 __

BASS (16 rows; octave 3 is the usual register)
01 __  02 __  03 __  04 __
05 __  06 __  07 __  08 __
09 __  10 __  11 __  12 __
13 __  14 __  15 __  16 __
```

`F#5` may also be written `FS5`. Keep melody within C5–E6 and bass within
C3–B3 for the current compact frequency table. A rest is `-`; do not add
chords to one row, since the cartridge has one melody voice and one bass voice.

## Track destinations

| Destination | Track IDs | Current intended character |
| --- | --- | --- |
| Exploration | stages 0–8 | Each dungeon needs its own identity. |
| Boss | bosses 0–8 | More urgent companion to the matching stage. |
| Title | 18 | Ancient, spacious, five-champion myth. |
| Victory | 19 | Bright ascent and release. |
| Game over | 20 | Brief, descending dirge. |

The engine restarts a track only when the stage or encounter changes; ordinary
room doors preserve the current exploration phrase. Every submitted track is
auditioned on the real 128 KiB ROM, checked against the bank budget, and tested
for correct stage/boss selection before release.

## Validate a draft locally

Save a filled-in block as a plain-text file, then run:

```sh
python3 scripts/music_sheet.py path/to/my-track.txt
```

The checker accepts the numbered layout above (and ignores the row numbers),
rejects wrong row counts and out-of-range notes, and prints the exact `u16`
frequency tables that the Game Boy uses. It **does not modify the game**: send
the sheet or its output back for a reviewed insertion and an emulator audition.
Use `python3 scripts/music_sheet.py --self-test` to verify the helper itself.

The printed loop time is the nominal musical duration: `tempo × rows / 60`.
For example, a 64-row theme at tempo 8 is roughly 8.5 seconds before it
repeats. Compact 32-row drafts remain accepted for title/ending cues and
sketches, while gameplay replacements should use 64 melody rows and 16 bass
rows. A slower 10–12 or strategically placed rests can give an atmospheric
title cue more air without making the action music drag.
