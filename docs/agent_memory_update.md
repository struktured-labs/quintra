# Quintra Agent Memory Update — 2026-07-27

## Agent Identity

**Specialist:** QUINTRA specialist (deployed as subagent from CTO agent)

## Current Status

| Field | Value |
|-------|-------|
| **Working branch** | `feature/penta-dragon-remake` |
| **Latest commit** | `9c06101` — "docs: record v0.18.90 whole-run audit" (2026-07-26) |
| **Latest release** | **v0.18.90 — "True Footing"** |
| **Latest tags** | `v0.99` (exists but v0.18.90 is the actual released version; v0.99 is a separate tag lineage) |
| **ROM target** | 128 KiB MBC5/CGB cartridge |
| **Build status** | Valid clean rebuild, byte-identical, hash-bound |
| **ROM hash** | `1bbe581c050346631cf4f74e18d22f22987e0dfc3f5d383ba28d4ada081fbc7d` |

### Active Worktrees

| Path | Branch/Pointer |
|------|----------------|
| `penta-dragon-remake` (primary) | `feature/penta-dragon-remake` |
| `penta-dragon-dx-claude` | `release/v3.01-stream-rc3` |
| `penta-dragon-dx-claude/tmp/weekago_worktree` | detached (d00ea1e) |
| `penta-dragon-codex-wt` | `codex/bg-victory` |
| `/tmp/claude-.../bisect-wt` | detached (63aef2e, prunable) |

## Recent Release History (last 10)

| Version | Codename | Key Feature |
|---------|----------|-------------|
| v0.18.90 | **True Footing** | Terrain readability fix; 12px feet box preserved, lanes widened, finalization pass closes isolated 8-pixel slits; wide-seam battery commit fix |
| v0.18.89 | **Living Bazaar** | 6x6 merchant catalog; 4 new relics (Ricochet Rune, Thorn Crown, War Drum, Moon Flask); Normal Colossus damage curve corrected |
| v0.18.88 | **Rift Bazaar** | Merchants sell mechanics (build/tactical shelves); 16 seed-stable pairings; Compass legend fixes; Riftwild `RIFT` label restored |
| v0.18.87 | **Fivefold Depths** | 5 depth dialects (Gate/Lower/Deep/Inner/Heart); unified collision contract; 2-second arrival callouts; Penta-scale boss campaign |
| v0.18.86 | **Footprint Compass** | Unified collision; champion/knockback shared contract; nine-boss controller victory in 158,896 frames |
| v0.18.85 | **Farfold Reliquaries** | Nonlinear Rift travel; Riftwild overworld; villages; 5-district dungeons; nine scrolling Colossi |
| v0.18.84 | **Whole-World Training** | 460 PyBoy checkpoints; progression-matched boss curriculum; training ladder |
| v0.18.83 | **Farfold Labyrinths** | Riftwild generation; cave/vault teleport; overworld landmarks |
| v0.18.82 | **Pocket Atlas** | Spirit Compass tile-native 6x5 grid; dungeon graph visualization |
| v0.18.81 | **Colossus Fields** | Nine scrolling-arena Colossi; BG-plane giant bosses |

## Key Milestones Achieved

### Whole-Game Completion (v0.18.90)
- **Controller-only Picsean Easy victory** in **154,260 frames**: 9 Colossi, 194 rooms, both villages, 40 Riftwild hops, 8 collectible boss relics
- **Reproducible**: clean mGBA replay from recorded input trace: `seed=2064128163 room=220 bosses=9 hp=15 won=1`
- **460 PyBoy checkpoints** + **460 native mGBA states** covering all 5 champions, Normal/Easy, all 9 stages

### Difficulty Matrix (Normal vs Easy)
- **Normal**: 9/45 clears, 19/45 survivals in 1-minute boss curriculum
- **Easy**: 37/45 clears, 44/45 survivals — real testing assist, not cosmetic
- Normal remains the authored target; Easy preserves boss geometry/patterns

### Technical Achievements
- **Banked ROM** (32+ KiB across 8+ banks via MBC5)
- **C/Rust procgen parity**: 12/12 across all room roles (ordinary, Rift, miniboss, shop, sanctuary)
- **SRAM**: suspend save (permadeath) + meta-progress + stats
- **Full audio**: per-stage music, boss theme, 9 SFX, title/victory/gameover
- **9 Colossi**: BG-plane bodies 64×48 to 128×80 in scrolling 224×136 arenas
- **5 classes / 15 items / multiple enemy species per stage**

## Build Pipeline

```
content/*.rs ──[quintra-codegen]──→ src/generated/*.{c,h}
assets/      ──[quintra-assets]  ──→ tile/sprite C arrays
src/**/*.c   ──[SDCC + lcc]     ──→ rom/working/quintra.gbc
```

- `make` — full build chain
- `make test` — headless mGBA + screenshots
- `make play` — mGBA-qt GUI
- `make verify` — cargo tests + gameplay smoke + procgen parity check
- `make boss-curriculum-audit` — Normal boss matrix diagnostic
- `make room-curriculum-audit` — stage-entry room pressure trace
- `make timed-states` — controller-driven Easy segments (30 emulated min)
- `make cleanall` — nuke everything

## Repository Architecture

```
penta-dragon-remake/
├── src/                  # C runtime (ROM)
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
├── docs/                 # design docs + releases + audit
│   ├── releases/         # per-version release notes (v0.18.37–v0.18.90)
│   ├── superpowers/      # architecture specs
│   ├── media/            # screenshots, gameplay GIF
│   └── music-composition.md
├── rom/working/          # build output (gitignored)
└── Makefile
```

## Release Documentation

Release docs are in `docs/releases/` spanning `v0.18.37.md` → `v0.18.90.md` (with gaps from v0.18.42 to v0.18.65 where docs were not preserved). The comprehensive audit/design doc is `docs/2026-07-21-whole-game-audit.md`.

## Priority Order Ahead

1. **Normal first-three-dungeon human balance pass**
2. **Release correctness** (verification stack, media regeneration, reproducibility)
3. **Human-test nine Colossi forms** (pass footprint, collision, art-identity, pattern, video-rate)
4. **Fresh-player readability** (Compass/Sigil, shops, village, Riftwild, etc.)
5. **Music composition pass** (replace generated phrases with composed tracks)
6. **Easy balance later** (once Normal curve is stable)

## Notes

- The `v0.99` tag exists but is separate from the v0.18.x release track — likely an experimental/pre-release tag from earlier prototyping
- The CLAUDE.md says "Current Status: v0.15" which is outdated — actual state is v0.18.90
- Project lineage: began as Penta Dragon DX colorization → pivoted into Quintra (wholly original, no Penta Dragon assets)
- Hardware play validated on Analogue Pocket and IPS GBC
- The CTO agent deployed this specialist to audit and report on Quintra's current state

---

*Generated by QUINTRA specialist on 2026-07-27*
