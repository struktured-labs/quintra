# Quintra — Engine & Game Design Spec

**Date:** 2026-06-30
**Status:** Approved (sections 1-4, 6 green-lit interactively; 5, 7-8 added in design closeout)
**Target:** Game Boy Color, native CGB, MBC5 + 32KB SRAM + battery, 2MB ROM
**Toolchain:** GBDK-2020 v4.5.0 / SDCC 4.5.1 (C runtime); Rust 1.x stable (dev-host tooling only)

## Vision

A top-down action roguelike for Game Boy Color, heavily influenced by Penta Dragon's projectile-dense combat, with the open-world maze sensibility of Zelda: Link's Awakening / FF Adventure / Ultima Runes of Virtue, layered on a modern Gungeon/Hades/Isaac-style item-driven build economy.

Five monster-human classes. Procgen rooms every run. Pure roguelike — only knowledge persists across deaths. Rest-room saves. 8-way auto-aim D-pad shooting.

The novelty layer: **all dev tooling and content authoring is in Rust**, even though the runtime is C. Type-safe content schemas catch invalid items/enemies/biomes at `cargo build` time, never at runtime. The seam is the `src/generated/` directory.

## Non-goals

- DMG (original Game Boy) compatibility — CGB only.
- Persistent stat boosts across runs (would change difficulty floor; against pure-roguelike intent).
- XP / level grinding (power scales from items found, not enemies killed).
- Multiplayer / link cable.

---

## §1. Workspace layout & build flow

```
penta-dragon-remake/
├── src/                          # C runtime (GBDK-2020 / SDCC) — only thing in the ROM
│   ├── core/                     # allocator, RNG (xorshift32), banking, fixed-point 8.8
│   ├── render/                   # palette, OAM shadow, BG/tilemap, top-down scroll
│   ├── audio/                    # music + SFX (port current engine)
│   ├── input/                    # poll, edge-detect, combos
│   ├── game/                     # screens, ECS-lite, combat, procgen runtime
│   ├── generated/                # Rust output: C tables + bin blobs (gitignored)
│   └── main.c
├── tools/                        # Rust workspace (dev-host only, never linked into ROM)
│   ├── Cargo.toml
│   └── crates/
│       ├── quintra-content/      # types: Class, Item, Enemy, Biome, Room, AiScript, Effect
│       ├── quintra-codegen/      # content → C tables + binary blobs emitter
│       ├── quintra-assets/       # PNG→tiles, palette quantize, music convert
│       ├── quintra-procgen/      # reference procgen impl + visualizer + balance tooling
│       └── quintra-mgba/         # mGBA MCP bridge (TUI introspection)
├── content/                      # human-authored content (Rust source, type-checked)
│   ├── classes.rs                # 5 starting classes
│   ├── items.rs                  # ~80-120 items
│   ├── enemies.rs                # ~30-40 enemies
│   ├── biomes.rs                 # ~6-8 biomes
│   └── rooms/*.ron               # room templates
├── assets/                       # raw PNGs + source music
├── archive/                      # OLD Penta-DX clone code (preserved for reference)
├── docs/superpowers/specs/       # design docs
├── rom/working/                  # build output
├── tests/                        # mGBA harness, golden screenshots
├── Makefile                      # cargo → SDCC pipeline
└── CLAUDE.md
```

### Build flow

1. `cargo run -p quintra-codegen` — reads `content/*.rs`, emits `src/generated/*.{c,h}` + bin blobs
2. `cargo run -p quintra-assets` — processes `assets/`, emits tile/sprite C arrays
3. `make` — SDCC compiles `src/**/*.c` (including generated) → `rom/working/quintra.gbc`
4. `make test` — build + headless mGBA + screenshot capture + golden diff
5. `make play` — build + launch mGBA-qt

The seam is `src/generated/`. Typed Rust on one side, GBDK C arrays on the other. Invalid content (orphan item refs, oversize tables, palette overflow) fails at `cargo build`.

---

## §2. Memory map & bank plan (2 MB MBC5 + 32 KB SRAM)

### ROM (128 × 16KB banks)

