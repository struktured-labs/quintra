#include "core/types.h"
#include "game/run_state.h"

run_state_t run_state;

// Total screens include the boss arena. The opening dungeon now occupies
// twenty cells and the campaign grows toward a thirty-room Void dungeon.
// Villages own explicit counters 63 and 136 and never shorten the following
// dungeon by occupying a global modulo sequence.
static const u8 stage_start[BOSSES_TO_WIN] = {
    0, 20, 41, 64, 87, 111, 137, 163, 191
};
static const u8 stage_boss_room[BOSSES_TO_WIN] = {
    19, 40, 62, 86, 110, 135, 162, 190, 220
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

u8 run_state_is_shop(void) {
    u8 size = run_state_dungeon_size();
    return (!run_state.world_mode && !run_state_is_boss_room()
        && run_state_dungeon_local() == (u8)(size - 3)) ? 1 : 0;
}

u8 run_state_room_is_town(u8 room_counter) {
    return (room_counter == 63 || room_counter == 136) ? 1 : 0;
}

u16 run_state_enemies_killed_total(void) {
    return (u16)run_state.enemies_killed
        | ((u16)run_state.enemies_killed_hi << 8);
}

u8 run_state_dungeon_cell(void) {
    return run_state_dungeon_local();
}

u8 run_state_dungeon_cell_seen(u8 cell) {
    if (cell < 8) return (run_state.dungeon_seen & (u8)(1u << cell)) ? 1 : 0;
    if (cell < 16)
        return (run_state.dungeon_seen_hi & (u8)(1u << (cell - 8))) ? 1 : 0;
    if (cell < 24)
        return (run_state.dungeon_seen_xhi & (u8)(1u << (cell - 16))) ? 1 : 0;
    if (cell < MAX_DUNGEON_CELLS)
        return (run_state.dungeon_seen_xxhi & (u8)(1u << (cell - 24))) ? 1 : 0;
    return 0;
}

u8 run_state_dungeon_cell_visited(u8 cell) {
    if (cell < 8)
        return (run_state.dungeon_visited & (u8)(1u << cell)) ? 1 : 0;
    if (cell < 16)
        return (run_state.dungeon_visited_hi
            & (u8)(1u << (cell - 8))) ? 1 : 0;
    if (cell < 24)
        return (run_state.dungeon_visited_xhi
            & (u8)(1u << (cell - 16))) ? 1 : 0;
    if (cell < MAX_DUNGEON_CELLS)
        return (run_state.dungeon_visited_xxhi
            & (u8)(1u << (cell - 24))) ? 1 : 0;
    return 0;
}

void run_state_mark_visited(void) {
    if (run_state.world_mode) {
        run_state_reveal_world_cell(run_state.world_screen);
    } else {
        u8 cell = run_state_dungeon_cell();
        if (cell < 8)
            run_state.dungeon_visited |= (u8)(1u << cell);
        else if (cell < 16)
            run_state.dungeon_visited_hi |= (u8)(1u << (cell - 8));
        else if (cell < 24)
            run_state.dungeon_visited_xhi |= (u8)(1u << (cell - 16));
        else if (cell < MAX_DUNGEON_CELLS)
            run_state.dungeon_visited_xxhi |= (u8)(1u << (cell - 24));
        run_state_reveal_dungeon_cell(cell);
    }
}
