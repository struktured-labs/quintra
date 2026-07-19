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

// A hooded chartwright with a pale map held open. Kept at one tile so the
// village gains a distinct resident without evicting any combat OBJ art.
static const u8 sprite_fx_cartographer[16] = {
    0x18, 0x18, 0x3C, 0x24, 0x7E, 0x42, 0x5A, 0x66,
    0x7E, 0x42, 0x3C, 0x3C, 0x24, 0x3C, 0x42, 0x42,
};

// Village Waykeeper: peaked hood, bright lantern, and a long gate staff.
// It occupies the Rune Lantern slot only in a town; room_enter reloads every
// enemy atlas before a combat room can render that slot again.
static const u8 sprite_fx_waykeeper[16] = {
    0x18, 0x18, 0x3C, 0x24, 0x5A, 0x66, 0x5A, 0x7E,
    0x3C, 0x7E, 0x24, 0x3C, 0x24, 0x3C, 0x42, 0x42,
};

// Town Lorekeeper: hood, raised quill, and a bright open scroll. The arrival
// square has no active Surge pickup, so its temporary-orb slot becomes a
// distinct civic resident without growing the CGB's full OBJ atlas.
static const u8 sprite_fx_lorekeeper[16] = {
    0x10, 0x10, 0x38, 0x28, 0x7C, 0x44, 0x5A, 0x66,
    0x3C, 0x7E, 0x2C, 0x3C, 0x52, 0x52, 0x42, 0x42,
};

void tiles_load_pickup_sprites(void) BANKED {
    set_sprite_data(SPR_HEART, 1, sprite_tile_heart);
    set_sprite_data(SPR_COIN,  1, sprite_tile_coin);
    set_sprite_data(SPR_VILLAGER, 1, sprite_fx_villager);
    set_sprite_data(SPR_MERCHANT, 1, sprite_fx_merchant);
    set_sprite_data(SPR_SMITH, 1, sprite_fx_smith);
    set_sprite_data(SPR_APOTHECARY, 1, sprite_fx_apothecary);
    set_sprite_data(SPR_CARTOGRAPHER, 1, sprite_fx_cartographer);
}

void tiles_load_town_waykeeper_sprite(void) BANKED {
    set_sprite_data(SPR_TOWN_WAYKEEPER, 1, sprite_fx_waykeeper);
}

void tiles_load_town_lorekeeper_sprite(void) BANKED {
    set_sprite_data(SPR_TOWN_LOREKEEPER, 1, sprite_fx_lorekeeper);
}

void tiles_load_all_class_sprites(void) BANKED {
    // Each class metasprite = 4 tiles (64 bytes). Load all 5 contiguously
    // at SPR_CLASS_BASE so class N's first tile is SPR_CLASS_BASE + N*4.
    set_sprite_data((u8)(SPR_CLASS_BASE + 0 * SPR_CLASS_STRIDE), 4, sprite_class_wolfkin);
    set_sprite_data((u8)(SPR_CLASS_BASE + 1 * SPR_CLASS_STRIDE), 4, sprite_class_sauran);
    set_sprite_data((u8)(SPR_CLASS_BASE + 2 * SPR_CLASS_STRIDE), 4, sprite_class_corvin);
    set_sprite_data((u8)(SPR_CLASS_BASE + 3 * SPR_CLASS_STRIDE), 4, sprite_class_picsean);
    set_sprite_data((u8)(SPR_CLASS_BASE + 4 * SPR_CLASS_STRIDE), 4, sprite_class_vespine);
    set_sprite_data((u8)(SPR_CLASS_WALK_BASE + 0 * SPR_CLASS_STRIDE), 4, sprite_class_wolfkin_walk);
    set_sprite_data((u8)(SPR_CLASS_WALK_BASE + 1 * SPR_CLASS_STRIDE), 4, sprite_class_sauran_walk);
    set_sprite_data((u8)(SPR_CLASS_WALK_BASE + 2 * SPR_CLASS_STRIDE), 4, sprite_class_corvin_walk);
    set_sprite_data((u8)(SPR_CLASS_WALK_BASE + 3 * SPR_CLASS_STRIDE), 4, sprite_class_picsean_walk);
    set_sprite_data((u8)(SPR_CLASS_WALK_BASE + 4 * SPR_CLASS_STRIDE), 4, sprite_class_vespine_walk);
    // The ascended atlas resides in bank 3, so its own banked loader performs
    // the VRAM copies. Direct pointers here would read whatever bank 2 has at
    // the same address rather than the transformed forms.
    tiles_load_ascended_sprites();
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
    set_sprite_data(SPR_ENEMY_FOLD_STAR, 1, sprite_enemy_fold_star);
    set_sprite_data(SPR_ENEMY_FLUTTERBAT, 1, sprite_enemy_flutterbat);
    set_sprite_data(SPR_ENEMY_GLOAM_LEECH, 1, sprite_enemy_gloam_leech);
    set_sprite_data(SPR_ENEMY_CINDER_MAW, 1, sprite_enemy_cinder_maw);
    set_sprite_data(SPR_ENEMY_RIFT_OOZE, 1, sprite_enemy_rift_ooze);
    set_sprite_data(SPR_ENEMY_MIRROR_MOTH, 1, sprite_enemy_mirror_moth);
    set_sprite_data(SPR_ENEMY_MIRE_SPORE, 1, sprite_enemy_mire_spore);
    set_sprite_data(SPR_ENEMY_ECHO_GUARD, 1, sprite_enemy_echo_guard);
    set_sprite_data(SPR_ENEMY_RUNE_LANTERN, 1, sprite_enemy_rune_lantern);
    // Bruiser tier: 16x16 (4 tiles each) for the heavy enemies
    set_sprite_data(SPR_BRUISER_ORC,     4, sprite_bruiser_orc);
    set_sprite_data(SPR_BRUISER_BOMBER,  4, sprite_bruiser_bomber);
    set_sprite_data(SPR_BRUISER_WARLOCK, 4, sprite_bruiser_warlock);
}