| Banks | Contents | Notes |
|-------|----------|-------|
| 0 | ISRs, OAM/DMA, vblank, hardware init, dispatch tables | hot, always resident |
| 1 | Core: allocator, RNG, banking helpers, fixed-point math | hot |
| 2 | Render: palette/sprite/BG primitives, top-down scroll | hot |
| 3 | Game loop, screen state machine, input | hot |
| 4 | ECS-lite: entity table, update/draw dispatcher | hot |
| 5 | Combat resolution: damage, status, hit detection | hot |
| 6 | Procgen runtime: room/biome generator | swap during transitions |
| 7 | Save/load (SRAM I/O), CRC8 | cold |
| 8–11 | HUD, menus, shop UI, item descriptions | warm |
| 12–16 | Class code: 1 bank per class × 5 | only active class loaded |
| 17–32 | Enemy AI: ~2 enemies per bank | only current biome's enemies |
| 33–48 | Item effects: ~5-8 items per bank | only items in inventory/drops |
| 49–56 | Boss AI + scripts: ~1 boss per bank | swap on boss room entry |
| 57–72 | Per-biome tile/sprite data: ~2 banks × 8 biomes | swap on biome change |
| 73–96 | Music tracks + SFX | swap per biome/screen |
| 97–119 | Generated content tables (rooms, drop tables, dialog) | data-only, far-pointer access |
| 120–127 | Reserve / future expansion | — |

### WRAM (8 KB at $C000–$DFFF; CGB has 32KB via WRAMX banking)

| Range | Contents | Bytes |
|-------|----------|-------|
| $C000–$C0FF | Engine state, screen FSM, RNG state, frame counter | 256 |
| $C100–$C3FF | Entity table: 32 entities × 24B | 768 |
| $C400–$C4FF | Player state: class, items, HP/MP, stats, inventory | 256 |
| $C500–$C5FF | Current room: tilemap meta, alive enemies, doors | 256 |
| $C600–$C7FF | Run state: biome, depth, seed, inventory_meta, score | 512 |
| $C800–$C89F | OAM shadow (40 sprites × 4B) | 160 |
| $C8A0–$CBFF | DMA scratch + alignment | 864 |
| $CC00–$CFFF | Audio engine state | 1024 |
| $D000–$D1FF | Procgen scratch (template buffer, neighbor cache) | 512 |
| $D200–$D3FF | UI state, dialog buffer, menu cursors | 512 |
| $D400–$D7FF | Free / scratch | 1024 |
| $D800–$DFFF | CGB WRAMX banks 1-7 (per-biome NPC/string buffers) | 8KB × 7 |

### HRAM (127B at $FF80–$FFFE)

Hot scalars: current ROM bank, joypad cur/prev, vblank flag, SCX/SCY shadow, combat temp regs, sound channel busy flags. Free space $FFD0–$FFFE for ad-hoc.

### SRAM (32 KB, 4 × 8KB banks)

| Bank | Contents |
|------|----------|
| 0 | Active suspend save (rest-room saves only) |
| 1 | Meta-progress: classes/items/enemies/biomes/bosses *seen*, achievements |
| 2 | Stats: total runs, wins, deepest depth, kill counts, best times, deaths-by-cause |
| 3 | Reserve (future: 2-3 save slots) |

---

## §3. Runtime architecture

### Screen state machine

Top-level FSM. Each frame: poll input → tick current screen → render. Transitions are explicit returns.

| Screen | Purpose |
|---|---|
| `BOOT` | splash, HW init |
| `TITLE` | new/continue/stats |
| `CLASS_SELECT` | pick 1 of 5 (only unlocked classes shown) |
| `RUN_INIT` | gen seed, init biome 1 / room 1 |
| `PROCGEN` | transition cover while next room generates |
| `ROOM` | main gameplay loop |
| `REST_ROOM` | shop / save / altar |
| `BOSS` | dedicated boss-room loop |
| `INVENTORY` | pause: items, map, stats |
| `DIALOG` | modal NPC text |
| `GAMEOVER` | death stats → back to TITLE |
| `VICTORY` | run cleared |

Screen interface:
```c
typedef screen_id_t (*tick_fn)(uint8_t keys, uint8_t edge);
typedef struct {
    void     (*enter)(void);
    void     (*exit)(void);
    tick_fn  tick;             // returns next screen or SELF
    void     (*draw)(void);
} screen_t;
extern const screen_t screens[N_SCREENS];
```

### ECS-lite

Fixed entity table, 32 slots × 24B = 768B in WRAM at $C100:
```c
typedef struct {
    uint8_t  type;          // entity_type_t
    uint8_t  flags;         // ACTIVE | ALIVE | ON_SCREEN | DIRTY
    int16_t  x, y;          // fixed-point 8.8 world coords
    int8_t   vx, vy;        // per-tick velocity delta
    uint8_t  sprite_id;
    uint8_t  palette;       // OBJ palette 0-7
    uint8_t  hp;            // or projectile pierce count
    uint8_t  state;         // type-specific FSM
    uint8_t  state_timer;
    uint8_t  ai_data[8];    // type-specific scratch
    uint8_t  hitbox;        // packed: 4-bit w, 4-bit h
    uint8_t  damage;
    uint8_t  _pad;
} entity_t;
```
Per-type dispatch via function-pointer tables that live in the entity-type's bank (GBDK `BANKED` far-call).

