#pragma bank 23
// M4 Lockmire Ferry (view/setup half, bank 23): matching keys, flip-conveyor, lure (spec 6.7-6.9, M4).
// Pinned in cold bank 27 (art in bank 24). The Stone Jagger here is a
// puzzle-owned actor (not an entity): nothing can hurt it, and its touch
// only shoves the hero back. All state is WRAM rebuilt on entry.
#include <gb/gb.h>
#include <gbdk/console.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/enemy_new_ai.h"
#include "game/lock_room.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/lock_art.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

#include "game/lock_room_int.h"
#define WX(lx) ((u8)(LK_X0 + (lx)))
#define WY(ly) ((u8)(LK_Y0 + (ly)))
#define PX(lx) ((u8)(WX(lx) << 3))
#define PY(ly) ((u8)(WY(ly) << 3))

// '#' wall, '.' floor, 'p' fixed west belt (the other direction, shown
// first), '=' barred window (see the closet and the vault before choosing),
// 'G' goal. Doors, gate, lane and weight plate are regions painted below.
static const char lk_layout[LK_H][LK_W + 1] = {
    "############",
    "#......#...#",   // Heart key (2,1), Star key (5,1) | Moon nook (8..10)
    "#......#...#",
    "#......##..#",   // Moon door (9..10, 3)
    "#..........#",   // reset plate (1..2, 4..5)
    "#..........#",   // lure pedestal (8..9, 5..6)
    "...........#",   // entrance rows 6..7
    "...........#",
    "############",   // Star door (5..6, 8)
    "#........###",   // flip plate (7..8, 9..10); fence over the Jagger
    "#........###",
    "#..........#",   // W (1..2) | lane (3..8) | Jagger rest (9..10)
    "#..........#",
    "#........pp#",
    "#==######==#",   // windows: closet (1..2), vault (9..10); gate (5..6)
    "#..........#",   // closet | Heart door W (3) | ante | Heart door E (8)
    "#........GG#",   // vault goal (9..10, 16)
    "############",
};

static const u8 reg_x[LK_REGIONS] = { 3, 5, 5, 9, 3, 8, 1 };

static const u8 reg_y[LK_REGIONS] = { 11, 14, 8, 3, 15, 15, 11 };

static const u8 reg_w[LK_REGIONS] = { 6, 2, 2, 2, 1, 1, 2 };

static const u8 reg_h[LK_REGIONS] = { 2, 1, 1, 1, 2, 2, 2 };

static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

// Tile + attribute of cell i (row-major) of region r, from live state.
static u8 reg_tile(u8 r, u8 i, u8 *attr) {
    u8 d;
    if (r == 0) { *attr = BGPAL_FLOOR; return lk_dir ? LK_T_CONV_W : LK_T_CONV_E; }
    if (r == 1) {
        if (lk_gate) { *attr = BGPAL_FLOOR; return BGT_FLOOR; }
        *attr = BGPAL_WALL; return LK_T_BARS;
    }
    if (r == 6) {
        static const u8 flip[4] = { 0, 0x20, 0x40, 0x60 };
        *attr = (u8)(BGPAL_DOOR | flip[i]);
        return lk_wpress ? LK_T_WPRESS : LK_T_WPLATE;
    }
    d = (u8)(r - 2);
    if (lk_open & (1 << d)) { *attr = BGPAL_FLOOR; return BGT_FLOOR; }
    // One symmetric door tile: mirrored across the door's long axis.
    *attr = (u8)(BGPAL_CRACK | (i ? ((r >= 4) ? 0x40 : 0x20) : 0));
    return LK_T_DOOR;
}

// World arrays now (collision and the belt read them); VRAM later.
void lk_reg_write(u8 r) BANKED {
    u8 i = 0, x, y, a;
    for (y = 0; y < reg_h[r]; ++y)
        for (x = 0; x < reg_w[r]; ++x, ++i)
            wset(WX(reg_x[r] + x), WY(reg_y[r] + y), reg_tile(r, i, &a));
}

