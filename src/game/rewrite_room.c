#pragma bank 26
// Pinned in bank 26 (cold bank 30 is full with the M1 chamber + art).
// M2 Cairn Ford: material rewrite switches (spec section 6.1 / M2).
#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/enemy_new_ai.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/rewrite_room.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/rewrite_art.h"
#include "render/tiles.h"
#include "content.h"

u8 rw_live;
u8 rw_a, rw_b;
u8 rw_resets;
u8 rw_blink;
u8 rw_offcam_sfx;
u8 rw_refusals;
static u8 rw_queue;             // regions still to paint (one per frame)
static u8 rw_flash;             // region currently blinking (bit) and timer
static u8 rw_flash_t;
static u8 rw_cool;              // debounce after any toggle
static u8 rw_on_a, rw_on_a2, rw_on_b, rw_on_reset, rw_on_goal;
static u8 rw_obj_ok;
static u8 rw_epoch;
static u8 rw_cue;               // off-camera cue already played this press
static u8 rw_frame;

#define WX(lx) ((u8)(RW_X0 + (lx)))
#define WY(ly) ((u8)(RW_Y0 + (ly)))
#define PX(lx) ((u8)(WX(lx) << 3))
#define PY(ly) ((u8)(WY(ly) << 3))

// '#' wall, '.' floor, 'G' goal plate, 'R' preview cairn (TL of 2x2),
// 'W' preview ford, 'C' chasm bed, 'F' sill bed, '-' rest of a 2x2.
static const char rw_layout[RW_H][RW_W + 1] = {
    "############",
    "#.....##...#",   // reset plate (3,1), Switch B (9,1) drawn as OBJ
    "#.....##...#",
    "#.....##...#",
    "#.....FF...#",   // Switch A (1,4); sill bed F1 (6..7, 4..5)
    "#.....FF...#",
    "......##...#",   // entrance rows 6..7; twin Switch A (9,6)
    "......##...#",
    "#R-.WW##...#",   // previews: cairn (1,8), ford (4,8)
    "#--.WW##...#",
    "#########CC#",   // chasm bed C1 (9..10, 10..11)
    "#########CC#",
    "#..........#",   // hall
    "#..........#",
    "#####CC#####",   // chasm bed C2 (5..6, 14..15), off-camera from foyer
    "#####CC#####",
    "#..........#",   // vault
    "#...GG.....#",
    "#..........#",
    "############",
};

static const u8 reg_x[RW_REGIONS] = { 6, 9, 5 };
static const u8 reg_y[RW_REGIONS] = { 4, 10, 14 };
static const u8 reg_bed[RW_REGIONS] = { RW_T_SILL, RW_T_CHASM, RW_T_CHASM };

static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

// Palette encodes passability, one meaning each: ford and sill use the
// floor ramp (walk on it), cairn and chasm the wall ramp (blocked). Never
// the stage crystal (reads as lava in Ember Depths) or the amber "secret".
// BG slots 5..7 belong to the HUD lanes, so no private slot is claimed.
static u8 tile_attr(u8 t) {
    if (t == RW_T_FORD) return BGPAL_FLOOR;
    if (t == RW_T_CHASM) return BGPAL_WALL;
    if (t == RW_T_SILL) return BGPAL_FLOOR;
    return BGPAL_WALL;
}

static void cairn_tiles(u8 *t) {
    t[0] = RW_T_CAIRN_TL; t[1] = RW_T_CAIRN_TR;
    t[2] = RW_T_CAIRN_BL; t[3] = RW_T_CAIRN_BR;
}

static void region_tiles(u8 r, u8 *t) {
    u8 m;
    if (rw_a && !rw_b) { cairn_tiles(t); return; }
    m = rw_a ? RW_T_FORD : reg_bed[r];
    t[0] = t[1] = t[2] = t[3] = m;
}

// Write one 2x2 block (world arrays + BG map + attributes); caller syncs.
static void block_put(u8 x, u8 y, const u8 *t, u8 flash) {
    u8 a[4], i;
    for (i = 0; i < 4; ++i) a[i] = flash ? BGPAL_DOOR : tile_attr(t[i]);
    wset(x, y, t[0]); wset((u8)(x + 1), y, t[1]);
    wset(x, (u8)(y + 1), t[2]); wset((u8)(x + 1), (u8)(y + 1), t[3]);
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 2, 2, t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 2, 2, a);
    VBK_REG = 0;
}

