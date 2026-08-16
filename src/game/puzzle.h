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

enum {
    HIDDEN_SECRET_NONE = 0,
    HIDDEN_SECRET_SHOT,
    HIDDEN_SECRET_WALK,
    HIDDEN_SECRET_PUSH,
};

// Hot room code reads these directly for door collision and palette cues.
extern u8 room_puzzle_kind;
extern u8 room_puzzle_locked;
extern u8 room_puzzle_visual_y;
extern u8 room_puzzle_phase_bit;
// Rare optional secrets deliberately retain ordinary wall/cairn art. These
// coordinates never participate in mandatory dungeon progression.
extern u8 room_hidden_secret_kind;
extern u8 room_hidden_secret_x;
extern u8 room_hidden_secret_y;
extern u8 room_hidden_secret_x2;
extern u8 room_hidden_secret_y2;
extern u8 room_hidden_secret_bit;

// Deterministically layer this dungeon's puzzle fixture over procgen.
void puzzle_prepare_room(void) BANKED;
// Final room-authoring boundary: prepare a fixture, sanitize procgen marks,
// and publish whether ordinary combat sealing applies.
void puzzle_prepare_room_role(void) BANKED;
u8 puzzle_combat_seal_policy(void) BANKED;

// Returns 1 exactly when a sealed room has just been solved.
u8 puzzle_update_player(void) BANKED;
u8 puzzle_on_block_moved(u8 old_x, u8 old_y) BANKED;
u8 puzzle_try_hidden_shot(u8 tx, u8 ty) BANKED;
// Echo Chime resolves the active room's optional disguised secret, if any.
u8 puzzle_chime_reveal(void) BANKED;

#endif
