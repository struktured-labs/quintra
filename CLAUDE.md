# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Quintra** — a top-down action roguelike for Game Boy Color, native CGB, written in C with GBDK-2020. Pure roguelike (only knowledge persists), 5 monster-human classes, procgen rooms every run, rest-room saves only, item-driven builds (no XP grinding). Heavy Penta Dragon mechanical influence (bullet-hell projectile patterns, form-energy mechanics) crossed with Zelda LA / FF Adventure / Ultima ROV (top-down maze exploration, items as permanent character expansions).

**The novelty layer:** all *dev-host* tooling and content authoring is in Rust under `tools/`. The C runtime is the only thing that ships on cart. Typed Rust content schema catches invalid items/enemies/biomes at `cargo build`, never at runtime. The seam is `src/generated/`.

**Lineage:** this project began as a Penta Dragon DX colorization effort (that history lives in the separate `penta-dragon-dx` repo) and pivoted into Quintra, a Penta-inspired but wholly original game.

**Current Status:** v0.9 — 9-stage roguelike, playable end to end, **banked
ROM** (autobank; see the 2026-07-05 banking spec — new gameplay files need
`#pragma bank 255` + `BANKED`, and `scripts/check_rom_layout.py` gates every
link). TITLE (pulsing + music, CONTINUE when a suspend save exists, BEST
score) → CLASS_SELECT (5 classes, live preview + cursor + SFX) → 9 stages of
6 rooms each, styled distinctly (Crystal Caverns → Verdant Hollow → Ember
Depths → Frost Vault → Toxic Mire → Shadow Keep → Golden Temple → Bloodmoon
→ Void Sanctum), each fading in from darkness. Per stage: normal rooms in 8
procgen shapes, ~12% elite enemies (boss-glow, 2x HP), a mini-boss (drops
A-weapon swap orbs), a merchant, and a **32x32 large-sprite stage boss** — 9
distinct bosses with HUD HP bar, death explosion + screen shake. Beat all 9
→ VICTORY. Combat: A = per-class primary weapon, B = signature move costing
2 MP (blue HUD digits; MP regens, +1 on room clear), DEF/LCK/elemental,
hit-flash + hit-stop + knockback both ways, pickup magnetism, room-clear
chime. Full audio: per-stage music, boss theme, title/victory/gameover,
9 SFX. START = pack/stats screen (stage names, weapon/signature). SRAM:
suspend save every room (dies with you — permadeath holds) + persistent
best/runs/wins. Zelda-style shootable cracked walls → treasure rooms.
5 classes / 15 items / 8 enemies (incl. exploding Bombers, teleporting
Shades) / 9 stage themes with designed weighted rosters + boss stats —
all compiled from typed Rust content; `make verify` runs cargo tests,
the gameplay smoke, and the C<->Rust procgen parity check.

### Controls
- D-pad move · A primary weapon · B signature move (2 MP) · START pack
  screen · SELECT quick-pause · shoot the glowing amber cracked walls for
  secrets · title: A = continue a suspended run.

### Toolchain

- **GBDK-2020 v4.5.0** at `~/gbdk` (C runtime)
- **SDCC 4.5.1** (included with GBDK)
- **Rust stable** (host-side tooling only — never compiled into ROM)
- Compiler driver: `~/gbdk/bin/lcc`

### Why a Rust tooling layer?

Rust cannot target GBC's Sharp SM83 CPU — no LLVM/GCC backend exists. Game runtime *must* be C. But Rust shines on the host side for content authoring: typed schemas, compile-time invariant checking, deterministic procgen reference impls, automated asset processing. See `docs/superpowers/specs/2026-06-30-quintra-engine-design.md` for the full architecture.

## Common Commands

### Build

```bash
make            # cargo codegen → SDCC → rom/working/quintra.gbc
make clean      # clean C build
make cleangen   # wipe src/generated/
make cleanall   # nuke everything
make info       # print build summary
```

### Test / Play

```bash
make test       # build + headless mGBA + screenshots (Phase 3+)
make play       # build + launch mGBA-qt for human testing
```

### Rust tooling

```bash
cd tools
cargo build --release             # build all crates
cargo test                        # run all Rust tests
cargo run -p quintra-codegen      # regen src/generated/ from content/
cargo run -p quintra-assets       # PNG → tile data (Phase 2+)
cargo run -p quintra-mgba         # mGBA debug TUI (Phase 3+)
```

## Architecture

