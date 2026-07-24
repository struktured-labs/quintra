#pragma bank 6

#include "audio/sfx.h"
#include "game/enemy_ai.h"
#include "game/enemy_mirror.h"
#include "game/player.h"
#include "game/projectile.h"

// Frost Vault mirror predator. It samples controller-produced hero movement,
// steps along the inverse vector, then sends a slow bolt back toward the hero.
// Standing still freezes translation but not its firing clock.
void mirror_moth_update(entity_t *e, u8 fire_rate) BANKED {
    u8 px = (u8)player.x, py = (u8)player.y;
    i8 dx = 0, dy = 0;
    if (e->ai_data[4] == 0) {
        e->ai_data[2] = px;
        e->ai_data[3] = py;
        e->ai_data[4] = 1;
    } else {
        i16 ddx = (i16)px - e->ai_data[2];
        i16 ddy = (i16)py - e->ai_data[3];
        // Ignore room-transition jumps; genuine movement is at most 2px.
        if (ddx >= -3 && ddx <= 3) dx = ddx > 0 ? -1 : ddx < 0 ? 1 : 0;
        if (ddy >= -3 && ddy <= 3) dy = ddy > 0 ? -1 : ddy < 0 ? 1 : 0;
        e->ai_data[2] = px;
        e->ai_data[3] = py;
        if (++e->ai_data[5] >= 3) {
            e->ai_data[5] = 0;
            if (dx) enemy_try_step(e, dx, 0);
            if (dy) enemy_try_step(e, 0, dy);
        }
    }
    if (++e->ai_data[1] >= fire_rate) {
        i16 cx = FIX8_TO_INT(e->x) + 4;
        i16 cy = FIX8_TO_INT(e->y) + 4;
        i8 vx = player.x > cx ? 1 : player.x < cx ? -1 : 0;
        i8 vy = player.y > cy ? 1 : player.y < cy ? -1 : 0;
        e->ai_data[1] = 0;
        if (!vx && !vy) vy = -1;
        projectile_spawn_enemy_v(cx, cy, vx, vy, e->damage);
        sfx_play(SFX_FIRE);
    }
}
