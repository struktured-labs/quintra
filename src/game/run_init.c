// RUN_INIT — initializes run-level state from current entropy + player class
// then immediately transitions to ROOM.

#include "core/types.h"
#include "core/rng.h"
#include "game/class_select.h"
#include "game/loop.h"
#include "game/player.h"
#include "game/run_init.h"
#include "game/run_state.h"
#include "game/sram.h"

void run_init_enter(void) {
    u32 seed = (u32)loop_frame_counter ^ 0xA5A5A5A5UL;
    rng_seed(seed);
    run_state_init(seed ^ 0xDEADBEEFUL);
    run_state.difficulty = class_select_easy_mode
        ? DIFFICULTY_EASY : DIFFICULTY_NORMAL;
    // Easy exists to let a human reach and inspect late content quickly while
    // Normal remains the only balance target. Keep enemy rosters and patterns
    // intact; keep all health visible and make tester clears much faster.
    if (RUN_IS_EASY()) {
        if (player.hp_max < EASY_HP_MAX) player.hp_max = EASY_HP_MAX;
        player.hp = player.hp_max;
        player.atk = (u8)(player.atk + EASY_ATK_BONUS);
        player.def = (u8)(player.def + EASY_DEF_BONUS);
    }
    sram_clear_run();   // a fresh run invalidates any suspend save
}

void run_init_exit(void) {}

screen_id_t run_init_tick(u8 keys, u8 pressed) {
    keys; pressed;
    return SCREEN_ROOM;
}

void run_init_draw(void) {}
