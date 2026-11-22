#pragma bank 26

#include <gb/gb.h>
#include <gb/cgb.h>

#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/waygear.h"
#include "render/gate_boulder.h"
#include "render/tiles.h"

// Open boulder: cracked / hollowed stone, gold rune. Color 0 is the
// Riftwild ground, so cracks read as openings through the rock.
// GPT Image 2 (gpt-image-2.6-sunburst) open-boulder-1, traced to 8x8
// and tweaked per Carbon: octagonal silhouette, centered hollow 4x4
// gold rune, four rim-breaking cracks. Color 0 is Riftwild ground.
const u8 bgt_gate_boulder_open[16] = {
    0x34, 0x00, 0x6E, 0x00, 0xE7, 0x3C, 0x82, 0x24,
    0x41, 0x24, 0xE7, 0x3C, 0x76, 0x00, 0x2C, 0x00
};

u8 gate_boulder_attr = BGPAL_WALL;

static u8 s_cue_done;
static u8 s_shimmer_ticks;
static u8 s_shimmer_tx;
static u8 s_shimmer_ty;

void gate_boulder_room_reset(void) BANKED {
    s_cue_done = 0;
    s_shimmer_ticks = 0;
}

static void poke_attr(u8 tx, u8 ty, u8 attr) {
    u8 buf = attr;
    VBK_REG = 1;
    if (room_world_height & 0x40)
        set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &buf);
    else
        set_bkg_tiles(tx, ty, 1, 1, &buf);
    VBK_REG = 0;
}

void tiles_apply_passable_boulder(void) BANKED {
    gate_boulder_attr = WAYGEAR_BOULDER_ATTR();
    if (WAYGEAR_CAN_PASS_BOULDER())
        set_bkg_data(BGT_GATE_BOULDER, 1, bgt_gate_boulder_open);
}

static void refresh_range(u8 x0, u8 y0, u8 x1, u8 y1) {
    u8 x, y, t;
    u8 attr = WAYGEAR_BOULDER_ATTR();
    for (y = y0; y < y1; ++y) {
        for (x = x0; x < x1; ++x) {
            t = room_tile_at_px((i16)x << 3, (i16)y << 3);
            if (t == BGT_GATE_BOULDER) poke_attr(x, y, attr);
        }
    }
}

void gate_boulder_refresh_attrs(void) BANKED {
    if (!(room_world_height & 0x40)) {
        refresh_range(0, 0, ROOM_W, ROOM_H);
        return;
    }
    // One-time grant/load walk, never the frame loop. Only boulder cells
    // are written.
    refresh_range(0, 0, ROOM_WIDE_W_TILES, ROOM_WIDE_H_TILES);
}

static void front_tile(u8 *tx, u8 *ty) {
    i16 px = (i16)player.x + 8;
    i16 py = (i16)player.y + 8;
    if (player.facing == FACE_N) py = (i16)player.y - 1;
    else if (player.facing == FACE_S) py = (i16)player.y + 16;
    else if (player.facing == FACE_W) px = (i16)player.x - 1;
    else px = (i16)player.x + 16;
    if (px < 0) px = 0;
    if (py < 0) py = 0;
    *tx = (u8)(px >> 3);
    *ty = (u8)(py >> 3);
}

void gate_boulder_tick(void) BANKED {
    u8 tx, ty, t;
    if (s_shimmer_ticks) {
        s_shimmer_ticks--;
        poke_attr(s_shimmer_tx, s_shimmer_ty,
            (s_shimmer_ticks & 2) ? BGPAL_DOOR : BGPAL_CRACK);
        if (!s_shimmer_ticks)
            poke_attr(s_shimmer_tx, s_shimmer_ty, BGPAL_CRACK);
        return;
    }
    if (s_cue_done || !WAYGEAR_CAN_PASS_BOULDER()) return;
    front_tile(&tx, &ty);
    t = room_tile_at_px((i16)tx << 3, (i16)ty << 3);
    if (t != BGT_GATE_BOULDER) return;
    s_cue_done = 1;
    s_shimmer_tx = tx;
    s_shimmer_ty = ty;
    s_shimmer_ticks = 10;
    poke_attr(tx, ty, BGPAL_DOOR);
}
