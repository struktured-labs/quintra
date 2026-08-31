# Quintra browser player

This directory contains the source for Quintra's self-hosted itch.io player.
It forms one browser program with WasmBoy and is licensed under
GPL-3.0-or-later. See `../../LICENSES/GPL-3.0-or-later.txt`.

The vendored browser bundle is rebuilt from WasmBoy 0.7.1, pinned to upstream
commit `8e96bcb70969d943b1ffc4028b169c835098ce04`, with Quintra's channel-1
double-speed timing and low-latency audio corrections applied. The complete
downstream changes are distributed in the `patches` directory.

The low-latency profile reduces WasmBoy's initial audio lead from 100 ms to
35 ms, caps its queued lead at 80 ms instead of 250 ms, and emits 512-sample
chunks instead of 1024-sample chunks. This keeps enough scheduling headroom
for ordinary browsers while making combat SFX track their visual event much
more closely.

Build the upload directory and ZIP from the repository root:

```sh
tools/build_itch_web.sh
```

The independently compiled `quintra.gbc` file is cartridge data and retains
the component licensing described in `../../LICENSES/README.md`.
