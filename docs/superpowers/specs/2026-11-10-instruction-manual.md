# Quintra instruction manual

Status: **source in tree, built by `make manual`.** This is a production
spec for a booklet and for the Markdown package the struktured labs site
will render. It is not a change to the cartridge.

The manual describes the source at `QUINTRA_VERSION` `v0.20.20` in
`src/game/version.h`. The tree also contains the v0.20.20-beta36 notes.
The cartridge footer prints `v0.20.20`.

## What ships from one source

`docs/manual/content/` is the only prose and picture source.

- `manifest.json` lists order, slug, title, `pdf` role, and `web`.
- One Markdown file per section. No raw HTML, no CSS, no style attributes.
- `images/` holds original PNGs at native size. The PDF build nearest-neighbor
  scales them by an integer. The web preview does not pre-scale; CSS uses
  `image-rendering: pixelated`.
- Every figure is `![alt](images/file.png)` followed by a `Caption:` line.
  The build fails if either is missing.

`snippets/after-the-sanctum.md` is `"web": false`. The HTML export does not
copy it, does not link it, and the build searches the site for the hidden
encounter’s name. A cryptic tease is allowed in the PDF only, in that file.

The public description, on the cover, the title page, and the back cover,
is the site’s line, unchanged:

> nine-stage action roguelike for Game Boy Color, five monster-human champions, procedural dungeons, bullet-hell bosses

Status line: **In development.**

The code agrees with that line: nine stages, five champions, procedural
dungeons, bullet-hell bosses. It also agrees the cartridge is playable from
title to the ninth colossus. “In development” is the site’s status, not a
claim that the game will not boot. Kept as specified.

## Where the site can put it

Intended mount: `/games/quintra/manual/` (`base_path` in the manifest).

- **As content pages.** The Next.js app imports the Markdown and the
  `images/` folder and supplies its own layout. Ignore `"web": false`.
  Do not import `docs/manual/tools/preview.css`.
- **As a standalone folder.** `docs/manual/build/site/` is a static tree.
  Links are relative, so it works at that mount or at any other prefix,
  including a local file server. The mount is recorded in
  `<meta name="quintra-manual-base">` and `manual.json`. There is no
  `<base>` tag, no script, no CDN, and no tracker.

Nothing here is deployed. No ROM link, no itch URL, no password.

## Trim and imposition

**A6, 105 × 148 mm.**

A Game Boy Color carton is a small box. The booklet that sat in one was
close to A6, and A6 is a size a printer can impose without a custom die.
A5 would read more easily and would not fit the carton. The type is 8.5 pt
Noto Serif on an ~80 mm measure, with a 12 mm gutter and a 9 mm outer
margin, so the page stays readable at that size.

Bleed is 3 mm. Crop marks sit in a 6 mm slug and do not cross the fold
into the other page’s trim. The press sheet is 234 × 166 mm (two bleed
pages side by side, slug around them).

The reader PDF is one A6 page per PDF page, no marks. The booklet PDF is
the same pages imposed for saddle stitch:

- outside of a sheet: even page on the left, odd page on the right
  (the outer sheet is page 48, the back cover, beside page 1)
- inside of that sheet: the next odd page on the left, the facing even
  page on the right

Print double-sided, **flip on the short edge**, fold on the vertical
center, nest outer sheet around inner sheets. Page count is forced to a
multiple of 4. The current build is **52 pages**. Three ruled “Field
notes” leaves are inserted before the back cover so the count divides
by four. They are layout, not a Markdown section.

## Page plan

Reader page, then what opens it. Headings start a new page, so a few
leaves are short on purpose (the tease, the notes plate).

