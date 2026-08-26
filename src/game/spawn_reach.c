#pragma bank 11
#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/spawn_reach.h"
#include "render/tiles.h"

// This runs hundreds of times while flooding one generated room. Calling the
// bank-1 gameplay predicate from this cold bank for every footprint tile
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

static u8 spawn_full_body_obstacle(u8 t) {
    t &= 0x7F;
    return t == BGT_PILLAR || t == BGT_BLOCK || t == BGT_BLOCK_TR
        || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR;
}

// Enemy placement intentionally retains its established feet-space flood so
// reward hardening does not reshuffle deterministic combat layouts. Major
// treasure opts into the stricter live-body model for one cold flood.
static u8 reach_full_body;

// A marked cell is the top-left of a clear 2x2 tile footprint. Flooding this
// graph models the champion's body instead of a point: one-tile cracks may be
// connected floor mathematically while remaining impossible to traverse.
static u8 spawn_cell_open(u8 x, u8 y) {
    if (x + 1 >= ROOM_W || y + 1 >= ROOM_H) return 0;
    // The live hero has a feet-anchored walk box, but pillars and push blocks
    // collide with the complete 16px body. A floor apron immediately below
    // one of those props therefore is not a real standing cell even though
    // its 2x2 floor footprint looks open. Reward placement uses this flood;
    // omitting the upper-body row can strand one boon beneath a pillar while
    // its sibling remains collectible.
    if (reach_full_body && y
            && (spawn_full_body_obstacle(room_tilemap[y - 1][x])
            || spawn_full_body_obstacle(room_tilemap[y - 1][x + 1])))
        return 0;
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
    // The marker intentionally covers the compact 20x17 storage plane; the
    // extension strips live in separate arrays. A hero entering a scrolling
    // court from its true west/north neighbour can therefore begin at
    // x=224/y=224, outside this local array. Project that arrival back onto
    // the guaranteed-open central seam before flooding. The wide generator
    // carves these two body-wide axes across the entire 31x31 court, so this
    // selects the same connected component without reading beyond
    // room_tilemap. Previously local room 9's west arrival made
    // spawn_cell_open() index off the compact map, suppressed its mandatory
    // Sentinel, and left the sanctuary gate permanently locked.
    if (sy >= ROOM_H - 1) {
        sx = 9;
        sy = ROOM_H - 2;
    } else if (sx >= ROOM_W - 1) {
        sx = ROOM_W - 2;
    }
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

void mark_enemy_spawn_reachable(void) BANKED {
    reach_full_body = 1;
    mark_spawn_reachable();
    reach_full_body = 0;
}

void clear_spawn_reachable(void) BANKED {
    u8 x, y;
    for (y = 0; y < ROOM_H; ++y)
        for (x = 0; x < ROOM_W; ++x)
            room_tilemap[y][x] &= 0x7F;
}

static u8 reward_tile_safe(u8 tile) {
    tile &= 0x7F;
    return spawn_tile_walkable(tile) && tile != BGT_SPIKES
        && tile != BGT_PORTAL && tile != BGT_SWITCH;
}

static u8 reward_cell_reachable(u8 x, u8 y) {
    if (x + 1 >= ROOM_W || y + 1 >= ROOM_H) return 0;
    // Only the top-left body cell carries the flood mark. The four terrain
    // samples independently reject hazards that are legal movement space but
    // terrible permanent-item pedestals.
    return (room_tilemap[y][x] & 0x80)
        && reward_tile_safe(room_tilemap[y][x])
        && reward_tile_safe(room_tilemap[y][x + 1])
        && reward_tile_safe(room_tilemap[y + 1][x])
        && reward_tile_safe(room_tilemap[y + 1][x + 1]);
}

u8 snap_reward_to_reachable(i16 *px, i16 *py) BANKED {
    u8 preferred_x = (u8)(*px >> 3);
    u8 preferred_y = (u8)(*py >> 3);
    u8 best_x = 0, best_y = 0, best_distance = 0xFF;
    u8 x, y, found = 0;

    reach_full_body = 1;
    mark_spawn_reachable();
    for (y = 0; y < ROOM_H - 1; ++y) {
        for (x = 0; x < ROOM_W - 1; ++x) {
            u8 dx, dy, distance;
            if (!reward_cell_reachable(x, y)) continue;
            dx = x > preferred_x ? (u8)(x - preferred_x)
                : (u8)(preferred_x - x);
            dy = y > preferred_y ? (u8)(y - preferred_y)
                : (u8)(preferred_y - y);
            distance = (u8)(dx + dy);
            if (!found || distance < best_distance) {
                best_x = x;
                best_y = y;
                best_distance = distance;
                found = 1;
            }
        }
    }
    clear_spawn_reachable();
    reach_full_body = 0;
    if (found) {
        *px = (i16)best_x << 3;
        *py = (i16)best_y << 3;
    }
    return found;
}

void snap_major_pickup_to_reachable(u8 kind, fix8_t *x, fix8_t *y) BANKED {
    i16 px, py;
    if (kind != PICKUP_ITEM && kind != PICKUP_WEAPON
        && kind != PICKUP_RIFT_SIGIL && kind != PICKUP_FARFOLD_RELIC
        && kind != PICKUP_BOON_CHOICE) return;
    px = FIX8_TO_INT(*x);
    py = FIX8_TO_INT(*y);
    // Authored objectives and caches live in the compact storage plane. Loot
    // dropped by a reachable enemy in a wide extension is already connected;
    // projecting it back would merely move it several screens away.
    if (px >= ROOM_VIEW_W_PX || py >= ROOM_VIEW_H_PX) return;
    if (snap_reward_to_reachable(&px, &py)) {
        *x = FIX8(px);
        *y = FIX8(py);
    }
}
