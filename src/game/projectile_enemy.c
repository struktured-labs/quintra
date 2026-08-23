#pragma bank 7
// Enemy-shot constructors are called at authored firing beats, not once per
// active bullet per frame. Keep them out of bank 3 so its hot projectile
// updater has development headroom.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "game/status.h"
#include "render/tiles.h"

// Core spawn with an explicit px/tick velocity — lets bosses mix bullet speeds
// (thin-fast streams vs. slow dense walls) within one pattern.
u8 projectile_spawn_enemy_v(i16 px, i16 py, i8 vx, i8 vy, u8 damage) BANKED {
    u8 idx;
    u8 actor_kind = QSTATUS_NONE;
    u8 source_id = 0;
    entity_t *e;
    if (vx == 0 && vy == 0) return 0xFF;
    if (status_enemy_actor < MAX_ENTITIES) {
        actor_kind = enemy_status_kind[status_enemy_actor];
        if (actor_kind == QSTATUS_MUTE) return 0xFF;
        if (actor_kind == QSTATUS_BLIND
            && ((entity_anim_counter + status_enemy_actor) & 1)) {
            i8 old_vx = vx;
            vx = vy;
            vy = (i8)-old_vx;
        }
        if (actor_kind == QSTATUS_INVERSION
            && enemy_status_aux[status_enemy_actor] == QSTATUS_INVERT_DAMAGE
            && damage > 1)
            damage = (u8)((damage + 1) >> 1);
        // Store source enemy ID + 1. Status bank 13 turns it into an authored
        // payload only on contact, keeping this already-nested volley path in
        // bank 7 and leaving zero as the unconditioned projectile sentinel.
        source_id = (u8)(entities[status_enemy_actor].ai_data[0] + 1);
    }
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
    e->ai_data[5] = source_id;
    if (actor_kind == QSTATUS_CONFUSION) {
        e->ai_data[4] |= PROJ_HOSTILE_CONFUSED;
        e->palette = 6;
        status_confused_projectiles = 1;
    }
    return idx;
}

u8 projectile_spawn_enemy(i16 px, i16 py, i8 dx, i8 dy, u8 damage) BANKED {
    return projectile_spawn_enemy_v(
        px, py, (i8)((i16)dx * 2), (i8)((i16)dy * 2), damage);
}
