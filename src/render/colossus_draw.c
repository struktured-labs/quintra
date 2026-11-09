#pragma bank 12
#include <gb/gb.h>
#include "game/entity.h"

// Square and 24x24 colossi. One banked call replaces 27 or 48 sprite-API
// calls. Crystal and the Sun Golem select their bank-1 poses here.
u8 colossus_oam_draw(u8 oam, u8 sx, u8 sy, u8 tile, u8 pal, u8 side,
    const entity_t *e, u8 hide) BANKED {
    OAM_item_t *it = &shadow_OAM[oam];
    u8 r, c;
    // Bank-1 OBJ 128..143. Hexa owns BG 40..55 and OBJ 88..127,
    // large-boss poses own 64..87, and vertical shots own 208..213.
    if (side == 4 && e->ai_data[2] == 0
        && ((e->ai_data[3] & 0x40) || e->x_pad
            || (e->vx > 0 && e->vx <= 18)
            || (entity_anim_counter & 16))) {
        pal |= 0x08;
        tile = 128;
    } else if (side == 4 && e->ai_data[2] == 6 && (entity_anim_counter & 16)) {
        pal |= 0x08;
        tile = 128;
    }
    for (r = 0; r < side; ++r) {
        u8 py = hide ? 0 : (u8)(sy + (r << 3));
        for (c = 0; c < side; ++c) {
            it->y = py;
            it->x = hide ? 0 : (u8)(sx + (c << 3));
            it->tile = tile++;
            it->prop = pal;
            ++it;
            ++oam;
        }
    }
    return oam;
}
