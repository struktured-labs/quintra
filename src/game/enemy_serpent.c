#pragma bank 9

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"
#include "render/hud.h"
#include "render/tiles.h"

void serpent_storm_pulse(entity_t *e) BANKED;

// Sixteen cardinal waypoints form a tightening rectangular spiral. Each fourth
// point carries a storm mote, so eating visibly advances to the next ring
// rather than sending the body down four long diagonal lines.
static const u8 route_x[16] = {
    76, 156, 156, 60,
    60, 144, 144, 76,
    76, 132, 132, 92,
    92, 116, 116, 100
};
static const u8 route_y[16] = {
    28, 28, 88, 88,
    40, 40, 76, 76,
    52, 52, 68, 68,
    44, 44, 60, 60
};

static void serpent_chase_tick(entity_t *e) {
    i16 ex, ey;
    i8 sx, sy;
    if (++e->state_timer < 4) return;
    e->state_timer = 0;
    ex = FIX8_TO_INT(e->x); ey = FIX8_TO_INT(e->y);
    sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
    sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
    if (sx) enemy_try_step(e, sx, 0);
    if (sy) enemy_try_step(e, 0, sy);
}

void serpent_feed_tick(entity_t *e) BANKED {
    u8 growth = e->ai_data[4];
    u8 turn = (u8)e->vy;
    u8 route = (u8)(growth * 4 + turn);
    u8 food = (turn == 3);
    i16 dx, dy, ax, ay;
    i8 sx, sy;

    // The last meal finishes expanding one scale at a time before the charge
    // begins; this makes maximum length an event rather than a three-sprite pop.
    if (growth >= 4) {
        if (serpent_tail_visible < 16) return;
        e->state = 1; e->vx = 96; e->vy = 0; e->state_timer = 0;
        room_shake(1, 12); sfx_play(SFX_ROAR);
        return;
    }

    // Only the fourth waypoint of each ring is food. Intermediate turns use a
    // dim hollow cue, making the tightening route readable without implying
    // that every corner grows the creature.
    if ((((u8)e->vx) & 15) == 0) {
        u8 tile = food ? SPR_FX_MUZZLE : SPR_SHIELD_AURA;
        fx_spawn(tile, 2, route_x[route], route_y[route], 12);
    }
    e->vx = (i8)((u8)e->vx + 1);
    if (++e->state_timer < 2) return;
    e->state_timer = 0;
    dx = (i16)route_x[route] - (FIX8_TO_INT(e->x) + 12);
    dy = (i16)route_y[route] - (FIX8_TO_INT(e->y) + 12);
    ax = dx < 0 ? -dx : dx; ay = dy < 0 ? -dy : dy;
    if (ax < 2 && ay < 2) {
        if (!food) { e->vy = (i8)(turn + 1); sfx_play(SFX_TICK); return; }
        fx_spawn(SPR_FX_IMPACT, 2, route_x[route], route_y[route], 14);
        e->ai_data[4] = (u8)(growth + 1);
        e->vy = 0;
        e->ai_data[7] = 8;
        sfx_play(SFX_HEART);
        return;
    }
    sx = dx > 0 ? 1 : dx < 0 ? -1 : 0;
    sy = dy > 0 ? 1 : dy < 0 ? -1 : 0;
    // Waypoints share one coordinate with their predecessor: move only that
    // cardinal leg, producing the hard turns of Snake rather than diagonal
    // chaser interpolation.
    if (ax) enemy_try_step(e, sx, 0);
    else if (ay) enemy_try_step(e, 0, sy);
}

void serpent_motion_tick(entity_t *e) BANKED {
    i16 ex, ey, dx, dy;
    u8 growth = e->ai_data[4];

    if (growth > 4 || e->state > 2) {
        e->ai_data[4] = growth = 0;
        serpent_tail_visible = 2;
        e->state = e->state_timer = e->vx = e->vy = 0;
    }
    serpent_tail_update(e);
    if (e->state == 1) {
        if ((e->vx & 7) == 0) {
            serpent_storm_pulse(e);
            sfx_play(SFX_TICK);
        }
        serpent_chase_tick(e);
        ex = FIX8_TO_INT(e->x); ey = FIX8_TO_INT(e->y);
        if (ex > (i16)room_world_width - 32)
            e->x = FIX8((i16)room_world_width - 32);
        if (ey > (i16)room_world_height - 24)
            e->y = FIX8((i16)room_world_height - 24);
        if (--e->vx) return;
        dx = (i16)player.x - (FIX8_TO_INT(e->x) + 12);
        dy = (i16)player.y - (FIX8_TO_INT(e->y) + 12);
        if (dx < 0) dx = -dx; if (dy < 0) dy = -dy;
        room_shake(2, 24);
        if (dx < 60 && dy < 60 && player.shield_timer == 0) {
            player.hp = (player.hp > 2) ? (u8)(player.hp - 2) : 0;
            player.iframes = 45;
            hud_redraw_hp();
            sfx_play(SFX_HURT);
        } else sfx_play(SFX_CLEAR);
        e->state = 2; e->vx = 5; e->state_timer = 0;
        return;
    }
    if (e->state == 2) {
        // The head coils inward while one real rear segment retracts every
        // five beats. All intermediate lengths are visible: 16,15,...,2.
        if (++e->state_timer >= 2) {
            ex = FIX8_TO_INT(e->x); ey = FIX8_TO_INT(e->y);
            e->state_timer = 0;
            if (ex != 92) enemy_try_step(e, ex < 92 ? 1 : -1, 0);
            if (ey != 48) enemy_try_step(e, 0, ey < 48 ? 1 : -1);
        }
        if (--e->vx) return;
        if (serpent_tail_visible > 2) {
            serpent_tail_visible--;
            e->ai_data[7] = 3;
            e->vx = 5;
        } else {
            e->ai_data[4] = 0;
            e->state = 0; e->vx = e->vy = 0;
            sfx_play(SFX_ROAR);
        }
        return;
    }
    serpent_feed_tick(e);
}
