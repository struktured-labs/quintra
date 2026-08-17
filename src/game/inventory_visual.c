#pragma bank 9

#include <gb/gb.h>

#include "core/types.h"
#include "game/inventory_visual.h"
#include "game/player.h"
#include "render/class_palettes.h"
#include "render/palette.h"
#include "render/tiles.h"

static const u16 gold[4] = {
    BGR555(0,0,0), BGR555(31,22,3), BGR555(16,8,1), BGR555(31,31,18),
};
static const u16 magic[4] = {
    BGR555(0,0,0), BGR555(19,8,28), BGR555(7,3,14), BGR555(30,23,31),
};
static void icon(u8 id, u8 tile, u8 col, u8 row, u8 palette) {
    set_sprite_tile(id, tile);
    set_sprite_prop(id, palette);
    move_sprite(id, (u8)(8 + col * 8), (u8)(16 + row * 8));
}

void inventory_prepare_sprites(void) BANKED {
    u8 i;
    u8 base = (u8)(SPR_CLASS_BASE + player.class_id * SPR_CLASS_STRIDE);
    u8 signature = player.active_item == 10 ? SPR_ITEM_SWIFT_FANG
        : player.active_item == 11 ? SPR_ITEM_WARD_CHARM
        : player.active_item == 12 ? SPR_ITEM_HUNTER_EYE
        : player.active_item == 13 ? SPR_ITEM_MANA_GEM
        : player.active_item == 14 ? SPR_ITEM_THORN : SPR_ITEM_ASCEND;
    class_palette_load_obj(1, player.class_id);
    palette_obj_load(2, gold);
    palette_obj_load(3, magic);
    tiles_load_all_class_sprites();
    tiles_load_pickup_sprites();
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
    for (i = 0; i < 4; ++i) {
        set_sprite_tile(i, (u8)(base + i));
        set_sprite_prop(i, 1);
        move_sprite(i, (u8)(16 + ((i & 1) ? 8 : 0)),
            (u8)(24 + ((i >= 2) ? 8 : 0)));
    }
    icon(4, SPR_ITEM_WEAPON, 3, 9, 2);
    icon(5, signature, 3, 11, 3);
    icon(6, SPR_ITEM_RIFT_SIGIL, 2, 14, 2);
    icon(7, SPR_COIN, 7, 7, 2);
}
