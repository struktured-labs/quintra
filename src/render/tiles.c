#pragma bank 2
#include <gb/gb.h>

#include "core/types.h"
#include "render/tiles.h"
#include "render/sprites_gen.h"
#include "stages.h"

// All tiles are 2bpp 8x8 (16 bytes). For each row: byte_low, byte_high.
// color = (high_bit, low_bit) per pixel.

// Void — color 0 (black); tile slot 0, loaded by tiles_load_dungeon_bg.
const u8 bg_tile_void[16] = {
    0,0, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0,
};

// Heart pickup (small heart icon for floor drops)
const u8 sprite_tile_heart[16] = {
    0x00, 0x00,
    0x66, 0x00,
    0xFF, 0x00,
    0xFF, 0x00,
    0x7E, 0x00,
    0x3C, 0x00,
    0x18, 0x00,
    0x00, 0x00,
};

// Coin pickup
const u8 sprite_tile_coin[16] = {
    0x00, 0x00,
    0x3C, 0x00,
    0x7E, 0x18,
    0x7E, 0x18,
    0x7E, 0x18,
    0x7E, 0x18,
    0x3C, 0x00,
    0x00, 0x00,
};

void tiles_load_pickup_sprites(void) BANKED {
    set_sprite_data(SPR_HEART, 1, sprite_tile_heart);
    set_sprite_data(SPR_COIN,  1, sprite_tile_coin);
    set_sprite_data(SPR_VILLAGER, 1, sprite_fx_villager);
    set_sprite_data(SPR_MERCHANT, 1, sprite_fx_merchant);
}

// HUD tiles — full heart, half heart, empty heart, coin glyph, blank,
// digits 0-9. 15 tiles total, loaded into BG slots HUD_HEART_FULL..+14.
const u8 hud_tiles[15][16] = {
    // 0 (slot 4): HEART_FULL — color 3 throughout
    { 0x66,0x66, 0xFF,0xFF, 0xFF,0xFF, 0xFF,0xFF,
      0x7E,0x7E, 0x3C,0x3C, 0x18,0x18, 0x00,0x00 },
    // 1 (slot 5): HEART_HALF — color 3 left, color 1 outline right
    { 0x66,0x60, 0xFF,0xF0, 0xFF,0xF0, 0xFF,0xF0,
      0x7E,0x70, 0x3C,0x30, 0x18,0x10, 0x00,0x00 },
    // 2 (slot 6): HEART_EMPTY — color 1 outline
    { 0x66,0x00, 0x99,0x00, 0x81,0x00, 0x81,0x00,
      0x42,0x00, 0x24,0x00, 0x18,0x00, 0x00,0x00 },
    // 3 (slot 7): COIN — circle in color 2 with color 3 center
    { 0x00,0x00, 0x3C,0x00, 0x7E,0x18, 0x7E,0x3C,
      0x7E,0x3C, 0x7E,0x18, 0x3C,0x00, 0x00,0x00 },
    // 4 (slot 8): BLANK
    { 0,0, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0, 0,0 },
    // 5-14 (slots 9..18): DIGITS 0-9, simple 3x5 in 8x8 cell, color 3
    // '0'
    { 0x00,0x00, 0x38,0x38, 0x44,0x44, 0x44,0x44,
      0x44,0x44, 0x44,0x44, 0x38,0x38, 0x00,0x00 },
    // '1'
    { 0x00,0x00, 0x10,0x10, 0x30,0x30, 0x10,0x10,
      0x10,0x10, 0x10,0x10, 0x38,0x38, 0x00,0x00 },
    // '2'
    { 0x00,0x00, 0x38,0x38, 0x44,0x44, 0x04,0x04,
      0x18,0x18, 0x20,0x20, 0x7C,0x7C, 0x00,0x00 },
    // '3'
    { 0x00,0x00, 0x38,0x38, 0x44,0x44, 0x18,0x18,
      0x04,0x04, 0x44,0x44, 0x38,0x38, 0x00,0x00 },
    // '4'
    { 0x00,0x00, 0x08,0x08, 0x18,0x18, 0x28,0x28,
      0x7C,0x7C, 0x08,0x08, 0x08,0x08, 0x00,0x00 },
    // '5'
    { 0x00,0x00, 0x7C,0x7C, 0x40,0x40, 0x78,0x78,
      0x04,0x04, 0x44,0x44, 0x38,0x38, 0x00,0x00 },
    // '6'
    { 0x00,0x00, 0x18,0x18, 0x20,0x20, 0x78,0x78,
      0x44,0x44, 0x44,0x44, 0x38,0x38, 0x00,0x00 },
    // '7'
    { 0x00,0x00, 0x7C,0x7C, 0x04,0x04, 0x08,0x08,
      0x10,0x10, 0x10,0x10, 0x10,0x10, 0x00,0x00 },
    // '8'
    { 0x00,0x00, 0x38,0x38, 0x44,0x44, 0x38,0x38,
      0x44,0x44, 0x44,0x44, 0x38,0x38, 0x00,0x00 },
    // '9'
    { 0x00,0x00, 0x38,0x38, 0x44,0x44, 0x44,0x44,
      0x3C,0x3C, 0x04,0x04, 0x18,0x18, 0x00,0x00 },
};

