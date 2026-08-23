#pragma bank 6

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"

// Context, not a purchase: reveal the nearest ware's price before the player
// touches it. Kept outside pickup.c so its dense collision/update bank retains
// enough emergency cartridge headroom for the Road Echo dispatch.
u8 pickup_nearby_shop_offer(u8 *ware_out, u8 *price_out) BANKED {
    u8 i, found = 0, best_distance = 0xFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 dx, dy;
        u8 distance;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_PICKUP
            || entities[i].ai_data[0] != PICKUP_SHOP) continue;
        dx = FIX8_TO_INT(entities[i].x) - (i16)player.x;
        dy = FIX8_TO_INT(entities[i].y) - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if (dx > 32 || dy > 32) continue;
        distance = (u8)(dx + dy);
        if (!found || distance < best_distance) {
            best_distance = distance;
            *ware_out = entities[i].ai_data[1];
            *price_out = entities[i].ai_data[2];
            found = 1;
        }
    }
    return found;
}