// Paint one 2x2 region in one vblank.
static void region_paint(u8 r, u8 flash) {
    u8 t[4];
    region_tiles(r, t);
    wait_vbl_done();
    block_put(WX(reg_x[r]), WY(reg_y[r]), t, flash);
}

// Re-dress after any dungeon BG reload: palette, both previews, all regions
// in their current state (no cue: nothing changed, the art just came back).
static void redress(void) {
    u8 t[4], r;
    wait_vbl_done();
    cairn_tiles(t);
    block_put(WX(1), WY(8), t, 0);
    t[0] = t[1] = t[2] = t[3] = RW_T_FORD;
    block_put(WX(4), WY(8), t, 0);
    rw_flash = rw_flash_t = 0;
    for (r = 0; r < RW_REGIONS; ++r) {
        region_tiles(r, t);
        wait_vbl_done();
        block_put(WX(reg_x[r]), WY(reg_y[r]), t, 0);
    }
}

static u8 region_in_view(u8 r) {
    u8 cx = (u8)(room_camera_x >> 3), cy = (u8)(room_camera_y >> 3);
    u8 x = WX(reg_x[r]), y = WY(reg_y[r]);
    // 20x18 tiles on screen; the bottom HUD row hides one more.
    return ((u8)(x + 2) > cx && x < (u8)(cx + 20)
        && (u8)(y + 2) > cy && y < (u8)(cy + 17)) ? 1 : 0;
}

static u8 body_hits(u8 bx, u8 by, u8 w, u8 h) {
    i16 x0 = (i16)player.x + 2, x1 = (i16)player.x + 14;
    i16 y0 = (i16)player.y + 8, y1 = (i16)player.y + 16;
    if (x1 <= (i16)bx || x0 >= (i16)(bx + w)) return 0;
    if (y1 <= (i16)by || y0 >= (i16)(by + h)) return 0;
    return 1;
}

static u8 hero_in_any_region(void) {
    u8 r;
    for (r = 0; r < RW_REGIONS; ++r)
        if (body_hits(PX(reg_x[r]), PY(reg_y[r]), 16, 16)) return 1;
    return 0;
}

static u8 foot_on(u8 lx, u8 ly) {
    u8 fx = (u8)((player.x + 8) >> 3), fy = (u8)((player.y + 12) >> 3);
    return ((u8)(fx - WX(lx)) < 2 && (u8)(fy - WY(ly)) < 2) ? 1 : 0;
}

static void refuse(void) {
    rw_refusals++;
    sfx_play(SFX_REFUSE);
    rw_cool = 20;
}

static void commit(void) {
    rw_queue = (1 << RW_REGIONS) - 1;
    rw_cue = 0;
    rw_cool = 20;
    sfx_play(SFX_DOOR);
}

static void press_a(void) {
    // A only moves rock: fords must sink back to cairns (B) first.
    if (rw_b) { refuse(); return; }
    // Raising a cairn on a body is refused (never entomb the hero).
    if (!rw_a && hero_in_any_region()) { refuse(); return; }
    rw_a ^= 1;
    commit();
}

static void press_b(void) {
    if (!rw_a) { refuse(); return; }            // dud: no rock to turn
    if (rw_b && hero_in_any_region()) { refuse(); return; }
    rw_b ^= 1;
    commit();
}

// A player shot that crosses a switch plate presses it (and is spent).
static u8 shot_on(u8 lx, u8 ly) {
    u8 i, bx = PX(lx), by = PY(ly);
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 cx, cy;
        if ((e->flags & (EF_ACTIVE | EF_PLAYER_PROJ))
            != (EF_ACTIVE | EF_PLAYER_PROJ) || e->type != ENT_PROJECTILE)
            continue;
        cx = e->x + 4; cy = e->y + 4;
        if (cx < (i16)bx || cx >= (i16)bx + 16) continue;
        if (cy < (i16)by || cy >= (i16)by + 16) continue;
        entity_kill(i);
        return 1;
    }
    return 0;
}

static void evict_enemies(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 cx, cy;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        cx = e->x + 8; cy = e->y + 8;
        if (cx < (i16)puzzle_keep_x0 || cy < (i16)puzzle_keep_y0) continue;
        e->x = (i16)PX(-4);
        e->y = (i16)PY(RW_ENTRY_Y);
    }
}

static u8 in_zone(u8 ex, u8 ey) {
    if (ex >= (u8)(RW_X0 - 4) && ey >= RW_Y0) return 1;
    return (ex >= 11 && ey >= (u8)(WY(RW_ENTRY_Y) - 1)
        && ey <= (u8)(WY(RW_ENTRY_Y) + 2)) ? 1 : 0;
}

