#pragma bank 27
// M4 Lockmire Ferry: matching keys, flip-conveyor, lure (spec 6.7-6.9, M4).
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
u8 lk_live;
u8 lk_held, lk_ped, lk_open;
u8 lk_dir, lk_gate, lk_wpress;
u8 lk_lure, lk_lx, lk_ly;
u8 lk_jx, lk_jy, lk_jst;
u8 lk_cool, lk_frame;
u8 lk_resets, lk_refusals, lk_coins, lk_blink, lk_offcam_sfx, lk_drops;
u8 lk_queue, lk_flash, lk_flash_t, lk_cue, lk_epoch, lk_dirty;
u8 lk_on_reset, lk_on_flip, lk_on_ped, lk_on_lure, lk_on_goal, lk_touch;
u8 lk_inside, lk_coin_given;
i16 lk_safe_x, lk_safe_y;

#define WX(lx) ((u8)(LK_X0 + (lx)))
#define WY(ly) ((u8)(LK_Y0 + (ly)))
#define PX(lx) ((u8)(WX(lx) << 3))
#define PY(ly) ((u8)(WY(ly) << 3))

static const u8 reg_x[LK_REGIONS] = { 3, 5, 5, 9, 3, 8, 1 };

static const u8 reg_y[LK_REGIONS] = { 11, 14, 8, 3, 15, 15, 11 };

static const u8 reg_w[LK_REGIONS] = { 6, 2, 2, 2, 1, 1, 2 };

static const u8 reg_h[LK_REGIONS] = { 2, 1, 1, 1, 2, 2, 2 };

// Doors: region index 2..5 -> door bit 0..3 and the key type it takes.
static const u8 door_type[4] = { LK_STAR, LK_MOON, LK_HEART, LK_HEART };

static const u8 ped_x[3] = { 2, 5, 1 }, ped_y[3] = { 1, 1, 15 };

static void commit(u8 r) {
    lk_reg_write(r);
    lk_queue |= (u8)(1 << r);
    lk_dirty = 1;
}

static void cue_reset(void) { lk_cue = 0; }

static void refuse(void) {
    lk_refusals++;
    sfx_play(SFX_REFUSE);
}

static u8 foot_on(u8 lx, u8 ly) {
    u8 fx = (u8)((player.x + 8) >> 3), fy = (u8)((player.y + 12) >> 3);
    return ((u8)(fx - WX(lx)) < 2 && (u8)(fy - WY(ly)) < 2) ? 1 : 0;
}

// Feet boxes: x+2..x+13, y+8..y+15 (hero and Jagger alike).
static u8 feet_overlap(i16 ax, i16 ay, i16 bx, i16 by) {
    return (ax + 2 <= bx + 13 && bx + 2 <= ax + 13
        && ay + 8 <= by + 15 && by + 8 <= ay + 15) ? 1 : 0;
}

static u8 body_tile_ok(u8 t) {
    return (t == BGT_FLOOR || t == LK_T_CONV_E || t == LK_T_CONV_W
        || t == LK_T_WPLATE || t == LK_T_WPRESS) ? 1 : 0;
}

// Can the Jagger stand at (nx, ny)? Lane, plate and rest only (fenced).
static u8 jagger_fits(i16 nx, i16 ny) {
    if (!body_tile_ok(room_tile_at_px(nx + 2, ny + 8))
        || !body_tile_ok(room_tile_at_px(nx + 13, ny + 8))
        || !body_tile_ok(room_tile_at_px(nx + 2, ny + 15))
        || !body_tile_ok(room_tile_at_px(nx + 13, ny + 15))) return 0;
    if (ny + 8 < (i16)PY(LK_JY) || ny + 15 >= (i16)PY(LK_JY + 2)) return 0;
    return feet_overlap(nx, ny, player.x, player.y) ? 0 : 1;
}

static u8 hero_fits(i16 nx, i16 ny) {
    u8 k;
    static const u8 cx[3] = { 2, 8, 13 };
    for (k = 0; k < 3; ++k) {
        if (!room_tile_walkable(room_tile_at_px(nx + cx[k], ny + 8))) return 0;
        if (!room_tile_walkable(room_tile_at_px(nx + cx[k], ny + 15))) return 0;
    }
    return feet_overlap(nx, ny, (i16)lk_jx, (i16)lk_jy) ? 0 : 1;
}

// Belt push under a feet centre: +2 east, -2 west, 0 none.
static i8 belt_at(i16 x, i16 y) {
    u8 t = room_tile_at_px(x + 8, y + 12);
    if (t == LK_T_CONV_E) return 2;
    if (t == LK_T_CONV_W) return -2;
    return 0;
}

