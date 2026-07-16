#include "core/types.h"
#include "game/run_state.h"

run_state_t run_state;

void run_state_clear(void) {
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
    run_state.world_mode = 0;
    run_state.world_screen = 0;
    run_state.world_return_screen = 0;
    run_state.dungeon_seen = 1;
    run_state.world_seen = 0;
    run_state.rift_sigils = 0;
}

void run_state_init(u32 seed) {
    run_state_clear();
    run_state.run_seed = (seed == 0UL) ? 0xCAFE1234UL : seed;
    run_state.biome_id = 0;     // Phase 7: only one biome — Crystal Caverns
}

void run_state_mark_visited(void) {
    if (run_state.world_mode) {
        run_state.world_seen |= (u16)(1u << (run_state.world_screen & 15));
    } else {
        u8 local = (u8)(run_state.room_counter % ROOMS_PER_STAGE);
        u8 cell = (local == 0 && run_state.room_counter > 0) ? 5
            : ((run_state.bosses_beaten > 0 && local > 0)
                ? (u8)(local - 1) : (local < 6 ? local : 5));
        run_state.dungeon_seen |= (u8)(1u << cell);
    }
}

void run_state_begin_world(void) {
    run_state.world_mode = 1;
    run_state.world_screen = 0;
    run_state.world_return_screen = 0;
    run_state.world_seen = 1;
}

void run_state_begin_dungeon(void) {
    run_state.world_mode = 0;
    run_state.world_return_screen = TOWN_ARRIVAL;
    run_state.dungeon_seen = 0;
}
