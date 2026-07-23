#pragma bank 5
#include <gb/gb.h>

#include "core/types.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

// Four quadrants of one 16x16 skull seal. room.c projects the second row onto
// the walkable approach cell, so a boss threshold reads as a deliberate
// commitment marker at native resolution instead of two tiny amber squares.
// The underlying tilemap and collision stay untouched.
static const u8 boss_gate_l[16] = {
    0x0F,0x0F, 0x3F,0x3F, 0x7F,0x7F, 0x73,0x73,
    0xE1,0xE1, 0xED,0xED, 0xE1,0xE1, 0x73,0x73
};
static const u8 boss_gate_r[16] = {
    0xF0,0xF0, 0xFC,0xFC, 0xFE,0xFE, 0xCE,0xCE,
    0x87,0x87, 0xB7,0xB7, 0x87,0x87, 0xCE,0xCE
};
static const u8 boss_gate_top[16] = {
    0x7F,0x7F, 0x38,0x38, 0x19,0x19, 0x1B,0x1B,
    0x1F,0x1F, 0x0D,0x0D, 0x0D,0x0D, 0x06,0x06
};
static const u8 boss_gate_bottom[16] = {
    0xFE,0xFE, 0x1C,0x1C, 0x98,0x98, 0xD8,0xD8,
    0xF8,0xF8, 0xB0,0xB0, 0xB0,0xB0, 0x60,0x60
};

static const u8 boss_gate_seal[4] = {
    BGT_BOSS_GATE_L, BGT_BOSS_GATE_R,
    BGT_BOSS_GATE_TOP, BGT_BOSS_GATE_BOTTOM
};
static const u8 boss_gate_attrs[4] = {
    BGPAL_CRACK, BGPAL_CRACK, BGPAL_CRACK, BGPAL_CRACK
};

void tiles_load_boss_cue_bg(void) BANKED {
    set_bkg_data(BGT_BOSS_GATE_L, 1, boss_gate_l);
    set_bkg_data(BGT_BOSS_GATE_R, 1, boss_gate_r);
    set_bkg_data(BGT_BOSS_GATE_TOP, 1, boss_gate_top);
    set_bkg_data(BGT_BOSS_GATE_BOTTOM, 1, boss_gate_bottom);
}

static void draw_seal(u8 x, u8 y) {
    VBK_REG = 0;
    set_bkg_tiles(x, y, 2, 2, boss_gate_seal);
    VBK_REG = 1;
    set_bkg_tiles(x, y, 2, 2, boss_gate_attrs);
    VBK_REG = 0;
}

void tiles_draw_boss_cue(u8 entered_from) BANKED {
    u8 x, y;
    u8 boss = run_state_boss_room(run_state.bosses_beaten);
    entered_from;
    // A generated door is always a two-cell pair. Render its seal one cell
    // inward so the complete skull stays visible at every screen edge.
    if (run_state_dungeon_neighbor(DIR_N) == boss) {
        for (x = 0; x < ROOM_W - 1; ++x)
            if (room_tilemap[0][x] == BGT_DOOR
                && room_tilemap[0][x + 1] == BGT_DOOR) draw_seal(x, 0);
    }
    if (run_state_dungeon_neighbor(DIR_S) == boss) {
        for (x = 0; x < ROOM_W - 1; ++x)
            if (room_tilemap[ROOM_H - 1][x] == BGT_DOOR
                && room_tilemap[ROOM_H - 1][x + 1] == BGT_DOOR)
                draw_seal(x, ROOM_H - 2);
    }
    if (run_state_dungeon_neighbor(DIR_W) == boss) {
        for (y = 0; y < ROOM_H - 1; ++y)
            if (room_tilemap[y][0] == BGT_DOOR
                && room_tilemap[y + 1][0] == BGT_DOOR) draw_seal(0, y);
    }
    if (run_state_dungeon_neighbor(DIR_E) == boss) {
        for (y = 0; y < ROOM_H - 1; ++y)
            if (room_tilemap[y][ROOM_W - 1] == BGT_DOOR
                && room_tilemap[y + 1][ROOM_W - 1] == BGT_DOOR)
                draw_seal(ROOM_W - 2, y);
    }
}
