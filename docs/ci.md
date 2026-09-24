# CI and releases

Pull requests and pushes to `main` get a pass/fail signal from
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml). Version tags publish
a GitHub Release. Long controller soaks run on a schedule and do not gate
merges.

The Makefile's GBDK location defaults to `/home/struktured/gbdk`. Override it
with the `GBDK` environment variable or `make GBDK=/path/to/gbdk`. CI points
that at a cached GBDK-2020 4.5.0 tree.

## What gates a pull request

| Check | Where |
|---|---|
| `cargo clippy --workspace --locked --all-targets` with `-D warnings` | Rust job |
| `cargo build --workspace --locked --all-targets` | Rust job |
| `cargo test --workspace --locked --all-targets` | Rust job |
| `make gen` and `make rom/working/quintra.gbc` (link runs `scripts/check_rom_layout.py`) | ROM job |
| `scripts/check_cartridge.py` | ROM job |
| `scripts/test_suspend.py` under PyBoy 2.7.0 (the battery power-cycle from `make preflight`) | ROM job |
| `scripts/test_smoke.sh` under headless mGBA (the cart walk from `make test`) | ROM job |

The ROM job uploads `quintra.gbc` plus the linker `.map` and `.noi` as the
`quintra-gbc` artifact.

Rust is pinned to **1.98.1**. `Cargo.toml` still declares `rust-version =
1.75`, but the lockfile pulls crates that need Cargo edition 2024 (Rust
1.85 or newer), so 1.75 cannot build this tree.

GBDK is the upstream 4.5.0 `gbdk-linux64.tar.gz`, cached between runs. mGBA
is a development build, not the 0.10.5 release packages: those omit the
`--script` flag that `scripts/test_smoke.sh` and the controller bot require.
CI builds upstream commit `1d201b22a86d31dfb3bc75145403711f6762015f`
with Lua 5.4 and Qt/SDL/headless frontends enabled, and caches the installed
tools. It verifies the fetched commit and scripting CLI, without depending on
a moving "latest" tarball. Bump the cache key when changing build settings.
PyBoy uses the same `pyboy==2.7.0` pin as the Makefile.

The ROM link does **not** run `make all`. That target also refreshes about
460 external PyBoy curriculum states after the cartridge exists. Those states
are developer fixtures, not cart data.

## What does not gate a pull request

**rustfmt.** `cargo fmt --all -- --check` wants to reformat on the order of
440 files. Content tables are hand-aligned; formatting them is a separate
change, so CI does not run rustfmt.

**Clippy lints that already fail on main.** The gate denies new warnings and
allows only:

- `too_many_arguments`
- `needless_range_loop`
- `unnecessary_cast`
- `if_same_then_else`
- `manual_range_contains`
- `useless_format`
- `manual_div_ceil`

**`make verify` and the rest of the PyBoy curriculum.** That stack is the
local whole-game regression (town, bosses, procgen parity, music, puzzles,
and the rest). It is much longer than the suspend and smoke checks above, so
it stays a local gate. Nothing in that suite was dropped because it fails on
main; it was left out so pull requests get a signal without a multi-hour run.

**Balance, endurance, and Picsean soaks.**
[`.github/workflows/endurance.yml`](../.github/workflows/endurance.yml) runs
`make endurance` every Monday at 07:00 UTC. `workflow_dispatch` can run
`endurance`, `balance`, or `picsean-endurance` instead. They use the `mgba-headless` binary from that development build, under Xvfb.
They are not required checks.

## Cutting a release

The release workflow
([`.github/workflows/release.yml`](../.github/workflows/release.yml)) runs
only on tags that look like `v0.20.19` (`v<major>.<minor>.<patch>`). It does
not run on pull requests or on ordinary pushes to `main`.

1. Bump `QUINTRA_VERSION`, update the pinned ROM hash inside
   `tools/build_itch_web.sh` if the cartridge bytes changed, and add
   `docs/releases/vX.Y.Z.md` when that tag should carry those notes.
2. Tag the release commit and push the tag:
   `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. The workflow links the ROM, runs the same cart checks as CI, and builds
   the itch web directory with `tools/build_itch_web.sh`. That script refuses
   to pack a ROM whose SHA-256 does not match its pin.
   The workflow passes `QUINTRA_WEB_VERSION` from the tag so the archive,
   browser version label, and `build.json` agree with the release. Manual
   builds retain the beta default unless that variable is explicitly set.
   `python3 tools/test_itch_version.py` checks tag/default packaging and invalid
   versions before release packaging; it never publishes.
4. It opens a GitHub Release titled `Quintra vX.Y.Z` with `quintra.gbc` and
   the zip `tools/build_itch_web.sh` writes. Release notes come from
   `docs/releases/<tag>.md` when that file exists.

### itch.io

The publish step follows the deployment spec and `tools/deploy_itch.sh`:

```sh
butler push --if-changed --userversion <tag> builds/itch-web struktured/quintra:web
```

- Target: `struktured/quintra`
- Channel: `web` (do not rename it)
- User version: the git tag

The spec also names a `rom` channel for a separate cartridge download. That
channel is still an open product decision, and the live deploy script only
pushes `web`, so the workflow does not create a `rom` channel. The `.gbc` is
attached to the GitHub Release instead.

The step runs only when the repository secret **`BUTLER_API_KEY`** is set
(an itch.io API key). If the secret is absent, the step is skipped and the
GitHub Release is still created. No other secret is required.
`GITHUB_TOKEN` is provided by Actions and is what creates the Release.
