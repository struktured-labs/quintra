#pragma bank 3

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"
#include "render/tiles.h"

// Procgen places counters; this module owns deterministic stock identity,
// payload, art, and prices.
static u8 market_weapon(void) {
    u8 count = pickup_weapon_count();
    u8 pick;
    if (count < 2) return player.starter_weapon;
    pick = pickup_weapon_from_roll((u8)(count - 2
        + (((u8)run_state.run_seed ^ run_state.bosses_beaten) & 1)));
    return (pick == player.starter_weapon) ? pickup_next_weapon(pick) : pick;
}

void pickup_configure_shop_ware(u8 idx, u8 ware) BANKED {
    if (ware == WARE_WEAPON) entities[idx].ai_data[3] = market_weapon();
    else if (ware == WARE_ITEM) {
        entities[idx].ai_data[3] = pickup_farfold_relic_for_class(
            (u8)((run_state.run_seed >> 8) ^ run_state.bosses_beaten));
    }
    entities[idx].sprite_tile = (ware == WARE_HEART) ? SPR_HEART
        : (ware == WARE_SURGE || ware == WARE_ASCEND)
            ? SPR_SURGE_ORB : SPR_ITEM_ORB;
    entities[idx].palette = (ware == WARE_ITEM || ware == WARE_FORGE
            || ware == WARE_PHOENIX) ? 0x05
        : (ware == WARE_SURGE || ware == WARE_RUNE
            || ware == WARE_CHART || ware == WARE_ASCEND
            || ware == WARE_ECHO) ? 0x06 : 0x04;
}

u8 pickup_dungeon_featured_ware(u8 shelf) BANKED {
    static const u8 build_wares[4] = {
        WARE_VAMP, WARE_WEAPON, WARE_GLASS, WARE_ECHO,
    };
    static const u8 tactical_wares[4] = {
        WARE_SURGE, WARE_CHART, WARE_PHOENIX, WARE_ASCEND,
    };
    u8 roll = (u8)((u8)run_state.run_seed ^ run_state.bosses_beaten);
    if (shelf) return tactical_wares[(u8)((roll >> 2) & 3)];
    return build_wares[roll & 3];
}

u8 pickup_dungeon_ware_price(u8 ware) BANKED {
    if (ware == WARE_CHART) return 15;
    if (ware == WARE_ASCEND) return 18;
    if (ware == WARE_SURGE || ware == WARE_GLASS) return 20;
    if (ware == WARE_PHOENIX || ware == WARE_VAMP
        || ware == WARE_BIG) return 35;
    return 30;
}
