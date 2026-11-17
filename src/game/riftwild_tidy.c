#pragma bank 20
// Riftwild tile tidy pass (docs/superpowers/specs/2026-11-17-riftwild-tile-tidy.md).
// Pinned to bank 20: as an autobanked module it landed in near-full banks
// and broke the 256-byte headroom floor (check_rom_layout.py).
//
// Two jobs, both deterministic and RNG-free:
//  * riftwild_tidy_field(): every field, before the set piece and scatter.
//    Trees and crags render as 2x2 canopies/peaks, so any tree or crag cell
//    that is not part of a complete aligned 2x2 block used to draw a lone
//    quarter (half a crown, a cut ridge). Erode those cells back to the
//    field's ground. Removing solid cells only ever widens routes;
//    capability gates and portals pin their neighbours. (Water/sinkhole
//    tips and one-tile channels are drawn by the lone/cap/strait shore
//    tiles instead of being pruned: a pruning scan cost ~5 frames per
//    field build.)
//  * riftwild_meta_scan(): every field, after the final terrain write.
//    Records which aligned 2x2 blocks are whole tree/crag metatiles so the
//    renderer draws quarters only there and a self-contained tile elsewhere
//    (rim hedge, one-tile grove walls, waygear pockets, den clearings).

#include <gb/gb.h>

#include "core/types.h"
#include "game/riftwild_phase.h"
#include "game/riftwild_setpiece.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

BANKREF(riftwild_tidy_field)

u8 rw_block_ok[RW_BLOCK_BYTES];

// Row tables (no 2-D index multiply): rows 0..16 of the field start in
// room_tilemap and continue at x >= 20 in room_world_extension (hi
// table, indexed from x - 20); rows
// 17..30 are whole rows of room_world_bottom. Every scan here runs on each
// field build, so cell access must stay a couple of loads.
static u8 * const rw_row_lo[ROOM_WIDE_H_TILES] = {
    &room_tilemap[0][0], &room_tilemap[1][0], &room_tilemap[2][0],
    &room_tilemap[3][0], &room_tilemap[4][0], &room_tilemap[5][0],
    &room_tilemap[6][0], &room_tilemap[7][0], &room_tilemap[8][0],
    &room_tilemap[9][0], &room_tilemap[10][0], &room_tilemap[11][0],
    &room_tilemap[12][0], &room_tilemap[13][0], &room_tilemap[14][0],
    &room_tilemap[15][0], &room_tilemap[16][0], &room_world_bottom[0][0],
    &room_world_bottom[1][0], &room_world_bottom[2][0],
    &room_world_bottom[3][0], &room_world_bottom[4][0],
    &room_world_bottom[5][0], &room_world_bottom[6][0],
    &room_world_bottom[7][0], &room_world_bottom[8][0],
    &room_world_bottom[9][0], &room_world_bottom[10][0],
    &room_world_bottom[11][0], &room_world_bottom[12][0],
    &room_world_bottom[13][0]
};
static u8 * const rw_row_hi[ROOM_H] = {
    &room_world_extension[0][0], &room_world_extension[1][0],
    &room_world_extension[2][0], &room_world_extension[3][0],
    &room_world_extension[4][0], &room_world_extension[5][0],
    &room_world_extension[6][0], &room_world_extension[7][0],
    &room_world_extension[8][0], &room_world_extension[9][0],
    &room_world_extension[10][0], &room_world_extension[11][0],
    &room_world_extension[12][0], &room_world_extension[13][0],
    &room_world_extension[14][0], &room_world_extension[15][0],
    &room_world_extension[16][0]
};

static u8 *cell_ptr(u8 x, u8 y) {
    if (y < ROOM_H && x >= ROOM_W) return rw_row_hi[y] + (u8)(x - ROOM_W);
    return rw_row_lo[y] + x;
}

static u8 at(u8 x, u8 y) {
    if (x >= ROOM_WIDE_W_TILES || y >= ROOM_WIDE_H_TILES) return 0xFF;
    return *cell_ptr(x, y);
}

static void put(u8 x, u8 y, u8 t) {
    *cell_ptr(x, y) = t;
}

static u8 pin_tile(u8 t) {
    return (t >= BGT_GATE_BOULDER && t <= BGT_GATE_VENT) || t == BGT_PORTAL;
}

// A cell beside a gate or portal keeps its silhouette: it may be the wall
// that makes the gate the only way through.
static u8 pinned(u8 x, u8 y) {
    // The Riftwell trader's counter: the seed-stable grove cell at (16, 4)
    // stops a player walking up the keeper column within talking range.
    if (run_state.world_screen == RIFTWELL_WORLD_SCREEN && x == 16 && y == 4)
        return 1;
    return pin_tile(at((u8)(x + 1), y)) || pin_tile(at((u8)(x - 1), y))
        || pin_tile(at(x, (u8)(y + 1))) || pin_tile(at(x, (u8)(y - 1)));
}

// Within one row segment consecutive x are consecutive bytes, so the
// scans below walk pointers.
static u8 rw_base;
#define WOODY(t) ((t) == BGT_TREE || (t) == BGT_WILD_MOUNTAIN)

