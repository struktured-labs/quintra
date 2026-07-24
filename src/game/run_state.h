// Run-level state — persists for the duration of one run (death wipes it).
#ifndef QUINTRA_GAME_RUN_STATE_H
#define QUINTRA_GAME_RUN_STATE_H

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
// it is reset before entering either a dungeon or Riftwild cave traversal.
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
// While in Riftwild, world_return_screen is a 0..15 cave/vault return
// anchor. Its high bit is otherwise unused and keeps the one-use landmark
// state out of the packed run-state ABI (which is shared with SRAM/tools).
#define RIFTWELL_USED_FLAG 0x80
#define RUN_RIFTWELL_USED() (run_state.world_return_screen & RIFTWELL_USED_FLAG)

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
    u8  enemies_killed;      // run total
    u8  world_mode;          // 1 while traversing the generated 4x4 overworld
    u8  world_screen;        // current overworld screen, row-major 0..15
    u8  world_return_screen; // cave/vault staircase return anchor
    u8  dungeon_seen;        // bit 0..7: rooms revealed in current dungeon
    u16 world_seen;          // bit 0..15: Riftwild cells revealed this stage
    u16 rift_sigils;         // bit 0..8: stage sigil claimed this run
    // Route knowledge purchased or earned in a town applies when the hero
    // next enters a dungeon, not to the town's own compass.
    u8  next_dungeon_reveal; // bit 0..7: cells to reveal on next entry
    u8  difficulty;          // DIFFICULTY_*; persisted with suspended run
    u8  dungeon_puzzles;     // bit 0..7: solved procedural puzzle rooms
    u8  dungeon_phase;       // bit 0: phase wall; bit 7: deep-Warden clear
    u8  dungeon_seen_hi;     // bit 0..7: visited dungeon cells 8..15
    u8  next_dungeon_reveal_hi; // queued chart knowledge for cells 8..15
    u8  dungeon_seen_xhi;    // bit 0..7: visited dungeon cells 16..23
    u8  next_dungeon_reveal_xhi; // queued chart knowledge for cells 16..23
    u8  dungeon_seen_xxhi;   // bit 0..5: visited dungeon cells 24..29
    u8  next_dungeon_reveal_xxhi; // queued chart knowledge for cells 24..29
} run_state_t;

#define RUN_IS_EASY() (run_state.difficulty == DIFFICULTY_EASY)

#define RUN_STAGE_SIGIL_BIT(stage) ((u16)(1u << ((stage) % BOSSES_TO_WIN)))
// Local room 3 is every dungeon's first Warden encounter. Its existing
// class-changing weapon reward is also the stage's required Warden Boon.
// Reuse that room's persisted puzzle bit so suspend saves remember the clear
// without expanding the packed run-state ABI.
#define RUN_WARDEN_BOON_BIT ((u8)(1u << 3))
// Roomier dungeons deliberately route through their authored back-half
// fixtures. Local room 7's puzzle becomes the Waystone needed from twelve
// cells onward; local room 9's second Warden is required from fourteen onward.
// Both reuse persistent bytes that already survive suspend without changing
// the packed run-state ABI.
#define RUN_WAYSTONE_BIT     ((u8)(1u << 7))
#define RUN_PHASE_OPEN_BIT   ((u8)(1u << 0))
#define RUN_DEEP_WARDEN_BIT  ((u8)(1u << 7))

extern run_state_t run_state;

void run_state_init(u32 seed);
void run_state_clear(void);
// Explicit stage topology. Later dungeons grow without allowing village
// counters to steal rooms from the following stage.
u8   run_state_stage_start(u8 stage);
u8   run_state_boss_room(u8 stage);
u8   run_state_dungeon_size(void);
u8   run_state_dungeon_local(void);
u8   run_state_dungeon_cell(void);
// Return the local cell of the reciprocal 6x5 maze neighbour in `dir`, or
// 0xFF when that edge is absent. The graph always owns a winding snake spine;
// one seed-stable vertical seam adds a loop without restoring the compact
// fully connected rectangle.
u8   run_state_dungeon_cell_neighbor(u8 cell, u8 dir);
u8   run_state_dungeon_cells_connected(u8 a, u8 b);
// Return the global room counter of the reciprocal 6x5 neighbour in `dir`,
// or 0xFF when that edge leaves the active stage footprint.
u8   run_state_dungeon_neighbor(u8 dir);
u8   run_state_is_boss_room(void);
u8   run_state_was_cleared_boss(void);
u8   run_state_is_sanctuary(void);
u8   run_state_is_miniboss(void);
u8   run_state_is_shop(void);
u8   run_state_room_is_town(u8 room_counter);
u8   run_state_dungeon_cell_seen(u8 cell);
void run_state_reveal_dungeon_cell(u8 cell);
void run_state_mark_visited(void);
void run_state_begin_world(void);
void run_state_begin_dungeon(void);

#endif
