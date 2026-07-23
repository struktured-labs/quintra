#pragma bank 6
#include <gb/gb.h>

#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "content.h"

// Keese-like cadence: cling motionless, flutter diagonally, dart, settle.
void flutterbat_update(entity_t *e) BANKED {
    if (e->state_timer == 0) {
        e->state = (u8)((e->state + 1) % 3);
        e->state_timer = (e->state == 0) ? (u8)(28 + (rng_next_u8() & 31))
                       : (e->state == 1) ? (u8)(36 + (rng_next_u8() & 15)) : 14;
        e->ai_data[2] = (u8)(rng_next_u8() | 1); // diagonal direction seed
    }
    e->state_timer--;
    if (e->state == 0) return;
    if ((e->state_timer & ((e->state == 2) ? 1 : 3)) == 0) {
        u8 d = (u8)((e->ai_data[2] + ((e->state_timer >> 2) & 2)) & 7);
        i8 dx = dir8_dx[d], dy = dir8_dy[d];
        u8 moved;
        // Resolve diagonals by axis. A direct diagonal lets this 8px flyer cut
        // across two solid corners into a notch no 12px champion can enter;
        // axis motion keeps the Keese-like slant in open space and slides the
        // bat along either wall when only one component is legal.
        if (dx && dy) {
            moved = enemy_try_step(e, dx, 0);
            if (enemy_try_step(e, 0, dy)) moved = 1;
        } else {
            moved = enemy_try_step(e, dx, dy);
        }
        if (!moved) e->state_timer = 0;
    }
}
