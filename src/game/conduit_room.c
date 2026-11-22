#pragma bank 24
// M5a Conduit: rules half (turret churn, stone lane, Jagger, keys, plates).
// Cold bank 24; the view/setup half is conduit_view.c (bank 5), art in
// conduit_art.c. All coordinates are world pixels in u8 (room < 256 px).
#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/enemy_ai.h"
#include "game/enemy_new_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/puzzle.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/tiles.h"

u8 cd_live;
u8 cd_side, cd_key, cd_held, cd_open, cd_charge;
u8 cd_jx, cd_jy, cd_jst;
u8 cd_sst, cd_sx, cd_st;
u8 cd_thp, cd_tt, cd_tell, cd_thead, cd_lock, cd_tflash;
u8 cd_shot[2];
u8 cd_armed, cd_pack[2];
u8 cd_pend;
u8 cd_frame, cd_resets, cd_refusals, cd_flips, cd_crushed, cd_shoves;
u8 cd_pack_id;
u8 cd_on;                       // edge latches, one bit per trigger
u8 cd_inside, cd_dirty, cd_epoch;
u8 cd_safe_x, cd_safe_y;

#define PX CD_PX
#define PY CD_PY
#define ON_RESET 1
#define ON_TP    2
#define ON_KEY   4
#define ON_FRZ   8
#define ON_SPAWN 16
#define ON_GOAL  32
#define ON_DOOR  64

#define HX ((u8)player.x)
#define HY ((u8)player.y)

static u8 foot_on(u8 lx, u8 ly) {
    u8 fx = (u8)((u8)(HX + 8) >> 3), fy = (u8)((u8)(HY + 12) >> 3);
    return ((u8)(fx - CD_WX(lx)) < 2 && (u8)(fy - CD_WY(ly)) < 2) ? 1 : 0;
}

// Rising edge of trigger bit b while cond holds.
static u8 edge(u8 cond, u8 b) {
    if (!cond) { cd_on &= (u8)~b; return 0; }
    if (cd_on & b) return 0;
    cd_on |= b;
    return 1;
}

// Feet boxes x+2..x+13, y+8..y+15 (hero and Jagger alike).
static u8 feet_hit(u8 ax, u8 ay, u8 bx, u8 by) {
    return ((u8)(ax + 2) <= (u8)(bx + 13) && (u8)(bx + 2) <= (u8)(ax + 13)
        && (u8)(ay + 8) <= (u8)(by + 15) && (u8)(by + 8) <= (u8)(ay + 15)) ? 1 : 0;
}

static u8 hero_box(u8 x0, u8 y0, u8 w, u8 h) {
    return ((u8)(HX + 13) >= x0 && (u8)(HX + 2) < (u8)(x0 + w)
        && (u8)(HY + 15) >= y0 && (u8)(HY + 8) < (u8)(y0 + h)) ? 1 : 0;
}

static void refuse(void) {
    cd_refusals++;
    sfx_play(SFX_REFUSE);
}

static void kill_slot(u8 *s) {
    // Only ever our own enemy shot (slots can be reused by player shots).
    if (*s != 0xFF && (entities[*s].flags & (EF_ACTIVE | EF_PLAYER_PROJ)) == EF_ACTIVE
        && entities[*s].type == ENT_PROJECTILE) entity_kill(*s);
    *s = 0xFF;
}

void cd_reset(void) BANKED {
    if (!cd_live) return;
    // Warp first, then relock: never sealed behind a door.
    player.x = (i16)PX(3);
    player.y = (i16)PY(CD_ENTRY_Y - 1);
    if (player.iframes < 45) player.iframes = 45;
    cd_safe_x = HX;
    cd_safe_y = HY;
    cd_restore();
    cd_resets++;
    sfx_play(SFX_PORTAL);
    room_shake(1, 10);
}

// ---- side door churn ----
static void side_set(u8 open) {
    cd_side = open;
    cd_paint(0);
    cd_flips++;
    cd_dirty = 1;
    cd_lock = RUN_IS_EASY() ? 80 : 64;
    sfx_play(open ? SFX_DOOR : SFX_TICK);
}

static void side_step(void) {
    if (!cd_pend) return;
    // A shut never lands on the hero: held until the door cells are clear.
    if (cd_side && hero_box(PX(CD_SIDE_X), PY(CD_SIDE_Y), 8, 16)) return;
    cd_pend = 0;
    side_set(cd_side ^ 1);
}