void tiles_load_dread_bell_sprite(void) BANKED {
    // OBJ VRAM is full. Normal dungeon combat never contains a merchant,
    // so it may safely repurpose the merchant-callout tile. Shop and town
    // rooms deliberately do not call this loader and keep their speech cue.
    set_sprite_data(SPR_ENEMY_DREAD_BELL, 1, sprite_enemy_dread_bell);
}

void tiles_load_rift_warden_sprite(void) BANKED {
    // The for-sale tag exists only in merchant/town rooms, which never
    // contain combat hostiles. Reclaim its slot in dungeon combat so this
    // additional enemy costs no permanent OBJ VRAM.
    set_sprite_data(SPR_ENEMY_RIFT_WARDEN, 1, sprite_enemy_rift_warden);
}

void tiles_load_prism_skitter_sprite(void) BANKED {
    // The elder/sanctuary tile exists only in peaceful rooms. A combat room
    // can reclaim it for the Skitter without evicting a live NPC or growing
    // the fixed OBJ atlas.
    set_sprite_data(SPR_ENEMY_PRISM_SKITTER, 1, sprite_enemy_prism_skitter);
}

void tiles_load_dusk_midge_sprite(void) BANKED {
    // Apothecary art is resident only in a town. Dungeon rooms cannot contain
    // that NPC, so reclaim its slot for the Midge without increasing OBJ VRAM.
    set_sprite_data(SPR_ENEMY_DUSK_MIDGE, 1, sprite_enemy_dusk_midge);
}

void tiles_load_sunwheel_sprite(void) BANKED {
    // Dusk Midges are only in Bloodmoon/Void. Golden Temple can therefore
    // reclaim this town-only apothecary slot for a new silhouette without
    // growing the full 128-tile OBJ atlas.
    set_sprite_data(SPR_ENEMY_SUNWHEEL, 1, sprite_enemy_sunwheel);
}

void tiles_load_cinder_kite_sprite(void) BANKED {
    // Ember comes long before Bloodmoon and never hosts a Sunwheel. Reclaim
    // the same town-only apothecary slot for its mobile harrier instead of
    // spending another permanently resident OBJ tile.
    set_sprite_data(SPR_ENEMY_CINDER_KITE, 1, sprite_enemy_cinder_kite);
}

void tiles_load_bog_toad_sprite(void) BANKED {
    // Toxic Mire cannot contain any other slot-79 specialist, so keep the
    // new pounce silhouette out of the permanently resident CGB OBJ atlas.
    set_sprite_data(SPR_ENEMY_BOG_TOAD, 1, sprite_enemy_bog_toad);
}

void tiles_load_bramble_sprite(void) BANKED {
    // Shadow Keep cannot contain the other phase-safe slot-79 specialists.
    // Reuse this town-only tile so the new procedural enemy costs no OBJ VRAM.
    set_sprite_data(SPR_ENEMY_BRAMBLE_SPRITE, 1, sprite_enemy_bramble_sprite);
}

