# Quintra content

This directory holds the **typed Rust source of truth for all game content**:
classes, items, enemies, biomes, room templates. The `quintra-codegen` tool
under `tools/` consumes these and emits the GBDK-compatible C tables that the
runtime reads.

Content here is hand-authored. Generated C never appears in this directory.

## Layout

- `classes.rs` — 5 starting classes (plus future hidden unlockables)
- `items.rs` — item pool
- `enemies.rs` — enemy roster
- `biomes.rs` — biome configs (depth ranges, enemy pools, room template pools, boss assignments)
- `rooms/*.ron` — room template tilemaps + spawn slots

These files are wired into `tools/crates/quintra-codegen/src/content.rs` (via
module include) and become the input to `cargo run -p quintra-codegen`.

## Adding content

1. Author the item/enemy/biome in the appropriate file
2. Reference it from biome/class as needed
3. `cargo run -p quintra-codegen` — validation runs first, any orphan ID or
   oversize table fails the build immediately
4. `make` rebuilds the ROM with the new content table

No content lives in C source. Treat `src/generated/` as a build artifact.
