# Quintra browser player

This directory contains the source for Quintra's self-hosted itch.io player.
It forms one browser program with WasmBoy and is licensed under
GPL-3.0-or-later. See `../../LICENSES/GPL-3.0-or-later.txt`.

The vendored browser bundle is built from Quintra's maintained WasmBoy fork,
tagged `v0.8.9-audio-flow-control` at commit
`8726d75662bd9908d638790353e98f216584ac64`. The player uses its direct
AudioWorklet path with a 24 ms target, bounded 512-frame blocks, and
acknowledgement-based producer flow control. The fork also includes the Game
Boy wave-channel pitch correction and Quintra's controller/mobile work.

Fork source:
https://github.com/struktured-labs/wasmboy/tree/v0.8.9-audio-flow-control

Build the upload directory and ZIP from the repository root:

```sh
tools/build_itch_web.sh
```

The independently compiled `quintra.gbc` file is cartridge data and retains
the component licensing described in `../../LICENSES/README.md`.
