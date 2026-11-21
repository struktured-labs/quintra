#pragma bank 31
// M5b Conduit vault: region / lock / Heart door painters (bank 31).
// Stamp, restore and redress are in conduit_vstate.c (bank 29).
#include <gb/gb.h>
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/kite_art.h"
#include "render/tiles.h"

#define PX CD_PX
#define PY CD_PY
#define WX CD_WX
#define WY CD_WY


static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

u8 cd_cd_vt[4], cd_cd_va[4];

// Write a w x h block (w*h <= 4) from vt/va to the world and, when live, VRAM.
void cd_vblk(u8 lx, u8 ly, u8 w, u8 h) BANKED {
    u8 i = 0, x, y;
    for (y = 0; y < h; ++y)
        for (x = 0; x < w; ++x, ++i) wset(WX(lx + x), WY(ly + y), cd_vt[i]);
    if (!cd_live) return;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(lx)), ROOM_BG_MAP_Y(WY(ly)), w, h, cd_vt);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(lx)), ROOM_BG_MAP_Y(WY(ly)), w, h, cd_va);
    VBK_REG = 0;
}

void cd_vfill(u8 t, u8 a) BANKED {
    cd_vt[0] = cd_vt[1] = cd_vt[2] = cd_vt[3] = t;
    cd_va[0] = cd_va[1] = cd_va[2] = cd_va[3] = a;
}

static void region(u8 lx, u8 stream) {
    if (stream) cd_vfill(CD_T_STREAM, BGPAL_CRYSTAL);
    else {
        cd_vt[0] = CD_T_CAIRN_TL; cd_vt[1] = CD_T_CAIRN_TR;
        cd_vt[2] = CD_T_CAIRN_BL; cd_vt[3] = CD_T_CAIRN_BR;
        cd_va[0] = cd_va[1] = cd_va[2] = cd_va[3] = BGPAL_WALL;
    }
    cd_vblk(lx, CD_STREAM_Y, 2, 2);
}

static void glyph(u8 lx, u8 stream) {
    cd_vt[0] = stream ? CD_T_GLYPH_STREAM : CD_T_GLYPH_ROCK;
    cd_va[0] = BGPAL_CRYSTAL;
    cd_vblk(lx, CD_SW_ROW, 1, 1);
}

static void hdoor(u8 lx, u8 open) {
    if (open) cd_vfill(BGT_FLOOR, BGPAL_FLOOR);
    else {
        cd_vfill(CD_T_DOOR, BGPAL_CRACK);   // Heart doors: heart-red plug
        cd_va[1] = (u8)(BGPAL_CRACK | 0x40);
    }
    cd_vblk(lx, CD_HD_Y, 1, 2);
}

// 0 region A (+ its glyph), 1 region B (+ glyph), 2 lock, 3 door A, 4 door B.
void cd_vpaint(u8 r) BANKED {
    if (r == 0) { region(CD_RA_X, cd_ra); glyph(CD_SWA_X, cd_ra); }
    else if (r == 1) { region(CD_RB_X, cd_rb); glyph(CD_SWB_X, cd_rb); }
    else if (r == 2) {
        if (cd_lockup) {
            cd_vfill(CD_T_LOCK, BGPAL_DOOR);
            cd_va[0] = (u8)(BGPAL_DOOR | 0x40); cd_va[1] = (u8)(BGPAL_DOOR | 0x60);
            cd_va[3] = (u8)(BGPAL_DOOR | 0x20);
        } else cd_vfill(BGT_FLOOR, BGPAL_FLOOR);
        cd_vblk(CD_LOCK_X, CD_LOCK_Y, 2, 2);
    } else if (r == 3) hdoor(CD_HDA_X, cd_hdoor & 1);
    else hdoor(CD_HDB_X, cd_hdoor & 2);
}

