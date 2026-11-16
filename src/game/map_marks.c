#pragma bank 14
#include <gb/gb.h>
#include <gb/cgb.h>
#include "core/types.h"
#include "game/map_marks.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/tiles.h"

#define BGPAL_SHOP 5

static const u16 map_pal_shop[4] = {
    BGR555(1,3,2), BGR555(16,8,1), BGR555(28,20,2), BGR555(31,29,10)
};

static u8 legend_attr(u8 tile) {
    if (tile == BGT_MAP_HERE) return 7;
    if (tile == BGT_MAP_SIGIL || tile == BGT_MAP_RIFT || tile == BGT_PORTAL)
        return BGPAL_CRYSTAL;
    if (tile == BGT_MAP_BOSS) return BGPAL_CRACK;
    if (tile == BGT_MAP_CACHE) return BGPAL_DOOR;
    if (tile == BGT_MAP_SHOP) return BGPAL_SHOP;
    return BGPAL_FLOOR;
}

static void put(u8 x, u8 y, u8 tile) {
    u8 attr = legend_attr(tile);
    VBK_REG = 0; set_bkg_tiles(x, y, 1, 1, &tile);
    VBK_REG = 1; set_bkg_tiles(x, y, 1, 1, &attr);
    VBK_REG = 0;
}

static void put_shop_key(u8 x, u8 y) {
    put(x, y, BGT_MAP_SHOP);
    put((u8)(x + 1), y, BGT_MAP_LABEL_S);
    put((u8)(x + 2), y, BGT_MAP_LABEL_H);
    put((u8)(x + 3), y, BGT_MAP_LABEL_O);
    put((u8)(x + 4), y, BGT_MAP_LABEL_P);
}

void map_load_shop_palette(void) BANKED {
    palette_bg_load(BGPAL_SHOP, map_pal_shop);
}

void map_draw_dungeon_legend(void) BANKED {
    static const u8 you[3] = {
        BGT_MAP_LABEL_Y, BGT_MAP_LABEL_O, BGT_MAP_LABEL_U
    };
    static const u8 goal[4] = {
        BGT_MAP_LABEL_G, BGT_MAP_LABEL_O, BGT_AREA_A, BGT_MAP_LABEL_L
    };
    static const u8 boss[4] = {
        BGT_MAP_LABEL_B, BGT_MAP_LABEL_O, BGT_MAP_LABEL_S, BGT_MAP_LABEL_S
    };
    static const u8 loot[4] = {
        BGT_MAP_LABEL_L, BGT_MAP_LABEL_O, BGT_MAP_LABEL_O, BGT_MAP_LABEL_T
    };
    u8 i;
    put(0, 17, BGT_MAP_HERE);
    for (i = 0; i < 3; ++i) put((u8)(1 + i), 17, you[i]);
    put(4, 17, BGT_MAP_SIGIL);
    for (i = 0; i < 4; ++i) put((u8)(5 + i), 17, goal[i]);
    put(9, 17, BGT_MAP_BOSS);
    for (i = 0; i < 4; ++i) put((u8)(10 + i), 17, boss[i]);
    put(14, 17, BGT_MAP_CACHE);
    for (i = 0; i < 4; ++i) put((u8)(15 + i), 17, loot[i]);
    put_shop_key(0, 16);
}

void map_draw_world_legend(void) BANKED {
    static const u8 you[3] = {
        BGT_MAP_LABEL_Y, BGT_MAP_LABEL_O, BGT_MAP_LABEL_U
    };
    static const u8 gate[4] = {
        BGT_AREA_G, BGT_AREA_A, BGT_MAP_LABEL_T, BGT_AREA_E
    };
    static const u8 rift[4] = {
        BGT_MAP_LABEL_R, BGT_MAP_LABEL_I,
        BGT_MAP_LABEL_F, BGT_MAP_LABEL_T
    };
    static const u8 boss[4] = {
        BGT_MAP_LABEL_B, BGT_MAP_LABEL_O,
        BGT_MAP_LABEL_S, BGT_MAP_LABEL_S
    };
    u8 i;
    put(13, 2, BGT_MAP_HERE);
    for (i = 0; i < 3; ++i) put((u8)(14 + i), 2, you[i]);
    put(13, 5, BGT_PORTAL);
    for (i = 0; i < 4; ++i) put((u8)(14 + i), 5, gate[i]);
    put(13, 8, BGT_MAP_RIFT);
    for (i = 0; i < 4; ++i) put((u8)(14 + i), 8, rift[i]);
    put(13, 11, BGT_MAP_BOSS);
    for (i = 0; i < 4; ++i) put((u8)(14 + i), 11, boss[i]);
    put_shop_key(13, 14);
}

u8 map_world_shop_icon(u8 cell, u8 icon) BANKED {
    if (icon != BGT_MAP_HERE
        && cell == RIFTWELL_WORLD_SCREEN
        && (run_state.riftwild_flags & RIFT_REGION_TRADER_FOUND_BIT))
        return BGT_MAP_SHOP;
    return icon;
}

u8 map_dungeon_shop_icon(u8 cell, u8 here, u8 icon) BANKED {
    if (cell != here
        && cell == run_state_dungeon_shop_cell()
        && run_state_dungeon_cell_visited(cell))
        return BGT_MAP_BIG_SHOP;
    return icon;
}

u8 map_town_shop_center(u8 visual_i, u8 here, u8 fallback) BANKED {
    if (visual_i == here) return BGT_MAP_HERE;
    if (visual_i == 2) return BGT_MAP_SHOP;
    return fallback;
}