```
penta-dragon-remake/
├── src/                  # C runtime (ONLY thing in the ROM)
│   ├── core/             # types, allocator, RNG, banking, fixed-point
│   ├── render/           # palette, OAM, BG/tilemap, top-down scroll
│   ├── audio/            # music + SFX
│   ├── input/            # joypad
│   ├── game/             # screens, ECS-lite, combat, procgen runtime
│   ├── generated/        # Rust → C tables (gitignored)
│   └── main.c
├── tools/                # Rust workspace (host-only)
│   └── crates/
│       ├── quintra-content/   # typed content schema
│       ├── quintra-codegen/   # content → C tables emitter
│       ├── quintra-assets/    # PNG → tile data
│       ├── quintra-procgen/   # reference procgen + rng
│       └── quintra-mgba/      # mGBA debug bridge
├── content/              # hand-authored content (Rust source)
├── assets/               # raw PNGs + music
├── docs/superpowers/specs/    # design docs
├── rom/working/          # build output (gitignored)
└── Makefile
```

### Cart spec
- **MBC5 + RAM + battery** (cart type 0x1B)
- **2 MB target** (currently building 512KB; bumps `-Wl-yo` as banks fill)
- **32 KB SRAM** (4 × 8KB banks)
- **CGB only** (`-Wm-yC` enforces)

### Memory layout

See `docs/superpowers/specs/2026-06-30-quintra-engine-design.md` §2 for the full bank/WRAM/SRAM plan. High-level:
- Banks 0–7: hot engine code (always resident)
- Banks 8+: warm/cold content + per-biome data
- WRAM `$C100`: 32-slot entity table (768 B)
- WRAM `$C400`: player state
- SRAM 0: suspend save; SRAM 1: meta-progress; SRAM 2: stats

### Build flow

1. `cargo run -p quintra-codegen` reads `content/*.rs` → emits `src/generated/*.{c,h}`
2. `cargo run -p quintra-assets` processes `assets/` → tile/sprite C arrays
3. SDCC compiles `src/**/*.c` (including generated) → `rom/working/quintra.gbc`

The Makefile chains these. `cargo build` failures fail the whole build — no ROM is emitted if content is invalid.

## Development conventions

### C runtime
- Plain GBDK-2020 idioms: `void main(void)`, `wait_vbl_done()`, `SHOW_BKG`, etc.
- Typedefs in `src/core/types.h`: `u8/i8/u16/i16/u32/i32`, `fix8_t` for 8.8 fixed point
- Typed IDs (`class_id_t`, `item_id_t`, etc.) — opaque newtypes, opaque to C
- `BANKED` keyword for far-bank functions
- `__addressmod` far pointers for cross-bank data reads
- One cross-bank far call per frame stage; no nested banking

### Rust tooling
- 2021 edition, MSRV 1.75
- `#![forbid(unsafe_code)]` in all crates
- Container types with `&'static [T]` skip serde (hand-authored Rust consts only)
- Leaf scalars (enums) keep serde for future RON support
- Validation always before emit: orphan ID, oversize table → cargo build fails

### Spec-first
- New systems get spec entries before code — see `docs/superpowers/specs/`
- Spec is source of truth for memory layout, bank plan, RPG numbers

## Testing

### Headless (preferred for automation)
- `make test` boots ROM in headless mGBA + screenshots (Phase 3+)
- Save-state anchors at title / mid-combat / rest-room / boss for fast regression
- NEVER launch mgba-qt GUI during automated testing (KDE Wayland)
- ALWAYS clean stray Xvfb procs: `pkill -9 -f 'Xvfb :'`

### Rust unit tests
- `cargo test` — content validation, procgen determinism, codegen output,
  sprite-pipeline golden test (quintra-assets output == checked-in
  sprites_gen.c), room-shape property tests (door connectivity across
  seeds, lane clearance, boss sealing)
- xorshift32 determinism is pinned by test — the on-cart C impl must match
- `uv run --with pyboy python scripts/test_procgen_parity.py` — cross-seam
  check: quintra-procgen's reference tilemap vs the real ROM's WRAM for
  seeded rooms (plain/mini-boss/shop/rest/boss). Run after ANY change to
  procgen.c's RNG call order or room layout code.

### mGBA MCP
- When available, prefer MCP `mgba_*` tools over CLI subprocess

## Legal Notice

Quintra is wholly original — no assets from Penta Dragon or any other game are used. This repository contains no original ROMs.
