# CLASS_SELECT typography and color

Status: **implemented.** The hero-select page was a nine-line wall of
identical white `font_min` text. Labels are now gold, values stay white,
the selected name and role use that hero's accent, stats sit on one tinted
row, and the Easy hint plus A/B prompts are dim lavender. The screen sets
its own CGB attribute map and commits BG palettes in VBlank the same way
the title commits OBJ palettes.

## Layout (20 columns, 18 rows)

Row 1 is the gold title `CHOOSE YOUR HERO`. Rows 3–7 remain the five-name
list, gold-star cursor, and live 16x16 preview; the selected name is in
the hero accent. Row 8 stays blank. Rows 9–12 are the kit (`ROLE`, `A`,
`B`, `TRAIT`) with gold labels and white values, except the role name
which is also accent-colored and aligned at column 6 with the trait value.
Rows 13 and 15 are blank separators. Row 14 is the compact stat line
`HPnn MPn ATn DFn SPn` (Picsean’s `MP10` drops the space after `HP14` so
the line stays 20 columns; gold letters, white digits). Row 16 is
`NORMAL  SEL FOR EASY` or `EASY MORE HP FEW HEX`. Row 17 is
`A CHOOSE   B BACK`.

## Copy that must fit

`font_min` has spaces, digits, and A–Z only (no `+`, no `>`). Corvin’s B
is `MARK AND RAVEN DIVE`. Picsean’s trait is `FAST MP REGEN`. Vespine’s
trait is `ELEMENT POWER`. Other kit strings are unchanged.

## Palettes

Every class-select BG palette uses deep blue `(0,2,6)` as color 0 so tile
seams stay invisible. `font_min` draws with color 3.

- BG0 body white: existing `cs_palette`
- BG1 label gold: `(0,2,6) (12,8,2) (22,16,4) (31,25,6)`
- BG2 hero accent: color 0 deep blue, colors 1–3 copied from
  `class_obj_palettes[cursor]` and refreshed on cursor move
- BG3 dim lavender: color 3 is `cs_palette` color 2 `(20,16,28)`
- BG4–7 mirror body white so a stray attribute cannot leak title colors

All of the screen's VRAM attribute and palette work happens in VBlank,
one bounded job per frame, from `class_select_vblank_step` (bank 4).
`class_select_tick` calls it first, which is right after `loop_run`'s
`input_poll()` and still at the top of the blank. Nothing is added
between `wait_vbl_done()` and the poll, and `loop.c` is unchanged from
before the restyle. That way input is sampled at the same LY, and
`loop_frame_counter` (the New Game seed) advances exactly as before. The
tick skips the job on frames where A or B is pressed, so the frame that
seeds a run, or returns to the title, does no extra work.

- `render()` (outside VBlank) builds the page-dependent attribute rows:
  the selected name in its accent, and the stat row with gold letters,
  derived from the stat numbers rather than read back from VRAM.
- Attribute jobs 1–6 `memcpy` three finished 20-column rows each into
  VRAM bank 1. Static rows are const templates, so no read-modify-write
  happens inside the blank. The screen never inherits the title
  attribute map.
- Then come 64 palette half-bursts: BG 4 slots, BG 4 slots, OBJ 4 slots,
  OBJ 4 slots per pass, for `PALETTE_OBJ_COMMIT_PASSES` passes. Each
  color re-arms BCPS/OCPS, and the start slot rotates each pass the same
  way as the title's OBJ commit. Mid-frame palette loads are not the
  source of truth.

In PyBoy, every job finishes by LY 151 when started at LY 146. A sweep of
title Start frames 150–400 against A delays 1–90 gives the same
`loop_frame_counter`/seed and later frame counters as main.
`class_select_exit` clears the queue so the next screen's palettes are
not overwritten.

## Non-goals

No gameplay or timing changes. No New Game seed change (do not wait for
VBlank inside `enter`). No new font tiles, no border tiles, no per-frame
palette animation, and no shrink or move of the name list or preview.
