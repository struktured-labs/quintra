# Game Over color and death motif

The Game Over screen was a single near-white glyph color on a dark field.
Every line used the same palette, so the title, stats, and prompt read as
monochrome. There was no death image after the short in-room fall beat.

## Motif (original, Quintra)

Do not copy Ultima: Runes of Virtue's skull-and-crossbones. The Quintra
image is the **Nameless Visor**: a tall hollow stone ritual mask carved
from cracked dungeon runes. Eye hollows are two dark vertical rift-slashes
lit by dying ember. A single vertical crack runs down the centre like a
sealed wound, not a jaw. Broken rune chips crumble from the rim as ash.
Behind the mask, two shattered ley-line staves of carved stone cross
loosely — geometric rods, not bones. The lore beat is a name fading
("ere all names fade"), not a cartoon grim reaper.

Art is generated with `gpt-image-2.6-sunburst`, box-downscaled to 160×144,
and quantized to at most three 4-colour CGB palettes (backdrop, stone,
ember). Raw model PNGs stay out of the repo. The committed artefacts are
the generated C tile/map arrays and a small preview sheet.

## Palettes

Colour 0 is a shared deep near-black so glyph cells do not flash a
different backing than the void.

| Slot | Role | Colour 3 (text / highlight) |
|---|---|---|
| 0 | muted blue-grey backdrop and thin frame | cool pale grey |
| 1 | visor stone | bone / ash |
| 2 | ember cracks and eye-slashes | pale gold-white |
| 3 | `GAME OVER` title | pale warm white on ember |
| 4 | stats, record, hint, `PRESS START` | cream on warm gold |

## Sequence (60 fps, skippable)

The in-room 50-frame fall is unchanged. This sequence starts when the
Game Over screen enters.

| Frames | Beat |
|---|---|
| 0–19 | Ember void, input locked so the killing blow cannot skip it. Music starts immediately. |
| 20–79 | The visor truly rises: the top of the mask sits on the well floor and climbs one tile-row at a time through its 10×9 well (rows 4–12, columns 5–14) while palettes fade from black to full. |
| 80–129 | Ember cracks pulse; two to four rune-shard objects fall through the well and expire at its floor so they never sit on the gold text. |
| 130+ | `GAME OVER` is centered on row 2 (ember-red) with row 3 left blank above the visor. Below the visor: optional `TRY EASY MODE` on row 13 when the run was Normal, a centered `RM`/`K`/`T` stats row on row 14, a centered `RUN`/`HI` (or `NEW`) row on row 15, and a centered blinking `PRESS START` on row 16. Every line stays in columns 1–18. Gold for those lower lines. The visor stays, with a slow ember pulse. Shards hide when the text appears. |

START or A after frame 19 jumps to the completed results layout. A second
press returns to TITLE, as today.

## Budgets

- Motif tiles live in **VRAM bank 1**, indices `0..N-1`, `N ≤ 96`.
  Attribute bit 3 selects them. `font_min` stays in bank 0, tiles 0–36.
- Bank 0 tile 37 is a 1-tile muted frame used on the top and bottom bars only. Side columns stay open. Every text line is centered in columns 1–18.
  The frame is never over text.
- Shard objects use four 8×8 tiles in OBJ VRAM and OBJ palette 0.
- New data and loaders live in fixed bank 27 (`gameover_art.c`) so they
  do not land in a bank already under the 256-byte emergency floor.
  `gameover.c` stays in bank 10. Palettes are copied to WRAM on entry so
  fade/pulse code can read them without a bank switch. Home bank is not
  used for this feature.
- On each rise step the visible well is rewritten after one `wait_vbl_done()`
  so the visor can climb from the floor without mid-frame VRAM snow or a white
  LCD-off flash. Fade and ember pulse run in `gameover_draw()` so palette heals
  land in the loop VBlank. `gameover_enter` forces the background map to 0x9800;
  art writes still hit both 0x9800 and 0x9C00.
- No new full-screen paintings beyond this motif. No merge or deploy
  in this change.

## Tests and contracts

`scripts/test_gameover.py` still proves a real combat death, permadeath
across a power cycle, and a clean follow-up run. It is updated to wait
for the results layout (or accept a skip) before reading glyphs, and to
check an authored attribute plane instead of requiring every attribute
byte to be zero:

- `GAME OVER` is centered on row 2, in bank-0 font tiles, title palette, with row 3 blank.
- The Normal hint is the 13-glyph `TRY EASY MODE`, centered on row 13, gold palette, and is omitted on Easy.
- Every results line stays in columns 1–18.
- Music track 20 still starts during `gameover_enter` (within 120 frames).
- Motif cells in the well use VRAM bank 1.
- No stale dungeon attributes remain.

Headless stills and a GIF are captured from a forced death for review.
