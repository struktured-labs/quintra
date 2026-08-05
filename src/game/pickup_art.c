#pragma bank 3
#include <gb/gb.h>

#include "core/types.h"
#include "game/pickup.h"
#include "render/tiles.h"
#include "content.h"

u8 pickup_item_sprite(u8 item_index) BANKED {
    u16 id = item_index < N_ITEMS ? items[item_index].id : 0xFFFFu;
    // Authored passive IDs 20..29 and OBJ glyphs 131..140 are both
    // contiguous contracts. Preserve content-table reorder safety without a
    // ten-arm SDCC switch in the crowded pickup-runtime bank.
    if (id >= 20u && id <= 29u)
        return (u8)(SPR_ITEM_IRON_HEART + (u8)(id - 20u));
    return (item_index < N_ITEMS && items[item_index].kind == ITEM_KIND_WEAPON)
        ? SPR_ITEM_WEAPON : SPR_ITEM_POWER_STONE;
}
