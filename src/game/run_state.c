#include "core/types.h"
#include "game/run_state.h"

run_state_t run_state;

// Total screens include the boss arena. Fourteen rooms gives the opening
// dungeon enough space to establish an entry, puzzle, Sigil, miniboss, shop,
// sanctuary, and genuine exploration between them. The campaign then grows
// toward a twenty-room Void dungeon. Villages own explicit counters 45 and 97 and
// never shorten the next dungeon by occupying a global modulo sequence.
static const u8 stage_start[BOSSES_TO_WIN] = {
    0, 14, 29, 46, 62, 79, 98, 116, 135
};
static const u8 stage_boss_room[BOSSES_TO_WIN] = {
    13, 28, 44, 61, 78, 96, 115, 134, 154
};

static u8 campaign_stage(u8 stage) {
    return (stage < BOSSES_TO_WIN) ? stage : (BOSSES_TO_WIN - 1);
}

u8 run_state_stage_start(u8 stage) {
    return stage_start[campaign_stage(stage)];
}

u8 run_state_boss_room(u8 stage) {
    return stage_boss_room[campaign_stage(stage)];
}

u8 run_state_dungeon_size(void) {
    u8 stage = campaign_stage(run_state.bosses_beaten);
    return (u8)(stage_boss_room[stage] - stage_start[stage] + 1);
}

u8 run_state_dungeon_local(void) {
    u8 start = run_state_stage_start(run_state.bosses_beaten);
    if (run_state.room_counter <= start) return 0;
    {
        u8 local = (u8)(run_state.room_counter - start);
        u8 last = (u8)(run_state_dungeon_size() - 1);
        return (local < last) ? local : last;
    }
}

u8 run_state_is_boss_room(void) {
    return (!run_state.world_mode
        && run_state.room_counter
            == run_state_boss_room(run_state.bosses_beaten)) ? 1 : 0;
}

u8 run_state_was_cleared_boss(void) {
    return (run_state.bosses_beaten
        && run_state.room_counter
            == run_state_boss_room((u8)(run_state.bosses_beaten - 1))) ? 1 : 0;
}

u8 run_state_is_sanctuary(void) {
    return (!run_state.world_mode
        && run_state.room_counter + 1
            == run_state_boss_room(run_state.bosses_beaten)) ? 1 : 0;
}

u8 run_state_is_miniboss(void) {
    u8 local = run_state_dungeon_local();
    return (!run_state.world_mode && !run_state_is_boss_room()
        && (local == 3
            || (run_state_dungeon_size() >= 14 && local == 9)
            || (run_state_dungeon_size() >= 19 && local == 15))) ? 1 : 0;
}

u8 run_state_is_shop(void) {
    u8 size = run_state_dungeon_size();
    return (!run_state.world_mode && !run_state_is_boss_room()
        && run_state_dungeon_local() == (u8)(size - 3)) ? 1 : 0;
}

u8 run_state_room_is_town(u8 room_counter) {
    return (room_counter == 45 || room_counter == 97) ? 1 : 0;
}

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
    run_state.difficulty = DIFFICULTY_NORMAL;
    run_state.dungeon_puzzles = 0;
    run_state.dungeon_phase = 0;
    run_state.dungeon_seen_hi = 0;
    run_state.next_dungeon_reveal_hi = 0;
    run_state.dungeon_seen_xhi = 0;
    run_state.next_dungeon_reveal_xhi = 0;
}

void run_state_init(u32 seed) {
    run_state_clear();
    run_state.run_seed = (seed == 0UL) ? 0xCAFE1234UL : seed;
    run_state.biome_id = 0;     // Phase 7: only one biome — Crystal Caverns
}

u8 run_state_dungeon_cell(void) {
    return run_state_dungeon_local();
}

u8 run_state_dungeon_neighbor(u8 dir) {
    u8 local = run_state_dungeon_local();
    u8 row = (u8)(local / DUNGEON_GRID_W);
    u8 offset = (u8)(local % DUNGEON_GRID_W);
    u8 col = (row & 1) ? (u8)((DUNGEON_GRID_W - 1) - offset) : offset;
    u8 next;
    if (dir == DIR_N) {
        if (row == 0) return 0xFF;
        row--;
    } else if (dir == DIR_E) {
        if (col == DUNGEON_GRID_W - 1) return 0xFF;
        col++;
    } else if (dir == DIR_S) {
        if (row == DUNGEON_GRID_H - 1) return 0xFF;
        row++;
    } else if (dir == DIR_W) {
        if (col == 0) return 0xFF;
        col--;
    } else return 0xFF;
    next = (u8)(row * DUNGEON_GRID_W
        + ((row & 1) ? ((DUNGEON_GRID_W - 1) - col) : col));
    if (next >= run_state_dungeon_size()) return 0xFF;
    return (u8)(run_state_stage_start(run_state.bosses_beaten) + next);
}

u8 run_state_dungeon_cell_seen(u8 cell) {
    if (cell < 8) return (run_state.dungeon_seen & (u8)(1u << cell)) ? 1 : 0;
    if (cell < MAX_DUNGEON_CELLS)
        return cell < 16
            ? ((run_state.dungeon_seen_hi & (u8)(1u << (cell - 8))) ? 1 : 0)
            : ((run_state.dungeon_seen_xhi & (u8)(1u << (cell - 16))) ? 1 : 0);
    return 0;
}

void run_state_reveal_dungeon_cell(u8 cell) {
    if (cell < 8) run_state.dungeon_seen |= (u8)(1u << cell);
    else if (cell < 16)
        run_state.dungeon_seen_hi |= (u8)(1u << (cell - 8));
    else if (cell < MAX_DUNGEON_CELLS)
        run_state.dungeon_seen_xhi |= (u8)(1u << (cell - 16));
}

void run_state_mark_visited(void) {
    if (run_state.world_mode) {
        run_state.world_seen |= (u16)(1u << (run_state.world_screen & 15));
    } else {
        run_state_reveal_dungeon_cell(run_state_dungeon_cell());
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
    run_state.dungeon_seen_hi = run_state.next_dungeon_reveal_hi;
    run_state.dungeon_seen_xhi = run_state.next_dungeon_reveal_xhi;
    run_state.next_dungeon_reveal = 0;
    run_state.next_dungeon_reveal_hi = 0;
    run_state.next_dungeon_reveal_xhi = 0;
    run_state.dungeon_puzzles = 0;
    run_state.dungeon_phase = 0;
}
