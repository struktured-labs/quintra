#pragma bank 255
// Prism Toggle: Oracle / Link's Awakening style crystal-switch chamber.
// Spec: docs/superpowers/specs/2026-11-15-puzzle-variety-and-dungeon-wide-puzzles.md
// (Section 3.2 and the "Batch 1 implementation" addendum).
//
// The chamber templates below are the single source of truth: the Rust
// mirror (tools/crates/quintra-procgen/src/prism_toggle.rs) parses this file
// between the PRISM-TEMPLATES markers and proves every variant solvable with
// base movement + melee, at least two strikes, and softlock-free even when
// shots or bombs flip the orbs from range.
//
// Legend: '#' wall, '.' floor, 'a' amber barrier, 'b' azure barrier,
// 'o' prism orb, 'G' goal seal. The compact court around the chamber is
// cleared to an open ring that touches every doorway. Amber starts raised.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/prism_toggle.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/sun_lattice.h"
#include "render/tiles.h"

#define PRISM_TEMPLATE_COUNT 5
#define PRISM_PENDING 6
#define PRISM_STRIKE_COOLDOWN 20

// PRISM-TEMPLATES-BEGIN
static const char prism_templates[PRISM_TEMPLATE_COUNT][PRISM_H][PRISM_W + 1] = {
    /* tier 0 : ring orb, one inner gate */
    {
        "############",
        "a....#.....#",
        "a....#.....#",
        "#....#.....#",
        "#....b..GG.#",
        "#....b..GG.#",
        "#....#.....#",
        "#....#.....#",
        "o....#.....#",
        "#....#.....#",
        "############",
    },
    /* tier 1 : left spine, two chambers on the right */
    {
        "############",
        "a...#.o....#",
        "a...#......#",
        "#...b......#",
        "#...b......#",
        "#...#####aa#",
        "#...#......#",
        "#...#..GG..#",
        "o...#..GG..#",
        "#...#......#",
        "############",
    },
    /* tier 1 : right spine, seal above the lower chamber */
    {
        "############",
        "#......#...#",
        "#..GG..#...o",
        "#..GG..#...#",
        "#......#...#",
        "###aa###...#",
        "#......b...#",
        "#......b...#",
        "#......#...a",
        "#o.....#...a",
        "############",
    },
    /* tier 2 : four chambers, four strikes */
    {
        "############",
        "a....#.....#",
        "a....#..o..#",
        "#....b.....#",
        "o....b.....#",
        "#######aa###",
        "#....#.....#",
        "#.GG.#.....#",
        "#.GG.b..o..#",
        "#....b.....#",
        "############",
    },
    /* tier 2 : four chambers, entrance from below */
    {
        "############",
        "#....b.....#",
        "#.GG.b..o..#",
        "#.GG.#.....#",
        "#....#.....#",
        "#######aa###",
        "o....#.....#",
        "#....b.....#",
        "a....b..o..#",
        "a....#.....#",
        "############",
    },
};
static const u8 prism_template_tier[PRISM_TEMPLATE_COUNT] = { 0, 1, 1, 2, 2 };
// PRISM-TEMPLATES-END

u8 prism_class[PRISM_H][PRISM_W];
u8 prism_raised;
static u8 prism_cooldown;
static u8 prism_pending_n;
static u8 prism_pending_x[PRISM_PENDING];
static u8 prism_pending_y[PRISM_PENDING];

static u8 prism_tier(u8 bosses_beaten) {
    if (bosses_beaten == 0) return 0;
    return (bosses_beaten <= 2) ? 1 : 2;
}