void tiles_load_frost_lancer_sprite(void) BANKED {
    // Frost Vault cannot contain any other slot-79 specialist. Reuse the
    // phase-safe town slot so this new silhouette has no permanent OBJ cost.
    set_sprite_data(SPR_ENEMY_FROST_LANCER, 1, sprite_enemy_frost_lancer);
}

void tiles_load_vine_coil_sprite(void) BANKED {
    // Verdant Hollow is the only stage that carries the Vine Coil, so its
    // living-seed silhouette can reclaim the town-only apothecary tile.
    set_sprite_data(SPR_ENEMY_VINE_COIL, 1, sprite_enemy_vine_coil);
}

void tiles_load_merchant_callout_sprite(void) BANKED {
    set_sprite_data(SPR_MERCHANT_CALLOUT, 1, sprite_fx_merchant_callout);
}

void tiles_load_spear_sprite(void) BANKED {
    // In dungeon rooms slot 123 has no resident NPC. Reclaim it for a real
    // long-shaft silhouette instead of making Astral Spear look like a claw.
    set_sprite_data(SPR_FX_SPEAR, 1, sprite_fx_spear);
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
    stage = (stage < 9) ? stage : 8;
    // Cast before shifting: SDCC otherwise keeps the u8 arithmetic and a
    // 256-byte row stride wraps to zero, selecting stage 0 every time.
    set_sprite_data(SPR_BOSS_BIG, 16,
        sprite_boss_stages + (((u16)stage) << 8));
}

void tiles_load_fx_sprites(void) BANKED {
    set_sprite_data(SPR_BULLET,     1, sprite_fx_bullet_a);
    set_sprite_data(SPR_BULLET_B,   1, sprite_fx_bullet_b);
    set_sprite_data(SPR_FX_MUZZLE,  1, sprite_fx_muzzle);
    set_sprite_data(SPR_FX_IMPACT,  1, sprite_fx_impact);
    set_sprite_data(SPR_ENEMY_WISP, 1, sprite_fx_wisp);
    set_sprite_data(SPR_ITEM_ORB,   1, sprite_fx_item_orb);
    set_sprite_data(SPR_SHOP_TAG,   1, sprite_fx_shop_tag);
    tiles_load_merchant_callout_sprite();
    set_sprite_data(SPR_SURGE_ORB,  1, sprite_fx_surge_orb);
    set_sprite_data(SPR_SHIELD_AURA, 1, sprite_fx_shield_aura);
    // Bold diagonal sweep: this is deliberately separate from the bullet
    // pair so Wolfkin's melee attack reads as a physical claw/weapon arc,
    // not an inexplicably slow ranged shot.
    {
        static const u8 swing[16] = {
            0x03,0x03, 0x07,0x07, 0x0E,0x0E, 0x1C,0x1C,
            0x38,0x38, 0x70,0x70, 0xE0,0xE0, 0xC0,0xC0,
        };
        set_sprite_data(SPR_FX_SWING, 1, swing);
    }
}

// Compact hand-authored outdoor vocabulary. These are deliberately runtime
// tiles rather than font glyphs: villages and Riftwild must read as a world,
// not recolored dungeon masonry.
static const u8 bgt_grass[16] = {
    0x00,0x00, 0x10,0x00, 0x00,0x00, 0x02,0x00,
    0x00,0x00, 0x40,0x00, 0x00,0x00, 0x08,0x00
};
static const u8 bgt_path[16] = {
    0x55,0x00, 0x00,0x22, 0x11,0x00, 0x00,0x88,
    0x44,0x00, 0x00,0x11, 0x22,0x00, 0x00,0x44
};
static const u8 bgt_roof[16] = {
    0xFF,0x00, 0x81,0x7E, 0xFF,0x00, 0x18,0xE7,
    0xFF,0x00, 0x81,0x7E, 0xFF,0x00, 0x18,0xE7
};
static const u8 bgt_fence[16] = {
    0x24,0x24, 0x24,0x24, 0xFF,0xDB, 0xFF,0xDB,
    0x24,0x24, 0x24,0x24, 0xFF,0xDB, 0xFF,0xDB
};
static const u8 bgt_tree[16] = {
    0x18,0x18, 0x7E,0x66, 0xFF,0xBD, 0xDB,0xFF,
    0x7E,0x66, 0x3C,0x24, 0x18,0x18, 0x18,0x00
};

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
    set_bkg_data(BGT_GRASS,    1, bgt_grass);
    set_bkg_data(BGT_PATH,     1, bgt_path);
    set_bkg_data(BGT_ROOF,     1, bgt_roof);
    set_bkg_data(BGT_FENCE,    1, bgt_fence);
    set_bkg_data(BGT_TREE,     1, bgt_tree);
}