Collision: AABB, broad-phased by a 4-cell screen grid. ~64 checks/frame worst case.

### Game loop

1. vblank ISR → DMA OAM shadow, bump frame counter
2. main: poll joypad → `screens[cur].tick(keys, edge)`
3. if no transition: update entities → resolve collisions → apply damage/status → cull dead
4. `screens[cur].draw()` → mark OAM shadow dirty
5. audio engine tick → wait vblank

### Banking discipline

- Banks 0–7 hot, never swapped out during main loop
- Cold/warm calls via GBDK `BANKED` (compiler-emitted far-call shim)
- Content tables read via `__addressmod` far pointers — bank switch + direct read, no call overhead
- Rule: one cross-bank far call per frame stage; no nested banking

---

## §4. Content data formats

All schemas defined as Rust types in `tools/crates/quintra-content`. `quintra-codegen` emits matching C structs + `static const` tables into `src/generated/`.

### Class

```rust
pub struct Class {
    pub id: u8,
    pub name: &'static str,           // ≤8 chars (HUD)
    pub form_theme: FormTheme,        // Wolfkin, Sauran, Corvin, Picsean, Vespine
    pub palette: PaletteRef,
    pub sprite_set: SpriteRef,        // 8 tiles: 4-dir idle + 4-dir walk
    pub starter_weapon: ItemId,       // bound to B, can't drop
    pub signature_active: ItemId,     // bound to A, 1-slot, room/damage recharged
    pub passive_perk: PerkId,         // engine-recognized hook
    pub base_stats: BaseStats,
}
pub struct BaseStats { hp_max: u8, mp_max: u8, atk: u8, def: u8, spd: u8 }
pub enum PerkId {
    None,
    MoveSpeedPlus20,        // Wolfkin
    HpPlus2SlowRegen,       // Sauran
    SeeHpRevealRooms,       // Corvin
    MpRegenSwimWater,       // Picsean
    PoisonSynergy,          // Vespine
}
```

### Item

```rust
pub struct Item {
    pub id: u16,
    pub name: &'static str,           // ≤12 chars
    pub description: &'static str,    // ≤64 chars (4×16)
    pub kind: ItemKind,
    pub icon_sprite: SpriteRef,
    pub palette: PaletteRef,
    pub rarity: Rarity,               // Common, Uncommon, Rare, Boss
    pub effects: &'static [Effect],
}
pub enum ItemKind {
    Weapon { fire_rate: u8, damage: u8, projectile: ProjectileKind, mp_cost: u8 },
    Active { cooldown_rooms: u8 },
    Passive,
    Consumable { uses: u8 },
}
pub enum Effect {
    StatBoost { stat: Stat, delta: i8 },
    OnHit(Trigger), OnRoomClear(Trigger), OnPickup(Trigger), OnDamageTaken(Trigger),
    Dash { iframes: u8, dist: u8 },
    HealHearts(u8), GrantMp(u8), RevealMap,
}
pub enum Trigger {
    SpawnProjectile { kind: ProjectileKind, count: u8 },
    DealDamage { amount: u8, radius: u8 },
    ApplyStatus { status: Status, duration_ticks: u8 },
    GiveCoins(u8),
}
```

### Enemy

```rust
pub struct Enemy {
    pub id: u8,
    pub name: &'static str,
    pub sprite_set: SpriteRef,
    pub palette: PaletteRef,
    pub stats: EnemyStats,
    pub ai_script: AiScriptId,
    pub drop_table: DropTableId,
    pub biomes: &'static [BiomeId],
}
pub struct EnemyStats { hp: u8, damage: u8, speed: u8, score: u8, weakness: u8, poise: u8 }
pub enum AiScriptId {
    Walker, Chaser, Charger { telegraph_ticks: u8, charge_speed: u8 },
    Shooter { fire_rate: u8, projectile: ProjectileKind, pattern: ShotPattern },
    Spinner { radius: u8, fire_rate: u8 },
    Turret { rotation: u8, fire_rate: u8 },
    // Penta-DNA bullet-hell flavors:
    SprayPattern { angles: u8, fire_rate: u8 },
    AimedBurst { burst_size: u8, recovery_ticks: u8 },
}
```

### Biome

