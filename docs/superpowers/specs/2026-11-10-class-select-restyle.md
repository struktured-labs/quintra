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

`class_select_enter` calls `palette_bg_fill_attrs` and then paints the
spans above. It must not inherit the title attribute map. BG (and the
preview/cursor OBJ slots) are written from a WRAM cache during VBlank
after `loop_run`’s `wait_vbl_done()`, re-armed per color, for
`PALETTE_OBJ_COMMIT_PASSES` frames with a rotating start slot, matching
the title OBJ fix. Mid-frame palette loads are not the source of truth.
`class_select_exit` clears both pending commit counters so the next
screen’s palettes are not overwritten.

## Non-goals

No gameplay or timing changes. No New Game seed change (do not wait for
VBlank inside `enter`). No new font tiles, no border tiles, no per-frame
palette animation, and no shrink or move of the name list or preview.