// Incomplete interior tree/crag blocks erode back to ground.
static void erode_block(u8 bx, u8 by) {
    u8 i, nt = 0, nc = 0, t, x, y;
    u8 *p0 = cell_ptr(bx, by), *p1 = cell_ptr(bx, (u8)(by + 1));
    // bx is even and the segment split is at x = 20, so p[0], p[1] share
    // a segment.
    for (i = 0; i < 2; ++i) {
        t = p0[i]; if (t == BGT_TREE) nt++; else if (t == BGT_WILD_MOUNTAIN) nc++;
        t = p1[i]; if (t == BGT_TREE) nt++; else if (t == BGT_WILD_MOUNTAIN) nc++;
    }
    if ((!nt || nt == 4) && (!nc || nc == 4)) return;
    for (i = 0; i < 4; ++i) {
        x = (u8)(bx + (i & 1));
        y = (u8)(by + (i >> 1));
        t = at(x, y);
        if (((t == BGT_TREE && nt != 4) || (t == BGT_WILD_MOUNTAIN && nc != 4))
            && !pinned(x, y)) put(x, y, rw_base);
    }
}

static void erode_blocks(void) {
    u8 bx, by, *p0, *p1;
    // Interior blocks only (x/y 2..29); rim blocks keep the boundary wall.
    // Walk row pointers two cells at a time (the 20/11 segment split falls
    // on an even x) and only stop at blocks that hold a tree or crag.
    for (by = 2; by <= 28; by += 2) {
        p0 = cell_ptr(2, by);
        p1 = cell_ptr(2, (u8)(by + 1));
        for (bx = 2; bx <= 28; bx += 2, p0 += 2, p1 += 2) {
            if (bx == ROOM_W) {
                if (by < ROOM_H) p0 = rw_row_hi[by];
                if ((u8)(by + 1) < ROOM_H) p1 = rw_row_hi[(u8)(by + 1)];
            }
            if (!WOODY(p0[0]) && !WOODY(p0[1]) && !WOODY(p1[0])
                && !WOODY(p1[1])) continue;
            erode_block(bx, by);
        }
    }
}

void riftwild_tidy_field(u8 base) BANKED {
    rw_base = base;
    erode_blocks();
}

void riftwild_meta_scan(void) BANKED {
    u8 bx, by, x, t, *p0, *p1, bit, *out;
    for (bx = 0; bx < RW_BLOCK_BYTES; ++bx) rw_block_ok[bx] = 0;
    // Blocks 0..14 on each axis; block 15 (x/y 30, 31) is never whole.
    for (by = 0; by < 15; ++by) {
        out = &rw_block_ok[(u8)(by << 1)];
        bit = 1;
        p0 = cell_ptr(0, (u8)(by << 1));
        p1 = cell_ptr(0, (u8)((by << 1) + 1));
        for (bx = 0, x = 0; bx < 15; ++bx, x += 2, p0 += 2, p1 += 2) {
            if (x == ROOM_W) {   // rows above 17 continue in the extension
                if ((u8)(by << 1) < ROOM_H)
                    p0 = rw_row_hi[(u8)(by << 1)];
                if ((u8)((by << 1) + 1) < ROOM_H)
                    p1 = rw_row_hi[(u8)((by << 1) + 1)];
            }
            if (bx == 8) { ++out; bit = 1; }
            t = p0[0];
            if ((t == BGT_TREE || t == BGT_WILD_MOUNTAIN)
                && p0[1] == t && p1[0] == t && p1[1] == t) *out |= bit;
            bit <<= 1;
        }
    }
}

void riftwild_seam_step(u8 step, u8 dir) BANKED {
    if (!run_state.world_mode) return;
    if (!step) riftwild_meta_scan();
    else if (step == 8 && (dir == DIR_N || dir == DIR_S))
        riftwild_load_world_palettes(0);
}

// Hollow shorelines choke with dead reeds. A water cell turns to reeds only
// when exactly one side is land and two open-water cells lie behind it, so
// the fringe reads as one coherent ring and swimmable channels never thin
// below two tiles (the old water/reed checkerboard drew a cut corner on
// every cell and could wall off a river).
#define WET(t) ((t) == BGT_WILD_WATER || (t) == BGT_WILD_REEDS)

static u8 deep(u8 x, u8 y, i8 dx, i8 dy) {
    return at((u8)(x + dx), (u8)(y + dy)) == BGT_WILD_WATER
        && at((u8)(x + dx + dx), (u8)(y + dy + dy)) == BGT_WILD_WATER;
}

static void reed_cell(u8 x, u8 y) {
    u8 t, n, s, w, e;
    t = at(x, (u8)(y - 1)); n = WET(t);
    t = at(x, (u8)(y + 1)); s = WET(t);
    t = at((u8)(x - 1), y); w = WET(t);
    t = at((u8)(x + 1), y); e = WET(t);
    if ((u8)(n + s + w + e) != 3) return;
    if (!n ? deep(x, y, 0, 1) : !s ? deep(x, y, 0, -1)
        : !w ? deep(x, y, 1, 0) : deep(x, y, -1, 0))
        put(x, y, BGT_WILD_REEDS);
}

void riftwild_hollow_reeds(void) BANKED {
    u8 x, y, *p;
    for (y = 1; y < ROOM_WIDE_H_TILES - 1; ++y) {
        p = cell_ptr(1, y);
        for (x = 1; x < ROOM_WIDE_W_TILES - 1; ++x, ++p) {
            if (x == ROOM_W && y < ROOM_H) p = rw_row_hi[y];
            if (*p == BGT_WILD_WATER) reed_cell(x, y);
        }
    }
}
