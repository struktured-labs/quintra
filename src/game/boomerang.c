#pragma bank 255

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/projectile.h"
#include "render/tiles.h"

static u8 owned(void) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == ITEM_ID_BOOMERANG) return 1;
    return 0;
}

static u8 fetches(u8 kind) {
    return kind == PICKUP_HEART_HALF || kind == PICKUP_COIN_1
        || kind == PICKUP_COIN_5 || kind == PICKUP_ITEM
        || kind == PICKUP_MP || kind == PICKUP_SURGE;
}

u8 projectile_throw_boomerang(u8 dir) BANKED {
    u8 i;
    entity_t *e;
    if (!owned()) return 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PROJECTILE
            && entities[i].ai_data[6] == PROJ_AUX_BOOMERANG) return 1;
    }
    i = entity_spawn(ENT_PROJECTILE);
    if (i == 0xFF) return 0;
    e = &entities[i];
    dir &= 7;
    e->flags |= EF_PLAYER_PROJ;
    e->x = FIX8((i16)player.x + 4);
    e->y = FIX8((i16)player.y + 4);
    e->vx = (i8)(dir8_dx[dir] * 3);
    e->vy = (i8)(dir8_dy[dir] * 3);
    e->sprite_tile = SPR_ITEM_BOOMERANG;
    e->palette = 6;
    e->hp = 255;
    e->state_timer = 120;
    e->hitbox = 0x77;
    e->ai_data[0] = 18;
    e->ai_data[2] = 1;
    e->ai_data[6] = PROJ_AUX_BOOMERANG;
    sfx_play_boomerang(0);
    return 1;
}

void projectile_update_boomerang(entity_t *e, u8 idx) BANKED {
    u8 i;
    i16 dx, dy;
    if (!e->state && e->ai_data[0] && --e->ai_data[0] == 0)
        e->state = 1;
    if (e->state) {
        dx = (i16)player.x + 4 - FIX8_TO_INT(e->x);
        dy = (i16)player.y + 4 - FIX8_TO_INT(e->y);
        if (dx >= -6 && dx <= 6 && dy >= -6 && dy <= 6) {
            entity_kill(idx);
            fx_spawn(SPR_FX_IMPACT, 6,
                (i16)player.x + 4, (i16)player.y + 4, 6);
            sfx_play_boomerang(1);
            return;
        }
        e->vx = dx > 0 ? 3 : dx < 0 ? -3 : 0;
        e->vy = dy > 0 ? 3 : dy < 0 ? -3 : 0;
    }
    e->ai_data[7]++;
    switch ((e->ai_data[7] >> 1) & 3) {
        case 1: e->ai_data[4] = PROJ_VIS_FLIP_X; break;
        case 2: e->ai_data[4] = PROJ_VIS_FLIP_X | PROJ_VIS_FLIP_Y; break;
        case 3: e->ai_data[4] = PROJ_VIS_FLIP_Y; break;
        default: e->ai_data[4] = 0; break;
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *loot = &entities[i];
        if (!(loot->flags & EF_ACTIVE) || loot->type != ENT_PICKUP
            || !fetches(loot->ai_data[0]) || !aabb_overlap_ee(e, loot))
            continue;
        loot->x = FIX8((i16)player.x + 4);
        loot->y = FIX8((i16)player.y + 4);
    }
}