| Pages | Section |
|---|---|
| 1 | Cover |
| 2 | Before You Play |
| 3 | The Cartridge |
| 4 | Title |
| 5–6 | Contents, then the generated outline with page numbers |
| 7–8 | Five Sparks |
| 9–11 | Getting Started, including the two cartridge screens |
| 12–14 | Controls |
| 15–16 | The Window |
| 17–21 | Champions |
| 22 | Road Echoes |
| 23–25 | Arms and Relics |
| 26–27 | Merchants and the Forge |
| 28 | Curses and Boons |
| 29–32 | The Road |
| 33–36 | Bestiary |
| 37–42 | Colossi |
| 43 | After the Sanctum (PDF only) |
| 44–46 | Fieldcraft |
| 47 | Credits |
| 48 | Notes, including the reserved painted-cover frame |
| 49–51 | Ruled field notes, added so the count is a multiple of 4 |
| 52 | Back cover |

The web outline is the same list without page 42.

## Art direction

Palette is the cartridge’s own. Champion colors are `class_obj_palettes`
in `src/render/class_palettes.c`. Dungeon and boss colors follow the stage
ramps in `content/src/stages.rs`. Plates are drawn by
`docs/manual/tools/make_art.py`. They are not traces of another game, and
they are not screenshots.

The cover is a pixel plate under a vector wordmark. Body pages are warm
paper (`#f6f0e4`) and brown-black ink, with a rust rule under each title.
Running heads carry the section name. That is the booklet’s layout, not
something stored in the Markdown.

**Effective resolution.** Type, rules, and crop marks are vectors. Every
pixel plate is below 300 dpi effective, because each source pixel is
printed as a block:

- 40 px and 64–96 px plates, scaled ×8: about 38 dpi effective
- the road map, ×7: about 43 dpi
- the 160 px cover, HUD diagram, and reserved plate, ×5: about 60 dpi

The PDF embeds the nearest-neighbor upscale at 300 dpi file resolution so
the blocks stay square. The low figure is the art’s pixel grid, and it is
called out here on purpose. A painted cover would be the piece that wants
a true 300 dpi illustration. The frame for that is
`images/placeholder-painted-cover.png`, labeled RESERVED / PAINTED COVER /
NOT FINAL ART, and it is printed on the notes page.

No third-party picture is used. Noto Serif and Noto Sans are vendored
under `docs/manual/fonts/` with the SIL Open Font License 1.1. They may
be embedded in a commercial booklet. They are not sold by themselves.

## Tooling

`make manual` runs `docs/manual/tools/build_manual.py`.

1. Redraw the plates.
2. Parse the Markdown subset (headings, paragraphs, quotes, lists, images).
3. Emit Typst. Typst 0.13.1 compiles the reader and a bleed-sized press PDF.
4. pypdf imposes the press PDF and stamps crop marks drawn by a second
   Typst file.
5. Typst renders page PNGs. Pillow builds the contact sheet and per-spread
   PNGs.
6. The same blocks become semantic HTML in `docs/manual/build/site/`.

CI job `manual` in `.github/workflows/ci.yml` installs Typst and the two
Python libraries and runs `make manual`. It does not build the ROM. The
job is a compile of text and small PNGs.

Build products are gitignored. The content package, the fonts, and this
spec are what the repository keeps.

## Canon, promoted spec, and proposed lore

**Cartridge canon** (on-screen strings, content tables, or the C that
implements them) includes: the five class names and their starting stats;
Fang Forms, Tail Spike, Featherbarb, BubbleBolt, Stinger; Howl, Stoneskin,
Raven Mark, Tidal Wave, Swarm; Hold Aim and Classic; the Pack cycle; Waygear
and the secondary B weapons; the four curses; Road Echo names and their
ask lines; the nine dungeon names in order; Riftwild as 6×6; Waking and
Hollow; the merchant, smith, apothecary, cartographer, and the quoted
resident lines; Oath names and the behaviors described in Fieldcraft; the
colossus advice quoted from `dialog.c`.

**Title procession, quoted.** The prologue’s seven couplets are the
beats in `title.c` (`WHEN THE SKY TORE` through `REKINDLE THE DAWN`).
The design spec’s longer epithets (Fang of Flame, Scale of Stone, and
the rest) are not used. The glass says “FANG GUARDS FLAME,” “SCALE
HOLDS STONE,” “WING READS SHADOW,” “FIN REMEMBERS TIDE,” and “STING
DEFIES ROT.” “You choose the vessel” restates the last beat.