u8 rw_prepare(void) BANKED {
    u8 i, x, y;
    rw_live = 0;
    if (!procgen_current_room_is_large || room_world_width < ROOM_WIDE_W_PX
        || room_world_height < ROOM_WIDE_H_PX) return 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 ex, ey;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PICKUP) continue;
        ex = (u8)((e->x + 8) >> 3);
        ey = (u8)((e->y + 8) >> 3);
        if (in_zone(ex, ey)
            && e->ai_data[0] != PICKUP_HEART_HALF
            && e->ai_data[0] != PICKUP_COIN_1
            && e->ai_data[0] != PICKUP_COIN_5
            && e->ai_data[0] != PICKUP_MP) return 0;
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 ex, ey, id;
        if (!(e->flags & EF_ACTIVE)) continue;
        id = e->ai_data[0];
        if (e->type == ENT_ENEMY && (id == ENEMY_LEYBEAM
                || id == ENEMY_SUN_BASILISK || id == ENEMY_NOX_BASILISK)) {
            entity_kill(i);
            continue;
        }
        if (e->type != ENT_ENEMY && e->type != ENT_PICKUP) continue;
        ex = (u8)((e->x + 8) >> 3);
        ey = (u8)((e->y + 8) >> 3);
        if (in_zone(ex, ey)) entity_kill(i);
    }
    rw_a = rw_b = 0;
    for (y = 0; y < RW_H; ++y)
        for (x = 0; x < RW_W; ++x) {
            char c = rw_layout[y][x];
            u8 t = BGT_FLOOR;
            if (c == '#') t = BGT_WALL;
            else if (c == 'W') t = RW_T_FORD;
            else if (c == 'C') t = RW_T_CHASM;
            else if (c == 'F') t = RW_T_SILL;
            else if (c == 'G') t = (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)
                ? BGT_SWITCH_PRESSED : BGT_SWITCH;
            wset(WX(x), WY(y), t);
        }
    // Static preview cairn: the rock the switches make, seen before any use.
    wset(WX(1), WY(8), RW_T_CAIRN_TL); wset(WX(2), WY(8), RW_T_CAIRN_TR);
    wset(WX(1), WY(9), RW_T_CAIRN_BL); wset(WX(2), WY(9), RW_T_CAIRN_BR);
    for (y = (u8)(RW_ENTRY_Y - 1); y <= (u8)(RW_ENTRY_Y + 2); ++y)
        for (x = (u8)(RW_X0 - 4); x < RW_X0; ++x)
            wset(x, WY(y), BGT_FLOOR);
    for (y = RW_ENTRY_Y; y <= (u8)(RW_ENTRY_Y + 1); ++y)
        for (x = 11; x < (u8)(RW_X0 - 4); ++x)
            wset(x, WY(y), BGT_FLOOR);
    rw_queue = rw_blink = rw_flash = rw_flash_t = rw_cool = 0;
    rw_on_a = rw_on_a2 = rw_on_b = rw_on_reset = rw_on_goal = 0;
    rw_resets = rw_offcam_sfx = rw_refusals = 0;
    rw_obj_ok = 0;
    rw_epoch = (u8)(tiles_bg_epoch - 1);
    puzzle_keep_x0 = (u8)((RW_X0 - 1) * 8);
    puzzle_keep_y0 = (u8)(RW_Y0 * 8);
    puzzle_keep_y1 = 0xFF;               // pocket runs to the bottom wall
    puzzle_keep_on = 1;
    puzzle_pack_n = 1;
    rw_live = 1;
    new_monsters_in_room = 1;
    return 1;
}

void rw_reset(void) BANKED {
    if (!rw_live) return;
    player.x = (i16)PX(1);
    player.y = (i16)PY(RW_ENTRY_Y - 1);
    if (player.iframes < 45) player.iframes = 45;
    rw_a = rw_b = 0;
    rw_queue = (1 << RW_REGIONS) - 1;
    rw_cue = 1;                 // a reset is its own cue (portal SFX)
    rw_blink = 0;
    rw_flash = rw_flash_t = 0;
    rw_on_reset = rw_on_a = rw_on_a2 = rw_on_b = 1;
    rw_cool = 20;
    rw_resets++;
    sfx_play(SFX_PORTAL);
    room_shake(1, 10);
}

