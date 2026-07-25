#pragma bank 6

#include "core/types.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

// The compact 20x17 ABI and its extension strips are one logical 31x31 map.
// Keeping the coordinate split here prevents every generator pass from
// learning three storage layouts.
static void court_set(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else {
        room_world_bottom[y - ROOM_H][x] = tile;
    }
}

static u8 court_texture(u32 seed, u8 x, u8 y) {
    u8 n = (u8)seed;
    n = (u8)(n + (u8)(x * 13) + (u8)(y * 17) + (u8)(x * y));
    return (n < 38) ? BGT_FLOOR2 : (n < 64) ? BGT_FLOOR3 : BGT_FLOOR;
}

static void court_floor_rect(u8 x0, u8 y0, u8 w, u8 h) {
    u8 x, y;
    for (y = y0; y < (u8)(y0 + h); ++y)
        for (x = x0; x < (u8)(x0 + w); ++x)
            court_set(x, y, BGT_FLOOR);
}

static void court_stamp_cluster(u8 x, u8 y, u8 accent) {
    court_set(x, y, BGT_PILLAR);
    court_set((u8)(x + 1), y, accent);
    court_set(x, (u8)(y + 1), accent);
    court_set((u8)(x + 1), (u8)(y + 1), BGT_PILLAR);
}

static void court_stamp_ruin(u8 x0, u8 y0, u8 w, u8 h,
                             u8 gap_x, u8 gap_y) {
    u8 x, y;
    u8 x1 = (u8)(x0 + w - 1);
    u8 y1 = (u8)(y0 + h - 1);
    for (x = x0; x <= x1; ++x) {
        if (x != gap_x && x != (u8)(gap_x + 1)) {
            court_set(x, y0, BGT_PILLAR);
            court_set(x, y1, BGT_PILLAR);
        }
    }
    for (y = (u8)(y0 + 1); y < y1; ++y) {
        if (y != gap_y && y != (u8)(gap_y + 1)) {
            court_set(x0, y, BGT_PILLAR);
            court_set(x1, y, BGT_PILLAR);
        }
    }
}

void room_generate_dungeon_court(u32 seed) BANKED {
    u8 x, y;
    u8 local = run_state_dungeon_local();
    u8 stage = (u8)(run_state.bosses_beaten % 9);
    u8 accent = (stage == 2 || stage == 4 || stage == 7)
        ? BGT_SPIKES : BGT_RUBBLE;
    u8 shift = (u8)((seed >> 5) & 1);
    u8 variant = (u8)((seed >> 11) & 3);

    // Only the true 31x31 perimeter is solid. The former 20x17 edge is
    // ordinary interior terrain on both axes.
    for (y = 0; y < ROOM_WIDE_H_TILES; ++y) {
        for (x = 0; x < ROOM_WIDE_W_TILES; ++x) {
            court_set(x, y,
                (x == 0 || x == ROOM_WIDE_W_TILES - 1
                    || y == 0 || y == ROOM_WIDE_H_TILES - 1)
                ? BGT_WALL : court_texture(seed, x, y));
        }
    }

    // Four seed-shifted landmark pairs give each repeated scrolling district
    // a stable silhouette without freezing every expedition to one arrangement.
    court_stamp_cluster((u8)(3 + shift), 3, accent);
    court_stamp_cluster((u8)(15 - shift), 4, accent);
    court_stamp_cluster((u8)(4 + shift), 21, accent);
    court_stamp_cluster((u8)(24 - shift), 19, accent);
    court_stamp_cluster((u8)(25 - shift), 26, accent);
    {
        // Four approach crests occupy distinct corners of the legacy
        // viewport. Combined with the independent one-tile ruin shift, this
        // gives every stage at least eight meaningful collision silhouettes
        // across the standard twelve-seed sample—not merely different floor
        // speckles. They sit outside the body-wide central cross.
        u8 bx = (variant & 1) ? 12 : 4;
        u8 by = (variant & 2) ? 14 : 2;
        for (x = bx; x < (u8)(bx + 4); ++x)
            court_set(x, by, (x & 1) ? BGT_PILLAR : accent);
    }
    if (local >= 11) {
        u8 gap = (seed & 0x100) ? 17 : 22;
        for (x = 15; x <= 24; ++x)
            if (x != gap && x != (u8)(gap + 1))
                court_set(x, 13, (x & 1) ? BGT_PILLAR : accent);
    }
    // Two recognizable side halls make camera travel expose architecture,
    // not a mostly empty floor. Seed-selected paired gaps keep both chambers
    // permeable while their walls create Penta-style firing lanes and cover.
    court_stamp_ruin(20, 2, 9, 8, shift ? 25 : 22, 5);
    court_stamp_ruin(14, 16, 15, 13,
                     shift ? 24 : 20, shift ? 23 : 19);

    // The familiar cardinal lanes are authoritative and are carved last, so
    // no landmark or ruin can turn a visible graph threshold into decoration.
    for (y = 1; y < ROOM_WIDE_H_TILES - 1; ++y) {
        court_set(9, y, BGT_FLOOR);
        court_set(10, y, BGT_FLOOR);
    }
    for (x = 1; x < ROOM_WIDE_W_TILES - 1; ++x) {
        court_set(x, 8, BGT_FLOOR);
        court_set(x, 9, BGT_FLOOR);
    }

    // Guaranteed body-valid encounter aprons in both distant sectors.
    court_floor_rect(22, 5, 4, 4);
    court_floor_rect(25, 24, 4, 4);

    // Only reciprocal dungeon graph edges become doors. North/south retain
    // x=9..10 and east/west y=8..9 so one threshold grammar spans all rooms.
    if (run_state_dungeon_neighbor(DIR_N) != 0xFF) {
        court_set(9, 0, BGT_DOOR); court_set(10, 0, BGT_DOOR);
    }
    if (run_state_dungeon_neighbor(DIR_E) != 0xFF) {
        court_set(ROOM_WIDE_W_TILES - 1, 8, BGT_DOOR);
        court_set(ROOM_WIDE_W_TILES - 1, 9, BGT_DOOR);
    }
    if (run_state_dungeon_neighbor(DIR_S) != 0xFF) {
        court_set(9, ROOM_WIDE_H_TILES - 1, BGT_DOOR);
        court_set(10, ROOM_WIDE_H_TILES - 1, BGT_DOOR);
    }
    if (run_state_dungeon_neighbor(DIR_W) != 0xFF) {
        court_set(0, 8, BGT_DOOR); court_set(0, 9, BGT_DOOR);
    }
}

