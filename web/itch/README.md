# Quintra browser player

This directory contains the source for Quintra's self-hosted itch.io player.
It forms one browser program with WasmBoy and is licensed under
GPL-3.0-or-later. See `../../LICENSES/GPL-3.0-or-later.txt`.

The vendored browser bundle is the unmodified WasmBoy 0.7.1 npm artifact,
pinned to upstream commit `8e96bcb70969d943b1ffc4028b169c835098ce04`.
Its npm integrity is
`sha512-qgA3bIFAqioYs8kYXtsanIvedgZlZQf382zs3gNlZHIItsAnRzV70/Vp6cJxbK4FyaiG58ah8/g7OW3orrs9Lg==`.

Build the upload directory and ZIP from the repository root:

```sh
tools/build_itch_web.sh
```

The independently compiled `quintra.gbc` file is cartridge data and retains
the component licensing described in `../../LICENSES/README.md`.
