#pragma bank 3

#include "audio/sfx.h"
#include "game/enemy_spore.h"
#include "game/player.h"
#include "game/projectile.h"

// state: 0 dormant, 1 armed, 2 recovering. ai_data[1] is the phase clock.
// The fuse flashes through the standard hit-shimmer timer, giving every class
// over half a second to leave one of the eight firing lanes.
void mire_spore_update(entity_t *e, u8 trigger_radius, u8 fuse_ticks) BANKED {
    i16 ex = FIX8_TO_INT(e->x) + 4;
    i16 ey = FIX8_TO_INT(e->y) + 4;
    i16 dx = (i16)player.x - ex;
    i16 dy = (i16)player.y - ey;
    u16 dist;
    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;
    dist = (u16)dx + (u16)dy;

    if (e->state == 0) {
        if (dist <= trigger_radius) {
            e->state = 1;
            e->ai_data[1] = fuse_ticks;
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (e->state == 2) {
        if (e->ai_data[1]) e->ai_data[1]--;
        else e->state = 0;
        return;
    }
    if (e->ai_data[1]) {
        e->ai_data[1]--;
        if ((e->ai_data[1] & 7) == 0) {
            e->ai_data[7] = 5;
            sfx_play(SFX_TICK);
        }
        return;
    }
    {
        static const i8 vx[8] = { 0, 1, 1, 1, 0, -1, -1, -1 };
        static const i8 vy[8] = { -1, -1, 0, 1, 1, 1, 0, -1 };
        u8 i;
        for (i = 0; i < 8; ++i)
            projectile_spawn_enemy_v(ex, ey, vx[i], vy[i], e->damage);
    }
    e->state = 2;
    e->ai_data[1] = 90;
    e->ai_data[7] = 8;
    sfx_play(SFX_FIRE);
}
