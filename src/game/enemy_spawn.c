#pragma bank 14

#include <gb/gb.h>

#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "content.h"

// Spawn-only initializer owned by the feature bank. Keeping the declaration
// private avoids making every translation unit depend on this cold hook.
void enemy_patrol_init(entity_t *e, u8 enemy_content_id) BANKED;
u8 status_enemy_summon_blocked(void) BANKED;

u8 enemy_spawn(u8 enemy_content_id, u8 tile_x, u8 tile_y) BANKED {
    u8 idx;
    entity_t *e;
    if (enemy_content_id >= N_ENEMIES) return 0xFF;
    // Mute shuts down an enemy's reinforcement spell but never its movement
    // or contact body. Procgen has no active actor and remains unaffected.
    if (status_enemy_summon_blocked()) return 0xFF;
    idx = entity_spawn(ENT_ENEMY);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    {
        const enemy_def_t *def = &enemies[enemy_content_id];
        e->x           = FIX8((i16)tile_x * 8);
        e->y           = FIX8((i16)tile_y * 8);
        e->vx = e->vy  = 0;
        e->sprite_tile = def->sprite_set;
        e->palette     = def->palette;
        e->hp          = def->stats.hp;
        e->damage      = def->stats.damage;
        e->ai_data[0]  = enemy_content_id;
        // CounterGuard's state byte is a shell machine, not a heading.
        e->state       = (u8)(rng_next_u8() & 0x07);
        if (def->ai_kind == AI_COUNTER_GUARD || def->ai_kind == AI_SUMMONER)
            e->state = 0;
        e->state_timer = 30;
        if (enemy_content_id >= ENEMY_FACET_RAM) {
            enemy_patrol_init(e, enemy_content_id);
            return idx;
        }
        if (enemy_content_id == ENEMY_FLUTTERBAT) {
            e->hitbox = (u8)0xAA;
        } else if (enemy_content_id == ENEMY_CINDER_MAW) {
            e->hitbox = (u8)0x8D;
        } else if (enemy_content_id == ENEMY_STONE_SENTINEL
            || enemy_content_id == ENEMY_ORC
            || enemy_content_id == ENEMY_BOMBER
            || enemy_content_id == ENEMY_WARLOCK) {
            e->hitbox = (u8)0xDD;
        } else {
            e->hitbox = (6 << 4) | 6;
        }
    }
    return idx;
}
