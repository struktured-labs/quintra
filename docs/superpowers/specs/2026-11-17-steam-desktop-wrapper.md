# Steam desktop wrapper (Electron, no Steamworks SDK)

Date: 2026-11-17
Status: implementing (branch `steam-wrapper`)

## Goal

Ship Quintra on Steam in December 2026 as a desktop app for Windows x64 and
Linux x64. The app wraps the existing WasmBoy browser player (`web/itch`) in
Electron. It bundles the ROM, needs no network and no itch password, and does
not link the Steamworks SDK.

## Non-goals (December)

- Steamworks SDK, achievements, overlay API calls, rich presence.
- macOS builds (notarization adds risk and review time).
- A second emulator core. WasmBoy stays; see the licensing section.
- Uploading to Steam. App and depot IDs don't exist yet.

## Architecture

```
desktop/
  package.json              pinned electron + electron-builder, npm ci
  main.js                   window, app:// protocol, offline policy, save IPC
  preload.js                contextBridge: window.QuintraDesktop
  renderer/desktop.js       desktop behaviour on top of the web player (GPL)
  renderer/desktop.css      game-only layout, credits overlay
  electron-builder.yml      dir targets for linux-x64 and win-x64
  scripts/stage.mjs         builds/itch-web -> desktop/build/app (+ desktop files)
  scripts/package.sh        stage, electron-builder, depot layout, archives
  steam/*.vdf.template      SteamPipe app_build / depot_build templates
  test/selftest.mjs         xvfb launch, screenshots, save round-trip, pad
```

The web player is built as before with `tools/build_itch_web.sh`. Staging
copies `builds/itch-web` into the app and injects `desktop.css` and
`desktop.js` into `index.html`. The itch build itself is unchanged apart from a
small hook surface in `player.js` (below).

### Loading

- Content is served from a privileged custom scheme `app://quintra/`
  (standard, secure, fetch-enabled), so WASM, workers, `fetch("quintra.gbc")`
  and IndexedDB behave like the hosted page. `file://` is not used.
- Every request that isn't `app:`, `data:`, `blob:` or `devtools:` is cancelled
  in `session.webRequest`. Navigation away from `app://quintra/` and
  `window.open` are denied. There is no network dependency.
- Chromium autoplay policy is set to `no-user-gesture-required` so the game
  starts with sound right away, with no click-to-start screen.
- Renderer: `contextIsolation`, `sandbox`, no `nodeIntegration`. The preload
  exposes a narrow API: read/write save, get/set fullscreen, quit, open the
  Chromium license file, app info.
- A single-instance lock prevents two processes writing the same save.

### Display

- Fullscreen by default. F11 and Alt+Enter toggle windowed mode, as does the
  Settings item "Windowed / Fullscreen". The choice persists in
  `desktop-settings.json` in Electron's userData directory.
- Windowed mode: 1280x800 by default (Steam Deck native), resizable, minimum
  480x432.
- Desktop CSS hides the web page chrome (header, toolbar, touch controls, help
  text). The game stage fills the window, and the existing Fit, Integer and
  Stretch modes size the 10:9 screen inside it (`computeGameRect`).
- The mouse cursor hides after 2 s without movement.

### Input

- The web player's gamepad code is reused unchanged. It is label-correct by
  default: Nintendo layouts read A from the east button; Xbox, PlayStation and
  generic pads read GB A from south and GB B from east (the labels match on
  Xbox). Swap A/B and press-A calibration stay in Settings.
- Settings opens with Esc, the Home button, or holding Select+Start, and adds
  desktop items: Windowed/Fullscreen, Sound on/off, Credits and licenses, Quit.
- Keyboard: arrows/WASD, X = A, Z = B, Enter = Start, Shift = Select.
- Steam Input: ship with Steam's default gamepad template. The game reads the
  XInput/SDL gamepad Steam exposes, so Deck controls work without in-game setup.

### Saves

- The source of truth is one file holding the exact 32 KiB battery RAM:
  - Windows: `%APPDATA%\Quintra\saves\quintra.sav` (Steam root `WinAppDataRoaming`, subdir `Quintra/saves`)
  - Linux: `${XDG_DATA_HOME:-~/.local/share}/Quintra/saves/quintra.sav` (Steam root `LinuxXdgDataHome`, subdir `Quintra/saves`)
