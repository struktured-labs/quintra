#pragma bank 14

#include "core/types.h"
#include "game/run_state.h"

static void clear_run_state(void) {
    run_state.biome_id       = 0;
    run_state.room_counter   = 0;
    run_state.run_seed       = 0xCAFE1234UL;
    run_state.entered_from   = DIR_NONE;
    run_state.run_timer      = 0;
    run_state.rooms_cleared  = 0;
    run_state.victory        = 0;
    run_state.bosses_beaten  = 0;
    run_state.pending_unseal = 0;
    run_state.secret_pending = 0;
    run_state.score          = 0;
    run_state.enemies_killed = 0;
    run_state.enemies_killed_hi = 0;
    run_state.world_mode = 0;
    run_state.world_screen = 0;
    run_state.world_return_screen = 0;
    run_state.dungeon_seen = 1;
    run_state.world_seen = 0;
    run_state.rift_sigils = 0;
    run_state.next_dungeon_reveal = 0;
    run_state.difficulty = DIFFICULTY_NORMAL;
    run_state.dungeon_puzzles = 0;
    run_state.dungeon_phase = 0;
    run_state.dungeon_seen_hi = 0;
    run_state.next_dungeon_reveal_hi = 0;
    run_state.dungeon_seen_xhi = 0;
    run_state.next_dungeon_reveal_xhi = 0;
    run_state.dungeon_seen_xxhi = 0;
    run_state.next_dungeon_reveal_xxhi = 0;
    run_state.dungeon_law = 0;
    run_state.mission_ready = 0;
    run_state.riftwild_region = 0;
    run_state.riftwild_flags = 0;
    run_state.world_seen_hi = 0;
    run_state.world_seen_xhi = 0;
    run_state.world_seen_xxhi = 0;
    run_state.companion_cooldown = 0;
    run_state.return_echo_flags = 0;
    run_state.dungeon_visited = 1;
    run_state.dungeon_visited_hi = 0;
    run_state.dungeon_visited_xhi = 0;
    run_state.dungeon_visited_xxhi = 0;
    run_state.riftwild_shadow = 0;
}

void run_state_init(u32 seed) BANKED {
    clear_run_state();
    run_state.run_seed = (seed == 0UL) ? 0xCAFE1234UL : seed;
    run_state.biome_id = 0;
    run_state_ensure_dungeon_law();
}
