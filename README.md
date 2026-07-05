# Quintra

**A 9-stage top-down action roguelike for the Game Boy Color.**

Native CGB. Five monster-human classes, procgen dungeons every run, bullet-hell
bosses, and item-driven builds. Heavy [Penta Dragon](https://en.wikipedia.org/wiki/Penta_Dragon)
influence (dense projectile patterns) crossed with the maze-exploration feel of
Zelda: Link's Awakening / Final Fantasy Adventure / Ultima: Runes of Virtue.

Written in C with GBDK-2020 — the only thing that ships on cart. All content
authoring and dev tooling is a typed **Rust** workspace that generates the C
tables at build time.

![Quintra gameplay](docs/media/gameplay.gif)

## Screens

| Title | Class select | Dungeon | Pack / stats |
|:---:|:---:|:---:|:---:|
| ![title](docs/media/title.png) | ![class](docs/media/class.png) | ![dungeon](docs/media/dungeon.png) | ![pack](docs/media/pack.png) |

## Features

- **5 monster-human classes** — Wolfkin, Sauran, Corvin, Picsean, Vespine — each
  with its own stats, primary weapon, and signature move.
- **9 distinct stages**, each with its own palette, music, and enemy roster:
  Crystal Caverns → Verdant Hollow → Ember Depths → Frost Vault → Toxic Mire →
  Shadow Keep → Golden Temple → Bloodmoon → Void Sanctum.
- **9 large-sprite bosses** (32×32 metasprites) — one per stage — plus
  Sentinel-style **mini-bosses** and **merchants** mid-stage.
- **Two-weapon combat**: `A` = your class's primary (distinct projectile per
  class), `B` = its signature move on a cooldown.
- **RPG layer**: HP/MP/ATK/DEF/SPD/LCK, elemental weakness bonuses, crits,
  hit-flash / hit-stop / knockback for weight.
- **Zelda-style secrets**: shoot the glowing amber cracked walls to open
  treasure rooms; kick apart rubble for hidden coins.
- **Item builds**: stat-boost pickups and shop wares stack into a run's power
  curve — no XP grinding.
- **Full chiptune audio**: per-stage exploration themes, a driving boss theme,
  title / victory / gameover tracks, and 8 register-level SFX.

## Controls

| Input | Action |
|---|---|
| **D-pad** | Move (8-way aim while firing) |
| **A** | Primary weapon |
| **B** | Class signature move |
| **START** | Pack screen (stats + held items) |
| **SELECT** | Quick pause |

Shoot the glowing amber wall tiles — they hide secret rooms.

## Build & run

Requires [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020) v4.5.0 at `~/gbdk`
and a stable Rust toolchain (host-side only — Rust never ships in the ROM).

```bash
make            # cargo codegen → SDCC → rom/working/quintra.gbc
make play       # build + launch in mGBA
make test       # build + headless mGBA smoke test
make info       # print build summary
```

Cart spec: **MBC5 + RAM + battery, CGB-only, 512 KB** (headroom to 2 MB).

## Architecture

The C runtime under `src/` is the only thing on the cartridge. Content
(classes, items, enemies, biomes, rooms) is hand-authored as **typed Rust** in
`content/`; the `tools/` Rust workspace validates it and emits GBDK-compatible
C tables into `src/generated/` at build time. Invalid content — an orphan item
reference, an oversize table — fails `cargo build`, never the Game Boy.

```
src/       C runtime (core / render / audio / input / game / generated)
content/   typed Rust content (the source of truth)
tools/     Rust workspace — content codegen, asset pipeline, procgen, mGBA bridge
docs/      design specs + media
```

See `docs/superpowers/specs/` for the full engine design and audit.

## Why Rust tooling but a C runtime?

Rust can't target the GBC's Sharp SM83 CPU — no LLVM/GCC backend exists, so the
runtime *must* be C. But Rust shines on the host side: typed content schemas and
compile-time invariant checking mean bad content can't reach the cart.

## Legal

Quintra is wholly original. It contains **no** assets from Penta Dragon or any
other game — only its own art, audio, and code.
