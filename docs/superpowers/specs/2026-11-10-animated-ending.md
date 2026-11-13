# Animated ending (spec — not implemented)

Status: proposal for struktured's review. Nothing here is built yet.
Storyboard: `/workspace/ending-mockup/` on the dev box (PNG frames at 4x
nearest-neighbour, plus `storyboard-sheet.png`). The frames are mockups drawn
from the real title-screen champion sprites and the real `font_min` glyphs;
the sky, Rift, sun and sparks are placeholder art.

## What exists today (beta36, `src/game/victory.c`)

| Path | What the player sees |
|---|---|
| Void Lord, 9th Colossus (`bosses_beaten == 9`) | Three text cards, 180 frames each (9 s): `THE RIFT IS BOUND / NINE COLOSSI FALL / FIVE SPARKS RISE`, `THE SPIRITS WAKE / FANG SCALE WING / FIN STING RETURN`, `THE ROADS REMEMBER / DAWN HAS A NAME / QUINTRA ENDURES`. A row of `O + O + O` that shifts every 30 frames, and a palette pulse on colour 2. Then the results page. |
| Hexa Dragmar (sanctum bit, `bosses_beaten == 10`) | One 180-frame card (3 s): `SIX SPARKS UNBOUND / DRAGMAR FALLS / THE SIXTH FALLS`, then results. |
| Endless-descent colossi (10th+ without the sanctum) | Results page only. |
| Credits | None in the ROM. |

Sprites are hidden for the whole screen (`HIDE_SPRITES`). `font_min` has only
space, `0-9` and `A-Z`, so `+`, `=`, `:`, `!` and `.` render as blanks: the
spark row is really `O   O   O`, `VICTORY!` reads `VICTORY`, the time reads
`0 49`, and the prompt reads `START END A DESCEND`.

## Goal

A short, cute, skippable animated ending, 16 s (960 frames) after the Void
Lord, that pays off the title myth: *WHEN THE SKY TORE / FIVE SPIRITS WOKE ...
BIND THE RIFT / ERE ALL NAMES FADE*. The five champions regroup, their sparks
seal the Rift, the night turns to dawn, then the existing results page. It
replaces the three text cards; the results page and its prompts stay.

## Storyboard (Void Lord ending, 60 fps)

| # | Frames | Time | Beat | Text (row 1, ≤ 20 chars) |
|---|---|---|---|---|
| 1 | 0–179 | 0–3 s | **Approach.** Night sky, the Rift is a tall jagged crack in the centre. The five champions walk in from the bottom using their real walk poses (`SPR_CLASS_BASE` / `SPR_CLASS_WALK_BASE`), staggered like the title procession. | `NINE COLOSSI FALL` |
| 2 | 180–359 | 3–6 s | **Sparks rise.** Champions stop in a shallow arc (centre champion highest). Each releases one spark in its class colour that drifts up. | `FIVE SPARKS RISE` |
| 3 | 360–509 | 6–8.5 s | **Bind.** The five sparks orbit the Rift in a pentagon while the crack shrinks in four tile-swap steps (every 32 frames). | `THE RIFT IS BOUND` |
| 4 | 510–629 | 8.5–10.5 s | **Seal.** The Rift collapses to one white star; a single soft palette lift (no strobe). | `EVERY NAME REMAINS` (the answer to *ERE ALL NAMES FADE*) |
| 5 | 630–809 | 10.5–13.5 s | **Sunrise.** Four sky bands ramp indigo → magenta → amber → cream over 16 palette steps; a half sun rises over the hills; champions do little alternating hops (2–6 px). | `DAWN HAS A NAME` |
| 6 | 810–959 | 13.5–16 s | **Regroup.** Champions line up shoulder to shoulder in the centre, one waves (walk pose toggle). | `QUINTRA ENDURES` |
| 7 | 960+ | — | Existing results page (`victory_ending_beat == 3`). | results |

`START SKIPS` sits on row 16 for the first beat only. Frames:
`01-approach-0s.png` … `06-regroup-14s.png`, `07-results-16s.png`.

## After Hexa Dragmar

The player already saw the full ending when the Void Lord fell, so Hexa gets
an 8 s coda, not a repeat (`h1-hexa-coda-sixth-spark.png`):