// ---- turret (spec 6.6): telegraph, aimed/random cardinal, lockout ----
static void turret_step(void) {
    u8 i, r;
    entity_t *e;
    if (!cd_thp) return;
    if (cd_tflash) cd_tflash--;
    // Player shots hurt it (vulnerable turret); they never touch the switch.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        e = &entities[i];
        if ((e->flags & (EF_ACTIVE | EF_PLAYER_PROJ)) != (EF_ACTIVE | EF_PLAYER_PROJ)
            || e->type != ENT_PROJECTILE) continue;
        if ((u8)e->x + 4 < PX(CD_TUR_X) || (u8)e->x >= PX(CD_TUR_X + 2)
            || (u8)e->y + 4 < PY(CD_TUR_Y) || (u8)e->y >= PY(CD_TUR_Y + 2)) continue;
        entity_kill(i);
        cd_tflash = 10;
        sfx_play(SFX_HIT);
        if (--cd_thp == 0) {
            // Death fail-safe: shots lose authority, the side door opens.
            kill_slot(&cd_shot[0]);
            kill_slot(&cd_shot[1]);
            cd_tell = 0;
            sfx_play(SFX_DEATH);
            cd_pend = 0;                    // a queued shut dies with it
            if (!cd_side) side_set(1);
            cd_dirty = 1;
            return;
        }
    }
    // Turret shots striking the gold switch flip the side door.
    for (i = 0; i < 2; ++i) {
        r = cd_shot[i];
        if (r == 0xFF) continue;
        e = &entities[r];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
            || (e->flags & EF_PLAYER_PROJ)) { cd_shot[i] = 0xFF; continue; }
        if ((u8)e->x + 6 < PX(CD_SW_X) || (u8)e->x >= PX(CD_SW_X + 2)
            || (u8)e->y + 6 < PY(CD_SW_Y) || (u8)e->y >= PY(CD_SW_Y + 2)) continue;
        entity_kill(r);
        cd_shot[i] = 0xFF;
        if (!cd_pend) { cd_pend = 1; side_step(); }
    }
    if (room_freeze_beats) return;          // freeze holds the cadence
    if (cd_lock) { cd_lock--; return; }     // lockout pauses the fire timer
    if (cd_tell) {
        if (--cd_tell) return;
        i = cd_shot[0] == 0xFF ? 0 : 1;
        kill_slot(&cd_shot[i]);
        r = status_enemy_actor;         // not any enemy's shot: no status quirks
        status_enemy_actor = 0xFF;
        if (cd_thead) cd_shot[i] = projectile_spawn_enemy((i16)PX(CD_TUR_X) + 4,
            (i16)PY(CD_TUR_Y + 2), 0, 1, 1);
        else cd_shot[i] = projectile_spawn_enemy((i16)PX(CD_TUR_X) - 8,
            (i16)PY(CD_TUR_Y) + 4, -1, 0, 1);
        status_enemy_actor = r;
        sfx_play(SFX_FIRE);
        return;
    }
    if (--cd_tt) return;
    r = rng_next_u8();
    // 70% aimed: S when the hero is below the turret's rows (that lane
    // crosses the switch), else W; 30% random from {W, S}.
    if (r < 179) cd_thead = ((u8)((u8)(HY + 12) >> 3) >= CD_WY(CD_TUR_Y + 2)) ? 1 : 0;
    else cd_thead = r & 1;
    cd_tell = RUN_IS_EASY() ? 32 : 24;
    cd_tt = (u8)((RUN_IS_EASY() ? 120 - 16 : 96 - 16) + (rng_next_u8() & 31));
    sfx_play(SFX_TICK);
}

