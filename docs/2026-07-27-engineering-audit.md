# Quintra engineering audit — 2026-07-27

Scope: build, verification, tooling, and repo health at commit `9c06101`
(v0.18.90 "True Footing"). This complements
`docs/2026-07-21-whole-game-audit.md`, which covers gameplay and design; that
axis is deliberately not re-litigated here.

Every claim below was executed, not read. Where a first reading turned out to
be wrong, the correction is recorded rather than deleted.

---

## Headline

**`make verify` cannot pass on the released HEAD.** It stops twice, for two
unrelated reasons, and both are recent regressions in gates the project itself
authored:

1. `report_budget.py` exits 1 — home bank 0 has **502 bytes** free against the
   project's own **512-byte** floor.
2. `scripts/test_smoke.sh` exits 1 — the first gameplay gate.

The **cartridge itself is healthy.** The build is byte-reproducible, the
C↔Rust procgen seam is 12/12, and 12 of 12 sampled live-ROM gameplay tests
pass, including a full victory route. Both failures are in the verification
layer, not the game.

---

## What was executed

| Gate | Result |
|---|---|
| `make` | PASS (exit 0) |
| Rebuild vs committed ROM | **byte-identical** — SHA-256 `1bbe581c…8fbc7d` |
| `check_rom_layout.py` | PASS — home ends `0x3E0A`, trampoline `0x3BA0`, banks 0–7 |
| `check_cartridge.py` | PASS — QUINTRA, 128 KiB, CGB-only, MBC5 + 32 KiB battery, checksums valid |
| `check_media.py` | PASS — v0.18.90, 174 frames, ROM/reel/recipe hashes current |
| `report_budget.py` | **FAIL (exit 1)** |
| `cargo test` | PASS — 53 tests across 6 crates |
| `test_procgen_parity.py` | PASS — 12/12 |
| `test_smoke.sh` | **FAIL (exit 1)** — 14/26 as shipped |
| victory · doors · performance · town · boss_identity · enemy_identity · compass_map · score · stage_states · dungeon_topology · miniboss_escorts · death_telemetry | PASS — 12/12 |
| `test_picsean_victory_replay.sh` | inconclusive — legitimately exceeds a 600 s cap |

---

## 1. Home-bank headroom is under its own gate

```
[budget] ROM=128 KiB (8 banks), home_end=0x3E0A, home_headroom=502 bytes
[budget] FAIL: less than 512 bytes remain in always-mapped bank 0
```

Ten bytes over the line, and `make verify` stops here at step 3 of ~124.

The next constraint is close behind: **bank 1 has 1,041 bytes free against the
1 KiB switchable-bank gate — 17 bytes of margin.** Both thresholds exist
because the flat 32 KB image once overflowed silently and shipped six broken
commits (per the banking spec); they are worth keeping honest.

Two defensible fixes: move one home-bank function into a `#pragma bank 255`
file, or lower the gate deliberately with a recorded rationale. What should not
happen is the gate being skipped, since it is the only automated defence
against the failure mode the spec was written for.

**Related documentation drift:** `README.md` states the cartridge "retains
1,209 bytes of home-bank" headroom. The measured figure is 502. The
whole-game audit similarly records "the home bank ends at 0x3D21 (735 bytes
free)" against a measured `0x3E0A`.

## 2. The smoke test has two separable defects, one of which has made the boss half vacuous

`scripts/test_smoke.sh` exits 1 with 14/26 checkpoints. Investigating it
produced a more useful result than the failure count suggests.

**(a) The harness truncates its own run.** The script backgrounds mGBA under
`timeout 60`, but its actual bound is an independent poll loop:

```bash
for _ in $(seq 1 240); do ... sleep 0.25; done   # = 60 s, then kill
```

The route now needs about **118 seconds**. Six checkpoints are therefore lost
to truncation and reported as `file missing`. Given a genuinely extended
window the same ROM scores **20/26** and produces all thirteen screenshots.

This is worth flagging loudly for whoever fixes it: **raising `timeout 60`
alone changes nothing** — the poll loop is the real bound. I made exactly that
mistake, ran at a nominal 240 s and 900 s, got byte-identical output three
times, and briefly concluded the harness was hung. It was not. Both numbers
have to move together.

**(b) The boss route genuinely does not arrive.** With enough time, the
controller stalls at **room 7** and never reaches boss room 19:

```
SHOT 08_BOSS_room   screen=5 room=7  bosses=0 giants=0  pos=(232,60) tile=0xFF
```

