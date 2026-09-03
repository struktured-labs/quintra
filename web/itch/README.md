# Quintra browser player

This directory contains the source for Quintra's self-hosted itch.io player.
It forms one browser program with WasmBoy and is licensed under
GPL-3.0-or-later. See `../../LICENSES/GPL-3.0-or-later.txt`.

The vendored browser bundle is built from Quintra's maintained WasmBoy fork,
tagged `v0.8.13-audio-fidelity` at commit
`f641ef1f318767fffc168f6158e13ea980942ec1`. The player uses its direct
AudioWorklet path with a 42 ms target, bounded 512-frame blocks, and
acknowledgement-based producer flow control. Its 44.1 kHz context, centered
sample decode, and starvation-only rate guard preserve pitch and avoid
low-level crossover distortion. The fork also includes the Game Boy
wave-channel pitch correction, deterministic startup memory, rendering
regression harness, and Quintra's controller/mobile work.

The launch poster is captured from the current cartridge title and omits the
build-number row so a browser-only deploy cannot advertise a stale ROM.

Fork source:
https://github.com/struktured-labs/wasmboy/tree/v0.8.13-audio-fidelity

Build the upload directory and ZIP from the repository root:

```sh
tools/build_itch_web.sh
```

The independently compiled `quintra.gbc` file is cartridge data and retains
the component licensing described in `../../LICENSES/README.md`.