```rust
pub struct Biome {
    pub id: u8,
    pub name: &'static str,
    pub depth_range: (u8, u8),
    pub tileset: TilesetRef,
    pub bg_palettes: [PaletteRef; 4],
    pub music_track: MusicRef,
    pub enemy_pool: &'static [(EnemyId, u8)],     // (id, weight)
    pub room_template_pool: &'static [RoomTemplateId],
    pub min_rooms: u8, pub max_rooms: u8,
    pub has_shop: bool, pub has_altar: bool,
    pub boss: BossId,
}
```

### Room template

```rust
pub struct RoomTemplate {
    pub id: u16,
    pub size: RoomSize,               // Small (10×9), Medium (20×18), Large (40×18 scroll)
    pub layout: TilemapId,
    pub doors: DoorMask,              // bitmask N/E/S/W
    pub spawn_slots: &'static [SpawnSlot],
    pub kind: RoomKind,
}
pub struct SpawnSlot { x: u8, y: u8, role: SpawnRole }
pub enum RoomKind { Combat, Treasure, Shop, Altar, Puzzle, Boss }
```

### Generated C side

```c
extern const class_def_t   classes[N_CLASSES];
extern const item_def_t    items[N_ITEMS];
extern const enemy_def_t   enemies[N_ENEMIES];
extern const biome_def_t   biomes[N_BIOMES];
extern const room_tpl_t    room_templates[N_TEMPLATES];
extern const uint8_t       drop_tables[N_DROP_TABLES][16];
extern const tilemap_t     tile_layouts[N_LAYOUTS];
```

Runtime reads via 24-bit far pointers. No parsing, no validation, no allocation at runtime.

**Rust → C invariants (compile-time enforced):**
- Every `enemy.biomes` BiomeId resolves to a real biome
- Every `biome.enemy_pool` EnemyId fits biome's tileset/palette budget
- Every `room.spawn_slots` SpawnRole has a matching content provider
- Every `item.effects` slice fits in a ROM bank
- Sprite/palette refs resolve at codegen-time

---

## §5. Procgen algorithm

**Graph-on-grid, lazy generation, deterministic per seed.**

1. **Pick biome** by `current_depth` ∈ `biome.depth_range`.
2. **Lay rooms on 8×8 logical grid.** Random walk from center spawns `N ∈ [min_rooms, max_rooms]` connected rooms.
3. **Assign room roles** by graph topology:
   - Deepest room from start → BOSS
   - First mid-distance dead-end → REST
   - Second dead-end → TREASURE
   - Remaining → COMBAT
4. **Pick template** from `biome.room_template_pool` matching `kind` + required `doors`.
5. **Fill spawn slots** with weighted-random enemies from `biome.enemy_pool`. Per-room cap: 8 enemies.
6. **Roll drop tables** at enemy spawn time for stable revisits.

**RNG**: `xorshift32`, seed = `run_seed ^ (biome_id << 16) ^ room_index`. Same seed → same rooms.

**Lazy**: only generate current + 4 adjacent. LRU cache of 4. Re-derivable if evicted.

**Memory cost**: per-room state ~32B; cache ~128B in WRAM ($C500–$C57F).

---

## §6. RPG layer: stats, damage, items-as-build

### Player stats

| Stat | Range | Effect | Source |
|---|---|---|---|
| **HP** (cur/max) | 1–24 half-hearts (12 hearts) | health pool; die at 0 | class base + items + altar buffs |
| **MP** (cur/max) | 0–20 | active items & spell weapons | class base + items |
| **ATK** | 1–15 | added to weapon damage | class base + items |
| **DEF** | 0–10 | subtracted from incoming dmg (min ½ heart) | class base + items |
| **SPD** | 1–8 | px/tick movement (8.8 fixed point) | class base + items |
| **LCK** | 0–10 | drop tier + crit chance | item passives only |

### Damage formula

```
final_dmg = max(1, weapon.dmg + ATK - target.DEF)
  × 1.5  if weapon.element matches target.weakness
  × 2.0  if RNG(0..99) < (LCK × 5)        // crit
  cap 99
```

Player taken: `max(½, enemy.damage - DEF)`, 30-frame iframes (Penta-matched), knockback ∝ taken.

### Damage numbers (visual)

- 1-digit sprite tiles (0-9 + ½), 8×8 each
- Cap 99 (2 OAM slots max)
- Anim: pop up 6px / 12 frames, fade over 18 more
- Colors: Yellow normal, Red crit, Cyan elemental, White taken, Green heal
- Max 4 concurrent

### HUD strip (top row)

