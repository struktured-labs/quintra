// Run-level state — persists for the duration of one run (death wipes it).
#ifndef QUINTRA_GAME_RUN_STATE_H
#define QUINTRA_GAME_RUN_STATE_H

#include <gb/gb.h>
#include "core/types.h"

// Directions (door entry/exit)
enum {
    DIR_N = 0,
    DIR_E,
    DIR_S,
    DIR_W,
    DIR_NONE = 0xFF,
};

#define ROOMS_PER_STAGE    6   // legacy pre-topology save/reference constant
#define DUNGEON_GRID_W     6
#define DUNGEON_GRID_H     5
#define MAX_DUNGEON_CELLS 30
#define BOSSES_TO_WIN      9   // 9 stages -> 9 large bosses to clear the run
#define MINIBOSS_EVERY     3   // rooms 3,9,15... (that aren't stage-boss rooms)

// World cadence: three dungeons make one region. The first room after each
// region is a safe procedural town. This gives the run a Zelda-I
// rhythm (dangerous free-roaming ruins separated by inhabited clearings)
// without abandoning deterministic room generation.
#define DUNGEONS_PER_REGION 3
#define RUN_ROOM_IS_TOWN(n) run_state_room_is_town(n)

// During a town, world_return_screen is safely reused as a local plaza index;
// regional persistence lives in appended dedicated bytes instead.
#define TOWN_ARRIVAL 0
#define TOWN_MARKET  1
#define TOWN_QUARTER 2

// Normal is the authored/release balance target. Easy is an intentionally
// generous playtest aid: it keeps every heart visible, strengthens the chosen
// champion, and caps damage without changing procgen, encounters, boss
// patterns, or route logic. Tune Easy only after Normal.
#define DIFFICULTY_NORMAL 0
#define DIFFICULTY_EASY   1
#define EASY_HP_MAX       16  // eight visible HUD hearts
#define EASY_ATK_BONUS     4
#define EASY_DEF_BONUS     2
#define EASY_IFRAME_MULTIPLIER 4 // coarse deep-test assist; Normal cadence is canonical

// Every post-boss Riftwild opens on screen zero and reaches the next dungeon
// through screen one.  Pinning the restorative landmark there makes it a
// readable, lore-like fixture between otherwise generated expeditions rather
// than a hidden roll the player can never reasonably plan around.
#define RIFTWELL_WORLD_SCREEN 1
// While in Riftwild, world_return_screen is a 0..35 cave/vault return anchor.
// The legacy high bit remains readable for old suspends; new runs keep
// one-use state in riftwild_flags so a town cannot erase a whole region.
#define RIFTWELL_USED_FLAG 0x80
#define RIFT_REGION_WELL_USED_BIT  0x01
#define RIFT_REGION_VAULT_USED_BIT 0x02
#define RIFT_REGION_GUARD_1_BIT    0x04
#define RIFT_REGION_GUARD_2_BIT    0x08
#define RIFT_REGION_GUARD_3_BIT    0x10
#define RIFT_REGION_READY_BIT      0x80
#define RIFTWILD_WAKING 0
#define RIFTWILD_HOLLOW 1
#define RIFT_SHADOW_HOLLOW_BIT 0x01
#define RIFT_SHADOW_RELIC_1_BIT 0x02
#define RIFT_SHADOW_RELIC_2_BIT 0x04
#define RIFT_SHADOW_RELIC_3_BIT 0x08
#define RIFT_SHADOW_RELIC_MASK  0x0E
#define RUN_RIFTWILD_IS_HOLLOW() ((run_state.riftwild_shadow \
    & RIFT_SHADOW_HOLLOW_BIT) ? 1 : 0)
#define RUN_RIFTWELL_USED() ((run_state.riftwild_flags \
    & RIFT_REGION_WELL_USED_BIT) \
    || (run_state.world_return_screen & RIFTWELL_USED_FLAG))

