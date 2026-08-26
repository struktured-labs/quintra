#pragma bank 10
// RUN_INIT — initializes run-level state from current entropy + player class
// then immediately transitions to ROOM.

#include <gb/gb.h>

#include "core/types.h"
#include "core/rng.h"
#include "game/class_select.h"
#include "game/loop.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_init.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "game/title.h"

BANKREF(run_init_enter)

// A stage warp approximates the guaranteed prior-Colossus reward curve used
// by the external deep-stage checkpoints. It deliberately grants no rare
// optional relics: this is a credible late-run baseline, not god mode.
static void apply_stage_warp_progression(u8 stage) {
    static const u8 rewards[3] = {
        ITEM_ID_POWER_STONE, ITEM_ID_SWIFT_FANG, ITEM_ID_BLOOD_SIGIL,
    };
    u8 i;
    for (i = 0; i < stage; ++i) {
        u8 item = rewards[i % 3];
        player.inventory[i] = item;
        if (player.atk < 15) player.atk++;
        if (item == ITEM_ID_SWIFT_FANG && player.spd < 9) player.spd++;
        if (item == ITEM_ID_BLOOD_SIGIL && player.hp_max < 30)
            player.hp_max++;
    }
    player.hp = player.hp_max;
    player.coins = (u16)(stage * 8u);
}

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
    if (title_stage_warp < BOSSES_TO_WIN) {
        u8 stage = title_stage_warp;
        run_state.bosses_beaten = stage;
        run_state.room_counter = run_state_stage_start(stage);
        run_state.rooms_cleared = (u8)(stage * 4u);
        run_state.score = (u16)(stage * 750u);
        run_state.enemies_killed = (u8)(stage * 12u);
        run_state.rift_sigils = stage ? (u16)((1u << stage) - 1u) : 0;
        // RUN_STATE_INIT prepared the stage-zero law before the warp existed.
        // Force the selected stage to derive its own seeded law instead.
        run_state.dungeon_law = 0;
        run_state_ensure_dungeon_law();
        apply_stage_warp_progression(stage);
    }
    sram_clear_run();   // a fresh run invalidates any suspend save
}

void run_init_exit(void) {}

screen_id_t run_init_tick(u8 keys, u8 pressed) {
    keys; pressed;
    return SCREEN_ROOM;
}

void run_init_draw(void) {}