**Proposed lore for owner review.** Only the PDF-only page:

- “The nine gates can close and the road can still answer.”
- “If the quiet after a win is not quiet, do not trust the second silence.”
- “This booklet will not name what listens.”

Those sentences are color. They are not a description of the encounter,
and the name of that encounter is not in the manual.

## Placeholder art

| File | Where it appears | What to commission |
|---|---|---|
| `images/placeholder-painted-cover.png` | Notes page, and the web Notes section | A painted cover to replace or sit beside the pixel plate. The shipping cover is the pixel plate, which is finished. |

No other frame is empty.

## Facts that do not match, or could not be verified

The manual follows the code when the code and an older sentence disagree,
and names the disagreement here.

- **Oath cost.** `OATH_MP_COST` in `src/game/oath_arts.h` is 1. The Combat
  page prints `A+B OATH: 2 MP`. `CLAUDE.md` also says 2 MP. The booklet
  tells the player the meter spends 1, and mentions the printed 2.
- **Full meter.** A+B at full MP is Spirit Convergence and empties the
  meter. It does not spend the 1 MP cost. That part is in `room.c`.
- **“FEW HEX”.** Easy mode’s class-select line is `EASY MORE HP FEW HEX`.
  Verified Easy changes: maximum health at least 16 (eight hearts),
  attack +4, defense +2, and several patterns eased. No separate “hex”
  rule was found for those two words.
- **Collapsing floors.** `stage_event_resolve_fall` sets health to 0 unless
  the champion is Corvin or owns the Rift Hook, in which case they stumble
  clear. The README’s line that Easy keeps recoverable fall damage was not
  what that function does. The booklet follows the function.
- **Hollow Riftwild.** Verified: Normal adds four bodies, Easy adds two
  (`procgen.c`). The README’s “50% enemy health” and “heavier contact”
  were not found on that path and are not in the booklet.
- **Riftwild size.** Generated `ZELDA_WORLD_W` and `ZELDA_WORLD_H` are 6.
  Older notes that say 4×4 are stale. The booklet says six by six.
- **Boss names.** Crystal Colossus, Storm Serpent, Kilnback Pack, Cinder
  Rex, Frost Spider, Mire Heart, Shadow Reaper, Sun Golem, Blood Hydra,
  and Void Lord are the names in the music cues, motion comments, and
  showcase files. The HUD draws a bar and does not print those titles.
  The motion comment for the first fight also says “Crystal Dragon.”
- **Sun Golem.** The wayfarer line is quoted. The motion switch’s default
  arm is a chase; a separate slam routine was not read line by line.
- **Dread Reaper.** It is enemy 34, a walker, and it is not in the nine
  stage pools. A guarantee about when it appears was not re-derived.
- **Random half-hearts.** The live roll is in `pickup_wildcard.c`: Normal
  about 31/256, Easy about 72/256. An older table inside `#if 0` still
  says 18%. The booklet uses the live roll. Alphas on Normal drop a
  half-heart only at half health or below; otherwise five coins.
- **Title plus sign.** The source string is `SELECT RECORDS+HELP`. `font_min` does not draw the plus, and the captured title shows a gap. The booklet describes the glass.
- **Screenshots.** Two frames were taken with PyBoy 2.7, `window="null"`,
  from a locally linked `rom/working/quintra.gbc` that is not committed:
  the title (`WHEN THE SKY TORE`) and Wolfkin on Normal at class select.
  They are stored at native 160×144 and printed at the same nearest-neighbor
  scale as the other 160 px plates, about 60 dpi effective. No GUI emulator
  was opened. `docs/manual/tools/capture_title.py` repeats the grab. It is
  not part of `make manual` and not part of CI.
- **Hidden encounter.** It exists in the source after the ninth colossus.
  The manual does not name it, diagram it, or explain it. The web build
  has no tease.

## What this spec does not do

It does not change gameplay, tag a release, or publish anywhere.
