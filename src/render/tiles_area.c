#pragma bank 7
#include <gb/gb.h>
#include <gb/cgb.h>

#include "game/dungeon_director.h"
#include "game/room.h"
#include "game/puzzle.h"
#include "game/run_state.h"
#include "render/tiles.h"

// Compact all-caps outdoor signage. Every lit pixel uses colour 3 so the
// labels remain crisp in the amber door palette against grass and paths.
// Letters are intentionally loaded into combat-unused BG slots 76..92.
static const u8 area_letters[17][16] = {
    // R
    { 0x7C,0x7C, 0x42,0x42, 0x42,0x42, 0x7C,0x7C,
      0x48,0x48, 0x44,0x44, 0x42,0x42, 0x00,0x00 },
    // I
    { 0x7E,0x7E, 0x18,0x18, 0x18,0x18, 0x18,0x18,
      0x18,0x18, 0x18,0x18, 0x7E,0x7E, 0x00,0x00 },
    // F
    { 0x7E,0x7E, 0x40,0x40, 0x40,0x40, 0x7C,0x7C,
      0x40,0x40, 0x40,0x40, 0x40,0x40, 0x00,0x00 },
    // T
    { 0x7E,0x7E, 0x18,0x18, 0x18,0x18, 0x18,0x18,
      0x18,0x18, 0x18,0x18, 0x18,0x18, 0x00,0x00 },
    // W
    { 0x42,0x42, 0x42,0x42, 0x42,0x42, 0x42,0x42,
      0x5A,0x5A, 0x66,0x66, 0x42,0x42, 0x00,0x00 },
    // L
    { 0x40,0x40, 0x40,0x40, 0x40,0x40, 0x40,0x40,
      0x40,0x40, 0x40,0x40, 0x7E,0x7E, 0x00,0x00 },
    // D
    { 0x78,0x78, 0x44,0x44, 0x42,0x42, 0x42,0x42,
      0x42,0x42, 0x44,0x44, 0x78,0x78, 0x00,0x00 },
    // V
    { 0x42,0x42, 0x42,0x42, 0x42,0x42, 0x42,0x42,
      0x24,0x24, 0x24,0x24, 0x18,0x18, 0x00,0x00 },
    // A
    { 0x18,0x18, 0x24,0x24, 0x42,0x42, 0x7E,0x7E,
      0x42,0x42, 0x42,0x42, 0x42,0x42, 0x00,0x00 },
    // G
    { 0x3C,0x3C, 0x42,0x42, 0x40,0x40, 0x4E,0x4E,
      0x42,0x42, 0x42,0x42, 0x3C,0x3C, 0x00,0x00 },
    // E
    { 0x7E,0x7E, 0x40,0x40, 0x40,0x40, 0x7C,0x7C,
      0x40,0x40, 0x40,0x40, 0x7E,0x7E, 0x00,0x00 },
    // M
    { 0x42,0x42, 0x66,0x66, 0x5A,0x5A, 0x5A,0x5A,
      0x42,0x42, 0x42,0x42, 0x42,0x42, 0x00,0x00 },
    // K
    { 0x42,0x42, 0x44,0x44, 0x48,0x48, 0x70,0x70,
      0x48,0x48, 0x44,0x44, 0x42,0x42, 0x00,0x00 },
    // O
    { 0x3C,0x3C, 0x42,0x42, 0x42,0x42, 0x42,0x42,
      0x42,0x42, 0x42,0x42, 0x3C,0x3C, 0x00,0x00 },
    // P
    { 0x7C,0x7C, 0x42,0x42, 0x42,0x42, 0x7C,0x7C,
      0x40,0x40, 0x40,0x40, 0x40,0x40, 0x00,0x00 },
    // N
    { 0x42,0x42, 0x62,0x62, 0x52,0x52, 0x4A,0x4A,
      0x46,0x46, 0x42,0x42, 0x42,0x42, 0x00,0x00 },
    // H
    { 0x42,0x42, 0x42,0x42, 0x42,0x42, 0x7E,0x7E,
      0x42,0x42, 0x42,0x42, 0x42,0x42, 0x00,0x00 },
};

void tiles_load_area_labels(void) BANKED {
    set_bkg_data(BGT_AREA_R, 17, area_letters[0]);
}

