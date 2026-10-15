# Cold-resume sprite colors

Reported: black monsters and pickups in the itch browser build.

Cause: `stage_seen` started at zero, which is also the first dungeon's index.
A cold battery resume beyond room zero skipped the stage-identity upload. OBJ
palette 6 and the stage sprite atlas were uninitialized. WasmBoy's deterministic
zero startup made affected actors black; PyBoy exposed unrelated initial colors.
This is a ROM bug, not a WasmBoy/WebAssembly rendering defect.

Fix: initialize `stage_seen` to `0xFF`, the existing no-stage sentinel. No save
format, emulator, gameplay, or controller changes.

- Broken ROM: `351dc43c717b41f7b42cbf154dfd75934e14220d6eb47c45a3b36ae2ec1e5c9e`.
- Fixed ROM: `57321748552396f336fae31f0705397d4a9daa51b32db8430f5972e8566b1978`.
- Web package: `v0.20.19-beta29`, same WasmBoy 0.8.14 bundle.
- Native fixture: staged first-dungeon court, cartridge-written battery save,
  new emulator instance, ordinary title Continue input. Both palette bytes and
  stage atlas match the pre-power-cycle identity after the fix. Parent fails.
- Browser fixture: import the same 32 KiB battery file, reload page, Continue,
  then open and close Pack. Parent palette 6 stays all-zero; candidate has the
  expected `[0,0,67,73,36,127,255,83]` throughout settled gameplay.
- Browser raw memory/screen evidence: `builds/color-probe-beta28-cold-resume/`
  and `builds/color-probe-beta29-cold-resume/`. The first exploratory probes used
  cached save-state memory; final probes read live WASM palette memory directly.
- Native evidence: `builds/resume-palette-351dc43c/` and
  `builds/resume-palette-57321748/`.

Passing checks: resume palette/atlas regression, battery suspend, gameover and
clean restart, Firefox launch/audio/fullscreen/input-release smoke test, browser
save persistence, static package/gamepad tests, package version/cache keys.
No hardware test or hardware deployment. Earlier ordinary-room and Serpent
performance failures remain open; this patch does not claim to fix them.

Itch publication is scoped to the existing `struktured/quintra:web` channel;
visibility, price and access settings are unchanged. Package metadata explicitly
records `sourceDirty: true`: this ROM includes uncommitted boss-overhaul work.

Published and verified: itch build `2049723`, upload `19038687`, beta29.
The hosted CDN ROM hashes to the fixed ROM above. The same saved-game
palette/menu test passes against the hosted page; evidence is in
`builds/color-probe-beta29-hosted/`. Visibility, price and access were unchanged.

All nine bosses were freshly recaptured from the fixed ROM in
`builds/boss-phases-57321748-97b05c62/`. `collage.html` is the animated nine-card
overview; `index.html` retains all 61 phase/transition/mechanic cards. Browser
checks cover video dimensions, playback and pause; the gallery retains its
earlier stationary/protected-player fixture disclosure.
