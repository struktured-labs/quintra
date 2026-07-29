#pragma bank 7
// Enemy-shot constructors are called at authored firing beats, not once per
// active bullet per frame. Keep them out of bank 3 so its hot projectile
// updater has development headroom.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "render/tiles.h"

// Core spawn with an explicit px/tick velocity — lets bosses mix bullet speeds
// (thin-fast streams vs. slow dense walls) within one pattern.
u8 projectile_spawn_enemy_v(i16 px, i16 py, i8 vx, i8 vy, u8 damage) BANKED {
    u8 idx;
    entity_t *e;
    if (vx == 0 && vy == 0) return 0xFF;
    idx = entity_spawn(ENT_PROJECTILE);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    // No EF_PLAYER_PROJ: combat treats it as hostile.
    e->x           = FIX8(px);
    e->y           = FIX8(py);
    e->vx          = vx;
    e->vy          = vy;
    e->sprite_tile = SPR_BULLET_B;
    e->palette     = 3;
    e->hp          = 1;
    e->state_timer = 110;
    e->hitbox      = (6 << 4) | 6;
    e->damage      = damage;
    return idx;
}

u8 projectile_spawn_enemy(i16 px, i16 py, i8 dx, i8 dy, u8 damage) BANKED {
    return projectile_spawn_enemy_v(
        px, py, (i8)((i16)dx * 2), (i8)((i16)dy * 2), damage);
}

void projectile_spawn_enemy_cross(i16 px, i16 py, u8 damage) BANKED {
    projectile_spawn_enemy_v(px, py, 0, -1, damage);
    projectile_spawn_enemy_v(px, py, 1, 0, damage);
    projectile_spawn_enemy_v(px, py, 0, 1, damage);
    projectile_spawn_enemy_v(px, py, -1, 0, damage);
}