// Boss HP bar segments: solid filled cell vs hollow outline. Drawn in the
// HUD palette (color 3 = red, color 1 = outline grey-blue).
static const u8 hud_bar_full[16] = {
    0x00,0x00, 0x7E,0x7E, 0x7E,0x7E, 0x7E,0x7E,
    0x7E,0x7E, 0x7E,0x7E, 0x7E,0x7E, 0x00,0x00,
};
static const u8 hud_bar_empty[16] = {
    0x00,0x00, 0x7E,0x00, 0x42,0x00, 0x42,0x00,
    0x42,0x00, 0x42,0x00, 0x7E,0x00, 0x00,0x00,
};

void tiles_load_hud(void) BANKED {
    u8 i;
    for (i = 0; i < HUD_TILE_COUNT; ++i) {
        set_bkg_data((u8)(HUD_HEART_FULL + i), 1, hud_tiles[i]);
    }
    set_bkg_data(HUD_BAR_FULL,  1, hud_bar_full);
    set_bkg_data(HUD_BAR_EMPTY, 1, hud_bar_empty);
}

void tiles_load_all_class_sprites(void) BANKED {
    // Each class metasprite = 4 tiles (64 bytes). Load all 5 contiguously
    // at SPR_CLASS_BASE so class N's first tile is SPR_CLASS_BASE + N*4.
    set_sprite_data((u8)(SPR_CLASS_BASE + 0 * SPR_CLASS_STRIDE), 4, sprite_class_wolfkin);
    set_sprite_data((u8)(SPR_CLASS_BASE + 1 * SPR_CLASS_STRIDE), 4, sprite_class_sauran);
    set_sprite_data((u8)(SPR_CLASS_BASE + 2 * SPR_CLASS_STRIDE), 4, sprite_class_corvin);
    set_sprite_data((u8)(SPR_CLASS_BASE + 3 * SPR_CLASS_STRIDE), 4, sprite_class_picsean);
    set_sprite_data((u8)(SPR_CLASS_BASE + 4 * SPR_CLASS_STRIDE), 4, sprite_class_vespine);
}

void tiles_load_all_enemy_sprites(void) BANKED {
    set_sprite_data(SPR_ENEMY_CRAWLER,  1, sprite_enemy_crawler);
    set_sprite_data(SPR_ENEMY_HORNET,   1, sprite_enemy_hornet);
    set_sprite_data(SPR_ENEMY_SKELETON, 1, sprite_enemy_skeleton);
    set_sprite_data(SPR_ENEMY_ORC,      1, sprite_enemy_orc);
    set_sprite_data(SPR_ENEMY_BOMBER,   1, sprite_enemy_bomber);
    set_sprite_data(SPR_ENEMY_SHADE,    1, sprite_enemy_shade);
    set_sprite_data(SPR_ENEMY_WARLOCK,  1, sprite_enemy_warlock);
    set_sprite_data(SPR_ENEMY_ROPE,     1, sprite_enemy_rope);
    set_sprite_data(SPR_ENEMY_SENTRY,   1, sprite_enemy_sentry);
    // Bruiser tier: 16x16 (4 tiles each) for the heavy enemies
    set_sprite_data(SPR_BRUISER_ORC,     4, sprite_bruiser_orc);
    set_sprite_data(SPR_BRUISER_BOMBER,  4, sprite_bruiser_bomber);
    set_sprite_data(SPR_BRUISER_WARLOCK, 4, sprite_bruiser_warlock);
}

