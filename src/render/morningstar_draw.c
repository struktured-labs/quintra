#pragma bank 26
#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "render/tiles.h"

u8 morningstar_draw(entity_t *e, u8 oam, u8 x, u8 y) BANKED {
    u8 i, pal, tile, px, py, links, n;
    i16 hx, hy, sx, sy, lx, ly;
    pal = e->palette;
    tile = SPR_ITEM_MORNINGSTAR_BIG;
    for (i = 0; i < 4 && oam < entity_oam_cap; ++i) {
        px = x + ((i & 1) ? 4 : (u8)-4);
        py = y + ((i & 2) ? 4 : (u8)-4);
        set_sprite_tile(oam, (u8)(tile + i));
        set_sprite_prop(oam, pal);
        if (((i & 1) || x >= 4) && ((i & 2) || y >= 4)
            && px < 168 && py < 152)
            move_sprite(oam, px, py);
        else
            move_sprite(oam, 0, 0);
        oam++;
    }
    // Full-Will (tier 3) shows two chain links; tier 2 shows one. Visual only.
    links = 0;
    if (e->ai_data[7] >= 3) links = 2;
    else if (e->ai_data[7] >= 2) links = 1;
    if (links) {
        hx = (i16)x;
        hy = (i16)y;
        sx = (i16)player.x - (i16)room_camera_x + 12;
        sy = (i16)player.y - (i16)room_camera_y + 20;
        // Midpoint (tier 2+) and quarter (tier 3) links, shifts only.
        n = (u8)(links >= 2 ? 2 : 1);
        for (; n >= 1 && oam < entity_oam_cap; --n) {
            lx = sx + ((hx - sx) >> n);
            ly = sy + ((hy - sy) >> n);
            set_sprite_tile(oam, SPR_BULLET);
            set_sprite_prop(oam, 6);
            if (lx > 0 && lx < 168 && ly > 0 && ly < 152)
                move_sprite(oam, (u8)lx, (u8)ly);
            else
                move_sprite(oam, 0, 0);
            oam++;
        }
    }
    return oam;
}
