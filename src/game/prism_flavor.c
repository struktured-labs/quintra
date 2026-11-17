#pragma bank 20
// Cold placement for the Prism Toggle court. Kept out of bank 19 so the
// live chamber code (prepare, strike, tick, inmate pen) still fits.
#include <gb/gb.h>

#include "content.h"
#include "game/dungeon_director.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/prism_toggle.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

// Goal-pocket flood scratch. Kept off the stack: a 132-byte local would
// blow the Game Boy call stack during room prepare.
static u8 prism_marked[PRISM_H][PRISM_W];

static u8 prism_inmate_ok(u8 id) {
    return (u8)(id == ENEMY_BLUE_CRAWLER
        || id == ENEMY_SKELETON
        || id == ENEMY_ORC
        || id == ENEMY_ROPE
        || id == ENEMY_SHARD_CRAB
        || id == ENEMY_BOG_TOAD
        || id == ENEMY_ECHO_GUARD);
}

static u8 prism_is_pocket_floor(u8 lx, u8 ly) {
    u8 cls, tile;
    if (lx >= PRISM_W || ly >= PRISM_H) return 0;
    cls = prism_class[ly][lx];
    tile = room_tilemap[(u8)(PRISM_Y0 + ly)][(u8)(PRISM_X0 + lx)];
    if (tile == BGT_WALL || tile == BGT_PILLAR) return 0;
    if (cls == PRISM_CLASS_ORB || cls == PRISM_CLASS_AMBER
        || cls == PRISM_CLASS_AZURE) return 0;
    return 1;
}

static void prism_mark_goal_pocket(void) {
    u8 x, y, changed, lx, ly;
    for (y = 0; y < PRISM_H; ++y)
        for (x = 0; x < PRISM_W; ++x)
            prism_marked[y][x] = (u8)(prism_class[y][x] == PRISM_CLASS_GOAL);
    changed = 1;
    while (changed) {
        changed = 0;
        for (y = 0; y < PRISM_H; ++y) {
            for (x = 0; x < PRISM_W; ++x) {
                if (!prism_marked[y][x]) continue;
                if (x && prism_is_pocket_floor((u8)(x - 1), y)
                    && !prism_marked[y][x - 1]) {
                    prism_marked[y][x - 1] = 1; changed = 1;
                }
                if ((u8)(x + 1) < PRISM_W && prism_is_pocket_floor((u8)(x + 1), y)
                    && !prism_marked[y][x + 1]) {
                    prism_marked[y][x + 1] = 1; changed = 1;
                }
                if (y && prism_is_pocket_floor(x, (u8)(y - 1))
                    && !prism_marked[y - 1][x]) {
                    prism_marked[y - 1][x] = 1; changed = 1;
                }
                if ((u8)(y + 1) < PRISM_H && prism_is_pocket_floor(x, (u8)(y + 1))
                    && !prism_marked[y + 1][x]) {
                    prism_marked[y + 1][x] = 1; changed = 1;
                }
            }
        }
    }
    prism_pocket_x0 = 0xFF;
    prism_pocket_x1 = 0;
    prism_pocket_y0 = 0xFF;
    prism_pocket_y1 = 0;
    prism_inmate_tx = 0xFF;
    prism_inmate_ty = 0xFF;
    for (y = 0; y < PRISM_H; ++y) {
        for (x = 0; x < PRISM_W; ++x) {
            if (!prism_marked[y][x]) continue;
            lx = (u8)(PRISM_X0 + x);
            ly = (u8)(PRISM_Y0 + y);
            if (lx < prism_pocket_x0) prism_pocket_x0 = lx;
            if (lx > prism_pocket_x1) prism_pocket_x1 = lx;
            if (ly < prism_pocket_y0) prism_pocket_y0 = ly;
            if (ly > prism_pocket_y1) prism_pocket_y1 = ly;
        }
    }
    // Prefer a 2x2 of non-goal floor so a 16px body stays off the seal.
    // Tight tier-2 pockets are only one floor tile around a 2x2 gold plate;
    // fall back to the non-goal floor cell farthest from every seal tile.
    for (y = 0; y + 1 < PRISM_H; ++y) {
        for (x = 0; x + 1 < PRISM_W; ++x) {
            if (!prism_marked[y][x] || !prism_marked[y][x + 1]
                || !prism_marked[y + 1][x] || !prism_marked[y + 1][x + 1]) continue;
            if (prism_class[y][x] == PRISM_CLASS_GOAL
                || prism_class[y][x + 1] == PRISM_CLASS_GOAL
                || prism_class[y + 1][x] == PRISM_CLASS_GOAL
                || prism_class[y + 1][x + 1] == PRISM_CLASS_GOAL)
                continue;
            prism_inmate_tx = (u8)(PRISM_X0 + x);
            prism_inmate_ty = (u8)(PRISM_Y0 + y);
            return;
        }
    }
    {
        u8 best = 0;
        for (y = 0; y < PRISM_H; ++y) {
            for (x = 0; x < PRISM_W; ++x) {
                u8 gy, gx, d, min_d;
                if (!prism_marked[y][x]) continue;
                if (prism_class[y][x] == PRISM_CLASS_GOAL) continue;
                min_d = 0xFF;
                for (gy = 0; gy < PRISM_H; ++gy) {
                    for (gx = 0; gx < PRISM_W; ++gx) {
                        u8 dx, dy;
                        if (prism_class[gy][gx] != PRISM_CLASS_GOAL) continue;
                        dx = (gx > x) ? (u8)(gx - x) : (u8)(x - gx);
                        dy = (gy > y) ? (u8)(gy - y) : (u8)(y - gy);
                        d = (u8)(dx + dy);
                        if (d < min_d) min_d = d;
                    }
                }
                if (min_d > best) {
                    best = min_d;
                    prism_inmate_tx = (u8)(PRISM_X0 + x);
                    prism_inmate_ty = (u8)(PRISM_Y0 + y);
                }
            }
        }
    }
}

