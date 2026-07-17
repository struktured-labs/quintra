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

#define ROOMS_PER_STAGE    6   // a large stage boss guards every 6th room
#define BOSS_EVERY_N_ROOMS ROOMS_PER_STAGE   // (legacy alias)
#define BOSSES_TO_WIN      9   // 9 stages -> 9 large bosses to clear the run
#define MINIBOSS_EVERY     3   // rooms 3,9,15... (that aren't stage-boss rooms)

// World cadence: three six-room dungeons make one region. The first room
// after each region is a safe procedural town. This gives the run a Zelda-I
// rhythm (dangerous free-roaming ruins separated by inhabited clearings)
// without abandoning deterministic room generation.
#define DUNGEONS_PER_REGION 3
#define ROOMS_PER_REGION    (ROOMS_PER_STAGE * DUNGEONS_PER_REGION)
#define RUN_ROOM_IS_TOWN(n) ((n) > ROOMS_PER_REGION && ((n) % ROOMS_PER_REGION) == 1)

// During a town, world_return_screen is safely reused as a local plaza index;
// it is reset before entering either a dungeon or Riftwild cave traversal.
#define TOWN_ARRIVAL 0
#define TOWN_MARKET  1
#define TOWN_QUARTER 2

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
    u8  secret_pending;      // next room is a secret treasure room
    u16 score;               // points scored from kills
    u8  enemies_killed;      // run total
    u8  world_mode;          // 1 while traversing the generated 4x4 overworld
    u8  world_screen;        // current overworld screen, row-major 0..15
    u8  world_return_screen; // cave/vault staircase return anchor
    u8  dungeon_seen;        // bit 0..5: rooms revealed in current dungeon
    u16 world_seen;          // bit 0..15: Riftwild cells revealed this stage
    u16 rift_sigils;         // bit 0..8: stage sigil claimed this run
} run_state_t;

#define RUN_STAGE_SIGIL_BIT(stage) ((u16)(1u << ((stage) % BOSSES_TO_WIN)))

extern run_state_t run_state;

void run_state_init(u32 seed);
void run_state_clear(void);
// Current six-cell compass position for the active dungeon. Both map drawing
// and fog-of-war use this so stage transitions cannot drift between them.
u8   run_state_dungeon_cell(void);
void run_state_mark_visited(void);
void run_state_begin_world(void);
void run_state_begin_dungeon(void);

#endif
