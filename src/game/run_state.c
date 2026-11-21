#include "core/types.h"
#include "game/run_state.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/player.h"

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

u8 run_state_dungeon_shop_cell(void) {
    u8 size = run_state_dungeon_size();
    return (size >= 3) ? (u8)(size - 3) : 0xFF;
}

u8 run_state_is_shop(void) {
    return (!run_state.world_mode && !run_state_is_boss_room()
        && run_state_dungeon_local() == run_state_dungeon_shop_cell()) ? 1 : 0;
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
        if (run_state.world_screen == RIFTWELL_WORLD_SCREEN)
            run_state.riftwild_flags |= RIFT_REGION_TRADER_FOUND_BIT;
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


u8 room_respawn_bypass;

static u8 room_respawn_tag(void) {
    return run_state.world_mode ? 2 : 1;
}

static u8 room_respawn_excluded(void) {
    u8 local;
    if (room_respawn_bypass) return 1;
    if (run_state_is_boss_room() || run_state_was_cleared_boss()
        || run_state_is_miniboss() || run_state_is_shop()
        || run_state_is_sanctuary()
        || run_state_room_is_town(run_state.room_counter)
        || room_encounter_kind == ENCOUNTER_HUNT
        || room_return_echo_kind)
        return 1;
    if (run_state.world_mode) return 0;
    local = run_state_dungeon_local();
    if (local == run_state.mission_trial_cell
        || local == run_state.mission_waystone_cell
        || local == run_state.mission_deep_switch_cell
        || local == run_state.mission_deep_gate_cell
        || local == run_state.mission_warden_cell
        || local == run_state.mission_sigil_cell
        || local == run_state.mission_deep_warden_cell)
        return 1;
    return 0;
}

u8 run_state_room_on_cooldown(void) BANKED {
    u8 i, tag, id, delta;
    if (room_respawn_excluded()) return 0;
    tag = room_respawn_tag();
    id = run_state.room_counter;
    for (i = 0; i < ROOM_RESPAWN_SLOTS; ++i) {
        if (run_state.room_clear_tag[i] != tag
            || run_state.room_clear_id[i] != id) continue;
        delta = (u8)(run_state.room_visit_seq - run_state.room_clear_seq[i]);
        if (delta < ROOM_RESPAWN_COOLDOWN) return 1;
        run_state.room_clear_tag[i] = 0;
        return 0;
    }
    return 0;
}

void run_state_note_room_visit(void) BANKED {
    run_state.room_visit_seq++;
}

void run_state_record_room_clear(void) BANKED {
    u8 i, tag, id, found, empty, oldest, age, oldest_age;
    if (room_respawn_excluded()) return;
    tag = room_respawn_tag();
    id = run_state.room_counter;
    found = 0xFF;
    empty = 0xFF;
    oldest = 0;
    oldest_age = 0;
    for (i = 0; i < ROOM_RESPAWN_SLOTS; ++i) {
        if (run_state.room_clear_tag[i] == tag
            && run_state.room_clear_id[i] == id) {
            found = i;
            break;
        }
        if (empty == 0xFF && run_state.room_clear_tag[i] == 0)
            empty = i;
        age = (u8)(run_state.room_visit_seq - run_state.room_clear_seq[i]);
        if (age >= oldest_age) {
            oldest_age = age;
            oldest = i;
        }
    }
    if (found == 0xFF)
        found = (empty != 0xFF) ? empty : oldest;
    run_state.room_clear_tag[found] = tag;
    run_state.room_clear_id[found] = id;
    run_state.room_clear_seq[found] = run_state.room_visit_seq;
}

void run_state_despawn_cooled_enemies(void) BANKED {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (entities[i].type == ENT_ENEMY && (entities[i].flags & EF_ACTIVE))
            entity_kill(i);
    }
}
