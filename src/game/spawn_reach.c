#pragma bank 2
#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "game/spawn_reach.h"

// A marked cell is the top-left of a clear 2x2 tile footprint. Flooding this
// graph models the champion's body instead of a point: one-tile cracks may be
// connected floor mathematically while remaining impossible to traverse.
static u8 spawn_cell_open(u8 x, u8 y) {
    if (x + 1 >= ROOM_W || y + 1 >= ROOM_H) return 0;
    return room_tile_walkable((u8)(room_tilemap[y][x] & 0x7F))
        && room_tile_walkable((u8)(room_tilemap[y][x + 1] & 0x7F))
        && room_tile_walkable((u8)(room_tilemap[y + 1][x] & 0x7F))
        && room_tile_walkable((u8)(room_tilemap[y + 1][x + 1] & 0x7F));
}

// The high bit is free in BG tile IDs and is cleared before procgen returns.
void mark_spawn_reachable(void) BANKED {
    u8 sx = (u8)((player.x + 2) >> 3);
    u8 sy = (u8)((player.y + 8) >> 3);
    u8 changed;
    if (!spawn_cell_open(sx, sy)) return;
    room_tilemap[sy][sx] |= 0x80;
    do {
        u8 x, y;
        changed = 0;
        for (y = 1; y < ROOM_H - 1; ++y) {
            for (x = 1; x < ROOM_W - 1; ++x) {
                u8 tile = room_tilemap[y][x];
                if ((tile & 0x80) || !spawn_cell_open(x, y)) continue;
                if ((room_tilemap[y - 1][x] & 0x80)
                    || (room_tilemap[y + 1][x] & 0x80)
                    || (room_tilemap[y][x - 1] & 0x80)
                    || (room_tilemap[y][x + 1] & 0x80)) {
                    room_tilemap[y][x] = (u8)(tile | 0x80);
                    changed = 1;
                }
            }
        }
    } while (changed);
}

void clear_spawn_reachable(void) BANKED {
    u8 x, y;
    for (y = 0; y < ROOM_H; ++y)
        for (x = 0; x < ROOM_W; ++x)
            room_tilemap[y][x] &= 0x7F;
}
