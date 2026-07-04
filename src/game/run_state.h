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

#define BOSS_EVERY_N_ROOMS 5   // a boss guards every 5th room
#define BOSSES_TO_WIN      3   // defeat this many to clear the run

typedef struct {
    u8  biome_id;            // current biome
    u8  room_counter;        // number of rooms entered this run
    u32 run_seed;            // run-level seed (combined w/ room_counter for per-room RNG)
    u8  entered_from;        // DIR_* — which door the player just came through
    u16 run_timer;           // total ticks since run started (1/60 sec)
    u8  rooms_cleared;       // count of rooms where all enemies were defeated
    u8  victory;             // 1 only when BOSSES_TO_WIN bosses are down (final win)
    u8  bosses_beaten;       // bosses defeated so far this run
    u8  pending_unseal;      // set by combat on boss kill; room unseals doors
    u8  secret_pending;      // next room is a secret treasure room
    u16 score;               // points scored from kills
    u8  enemies_killed;      // run total
} run_state_t;

extern run_state_t run_state;

void run_state_init(u32 seed);
void run_state_clear(void);

#endif
