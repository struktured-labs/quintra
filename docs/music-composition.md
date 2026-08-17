# Quintra music worksheet

Quintra's cartridge sequencer turns eight authored 16-row ideas into a complete
32-section arrangement. Pulse 2 carries your melody and the wave channel your
bass; the engine adds restrained pulse-1 harmony and biome-specific noise
percussion whenever gameplay sound effects are not using those channels. You
can replace the authored notes and section order without changing the engine.

## What to send

For one track, send:

- Track name and destination (for example `Golden Temple exploration` or
  `Void Lord boss`).
- Tempo in **frames per row**: `3` is intense, `6–8` is normal action,
  `9–10` is spacious. The Game Boy advances at 60 frames/second.
- 128 melody rows: eight 16-row ideas named A through H, using notes such as
  `D5`, `F#5`, `A5`, `~` to hold the preceding lead note without retriggering,
  or `-` for a real rest.
- 32 bass rows, using notes such as `D3`, `A3`, or `-` for a rest. Each bass
  row lasts four melody rows.
- Optionally, a 32-letter `FORM` using A–H. Omit it to start from the
  standard intro/A-B/bridge/development/return form.

Copy this block for a draft:

```text
TRACK: ______________________________
DESTINATION: ________________________
TEMPO: ___  # frames per row

MELODY (128 rows; A=01–16, B=17–32 ... H=113–128)
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
65 __  66 __  67 __  68 __
69 __  70 __  71 __  72 __
73 __  74 __  75 __  76 __
77 __  78 __  79 __  80 __
81 __  82 __  83 __  84 __
85 __  86 __  87 __  88 __
89 __  90 __  91 __  92 __
93 __  94 __  95 __  96 __
97 __  98 __  99 __  100 __
101 __  102 __  103 __  104 __
105 __  106 __  107 __  108 __
109 __  110 __  111 __  112 __
113 __  114 __  115 __  116 __
117 __  118 __  119 __  120 __
121 __  122 __  123 __  124 __
125 __  126 __  127 __  128 __

BASS (32 rows; four changes per 16-row idea)
01 __  02 __  03 __  04 __
05 __  06 __  07 __  08 __
09 __  10 __  11 __  12 __
13 __  14 __  15 __  16 __
17 __  18 __  19 __  20 __
21 __  22 __  23 __  24 __
25 __  26 __  27 __  28 __
29 __  30 __  31 __  32 __

FORM (32 sections; each letter plays the matching 16-row idea)
A A B A | C B D A | B C D B | E F E G
F G H E | C F D G | A C B D | G H B A
```

`F#5` may also be written `FS5`. Keep melody within C5–E6 and bass within
C3–B3 for the current compact frequency table. A rest is `-`; a melody tie is
`~`. Bass rows already sustain for four melody rows, so `~` is lead-only. Do
not add chords to one row, since the cartridge has one melody voice and one
bass voice.
All chromatic pitches in those ranges are available (`C#`, `D#`, `F#`, `G#`,
and `A#`; write flats as their enharmonic sharps). The accompaniment derives
its triad quality from the destination's authored mode, so choose the correct
destination as well as valid pitches.

## Track destinations

| Destination | Track IDs | Current intended character |
| --- | --- | --- |
| Exploration | stages 0–8 | Each dungeon needs its own identity. |
| Boss | bosses 0–8 | More urgent companion to the matching stage. |
| Title | 18 | Ancient, spacious, five-champion myth. |
| Victory | 19 | Bright ascent and release. |
| Game over | 20 | Brief, descending dirge. |

## Tonal and rhythmic identities

| Pair | Tonal field | Sound and motion |
| --- | --- | --- |
| Crystal / Crystal Colossus | D Dorian | Faceted triangle, glass taps, reflected falling cells. |
| Verdant / Briar Crown | E Aeolian | Rounded reed, uneven leaf pulse, climbing and curling lines. |
| Ember / Kilnback Pack & Cinder Rex | A Phrygian | Rounded furnace reed, spacious bellows pulse, the B-flat/A heat rub; the boss hardens it back into a saw-edged cross-rhythm. |
| Frost / Frost Wyrm | G Lydian | Bell wave, suspended gaps, C-sharp/F-sharp ice glare. |
| Mire / Mire Sovereign | F Dorian | Hollow wave, lopsided sinking pulse, chromatic-looking black-key color. |
| Shadow / Shadow Reaper | D harmonic minor | Stalking rests, C-sharp leading tone, blade-like answers. |
| Golden / Sun Golem | C Lydian | Processional reed, F-sharp lift, broad fanfare cells. |
| Bloodmoon / Blood Hydra | A harmonic minor | Ritual saw, dense asymmetric drum cycle, G-sharp invocation. |
| Void / Void Lord | C octatonic | Fractured wave, irregular static, tritones and broken orbits. |

