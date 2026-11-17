# Steam release: building and uploading the desktop wrapper

This is the runbook for shipping Quintra on Steam with the Electron desktop
wrapper in `desktop/`. The design is in
`docs/superpowers/specs/2026-11-17-steam-desktop-wrapper.md`.

Nothing here uploads anything by itself. You run `steamcmd` by hand after
the Steamworks app exists. **Never set a branch live from a script.** Builds
go live only from the Steamworks site, and only once you choose to.

## 1. Build the packages

You need a ROM and the web bundle first:

```sh
export PATH=$HOME/gbdk/bin:$PATH GBDK_HOME=$HOME/gbdk
make gen && make -j16 rom/working/quintra.gbc
tools/build_itch_web.sh
(cd desktop && npm ci)
STEAM_APP_ID=<app id> STEAM_DEPOT_WINDOWS=<windows depot> STEAM_DEPOT_LINUX=<linux depot> \
  bash desktop/scripts/package.sh
node desktop/test/selftest.mjs        # headless (xvfb) launch, pad, save round trip
```

`package.sh` writes these files:

| Path | What it is |
| --- | --- |
| `builds/desktop/quintra-desktop-<ver>-linux-x64.tar.gz` | Linux build, for testing outside Steam |
| `builds/desktop/quintra-desktop-<ver>-win-x64.zip` | Windows build, for testing outside Steam |
| `builds/desktop/SHA256SUMS` | Checksums for the two archives |
| `builds/steam/content/windows/` | Windows depot content (`quintra.exe` at the root) |
| `builds/steam/content/linux/` | Linux depot content (`quintra` at the root) |
| `builds/steam/scripts/app_build.vdf` | SteamPipe app build script |
| `builds/steam/scripts/depot_build_{windows,linux}.vdf` | SteamPipe depot scripts |
| `builds/steam/output/` | Scratch space for steamcmd logs and cache |

The build is reproducible: mtimes come from `SOURCE_DATE_EPOCH`, which is
the HEAD commit time, and the archives are sorted with gzip and zip
timestamps stripped. Two builds of the same commit give identical SHA256SUMS.
The version string comes from `builds/itch-web/build.json`. To override it,
set `QUINTRA_DESKTOP_VERSION=v1.0.0`.

If the IDs are not set, the VDFs are rendered with `0` placeholders and the
script prints a NOTE. steamcmd rejects app 0, so you cannot upload a
placeholder build by accident. The templates live in `desktop/steam/*.template`.

CI (`desktop` job in `.github/workflows/ci.yml`) builds the same packages,
runs the self-test, and stores them as workflow artifacts
(`quintra-desktop-linux-x64`, `quintra-desktop-win-x64`,
`quintra-desktop-selftest`). CI never publishes a release.

## 2. One-time Steamworks setup (after the app ID exists)

1. **Depots.** Go to Steamworks > App Admin > SteamPipe > Depots. Create one
   Windows depot (OS: Windows, 64-bit) and one Linux depot (OS: Linux +
   SteamOS). Put both IDs in the env vars above. Publish.
2. **Launch options** (Installation > General):
   - Windows: executable `quintra.exe`, OS Windows, 64-bit only.
   - Linux: executable `quintra`, OS Linux + SteamOS.
   - No arguments are needed. The game starts fullscreen. Players can press
     F11 / Alt+Enter, or use Settings > Window mode.
