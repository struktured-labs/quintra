#ifndef QUINTRA_GAME_ROOM_H
#define QUINTRA_GAME_ROOM_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

// Visible BG grid: 20 cols × 17 rows (136 px). The bottom 8 px of the
// screen belong to the HUD WINDOW strip — GB windows extend to the bottom
// of the frame, so the HUD must be the LAST rows, and the room must end
// above it. No scrolling yet.
#define ROOM_W 20
#define ROOM_H 17

extern u8 room_tilemap[ROOM_H][ROOM_W];
extern u8 room_transform_ticks;
// Runtime contract exposed for emulator instrumentation: only authored seal
// encounters lock unexplored exits while hostiles remain.
extern u8 room_combat_sealed;
// Progression-fixture transaction marker for emulator contract tests.
// 5 means the current dungeon's Rift Sigil was successfully placed.
extern u8 room_sigil_status;

// Tile id at world pixel position (BGT_WALL for out-of-bounds).
u8 room_tile_at_px(i16 px, i16 py) BANKED;
// 1 if the tile id is walkable / passable for entities+bullets.
u8 room_tile_walkable(u8 t) BANKED;
// A player shot hit a cracked wall: convert it to a secret door.
void room_open_secret(u8 tx, u8 ty) BANKED;
// A player shot shattered a crystal: floor it, maybe drop a +1 MP wisp.
void room_break_crystal(u8 tx, u8 ty) BANKED;
// A player shot smashed a pot: floor it and roll a loot drop.
void room_break_pot(u8 tx, u8 ty) BANKED;

// Impact shake: wiggle the BG scroll (HUD unaffected) for a few frames.
// mag = pixels (1-2 sensible); longer of current/new duration wins.
void room_shake(u8 mag, u8 frames) BANKED;

// Request that the next room_enter resume the CURRENT room (skip procgen)
// instead of generating a new one — used when returning from the pack screen.
void room_request_resume(void) BANKED;

void        room_enter(void);
void        room_exit(void);
screen_id_t room_tick(u8 keys, u8 pressed);
void        room_draw(void);

#endif