1. 0–3 s: dawn background from beat 6, the five champions lined up; a sixth,
   magenta spark (Dragmar's) drifts down and joins. `SIX SPARKS UNBOUND`.
2. 3–8 s: six sparks circle the sun once; `DRAGMAR FALLS` on row 15.
3. Results page, with the existing `A` = descend behaviour.

`A DESCEND` after Hexa: verified in PyBoy on the fixed ROM that A returns to
Riftwild with `bosses_beaten = 10`, the sanctum bit cleared and Hexa inactive,
so endless descent is still a coherent offer. Recommendation: keep it, but
consider relabelling to `A KEEP DELVING` on both paths so it does not read as
another boss gate. Decision for struktured.

Endless-descent colossi (11th+) keep going straight to results.

## Controls

- **START** skips to the results page from any frame (same as today); a second
  START on results ends the run to the title.
- The first 20 frames ignore START so the button held for the killing blow,
  or a pause press, cannot skip an ending nobody saw.
- **A** does nothing until the results page (unchanged).

## Frame budget

The GBC frame is 70,224 CPU cycles (140,448 T at double speed; the benchmark
harness budget). The ending has no enemies, collision or AI, so the limit is
VBlank VRAM access, not CPU:

- At most **8 BG tile-map writes per frame** (Rift step = 6 cells; sun step =
  ≤ 8 cells), always inside VBlank, never during a palette write frame.
- At most **2 BG palettes per frame** for the sunrise ramp (4 bands × 16 steps
  spread over 64 frames).
- OAM through the existing shadow-OAM DMA only; 20 objects for champions,
  ≤ 6 for sparks, ≤ 1 for the star.
- Target: the ending's per-frame update under 5% of the frame; add it to
  `bench_crowded_baseline.py` as a scene with a hard "never misses a frame"
  check (0 lag frames over 960).

## Tile, VRAM and OAM budget

- **BG tiles:** at most **48 new 8×8 tiles** (≤ 768 B ROM) for sky band fills,
  hills, Rift (4 steps × ≤ 4 tiles), sun (half + full, ≤ 12 tiles) and star.
  Load them into **VRAM bank 1, BG indices 64..111** (attribute bit 3). Bank-1
  BG 40..55 belongs to Hexa Dragmar; bank-1 BG is otherwise unused, and
  `0x9000`-relative indices 0..127 do not alias OBJ tiles. Text stays on the
  bank-0 `font_min` glyphs (tiles 0..36).
- **Attributes:** the ending owns the whole 20×18 attribute map. It must write
  every visible cell on entry and clear it again (`palette_bg_fill_attrs(0)`)
  before the results page, so nothing leaks (see the victory-screen fix: stale
  Hexa attributes painted the sanctum over the results).
- **BG palettes:** 0 = text/background, 1–4 = sky bands, 5 = hills, 6 = Rift
  / sun, 7 = font mirror (as today).
- **OBJ:** five champions reuse the already-loaded class sprites (OBJ palettes
  1..5, as on the title). Sparks reuse one existing small pickup/shot glyph
  with OBJ palettes 1..5 (+ 6 for Dragmar's magenta spark).
- **10 sprites per scanline:** five 16-px champions side by side is exactly 10
  objects per line, the hardware cap. Sparks and the star must never share
  champion rows; the regroup line (beat 6) must stay ≤ 5 champions wide on
  one row.

## Code shape (when approved)

- New `src/game/ending.c` + `ending.h`, `#pragma bank 255`, every entry point
  `BANKED` (`ending_enter`, `ending_tick`, `ending_done`). `victory.c` keeps
  the screen and calls into it; no new `SCREEN_*` id.
- Data-driven: one `const` table of beats (start frame, text, sprite targets,
  Rift step, palette step) so the timing is reviewable in one place.
- Expected ROM cost ≈ 1.5 KB code + ≤ 768 B tiles + ~200 B tables, in an
  autobank bank (banks 4, 6, 14 have 1.5–1.9 KB free today).
  `scripts/check_rom_layout.py` must pass; no new WRAM beyond ~16 B of state.
- Music: keep `music_play_victory()`; optionally a softer intro for beats 1–4
  and the current cadence from the sunrise. No new audio channels.

## Tests

- Extend `scripts/test_victory.py` and `scripts/test_hexa_dragmar.py`:
  ending length (960 / 480 frames ±1), START skip from frames 0, 20, 500 and
  959, no skip before frame 20, results page reached with clean attributes,
  wins/flags still recorded exactly once.
- Golden PNG per beat (PyBoy, headless) under `evidence/`.
- 0 lag frames across the ending in the benchmark harness.
- Hardware check on rivalmage before release (sprite colours on the real CGB;
  the title already shows two champions dark on hardware but not in PyBoy).

## Open decisions for struktured

1. Length: 16 s Void Lord ending + 8 s Hexa coda, or shorter?
2. Text: keep the six lines above, or reuse the beta36 card lines?
3. Hexa: coda (proposed) or the full ending replayed with six sparks?
4. `A DESCEND` wording after either win.
5. Optional: add `+ : ! = .` glyphs to the console font so the stats read
   `0:49`, `START=END`, `VICTORY!` (separate small change).
