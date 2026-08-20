#pragma bank 6

#include "audio/sfx.h"
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

static u8 court_get(u8 x, u8 y) {
    if (y < ROOM_H) {
        return (x < ROOM_W) ? room_tilemap[y][x]
            : room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

static u8 court_hard_scenery(u8 tile) {
    tile &= 0x7F;
    return tile == BGT_WALL || tile == BGT_PILLAR || tile == BGT_CRYSTAL;
}

static u8 court_false_gap_floor(u8 tile) {
    tile &= 0x7F;
    return tile == BGT_FLOOR || tile == BGT_FLOOR2
        || tile == BGT_FLOOR3 || tile == BGT_RUBBLE
        || tile == BGT_SPIKES;
}

// Layering a stage silhouette over the 31x31 court can place two permanent
// masses exactly one floor tile apart. The 8px slit is not traversable by the
// champion's 12px feet box, so retaining it only teaches a false collision
// rule. Merge those zero-utility cells into the surrounding architecture.
// True routes are always two or more tiles wide and remain untouched.
void room_close_dungeon_false_gaps(void) BANKED {
    u8 x, y;
    // Geometry authoring guarantees every intentional passage is body-wide.
    // Stage silhouettes can overlap the shared court only in the western
    // 20x17 ABI. Normalize that composition east-to-west: the shared 2x2
    // cluster grammar puts its accent on the western side, so filling it can
    // expose the immediately preceding cell as another 8px slit. The distant
    // court is authored directly with body-wide gates and does not need a
    // 31x31 runtime rescan on every doorway.
    // Archetype landmarks occupy rows 2..14 and columns 1..17; the old row
    // 16/column 19 borders are open seams in a wide court. Keeping those
    // guaranteed-floor margins out of this hot loop saves the last doorway
    // frame without omitting any possible silhouette overlap.
    for (y = 2; y < ROOM_H - 2; ++y) {
        for (x = ROOM_W - 3; x > 0; --x) {
            u8 tile = court_get(x, y);
            if (!court_false_gap_floor(tile)) continue;
            if ((court_hard_scenery(court_get((u8)(x - 1), y))
                    && court_hard_scenery(court_get((u8)(x + 1), y)))
                || (court_hard_scenery(court_get(x, (u8)(y - 1)))
                    && court_hard_scenery(court_get(x, (u8)(y + 1))))) {
                court_set(x, y, BGT_PILLAR);
            }
        }
    }
}

static u8 court_texture(u32 seed, u8 x, u8 y, u8 district) {
    u8 n = (u8)seed;
    n = (u8)(n + (u8)(x * 13) + (u8)(y * 17) + (u8)(x * y));
    // A stage's five Compass rows are physical districts, not five copies of
    // one generic ruin. Their floor dialect remains seed-stable while making
    // depth readable even before the player opens SELECT.
    if (district == 0)
        return (n < 76) ? BGT_FLOOR3 : BGT_FLOOR;
    if (district == 1)
        return ((u8)(x + (y << 1) + n) & 3) ? BGT_FLOOR : BGT_FLOOR2;
    if (district == 2)
        return (n < 92) ? BGT_FLOOR2 : BGT_FLOOR;
    if (district == 3)
        return ((u8)(x ^ y ^ n) & 3) ? BGT_FLOOR : BGT_FLOOR3;
    return (n < 48) ? BGT_FLOOR2
        : (n > 214) ? BGT_FLOOR3 : BGT_FLOOR;
}

static void court_floor_rect(u8 x0, u8 y0, u8 w, u8 h) {
    u8 x, y;
    for (y = y0; y < (u8)(y0 + h); ++y)
        for (x = x0; x < (u8)(x0 + w); ++x)
            court_set(x, y, BGT_FLOOR);
}

static void court_stamp_cluster(u8 x, u8 y, u8 accent) {
    court_set(x, y, BGT_PILLAR);
    court_set((u8)(x + 1), y, BGT_PILLAR);
    court_set(x, (u8)(y + 1), accent);
    court_set((u8)(x + 1), (u8)(y + 1), accent);
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

static void court_wall_h(u8 y, u8 x0, u8 x1, u8 gap) {
    u8 x;
    for (x = x0; x <= x1; ++x)
        if (x != gap && x != (u8)(gap + 1))
            court_set(x, y, BGT_PILLAR);
}

static void court_wall_v(u8 x, u8 y0, u8 y1, u8 gap) {
    u8 y;
    for (y = y0; y <= y1; ++y)
        if (y != gap && y != (u8)(gap + 1))
            court_set(x, y, BGT_PILLAR);
}

// The six-cell Compass rows now correspond to five full-field geographic
// districts. These silhouettes deliberately occupy the former off-screen
// acreage: the western stage archetype still says "Ember" or "Frost", while
// this layer says how far inside that place the champion has travelled.
// Every wall has a body-wide gate, and the authoritative cardinal cross plus
// encounter aprons are carved again after this pass.
static void court_stamp_district(u8 district, u8 variant, u8 accent) {
    u8 shift = variant & 1;
    if (district == 0) {
        // GATE: four long pylons make an unmistakable outer march.
        court_wall_v((u8)(18 + shift), 2, 15, 8);
        court_wall_v((u8)(27 - shift), 2, 15, 8);
        // Their northern tips sit one row below the true boundary. Join that
        // cap to the architecture so row one never advertises an 8px pocket.
        court_set((u8)(18 + shift), 1, BGT_PILLAR);
        court_set((u8)(27 - shift), 1, BGT_PILLAR);
        court_stamp_cluster((u8)(18 + shift), 18, accent);
        court_stamp_cluster((u8)(26 - shift), 18, accent);
    } else if (district == 1) {
        // LOWER: offset retaining walls force a broad left/right weave.
        court_wall_h(12, 12, 29, shift ? 22 : 18);
        court_wall_h(21, 12, 29, shift ? 18 : 24);
        court_stamp_cluster(13, 14, accent);
        court_stamp_cluster(27, 23, accent);
    } else if (district == 2) {
        // DEEP: a four-gated sunken ring owns the southeast expedition.
        court_wall_h(15, 16, 29, shift ? 24 : 21);
        court_wall_h(29, 16, 29, shift ? 21 : 24);
        court_wall_v(16, 16, 28, shift ? 23 : 20);
        court_wall_v(29, 16, 28, shift ? 20 : 23);
    } else if (district == 3) {
        // INNER: crossing processional walls divide the field into wards.
        court_wall_v((u8)(20 + shift), 2, 28, 8);
        court_wall_h((u8)(20 - shift), 2, 29, 9);
        court_stamp_cluster(24, 4, accent);
        court_stamp_cluster(4, 24, accent);
    } else {
        // HEART: a broken nested keep makes the last row feel like an inner
        // destination before the compact merchant/sanctuary/Colossus cadence.
        court_wall_h(12, 14, 29, shift ? 24 : 20);
        court_wall_v(14, 12, 28, shift ? 22 : 18);
        court_wall_v(29, 12, 28, shift ? 18 : 22);
        court_wall_h(28, 14, 29, shift ? 20 : 24);
        court_wall_h(18, 19, 27, shift ? 23 : 20);
    }
}

void room_generate_dungeon_court(u32 seed) BANKED {
    u8 x, y;
    u8 local = run_state_dungeon_local();
    u8 district = (u8)(local / DUNGEON_GRID_W);
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
                ? BGT_WALL : court_texture(seed, x, y, district));
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
        // viewport. Two joined pillars face a two-tile accent bed: there is
        // no longer a decorative one-tile slit between hard columns that
        // looks open but cannot admit the champion. Combined with the
        // independent one-tile ruin shift, this gives every stage at least
        // eight meaningful collision silhouettes across the standard
        // twelve-seed sample—not merely different floor speckles. They sit
        // outside the body-wide central cross.
        u8 bx = (variant & 1) ? 12 : 4;
        u8 by = (variant & 2) ? 14 : 2;
        // A north-facing crest must meet the outer wall. Leaving row 1 as
        // floor above these pillars reads as a passable one-tile channel,
        // even though the champion cannot fit through it.
        if (by == 2) {
            court_set(bx, 1, BGT_PILLAR);
            court_set((u8)(bx + 1), 1, BGT_PILLAR);
        }
        court_set(bx, by, BGT_PILLAR);
        court_set((u8)(bx + 1), by, BGT_PILLAR);
        court_set((u8)(bx + 2), by, accent);
        court_set((u8)(bx + 3), by, accent);
    }
    // Two recognizable side halls make camera travel expose architecture,
    // not a mostly empty floor. Seed-selected paired gaps keep both chambers
    // permeable while their walls create Penta-style firing lanes and cover.
    {
        u8 east_gap = shift ? 25 : 22;
        court_stamp_ruin(20, 2, 9, 8, east_gap, 5);
        // The ruin's top edge sits only one tile below the true world wall.
        // A gate here creates a 16x16-looking alcove whose body positions
        // cannot rejoin the field. Keep this edge solid; the paired side and
        // south gates still make the hall permeable, while false-gap
        // normalization can honestly merge the one-tile northern overhang.
        court_set(east_gap, 2, BGT_PILLAR);
        court_set((u8)(east_gap + 1), 2, BGT_PILLAR);
        // Row one would otherwise be an 8px strip trapped between the true
        // world boundary and this solid ruin roof. Author it as the same
        // architectural mass up front; the fast western normalization pass
        // never needs to scan this distant sector.
        for (x = 20; x <= 28; ++x)
            court_set(x, 1, BGT_PILLAR);
    }
    // Start the lower ruin at x=13 rather than x=14. The Deep district's
    // independent ring owns a permanent wall at x=16; leaving the ruin at
    // x=14 made their "cloister" only column 15—an 8px visual slit the
    // champion could never enter. Columns 14..15 now form a genuine
    // body-wide passage while the ruin keeps the same eastern boundary.
    court_stamp_ruin(13, 16, 16, 13,
                     shift ? 24 : 20, shift ? 23 : 19);
    court_stamp_district(district, variant, accent);

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
    // Carry the northeast apron through the side-hall perimeter. District
    // pylons may cross the old ruin, and a body entering from its far side
    // must never be marooned between that landmark and the outer wall.
    court_floor_rect(19, 5, 11, 4);
    // The lower ruin can be crossed by both its own perimeter and the Inner
    // district's processional walls. Reopen a body-wide cloister through
    // every overlapping layer so neither half becomes an isolated pocket.
    // Begin at the central x=9..10 route, not at the ruin wall. Columns
    // 11..12 could inherit a district barrier and silently turn the entire
    // southern court—including its optional reliquary—into an open island.
    court_floor_rect(9, 19, 21, 2);
    court_floor_rect(23, 24, 7, 6);

    // Close the one-tile service strips left between the two side halls and
    // the true east/south perimeter. They look like passages but are only
    // eight pixels wide; the broad aprons above remain the playable route.
    for (y = 1; y <= 4; ++y)
        court_set(29, y, BGT_PILLAR);
    for (y = 16; y <= 18; ++y)
        court_set(29, y, BGT_PILLAR);
    for (y = 21; y <= 22; ++y)
        court_set(29, y, BGT_PILLAR);
    for (x = 13; x <= 22; ++x)
        court_set(x, 29, BGT_PILLAR);

    // Joined landmarks can also sandwich a single floor cell where their
    // authored silhouettes overlap. Merge those few fixed joints rather
    // than paying for another full-field normalization pass on every door.
    court_set(27, 3, BGT_PILLAR);
    court_set(27, 4, BGT_PILLAR);
    court_set(19, 17, BGT_PILLAR);
    court_set(20, 17, BGT_PILLAR);
    court_set(26, 17, BGT_PILLAR);
    court_set(27, 17, BGT_PILLAR);
    court_set(27, 18, BGT_PILLAR);

    if (local == run_state_dungeon_cache_cell()) {
        // One generated dead-end owns a recognizable southeast reliquary.
        // It sits well away from the cardinal cross, making the scrolling
        // acreage mechanically optional rather than decorative padding.
        // Join the altar to the lower processional hall with a body-wide
        // cloister. The old visual apron was open locally but could become a
        // disconnected island when the Inner district walls overlapped it.
        court_floor_rect(25, 19, 4, 10);
        // Four pylons frame a walkable altar on the guaranteed cloister.
        court_set(24, 23, BGT_CRYSTAL);
        court_set(29, 23, BGT_CRYSTAL);
        court_set(24, 28, BGT_CRYSTAL);
        court_set(29, 28, BGT_CRYSTAL);
        court_set(26, 25, BGT_RUBBLE);
        court_set(27, 25, BGT_RUBBLE);
        court_set(26, 26, BGT_RUBBLE);
        court_set(27, 26, BGT_SWITCH);
    }

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

    // Maze rows only connect north/south across a district boundary. The
    // generator runs after the ordinary door whoosh, so this calm two-note
    // bell replaces it precisely when the hero crosses into another named
    // depth band. DIR_NONE on initial entry and nonlinear Rifts stays quiet.
    if (run_state.entered_from == DIR_N || run_state.entered_from == DIR_S)
        sfx_play(SFX_DISTRICT);
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
    // False-gap normalization runs once after every terrain-writing role in
    // procgen has finished. Running it here as well made the second pass see
    // the first pass's intentional fill as fresh scenery and could shrink a
    // legitimate two-tile gate one layer at a time.
}
