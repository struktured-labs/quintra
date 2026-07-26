#pragma bank 7

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

static u8 ware_owned(u8 ware) {
    u8 item = ware == WARE_PHOENIX ? ITEM_ID_PHOENIX_THREAD
        : ware == WARE_ECHO ? ITEM_ID_ECHO_PRISM
        : ware == WARE_RICOCHET ? ITEM_ID_RICOCHET_RUNE
        : ware == WARE_THORN ? ITEM_ID_THORN_CROWN
        : ware == WARE_DRUM ? ITEM_ID_WAR_DRUM
        : ware == WARE_FLASK ? ITEM_ID_MOON_FLASK : 0xFF;
    u8 i;
    if (item == 0xFF) return 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == item) return 1;
    return 0;
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
            || ware == WARE_PHOENIX || ware == WARE_DRUM) ? 0x05
        : (ware == WARE_SURGE || ware == WARE_RUNE
            || ware == WARE_CHART || ware == WARE_ASCEND
            || ware == WARE_ECHO || ware == WARE_RICOCHET
            || ware == WARE_FLASK) ? 0x06 : 0x04;
}

u8 pickup_dungeon_featured_ware(u8 shelf) BANKED {
    static const u8 build_wares[6] = {
        WARE_VAMP, WARE_WEAPON, WARE_GLASS, WARE_ECHO,
        WARE_RICOCHET, WARE_THORN,
    };
    static const u8 tactical_wares[6] = {
        WARE_SURGE, WARE_CHART, WARE_PHOENIX, WARE_ASCEND,
        WARE_DRUM, WARE_FLASK,
    };
    u8 roll = (u8)((u8)run_state.run_seed ^ run_state.bosses_beaten);
    u8 pick, tries = 0;
    // Six-by-six catalog: contiguous low-byte seeds enumerate every pair.
    // If a unique relic is already carried, walk forward within that shelf
    // so a later merchant never wastes its interesting counter on a dead
    // duplicate.
    if (shelf) {
        pick = (u8)((roll / 6) % 6);
        while (tries++ < 6 && ware_owned(tactical_wares[pick]))
            pick = (u8)((pick + 1) % 6);
        return tactical_wares[pick];
    }
    pick = (u8)(roll % 6);
    while (tries++ < 6 && ware_owned(build_wares[pick]))
        pick = (u8)((pick + 1) % 6);
    return build_wares[pick];
}

u8 pickup_dungeon_ware_price(u8 ware) BANKED {
    if (ware == WARE_CHART) return 15;
    if (ware == WARE_ASCEND) return 18;
    if (ware == WARE_SURGE || ware == WARE_GLASS
        || ware == WARE_FLASK) return 20;
    if (ware == WARE_DRUM || ware == WARE_RICOCHET) return 28;
    if (ware == WARE_PHOENIX || ware == WARE_VAMP
        || ware == WARE_BIG || ware == WARE_THORN) return 35;
    return 30;
}
