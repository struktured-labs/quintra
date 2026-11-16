#ifndef QUINTRA_GAME_PUZZLE_H
#define QUINTRA_GAME_PUZZLE_H

#include <gb/gb.h>
#include "core/types.h"
#include "render/tiles.h"
#include "game/prism_toggle.h"

enum {
    PUZZLE_NONE = 0,
    PUZZLE_PUSH_SEAL,
    PUZZLE_RUNE_SEQUENCE,
    PUZZLE_PHASE_SWITCH,
    PUZZLE_PHASE_GATE,
    PUZZLE_SUN_LATTICE,
    PUZZLE_PRISM_TOGGLE,
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
// Push Seal socket (2x2 gold plate, top-left), 0xFF when absent.
extern u8 room_socket_x;
extern u8 room_socket_y;

// Deterministically layer this dungeon's puzzle fixture over procgen.
void puzzle_prepare_room(void) BANKED;
// Mandatory puzzle kind for slot 0 (Trial) or 1 (Waystone) this dungeon.
u8 puzzle_slot_kind(u8 slot) BANKED;
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

// Active rune-sequence plates. Valid while room_puzzle_kind is
// PUZZLE_RUNE_SEQUENCE and room_rune_count > 0 (the prepared, unsolved
// or just-solved visit). Cleared at the start of the next room prepare.
extern u8 room_rune_count;
extern u8 room_rune_x[5];
extern u8 room_rune_y[5];
extern u8 room_rune_pitch[5];

// Pitch 0..2 pack into BGPAL_CRYSTAL (colour indices 1..3); pitches 3..4
// pack into BGPAL_DOOR (indices 1..2). Colour 3 of the door palette is
// reserved for the near-white flash-on-play tile (BGT_NOTE_C).
#define RUNE_NOTE_PAL(p) ((u8)((p) <= 2 ? BGPAL_CRYSTAL : BGPAL_DOOR))
#define RUNE_IDLE_TILE(p) ((u8)(BGT_NOTE_0 + (p)))
#define RUNE_LIT_TILE(p)  ((u8)(BGT_NOTE_LIT_0 + (p)))
#define RUNE_IS_PLATE_TILE(t) ((u8)((t) >= BGT_NOTE_0 && (t) <= BGT_NOTE_FLASH))
#define RUNE_PITCH_FROM_TILE(t) ((u8)((t) >= BGT_NOTE_LIT_0 && (t) <= BGT_NOTE_LIT_4     ? (t) - BGT_NOTE_LIT_0 : (t) - BGT_NOTE_0))
#define RUNE_FLASH_TILE BGT_NOTE_FLASH
#define RUNE_FLASH_PAL  BGPAL_DOOR

#define RUNE_ATTR_AT(x, y, tile) \
    ((tile) == BGT_NOTE_FLASH ? BGPAL_DOOR     : ((tile) >= BGT_NOTE_0 && (tile) <= BGT_NOTE_LIT_4)         ? RUNE_NOTE_PAL(RUNE_PITCH_FROM_TILE(tile))     : ((tile) == BGT_DOOR || (tile) == BGT_DOOR_LOCKED         || (tile) == BGT_CRYSTAL || (tile) == BGT_PORTAL) ? BGPAL_CRACK     : 0xFF)

void puzzle_load_note_palettes(void) BANKED;
void tiles_load_note_plates(void) BANKED;
void rune_cancel_flash(void) BANKED;
void rune_start_flash(u8 plate) BANKED;
void tick_rune_flash(void) BANKED;
void rune_paint_all(void) BANKED;
void voice_plate(u8 plate) BANKED;
u8 puzzle_plate_is_lit(u8 plate) BANKED;

// Shared palette override for authored puzzle fixtures (Push Seal socket,
// Prism Toggle chamber). 0xFF means "use the ordinary terrain palette".
// Inline so the hot render paths never pay a far call per tile.
#define PUZZLE_SOCKET_AT(x, y) (room_socket_x != 0xFF \
    && (u8)((u8)(x) - room_socket_x) < 2 && (u8)((u8)(y) - room_socket_y) < 2)
#define PUZZLE_ATTR_OVERRIDE(x, y, tile) \
    ((room_puzzle_kind == PUZZLE_PRISM_TOGGLE) ? PRISM_ATTR_AT(x, y) \
    : (room_puzzle_kind == PUZZLE_PUSH_SEAL && (tile) == BGT_FLOOR3 \
        && PUZZLE_SOCKET_AT(x, y)) ? BGPAL_DOOR \
    : (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE) ? RUNE_ATTR_AT(x, y, tile) \
    : 0xFF)

#endif
