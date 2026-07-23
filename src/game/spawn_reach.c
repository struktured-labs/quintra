#pragma bank 6
#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "game/spawn_reach.h"
#include "render/tiles.h"

// This runs hundreds of times while flooding one generated room. Calling the
// bank-1 gameplay predicate from bank 2 for every one of four footprint tiles
// used to cross the far-call trampoline thousands of times and accounted for
// most of the visible pause before a room slide. Keep the exact predicate
// local to the generator's reachability pass; the live collision path retains
// room_tile_walkable() as its authoritative entry point.
static u8 spawn_tile_walkable(u8 t) {
    return (t == BGT_FLOOR || t == BGT_FLOOR2 || t == BGT_FLOOR3
         || t == BGT_GRASS || t == BGT_PATH || t == BGT_WILD_FLOWER
         || t == BGT_RUBBLE || t == BGT_DOOR || t == BGT_SPIKES
         || t == BGT_SWITCH || t == BGT_PORTAL
         || (t >= BGT_COLOSSUS_VOID && t <= BGT_COLOSSUS_HORN)
         || t == HUD_COIN || (t >= HUD_DIGIT_0 && t <= HUD_DIGIT_0 + 9));
}

// A marked cell is the top-left of a clear 2x2 tile footprint. Flooding this
// graph models the champion's body instead of a point: one-tile cracks may be
// connected floor mathematically while remaining impossible to traverse.
static u8 spawn_cell_open(u8 x, u8 y) {
    if (x + 1 >= ROOM_W || y + 1 >= ROOM_H) return 0;
    return spawn_tile_walkable((u8)(room_tilemap[y][x] & 0x7F))
        && spawn_tile_walkable((u8)(room_tilemap[y][x + 1] & 0x7F))
        && spawn_tile_walkable((u8)(room_tilemap[y + 1][x] & 0x7F))
        && spawn_tile_walkable((u8)(room_tilemap[y + 1][x + 1] & 0x7F));
}

// A generated room has only 340 cells. Spending a small slice of otherwise
// unused WRAM on a linear flood is dramatically cheaper than rescanning the
// entire tilemap until no new cell changes (the old worst case performed
// thousands of 2x2 footprint tests before every Zelda-style slide).
static u16 reach_queue[ROOM_W * ROOM_H];
static u16 reach_tail;

static void reach_enqueue(u8 x, u8 y) {
    if (x + 1 >= ROOM_W || y + 1 >= ROOM_H) return;
    if (room_tilemap[y][x] & 0x80) return;
    if (!spawn_cell_open(x, y)) return;
    room_tilemap[y][x] |= 0x80;
    reach_queue[reach_tail++] = (u16)(((u16)y << 8) | x);
}

// The high bit is free in BG tile IDs and is cleared before procgen returns.
void mark_spawn_reachable(void) BANKED {
    u8 sx = (u8)((player.x + 2) >> 3);
    u8 sy = (u8)((player.y + 8) >> 3);
    u16 head = 0;
    if (!spawn_cell_open(sx, sy)) return;
    reach_tail = 0;
    reach_enqueue(sx, sy);
    while (head < reach_tail) {
        u16 packed = reach_queue[head++];
        u8 x = (u8)packed;
        u8 y = (u8)(packed >> 8);
        if (x) reach_enqueue((u8)(x - 1), y);
        if (x + 1 < ROOM_W) reach_enqueue((u8)(x + 1), y);
        if (y) reach_enqueue(x, (u8)(y - 1));
        if (y + 1 < ROOM_H) reach_enqueue(x, (u8)(y + 1));
        // Every cell enters exactly once, so the fixed room-sized queue
        // cannot overflow even when the whole chamber is open.
        if (reach_tail >= ROOM_W * ROOM_H) return;
    }
}

void clear_spawn_reachable(void) BANKED {
    u8 x, y;
    for (y = 0; y < ROOM_H; ++y)
        for (x = 0; x < ROOM_W; ++x)
            room_tilemap[y][x] &= 0x7F;
}