void lk_reset(void) BANKED {
    if (!lk_live) return;
    // Warp first, then relock: the hero is never sealed behind a door.
    player.x = (i16)PX(3);
    player.y = (i16)PY(LK_ENTRY_Y - 1);
    if (player.iframes < 45) player.iframes = 45;
    lk_safe_x = player.x;
    lk_safe_y = player.y;
    lk_restore();
    lk_resets++;
    sfx_play(SFX_PORTAL);
    room_shake(1, 10);
}

// The lure is dropped at the hero's feet, on plain floor of the ferry hall
// only (never the entrance / reset side, the lane, the plates).
static void lk_drop(void) {
    u8 x = (u8)((u8)(player.x + 4) & 0xF8), y = (u8)((u8)(player.y + 4) & 0xF8);
    u8 ok = 1, k;
    if (lk_lure != 1) { refuse(); return; }
    if (y < PY(9) || (u8)(y + 16) > PY(11) || x < PX(1) || (u8)(x + 16) > PX(LK_FLIP_X))
        ok = 0;
    for (k = 0; ok && k < 4; ++k)
        if (room_tile_at_px((i16)x + ((k & 1) << 3), (i16)y + ((k & 2) << 2)) != BGT_FLOOR)
            ok = 0;
    if (!ok) { refuse(); return; }
    lk_lure = 2;
    lk_lx = x; lk_ly = y;
    lk_drops++;
    lk_dirty = 1;
    if (lk_jst == LK_J_IDLE) lk_jst = LK_J_SEEK;
    sfx_play(SFX_DOOR);
}

static void jagger_step(void) {
    i8 b;
    u8 cx;
    if (lk_jst == LK_J_SETTLED) return;
    cx = (u8)((u8)(lk_jx + 8) >> 3);
    if (cx <= WX(LK_WX + 1)) {
        // Feet on the weight plate: it settles there until a reset.
        lk_jx = PX(LK_WX);
        lk_jst = LK_J_SETTLED;
        sfx_play(SFX_TICK);
        return;
    }
    b = belt_at((i16)lk_jx, (i16)lk_jy);
    if (b) {
        // On the belt it rides (no walking of its own); blocked = waits.
        if (jagger_fits((i16)lk_jx + b, (i16)lk_jy)) lk_jx = (u8)(lk_jx + b);
        else if (jagger_fits((i16)lk_jx + (b > 0 ? 1 : -1), (i16)lk_jy))
            lk_jx = (u8)(lk_jx + (b > 0 ? 1 : -1));
        return;
    }
    if (lk_jst != LK_J_SEEK || (lk_frame & 1)) return;
    // Lure down: x first, then y (the fence leaves only the lane west).
    if (lk_lx < lk_jx && jagger_fits((i16)lk_jx - 1, (i16)lk_jy)) lk_jx--;
    else if (lk_lx > lk_jx && jagger_fits((i16)lk_jx + 1, (i16)lk_jy)) lk_jx++;
    else if (lk_ly < lk_jy && jagger_fits((i16)lk_jx, (i16)lk_jy - 1)) lk_jy--;
    else if (lk_ly > lk_jy && jagger_fits((i16)lk_jx, (i16)lk_jy + 1)) lk_jy++;
}

static void hero_belt(void) {
    i8 b = belt_at(player.x, player.y), s;
    u8 k;
    if (!b) return;
    s = (b > 0) ? 1 : -1;
    for (k = 0; k < 2; ++k)
        if (hero_fits(player.x + s, player.y)) player.x += s;
}

static void keys_step(void) {
    u8 k, on = 0, bit;
    for (k = 0; k < 3; ++k) {
        bit = (u8)(1 << k);
        if (!(lk_ped & bit) || !foot_on(ped_x[k], ped_y[k])) continue;
        on = bit;
        if (lk_on_ped & bit) break;
        if (lk_held & bit) refuse();        // one of each type at a time
        else {
            lk_held |= bit;
            lk_ped &= (u8)~bit;
            lk_dirty = 1;
            sfx_play(SFX_COIN);
        }
        break;
    }
    lk_on_ped = on;
    on = (lk_lure == 0 && foot_on(LK_LURE_X, LK_LURE_Y)) ? 1 : 0;
    if (on && !lk_on_lure) {
        lk_lure = 1;
        lk_dirty = 1;
        sfx_play(SFX_COIN);
    }
    lk_on_lure = on;
}

