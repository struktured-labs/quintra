#pragma bank 11

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "render/tiles.h"

// Full-growth warning rings travel through three meaningful points on the
// articulated creature. This is visual feedback for the imminent AOE and
// makes the concentric scale motif move rather than remain surface decoration.
void serpent_storm_pulse(entity_t *e) BANKED {
    u8 segment;
    e->ai_data[7] = 6;
    if (e->vy) {
        segment = (e->vy == 1)
            ? (u8)(serpent_tail_visible >> 1) : serpent_tail_visible;
        fx_spawn(SPR_SHIELD_AURA, 2, serpent_tail_x[segment],
            serpent_tail_y[segment], 8);
    } else fx_spawn(SPR_SHIELD_AURA, 2, FIX8_TO_INT(e->x) + 12,
            FIX8_TO_INT(e->y) + 12, 8);
    if (++e->vy >= 3) e->vy = 0;
}
