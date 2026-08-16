#pragma bank 7

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/room.h"
#include "render/tiles.h"

// Feeding is split from the Colossus movement dispatcher because SDCC's
// signed 16-bit comparisons expand heavily. Keeping the two phases in
// separate existing banks preserves the 128 KiB cartridge layout.
void serpent_feed_tick(entity_t *e) BANKED {
    static const u8 food_x[4] = { 184, 28, 176, 44 };
    static const u8 food_y[4] = { 24, 92, 96, 28 };
    u8 growth = e->ai_data[4];
    i16 dx, dy, ax, ay;
    i8 sx, sy;

    // Redraw a short-lived mote rather than reserving a logical entity for
    // the whole fight; the rotating bullet hell keeps its projectile slots.
    if ((((u8)e->vx) & 15) == 0)
        fx_spawn(SPR_FX_MUZZLE, 2, food_x[growth], food_y[growth], 12);
    e->vx = (i8)((u8)e->vx + 1);
    if (++e->state_timer < 2) return;
    e->state_timer = 0;
    dx = (i16)food_x[growth] - (FIX8_TO_INT(e->x) + 12);
    dy = (i16)food_y[growth] - (FIX8_TO_INT(e->y) + 12);
    ax = dx < 0 ? -dx : dx; ay = dy < 0 ? -dy : dy;
    if (ax < 7 && ay < 7) {
        fx_spawn(SPR_FX_IMPACT, 2, food_x[growth], food_y[growth], 14);
        e->ai_data[4] = ++growth;
        serpent_tail_visible = (u8)(2 + growth + (growth << 1));
        e->ai_data[7] = 8;
        sfx_play(SFX_HEART);
        if (growth == 4) {
            e->state = 1; e->vx = 96; e->vy = 0; e->state_timer = 0;
            room_shake(1, 12); sfx_play(SFX_ROAR);
        }
        return;
    }
    sx = dx > 0 ? 1 : dx < 0 ? -1 : 0;
    sy = dy > 0 ? 1 : dy < 0 ? -1 : 0;
    // Three corrective beats and one counter-step create a visible wiggle
    // while the dominant axis keeps advancing toward the next meal.
    if (ax >= ay) {
        if (sx) enemy_try_step(e, sx, 0);
        if (sy) enemy_try_step(e, 0, ((u8)e->vy & 3) ? sy : -sy);
    } else {
        if (sy) enemy_try_step(e, 0, sy);
        if (sx) enemy_try_step(e, ((u8)e->vy & 3) ? sx : -sx, 0);
    }
    e->vy = (i8)((u8)e->vy + 1);
}