static void solve(void) {
    u8 t[2] = { BGT_SWITCH_PRESSED, BGT_SWITCH_PRESSED };
    u8 a[2] = { BGPAL_DOOR, BGPAL_DOOR };
    run_state.dungeon_puzzles |= RUN_RIME_SOLVED_BIT;
    wset(WX(RW_GOAL_X), WY(RW_GOAL_Y), BGT_SWITCH_PRESSED);
    wset(WX(RW_GOAL_X + 1), WY(RW_GOAL_Y), BGT_SWITCH_PRESSED);
    wait_vbl_done();
    set_bkg_tiles(ROOM_BG_MAP_X(WX(RW_GOAL_X)), ROOM_BG_MAP_Y(WY(RW_GOAL_Y)), 2, 1, t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(RW_GOAL_X)), ROOM_BG_MAP_Y(WY(RW_GOAL_Y)), 2, 1, a);
    VBK_REG = 0;
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed + rime_cell) % 3),
        player.x, player.y);
}

static void paint_step(void) {
    u8 r;
    for (r = 0; r < RW_REGIONS; ++r) {
        if (!(rw_queue & (1 << r))) continue;
        rw_queue &= (u8)~(1 << r);
        if (rw_flash & (1 << r)) { rw_flash = 0; rw_flash_t = 0; }
        if (!region_in_view(r)) {
            // Off camera: one distinct cue per press, then a blink on arrival.
            rw_blink |= (u8)(1 << r);
            if (!rw_cue) {
                rw_cue = 1;
                rw_offcam_sfx++;
                sfx_play(SFX_DISTRICT);
            }
        } else rw_blink &= (u8)~(1 << r);
        region_paint(r, 0);
        return;                         // amortized: one 2x2 per frame
    }
}

static void blink_step(void) {
    u8 r;
    if (rw_flash_t) {
        if (--rw_flash_t == 0) {
            for (r = 0; r < RW_REGIONS; ++r)
                if (rw_flash & (1 << r)) region_paint(r, 0);
            rw_flash = 0;
        }
        return;
    }
    for (r = 0; r < RW_REGIONS; ++r) {
        if (!(rw_blink & (1 << r)) || !region_in_view(r)) continue;
        rw_blink &= (u8)~(1 << r);
        rw_flash = (u8)(1 << r);
        rw_flash_t = 16;
        region_paint(r, 1);
        return;
    }
}

void rw_tick(void) BANKED {
    u8 on;
    if (!rw_live) return;
    if (rw_epoch != tiles_bg_epoch) {
        // Room entry or Pack resume reloaded the dungeon set: re-dress.
        rw_bg_art_load();
        rw_art_load();
        redress();
        rw_epoch = tiles_bg_epoch;
    }
    new_monsters_in_room = 1;
    if (rw_cool) rw_cool--;
    paint_step();
    blink_step();

    on = foot_on(RW_RESET_X, RW_RESET_Y);
    if (on && !rw_on_reset) { rw_reset(); return; }
    rw_on_reset = on;

    // Edges are sampled every frame; cooldown/queue only gate the press,
    // so a plate never fires late by itself or swallows a fresh step.
    {
        u8 ok = (!rw_cool && !rw_queue) ? 1 : 0;
        on = foot_on(RW_PLATE_A_X, RW_PLATE_A_Y);
        if (ok && ((on && !rw_on_a) || shot_on(RW_PLATE_A_X, RW_PLATE_A_Y))) {
            press_a(); ok = 0;
        }
        rw_on_a = on;
        // Twin of Switch A inside the alcove: one graphic, one meaning.
        on = foot_on(RW_PLATE_A2_X, RW_PLATE_A2_Y);
        if (ok && ((on && !rw_on_a2) || shot_on(RW_PLATE_A2_X, RW_PLATE_A2_Y))) {
            press_a(); ok = 0;
        }
        rw_on_a2 = on;
        on = foot_on(RW_PLATE_B_X, RW_PLATE_B_Y);
        if (ok && ((on && !rw_on_b) || shot_on(RW_PLATE_B_X, RW_PLATE_B_Y)))
            press_b();
        rw_on_b = on;
    }

    on = (foot_on(RW_GOAL_X, RW_GOAL_Y) && ((player.y + 12) >> 3) == WY(RW_GOAL_Y)) ? 1 : 0;
    if (on && !rw_on_goal && !(run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT))
        solve();
    rw_on_goal = on;
    if (!(++rw_frame & 7)) evict_enemies();
}
