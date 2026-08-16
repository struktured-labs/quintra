#pragma bank 6

#include <gbdk/console.h>

#include "game/inventory_copy.h"
#include "game/run_state.h"
#include "render/text.h"

void inventory_write_current_goal(void) BANKED {
    gotoxy(4, 14);
    if (run_state.world_mode) text_write("FIND DUNGEON");
    else if (RUN_ROOM_IS_TOWN(run_state.room_counter))
        text_write("REST THEN NORTH");
    else if (run_state_is_boss_room()) text_write("BREAK COLOSSUS");
    else if (!(run_state.dungeon_puzzles & RUN_TRIAL_BIT))
        text_write("BREAK TRIAL");
    else if ((run_state.mission_order & 1)
            && !(run_state.dungeon_puzzles & RUN_WARDEN_BOON_BIT))
        text_write("CLEAR WARDEN");
    else if (!(run_state.rift_sigils
            & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten)))
        text_write("FIND SIGIL KEY");
    else if (!(run_state.dungeon_puzzles & RUN_WARDEN_BOON_BIT))
        text_write("CLEAR WARDEN");
    else if (!(run_state.dungeon_puzzles & RUN_WAYSTONE_BIT))
        text_write("WAKE WAYSTONE");
    else if (!(run_state.dungeon_phase & RUN_DEEP_WARDEN_BIT))
        text_write("CLEAR DEEP WARD");
    else if (!(run_state.dungeon_phase & RUN_DEEP_PHASE_OPEN_BIT))
        text_write("OPEN DEEP SEAL");
    else if (!(run_state.dungeon_puzzles & RUN_DEEP_GATE_BIT))
        text_write("CROSS DEEP GATE");
    else text_write("SEEK SKULL GATE");
}
