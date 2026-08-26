#pragma bank 10
#include <gb/gb.h>

#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "content.h"

// A Flutterbat is visually small, but a sealed combat room must never let it
// fly through an 8px crack into a pocket the champion cannot enter. Require a
// complete 16x16 walkable footprint along every move. Starting positions are
// already chosen from the generated reachable component, so preserving this
// footprint also preserves a real route back to the player.
static u8 flutterbat_space_clear(i16 x, i16 y) {
    if (x < 0 || y < 0 || x > (i16)(room_world_width - 16)
        || y > (i16)(room_world_height - 16)) return 0;
    return room_tile_walkable(room_tile_at_px(x + 1, y + 1))
        && room_tile_walkable(room_tile_at_px(x + 14, y + 1))
        && room_tile_walkable(room_tile_at_px(x + 1, y + 14))
        && room_tile_walkable(room_tile_at_px(x + 14, y + 14));
}

static u8 flutterbat_try_step(entity_t *e, i8 dx, i8 dy) {
    i16 nx = FIX8_TO_INT(e->x) + dx;
    i16 ny = FIX8_TO_INT(e->y) + dy;
    if (!flutterbat_space_clear(nx, ny)) return 0;
    return enemy_try_step(e, dx, dy);
}

// Keese-like cadence: cling motionless, flutter diagonally, dart, settle.
void flutterbat_update(entity_t *e) BANKED {
    // Cache a nonzero spawn-coordinate salt in otherwise-free scratch. Using
    // the live x position would let wall slides accelerate or suppress casts.
    if (e->ai_data[1] == 0)
        e->ai_data[1] = (u8)(FIX8_TO_INT(e->x) + 1);
    if (!RUN_IS_EASY()) weak_pattern_tick(e, e->ai_data[1]);
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
            moved = flutterbat_try_step(e, dx, 0);
            if (flutterbat_try_step(e, 0, dy)) moved = 1;
        } else {
            moved = flutterbat_try_step(e, dx, dy);
        }
        if (!moved) {
            // A blocked odd diagonal must not leave a required Keese clinging
            // forever inside the last legal corner of a sealed room. Take one
            // collision-checked axis beat toward the champion, which is both
            // a readable hunting twitch and a guaranteed attempt to retrace
            // the same full-footprint space from which it entered.
            i16 ex = FIX8_TO_INT(e->x);
            i16 ey = FIX8_TO_INT(e->y);
            i8 hunt_x = player.x > ex ? 1 : player.x < ex ? -1 : 0;
            i8 hunt_y = player.y > ey ? 1 : player.y < ey ? -1 : 0;
            if (hunt_x) moved = flutterbat_try_step(e, hunt_x, 0);
            if (!moved && hunt_y) moved = flutterbat_try_step(e, 0, hunt_y);
            if (!moved) e->state_timer = 0;
        }
    }
}