void tiles_load_miniboss(u8 stage) BANKED {
    // Load this stage's 16x16 mini-boss into the shared SPR_BOSS slot so each
    // stage's mini-boss looks distinct. Variant table must match the palette
    // table in procgen.c (miniboss spawn). 0=sentinel,1=orc,2=skel,3=crawl,4=hornet
    static const u8 *const mb[5] = {
        sprite_boss_sentinel, sprite_miniboss_orc, sprite_miniboss_skeleton,
        sprite_bruiser_bomber, sprite_bruiser_warlock,
    };
    set_sprite_data(SPR_BOSS, 4, mb[stage_mb_variant[stage < 9 ? stage : 8]]);
}

void tiles_load_boss_big(u8 stage) BANKED {
    // Load the current stage's distinct 32x32 boss into the fixed 16-tile
    // slot range (SPR_BOSS_BIG). Only the active stage's art is resident.
    static const u8 *const bosses[9] = {
        sprite_boss_stage0, sprite_boss_stage1, sprite_boss_stage2,
        sprite_boss_stage3, sprite_boss_stage4, sprite_boss_stage5,
        sprite_boss_stage6, sprite_boss_stage7, sprite_boss_stage8,
    };
    set_sprite_data(SPR_BOSS_BIG, 16, bosses[stage < 9 ? stage : 8]);
}

void tiles_load_fx_sprites(void) BANKED {
    set_sprite_data(SPR_BULLET,     1, sprite_fx_bullet_a);
    set_sprite_data(SPR_BULLET_B,   1, sprite_fx_bullet_b);
    set_sprite_data(SPR_FX_MUZZLE,  1, sprite_fx_muzzle);
    set_sprite_data(SPR_FX_IMPACT,  1, sprite_fx_impact);
    set_sprite_data(SPR_ENEMY_WISP, 1, sprite_fx_wisp);
    set_sprite_data(SPR_ITEM_ORB,   1, sprite_fx_item_orb);
}

void tiles_load_dungeon_bg(void) BANKED {
    // Authored dungeon tileset (slot 0 = void/black; the rest overwrite the
    // former flat placeholders).
    set_bkg_data(BGT_VOID,    1, bg_tile_void);
    set_bkg_data(BGT_FLOOR,   1, bgt_floor_plain);
    set_bkg_data(BGT_WALL,    1, bgt_wall_brick);
    set_bkg_data(BGT_DOOR,    1, bgt_door_frame);
    set_bkg_data(BGT_FLOOR2,  1, bgt_floor_crack);
    set_bkg_data(BGT_FLOOR3,  1, bgt_floor_pebble);
    set_bkg_data(BGT_PILLAR,  1, bgt_pillar);
    set_bkg_data(BGT_CRYSTAL, 1, bgt_crystal);
    set_bkg_data(BGT_RUBBLE,  1, bgt_rubble);
    set_bkg_data(BGT_WALL_CRACK, 1, bgt_wall_crack);
    set_bkg_data(BGT_BLOCK,    1, bgt_block16_tl);
    set_bkg_data(BGT_BLOCK_TR, 1, bgt_block16_tr);
    set_bkg_data(BGT_BLOCK_BL, 1, bgt_block16_bl);
    set_bkg_data(BGT_BLOCK_BR, 1, bgt_block16_br);
    set_bkg_data(BGT_SPIKES,   1, bgt_spikes);
    set_bkg_data(BGT_POT,      1, bgt_pot);
    set_bkg_data(BGT_SWITCH,   1, bgt_switch);
    set_bkg_data(BGT_PORTAL,   1, bgt_portal);
}