static void reg_paint(u8 r, u8 flash) {
    u8 t[12], a[12], i = 0, x, y, n;
    for (y = 0; y < reg_h[r]; ++y)
        for (x = 0; x < reg_w[r]; ++x, ++i) {
            t[i] = reg_tile(r, i, &a[i]);
            if (flash) a[i] = (u8)((a[i] & 0xF8) | BGPAL_DOOR);
        }
    x = WX(reg_x[r]); y = WY(reg_y[r]); n = reg_w[r];
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), n, reg_h[r], t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), n, reg_h[r], a);
    VBK_REG = 0;
}

static u8 reg_in_view(u8 r) {
    u8 cx = (u8)(room_camera_x >> 3), cy = (u8)(room_camera_y >> 3);
    u8 x = WX(reg_x[r]), y = WY(reg_y[r]);
    return ((u8)(x + reg_w[r]) > cx && x < (u8)(cx + 20)
        && (u8)(y + reg_h[r]) > cy && y < (u8)(cy + 17)) ? 1 : 0;
}

static u8 paint_step(void) {
    u8 r;
    for (r = 0; r < LK_REGIONS; ++r) {
        if (!(lk_queue & (1 << r))) continue;
        lk_queue &= (u8)~(1 << r);
        if (lk_flash & (1 << r)) { lk_flash = 0; lk_flash_t = 0; }
        if (!reg_in_view(r)) {
            // Off camera: one distinct cue per change, a blink on arrival.
            // A reset's repaint (lk_cue == 2) is quiet: no cue, no blink.
            if (lk_cue != 2) lk_blink |= (u8)(1 << r);
            if (!lk_cue) {
                lk_cue = 1;
                lk_offcam_sfx++;
                sfx_play(SFX_DISTRICT);
            }
        } else lk_blink &= (u8)~(1 << r);
        reg_paint(r, 0);
        return 1;
    }
    return 0;
}

static void blink_step(void) {
    u8 r;
    if (lk_flash_t) {
        if (--lk_flash_t == 0) {
            for (r = 0; r < LK_REGIONS; ++r)
                if (lk_flash & (1 << r)) reg_paint(r, 0);
            lk_flash = 0;
        }
        return;
    }
    for (r = 0; r < LK_REGIONS; ++r) {
        if (!(lk_blink & (1 << r)) || !reg_in_view(r)) continue;
        lk_blink &= (u8)~(1 << r);
        lk_flash = (u8)(1 << r);
        lk_flash_t = 16;
        reg_paint(r, 1);
        return;
    }
}

static void fixed_paint(u8 x, u8 y, u8 n, u8 t, u8 a) {
    u8 tt[2], aa[2];
    tt[0] = tt[1] = t; aa[0] = aa[1] = a;
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(x)), ROOM_BG_MAP_Y(WY(y)), n, 1, aa);
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(x)), ROOM_BG_MAP_Y(WY(y)), n, 1, tt);
}

// Re-dress after any dungeon BG reload: art, every region, fixed pieces.
static void redress(void) {
    u8 r;
    lk_flash = lk_flash_t = 0;
    lk_queue = 0;                       // everything is painted right here
    for (r = 0; r < LK_REGIONS; ++r) reg_paint(r, 0);
    wait_vbl_done();
    if (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)
        fixed_paint(LK_GOAL_X, LK_GOAL_Y, 2, BGT_SWITCH_PRESSED, BGPAL_DOOR);
    fixed_paint(9, 13, 2, LK_T_CONV_W, BGPAL_FLOOR);
    fixed_paint(1, 14, 2, LK_T_BARS, BGPAL_WALL);
    fixed_paint(9, 14, 2, LK_T_BARS, BGPAL_WALL);
}

void lk_view_step(void) BANKED {
    if (lk_epoch != tiles_bg_epoch) {
        lk_bg_art_load();
        lk_art_load();
        redress();
        lk_epoch = tiles_bg_epoch;
    }
    // At most one VRAM region write per frame.
    if (!paint_step()) blink_step();
    if (!(lk_frame & 7)) lk_belt_anim((u8)(lk_frame >> 3));
}

static void jagger_home(void) {
    lk_jx = PX(LK_JX);
    lk_jy = PY(LK_JY);
    lk_jst = LK_J_IDLE;
}