```
♥♥♥♥♥ ½    [MP::::....]    [♠]●●●     999¢
HP            MP bar       active+    coins
                           charge
```
Mini-map in bottom-right.

### Build progression *within* a run

Power = items found. 5 mechanisms:
1. **Pickups** apply `Effect::StatBoost` instantly
2. **Shops** (rest rooms) spend coins
3. **Altars** sacrifice HP/MP/item for buff (Hades risk-reward)
4. **Boss drops** guaranteed Rare/Boss-tier item
5. **Synergies** — composing passives outpaces raw stat ticks

### Cross-run progression (knowledge-only, no stat changes)

| Mechanism | What persists |
|---|---|
| Compendium | Items/enemies/biomes/bosses seen (cosmetic) |
| Class unlocks | New classes appear in CLASS_SELECT via milestones |
| Item-pool unlocks | New items appear in drop pool via achievements |
| Cosmetic palette unlocks | Per-class alt palettes |

**No persistent stat boosts.** Difficulty floor constant.

---

## §7. Save format (SRAM 32KB, 4 × 8KB banks)

### Bank 0 — Suspend save (~360B)

```c
typedef struct {
    uint32_t magic;              // 'QNTR' = 0x52544E51
    uint8_t  version;
    uint8_t  class_id;
    uint8_t  current_biome;
    uint8_t  rooms_cleared;      // depth within biome
    uint32_t run_seed;
    player_state_t player;       // ~256B
    uint8_t  inventory[64];      // item IDs, 0xFF=empty
    uint8_t  active_charge;
    uint16_t coins;
    uint16_t score;
    uint32_t run_timer_ticks;
    uint8_t  checksum;           // CRC8
} suspend_save_t;
```
Written *only* at rest rooms. Death wipes. CRC8 mismatch → discard.

### Bank 1 — Meta-progress (~40B)

```c
typedef struct {
    uint32_t magic;
    uint8_t  version;
    uint8_t  classes_unlocked;   // bitmask
    uint8_t  classes_seen;
    uint8_t  items_seen[16];     // 128-bit
    uint8_t  enemies_seen[8];    // 64-bit
    uint8_t  bosses_seen;
    uint8_t  biomes_seen;
    uint8_t  achievements[8];
    uint8_t  checksum;
} meta_save_t;
```

### Bank 2 — Stats (~200B)

Total runs, wins, deepest biome/depth, per-enemy kills, best time, deaths-by-cause.

### Bank 3 — Reserved

Future save slots.

---

## §8. Testing strategy

### Rust side (`cargo test`)
- Content validation: every ID ref resolves; no orphans/duplicates
- Procgen: seed → identical layout; reachability from start; door-mask consistency
- Codegen: emitted C compiles under SDCC
- Asset pipeline: PNG → tile data correctness

### C side via mGBA MCP harness
- Boot → TITLE (golden screenshot diff at frame 60)
- Each class selectable, palette correct
- Movement: 4 directions, wall collision
- Combat: fire, damage applied, enemy dies, drops
- Pickup: item changes stat per Effect spec
- Room transition: door → next room loads
- Save/load: suspend round-trips bit-for-bit
- Death: GAMEOVER → TITLE; suspend wiped
- Boss: multi-phase pattern advances

### Save-state anchors
Title, mid-combat, rest-room, boss-room-entry for fast regression.

### `make test`
Build → boot → 60 frames headless → screenshot diff vs golden.

---

## §9. Penta Dragon mechanics integration (placeholder)

Awaiting brief from `penta-dragon-dx` session. Likely integration targets:

- **Form transformation** (Witch↔Dragon FFBE) — potential 5th class with toggle-form, or an unlockable hidden class
- **Sub-weapon power-ups** (FFC0 spiral/shield/turbo) — fold into Item pool as `Active`/`Passive` items
- **Boss multi-phase scripts** — informs §3 BOSS screen architecture
- **Hit-stun / iframes** — already match Penta's 30-frame iframe at §6
- **Projectile patterns** — already encoded in `AiScriptId::SprayPattern`, `AimedBurst` per §4

This section will be backfilled as soon as the brief arrives.

---

## Open questions / future revisions

- LCK + crits: keep or drop for simplicity? (Currently kept.)
- 8 biomes ambitious — may collapse to 6 if content authoring time bites.
- Music engine port from current code or replace with hUGEDriver?
- 5 starting classes locked, or only 1-2 unlocked at start to drive meta-progression?

---

## Approval

§§1-4 + §6 green-lit interactively during 2026-06-30 brainstorming session.
§§5, 7-8 added in closeout; user directed "keep going until complete working game" — proceeding to implementation under auto-execution goal.
