# Quintra itch.io beta deployment spec

Status: first implementation draft, 2026-08-30  
Target release: free or pay-what-you-want browser beta, with the raw `.gbc` ROM
available as a separate download  
Current cartridge: `v0.20.18`, SHA-256
`e8690e387c32c0ab6f2ee2dabc7b7f5cd4e14b64284957d8646526e24b424c6b`

## Decision

Build the first beta around a **self-hosted WasmBoy fork and a Quintra-specific
browser shell**. Do not use the externally hosted WasmBoy iframe: the ROM,
emulator, player, saves, and license/source links must all ship in our package.

WasmBoy is browser-native, explicitly designed for homebrew embedding on
itch.io, and already supplies a responsive canvas, Web Audio, Web Workers,
keyboard/gamepad input, and save support. Upstream also warns that it is
pre-1.0 and not fully accurate. That is an invitation to test and improve it,
not permission to ship known emulation faults. The exact Quintra ROM must pass
the compatibility matrix; general emulator defects should be fixed in our
GPL-3.0-or-later fork with focused regression coverage and offered upstream.

SameBoy remains the desktop accuracy oracle and hardware comparison point.
binjgb remains the small MIT-licensed fallback used to distinguish a WasmBoy
defect from a ROM defect. A SameBoy web port is the last resort because
upstream does not publish an official browser frontend.

References:

