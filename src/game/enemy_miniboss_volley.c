#pragma bank 15
// Mini-boss volleys. Kept out of bank 2 so that bank keeps its emergency floor
// after the Hexa Dragmar dispatch.

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"

static u8 aim_dir8(i16 cx, i16 cy) {
    i8 sx = ((i16)player.x > cx) ? 1 : ((i16)player.x < cx) ? -1 : 0;
    i8 sy = ((i16)player.y > cy) ? 1 : ((i16)player.y < cy) ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 0;
}

static void boss_shot(i16 cx, i16 cy, u8 d, i8 spd, u8 dmg) {
    projectile_spawn_enemy_v(cx, cy, (i8)(dir8_dx[d] * spd), (i8)(dir8_dy[d] * spd), dmg);
}

void miniboss_volley_fire(entity_t *e) BANKED {
    u8 dmg = e->damage;
    u8 d, k;
    i16 cx = FIX8_TO_INT(e->x) + 8;
    i16 cy = FIX8_TO_INT(e->y) + 8;
    u8 cadence;
    switch (e->ai_data[2]) {
        case 1:
            d = aim_dir8(cx, cy);
            boss_shot(cx, cy, d, 3, dmg);
            boss_shot(cx, cy, (u8)((d + 1) & 7), 3, dmg);
            boss_shot(cx, cy, (u8)((d + 7) & 7), 3, dmg);
            cadence = 46;
            break;
        case 2:
            for (d = 0; d < 8; ++d) boss_shot(cx, cy, d, 2, dmg);
            cadence = 90;
            break;
        case 3:
            for (k = 0; k < 4; ++k)
                boss_shot(cx, cy, (u8)((e->ai_data[5] * 3 + k * 2) & 7), 2, dmg);
            cadence = 34;
            break;
        case 4:
            d = aim_dir8(cx, cy);
            boss_shot(cx, cy, d, 2, dmg);
            boss_shot(cx, cy, (u8)((d + 1) & 7), 2, dmg);
            boss_shot(cx, cy, (u8)((d + 7) & 7), 2, dmg);
            boss_shot(cx, cy, (u8)((d + 2) & 7), 2, dmg);
            boss_shot(cx, cy, (u8)((d + 6) & 7), 2, dmg);
            cadence = 58;
            break;
        case 0:
        default:
            for (d = (u8)(e->ai_data[5] & 1); d < 8; d = (u8)(d + 2))
                boss_shot(cx, cy, d, 2, dmg);
            cadence = 70;
            break;
    }
    if (e->ai_data[2] != 8) e->ai_data[5]++;
    if (cadence > 34 && e->hp < (u8)(e->ai_data[6] >> 1))
        cadence = (u8)(cadence - 18);
    e->ai_data[1] = cadence;
}