static u8 in_zone(u8 ex, u8 ey) {
    if (ex >= (u8)(LK_X0 - 4) && ey >= LK_Y0 && ey < (u8)(LK_Y0 + LK_H)) return 1;
    return (ex >= 11 && ey >= (u8)(WY(LK_ENTRY_Y) - 1)
        && ey <= (u8)(WY(LK_ENTRY_Y) + 2)) ? 1 : 0;
}

// Entry state of every moving part (not the coin, which never comes back).
void lk_restore(void) BANKED {
    u8 r;
    lk_held = 0;
    lk_ped = LK_HEART | LK_STAR | LK_MOON;
    lk_open = 0;
    lk_dir = lk_gate = lk_wpress = 0;
    lk_lure = 0;
    jagger_home();
    for (r = 0; r < LK_REGIONS; ++r) lk_reg_write(r);
    lk_queue = (1 << LK_REGIONS) - 1;
    lk_cue = 2;
    lk_blink = 0;
    lk_flash = lk_flash_t = 0;
    lk_on_reset = lk_on_flip = lk_on_ped = lk_on_lure = lk_on_goal = 1;
    lk_touch = 0x0F;
    lk_cool = 20;
    lk_dirty = 0;
}

u8 lk_prepare(void) BANKED {
    u8 i, x, y;
    lk_live = 0;
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
    for (y = 0; y < LK_H; ++y)
        for (x = 0; x < LK_W; ++x) {
            char c = lk_layout[y][x];
            u8 t = BGT_FLOOR;
            if (c == '#') t = BGT_WALL;
            else if (c == 'p') t = LK_T_CONV_W;
            else if (c == '=') t = LK_T_BARS;
            else if (c == 'G') t = (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)
                ? BGT_SWITCH_PRESSED : BGT_SWITCH;
            wset(WX(x), WY(y), t);
        }
    for (y = (u8)(LK_ENTRY_Y - 1); y <= (u8)(LK_ENTRY_Y + 2); ++y)
        for (x = (u8)(LK_X0 - 4); x < LK_X0; ++x)
            wset(x, WY(y), BGT_FLOOR);
    for (y = LK_ENTRY_Y; y <= (u8)(LK_ENTRY_Y + 1); ++y)
        for (x = 11; x < (u8)(LK_X0 - 4); ++x)
            wset(x, WY(y), BGT_FLOOR);
    lk_restore();
    lk_on_reset = lk_on_flip = lk_on_ped = lk_on_lure = lk_on_goal = 0;
    lk_touch = 0;
    lk_resets = lk_refusals = lk_coins = lk_offcam_sfx = lk_drops = 0;
    lk_coin_given = 0;
    lk_inside = 0;
    lk_frame = 0;
    lk_safe_x = player.x;
    lk_safe_y = player.y;
    lk_epoch = (u8)(tiles_bg_epoch - 1);
    puzzle_keep_x0 = (u8)((LK_X0 - 1) * 8);
    puzzle_keep_y0 = (u8)(LK_Y0 * 8);
    puzzle_keep_y1 = (u8)((LK_Y0 + LK_H) * 8);
    puzzle_keep_on = 1;
    puzzle_pack_n = 2;
    lk_live = 1;
    new_monsters_in_room = 1;
    return 1;
}

void lk_solve(void) BANKED {
    u8 t[2] = { BGT_SWITCH_PRESSED, BGT_SWITCH_PRESSED };
    u8 a[2] = { BGPAL_DOOR, BGPAL_DOOR };
    run_state.dungeon_puzzles |= RUN_RIME_SOLVED_BIT;
    wset(WX(LK_GOAL_X), WY(LK_GOAL_Y), BGT_SWITCH_PRESSED);
    wset(WX(LK_GOAL_X + 1), WY(LK_GOAL_Y), BGT_SWITCH_PRESSED);
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(LK_GOAL_X)), ROOM_BG_MAP_Y(WY(LK_GOAL_Y)), 2, 1, t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(LK_GOAL_X)), ROOM_BG_MAP_Y(WY(LK_GOAL_Y)), 2, 1, a);
    VBK_REG = 0;
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed + rime_cell) % 3),
        player.x, player.y);
}