static void doors_step(void) {
    u8 d, r, touch = 0;
    i16 fx0 = player.x + 1, fx1 = player.x + 14, fy0 = player.y + 7, fy1 = player.y + 16;
    for (d = 0; d < 4; ++d) {
        i16 x0, y0;
        r = (u8)(d + 2);
        if (lk_open & (1 << d)) continue;
        x0 = (i16)PX(reg_x[r]); y0 = (i16)PY(reg_y[r]);
        if (fx1 < x0 || fx0 >= x0 + (i16)(reg_w[r] << 3)
            || fy1 < y0 || fy0 >= y0 + (i16)(reg_h[r] << 3)) continue;
        touch |= (u8)(1 << d);
        if (lk_touch & (1 << d)) continue;
        if (lk_held & door_type[d]) {
            // A matching key is spent on a real unlock, never on a bump.
            lk_held &= (u8)~door_type[d];
            lk_open |= (u8)(1 << d);
            commit(r);
            cue_reset();
            sfx_play(SFX_DOOR);
            if (d == 1 && !lk_coin_given
                && !(run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)) {
                lk_coin_given = 1;
                lk_coins++;
                pickup_spawn(PICKUP_COIN_5, (i16)PX(LK_COIN_X), (i16)PY(LK_COIN_Y));
            }
        } else refuse();                    // wrong key or none: locked
    }
    lk_touch = touch;
}

static void gate_step(void) {
    u8 want = (lk_jst == LK_J_SETTLED || foot_on(LK_WX, LK_WY)) ? 1 : 0;
    if (want != lk_wpress) { lk_wpress = want; commit(6); }
    if (want == lk_gate) return;
    // Never close the bars on the hero.
    // Exact test: any hero collision sample inside the gate's 16x8 cells.
    if (!want && player.x + 13 >= (i16)PX(5) && player.x + 2 < (i16)PX(7)
        && player.y + 15 >= (i16)PY(14) && player.y + 8 < (i16)PY(15))
        return;
    lk_gate = want;
    commit(1);
    cue_reset();
    sfx_play(want ? SFX_DOOR : SFX_TICK);
}

void lk_tick(void) BANKED {
    u8 on, fx, fy, inside;
    if (!lk_live) return;
    new_monsters_in_room = 1;
    lk_frame++;
    if (lk_cool) lk_cool--;
    lk_view_step();

    fx = (u8)((player.x + 8) >> 3);
    fy = (u8)((player.y + 12) >> 3);
    inside = (fx >= LK_X0 && fx < (u8)(LK_X0 + LK_W)
        && fy >= LK_Y0 && fy < (u8)(LK_Y0 + LK_H)) ? 1 : 0;
    // Walking out of the entrance is the same reset (keys, lure, doors).
    if (lk_inside && !inside && lk_dirty) lk_restore();
    lk_inside = inside;

    on = foot_on(LK_RESET_X, LK_RESET_Y);
    if (on && !lk_on_reset) { lk_reset(); return; }
    lk_on_reset = on;

    if (inside) hero_belt();
    if (feet_overlap(player.x, player.y, (i16)lk_jx, (i16)lk_jy)) {
        // The Jagger's touch is a shove back, never damage.
        player.x = lk_safe_x;
        player.y = lk_safe_y;
    } else { lk_safe_x = player.x; lk_safe_y = player.y; }

    keys_step();
    on = foot_on(LK_FLIP_X, LK_FLIP_Y);
    if (!on) lk_on_flip = 0;
    else if (!lk_on_flip && !lk_cool) {
        // Both tiles are walkable, so a flip under a body is always safe.
        lk_on_flip = 1;
        lk_dir ^= 1;
        commit(0);
        cue_reset();
        lk_cool = 20;
        sfx_play(SFX_DOOR);
    }
    doors_step();
    jagger_step();
    gate_step();

    on = (foot_on(LK_GOAL_X, LK_GOAL_Y) && fy == WY(LK_GOAL_Y)) ? 1 : 0;
    if (on && !lk_on_goal && !(run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT))
        lk_solve();
    lk_on_goal = on;
    lk_guard_step();
}

u8 lk_pack_a(u8 idx) BANKED {
    if (idx == 0 && lk_lure != 1) {
        sfx_play(SFX_HURT);
        return 1;
    }
    sfx_play(SFX_CLEAR);
    return 2;
}

void lk_pack_apply(u8 idx) BANKED {
    if (idx == 0) lk_drop();
    else lk_reset();
}
