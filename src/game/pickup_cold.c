#pragma bank 10

// Low-frequency world fixtures and temporary-reward constructors. Keeping
// these wrappers out of the combat pickup bank preserves emergency headroom;
// their shared pickup_spawn transaction remains authoritative.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "render/tiles.h"

void pickup_spawn_surge(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_SURGE, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_ITEM_SURGE;
        entities[idx].palette = 0x06;
        entities[idx].state_timer = 255;
    }
}

u8 pickup_spawn_waygear(u8 gear, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_WAYGEAR, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1] = gear;
        entities[idx].sprite_tile = (u8)(SPR_WAYGEAR_GLOVE + gear);
        entities[idx].palette = 0x06;
        entities[idx].state_timer = 255;
        entities[idx].hitbox = 0x88;
    }
    return idx;
}

u8 pickup_spawn_riftwell(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_RIFTWELL, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_SURGE_ORB;
        entities[idx].palette = 0x06;
        entities[idx].hitbox = 0x88;
        entities[idx].state_timer = 0;
    }
    return idx;
}
