#pragma bank 13

#include "core/types.h"
#include "game/run_state.h"

// Cold progression mutations live with the status scheduler in the roomy
// development bank. Queries used by movement, maps, and procgen remain in
// ROM0; a kill, room arrival, or dungeon-law setup can afford one far call.
void run_state_record_enemy_kill(void) BANKED {
    if (run_state.enemies_killed == 0xFF) {
        if (run_state.enemies_killed_hi == 0xFF) return;
        run_state.enemies_killed = 0;
        run_state.enemies_killed_hi++;
    } else {
        run_state.enemies_killed++;
    }
}

void run_state_reveal_dungeon_cell(u8 cell) BANKED {
    if (cell < 8) run_state.dungeon_seen |= (u8)(1u << cell);
    else if (cell < 16)
        run_state.dungeon_seen_hi |= (u8)(1u << (cell - 8));
    else if (cell < 24)
        run_state.dungeon_seen_xhi |= (u8)(1u << (cell - 16));
    else if (cell < MAX_DUNGEON_CELLS)
        run_state.dungeon_seen_xxhi |= (u8)(1u << (cell - 24));
}
