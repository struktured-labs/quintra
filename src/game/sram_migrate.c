#pragma bank 6

#include <gb/gb.h>

#include "core/types.h"
#include "game/run_state.h"

#define PRE_WIDE_MAP_RS_SIZE 29

// Cold compatibility path for pre-v0.18.60 suspend saves. Keeping this in the
// spacious utility bank preserves always-mapped headroom without charging hot
// save/resume calls for code that executes at most once per migrated run.
void sram_migrate_run(u8 saved_rs) BANKED {
    u8 stage = run_state.bosses_beaten;
    if (saved_rs == PRE_WIDE_MAP_RS_SIZE) {
        if (run_state.world_mode && stage)
            run_state.room_counter = run_state_boss_room((u8)(stage - 1));
        else if (stage == 3 && run_state.room_counter == 19)
            run_state.room_counter = 45;
        else if (stage == 6 && run_state.room_counter == 37)
            run_state.room_counter = 97;
        else {
            u8 old_start = stage ? (u8)(stage * 6 + 1) : 0;
            u8 old_local = (run_state.room_counter > old_start)
                ? (u8)(run_state.room_counter - old_start) : 0;
            u8 new_last = (u8)(run_state_dungeon_size() - 1);
            if (old_local > new_last) old_local = new_last;
            run_state.room_counter =
                (u8)(run_state_stage_start(stage) + old_local);
        }
    } else {
        static const u8 old_start[BOSSES_TO_WIN] = {
            0, 10, 21, 34, 46, 59, 74, 88, 103
        };
        static const u8 old_boss[BOSSES_TO_WIN] = {
            9, 20, 32, 45, 58, 72, 87, 102, 118
        };
        if (run_state.world_mode && stage)
            run_state.room_counter = run_state_boss_room((u8)(stage - 1));
        else if (stage == 3 && run_state.room_counter == 33)
            run_state.room_counter = 45;
        else if (stage == 6 && run_state.room_counter == 73)
            run_state.room_counter = 97;
        else {
            u8 old_local = (run_state.room_counter > old_start[stage])
                ? (u8)(run_state.room_counter - old_start[stage]) : 0;
            u8 old_last = (u8)(old_boss[stage] - old_start[stage]);
            u8 new_last = (u8)(run_state_dungeon_size() - 1);
            if (old_local >= old_last)
                old_local = new_last;
            else if (old_local + 1 == old_last)
                old_local = (u8)(new_last - 1);
            run_state.room_counter =
                (u8)(run_state_stage_start(stage) + old_local);
        }
    }
}
