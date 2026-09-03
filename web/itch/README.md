# Quintra browser player

This directory contains the source for Quintra's self-hosted itch.io player.
It forms one browser program with WasmBoy and is licensed under
GPL-3.0-or-later. See `../../LICENSES/GPL-3.0-or-later.txt`.

The vendored browser bundle is built from Quintra's maintained WasmBoy fork,
at commit `1d73f9c54c3401891ddd5fb9303a7ae9da520da9`. The player uses its direct
AudioWorklet path with a 42 ms target, bounded 512-frame blocks, and
acknowledgement-based producer flow control. Its 44.1 kHz context, centered
sample decode, and starvation-only rate guard preserve pitch and avoid
low-level crossover distortion. The fork also includes the Game Boy
wave-channel pitch correction, deterministic startup memory, rendering
regression harness, and Quintra's controller/mobile work.

The launch poster is captured from the current cartridge title and omits the
build-number row so a browser-only deploy cannot advertise a stale ROM.
The shell owns tab suspension so a running game resumes after the player
returns, while WasmBoy's unload handler still preserves cartridge RAM.
Battery RAM uses a stable Quintra-only key and an exact 32 KiB payload, so
browser progress survives cartridge revisions while save states remain
revision-specific.

Gate a built package through real Firefox before publishing:

```sh
python3 -m http.server 8765 -d builds/itch-web
DISPLAY=:0 uv run --with selenium python tools/test_itch_firefox.py http://127.0.0.1:8765/ --headed
uv run --with selenium python tools/test_itch_firefox.py http://127.0.0.1:8765/ --duration 3 --portrait --layout-only
uv run --with selenium python tools/test_itch_persistence.py http://127.0.0.1:8765/
uv run --with selenium python tools/test_itch_cross_rom_persistence.py /path/to/previous/package builds/itch-web
```

Use `--firefox-binary PATH` when the system launcher is a wrapper rather than
the browser executable.

Fork source:
https://github.com/struktured-labs/wasmboy/commit/1d73f9c54c3401891ddd5fb9303a7ae9da520da9

Build the upload directory and ZIP from the repository root:

```sh
tools/build_itch_web.sh
```

The independently compiled `quintra.gbc` file is cartridge data and retains
the component licensing described in `../../LICENSES/README.md`.
