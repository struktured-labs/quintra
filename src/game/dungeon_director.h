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
    // Animated biome hazards own the room's existing director update slot,
    // avoiding any new branch in every ordinary 60 Hz room tick.
    ENCOUNTER_STAGE_EVENT,
};

// Procedural room-level roster grammar. Mixed preserves the original
// independent weighted rolls; the other shapes give an ordinary room a
// readable species identity without changing its body count or stage pool.
enum {
    ROOM_ROSTER_MIXED = 0,
    ROOM_ROSTER_BROOD,
    ROOM_ROSTER_PAIR,
    ROOM_ROSTER_COMMAND,
};

// Runtime-only room identity. Directives are deterministic first-visit
// events; suspend/backtrack regeneration falls back to ordinary combat so a
// completed risk room can never be farmed for another boon pair.
extern u8 room_encounter_kind;
extern u8 room_encounter_phase;
extern u16 room_encounter_timer;
extern u8 room_encounter_complete;
extern u8 room_encounter_reward_pending;
extern u8 room_encounter_target;

// Runtime-only roster identity, exposed for live-ROM coverage and future
// Compass/lore presentation. Primary/secondary are content enemy IDs.
extern u8 room_roster_kind;
extern u8 room_roster_primary;
extern u8 room_roster_secondary;

// Immediate cardinal route from the current dungeon cell toward the next
// progression fixture. DIR_NONE means the player is already at that fixture
// (or is outside a dungeon).
extern u8 room_objective_dir;

// Reset before every procgen transaction, then choose one directive after
// deterministic room roles are known.
void dungeon_director_reset(void) BANKED;
void dungeon_director_prepare_roster(u8 eligible) BANKED;
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