typedef struct {
    u8  biome_id;            // current biome
    u8  room_counter;        // number of rooms entered this run
    u32 run_seed;            // run-level seed (combined w/ room_counter for per-room RNG)
    u8  entered_from;        // DIR_* — which door the player just came through
    u16 run_timer;           // active-play seconds since the run started
    u8  rooms_cleared;       // count of rooms where all enemies were defeated
    u8  victory;             // 1 only when BOSSES_TO_WIN bosses are down (final win)
    u8  bosses_beaten;       // bosses defeated so far this run
    u8  pending_unseal;      // set by combat on boss kill; room unseals doors
    u8  secret_pending;      // 0 normal, 1 entering cache, 2 inside cache
    u16 score;               // points scored from kills
    u8  enemies_killed;      // run total, low byte (legacy ABI position)
    u8  world_mode;          // 1 while traversing the generated Riftwild
    u8  world_screen;        // current field, row-major 0..35
    u8  world_return_screen; // cave/vault staircase return anchor
    u8  dungeon_seen;        // bit 0..7: rooms revealed in current dungeon
    u16 world_seen;          // bit 0..15: legacy low Riftwild exploration
    u16 rift_sigils;         // bit 0..8: stage sigil claimed this run
    // Route knowledge purchased or earned in a town applies when the hero
    // next enters a dungeon, not to the town's own compass.
    u8  next_dungeon_reveal; // bit 0..7: cells to reveal on next entry
    u8  difficulty;          // DIFFICULTY_*; persisted with suspended run
    u8  dungeon_puzzles;     // bit 0..7: solved procedural puzzle rooms
    u8  dungeon_phase;       // route/cache/hidden-secret state; see masks below
    u8  dungeon_seen_hi;     // bit 0..7: visited dungeon cells 8..15
    u8  next_dungeon_reveal_hi; // queued chart knowledge for cells 8..15
    u8  dungeon_seen_xhi;    // bit 0..7: visited dungeon cells 16..23
    u8  next_dungeon_reveal_xhi; // queued chart knowledge for cells 16..23
    u8  dungeon_seen_xxhi;   // bit 0..5: visited dungeon cells 24..29
    u8  next_dungeon_reveal_xxhi; // queued chart knowledge for cells 24..29
    u8  enemies_killed_hi;   // high byte; long/dense runs exceed 255 hostiles
    // Seeded dungeon-wide two-state rule. Low bits choose its material
    // grammar; bit 7 is the current WAX/WANE state; bit 6 marks initialized.
    // Appended so every historical run-state offset remains stable.
    u8  dungeon_law;
    // Generated before any room in the stage. These cells turn the maze into
    // a seed-stable mission graph instead of pinning lore roles to 1/2/3/7.
    // mission_order bit 0 chooses whether the Warden or Sigil branch is
    // required first; every other dependency remains readable campaign lore.
    u8  mission_ready;
    u8  mission_order;
    u8  mission_trial_cell;
    u8  mission_sigil_cell;
    u8  mission_warden_cell;
    u8  mission_waystone_cell;
    u8  mission_deep_warden_cell;
    u8  mission_deep_switch_cell;
    u8  mission_deep_gate_cell;
    // One persistent Riftwild serves a complete three-dungeon region.
    // Geography/seen cells and these landmark flags survive dungeon trips;
    // the region id changes only after the third and sixth Colossi.
    u8  riftwild_region;
    u8  riftwild_flags;
    // Appended exploration bits grow the regional graph to 36 scrolling
    // fields without shifting any historical suspend/debug offsets.
    u8  world_seen_hi;       // cells 16..23
    u8  world_seen_xhi;      // cells 24..31
    u8  world_seen_xxhi;     // cells 32..35 (upper nibble reserved)
    // Low six bits: active seconds until ASK recovers. High bits persist the
    // optional cache discovery/reveal without shifting the suspend ABI. The
    // companion role is derived once from the run seed and stays stable.
    u8  companion_cooldown;
    // One return-route surprise per completed objective leg. Each bit records
    // that the matching progress phase already spent its echo ambush.
    u8  return_echo_flags;
    // Compass knowledge is not proof of travel. Keep a second four-byte map
    // for rooms the champion actually entered so Cartographer/ASK reveals
    // cannot spring a "return" encounter on a first visit.
    u8  dungeon_visited;
    u8  dungeon_visited_hi;
    u8  dungeon_visited_xhi;
    u8  dungeon_visited_xxhi;
    // Waking/Hollow counterpart state. Bit zero is the currently manifested
    // reality; bits 1..3 persist the three Hollow-only relic claims for this
    // three-dungeon region. Appended to preserve the complete historical ABI.
    u8  riftwild_shadow;
} run_state_t;