3. **Steam Cloud (Auto-Cloud)** (Application > Steam Cloud):
   - Byte quota 1048576, number of files 10. The save is one 32 KiB file
     plus a `.bak`.
   - Root path: **WinAppDataRoaming**, subdirectory `Quintra/saves`,
     pattern `*.sav`, OS Windows, not recursive.
   - Root override for Linux: original root WinAppDataRoaming, new root
     **LinuxXdgDataHome**, OS Linux, add or replace path `Quintra/saves`.
     With this override, saves sync both ways between Windows and Linux/Deck.
   - Do not sync `.bak`. If you only want the main file, pattern `quintra.sav`
     also works.
   - The wrapper writes `%APPDATA%\Quintra\saves\quintra.sav` on Windows and
     `${XDG_DATA_HOME:-~/.local/share}/Quintra/saves/quintra.sav` on Linux.
     Writes are atomic (temp file, fsync, rename). The save is a raw 32 KiB
     MBC5 SRAM image, which is the same `.sav` format as the browser player's
     export.
   - Publish, then check it with the cloud test below.
4. **Redistributables**: none. Electron bundles everything. Leave all
   "Installation > Redistributables" boxes unchecked.
5. **Steam Input**: the game reads the standard Gamepad API. It is
   label-correct, so Nintendo pads get A on the right, and Xbox/PlayStation
   pads get the confirm button on the bottom. Under Steam Input set
   "Default configuration" to **Gamepad** (the official "Gamepad" template),
   and leave Steam Input opted in for all controller types. Players can still
   use Settings > Swap A/B and Recalibrate.
6. **Steam Deck**: Linux depot with the Steam Linux Runtime. The wrapper
   adds `--no-sandbox` by itself when `chrome-sandbox` is not setuid root,
   because SteamPipe does not keep setuid bits.

## 3. Upload a build (manual)

Install steamcmd. On Debian/Ubuntu:

```sh
sudo dpkg --add-architecture i386 && sudo apt update && sudo apt install steamcmd
# or: mkdir ~/steamcmd && cd ~/steamcmd && curl -sqL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar zxf -
```

Use a dedicated builder account with only "Edit App Metadata" and "Publish
App Changes To Steam" permissions, and Steam Guard on. Then run:

```sh
steamcmd +login <builder_account> \
  +run_app_build "$(pwd)/builds/steam/scripts/app_build.vdf" +quit
```

The first login asks for the Steam Guard code. `app_build.vdf` has
`SetLive ""`, so the upload lands unreleased. Then:

1. Steamworks > SteamPipe > Builds. Find the new build and add a description.
2. Set it live on a **private beta branch** (for example `testing`) and
   install it from that branch in a Steam client.
3. Only once it has passed the checks in section 4, set it live on `default`.
   Do this from the website, never from a script.

## 4. Pre-review checks (Valve's build review looks at these)

- **5-minute play check**: install from Steam on Windows, and on Linux or a
  Deck. Launch it, reach gameplay, play 5 minutes, quit from Settings > Quit
  Quintra, and relaunch. The save must persist.
- **Cloud test save**: Steam Cloud is listed, so confirm a cloud round trip
  from an account in the partner group **with developer mode OFF**:
  1. Save in-game on machine A. Wait for "Cloud sync complete" after quitting.
  2. On machine B (or after deleting the local `Quintra/saves` folder),
     launch. The save must be there.
  3. Check that Steamworks > Steam Cloud > "Recently uploaded" lists `quintra.sav`.
- **Controller**: confirm with Xbox, PlayStation, and a Switch Pro
  Controller. Check the menu confirm/cancel buttons, and Settings opening with
  Home or Select+Start.
- **Redistributables**: confirm none are installed or required. The game
  starts on a clean Windows 10/11 VM.
- **Offline**: the game makes no network requests (the self-test checks
  this), so it runs in Steam offline mode.

## 5. Licensing notes

The wrapper and the browser player are GPL-3.0-or-later. WasmBoy is
GPL-3.0-or-later. Electron is MIT, and Chromium ships its own notices in
`LICENSES.chromium.html` next to the executable. The in-game Credits and
licenses screen (Settings) shows every notice plus a written source offer.
Each build that ships must match a public commit of
`struktured-labs/quintra`. Tag the commit you upload.

The store page's content survey includes the Generative AI disclosure. Some
art in Quintra was made with image-generation tools, so you must disclose it
there.
