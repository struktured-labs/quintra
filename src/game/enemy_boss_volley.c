#pragma bank 9

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"

static u8 volley_aim(i16 cx, i16 cy) {
    i8 sx = ((i16)player.x > cx) ? 1 : ((i16)player.x < cx) ? -1 : 0;
    i8 sy = ((i16)player.y > cy) ? 1 : ((i16)player.y < cy) ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 0;
}

static void volley_shot(i16 x, i16 y, u8 d, i8 speed, u8 damage) {
    projectile_spawn_enemy_v(x, y,
        (i8)(dir8_dx[d] * speed), (i8)(dir8_dy[d] * speed), damage);
}

void boss_volley_tick(entity_t *e) BANKED {
    u8 d, k;
    u8 damage = e->damage > 3 ? 3 : e->damage;
    u8 cadence;
    i16 cx = FIX8_TO_INT(e->x) + 12;
    i16 cy = FIX8_TO_INT(e->y) + 12;
    if (!damage) damage = 1;

    switch (e->ai_data[2]) {
        case 1: // Serpent: aimed fangs plus a counter-rotating tail wake.
            d = volley_aim(cx, cy);
            volley_shot(cx, cy, d, 3, damage);
            volley_shot(cx, cy, (u8)((d + 1) & 7), 2, damage);
            volley_shot(cx, cy, (u8)((d + 7) & 7), 2, damage);
            d = (u8)(e->ai_data[5] & 7);
            cx = serpent_tail_x[serpent_tail_visible];
            cy = serpent_tail_y[serpent_tail_visible];
            volley_shot(cx, cy, d, 1, damage);
            volley_shot(cx, cy, (u8)((d + 4) & 7), 2, damage);
            cadence = 30;
            break;
        case 3: // Spider: alternating cardinal/diagonal web.
            for (d = (u8)(e->ai_data[5] & 1); d < 8; d = (u8)(d + 2))
                volley_shot(cx, cy, d, 2, damage);
            cadence = 44;
            break;
        case 4: // Mire: six mixed-speed scatter lanes.
            for (k = 0; k < 6; ++k)
                volley_shot(cx, cy, (u8)rng_range(8),
                    (i8)(1 + rng_range(3)), damage);
            cadence = 34;
            break;
        case 5: // Reaper: three-shot burst, then a real pause.
            volley_shot(cx, cy, volley_aim(cx, cy), 3, damage);
            e->ai_data[4]++;
            if (e->ai_data[4] < 3) {
                e->ai_data[1] = 8;
                e->ai_data[5]++;
                return;
            }
            e->ai_data[4] = 0;
            cadence = 72;
            break;
        case 6: // Golem: slow, heavy complete ring.
            for (d = 0; d < 8; ++d) volley_shot(cx, cy, d, 1, damage);
            cadence = 58;
            break;
        case 7: // Hydra: five streams stacked at three distinct speeds.
            d = volley_aim(cx, cy);
            volley_shot(cx, cy, d, 1, damage);
            volley_shot(cx, cy, d, 2, damage);
            volley_shot(cx, cy, d, 3, damage);
            volley_shot(cx, cy, (u8)((d + 1) & 7), 2, damage);
            volley_shot(cx, cy, (u8)((d + 7) & 7), 2, damage);
            cadence = 30;
            break;
        case 8: // Void Lord: World Collapse, one announced safe pocket.
            if (!e->ai_data[4]) {
                e->ai_data[4] = 1;
                e->ai_data[5] = (player.x >= (ROOM_COLOSSUS_W_PX >> 1)) ? 1 : 0;
                e->ai_data[5] |= (u8)(rng_next_u8() & 2);
                cadence = 132;
            } else {
                static const u8 safe_x[4] = { 20,188,20,188 };
                static const u8 safe_y[4] = { 20,20,100,100 };
                i16 dx = (i16)player.x - safe_x[e->ai_data[5] & 3];
                i16 dy = (i16)player.y - safe_y[e->ai_data[5] & 3];
                u8 blast = (u8)(damage + 1);
                if (dx < 0) dx = -dx;
                if (dy < 0) dy = -dy;
                room_shake(3, 40);
                for (d = 0; d < 8; ++d) volley_shot(cx, cy, d, 3, damage);
                if ((u16)(dx + dy) > 20 && !player.shield_timer) {
                    if (RUN_IS_EASY()) blast = 1;
                    player.hp = player.hp > blast ? (u8)(player.hp - blast) : 0;
                    player.iframes = 60;
                    hud_redraw_hp();
                    sfx_play(SFX_DEATH);
                } else sfx_play(SFX_CLEAR);
                e->ai_data[4] = 0;
                cadence = 150;
            }
            break;
        case 0: // Crystal: classic full ring plus one aimed lane.
        default:
            for (d = 0; d < 8; ++d) volley_shot(cx, cy, d, 2, damage);
            volley_shot(cx, cy, volley_aim(cx, cy), 2, damage);
            cadence = 55;
            break;
    }

    if (e->ai_data[2] != 8) e->ai_data[5]++;
    if (cadence > 34 && e->hp < (u8)(e->ai_data[6] >> 1))
        cadence = (u8)(cadence - 18);
    e->ai_data[1] = cadence;
}