static u8 wide_attr(u8 tile, u8 outdoor, u8 x, u8 y) {
    if (outdoor) {
        return (tile == BGT_TREE || tile == BGT_WILD_STONE)
            ? BGPAL_WALL
            : (tile == BGT_WILD_WATER || tile == BGT_WILD_FLOWER)
                ? BGPAL_CRYSTAL
                : (tile == BGT_WILD_STUMP || tile == BGT_DOOR)
                    ? BGPAL_DOOR : BGPAL_FLOOR;
    }
    if (tile == BGT_WALL || tile == BGT_PILLAR
        || tile == BGT_BLOCK || tile == BGT_BLOCK_TR
        || tile == BGT_BLOCK_BL || tile == BGT_BLOCK_BR
        || tile == BGT_ROOF || tile == BGT_FENCE
        || tile == BGT_TREE || tile == BGT_WILD_STONE)
        return BGPAL_WALL;
    if (tile == BGT_SPIKES || tile == BGT_WALL_CRACK
        || tile == BGT_BOSS_GATE_L || tile == BGT_BOSS_GATE_R
        || tile == BGT_BOSS_GATE_TOP || tile == BGT_BOSS_GATE_BOTTOM)
        return BGPAL_CRACK;
    if (tile == BGT_DOOR) {
        if (room_combat_sealed || room_puzzle_locked) return BGPAL_CRACK;
        if ((y == 0 && room_objective_dir == DIR_N)
            || (x == ROOM_WIDE_W_TILES - 1
                && room_objective_dir == DIR_E)
            || (y == ROOM_WIDE_H_TILES - 1
                && room_objective_dir == DIR_S)
            || (x == 0 && room_objective_dir == DIR_W))
            return BGPAL_CRYSTAL;
        return BGPAL_DOOR;
    }
    if (tile == BGT_POT || tile == BGT_SWITCH) return BGPAL_DOOR;
    if (tile == BGT_CRYSTAL || tile == BGT_PORTAL) return BGPAL_CRYSTAL;
    if (tile == HUD_COIN || (tile >= HUD_DIGIT_0
        && tile <= HUD_DIGIT_0 + 9)) return BGPAL_CRACK;
    return BGPAL_FLOOR;
}

