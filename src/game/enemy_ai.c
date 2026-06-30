#include <gb/gb.h>

#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/room.h"
#include "render/tiles.h"
#include "content.h"

// State byte for Walker AI: low nibble = direction (0-7), high nibble unused.

// Map content enemy_id to OBJ tile slot in VRAM.
static u8 sprite_for_enemy(u8 enemy_content_id) {
    switch (enemy_content_id) {
        case 0: return SPR_ENEMY_CRAWLER;
        case 1: return SPR_BOSS;
        case 2: return SPR_ENEMY_HORNET;
        case 3: return SPR_ENEMY_SKELETON;
        case 4: return SPR_ENEMY_ORC;
        default: return SPR_ENEMY_CRAWLER;
    }
}

u8 enemy_spawn(u8 enemy_content_id, u8 tile_x, u8 tile_y) {
    u8 idx;
    entity_t *e;
    if (enemy_content_id >= N_ENEMIES) return 0xFF;
    idx = entity_spawn(ENT_ENEMY);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    {
        const enemy_def_t *def = &enemies[enemy_content_id];
        e->x           = FIX8((i16)tile_x * 8);
        e->y           = FIX8((i16)tile_y * 8);
        e->vx = e->vy  = 0;
        e->sprite_tile = sprite_for_enemy(enemy_content_id);
        e->palette     = def->palette;
        e->hp          = def->stats.hp;
        e->damage      = def->stats.damage;
        e->ai_data[0]  = enemy_content_id;
        e->state       = (u8)(rng_next_u8() & 0x07);
        e->state_timer = 30;
        e->hitbox      = (6 << 4) | 6;
    }
    return idx;
}

// Walker AI: pick a random 8-dir, walk for N ticks, repeat.
// (Phase 5 placeholder — Phase 7 will dispatch on def->ai_script.)
static void walker_tick(entity_t *e) {
    if (e->state_timer == 0) {
        e->state       = (u8)(rng_next_u8() & 0x07);
        e->state_timer = (u8)(20 + (rng_next_u8() & 0x1F));
    }
    e->state_timer--;

    {
        i8 dx = dir8_dx[e->state & 0x07];
        i8 dy = dir8_dy[e->state & 0x07];
        // Slow movement — 1 px per 4 ticks
        if ((e->state_timer & 0x03) == 0) {
            fix8_t nx = (fix8_t)(e->x + FIX8(dx));
            fix8_t ny = (fix8_t)(e->y + FIX8(dy));
            // Don't walk off the room
            {
                i16 ix = FIX8_TO_INT(nx);
                i16 iy = FIX8_TO_INT(ny);
                if (ix >= 8 && ix < (i16)((ROOM_W - 1) * 8)
                    && iy >= 8 && iy < (i16)((ROOM_H - 1) * 8)) {
                    e->x = nx;
                    e->y = ny;
                } else {
                    // Hit edge — pick a new direction next tick
                    e->state_timer = 0;
                }
            }
        }
    }
}

void enemy_update(entity_t *e, u8 idx) {
    idx;
    // Phase 5: every enemy uses Walker. Phase 7 dispatches on def->ai_script.
    walker_tick(e);
}
