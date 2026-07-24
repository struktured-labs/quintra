#ifndef QUINTRA_GAME_ROOM_H
#define QUINTRA_GAME_ROOM_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

// Visible BG grid: 20 cols × 17 rows (136 px). The bottom 8 px of the
// screen belong to the HUD WINDOW strip — GB windows extend to the bottom
// of the frame, so the HUD must be the LAST rows. Most rooms remain exactly
// one viewport; authored arenas may expose more of the 32-tile hardware BG
// through room_world_width and room_camera_x.
#define ROOM_W 20
#define ROOM_H 17
#define ROOM_VIEW_W_PX (ROOM_W * 8)
#define ROOM_CRYSTAL_W_TILES 28
#define ROOM_CRYSTAL_W_PX (ROOM_CRYSTAL_W_TILES * 8)

extern u8 room_tilemap[ROOM_H][ROOM_W];
// World-space contract shared by collision, projectiles, OBJ projection, and
// emulator instrumentation. Ordinary rooms are 160 px; Crystal's proving
// arena is 224 px with a bounded 0..64 px camera.
extern u8 room_world_width;
extern u8 room_camera_x;
extern u8 room_transform_ticks;
// Temporary combat boon: decremented in active gameplay only, so menus do
// not consume it and it never needs to inflate the suspend-save payload.
extern u8 room_weapon_surge_ticks;
// Runtime contract exposed for emulator instrumentation: only authored seal
// encounters lock unexplored exits while hostiles remain.
extern u8 room_combat_sealed;
// Progression-fixture transaction marker for emulator contract tests.
// 5 means the current dungeon's Rift Sigil was successfully placed.
extern u8 room_sigil_status;

// Called immediately after procgen clears the entity table, before optional
// combat/loot population can consume every slot. Idempotent on later room
// orchestration passes.
void room_spawn_progression_fixture(void) BANKED;

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
void room_start_weapon_surge(void) BANKED;
// Passive HP/MP clocks continue through ordinary rooms but must never carry
// from a dead/completed run into a newly initialized champion.
void room_reset_passive_timers(void) BANKED;

// Request that the next room_enter resume the CURRENT room (skip procgen)
// instead of generating a new one — used when returning from the pack screen.
void room_request_resume(void) BANKED;

void        room_enter(void);
void        room_exit(void);
screen_id_t room_tick(u8 keys, u8 pressed);
void        room_draw(void);

#endif
