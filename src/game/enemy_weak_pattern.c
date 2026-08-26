#pragma bank 14

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"

static u8 weak_aim_dir(i16 cx, i16 cy) {
    i8 sx = ((i16)player.x > cx) ? 1 : ((i16)player.x < cx) ? -1 : 0;
    i8 sy = ((i16)player.y > cy) ? 1 : ((i16)player.y < cy) ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 0;
}

static void weak_pattern_shot(i16 cx, i16 cy, u8 d, u8 damage) {
    u8 shot = projectile_spawn_enemy_v(cx, cy,
        dir8_dx[d], dir8_dy[d], damage);
    if (shot != 0xFF) {
        // Penta-style pressure comes from slow lanes that remain relevant,
        // not from turning starter creatures into twitch snipers.
        entities[shot].state_timer = 180;
        entities[shot].palette = 4;
    }
}

void weak_pattern_tick(entity_t *e, u8 salt) BANKED {
    u8 phase = (u8)(entity_anim_counter + (u8)(salt * 29));
    u8 d;
    i16 cx;
    i16 cy;
    // One wrap per 256 frames per body, with prime-ish spawn/slot staggering. A
    // visible pack builds a steady field instead of one entity-cap burst.
    if (phase == 12 && e->ai_data[7] == 0) e->ai_data[7] = 12;
    if (phase != 0) return;
    cx = FIX8_TO_INT(e->x) + 4;
    cy = FIX8_TO_INT(e->y) + 4;
    d = weak_aim_dir(cx, cy);
    weak_pattern_shot(cx, cy, (u8)((d + 7) & 7), e->damage);
    weak_pattern_shot(cx, cy, d, e->damage);
    weak_pattern_shot(cx, cy, (u8)((d + 1) & 7), e->damage);
}
