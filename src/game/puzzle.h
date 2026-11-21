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
    // M1 Rime chamber (rime_room.c): optional, never sealed.
    PUZZLE_RIME_ROOM,
    // M2 Cairn Ford (rewrite_room.c): optional, never sealed.
    PUZZLE_REWRITE_ROOM,
    // M3 Kite Kennel (kite_room.c): optional, never sealed.
    PUZZLE_KITE_ROOM,
    // M4 Lockmire Ferry (lock_room.c): optional, never sealed.
    PUZZLE_LOCK_ROOM,
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
extern u8 room_rune_lit_mask;

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

#define RUNE_ATTR_AT(x, y, tile) puzzle_rune_attr(tile)
// Rooms whose fixtures are note plates: rune phrases and the Aether Lattice
// switch row (PUZZLE_PHASE_SWITCH). Both borrow the packed note palettes.
#define PUZZLE_KIND_HAS_NOTES(k) ((k) == PUZZLE_RUNE_SEQUENCE \
    || (k) == PUZZLE_PHASE_SWITCH)
void puzzle_phase_switch_zap(void) BANKED;
void rune_row_prepare(u8 bit, u8 mix) BANKED;
void rune_row_tick(u8 tx, u8 ty) BANKED;
void rune_echo_tick(void) BANKED;
void rune_echo_cancel(void) BANKED;
void voice_plate_final(u8 plate) BANKED;

// Seeded Aether Lattice phrase, published for tests and palettes.
extern u8 room_row_len;
extern u8 room_row_phrase[5];
extern u8 room_row_progress;
extern u8 room_echo_mode;

void puzzle_load_note_palettes(void) BANKED;
void puzzle_apply_note_palettes(u8 dim) BANKED;
void tiles_load_note_plates(void) BANKED;
void rune_cancel_flash(void) BANKED;
void rune_start_flash(u8 plate) BANKED;
void tick_rune_flash(void) BANKED;
void rune_paint_all(void) BANKED;
void voice_plate(u8 plate) BANKED;
u8 puzzle_rune_attr(u8 tile) BANKED;
#define puzzle_plate_is_lit(plate) ((u8)(room_rune_lit_mask & (u8)(1u << (plate))))

// Shared palette override for authored puzzle fixtures (Push Seal socket,
// Prism Toggle chamber). 0xFF means "use the ordinary terrain palette".
// Inline so the hot render paths never pay a far call per tile.
#define PUZZLE_SOCKET_AT(x, y) (room_socket_x != 0xFF \
    && (u8)((u8)(x) - room_socket_x) < 2 && (u8)((u8)(y) - room_socket_y) < 2)
#define PUZZLE_ATTR_OVERRIDE(x, y, tile) \
    ((room_puzzle_kind == PUZZLE_PRISM_TOGGLE) ? PRISM_ATTR_AT(x, y) \
    : (room_puzzle_kind == PUZZLE_PUSH_SEAL && (tile) == BGT_FLOOR3 \
        && PUZZLE_SOCKET_AT(x, y)) ? BGPAL_DOOR \
    : PUZZLE_KIND_HAS_NOTES(room_puzzle_kind) ? RUNE_ATTR_AT(x, y, tile) \
    : 0xFF)

#endif
