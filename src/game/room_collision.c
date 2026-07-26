#pragma bank 6
// Cold whole-body collision paths. Ordinary movement stays in room.c's hot
// bank; damage knockback and spike recovery call this stricter shared check.

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

static u8 full_body_obstacle(i16 x, i16 y) {
    u8 t = room_tile_at_px(x, y);
    return (t == BGT_PILLAR
         || t == BGT_BLOCK || t == BGT_BLOCK_TR
         || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR);
}

u8 room_player_position_clear(i16 x, i16 y) BANKED {
    return room_player_position_in_bounds(x, y)
        && room_tile_walkable(room_tile_at_px(x + 2,  y + 8))
        && room_tile_walkable(room_tile_at_px(x + 8,  y + 8))
        && room_tile_walkable(room_tile_at_px(x + 13, y + 8))
        && room_tile_walkable(room_tile_at_px(x + 2,  y + 15))
        && room_tile_walkable(room_tile_at_px(x + 8,  y + 15))
        && room_tile_walkable(room_tile_at_px(x + 13, y + 15))
        && !full_body_obstacle(x + 2,  y)
        && !full_body_obstacle(x + 8,  y)
        && !full_body_obstacle(x + 13, y)
        && !full_body_obstacle(x + 2,  y + 7)
        && !full_body_obstacle(x + 8,  y + 7)
        && !full_body_obstacle(x + 13, y + 7);
}

// A spike is a readable positional tax, never a soft-lock.
void room_stumble_off_hazard(void) BANKED {
    static const i8 dx[4] = { 0, 8, 0, -8 };
    static const i8 dy[4] = { -8, 0, 8, 0 };
    u8 i;
    for (i = 0; i < 4; ++i) {
        ppos_t nx = (ppos_t)(player.x + dx[i]);
        ppos_t ny = (ppos_t)(player.y + dy[i]);
        if (room_tile_at_px(nx + 8, ny + 12) == BGT_SPIKES) continue;
        if (room_player_position_clear(nx, ny)) {
            player.x = nx;
            player.y = ny;
            return;
        }
    }
}
