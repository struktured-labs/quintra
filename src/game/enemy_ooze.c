#pragma bank 6
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "render/tiles.h"
#include "content.h"

// A Rift Ooze's two crawler fragments are real enemies: kill either before
// their scatter clock ends, or they reverse course and reform a weakened ooze.
// The merge reuses one fragment slot, so it remains safe at the 32-entity cap.
void ooze_fragment_update(entity_t *e, u8 idx) BANKED {
    u8 i;
    if (e->ai_data[1] != 0) {
        e->ai_data[1]--;
        // Scatter in the ordinary crawler cadence before the magnetic return.
        if ((e->ai_data[1] & 3) == 0) {
            i8 dx = dir8_dx[e->state & 7], dy = dir8_dy[e->state & 7];
            if (!enemy_try_step(e, dx, dy)) e->state = (u8)((e->state + 3) & 7);
        }
        return;
    }

    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *other = &entities[i];
        i16 ex, ey, ox, oy;
        i16 dx, dy;
        if (i == idx || !(other->flags & EF_ACTIVE) || other->type != ENT_ENEMY
            || other->ai_data[0] != ENEMY_BLUE_CRAWLER
            || other->ai_data[2] != ENEMY_AUX_OOZE_FRAGMENT) continue;
        ex = FIX8_TO_INT(e->x); ey = FIX8_TO_INT(e->y);
        ox = FIX8_TO_INT(other->x); oy = FIX8_TO_INT(other->y);
        dx = ox - ex; dy = oy - ey;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        // Only the higher-index fragment resolves the merge. This prevents
        // both updates from consuming each other in the same frame.
        if (dx <= 12 && dy <= 12 && idx > i) {
            e->x = FIX8((ex + ox) >> 1);
            e->y = FIX8((ey + oy) >> 1);
            e->ai_data[0] = ENEMY_RIFT_OOZE;
            e->ai_data[1] = e->ai_data[2] = 0;
            e->state = 0;
            e->state_timer = 30;
            e->sprite_tile = enemies[ENEMY_RIFT_OOZE].sprite_set;
            e->palette = enemies[ENEMY_RIFT_OOZE].palette;
            // A reformed ooze is a pressure reset, not a full second boss.
            e->hp = 8;
            e->damage = enemies[ENEMY_RIFT_OOZE].stats.damage;
            e->ai_data[7] = 10;
            entity_kill(i);
            fx_spawn(SPR_FX_IMPACT, 0x05, ex, ey, 14);
            sfx_play(SFX_ROAR);
            return;
        }
        // The pair has found one another. Pull along one axis at a time so
        // their 8px bodies still honor every pillar and corridor.
        if ((e->state_timer++ & 1) == 0) {
            if (dx >= dy) enemy_try_step(e, ox > ex ? 1 : -1, 0);
            else enemy_try_step(e, 0, oy > ey ? 1 : -1);
        }
        return;
    }

    // A lone surviving fragment stays an ordinary small crawler until killed.
    if ((e->state_timer++ & 3) == 0)
        enemy_try_step(e, dir8_dx[e->state & 7], dir8_dy[e->state & 7]);
}
