# Quintra license map

Copyright © 2025–2026 Quintra contributors.

Quintra deliberately separates its reusable software from its original
creative identity. A public source tree does not place every work in the tree
under the same license.

## Software — MPL-2.0

Unless a file says otherwise, the software source code and build/test tooling
in these paths are licensed under the Mozilla Public License 2.0 in the root
[`LICENSE`](../LICENSE):

- `src/`
- `content/`
- `tools/`
- `scripts/`
- `Makefile`

Generated source derived from MPL-covered software remains covered to the
extent it contains that software. When an executable form is distributed,
recipients may obtain the corresponding MPL-covered source from this
repository.

## Creative works — rights reserved

Unless a work carries its own express license, all rights are reserved in
Quintra's original creative works, including:

- visual art, sprites, tiles, animations, logos, and presentation media;
- musical compositions, arrangements, sound effects, and recordings;
- story, dialogue, lore, character writing, names, and descriptive prose;
- game-design documentation, screenshots, trailers, and promotional assets.

This reservation applies when creative data is stored directly in a source
file—for example, tile bytes, sprite patterns, note sequences, dialogue
strings, or generated media. The MPL grant covers the software expression in
such a file; it does not grant permission to reuse independently copyrightable
creative content embedded in it.

The compiled Quintra ROM contains both MPL-covered software and reserved
creative works. Distribution of the ROM by the copyright holders does not
waive the reserved rights in those creative works or restrict the MPL rights
in the corresponding software source.

## Browser player — GPL-3.0-or-later

The future self-hosted WasmBoy fork and code that forms one combined browser
program with it will live under `web/` and be licensed under
GPL-3.0-or-later. The license text is in
[`GPL-3.0-or-later.txt`](GPL-3.0-or-later.txt). A file in `web/` may identify a
different compatible license when appropriate.

The independently compiled `quintra.gbc` ROM is loaded as cartridge data and
is not part of the WasmBoy program. Packaging the two together does not change
the component licenses.

## Third-party works

Third-party components retain their own copyright and license terms. Their
notices must remain with source and binary distributions. No third-party work
is relicensed by this map.

## Branding

No software or content license grants rights to the Quintra name, logo, or
other source-identifying marks. See [`TRADEMARKS.md`](../TRADEMARKS.md).
