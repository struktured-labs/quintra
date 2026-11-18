# Quintra desktop notices

## Desktop wrapper

`main.js`, `preload.js` and `renderer/` form one program with Quintra's
browser player and WasmBoy. They are licensed under GPL-3.0-or-later (see
`GPL-3.0-or-later.txt`). Source: https://github.com/struktured-labs/quintra
(`desktop/` and `web/`).

The desktop build links no Steamworks SDK and makes no network requests.

## Electron and Chromium

The app runs on Electron (MIT License, text in `ELECTRON-LICENSE.txt`), which
bundles Chromium, Node.js, V8, FFmpeg and other components. Their licenses
are in `LICENSES.chromium.html`, shipped next to the game executable, and can
be opened from Credits and licenses > Electron.

- Electron: https://github.com/electron/electron
- Chromium: https://www.chromium.org/

electron-builder is a build tool only and is not distributed with the app.

## The cartridge

The bundled `quintra.gbc` is independent cartridge data, not part of the GPL
program. See `QUINTRA-LICENSE-MAP.md` and `CARTRIDGE-THIRD-PARTY-NOTICES.md`.
