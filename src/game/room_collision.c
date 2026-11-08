#pragma bank 8
// Whole-body collision. Bank 6 no longer had room for the compact-map fast
// path. Callers already use a banked call, so the bank change is not an
// extra trampoline on the crawler step.

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/entity.h"
#include "game/room.h"
#include "game/waygear.h"
#include "render/tiles.h"

static u8 full_body_obstacle(i16 x, i16 y) {
    u8 t = room_tile_at_px(x, y);
    return (t == BGT_PILLAR
         || t == BGT_BLOCK || t == BGT_BLOCK_TR
         || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR);
}

u8 aabb_overlap_player_wide(const entity_t *e) BANKED {
    return player.x+16>e->x && e->x+(e->hitbox>>4)>player.x
        && player.y+16>e->y && e->y+(e->hitbox&15)>player.y;
}

static u8 player_walkable(i16 x, i16 y) {
    u8 tile = room_tile_at_px(x, y);
    return room_tile_walkable(tile) || WAYGEAR_TILE_PASSABLE(tile);
}

// Probes at x+13 and y+15 stay inside the 20x17 tilemap when the body
// origin is in this rectangle. Wider coordinates keep the streamed lookup.
#define CLEAR_FAST_X 146
#define CLEAR_FAST_Y 120

static u8 masked_walkable(u8 tile) {
    tile = (u8)(tile & 0x7F);
    return room_tile_walkable(tile) || WAYGEAR_TILE_PASSABLE(tile);
}

static u8 masked_body_block(u8 tile) {
    tile = (u8)(tile & 0x7F);
    return (u8)(tile == BGT_PILLAR || tile == BGT_BLOCK
        || tile == BGT_BLOCK_TR || tile == BGT_BLOCK_BL
        || tile == BGT_BLOCK_BR);
}

static u8 row_feet(u8 *row, u8 a, u8 b, u8 c) {
    if (!masked_walkable(row[a])) return 0;
    if (b != a && !masked_walkable(row[b])) return 0;
    if (c != a && c != b && !masked_walkable(row[c])) return 0;
    return 1;
}

static u8 row_body(u8 *row, u8 a, u8 b, u8 c) {
    if (masked_body_block(row[a])) return 0;
    if (b != a && masked_body_block(row[b])) return 0;
    if (c != a && c != b && masked_body_block(row[c])) return 0;
    return 1;
}

u8 room_player_position_clear(i16 x, i16 y) BANKED {
    if (x < 0 || y < 0
        || x > (i16)(room_world_width - 16)
        || y > (i16)(room_world_height - 16)) return 0;
    // Same 12 probes as the calls below. Inside the compact map each row
    // pointer replaces three tile lookups, and a repeated row is one test.
    if (x <= CLEAR_FAST_X && y <= CLEAR_FAST_Y) {
        u8 ux = (u8)x;
        u8 uy = (u8)y;
        u8 tx0 = (u8)((ux + 2) >> 3);
        u8 tx1 = (u8)((ux + 8) >> 3);
        u8 tx2 = (u8)((ux + 13) >> 3);
        u8 ty = (u8)((uy + 8) >> 3);
        u8 ty2;
        u8 *row = room_tilemap[ty];
        if (!row_feet(row, tx0, tx1, tx2)) return 0;
        ty2 = (u8)((uy + 15) >> 3);
        if (ty2 != ty) {
            row = room_tilemap[ty2];
            if (!row_feet(row, tx0, tx1, tx2)) return 0;
        }
        ty = (u8)(uy >> 3);
        row = room_tilemap[ty];
        if (!row_body(row, tx0, tx1, tx2)) return 0;
        ty2 = (u8)((uy + 7) >> 3);
        if (ty2 != ty) {
            row = room_tilemap[ty2];
            if (!row_body(row, tx0, tx1, tx2)) return 0;
        }
        return 1;
    }
    return player_walkable(x + 2,  y + 8)
        && player_walkable(x + 8,  y + 8)
        && player_walkable(x + 13, y + 8)
        && player_walkable(x + 2,  y + 15)
        && player_walkable(x + 8,  y + 15)
        && player_walkable(x + 13, y + 15)
        && !full_body_obstacle(x + 2,  y)
        && !full_body_obstacle(x + 8,  y)
        && !full_body_obstacle(x + 13, y)
        && !full_body_obstacle(x + 2,  y + 7)
        && !full_body_obstacle(x + 8,  y + 7)
        && !full_body_obstacle(x + 13, y + 7);
}

// A floor hazard is a readable positional tax, never a soft-lock.
void room_stumble_off_hazard(void) BANKED {
    static const i8 dx[4] = { 0, 8, 0, -8 };
    static const i8 dy[4] = { -8, 0, 8, 0 };
    u8 i;
    for (i = 0; i < 4; ++i) {
        ppos_t nx = (ppos_t)(player.x + dx[i]);
        ppos_t ny = (ppos_t)(player.y + dy[i]);
        {
            u8 tile = room_tile_at_px(nx + 8, ny + 12);
            if (tile == BGT_SPIKES || tile == BGT_VOID) continue;
        }
        if (room_player_position_clear(nx, ny)) {
            player.x = nx;
            player.y = ny;
            return;
        }
    }
}
