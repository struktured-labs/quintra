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

// OBJ tile slots — 5 classes × 4 tiles each (metasprite) + 4 enemies + 4 boss tiles + pickups + bullet
#define SPR_CLASS_BASE     0     // 5 classes × 4 tiles = 0..19
#define SPR_CLASS_STRIDE   4
#define SPR_ENEMY_CRAWLER  20
#define SPR_ENEMY_HORNET   21
#define SPR_ENEMY_SKELETON 22
#define SPR_ENEMY_ORC      23
#define SPR_BOSS           24    // 4 tiles: 24..27
#define SPR_BULLET         28
#define SPR_HEART          29
#define SPR_COIN           30
// Legacy aliases (kept for back-compat with existing code):
#define SPR_PLAYER         SPR_CLASS_BASE
#define SPR_ENEMY          SPR_ENEMY_CRAWLER

// Tile blobs
extern const u8 bg_tile_floor[16];
extern const u8 bg_tile_wall[16];
extern const u8 bg_tile_door[16];
extern const u8 bg_tile_void[16];
extern const u8 sprite_tile_player[16];   // legacy 8x8 (unused if metasprite loaded)
extern const u8 sprite_tile_bullet[16];
extern const u8 sprite_tile_enemy[16];
extern const u8 sprite_tile_heart[16];
extern const u8 sprite_tile_coin[16];
extern const u8 sprite_tile_boss[16];

extern const u8 hud_tiles[][16];
#define HUD_TILE_COUNT 15

void tiles_load_room_bg(void);
void tiles_load_player_sprite(void);
void tiles_load_combat_sprites(void);
void tiles_load_pickup_sprites(void);
void tiles_load_boss_sprite(void);
void tiles_load_hud(void);

// Phase 12 metasprite loaders
void tiles_load_all_class_sprites(void);   // loads 5 classes × 4 tiles = 20 OBJ tiles
void tiles_load_all_enemy_sprites(void);   // 4 enemy tiles
void tiles_load_boss_metasprite(void);     // 16x16 boss (4 tiles at SPR_BOSS..+3)

#endif
