# Quintra browser player

This directory contains the source for Quintra's self-hosted itch.io player.
It forms one browser program with WasmBoy and is licensed under
GPL-3.0-or-later. See `../../LICENSES/GPL-3.0-or-later.txt`.

The vendored browser bundle is built from Quintra's maintained WasmBoy fork,
tagged `v0.8.11-render-harness` at commit
`62fe21fd5781d97f77cd93560d9122d16a6a4eba`. The player uses its direct
AudioWorklet path with a 24 ms target, bounded 512-frame blocks, and
acknowledgement-based producer flow control. The fork also includes the Game
Boy wave-channel pitch correction, deterministic startup memory, rendering
regression harness, and Quintra's controller/mobile work.

Fork source:
https://github.com/struktured-labs/wasmboy/tree/v0.8.11-render-harness

Build the upload directory and ZIP from the repository root:

```sh
tools/build_itch_web.sh
```

The independently compiled `quintra.gbc` file is cartridge data and retains
the component licensing described in `../../LICENSES/README.md`.
