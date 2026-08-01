#ifndef QUINTRA_GAME_DUNGEON_DIRECTOR_H
#define QUINTRA_GAME_DUNGEON_DIRECTOR_H

#include <gb/gb.h>
#include "core/types.h"

enum {
    ENCOUNTER_SKIRMISH = 0,
    ENCOUNTER_TRAP,
    ENCOUNTER_WAVE,
    ENCOUNTER_ELITE,
    ENCOUNTER_HOLD,
};

// Runtime-only room identity. Directives are deterministic first-visit
// events; suspend/backtrack regeneration falls back to ordinary combat so a
// completed risk room can never be farmed for another boon pair.
extern u8 room_encounter_kind;
extern u8 room_encounter_phase;
extern u16 room_encounter_timer;
extern u8 room_encounter_complete;

// Immediate cardinal route from the current dungeon cell toward the next
// progression fixture. DIR_NONE means the player is already at that fixture
// (or is outside a dungeon).
extern u8 room_objective_dir;

// Reset before every procgen transaction, then choose one directive after
// deterministic room roles are known.
void dungeon_director_reset(void) BANKED;
void dungeon_director_choose(u8 eligible, u8 was_seen) BANKED;
u8 dungeon_director_adjust_initial_count(u8 proposed) BANKED;
u8 dungeon_director_pick_stage_enemy(u8 stage) BANKED;
void dungeon_director_configure_initial(u8 entity_index, u8 ordinal) BANKED;

// Apply the directive's door contract after puzzle preparation and refresh
// the route cue before rendering.
void dungeon_director_activate(void) BANKED;
void dungeon_director_refresh_route(void) BANKED;

// Per-frame special-room state machine. Returns the live hostile count after
// any just-in-time wave spawn. room_encounter_complete pulses for one frame
// when HOLD/ELITE/WAVE/TRAP releases the room.
u8 dungeon_director_update(u8 alive) BANKED;

// Spatial objective helpers shared with the SELECT Compass.
u8 dungeon_director_goal_cell(void) BANKED;
u8 dungeon_director_direction_from(u8 start) BANKED;

#define ENCOUNTER_TARGET_TAG 0xD7

#endif
