#include <gb/gb.h>

#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "render/hud.h"
#include "render/tiles.h"

u8 pickup_spawn(u8 kind, fix8_t x, fix8_t y) {
    u8 idx = entity_spawn(ENT_PICKUP);
    if (idx == 0xFF) return 0xFF;
    {
        entity_t *e = &entities[idx];
        e->x = x;
        e->y = y;
        e->vx = e->vy = 0;
        e->ai_data[0] = kind;
        e->hitbox     = (6 << 4) | 6;
        e->damage     = 0;
        e->hp         = 1;
        e->state_timer = 240;    // despawn after 4 seconds
        switch (kind) {
            case PICKUP_HEART_HALF:
                e->sprite_tile = SPR_HEART;
                e->palette     = 0x04;   // OBJ palette 4 (heart red)
                break;
            case PICKUP_COIN_1:
            case PICKUP_COIN_5:
            default:
                e->sprite_tile = SPR_COIN;
                e->palette     = 0x05;   // OBJ palette 5 (coin gold)
                break;
        }
    }
    return idx;
}

void pickup_roll_drop(fix8_t x, fix8_t y) {
    u8 r = rng_next_u8();
    if      (r < 0x4C) pickup_spawn(PICKUP_HEART_HALF, x, y);   // 30%
    else if (r < 0xCD) pickup_spawn(PICKUP_COIN_1,     x, y);   // 50%
    // else: no drop (20%)
}

void pickup_update(entity_t *e, u8 idx) {
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;
    // No movement; pickups sit still.
}

u8 pickup_check_player_collision(void) {
    u8 i;
    u8 any = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type != ENT_PICKUP)   continue;
        if (aabb_overlap_player(&entities[i])) {
            switch (entities[i].ai_data[0]) {
                case PICKUP_HEART_HALF:
                    if (player.hp < player.hp_max) {
                        player.hp = (u8)(player.hp + 1);
                        if (player.hp > player.hp_max) player.hp = player.hp_max;
                        hud_redraw_hp();
                    }
                    break;
                case PICKUP_COIN_1:
                    if (player.coins < 999) player.coins++;
                    hud_redraw_coins();
                    break;
                case PICKUP_COIN_5:
                    player.coins = (u16)(player.coins + 5);
                    if (player.coins > 999) player.coins = 999;
                    hud_redraw_coins();
                    break;
            }
            entity_kill(i);
            any = 1;
        }
    }
    return any;
}
