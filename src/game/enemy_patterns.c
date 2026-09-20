#pragma bank 13

#include "audio/sfx.h"
#include "game/dungeon_director.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/run_state.h"

void enemy_pattern_emit(entity_t *e, u8 direction, u8 palette) BANKED {
    u8 i, hostile = 0, free = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) free++;
        else if (entities[i].type == ENT_PROJECTILE
            && !(entities[i].flags & EF_PLAYER_PROJ)) hostile++;
    }
    if (hostile >= 12 || free <= 4) return;
    i = projectile_spawn_enemy_v(e->x + 6, e->y + 6,
        dir8_dx[direction & 7], dir8_dy[direction & 7], e->damage);
    if (i != 0xFF) {
        entities[i].state_timer = 110;
        entities[i].palette = palette;
    }
}

u8 enemy_return_variant(entity_t *e) BANKED {
    u8 variant = run_state.bosses_beaten % 3;
    i8 dx = player.x > e->x ? 1 : -1;
    i8 dy = player.y > e->y ? 1 : -1;
    if (!variant || room_return_echo_kind < 4) return 0;
    if (e->ai_data[3]) e->ai_data[3]--;
    if (e->ai_data[2] == 0) {
        if ((++e->ai_data[1] & 3) == 0) {
            if (variant == 1) {
                if (!enemy_try_step(e, dy, -dx)) enemy_try_step(e, -dy, dx);
            } else enemy_try_step(e, dx, 0);
        }
        if (!e->ai_data[3]) {
            e->ai_data[4] = (player.x - e->x > 0) ? 2 : 6;
            if ((player.y - e->y > 32) || (e->y - player.y > 32))
                e->ai_data[4] = player.y > e->y ? 4 : 0;
            e->ai_data[2] = 1;
            e->ai_data[3] = 32;
            e->ai_data[7] = 16;
            sfx_play(SFX_TICK);
        }
    } else if (e->ai_data[2] == 1) {
        if (!e->ai_data[3]) {
            e->ai_data[2] = 2;
            e->ai_data[3] = variant == 1 ? 64 : 24;
            sfx_play(SFX_ROAR);
        }
    } else if (e->ai_data[2] == 2) {
        if (variant == 1) {
            if (!(e->ai_data[3] & 7))
                enemy_pattern_emit(e, (u8)(e->ai_data[4]++), 6);
        } else {
            u8 d = e->ai_data[4];
            enemy_try_step(e, dir8_dx[d], dir8_dy[d]);
            enemy_try_step(e, dir8_dx[d], dir8_dy[d]);
            if (!(e->ai_data[3] & 7)) {
                enemy_pattern_emit(e, (u8)(d + 2), 4);
                enemy_pattern_emit(e, (u8)(d + 6), 4);
            }
        }
        if (!e->ai_data[3]) { e->ai_data[2] = 3; e->ai_data[3] = 64; }
    } else if (!e->ai_data[3]) {
        e->ai_data[2] = 0;
        e->ai_data[3] = 96;
    }
    return 1;
}
