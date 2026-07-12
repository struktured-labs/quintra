// Auto-generated declarations matching sprites_gen.c.
// Regenerate both files via: python3 scripts/sprite_authoring.py c > src/render/sprites_gen.c
#ifndef QUINTRA_RENDER_SPRITES_GEN_H
#define QUINTRA_RENDER_SPRITES_GEN_H

#include "core/types.h"

// 16x16 player class metasprites (4 tiles each, row-major TL/TR/BL/BR)
extern const u8 sprite_class_wolfkin[64];
extern const u8 sprite_class_sauran[64];
extern const u8 sprite_class_corvin[64];
extern const u8 sprite_class_picsean[64];
extern const u8 sprite_class_vespine[64];

// 8x8 enemy sprites
extern const u8 sprite_enemy_crawler[16];
extern const u8 sprite_enemy_hornet[16];
extern const u8 sprite_enemy_skeleton[16];
extern const u8 sprite_enemy_orc[16];
extern const u8 sprite_enemy_bomber[16];
extern const u8 sprite_enemy_shade[16];
extern const u8 sprite_enemy_warlock[16];
extern const u8 sprite_enemy_rope[16];

// 8x8 FX sprites
extern const u8 sprite_fx_bullet_a[16];
extern const u8 sprite_fx_bullet_b[16];
extern const u8 sprite_fx_muzzle[16];
extern const u8 sprite_fx_impact[16];
extern const u8 sprite_fx_wisp[16];
extern const u8 sprite_fx_item_orb[16];

// 16x16 boss metasprite
extern const u8 sprite_boss_sentinel[64];

// 16x16 mini-boss variants (2x-scaled enemy art)
extern const u8 sprite_miniboss_orc[64];
extern const u8 sprite_miniboss_skeleton[64];
extern const u8 sprite_bruiser_orc[64];
extern const u8 sprite_bruiser_bomber[64];
extern const u8 sprite_bruiser_warlock[64];

// 9 distinct 32x32 stage bosses (16 tiles each; stage 0 is the Colossus)
extern const u8 sprite_boss_stage0[256];
extern const u8 sprite_boss_stage1[256];
extern const u8 sprite_boss_stage2[256];
extern const u8 sprite_boss_stage3[256];
extern const u8 sprite_boss_stage4[256];
extern const u8 sprite_boss_stage5[256];
extern const u8 sprite_boss_stage6[256];
extern const u8 sprite_boss_stage7[256];
extern const u8 sprite_boss_stage8[256];

// 8x8 dungeon BG tiles
extern const u8 bgt_floor_plain[16];
extern const u8 bgt_floor_crack[16];
extern const u8 bgt_floor_pebble[16];
extern const u8 bgt_wall_brick[16];
extern const u8 bgt_door_frame[16];
extern const u8 bgt_pillar[16];
extern const u8 bgt_crystal[16];
extern const u8 bgt_rubble[16];
extern const u8 bgt_wall_crack[16];
extern const u8 bgt_block[16];
extern const u8 bgt_block16_tl[16];
extern const u8 bgt_block16_tr[16];
extern const u8 bgt_block16_bl[16];
extern const u8 bgt_block16_br[16];

#endif
