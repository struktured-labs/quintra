#pragma bank 7

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/room.h"
#include "render/hud.h"
#include "render/tiles.h"

u8 pickup_try_phoenix_revive(void) BANKED {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i) {
        if (player.inventory[i] == ITEM_ID_PHOENIX_THREAD) {
            player.inventory[i] = 0xFF;
            player.hp = (u8)((player.hp_max + 1) >> 1);
            player.iframes = 120;
            hud_redraw_hp();
            room_shake(2, 18);
            fx_spawn(SPR_SURGE_ORB, 0x05,
                (i16)player.x + 4, (i16)player.y - 8, 32);
            sfx_play(SFX_CLEAR);
            return 1;
        }
    }
    return 0;
}