#define DUNGEON_LAW_KIND_MASK 0x03
#define DUNGEON_LAW_READY_BIT 0x40
#define DUNGEON_LAW_STATE_BIT 0x80
#define MISSION_GRAPH_READY    0xA5

#define RUN_IS_EASY() (run_state.difficulty == DIFFICULTY_EASY)

#define RUN_STAGE_SIGIL_BIT(stage) ((u16)(1u << ((stage) % BOSSES_TO_WIN)))
#define RUN_TRIAL_BIT       ((u8)(1u << 0))
#define RUN_REAPER_CLEARED_BIT ((u8)(1u << 2))
#define RUN_REAPER_HUNT_BIT    ((u8)(1u << 7))
#define RUN_WARDEN_BOON_BIT ((u8)(1u << 3))
#define RUN_DEEP_GATE_BIT    ((u8)(1u << 6))
#define RUN_WAYSTONE_BIT     ((u8)(1u << 7))
#define RUN_PHASE_OPEN_BIT   ((u8)(1u << 0))
#define RUN_FARFOLD_CACHE_BIT ((u8)(1u << 1))
#define RUN_DEEP_PHASE_OPEN_BIT ((u8)(1u << 2))
#define RUN_HIDDEN_SECRET_BIT(slot) ((u8)(1u << (3 + ((slot) & 3))))
#define RUN_HIDDEN_SECRET_MASK ((u8)0x78)
#define RUN_DEEP_WARDEN_BIT  ((u8)(1u << 7))

extern run_state_t run_state;

// Cold, once-per-run initialization lives outside scarce always-mapped ROM.
void run_state_init(u32 seed) BANKED;
// Explicit stage topology. Later dungeons grow without allowing village
// counters to steal rooms from the following stage.
u8   run_state_stage_start(u8 stage);
u8   run_state_boss_room(u8 stage);
u8   run_state_dungeon_size(void);
u8   run_state_dungeon_local(void);
u8   run_state_dungeon_cell(void);
// Return the local cell of the reciprocal 6x5 maze neighbour in `dir`, or
// 0xFF when that edge is absent. Seed-selected safe folds give each dungeon
// horizontal districts, meaningful branches/dead ends, and one fixed
// objective loop between cells 1 and 10. The fold table preserves the staged
// Sigil/Warden/Waystone route while making macro topology procgen-first.
u8   run_state_dungeon_cell_neighbor(u8 cell, u8 dir) BANKED;
u8   run_state_dungeon_cells_connected(u8 a, u8 b) BANKED;
// Return one generated optional dead-end room which owns this dungeon's
// Farfold Cache. The cache is never placed on a lore fixture or service room.
u8   run_state_dungeon_cache_cell(void) BANKED;
// Return the global room counter of the reciprocal 6x5 neighbour in `dir`,
// or 0xFF when that edge leaves the active stage footprint.
u8   run_state_dungeon_neighbor(u8 dir) BANKED;
u8   run_state_is_boss_room(void);
u8   run_state_was_cleared_boss(void);
u8   run_state_is_sanctuary(void);
u8   run_state_is_miniboss(void) BANKED;
u8   run_state_is_shop(void);
u8   run_state_room_is_town(u8 room_counter);
u8   run_state_dungeon_cell_seen(u8 cell);
u8   run_state_dungeon_cell_visited(u8 cell);
void run_state_reveal_dungeon_cell(u8 cell) BANKED;
void run_state_mark_visited(void);
u8   run_state_world_cell_seen(u8 cell) BANKED;
void run_state_reveal_world_cell(u8 cell) BANKED;
void run_state_begin_world(void) BANKED;
void run_state_begin_dungeon(void) BANKED;
u8   run_state_riftwild_gate_screen(void) BANKED;
u8   run_state_riftwild_gate_active(u8 screen) BANKED;
u8   run_state_riftwild_guard_active(u8 screen) BANKED;
u8   run_state_riftwild_guard_cleared(u8 screen) BANKED;
u8   run_state_riftwild_guard_gear(u8 screen) BANKED;
void run_state_riftwild_clear_guard(void) BANKED;
void run_state_ensure_dungeon_law(void) BANKED;
u16  run_state_enemies_killed_total(void);
void run_state_record_enemy_kill(void) BANKED;

#endif