`navigate_to` returns false and the script continues regardless, so shots
08–13 are captured in an ordinary room. The consequence is the important part:
**the six boss-fight assertions in the smoke have not been exercising a boss.**
Whatever they have been reporting, it was not the Colossus encounter they
name.

The recurring `pos=(232,60) tile=0xFF` signature — the hero parked at the east
edge with an out-of-range tile probe — points at the harness's routing model
rather than the ROM. `navigate_to` hardcodes `local size = 20` and the tile
probe reads as if rooms were 20 columns wide, while stage geometry is now
31×31. That is a lead, not a diagnosis.

Two checkpoints also assert the wrong room even in the healthy run
(`05_room2_sigil` and `06_room5_branch` both land in room 1), which suggests
the route expectations drifted at the same time.

## 3. Content validation is wired in, but six of nine validators are unproven

The premise in CLAUDE.md — invalid content fails `cargo build`, never at
runtime — holds. `registry.validate()` is genuinely invoked from
`quintra-codegen/src/main.rs:29`, and it aggregates every per-type validator.

The gap is proof, not plumbing. There are **nine `validate()` implementations**
and **three negative tests**, all three exercising the *enemy* validator
(duplicate symbol, OBJ tile range, OBJ palette range). The validators for
biome, item, class, room, stage (two), and zelda_overworld have no test that
proves they reject anything. They are substantive code today; nothing stops one
from quietly becoming permissive under edit, because authored content is valid
and the suite would stay green.

Also worth noting: `quintra-codegen/src/emit.rs` is 956 lines — the entire
Rust→C seam — and carries exactly **one** test, which covers file-rewrite
caching rather than emitted correctness. The seam is well covered *downstream*
by the 12/12 procgen parity check and the live-ROM suite, so this is a
defence-in-depth observation rather than an exposure.

Roughly thirty lines of `expect_err` tests would close the validator half.

## 4. Documentation drift, including one actively dangerous instruction

`CLAUDE.md` is the file agents read first, and it is materially stale:

| Claim | Measured |
|---|---|
| "Current Status: **v0.15**" | v0.18.90 |
| "5 classes / 15 items / **8 enemies**" | 5 / **36** / **32** |
| "**2 MB** target (currently building **512KB**)" | **128 KiB**, with a hard ≤128 KiB gate in `report_budget.py` |

The third row carries a real hazard. CLAUDE.md advises bumping `-Wl-yo` "as
banks fill". The Makefile says the opposite, in capitals, with the reason:

```
# DO NOT add -Wm-yo<n>: a fixed bank count suppresses the auto sizing and
# collapses all banked code back into banks 0-1 (silent boot-breakage).
```

An agent hitting the bank-1 wall (17 bytes away) and following CLAUDE.md would
do the thing the Makefile documents as silently breaking the boot. This is the
single cheapest fix in the audit.

Separately, the memory-layout section cites absolute WRAM addresses (`$C100`
entity table, `$C400` player state). The runtime uses no `__at` or absolute
placement at all — allocation is left to the linker, and the test harness
resolves symbols from the `.noi` map. The implementation is better than the
doc; the doc reads as normative and is not.

## 5. Repository hygiene

**The built ROM is tracked in git.** `.gitignore` lists both `*.gbc` and
`rom/**/*.gbc`, but ignore rules do not apply to already-tracked files, so
`rom/working/quintra.gbc` has been committed across **179 commits** — a 128 KiB
binary churning on essentially every release. The shared `.git` is 91 MB. The
ROM is already published properly through GitHub Releases, so `git rm --cached`
would cost nothing and would make the stated intent true.

**12 MB of accidental desktop screenshots sit at the repo root.** The files
`hashlib`, `json`, and `re` are 4 MB PostScript images written by ImageMagick
on 2026-07-20 — a Python `import hashlib, json, re` line was pasted into a
shell, where `import` is ImageMagick's *screen capture* tool. They are
untracked, but they are screen captures of the desktop sitting in a directory
that gets `git add`-ed. Worth deleting on both counts.

**`test_smoke.sh:56` kills processes machine-wide:** `pkill -9 -f 'Xvfb :'`.
On a box running several agent sessions, a Quintra smoke run terminates any
other session's Xvfb-based tests. It is the only script that does this.

