#pragma bank 15
// Limb quads. Split from the tick bank so the draw can use plain sprite
// calls without crowding the encounter bank.

#include <gb/gb.h>

#include "game/entity.h"
#include "game/hexa_boss.h"

extern i8 hexa_limb_ox[5];
extern i8 hexa_limb_oy[5];
extern u8 hexa_limb_flash[5];

u8 hexa_draw_stamp;

static const u8 limb_x[5] = { 32, 112, 24, 120, 72 };
static const u8 limb_y[5] = { 72, 72, 32, 32, 16 };

u8 hexa_boss_draw(u8 oam) BANKED {
    u8 i;
    if (!hexa_boss_active) return oam;
    if (hexa_core_entity >= MAX_ENTITIES
        || !(entities[hexa_core_entity].flags & EF_ACTIVE)) {
        hexa_boss_active = 0;
        return oam;
    }
    for (i = 0; i < 5; ++i) {
        u8 pose = (hexa_limb_state[i] == HEXA_LIMB_TELEGRAPH
                   || hexa_limb_state[i] == HEXA_LIMB_ACTIVE) ? 4 : 0;
        u8 base = (u8)(HEXA_LIMB_TILE + (i * 8) + pose);
        u8 pal = (hexa_spotlight_limb == i) ? 6 : 5;
        u8 sx = (u8)((i16)limb_x[i] + hexa_limb_ox[i] + 8);
        u8 sy = (u8)((i16)limb_y[i] + hexa_limb_oy[i] + 16);
        u8 s0;
        if (hexa_limb_state[i] == HEXA_LIMB_BROKEN) sy = (u8)(sy + 4);
        if (hexa_limb_flash[i] && (hexa_limb_flash[i] & 1) == 0)
            pal = (hexa_limb_state[i] == HEXA_LIMB_TELEGRAPH) ? 7 : 0;
        pal |= 0x08;
        s0 = oam;
        move_sprite(s0, sx, sy);
        move_sprite((u8)(s0 + 1), (u8)(sx + 8), sy);
        move_sprite((u8)(s0 + 2), sx, (u8)(sy + 8));
        move_sprite((u8)(s0 + 3), (u8)(sx + 8), (u8)(sy + 8));
        set_sprite_tile(s0, base);
        set_sprite_tile((u8)(s0 + 1), (u8)(base + 1));
        set_sprite_tile((u8)(s0 + 2), (u8)(base + 2));
        set_sprite_tile((u8)(s0 + 3), (u8)(base + 3));
        set_sprite_prop(s0, pal);
        set_sprite_prop((u8)(s0 + 1), pal);
        set_sprite_prop((u8)(s0 + 2), pal);
        set_sprite_prop((u8)(s0 + 3), pal);
        oam = (u8)(s0 + 4);
    }
    hexa_draw_stamp++;
    return oam;
}