static u8 wide_tile(u8 x, u8 y, u8 outdoor) {
    if (x >= ROOM_WIDE_W_TILES || y >= ROOM_WIDE_H_TILES)
        return outdoor ? BGT_TREE : BGT_WALL;
    if (y < ROOM_H) {
        if (x < ROOM_W) return room_tilemap[y][x];
        return room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

// Render a complete logical 31x31 field plus its deterministic overscan into
// the rotated hardware map. Building each physical row in a 32-byte buffer
// avoids any assumption that GBDK's rectangular writer wraps at map edges.
void tiles_prepare_wide_field(void) BANKED {
    u8 logical_x, logical_y;
    u8 outdoor = run_state.world_mode;
    u8 tiles[32];
    u8 attrs[32];
    if (!(room_world_height & 0x40)) return;
    for (logical_y = 0; logical_y < 32; ++logical_y) {
        u8 physical_y = ROOM_BG_MAP_Y(logical_y);
        for (logical_x = 0; logical_x < 32; ++logical_x) {
            u8 physical_x = ROOM_BG_MAP_X(logical_x);
            u8 tile = wide_tile(logical_x, logical_y, outdoor);
            tiles[physical_x] = tile;
            attrs[physical_x] = wide_attr(tile, outdoor,
                logical_x, logical_y);
        }
        VBK_REG = 0;
        set_bkg_tiles(0, physical_y, 32, 1, tiles);
        VBK_REG = 1;
        set_bkg_tiles(0, physical_y, 32, 1, attrs);
    }
    VBK_REG = 0;
}

void tiles_stream_wide_column(u8 logical_x, u8 physical_x) BANKED {
    u8 logical_y;
    u8 outdoor = run_state.world_mode;
    u8 tiles[32];
    u8 attrs[32];
    for (logical_y = 0; logical_y < 32; ++logical_y) {
        u8 physical_y = ROOM_BG_MAP_Y(logical_y);
        u8 tile = wide_tile(logical_x, logical_y, outdoor);
        tiles[physical_y] = tile;
        attrs[physical_y] = wide_attr(tile, outdoor,
            logical_x, logical_y);
    }
    VBK_REG = 0;
    set_bkg_tiles(physical_x, 0, 1, 32, tiles);
    VBK_REG = 1;
    set_bkg_tiles(physical_x, 0, 1, 32, attrs);
    VBK_REG = 0;
}

void tiles_stream_wide_row(u8 logical_y, u8 physical_y) BANKED {
    u8 logical_x;
    u8 outdoor = run_state.world_mode;
    u8 tiles[32];
    u8 attrs[32];
    for (logical_x = 0; logical_x < 32; ++logical_x) {
        u8 physical_x = ROOM_BG_MAP_X(logical_x);
        u8 tile = wide_tile(logical_x, logical_y, outdoor);
        tiles[physical_x] = tile;
        attrs[physical_x] = wide_attr(tile, outdoor,
            logical_x, logical_y);
    }
    VBK_REG = 0;
    set_bkg_tiles(0, physical_y, 32, 1, tiles);
    VBK_REG = 1;
    set_bkg_tiles(0, physical_y, 32, 1, attrs);
    VBK_REG = 0;
}

void tiles_draw_area_label(u8 kind) BANKED {
    static const u8 riftwild[8] = {
        BGT_AREA_R, BGT_AREA_I, BGT_AREA_F, BGT_AREA_T,
        BGT_AREA_W, BGT_AREA_I, BGT_AREA_L, BGT_AREA_D
    };
    static const u8 village[7] = {
        BGT_AREA_V, BGT_AREA_I, BGT_AREA_L, BGT_AREA_L,
        BGT_AREA_A, BGT_AREA_G, BGT_AREA_E
    };
    static const u8 market[6] = {
        BGT_AREA_M, BGT_AREA_A, BGT_AREA_R,
        BGT_AREA_K, BGT_AREA_E, BGT_AREA_T
    };
    static const u8 forge[5] = {
        BGT_AREA_F, BGT_AREA_O, BGT_AREA_R, BGT_AREA_G, BGT_AREA_E
    };
    static const u8 gate[4] = {
        BGT_AREA_G, BGT_AREA_A, BGT_AREA_T, BGT_AREA_E
    };
    static const u8 lower[5] = {
        BGT_AREA_L, BGT_AREA_O, BGT_AREA_W, BGT_AREA_E, BGT_AREA_R
    };
    static const u8 deep[4] = {
        BGT_AREA_D, BGT_AREA_E, BGT_AREA_E, BGT_AREA_P
    };
    static const u8 inner[5] = {
        BGT_AREA_I, BGT_AREA_N, BGT_AREA_N, BGT_AREA_E, BGT_AREA_R
    };
    static const u8 heart[5] = {
        BGT_AREA_H, BGT_AREA_E, BGT_AREA_A, BGT_AREA_R, BGT_AREA_T
    };
    static const u8 trap[4] = {
        BGT_AREA_T, BGT_AREA_R, BGT_AREA_A, BGT_AREA_P
    };
    static const u8 wave[4] = {
        BGT_AREA_W, BGT_AREA_A, BGT_AREA_V, BGT_AREA_E
    };
    static const u8 elite[5] = {
        BGT_AREA_E, BGT_AREA_L, BGT_AREA_I, BGT_AREA_T, BGT_AREA_E
    };
    static const u8 hold[4] = {
        BGT_AREA_H, BGT_AREA_O, BGT_AREA_L, BGT_AREA_D
    };
    static const u8 attrs[8] = {
        BGPAL_DOOR, BGPAL_DOOR, BGPAL_DOOR, BGPAL_DOOR,
        BGPAL_DOOR, BGPAL_DOOR, BGPAL_DOOR, BGPAL_DOOR
    };
    const u8 *letters;
    u8 x, width;
    if (kind == 1) { letters = riftwild; x = 6; width = 8; }
    else if (kind == 2) { letters = village; x = 7; width = 7; }
    else if (kind == 3) { letters = market; x = 7; width = 6; }
    else if (kind == 4) { letters = forge; x = 8; width = 5; }
    else if (kind == 5) { letters = gate; x = 8; width = 4; }
    else if (kind == 6) { letters = lower; x = 8; width = 5; }
    else if (kind == 7) { letters = deep; x = 8; width = 4; }
    else if (kind == 8) { letters = inner; x = 8; width = 5; }
    else if (kind == 9) { letters = heart; x = 8; width = 5; }
    else if (kind == 10) { letters = trap; x = 8; width = 4; }
    else if (kind == 11) { letters = wave; x = 8; width = 4; }
    else if (kind == 12) { letters = elite; x = 8; width = 5; }
    else { letters = hold; x = 8; width = 4; }
    // A Riftwild field may have crossed several continuous seams. Project the
    // display-only sign through the same logical-to-physical origin instead
    // of writing it into the previous field's canonical top-left.
    if (room_world_width > ROOM_VIEW_W_PX
        || room_world_height > ROOM_VIEW_H_PX) {
        u8 i;
        u8 py = ROOM_BG_MAP_Y(1);
        for (i = 0; i < width; ++i) {
            u8 px = ROOM_BG_MAP_X((u8)(x + i));
            VBK_REG = 0; set_bkg_tiles(px, py, 1, 1, &letters[i]);
            VBK_REG = 1; set_bkg_tiles(px, py, 1, 1, &attrs[i]);
        }
    } else {
        VBK_REG = 0; set_bkg_tiles(x, 1, width, 1, letters);
        VBK_REG = 1; set_bkg_tiles(x, 1, width, 1, attrs);
    }
    VBK_REG = 0;
}