- [itch.io HTML5 upload requirements](https://itch.io/docs/creators/html5)
- [itch.io butler push and channel rules](https://itch.io/docs/butler/pushing.html)
- [WasmBoy upstream](https://github.com/torch2424/wasmboy)
- [SameBoy upstream](https://github.com/LIJI32/SameBoy)
- [binjgb browser embed and capabilities](https://github.com/binji/binjgb)

## Product shape

The itch page should offer two ways to play the same hash-bound candidate:

1. **Play in browser** — the WebAssembly emulator autoloads `quintra.gbc`.
2. **Download cartridge ROM** — the same ROM for Analogue Pocket, flash carts,
   and desktop emulators.

The page should be free or pay-what-you-want during beta. itch treats payments
on HTML games as donations; selling access would require a Downloadable-kind
page instead. Do not mark the ROM download as Windows, macOS, or Linux merely
because emulators exist on those platforms.

Suggested first-page state:

- visibility: restricted/unlisted while the browser candidate is tested;
- release label: `Quintra Beta v0.21b1` once the in-game version is bumped;
- browser channel: `web` — choose once and never rename it;
- ROM channel: `rom`;
- click-to-play: enabled, so browser audio starts from a user gesture;
- desktop embed: responsive 10:9 canvas, starting around 640×576;
- fullscreen button: enabled;
- mobile-friendly: disabled until touch, audio, rotation, and save persistence
  pass on real iOS and Android devices.

The proposed itch target is `struktured/quintra`, but the account and page slug
must be confirmed before the first push. The channel name is effectively part
of the public deployment identity, so the deploy script must not invent or
rename it.

## Package contract

The generated directory—not a hand-built ZIP—is the source uploaded by butler:

```text
builds/itch-web/
├── index.html                 # mandatory, at upload root
├── quintra.gbc                # exact tested release ROM
├── quintra.sha256             # ROM integrity record
├── build.json                 # version, git commit, ROM/core hashes
├── emulator/
│   ├── wasmboy.js
│   ├── wasmboy.wasm
│   ├── quintra-player.js
│   └── quintra-player.css
├── licenses/
│   ├── GPL-3.0-or-later.txt
│   ├── QUINTRA-LICENSE-MAP.md
│   └── THIRD-PARTY-NOTICES.md
└── media/
    └── cover.png
```

All paths must be relative and case-correct. The package must be fully local:
no CDN scripts, analytics, remote emulator iframe, remote ROM request, or font
request. itch serves HTML builds from a subdirectory and absolute asset paths
will fail.

`build.json` is the browser package's identity seam:

```json
{
  "version": "v0.21b1",
  "gitCommit": "<full commit>",
  "romSha256": "<sha256>",
  "emulator": "wasmboy-quintra",
  "emulatorCommit": "<pinned upstream commit>",
  "channel": "web"
}
```

The build must vendor a pinned, reviewed emulator revision. Never fetch
`latest` during packaging.

## License boundary

Quintra's software source and build tooling are MPL-2.0. Original game art,
music, writing, media, and branding remain separately protected. The WasmBoy
fork and the browser shell that forms one program with it are
GPL-3.0-or-later. The independently compiled ROM is cartridge data loaded by
the emulator, not a linked part of the browser program.

The itch package must include the complete license map and GPL text plus a
prominent link to the exact corresponding WasmBoy/player source revision and
reproducible build instructions. Every modified WasmBoy file must retain
upstream attribution and identify our changes. See `LICENSES/README.md` for the
repository-wide component map.

## Player shell

The shell should frame the game, not compete with it. Required controls:

- D-pad: arrows or WASD;
- GBC A: `X` / primary gamepad face button;
- GBC B: `Z` / secondary gamepad face button;
- Start: Enter;
- Select: Shift or Backspace, avoiding Tab because browsers reserve it for
  focus navigation;
- fullscreen and mute buttons outside the canvas;
- a compact controls panel visible before launch and reachable during play;
- touch controls only when a touch-capable device is detected.

Prevent default browser scrolling only while the game canvas has focus. Pause
or mute when the tab becomes hidden. The canvas must integer-scale whenever
possible, preserve the 160×144 aspect ratio, and use crisp nearest-neighbor
rendering. Do not add shader blur, fake LCD persistence, or a decorative shell
to the first beta.

The browser UI should say clearly that the game itself is a real Game Boy Color
cartridge and that browser play is an included emulator convenience.

## Battery SRAM is the critical risk

Quintra uses MBC5 with 32 KiB battery RAM. A browser build is unacceptable if
the emulator can appear to save but lose SRAM on refresh, tab close, browser
restart, or a new deployment.

The player adapter must:

1. load battery SRAM from IndexedDB before starting the ROM;
2. write dirty SRAM to IndexedDB on the emulator's battery-save callback;
3. request a flush after in-game suspend/save events where the core exposes
   one;
4. keep a stable database and key namespace across beta versions;
5. provide explicit **Export Save** and **Import Save** controls using the
   standard 32 KiB `.sav` payload;
6. never silently replace an existing save because the ROM filename or page
   version changed.

LocalStorage is not the primary save store. It can hold tiny UI preferences,
but the cartridge save belongs in IndexedDB as binary data.

The save schema should be keyed by a stable cartridge identity such as
`quintra:mbc5:sram:v1`, not the changing ROM hash. The current ROM's own SRAM
migration logic remains responsible for older save contents.

## Deployment gates

`tools/deploy_itch.sh` should be publish-off-by-default and run these stages in
order:

1. build the cartridge;
2. run the release-critical ROM checks;
3. assemble a clean `builds/itch-web/` directory;
4. verify the ROM hash in `build.json`, `quintra.sha256`, README media manifest,
   and packaged ROM all agree;
5. verify `index.html` is at the upload root and every referenced asset exists;
6. reject remote URLs in HTML, CSS, and JavaScript;
7. report file count, extracted size, and largest file;
8. enforce itch limits with headroom: fewer than 1,000 files, under 450 MB
   extracted, no file over 180 MB, and paths under 220 characters;
9. run desktop browser smoke in Chromium and Firefox;
10. run the battery save round-trip test;
11. optionally run `butler push-preview --changes-only`;
12. push only when explicitly invoked with `--publish`.

The final command should be equivalent to:

```sh
butler push builds/itch-web struktured/quintra:web --userversion v0.21b1
```

The first experimental push should add `--hidden`. itch only honors `--hidden`
when creating a new channel, so later deployments need page visibility managed
through the itch dashboard.

Cowir's deployment lane supplied three hard-won constraints that this spec
adopts directly: never rename a live channel, gate the 200 MB per-file ceiling
in code, and require an explicit publish flag after every other check passes.

## Browser acceptance matrix

The beta candidate must pass these tests against the exact packaged directory,
served over HTTP rather than opened as `file://`:

| Surface | Required proof |
|---|---|
| Chromium desktop | boot, controls, audio, suspend, reload, Continue |
| Firefox desktop | boot, controls, audio, suspend, reload, Continue |
| Safari desktop | manual boot/audio/save check before public beta |
| Gamepad | D-pad, A/B, Start/Select, disconnect/reconnect |
| Keyboard | no page scroll or focus trap while playing |
| Fullscreen | integer-scaled canvas and restored focus on exit |
| Save migration | existing `.sav` imports and survives reload |
| New build | deploy a changed shell without losing prior SRAM |
| Performance | stable audio and full-speed play in a projectile-heavy room |
| Long session | 30-minute run with no audio drift or growing memory use |

The automated save test should create a recognizable save, reload the page in
the same browser profile, choose Continue, and assert the restored run state.
This follows Cowir's measured lesson: only a real browser round-trip catches an
asynchronous persistence path that reports success but never reaches IndexedDB.

## Emulator go/no-go probe

Before building the polished shell, package the current ROM in bare WasmBoy and
test these Quintra-specific risks:

- CGB-only boot and cartridge header handling;
- MBC5 banking across the full 256 KiB ROM;
- all four audio channels, music transitions, and dense SFX priority;
- sprite/background priority in bosses and Riftwild phase transitions;
- timer behavior during projectile-heavy rooms;
- SRAM write, reload, export, import, and existing-save migration;
- keyboard and common XInput/PlayStation-style controllers;
- 30-minute stability in Chromium and Firefox.

Any progression, audio, rendering, or save defect is a **no-go**, not a known
beta limitation. Reproduce failures against SameBoy/hardware and binjgb, reduce
them to emulator-focused cases where possible, fix our pinned WasmBoy fork,
and offer generally useful fixes upstream. If WasmBoy cannot be made reliable
within the beta budget, ship binjgb only after it independently passes the same
matrix. A SameBoy/libretro web frontend is a separate engineering project, not
packaging work.

## Page assets and copy

Reuse the exact repository-generated media instead of recapturing by hand:

- `docs/media/gameplay.gif` for the page trailer;
- `docs/media/title.png` for the cover seed;
- `docs/media/boss-gallery.gif` for the boss section;
- `docs/media/riftwild-map.png`, `village.png`, and `dungeon.png` for the
  screenshot strip.

The page needs a short beta disclosure: balance, boss sprite refinement, and
late-game polish remain active; save compatibility is intended but beta
backups are recommended. Link the GitHub repository, controls, issue tracker,
ROM hash, and third-party emulator source/license.

## Implementation sequence

1. Pin and vendor a WasmBoy revision; preserve GPL notices and record its
   source revision.
2. Produce the bare local package and run the emulator go/no-go probe.
3. Fix Quintra-visible emulator defects with regression tests; offer generic
   repairs upstream without blocking our pinned fork on review latency.
4. Implement the GPL Quintra player shell and stable control mapping.
5. Implement IndexedDB SRAM plus import/export.
6. Add Playwright boot, input, and save-round-trip tests.
7. Add corresponding-source, package-integrity, and size gates.
8. Add publish-off-by-default butler deployment.
9. Create the restricted itch page and permanently reserve the `web` channel.
10. Upload the hidden first candidate and test inside itch's iframe.
11. Bump the game to the beta version, rebuild ROM/media/package from one
    commit, and publish only that exact candidate.

## Open decisions before the first push

- Confirm itch account and page slug (`struktured/quintra` is only proposed).
- Confirm free vs pay-what-you-want; this spec recommends PWYW with zero
  minimum for beta.
- Decide whether the raw ROM download is public on day one or limited to beta
  testers.
- Keep the public beta version bound to the linked cartridge hash; never
  relabel a prior cartridge without rebuilding it.
- Decide whether mobile is in beta scope after touch/save tests, not before.