- It uses the same 32 KiB layout as the web player's Export save, so a browser
  `.sav` can be copied in directly. Settings also offers "Import browser save"
  (file picker).
- Startup: after WasmBoy loads the ROM, the disk save is injected before the
  first frame. If there's no disk file but WasmBoy's own IndexedDB copy holds
  non-blank RAM, that copy is written to disk once (migration).
- While running, the wrapper polls cartridge RAM every 2 s with
  `_getWasmMemorySection`, which reads the worker's memory without pausing
  emulation. It writes the file when the bytes change. It flushes on quit,
  window close and visibility change. The main process asks the renderer for a
  final flush before exit, with a 3 s timeout.
- Writes are atomic: temp file, fsync, rename. The previous file is kept as
  `quintra.sav.bak`. Reads reject a file that isn't exactly 32 KiB and fall
  back to the `.bak`.
- Save states stay revision-specific in IndexedDB, as on the web, and are not
  clouded.

### Credits and licenses

An in-app overlay, reachable from Settings and navigable with the keyboard or a
gamepad, shows:

- Quintra license map, cartridge notices (GBDK-2020 GPLv2+LE, SDCC).
- WasmBoy GPL-3.0-or-later notice and full license text.
- The Electron MIT license and a button that opens Chromium's
  `LICENSES.chromium.html` (shipped next to the executable).
- A source offer: the browser player and the desktop wrapper (GPL-3.0-or-later,
  one combined program with WasmBoy) and the WasmBoy fork are public at
  github.com/struktured-labs/quintra and github.com/struktured-labs/wasmboy,
  with a written offer to provide the corresponding source for 3 years.

The wrapper's JS (`main.js`, `preload.js`, `renderer/*`) is GPL-3.0-or-later,
like `web/`. The ROM stays independent cartridge data.

## Packaging

- `electron` and `electron-builder` are pinned to exact versions, installed with
  `npm ci` from a committed lockfile.
- electron-builder `dir` targets for `linux` and `win` (x64), `asar: true`, no
  code signing, `signAndEditExecutable: false` so Windows builds need no Wine.
- `scripts/package.sh` sets `SOURCE_DATE_EPOCH` from the HEAD commit time,
  normalises mtimes, and writes sorted tar/zip archives:
  - `quintra-desktop-<version>-linux-x64.tar.gz`
  - `quintra-desktop-<version>-win-x64.zip`
  - plus `SHA256SUMS`.
- SteamPipe layout: `builds/steam/content/{windows,linux}` (unpacked apps),
  `builds/steam/scripts/{app_build,depot_build_windows,depot_build_linux}.vdf`
  generated from the templates. App/depot IDs come from env vars
  (`STEAM_APP_ID`, `STEAM_DEPOT_WINDOWS`, `STEAM_DEPOT_LINUX`). Without them
  they stay `0` placeholders and the script refuses to upload. It never uploads
  anyway; upload steps are documented in `docs/steam-release.md`.

## CI

A new `desktop` job in `ci.yml` needs `rom`. It downloads the `quintra-gbc`
artifact, builds the web bundle, runs `npm ci`, packages both platforms, runs
the xvfb self-test on the Linux build, and uploads the two archives plus
`SHA256SUMS` as workflow artifacts. Nothing goes to GitHub Releases.

## Verification (headless)

`desktop/test/selftest.mjs` launches the packaged Linux app under `xvfb-run`
with `--quintra-selftest=<outdir>` and isolated userData/save dirs:

1. Wait for ready; assert the window is fullscreen; capture `boot.png`.
2. Run about 6 s, press Start, capture `title.png` and `play.png`.
3. Simulated gamepad: override `navigator.getGamepads` with a virtual Xbox pad
   and a virtual Switch Pro pad. Assert the label-correct layouts through
   `QuintraPads.layoutFor`, and assert that the pad's Start (button 9) changes
   the frame.
4. Save round-trip, run 1: import a 32 KiB pattern, flush, assert the disk file
   equals the pattern. Run 2 (same dirs): assert cartridge RAM equals the disk
   file before the first frame.
5. Assert that no non-`app:` request was attempted.

## Risks

- `_getWasmMemorySection` and `CARTRIDGE_RAM_LOCATION` are WasmBoy internals.
  The pinned fork makes them stable. The self-test covers the read path.
- GPL plus a future Steamworks SDK: out of scope. Revisit before adding any SDK.
- Steam Deck runs the native Linux build. Proton isn't needed.