Verdant, Frost, Mire, Shadow, Bloodmoon, and Void redistribute each equal pair
of rows into a track-specific long/short pulse. Crystal, Ember, and Golden stay
straight for contrast; selected bosses inherit or sharpen the corresponding
uneven gait. Because the long and short rows sum to the same duration, swing
changes the feel without shortening the full form or causing room-transition
drift. Authored `~` ties then separate sustained bells, ritual calls, and broad
processional tones from clipped fire and combat figures.

Articulation is part of the composition, not cleanup after the pitches are
written. Every eight-section track must use at least four distinct patterns of
attacks, ties, and rests, with audible breaths and cadences across the full
form. The current 18-track score contains 56 rhythmic profiles across its 144
sections; no profile occupies more than 20 sections, and the old pattern that
retriggers the lead on every row until one final rest is rejected outright.
`scripts/test_music.py` enforces those limits alongside the tonal checks.

The boss must retain enough two- and three-note cells to be recognized as the
dungeon's adversarial answer, but it must not copy the dungeon phrase and add
tempo. Change its rhythm, contour, register, cadence, accompaniment density,
and development path.

The engine restarts a track only when the stage or encounter changes; ordinary
room doors preserve the current section and row. A–D establish the identity;
E–H are separately authored bridge/development material rather than copied
opening bars. The form supplies a soft intro, exchanges, stripped bridge,
development, return, and full cadence. Bosses use denser harmony and percussion
than exploration. Every submitted track is auditioned on the real 128 KiB ROM,
checked against the bank budget, and tested for correct selection before release.

## Validate a draft locally

Save a filled-in block as a plain-text file, then run:

```sh
python3 scripts/music_sheet.py path/to/my-track.txt
```

The checker accepts the numbered layout above (and ignores the row numbers),
rejects wrong row counts and out-of-range notes, and prints the exact compact
note-code and form tables the ROM uses. It **does not modify the game**:
send the sheet or its output back for a reviewed insertion and emulator audition.
Use `python3 scripts/music_sheet.py --self-test` to verify the helper itself.

To audition the current cartridge rather than a host-side imitation, run:

```sh
uv run --with pyboy==2.7.0 python scripts/render_music_preview.py
```

This writes 18 stereo WAVs, a five-minute continuous WAV/Opus audition album,
and a ROM-hash-bound manifest under `tmp/music-preview/`. Each numbered file
joins a full-density opening excerpt to a later development excerpt; the album
places them in stage/boss pairs with a short gap. Boss files retain the live
encounter mix, because musical quality also includes whether attacks and
discovery sounds can coexist with the score. The renderer rejects clipping, an
inaudible mix, identical output files, or a track that changes during capture.

Before a hardware candidate, record every complete form as well:

```sh
uv run --with pyboy==2.7.0 python scripts/render_music_preview.py \
  --full-form --out tmp/music-full
```

This produces an approximately nineteen-minute album that crosses all 32
sections and the real loop boundary of every stage and Colossus score. The
full-form gate rejects cartridge clipping, inaudible or insufficiently dynamic
arrangements, fewer than 24 distinct rendered sections, and live tempo drift
above 0.5%. Timing follows the free-running hardware VBlank epoch rather than
the simulation loop, so a projectile-heavy encounter cannot stretch Ember's
59.7-second score into a 70-second slow-motion version.

The symbolic gate also follows the arranged final section into its restart.
Every loop must return within an octave; a piece that omits the final rest must
voice-lead by unison or octave instead of exposing an arbitrary jump. The
current eighteen forms pass by rests, held unisons, octave returns, one
dominant-like fall, or Blood Hydra's deliberate semitone pull into its tonic.

The printed loop time is the nominal musical duration: `tempo × 512 / 60` for
a gameplay form. At tempo 8 that is about 68 seconds, during which eight
authored ideas recur in changing contexts rather than as one short phrase.
Current exploration arrangements span roughly 60–85 seconds; boss forms span
roughly 43–60 seconds. Compact 32-row drafts remain accepted for title/ending
cues and 64-row sketches remain accepted. Tempo 7–10 is the useful gameplay
range; use rests and section contrast for breathing room instead of stretching
every note.