static void prism_put(u8 x, u8 y, u8 tile, u8 attr) {
    room_tilemap[y][x] = tile;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

// Generous full-sprite box: never raise a barrier into any visible part of
// the champion. The tile stays lowered until the hero has stepped clear.
static u8 prism_under_player(u8 x, u8 y) {
    i16 l = (i16)((i16)x << 3), t = (i16)((i16)y << 3);
    return ((i16)(player.x + 14) > l && (i16)(player.x + 1) < (i16)(l + 8)
        && (i16)(player.y + 16) > t && (i16)player.y < (i16)(t + 8)) ? 1 : 0;
}

static u8 prism_barrier_colour(u8 cls) {
    return (cls == PRISM_CLASS_AMBER) ? 0 : 1;
}

void prism_prepare(u32 seed, u8 bosses_beaten, u8 solved) BANKED {
    u8 tier = prism_tier(bosses_beaten);
    u8 ids[PRISM_TEMPLATE_COUNT];
    u8 count = 0, i, x, y, pick, mirror, swap;
    for (i = 0; i < PRISM_TEMPLATE_COUNT; ++i)
        if (prism_template_tier[i] == tier) ids[count++] = i;
    pick = ids[(u8)(seed >> 8) % count];
    mirror = (seed & 0x10) ? 1 : 0;
    swap = (seed & 0x20) ? 1 : 0;
    prism_raised = swap;
    prism_cooldown = 0;
    prism_pending_n = 0;
    // An open ring touches every compact doorway; in wide courts the ring's
    // east column and south row meet the streamed terrain beyond x=19/y=16.
    for (y = 1; y < ROOM_H - 1; ++y)
        for (x = 1; x < ROOM_W - 1; ++x)
            room_tilemap[y][x] = BGT_FLOOR;
    for (y = 0; y < PRISM_H; ++y) {
        for (x = 0; x < PRISM_W; ++x) {
            char ch = prism_templates[pick][y][mirror ? (PRISM_W - 1 - x) : x];
            u8 cls = PRISM_CLASS_NONE;
            u8 tile = BGT_FLOOR;
            if (ch == '#') tile = BGT_WALL;
            else if (ch == 'o') { cls = PRISM_CLASS_ORB; tile = BGT_CRYSTAL; }
            else if (ch == 'G') { cls = PRISM_CLASS_GOAL; tile = BGT_FLOOR3; }
            else if (ch == 'a' || ch == 'b') {
                u8 colour = (u8)(((ch == 'b') ? 1 : 0) ^ swap);
                cls = colour ? PRISM_CLASS_AZURE : PRISM_CLASS_AMBER;
                tile = (!solved && colour == prism_raised)
                    ? BGT_PILLAR : BGT_FLOOR2;
            }
            prism_class[y][x] = cls;
            room_tilemap[(u8)(PRISM_Y0 + y)][(u8)(PRISM_X0 + x)] = tile;
        }
    }
    // Guards remain in the open ring; any body generated inside the chamber
    // would be sealed in a pocket or a raised barrier.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY) {
            u8 ex = (u8)((FIX8_TO_INT(entities[i].x) + 8) >> 3);
            u8 ey = (u8)((FIX8_TO_INT(entities[i].y) + 8) >> 3);
            if (ex + 1 >= PRISM_X0 && ex <= PRISM_X0 + PRISM_W
                && ey + 1 >= PRISM_Y0 && ey <= PRISM_Y0 + PRISM_H)
                entities[i].flags = 0;
        }
    }
}

static void prism_paint_barriers(u8 open_all) {
    u8 x, y;
    prism_pending_n = 0;
    for (y = 0; y < PRISM_H; ++y) {
        for (x = 0; x < PRISM_W; ++x) {
            u8 cls = prism_class[y][x];
            u8 tx = (u8)(PRISM_X0 + x), ty = (u8)(PRISM_Y0 + y);
            u8 want;
            if (cls == PRISM_CLASS_ORB) {
                prism_put(tx, ty, BGT_CRYSTAL,
                    prism_raised ? BGPAL_CRYSTAL : BGPAL_CRACK);
                continue;
            }
            if (cls != PRISM_CLASS_AMBER && cls != PRISM_CLASS_AZURE) continue;
            want = (!open_all && prism_barrier_colour(cls) == prism_raised)
                ? BGT_PILLAR : BGT_FLOOR2;
            if (want == BGT_PILLAR && prism_under_player(tx, ty)) {
                if (prism_pending_n < PRISM_PENDING) {
                    prism_pending_x[prism_pending_n] = tx;
                    prism_pending_y[prism_pending_n] = ty;
                    prism_pending_n++;
                }
                want = BGT_FLOOR2;
            }
            if (room_tilemap[ty][tx] != want)
                prism_put(tx, ty, want,
                    (cls == PRISM_CLASS_AMBER) ? BGPAL_CRACK : BGPAL_CRYSTAL);
        }
    }
}

u8 prism_strike(u8 tx, u8 ty) BANKED {
    if (!PRISM_IS_ORB(tx, ty)) return 0;
    if (!room_puzzle_locked || prism_cooldown) return 1;
    prism_cooldown = PRISM_STRIKE_COOLDOWN;
    prism_raised ^= 1;
    prism_paint_barriers(0);
    sfx_play_rune(prism_raised ? 4 : 0);
    room_shake(1, 4);
    return 1;
}

void prism_shot_tile(u8 t, u8 tx, u8 ty) BANKED {
    if (t == BGT_PILLAR) sun_lattice_strike(tx, ty);
    else if (t == BGT_CRYSTAL && room_puzzle_kind == PUZZLE_PRISM_TOGGLE)
        prism_strike(tx, ty);
}

u8 prism_tick(void) BANKED {
    u8 i, fx, fy;
    if (prism_cooldown) prism_cooldown--;
    for (i = 0; i < prism_pending_n; ++i) {
        u8 tx = prism_pending_x[i], ty = prism_pending_y[i];
        u8 cls = PRISM_CLASS(tx, ty);
        if (prism_under_player(tx, ty)) continue;
        if (room_puzzle_locked && prism_barrier_colour(cls) == prism_raised)
            prism_put(tx, ty, BGT_PILLAR,
                (cls == PRISM_CLASS_AMBER) ? BGPAL_CRACK : BGPAL_CRYSTAL);
        prism_pending_x[i] = prism_pending_x[prism_pending_n - 1];
        prism_pending_y[i] = prism_pending_y[prism_pending_n - 1];
        prism_pending_n--;
        break;   // one live tile per frame
    }
    if (!room_puzzle_locked) return 0;
    fx = (u8)((player.x + 8) >> 3);
    fy = (u8)((player.y + 12) >> 3);
    if (PRISM_CLASS(fx, fy) != PRISM_CLASS_GOAL) return 0;
    // The seal opens the whole chamber so the way back is never in doubt.
    prism_paint_barriers(1);
    prism_pending_n = 0;
    return 1;
}
