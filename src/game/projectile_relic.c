#pragma bank 10

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "render/tiles.h"

static void spawn_fractal(i16 px, i16 py, u8 dir, u8 damage, u8 can_fork) {
    u8 idx = entity_spawn(ENT_PROJECTILE);
    entity_t *e;
    if (idx == 0xFF) return;
    e = &entities[idx];
    e->flags |= EF_PLAYER_PROJ;
    e->x = FIX8(px);
    e->y = FIX8(py);
    e->vx = (i8)(dir8_dx[dir] * 3);
    e->vy = (i8)(dir8_dy[dir] * 3);
    e->sprite_tile = SPR_BULLET_B;
    e->palette = 6;
    e->hp = 1;
    e->state_timer = 34;
    e->hitbox = 0x55;
    e->damage = damage ? damage : 1;
    e->ai_data[1] = g_shot_element;
    if (can_fork) {
        e->ai_data[3] = PROJ_FLAG_FRACTAL;
        e->ai_data[7] = 10;
    }
}

void projectile_spawn_fractal_pair(i16 px, i16 py, u8 dir,
    u8 damage, u8 can_fork) BANKED {
    spawn_fractal(px, py, (u8)((dir + 1) & 7), damage, can_fork);
    spawn_fractal(px, py, (u8)((dir + 7) & 7), damage, can_fork);
    fx_spawn(SPR_FX_MUZZLE, 6, px, py, 7);
}

void projectile_spawn_splash(i16 px, i16 py, u8 damage,
    u8 avoid_slot) BANKED {
    u8 idx = entity_spawn(ENT_PROJECTILE);
    entity_t *e;
    if (idx == 0xFF) return;
    e = &entities[idx];
    e->flags |= EF_PLAYER_PROJ;
    e->x = FIX8(px - 7);
    e->y = FIX8(py - 7);
    e->sprite_tile = SPR_FX_IMPACT;
    e->palette = 4;
    e->hp = 8;
    // The next frame's update arms one collision sweep; this avoids making
    // behavior depend on whether the free entity slot precedes its parent.
    e->state_timer = 3;
    e->hitbox = 0xFF;
    e->damage = damage ? damage : 1;
    e->ai_data[5] = avoid_slot;
    e->ai_data[6] = PROJ_AUX_SPLASH;
    e->ai_data[7] = 1;
}

void projectile_update_relic(entity_t *e) BANKED {
    if (e->ai_data[6] == PROJ_AUX_SPLASH && e->ai_data[7] == 1)
        e->ai_data[7] = 2;
    if ((e->ai_data[3] & PROJ_FLAG_FRACTAL)
        && e->ai_data[7] && --e->ai_data[7] == 0) {
        u8 dir;
        if (e->vx == 0) dir = e->vy < 0 ? 0 : 4;
        else if (e->vx > 0)
            dir = e->vy < 0 ? 1 : e->vy > 0 ? 3 : 2;
        else dir = e->vy < 0 ? 7 : e->vy > 0 ? 5 : 6;
        e->ai_data[3] &= (u8)~PROJ_FLAG_FRACTAL;
        projectile_spawn_fractal_pair(FIX8_TO_INT(e->x),
            FIX8_TO_INT(e->y), dir,
            e->damage > 1 ? (u8)((e->damage + 1) >> 1) : 1, 0);
    }
}

void projectile_make_beam(u8 idx) BANKED {
    entity_t *e;
    u8 tail;
    i8 bx, by;
    if (idx >= MAX_ENTITIES || !(entities[idx].flags & EF_ACTIVE)) return;
    e = &entities[idx];
    e->ai_data[3] |= PROJ_FLAG_BEAM;
    e->sprite_tile = SPR_FX_BEAM_HEAD;
    e->palette = 6;
    e->hitbox = 0xDD;
    e->hp = e->hp > 251 ? 255 : (u8)(e->hp + 4);
    e->damage++;
    e->state_timer = e->state_timer > 243
        ? 255 : (u8)(e->state_timer + 12);
    bx = e->vx > 0 ? -6 : e->vx < 0 ? 6 : 0;
    by = e->vy > 0 ? -6 : e->vy < 0 ? 6 : 0;
    tail = fx_spawn(SPR_FX_BEAM_TAIL, e->palette,
        FIX8_TO_INT(e->x) + bx, FIX8_TO_INT(e->y) + by, e->state_timer);
    if (tail != 0xFF) {
        entity_t *t = &entities[tail];
        t->vx = e->vx;
        t->vy = e->vy;
        t->ai_data[4] = e->ai_data[4];
        t->ai_data[6] = PROJ_AUX_BEAM_TRAIL;
    }
}