void room_reopen_dungeon_court_seams(u32 seed) BANKED {
    u8 seam, x, y;
    // A wide court owns one continuous 31x31 collision field. The compact
    // map's final row and column are interior after expansion, even when the
    // stage archetype layered immediately afterward was authored for 20x17.
    for (seam = 1; seam < ROOM_W - 1; ++seam)
        room_tilemap[ROOM_H - 1][seam] = BGT_FLOOR;
    for (seam = 1; seam < ROOM_H - 1; ++seam)
        room_tilemap[seam][ROOM_W - 1] = BGT_FLOOR;

    // The compact generator stamps the nonlinear local-2/local-8 Rift before
    // a wide court replaces its complete map. Re-author that seed-pure
    // fixture after stage silhouettes and seam cleanup, keeping the portal in
    // the readable western sector with a body-wide route to the central
    // cross. This consumes no RNG and lives in the roomy world bank rather
    // than crowding procgen's release-critical bank.
    if (run_state.bosses_beaten > 0
        && (run_state_dungeon_local() == 2
            || run_state_dungeon_local() == 8)) {
        u8 px = (seed & 4) ? 5 : 14;
        u8 py = (seed & 8) ? 4 : 12;
        u8 left = (px < 10) ? (u8)(px - 2) : 9;
        u8 right = (px < 10) ? 10 : px;
        u8 top = (py < 8) ? (u8)(py - 2) : 7;
        u8 bottom = (py < 8) ? 8 : py;
        for (y = (u8)(py - 2); y <= py; ++y)
            for (x = left; x <= right; ++x)
                court_set(x, y, BGT_FLOOR);
        for (y = top; y <= bottom; ++y)
            for (x = 9; x <= 11; ++x)
                court_set(x, y, BGT_FLOOR);
        for (y = 7; y <= 9; ++y)
            for (x = 1; x < ROOM_W - 1; ++x)
                court_set(x, y, BGT_FLOOR);
        for (y = 1; y < ROOM_H - 1; ++y)
            for (x = 9; x <= 11; ++x)
                court_set(x, y, BGT_FLOOR);
        for (y = (u8)(py - 2); y <= py; ++y)
            for (x = (u8)(px - 2); x <= px; ++x)
                court_set(x, y, BGT_FLOOR);
        court_set(px, py, BGT_PORTAL);
    }
}
