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
    run_state.next_dungeon_reveal = 0;
}

void run_state_init(u32 seed) {
    run_state_clear();
    run_state.run_seed = (seed == 0UL) ? 0xCAFE1234UL : seed;
    run_state.biome_id = 0;     // Phase 7: only one biome — Crystal Caverns
}

u8 run_state_dungeon_cell(void) {
    u8 local = (u8)(run_state.room_counter % ROOMS_PER_STAGE);
    // The boss is always the final compass cell. After a cleared boss, room
    // counters continue globally, so the next dungeon's local rooms shift
    // back into cells 0..4 instead of leaving a phantom first slot.
    if (local == 0 && run_state.room_counter > 0) return 5;
    if (run_state.bosses_beaten > 0 && local > 0) return (u8)(local - 1);
    return local;
}

void run_state_mark_visited(void) {
    if (run_state.world_mode) {
        run_state.world_seen |= (u16)(1u << (run_state.world_screen & 15));
    } else {
        run_state.dungeon_seen |= (u8)(1u << run_state_dungeon_cell());
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
    // Town chart knowledge intentionally survives the doorway. The prior
    // chartwright wrote directly to dungeon_seen here, so its visible
    // blessing was silently erased during the transition.
    run_state.dungeon_seen = run_state.next_dungeon_reveal;
    run_state.next_dungeon_reveal = 0;
}
