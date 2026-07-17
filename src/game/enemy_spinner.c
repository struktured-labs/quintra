#pragma bank 5

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "content.h"

// ai_p0 is the desired manhattan radius; ai_p1 is the volley cadence.
// The compact behavior lives in bank 5, keeping the shared enemy dispatcher
// and the fixed bank-2 budget available for the rest of combat.
void spinner_update(entity_t *e, const enemy_def_t *def) BANKED {
    i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
    i16 dx = (i16)player.x - ex, dy = (i16)player.y - ey;
    i16 ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
    i16 distance = ax + ay;
    i8 mx = 0, my = 0;
    u8 clockwise = e->ai_data[3] & 1;

    if (++e->state_timer >= 3) {
        e->state_timer = 0;
        if (distance > (i16)def->ai_p0 + 12) {
            if (ax >= ay) mx = dx > 0 ? 1 : -1;
            else my = dy > 0 ? 1 : -1;
        } else if (distance + 12 < def->ai_p0) {
            if (ax >= ay) mx = dx > 0 ? -1 : 1;
            else my = dy > 0 ? -1 : 1;
        } else if (ax >= ay) {
            my = (dx > 0) == clockwise ? 1 : -1;
        } else {
            mx = (dy > 0) == clockwise ? -1 : 1;
        }
        if (!enemy_try_step(e, mx, my)) {
            e->ai_data[3] ^= 1;
            if (mx) mx = -mx;
            else my = -my;
            enemy_try_step(e, mx, my);
        }
    }

    if (e->ai_data[1] == 0) {
        u8 d = e->ai_data[2] & 7;
        projectile_spawn_enemy_v(ex + 4, ey + 4,
            (i8)(dir8_dx[d] * 2), (i8)(dir8_dy[d] * 2), e->damage);
        d = (u8)((d + 4) & 7);
        projectile_spawn_enemy_v(ex + 4, ey + 4,
            (i8)(dir8_dx[d] * 2), (i8)(dir8_dy[d] * 2), e->damage);
        e->ai_data[2] = (u8)((e->ai_data[2] + 1) & 7);
        e->ai_data[1] = def->ai_p1;
        sfx_play(SFX_TICK);
    } else {
        e->ai_data[1]--;
    }
}
