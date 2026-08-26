#pragma bank 14

#include <gb/gb.h>

#include "audio/sfx.h"
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

static void crawler_shot(i16 cx, i16 cy, u8 d, u8 speed,
    u8 damage, u8 palette) {
    u8 shot = projectile_spawn_enemy_v(cx, cy,
        (i8)(dir8_dx[d] * speed), (i8)(dir8_dy[d] * speed), damage);
    if (shot != 0xFF) {
        entities[shot].state_timer = speed == 1 ? 170 : 105;
        entities[shot].palette = palette;
    }
}

void blue_crawler_pattern_tick(entity_t *e, u8 idx) BANKED {
    u8 clock;
    u8 d;
    i16 cx;
    i16 cy;

    // ai_data[4] is a one-based stable cast identity. Derive it from spawn
    // position and slot without consuming procgen RNG; otherwise adding these
    // projectiles would silently reshuffle every later room decision.
    if (e->ai_data[4] == 0) {
        e->ai_data[4] = (e->flags & (EF_ELITE | EF_ALPHA)) ? 3
            : (u8)(1 + ((idx + (u8)(FIX8_TO_INT(e->x) >> 3)
                + (u8)(FIX8_TO_INT(e->y) >> 3)) % 3));
        e->ai_data[3] = (u8)((idx * 29
            + (u8)FIX8_TO_INT(e->x) + (u8)FIX8_TO_INT(e->y)) % 120);
        return;
    }

    clock = (u8)(e->ai_data[3] + 1);
    e->ai_data[3] = clock;
    cx = FIX8_TO_INT(e->x) + 4;
    cy = FIX8_TO_INT(e->y) + 4;

    if (e->ai_data[4] == 1) {
        // Blue dart: a quicker single aimed lane, easy to read and sidestep.
        if (clock < 145) return;
        e->ai_data[3] = 0;
        d = weak_aim_dir(cx, cy);
        crawler_shot(cx, cy, d, 2, e->damage, 3);
        return;
    }
    if (e->ai_data[4] == 2) {
        // Fuzzy fan: three slow adjacent lanes that linger longer than dart.
        if (clock < 175) return;
        e->ai_data[3] = 0;
        d = weak_aim_dir(cx, cy);
        crawler_shot(cx, cy, (u8)((d + 7) & 7), 1, e->damage, 6);
        crawler_shot(cx, cy, d, 1, e->damage, 6);
        crawler_shot(cx, cy, (u8)((d + 1) & 7), 1, e->damage, 6);
        return;
    }

    // Viral pulse: a warning flash, then cardinals and diagonals ten frames
    // apart. Across the two readable beats it fills all eight radial lanes
    // without exhausting half the entity table in one invisible instant.
    if (clock == 150) {
        e->ai_data[7] = 8;
        sfx_play(SFX_TICK);
    } else if (clock == 160) {
        for (d = 0; d < 8; d = (u8)(d + 2))
            crawler_shot(cx, cy, d, 1, e->damage, 4);
    } else if (clock >= 170) {
        for (d = 1; d < 8; d = (u8)(d + 2))
            crawler_shot(cx, cy, d, 1, e->damage, 4);
        e->ai_data[3] = 0;
    }
}
