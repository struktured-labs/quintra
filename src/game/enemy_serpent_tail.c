#pragma bank 8

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/room.h"
#include "render/hud.h"

u8 serpent_tail_x[SERPENT_TAIL_POINTS];
u8 serpent_tail_y[SERPENT_TAIL_POINTS];
u8 serpent_tail_count;
u8 serpent_tail_visible;
u8 serpent_tail_active;
u8 serpent_head_index;
extern u8 entity_anim_counter;

void serpent_tail_update(entity_t *e) BANKED {
    u8 i;
    u8 cx = (u8)(FIX8_TO_INT(e->x) + 12);
    u8 cy = (u8)(FIX8_TO_INT(e->y) + 12);
    u8 dx = (cx > serpent_tail_x[0])
        ? (u8)(cx - serpent_tail_x[0]) : (u8)(serpent_tail_x[0] - cx);
    u8 dy = (cy > serpent_tail_y[0])
        ? (u8)(cy - serpent_tail_y[0]) : (u8)(serpent_tail_y[0] - cy);

    if (e->state == 0) {
        u8 target = (u8)(2 + e->ai_data[4] + (e->ai_data[4] << 1));
        if (serpent_tail_visible < target && !(entity_anim_counter & 3))
            serpent_tail_visible++;
    }
    // Eight-pixel sampling stretches fourteen scales across 112 route pixels
    // while keeping adjacent 8x8 art edge-connected. The inner loop therefore
    // reaches back into the previous ring instead of collapsing beside the head.
    if ((u16)(dx + dy) >= 8) {
        for (i = SERPENT_TAIL_POINTS - 1; i != 0; --i) {
            serpent_tail_x[i] = serpent_tail_x[i - 1];
            serpent_tail_y[i] = serpent_tail_y[i - 1];
        }
        serpent_tail_x[0] = cx;
        serpent_tail_y[0] = cy;
    }

}

void serpent_tail_contact(void) BANKED {
    u8 i, cx, cy, dx, dy;
    if (!serpent_tail_active) return;
    // The articulated body is a passable but damaging ribbon. Combining the
    // scale's four-pixel radius with the champion's centered hurtbox requires
    // a wider test than point contact; adjacent eight-pixel samples overlap.
    if (player.iframes || player.shield_timer) return;
    cx = (u8)(player.x + 8);
    cy = (u8)(player.y + 12);
    for (i = 1; i <= serpent_tail_visible && i < serpent_tail_count; ++i) {
        dx = (cx > serpent_tail_x[i])
            ? (u8)(cx - serpent_tail_x[i]) : (u8)(serpent_tail_x[i] - cx);
        dy = (cy > serpent_tail_y[i])
            ? (u8)(cy - serpent_tail_y[i]) : (u8)(serpent_tail_y[i] - cy);
        if (dx < 10 && dy < 10) {
            player.hp = player.hp ? (u8)(player.hp - 1) : 0;
            player.iframes = 24;
            hud_redraw_hp();
            room_shake(1, 10);
            sfx_play(SFX_HURT);
            return;
        }
    }
}
