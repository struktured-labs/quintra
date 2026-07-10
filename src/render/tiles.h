// Tile / sprite primitives — Phase 4 placeholder graphics.
// Phase 7+ will replace these with real biome-themed assets via quintra-assets.
#ifndef QUINTRA_RENDER_TILES_H
#define QUINTRA_RENDER_TILES_H


#include <gb/gb.h>
#include "core/types.h"

// BG tile slots
#define BGT_VOID   0
#define BGT_FLOOR  1     // plain stone (bright)
#define BGT_WALL   2     // brick face
#define BGT_DOOR   3     // gold door frame

// HUD tile slots (BG tile data, rendered via WINDOW layer)
#define HUD_HEART_FULL  4
#define HUD_HEART_HALF  5
#define HUD_HEART_EMPTY 6
#define HUD_COIN        7
#define HUD_BLANK       8
#define HUD_DIGIT_0     9    // ...9..18 = digits 0..9
// Boss HP bar segments (loaded with the HUD set; slots after dungeon tiles)
#define HUD_BAR_FULL   26
#define HUD_BAR_EMPTY  27

// Dungeon tile slots (after HUD block)
#define BGT_FLOOR2  19   // cracked floor variant
#define BGT_FLOOR3  20   // pebbled floor variant
#define BGT_PILLAR  21   // solid obstacle
#define BGT_CRYSTAL 22   // solid glowing obstacle
#define BGT_RUBBLE  23   // walkable decoration
#define BGT_WALL_CRACK 24  // secret wall: solid until shot, then becomes a door
#define BGT_BLOCK      25  // pushable crate TL quadrant (16x16 crate = 4 tiles)
#define BGT_BLOCK_TR   28  // crate top-right
#define BGT_BLOCK_BL   29  // crate bottom-left
#define BGT_BLOCK_BR   30  // crate bottom-right

// CGB BG palette slot per tile kind (written to VRAM bank 1 attributes)
#define BGPAL_FLOOR   0
#define BGPAL_WALL    1
#define BGPAL_CRYSTAL 2
#define BGPAL_DOOR    3
#define BGPAL_CRACK   4     // glowing amber so secret walls stand out

// OBJ tile slots — 5 classes × 4 tiles each (metasprite) + 4 enemies + 4 boss tiles + pickups + bullet
#define SPR_CLASS_BASE     0     // 5 classes × 4 tiles = 0..19
#define SPR_CLASS_STRIDE   4
#define SPR_ENEMY_CRAWLER  20
#define SPR_ENEMY_HORNET   21
#define SPR_ENEMY_SKELETON 22
#define SPR_ENEMY_ORC      23
#define SPR_BOSS           24    // 4 tiles: 24..27
#define SPR_BULLET         28    // 2-frame anim: SPR_BULLET + SPR_BULLET_B
#define SPR_BULLET_B       29
#define SPR_HEART          30
#define SPR_COIN           31
#define SPR_FX_MUZZLE      32
#define SPR_FX_IMPACT      33
#define SPR_ENEMY_WISP     34
#define SPR_ITEM_ORB       35
#define SPR_ENEMY_BOMBER   36
#define SPR_ENEMY_SHADE    37
#define SPR_ENEMY_WARLOCK  38
#define SPR_BOSS_BIG       40    // 16 tiles: 40..55 (32x32 final boss)
// Legacy aliases (kept for back-compat with existing code):
#define SPR_PLAYER         SPR_CLASS_BASE
#define SPR_ENEMY          SPR_ENEMY_CRAWLER

// Tile blobs
extern const u8 bg_tile_void[16];
extern const u8 sprite_tile_heart[16];
extern const u8 sprite_tile_coin[16];

extern const u8 hud_tiles[][16];
#define HUD_TILE_COUNT 15

void tiles_load_pickup_sprites(void) BANKED;
void tiles_load_hud(void) BANKED;

// Phase 12 metasprite loaders
void tiles_load_all_class_sprites(void) BANKED;   // loads 5 classes × 4 tiles = 20 OBJ tiles
void tiles_load_all_enemy_sprites(void) BANKED;   // 4 enemy tiles
void tiles_load_miniboss(u8 stage) BANKED;        // stage's distinct 16x16 mini-boss into SPR_BOSS
void tiles_load_boss_big(u8 stage) BANKED;        // load stage's 32x32 boss (16 tiles at SPR_BOSS_BIG)
void tiles_load_fx_sprites(void) BANKED;          // bullet (2 frames), muzzle, impact
void tiles_load_dungeon_bg(void) BANKED;          // dungeon tileset (replaces flat placeholders)

#endif
