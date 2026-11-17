#pragma bank 255
// Riftwild tile tidy pass (docs/superpowers/specs/2026-11-17-riftwild-tile-tidy.md).
//
// Two jobs, both deterministic and RNG-free:
//  * riftwild_tidy_field(): ordinary fields only, before the set piece and
//    scatter. Trees and crags render as 2x2 canopies/peaks, so any tree or
//    crag cell that is not part of a complete aligned 2x2 block used to draw
//    a lone quarter (half a crown, a cut ridge). Erode those cells back to
//    the field's ground, and prune one-tile water/sinkhole tips and
//    channels the shoreline set cannot draw. Removing solid cells only ever
//    widens routes; capability gates and portals pin their neighbours.
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

static u8 at(u8 x, u8 y) {
    if (x >= ROOM_WIDE_W_TILES || y >= ROOM_WIDE_H_TILES) return 0xFF;
    if (y < ROOM_H) {
        if (x < ROOM_W) return room_tilemap[y][x];
        return room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

static void put(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][x - ROOM_W] = t;
    } else room_world_bottom[y - ROOM_H][x] = t;
}

static u8 pin_tile(u8 t) {
    return (t >= BGT_GATE_BOULDER && t <= BGT_GATE_VENT) || t == BGT_PORTAL;
}

// A cell beside a gate or portal keeps its silhouette: it may be the wall
// that makes the gate the only way through.
static u8 pinned(u8 x, u8 y) {
    return pin_tile(at((u8)(x + 1), y)) || pin_tile(at((u8)(x - 1), y))
        || pin_tile(at(x, (u8)(y + 1))) || pin_tile(at(x, (u8)(y - 1)));
}

static void erode_blocks(u8 kind, u8 base) {
    u8 bx, by, i, n;
    // Interior blocks only (x/y 2..29); rim blocks keep the boundary wall.
    for (by = 2; by <= 28; by += 2) {
        for (bx = 2; bx <= 28; bx += 2) {
            n = 0;
            for (i = 0; i < 4; ++i)
                if (at((u8)(bx + (i & 1)), (u8)(by + (i >> 1))) == kind) n++;
            if (!n || n == 4) continue;
            for (i = 0; i < 4; ++i) {
                u8 x = (u8)(bx + (i & 1)), y = (u8)(by + (i >> 1));
                if (at(x, y) == kind && !pinned(x, y)) put(x, y, base);
            }
        }
    }
}

static void prune_bodies(u8 body, u8 base) {
    u8 x, y, pass;
    for (pass = 0; pass < 2; ++pass) {
        for (y = 1; y < ROOM_WIDE_H_TILES - 1; ++y) {
            for (x = 1; x < ROOM_WIDE_W_TILES - 1; ++x) {
                u8 n, s, w, e;
                if (at(x, y) != body) continue;
                n = at(x, (u8)(y - 1)) != body;
                s = at(x, (u8)(y + 1)) != body;
                w = at((u8)(x - 1), y) != body;
                e = at((u8)(x + 1), y) != body;
                if ((u8)(n + s + w + e) >= 3 || (n && s) || (w && e))
                    if (!pinned(x, y)) put(x, y, base);
            }
        }
    }
}

void riftwild_tidy_field(u8 base) BANKED {
    erode_blocks(BGT_TREE, base);
    erode_blocks(BGT_WILD_MOUNTAIN, base);
    prune_bodies(BGT_WILD_WATER, base);
    prune_bodies(BGT_WILD_HOLE, base);
}

void riftwild_meta_scan(void) BANKED {
    u8 bx, by;
    for (bx = 0; bx < RW_BLOCK_BYTES; ++bx) rw_block_ok[bx] = 0;
    // Blocks 0..14 on each axis; block 15 (x/y 30, 31) is never whole.
    for (by = 0; by < 15; ++by) {
        u8 y = (u8)(by << 1);
        for (bx = 0; bx < 15; ++bx) {
            u8 x = (u8)(bx << 1);
            u8 t = at(x, y);
            if (t != BGT_TREE && t != BGT_WILD_MOUNTAIN) continue;
            if (at((u8)(x + 1), y) != t || at(x, (u8)(y + 1)) != t
                || at((u8)(x + 1), (u8)(y + 1)) != t) continue;
            rw_block_ok[(u8)(by << 1) + (bx >> 3)] |= (u8)(1u << (bx & 7));
        }
    }
}

void riftwild_seam_step(u8 step, u8 dir) BANKED {
    if (!run_state.world_mode) return;
    if (!step) riftwild_meta_scan();
    else if (step == 8 && (dir == DIR_N || dir == DIR_S))
        riftwild_load_world_palettes(0);
}
