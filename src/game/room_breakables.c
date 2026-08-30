#pragma bank 13

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/stage_event.h"
#include "render/tiles.h"

static void breakable_set_tile(u8 tx, u8 ty, u8 tile, u8 attr) {
    if (ty < ROOM_H) {
        if (tx < ROOM_W) room_tilemap[ty][tx] = tile;
        else room_world_extension[ty][tx - ROOM_W] = tile;
    } else room_world_bottom[ty - ROOM_H][tx] = tile;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &attr);
    VBK_REG = 0;
}

void room_break_crystal(u8 tx, u8 ty) BANKED {
    if (tx >= (u8)(room_world_width >> 3)
        || ty >= (u8)(room_world_height >> 3)) return;
    if (room_tile_at_px((i16)tx << 3, (i16)ty << 3) != BGT_CRYSTAL) return;
    breakable_set_tile(tx, ty, BGT_FLOOR, BGPAL_FLOOR);
    sfx_play(SFX_HIT);
    if (rng_next_u8() < 64)
        pickup_spawn_mp(FIX8((i16)tx * 8), FIX8((i16)ty * 8));
    stage_event_on_crystal_break(tx, ty);
}

void room_break_pot(u8 tx, u8 ty) BANKED {
    u8 r;
    if (tx >= (u8)(room_world_width >> 3)
        || ty >= (u8)(room_world_height >> 3)) return;
    if (room_tile_at_px((i16)tx << 3, (i16)ty << 3) != BGT_POT) return;
    breakable_set_tile(tx, ty, BGT_FLOOR, BGPAL_FLOOR);
    sfx_play(SFX_HIT);
    r = rng_next_u8();
    if (r < 0x50) pickup_spawn(PICKUP_HEART_HALF,
        FIX8((i16)tx * 8), FIX8((i16)ty * 8));
    else if (r < 0xC0) pickup_spawn(PICKUP_COIN_1,
        FIX8((i16)tx * 8), FIX8((i16)ty * 8));
}
