#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

#define PROJECTILE_SPEED  4    // px/tick
#define PROJECTILE_TTL    60   // ticks before despawn (1 second)
#define PROJECTILE_DAMAGE 2

u8 projectile_spawn_player(i8 dx, i8 dy) {
    u8 idx;
    entity_t *e;
    if (dx == 0 && dy == 0) return 0xFF;
    idx = entity_spawn(ENT_PROJECTILE);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    e->flags      |= EF_PLAYER_PROJ;
    e->x           = (fix8_t)(player.x + FIX8(2));
    e->y           = (fix8_t)(player.y + FIX8(2));
    e->vx          = (i8)((i16)dx * PROJECTILE_SPEED);
    e->vy          = (i8)((i16)dy * PROJECTILE_SPEED);
    e->sprite_tile = SPR_BULLET;
    e->palette     = 2;                  // OBJ palette 2 (item-gold accent)
    e->hp          = 1;                  // pierce = 1 enemy
    e->state_timer = PROJECTILE_TTL;
    e->hitbox      = (4 << 4) | 4;       // 4×4 hitbox
    e->damage      = PROJECTILE_DAMAGE;
    return idx;
}

void projectile_update(entity_t *e, u8 idx) {
    // Despawn after TTL or off-screen / on wall
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;

    e->x = (fix8_t)(e->x + FIX8(0) + ((i16)e->vx << 4));   // velocity in 4.4
    e->y = (fix8_t)(e->y + FIX8(0) + ((i16)e->vy << 4));

    {
        i16 px = FIX8_TO_INT(e->x);
        i16 py = FIX8_TO_INT(e->y);
        if (px < 8 || px > (ROOM_W * 8 - 8)
            || py < 8 || py > (ROOM_H * 8 - 8)) {
            entity_kill(idx);
            return;
        }
    }
}
