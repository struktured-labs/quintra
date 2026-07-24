#ifndef QUINTRA_GAME_PUZZLE_H
#define QUINTRA_GAME_PUZZLE_H

#include <gb/gb.h>
#include "core/types.h"

enum {
    PUZZLE_NONE = 0,
    PUZZLE_PUSH_SEAL,
    PUZZLE_RUNE_SEQUENCE,
    PUZZLE_PHASE_SWITCH,
    PUZZLE_PHASE_GATE,
};

// Hot room code reads these directly for door collision and palette cues.
extern u8 room_puzzle_kind;
extern u8 room_puzzle_locked;
extern u8 room_puzzle_visual_y;

// Deterministically layer this dungeon's puzzle fixture over procgen.
void puzzle_prepare_room(void) BANKED;
// Final room-authoring boundary: prepare a fixture, sanitize procgen marks,
// and publish whether ordinary combat sealing applies.
void puzzle_prepare_room_role(void) BANKED;
u8 puzzle_combat_seal_policy(void) BANKED;

// Returns 1 exactly when a sealed room has just been solved.
u8 puzzle_update_player(void) BANKED;
u8 puzzle_on_block_moved(u8 old_x, u8 old_y) BANKED;

#endif
