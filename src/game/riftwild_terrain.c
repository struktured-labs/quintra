#pragma bank 11

#include <gb/gb.h>

#include "core/types.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

static u8 world_tile(u8 x, u8 y) {
    if (y < ROOM_H) {
        if (x < ROOM_W) return room_tilemap[y][x];
        return room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

static void world_put(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
}

static u8 climate_floor(u8 zone) {
    if (zone == 0) return BGT_WILD_SNOW;
    if (zone == 4) return BGT_WILD_MUD;
    if (zone == 5) return BGT_WILD_SAND;
    return BGT_GRASS;
}

static u8 feature_floor(u8 tile, u8 base) {
    return tile == BGT_GRASS || tile == base;
}

// Keep the tiny reciprocal-edge rule resident with the terrain painter.
// zelda_overworlds[] is switchable-bank data owned by the generator; reading
// its pointer directly from bank 11 aliases unrelated ROM on real hardware.
static u8 horizontal_open(u8 row, u8 col) {
    return !((row == 1 && col == 2)
        || (row == 2 && col == 0)
        || (row == 3 && col == 3)
        || (row == 4 && col == 1));
}

static u8 vertical_open(u8 row, u8 col) {
    return !((row == 0 && col == 4)
        || (row == 1 && col == 1)
        || (row == 2 && col == 3)
        || (row == 3 && col == 0)
        || (row == 4 && col == 4));
}

static u8 terrain_edges(u8 screen) {
    u8 row = (u8)(screen / 6);
    u8 col = (u8)(screen - row * 6);
    u8 edges = 0;
    if (row && vertical_open((u8)(row - 1), col)) edges |= 0x01;
    if (col < 5 && horizontal_open(row, col)) edges |= 0x02;
    if (row < 5 && vertical_open(row, col)) edges |= 0x04;
    if (col && horizontal_open(row, (u8)(col - 1))) edges |= 0x08;
    return edges;
}

// Diamond-shaped geography reads cleanly at 8px while avoiding noisy single
// tile scatter. Existing paths, portals, landmarks, and capability gates are
// never overwritten, so terrain can be dramatic without invalidating a route.
static void stamp_land(u8 cx, u8 cy, u8 rx, u8 ry, u8 tile, u8 base) {
    u8 x, y;
    for (y = (cy > ry ? (u8)(cy - ry) : 1);
         y <= (u8)(cy + ry) && y < ROOM_WIDE_H_TILES - 1; ++y) {
        for (x = (cx > rx ? (u8)(cx - rx) : 1);
             x <= (u8)(cx + rx) && x < ROOM_WIDE_W_TILES - 1; ++x) {
            u8 dx = x > cx ? (u8)(x - cx) : (u8)(cx - x);
            u8 dy = y > cy ? (u8)(y - cy) : (u8)(cy - y);
            u8 old = world_tile(x, y);
            if ((u16)dx * ry + (u16)dy * rx <= (u16)rx * ry
                && feature_floor(old, base)) world_put(x, y, tile);
        }
    }
}

static void carve_edge_mouths(u8 edges, u8 base) {
    u8 i, d;
    // Six-tile natural thresholds replace the dungeon-like two-tile doorway.
    // Boundary cells stay PATH because the transition detector needs a clear
    // authored edge; the next two rows/columns flare into the local climate.
    if (edges & 0x01) for (d = 0; d < 3; ++d) for (i = 7; i <= 12; ++i)
        world_put(i, d, d == 0 || (i >= 9 && i <= 10) ? BGT_PATH : base);
    if (edges & 0x04) for (d = 0; d < 3; ++d) for (i = 7; i <= 12; ++i)
        world_put(i, (u8)(30 - d), d == 0 || (i >= 9 && i <= 10)
            ? BGT_PATH : base);
    if (edges & 0x08) for (d = 0; d < 3; ++d) for (i = 6; i <= 11; ++i)
        world_put(d, i, d == 0 || (i >= 8 && i <= 9) ? BGT_PATH : base);
    if (edges & 0x02) for (d = 0; d < 3; ++d) for (i = 6; i <= 11; ++i)
        world_put((u8)(30 - d), i, d == 0 || (i >= 8 && i <= 9)
            ? BGT_PATH : base);
}

static void carve_return_landing(u8 base) {
    u8 x, y;
    // Boss exits enter fields 0, 8, and 21 from a non-graph threshold. Give
    // that centered arrival a body-safe outdoor apron before reachability
    // marks encounters; otherwise a climate ridge can suppress the complete
    // field roster or make the hero's first step an apparent soft lock.
    for (y = 1; y <= 5; ++y)
        for (x = 7; x <= 12; ++x)
            world_put(x, y, (x == 9 || x == 10) ? BGT_PATH : base);
    // Join the apron to the permanent field crossing through any ridge/lake
    // feature, so encounter placement and the player share the full region.
    for (y = 5; y <= 10; ++y)
        world_put(9, y, BGT_PATH), world_put(10, y, BGT_PATH);
}

static u8 hollow_reward_screen(void) {
    u8 step = run_state.bosses_beaten;
    static const u8 reward[3] = { 5, 22, 35 };
    if (step) step--;
    while (step >= DUNGEONS_PER_REGION)
        step = (u8)(step - DUNGEONS_PER_REGION);
    return reward[step];
}

static void hollow_world_apply(u8 base) {
    u8 x, y;
    // Erase the living world's meaning rather than merely dimming it:
    // flowers become broken earth, standing water becomes void holes, and
    // strips of remembered ground survive as bone-pale snow/mud islands.
    for (y = 1; y < ROOM_WIDE_H_TILES - 1; ++y) {
        for (x = 1; x < ROOM_WIDE_W_TILES - 1; ++x) {
            u8 tile = world_tile(x, y);
            if (tile == BGT_WILD_FLOWER) world_put(x, y, BGT_WILD_HOLE);
            else if (tile == BGT_WILD_WATER && ((x + y) & 1))
                world_put(x, y, BGT_WILD_REEDS);
            else if ((tile == BGT_GRASS || tile == base)
                && ((u8)(x * 3 + y * 5 + run_state.world_screen) & 15) < 3)
                world_put(x, y, (x & 1) ? BGT_WILD_MUD : BGT_WILD_SNOW);
        }
    }
    // Hollow-only relics sit in the far matching sector. Carve an obvious
    // broken processional road from the shared cross so the reward is gated
    // by finding the counterpart field and surviving it, never by collision.
    if (run_state.world_screen == hollow_reward_screen()) {
        for (y = 9; y <= 25; ++y) {
            world_put(9, y, BGT_PATH);
            world_put(10, y, BGT_PATH);
        }
        for (x = 9; x <= 27; ++x) {
            world_put(x, 24, BGT_PATH);
            world_put(x, 25, BGT_PATH);
        }
        for (y = 23; y <= 27; ++y)
            for (x = 24; x <= 28; ++x)
                world_put(x, y, BGT_WILD_SNOW);
        world_put(25, 23, BGT_CRYSTAL);
        world_put(27, 23, BGT_CRYSTAL);
        world_put(25, 27, BGT_CRYSTAL);
        world_put(27, 27, BGT_CRYSTAL);
    }
}

void riftwild_terrain_apply(u8 seed_low) BANKED {
    u8 x, y;
    u8 zone = (u8)(run_state.world_screen / 6);
    u8 salt = (u8)(seed_low + run_state.riftwild_region * 17u);
    u8 base = climate_floor(zone);

    // Broad regional ground first: frost north, wetlands south-west, dunes
    // south-east. The middle belts retain grass beneath their stronger forms.
    if (base != BGT_GRASS) {
        for (y = 1; y < ROOM_WIDE_H_TILES - 1; ++y)
            for (x = 1; x < ROOM_WIDE_W_TILES - 1; ++x)
                if (world_tile(x, y) == BGT_GRASS) world_put(x, y, base);
    }

    if (zone == 0) {
        // Frostfell: a frozen lake basin and a hard northern mountain crown.
        stamp_land((u8)(21 + (salt & 1)), 21, 7, 5,
            BGT_WILD_WATER, base);
        stamp_land((u8)(6 + ((salt >> 1) & 3)), 5, 6, 3,
            BGT_WILD_MOUNTAIN, base);
    } else if (zone == 1) {
        // Lakewood: dense old growth bends around one large blue lake.
        stamp_land((u8)(7 + (salt & 3)), 22, 6, 5,
            BGT_WILD_WATER, base);
        stamp_land(23, (u8)(5 + ((salt >> 2) & 3)), 6, 4,
            BGT_TREE, base);
        stamp_land(5, 6, 3, 3, BGT_TREE, base);
    } else if (zone == 2) {
        // High ridge: two staggered masses make genuine mountain passes.
        stamp_land((u8)(7 + (salt & 3)), 7, 7, 4,
            BGT_WILD_MOUNTAIN, base);
        stamp_land((u8)(22 - ((salt >> 2) & 3)), 22, 7, 4,
            BGT_WILD_STONE, base);
        stamp_land(24, 5, 3, 3, BGT_WILD_HOLE, base);
    } else if (zone == 3) {
        // Riverplain: a connected meander and broad central lake. PATH cells
        // survive as visible bridges wherever a route crosses the water.
        u8 river = (u8)(5 + (salt & 3));
        for (y = 1; y < ROOM_WIDE_H_TILES - 1; ++y) {
            if ((y & 3) == 0 && river < 23) river++;
            for (x = river; x <= (u8)(river + 2); ++x)
                if (feature_floor(world_tile(x, y), base))
                    world_put(x, y, BGT_WILD_WATER);
        }
        stamp_land(22, (u8)(20 + ((salt >> 3) & 3)), 6, 5,
            BGT_WILD_WATER, base);
    } else if (zone == 4) {
        // Mire: mud is traversable; pools, reeds, stumps, and sinkholes shape
        // slower-looking lanes without adding hidden movement penalties.
        stamp_land((u8)(6 + (salt & 3)), 7, 5, 4,
            BGT_WILD_WATER, base);
        stamp_land(23, 21, 6, 5, BGT_WILD_REEDS, base);
        stamp_land(6, 24, 3, 3, BGT_WILD_HOLE, base);
        stamp_land(24, 6, 3, 3, BGT_WILD_STUMP, base);
    } else {
        // Sunscar: open sand, a broken canyon, mountain teeth, and one oasis.
        stamp_land((u8)(6 + (salt & 3)), 7, 6, 3,
            BGT_WILD_MOUNTAIN, base);
        stamp_land(20, 22, 7, 3, BGT_WILD_HOLE, base);
        stamp_land(24, 7, 4, 3, BGT_WILD_WATER, base);
        stamp_land(24, 7, 5, 4, BGT_WILD_FLOWER, base);
        stamp_land(24, 7, 3, 2, BGT_WILD_WATER, base);
    }

    if (run_state.world_screen == 0 || run_state.world_screen == 8
        || run_state.world_screen == 21) carve_return_landing(base);
    if (RUN_RIFTWILD_IS_HOLLOW()) hollow_world_apply(base);
    carve_edge_mouths(terrain_edges(run_state.world_screen), base);
}
