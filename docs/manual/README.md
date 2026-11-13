# Quintra instruction manual

The words and pictures live in [`content/`](content/). That folder is the
single source for the print booklet and for the struktured labs site.
`make manual` reads it and writes a reader PDF, a saddle-stitched booklet,
and a local HTML preview. It does not link the cartridge.

## Content package

`docs/manual/content/`

- `manifest.json` — order, slug, title, and whether a section is in the web
  export. `base_path` is `/games/quintra/manual/`.
- One Markdown file per section. No HTML and no CSS in those files.
- `images/` — original PNGs at native pixel size. Every figure has alt text
  and a following `Caption:` line.
- `snippets/after-the-sanctum.md` — PDF only (`"web": false`). The web
  export omits it. It does not name the hidden encounter.

The site should render the Markdown itself. Two ways to mount it:

1. **Content pages.** Import the Markdown and `images/` into the Next.js
   app and lay them out there. Skip any manifest entry with `"web": false`.
   Links in the preview are not part of the package.
2. **Standalone folder.** `make manual` writes `docs/manual/build/site/`.
   Every link is relative, so the folder can be served at
   `/games/quintra/manual/` or at any other prefix. The intended mount is
   only a `<meta name="quintra-manual-base">` tag and `manual.json`. There
   is no `<base>` element and no JavaScript. The preview stylesheet is for
   local reading; the Next.js site should not reuse it unless someone asks.

Do not put a ROM, an itch build, or a password in this tree.

## Build

```sh
make manual
```

Needs [Typst 0.13.x](https://github.com/typst/typst/releases) on `PATH`
(or `~/.local/bin/typst`), plus Pillow and pypdf. The script redraws the
pixel plates, then compiles.

Outputs, all gitignored:

| Path | What it is |
|---|---|
| `docs/manual/build/pdf/quintra-manual.pdf` | Reader. One A6 page per sheet. |
| `docs/manual/build/pdf/quintra-manual-booklet.pdf` | Saddle-stitch imposition with bleed and crop marks. |
| `docs/manual/build/contact/spreads-contact.png` | Every spread on one sheet. |
| `docs/manual/build/contact/spreads/` | One PNG per spread. |
| `docs/manual/build/site/` | The HTML preview. |

Trim is A6, 105 × 148 mm. The press sheet is 234 × 166 mm: 3 mm bleed and
6 mm of slug for the marks. Print the booklet double-sided and flip on the
short edge, then fold and nest. Page count is a multiple of 4.

Type is Noto Serif and Noto Sans, vendored under `fonts/` with the SIL Open
Font License. Pixel plates are below 300 dpi effective on purpose; the type
and rules are vectors. See the spec for the numbers.

`make manual` does not boot a cartridge. To refresh the two committed
screens, link `rom/working/quintra.gbc` yourself and run:

```sh
python3 docs/manual/tools/capture_title.py
```

That script uses PyBoy with `window="null"`. It does not launch a GUI, and
it does not belong in CI. The `.gbc` stays gitignored.
