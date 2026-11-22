#pragma bank 24
// Ordinary-room respawn cooldown. Lives with other run_state helpers
// outside bank 0 so _HOME stays inside 0x4000 after the #181 merge.

#include "core/types.h"
#include "game/run_state.h"
#include "game/dungeon_director.h"
#include "game/entity.h"

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
