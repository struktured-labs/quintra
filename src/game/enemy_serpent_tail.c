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
    u8 *trail;
    u8 cx = (u8)(FIX8_TO_INT(e->x) + 12);
    u8 cy = (u8)(FIX8_TO_INT(e->y) + 12);
    u8 dx = (cx > serpent_tail_x[0])
        ? (u8)(cx - serpent_tail_x[0]) : (u8)(serpent_tail_x[0] - cx);
    u8 dy = (cy > serpent_tail_y[0])
        ? (u8)(cy - serpent_tail_y[0]) : (u8)(serpent_tail_y[0] - cy);

    if (e->state == 0) {
        u8 target = (u8)(2 + e->ai_data[4] * 12);
        if (target > SERPENT_TAIL_MAX) target = SERPENT_TAIL_MAX;
        if (serpent_tail_visible < target && !(entity_anim_counter & 3)) {
            serpent_tail_visible++;
            serpent_body_dirty = 1;
        }
    }
    if ((u16)(dx + dy) >= 8) {
        trail = serpent_tail_x + SERPENT_TAIL_MAX;
        for (i = SERPENT_TAIL_MAX; i; --i, --trail) *trail = *(trail-1);
        trail = serpent_tail_y + SERPENT_TAIL_MAX;
        for (i = SERPENT_TAIL_MAX; i; --i, --trail) *trail = *(trail-1);
        serpent_tail_x[0] = cx;
        serpent_tail_y[0] = cy;
        serpent_body_dirty = 1;
    }

}

void serpent_tail_contact(void) BANKED {
    u8 i, count, cx, cy, dx, dy, tx, ty;
    u8 *xs = serpent_tail_x + 1, *ys = serpent_tail_y + 1;
    if (!serpent_tail_active) return;
    if (player.iframes || player.shield_timer) return;
    if (serpent_head_index >= MAX_ENTITIES
        || entities[serpent_head_index].type != ENT_ENEMY
        || !(entities[serpent_head_index].flags & EF_ACTIVE)) return;
    cx = (u8)(player.x + 8);
    cy = (u8)(player.y + 12);
    count = serpent_tail_visible;
    if (count >= serpent_tail_count) count = serpent_tail_count - 1;
    for (i = count; i; --i, ++xs, ++ys) {
        tx = (*xs & 0xF8) + 4;
        dx = (u8)(cx - tx + 7);
        if (dx >= 15) continue;
        ty = (*ys & 0xF8) + 4;
        dy = (u8)(cy - ty + 7);
        if (dy < 15) {
            player.hp = player.hp ? (u8)(player.hp - 1) : 0;
            player.iframes = 24;
            hud_redraw_hp();
            room_shake(1, 10);
            sfx_play(SFX_HURT);
            return;
        }
    }
}
