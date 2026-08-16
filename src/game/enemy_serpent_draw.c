#pragma bank 5

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/room.h"

extern u8 entity_anim_counter;

void serpent_draw(void) BANKED {
    entity_t *e;
    u8 oam = 4;
    u8 r, c, segment, pal, flash, head_pal, tail_pal;
    i16 sx, sy;
    if (!serpent_tail_active || serpent_head_index >= MAX_ENTITIES) return;
    e = &entities[serpent_head_index];
    if (!(e->flags & EF_ACTIVE) || !(e->flags & EF_ON_SCREEN)) return;
    pal = e->palette;
    flash = e->ai_data[7] ? 1 : 0;
    if (flash) e->ai_data[7]--;
    // Damage and feeding feedback tint the hood instead of parking all twelve
    // sprites at (0,0). The former disappearance was real cartridge flicker;
    // palette zero gives the hit a readable lightning-white pulse instead.
    head_pal = (flash && (e->ai_data[7] & 1)) ? 0 : pal;
    tail_pal = (e->ai_data[4] >= 4 && (entity_anim_counter & 0x10)) ? 0 : pal;
    sx = FIX8_TO_INT(e->x) - room_camera_x + 8;
    sy = FIX8_TO_INT(e->y) - room_camera_y + 16;

    // A broad cobra head, not the generic square 4x4 Colossus frame.
    for (r = 0; r < 3; ++r) {
        for (c = 0; c < 4; ++c) {
            set_sprite_tile(oam, (u8)(e->sprite_tile + r * 4 + c));
            set_sprite_prop(oam, head_pal);
            move_sprite(oam, (u8)(sx + c * 8), (u8)(sy + r * 8));
            oam++;
        }
    }

    // Overlapping, spiked scales follow sampled head positions. Each meal
    // exposes four more (then two for the final meal); contraction hides them
    // from the rear. At full growth a pale pulse telegraphs the wider aura.
    for (segment = 1;
         segment <= serpent_tail_visible && segment < serpent_tail_count;
         ++segment) {
        sx = (i16)serpent_tail_x[segment] - room_camera_x;
        sy = (i16)serpent_tail_y[segment] - room_camera_y;
        if (sx < -7 || sx >= ROOM_VIEW_W_PX
            || sy < -7 || sy >= ROOM_VIEW_H_PX) continue;
        set_sprite_tile(oam, ((segment + (entity_anim_counter >> 3)) & 1)
            ? (u8)(e->sprite_tile + 12) : (u8)(e->sprite_tile + 13));
        set_sprite_prop(oam, tail_pal);
        move_sprite(oam, (u8)(sx + 4), (u8)(sy + 12));
        oam++;
    }
    while (oam < 32) move_sprite(oam++, 0, 0);
}