**The shared pre-commit hook belongs to the other project.** The gitdir is
shared with `penta-dragon-dx`, and the hook references
`rom/working/penta_dragon_dx_teleport.gb`, `scripts/build_v301_teleport.py`,
and the Sara/orc colour-regression suite — none of which exist in the Quintra
worktree. Its trigger pattern includes `rom/working/`, which every Quintra
release commit touches (see above), so it fires, fails to find a DX build
script, and blocks the commit. Hence `--no-verify` as standing practice, which
means the hook currently provides zero protection and pure friction. Either
scope it per-worktree or make it a no-op outside DX.

## 6. Build ergonomics

`make` takes roughly four minutes, and two things dominate:

- **`src/game/room.c` is 2,274 lines and takes over 56 seconds alone** under
  SDCC. It also holds ~53 functions spanning room state, collision, palettes,
  doors, secrets, scroll transitions, sprite placement, input mapping, music,
  shops, and town residents. Splitting it would cut both the compile bottleneck
  and the file's responsibility count.
- **The `build` target runs the emulator.** It regenerates all 460 PyBoy
  checkpoint states (89 MB) after every link, so the ROM cannot be built
  without PyBoy and a network fetch on first use. There is a real argument for
  this coupling — a checkpoint bound to a stale ROM hash is worse than no
  checkpoint — but it belongs behind `make states` rather than in the path a
  contributor takes to get a cartridge.

`HDRS` is also a coarse dependency on every header under `src/`, so any header
edit rebuilds everything. `version.h` is already excluded for exactly this
reason; the same treatment would help elsewhere.

Test-harness mass is worth stating plainly: **27,026 lines of Python/Bash/Lua
tooling against 13,351 lines of C and 6,700 of Rust.** `make verify` is 124
sequential steps including 83 separate PyBoy launches, with no parallelism. The
per-boss and per-enemy scripts share about half their lines with each other
(41 of ~88 between two Colossus tests), the rest being genuinely bespoke
per-boss contracts — so this is a moderate consolidation opportunity, not
copy-paste.

---

## Things that are right

Worth recording, because they are load-bearing and easy to erode:

- **The build is reproducible.** A clean rebuild produced a ROM byte-identical
  to the committed one, including the deliberate `sort` on the source manifest
  that keeps autobank placement stable.
- **Tests resolve symbols from the linker map** (`.noi`) rather than hardcoding
  WRAM addresses, so a relink cannot silently invalidate the suite.
- **The C↔Rust procgen seam is verified at the seam**, not just on either side —
  12/12 across plain, mini-boss, shop, rest, and boss rooms.
- **Zero `TODO`/`FIXME`/`HACK`/`XXX` markers** in 20,000 lines of C and Rust.
- **`check_rom_layout.py` gates every link**, which is the correct response to
  the boot-breakage class that motivated the banking refactor.
- Content validation genuinely runs at codegen time, so invalid content fails
  `cargo build` as advertised.

---

## Corrections made during this audit

Recorded because each was a plausible finding that did not survive checking:

- **"v0.18.90 is untagged"** — false. The tag exists on `origin` and as a
  GitHub Release; only the local worktree had not fetched tags.
- **"The smoke harness hangs"** — false. It is truncated by its own 60 s poll
  loop; my first three "extended" runs never actually extended anything.
- **"The smoke's BFS router loops forever"** — false. `dungeon_route_dir` is
  correctly bounded by its `seen` set.
- **"`entity_anim_counter` double-increments"** — false. The one-screen and
  banked world renderers are an if/else per frame.
- **"Procgen parity fails"** — false. My first run omitted the
  `cargo build --release -p quintra-procgen` step that `make verify` performs
  first.
- **"Content validation is untested"** — overstated. It is tested for enemies;
  six of nine validators are the actual gap.

---

## Suggested order

1. **Recover ten bytes of home bank** (or re-set the gate deliberately) so
   `make verify` can start. Watch bank 1 — 17 bytes of margin.
2. **Fix the smoke harness**, both halves: move the poll loop and `timeout`
   together, and either repair the room-19 route or delete the six boss
   assertions. They currently assert against an ordinary room.
3. **Reconcile CLAUDE.md**, starting with the `-Wl-yo` advice that contradicts
   the Makefile's boot-breakage warning. Then version, content counts, and ROM
   size.
4. **Repo hygiene**: delete the three stray screenshots, `git rm --cached` the
   ROM, scope the pre-commit hook, and narrow the machine-wide `pkill`.
5. **Add negative tests for the six unproven validators** — about thirty lines.
6. **Split `room.c`** when convenient; it is both the compile bottleneck and
   the largest concentration of unrelated responsibilities.
