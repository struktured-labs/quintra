#pragma bank 24

// Low-frequency world fixtures and temporary-reward constructors. Keeping
// these wrappers out of the combat pickup bank preserves emergency headroom;
// their shared pickup_spawn transaction remains authoritative.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "render/tiles.h"
#include "content.h"

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

// Moved from bank 5 (Antidote PR) to keep the pickup bank's emergency floor.
u8 pickup_spawn_weapon(u8 weapon_index, fix8_t x, fix8_t y) BANKED {
    u8 idx;
    if (weapon_index >= N_ITEMS || items[weapon_index].kind != ITEM_KIND_WEAPON)
        return 0xFF;
    idx = pickup_spawn(PICKUP_WEAPON, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1]  = weapon_index;
        entities[idx].sprite_tile = SPR_ITEM_WEAPON;
        entities[idx].palette     = 0x04;      // red orb = weapon
        entities[idx].state       = 45;        // grace: no instant pickup
    }
    return idx;
}

u8 pickup_spawn_farfold_relic(u8 item_index, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_FARFOLD_RELIC, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1] = item_index;
        entities[idx].sprite_tile = pickup_item_sprite(item_index);
        entities[idx].palette = 0x06;
        entities[idx].hitbox = (u8)0x88;
        // Optional exploration cannot be a four-second reaction test. The
        // cache orb persists until claimed or the player leaves the district.
        entities[idx].state_timer = 0;
    }
    return idx;
}