static u8 prism_body_in_chamber(u8 idx) {
    i16 x, y;
    u8 x0, y0, x1, y1;
    x = FIX8_TO_INT(entities[idx].x);
    y = FIX8_TO_INT(entities[idx].y);
    x0 = (u8)(x >> 3); y0 = (u8)(y >> 3);
    x1 = (u8)((x + 15) >> 3); y1 = (u8)((y + 15) >> 3);
    if (x1 < PRISM_X0 || x0 > (u8)(PRISM_X0 + PRISM_W - 1)) return 0;
    if (y1 < PRISM_Y0 || y0 > (u8)(PRISM_Y0 + PRISM_H - 1)) return 0;
    return 1;
}

static u8 prism_floor_2x2(u8 tx, u8 ty) {
    u8 x, y, t;
    if ((u8)(tx + 1) >= ROOM_W || (u8)(ty + 1) >= ROOM_H) return 0;
    for (y = ty; y <= (u8)(ty + 1); ++y) {
        for (x = tx; x <= (u8)(tx + 1); ++x) {
            t = room_tilemap[y][x];
            if (t != BGT_FLOOR && t != BGT_FLOOR2 && t != BGT_FLOOR3
                && t != BGT_GRASS && t != BGT_PATH)
                return 0;
        }
    }
    return 1;
}

static u8 prism_site_free(u8 tx, u8 ty) {
    i16 px = (i16)tx * 8, py = (i16)ty * 8;
    i16 dx, dy;
    u8 i;
    dx = (i16)(px - player.x); if (dx < 0) dx = (i16)-dx;
    dy = (i16)(py - player.y); if (dy < 0) dy = (i16)-dy;
    if (dx < 24 && dy < 24) return 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 ex, ey;
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_ENEMY) continue;
        ex = FIX8_TO_INT(entities[i].x);
        ey = FIX8_TO_INT(entities[i].y);
        dx = (i16)(ex - px); if (dx < 0) dx = (i16)-dx;
        dy = (i16)(ey - py); if (dy < 0) dy = (i16)-dy;
        if (dx < 16 && dy < 16) return 0;
    }
    return 1;
}

static u8 prism_pick_inmate(void) {
    u8 n, id;
    for (n = 0; n < 8; ++n) {
        id = dungeon_director_pick_stage_enemy(run_state.bosses_beaten);
        if (prism_inmate_ok(id)) return id;
    }
    return ENEMY_BLUE_CRAWLER;
}

void prism_place_flavor_guards(void) BANKED {
    static const u8 ring_x[12] = {
        1, 8, 17, 1, 17, 1, 17, 1, 8, 17, 4, 14
    };
    static const u8 ring_y[12] = {
        1, 1, 1, 7, 7, 10, 10, 14, 14, 14, 1, 14
    };
    u8 i, ring, target, start, tries, idx, tx, ty, id, ordinal;
    prism_inmate_idx = 0xFF;
    prism_mark_goal_pocket();
    // Remove procgen bodies that landed inside the carved chamber so they
    // cannot occupy an orb pocket or sit under a wall. entity_kill keeps
    // entity_enemy_count honest (the old flags=0 path did not).
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_ENEMY) continue;
        if (prism_body_in_chamber(i)) entity_kill(i);
    }
    if (prism_inmate_tx != 0xFF) {
        id = prism_pick_inmate();
        idx = enemy_spawn(id, prism_inmate_tx, prism_inmate_ty);
        if (idx != 0xFF) {
            dungeon_director_configure_initial(idx, 0);
            prism_inmate_idx = idx;
        }
    }
    ring = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_ENEMY) continue;
        if (i == prism_inmate_idx) continue;
        if (!prism_body_in_chamber(i)) ring++;
    }
    // Intended puzzle-room band was 3/4 (+1 from Stage 4). The chamber carve
    // used to cull most of that pack. Restore a slightly denser apron and
    // keep the inmate extra.
    target = (u8)((RUN_IS_EASY() ? 4 : 5)
        + (run_state.bosses_beaten >= 3 ? 1 : 0));
    start = (u8)((u8)run_state.run_seed
        + run_state.room_counter
        + (u8)(run_state.bosses_beaten << 1));
    while (start >= 12) start = (u8)(start - 12);
    tries = 0;
    ordinal = ring;
    while (ring < target && tries < 12) {
        tx = ring_x[(u8)(start + tries) % 12];
        ty = ring_y[(u8)(start + tries) % 12];
        tries++;
        if (!prism_floor_2x2(tx, ty) || !prism_site_free(tx, ty)) continue;
        id = dungeon_director_pick_stage_enemy(run_state.bosses_beaten);
        idx = enemy_spawn(id, tx, ty);
        if (idx == 0xFF) continue;
        dungeon_director_configure_initial(idx, ordinal);
        ordinal++;
        ring++;
    }
}