// ---- pedestals, plates, doors ----
static void pads_step(void) {
    u8 on;
    if (edge(foot_on(CD_KEY_X, CD_KEY_Y), ON_KEY) && cd_key) {
        cd_key = 0;
        cd_held |= 1;
        cd_dirty = 1;
        sfx_play(SFX_COIN);
    }
    // Rime pedestal re-arms whenever the hero has no charge and no freeze.
    if (edge(foot_on(CD_FRZ_X, CD_FRZ_Y), ON_FRZ) && !cd_charge && !room_freeze_beats) {
        cd_charge = 1;
        cd_dirty = 1;
        sfx_play(SFX_COIN);
    }
    if (edge(foot_on(CD_TP_X, CD_TP_Y), ON_TP)) {
        // Teleport skip: lands past the spawn plate, never armed.
        player.x = (i16)PX(2);          // clear of rewrite switch A (col 1)
        player.y = (i16)PY(CD_TPD_Y) - 8;
        cd_safe_x = HX;
        cd_safe_y = HY;
        if (player.iframes < 30) player.iframes = 30;
        cd_on |= ON_SPAWN;
        sfx_play(SFX_PORTAL);
        return;
    }
    if (edge(foot_on(CD_SPAWN_X, CD_SPAWN_Y), ON_SPAWN) && !cd_armed) {
        cd_armed = 1;
        cd_dirty = 1;
        // The pack must move in the lower hall: while it lives the keep-out
        // box shrinks to rows 0..7 (cd_guard still evicts anything else).
        puzzle_keep_y1 = (u8)((CD_Y0 + 8) * 8);   // lower hall opens to the pack only
        if (cd_pack_id != 0xFF) {
            cd_pack[0] = enemy_spawn(cd_pack_id, CD_WX(7), CD_WY(9));
            cd_pack[1] = enemy_spawn(cd_pack_id, CD_WX(9), CD_WY(9));
        }
        sfx_play(SFX_ROAR);
    }
    // Star door: feet box + 1 px touching it.
    on = hero_box((u8)(PX(CD_DOOR_X) - 1), (u8)(PY(CD_DOOR_Y) - 1), 18, 10);
    if (!cd_open && edge(on, ON_DOOR)) {
        if (cd_held & 1) {
            cd_held &= (u8)~1;
            cd_open = 1;
            cd_dirty = 1;
            cd_paint(1);
            sfx_play(SFX_DOOR);
        } else refuse();
    }
    on = (foot_on(CD_GOAL_X, CD_GOAL_Y) && (u8)((u8)(HY + 12) >> 3) == CD_WY(CD_GOAL_Y)) ? 1 : 0;
    if (edge(on, ON_GOAL) && !(run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT))
        cd_solve();
}

static void guard_step(void) {
    u8 i;
    entity_t *e;
    for (i = 0; i < 2; ++i)
        if (cd_pack[i] != 0xFF && (!(entities[cd_pack[i]].flags & EF_ACTIVE)
                || entities[cd_pack[i]].type != ENT_ENEMY)) cd_pack[i] = 0xFF;
    if (cd_pack[0] == 0xFF && cd_pack[1] == 0xFF) puzzle_keep_y1 = (u8)((CD_Y0 + CD_H) * 8);
    for (i = 0; i < MAX_ENTITIES; ++i) {
        e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY
            || i == cd_pack[0] || i == cd_pack[1]) continue;
        if ((u8)e->x + 8 < puzzle_keep_x0 || (u8)e->y + 8 < puzzle_keep_y0
            || (u8)e->y + 8 >= puzzle_keep_y1) continue;
        e->x = (i16)PX(0) - 32;
        e->y = (i16)PY(CD_ENTRY_Y);
    }
}

void cd_tick(void) BANKED {
    u8 fx, fy, inside;
    if (!cd_live) return;
    if (cd_epoch != tiles_bg_epoch) {
        cd_redress();
        cd_epoch = tiles_bg_epoch;
    }
    new_monsters_in_room = 1;
    cd_frame++;
    if (room_freeze_beats && !(cd_frame & 3)) room_freeze_beats--;

    fx = (u8)((u8)(HX + 8) >> 3);
    fy = (u8)((u8)(HY + 12) >> 3);
    inside = (fx >= CD_X0 && fx < (u8)(CD_X0 + CD_W)
        && fy >= CD_Y0 && fy < (u8)(CD_Y0 + CD_H)) ? 1 : 0;
    if (cd_inside && !inside && cd_dirty) cd_restore();   // walking out resets
    cd_inside = inside;

    if (edge(foot_on(CD_RESET_X, CD_RESET_Y), ON_RESET)) { cd_reset(); return; }

    if ((cd_jst != CD_J_DEAD && feet_hit(HX, HY, cd_jx, cd_jy))
        || (cd_thp && feet_hit(HX, HY, PX(CD_TUR_X), PY(CD_TUR_Y)))) {
        // The Jagger's touch is a shove back, never damage.
        player.x = (i16)cd_safe_x;
        player.y = (i16)cd_safe_y;
    } else { cd_safe_x = HX; cd_safe_y = HY; }

    pads_step();
    side_step();
    turret_step();
    cd_lane_step();
    cd_vault_tick();
    if (!(cd_frame & 7) || cd_frame == 1) guard_step();
}

// Pack TOOL entries: 0 = FREEZE (Rime charge), 1 = RESET ROOM.
u8 cd_pack_a(u8 idx) BANKED {
    if (idx == 0 && !cd_charge) {
        sfx_play(SFX_HURT);
        return 1;
    }
    sfx_play(SFX_CLEAR);
    return 2;
}

void cd_pack_apply(u8 idx) BANKED {
    if (idx) { cd_reset(); return; }
    if (!cd_charge) return;
    cd_charge = 0;
    cd_dirty = 1;
    room_freeze_beats = RUN_IS_EASY() ? RIME_FREEZE_EASY : RIME_FREEZE_NORMAL;
    sfx_play(SFX_WILL);
}
