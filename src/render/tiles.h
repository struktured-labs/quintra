// Tile / sprite primitives — Phase 4 placeholder graphics.
// Phase 7+ will replace these with real biome-themed assets via quintra-assets.
#ifndef QUINTRA_RENDER_TILES_H
#define QUINTRA_RENDER_TILES_H

#include "core/types.h"

// BG tile slots
#define BGT_VOID   0
#define BGT_FLOOR  1
#define BGT_WALL   2
#define BGT_DOOR   3

// HUD tile slots (BG tile data, rendered via WINDOW layer)
#define HUD_HEART_FULL  4
#define HUD_HEART_HALF  5
#define HUD_HEART_EMPTY 6
#define HUD_COIN        7
#define HUD_BLANK       8
#define HUD_DIGIT_0     9    // ...9..18 = digits 0..9

// OBJ tile slots (sprite VRAM lives at 0x8000)
#define SPR_PLAYER 0
#define SPR_BULLET 1
#define SPR_ENEMY  2
#define SPR_HEART  3
#define SPR_COIN   4

// Tile blobs
extern const u8 bg_tile_floor[16];
extern const u8 bg_tile_wall[16];
extern const u8 bg_tile_door[16];
extern const u8 bg_tile_void[16];
extern const u8 sprite_tile_player[16];
extern const u8 sprite_tile_bullet[16];
extern const u8 sprite_tile_enemy[16];
extern const u8 sprite_tile_heart[16];
extern const u8 sprite_tile_coin[16];

extern const u8 hud_tiles[][16];    // 15 tiles starting at HUD_HEART_FULL
#define HUD_TILE_COUNT 15

void tiles_load_room_bg(void);
void tiles_load_player_sprite(void);
void tiles_load_combat_sprites(void);    // bullet + enemy
void tiles_load_pickup_sprites(void);    // heart + coin
void tiles_load_hud(void);               // hud BG tiles + 10 digits

#endif
