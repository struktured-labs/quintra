#pragma bank 14

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/procgen_spawn.h"
#include "game/room.h"

void procgen_place_visible_puzzle_guard(void) BANKED {
    u8 idx;
    // Every wide dungeon field has a permanent two-tile central cross. Move
    // one existing puzzle guard onto the arm visible from the arrival camera,
    // far enough inward to read as a sentry rather than a doorway collision.
    // The west/north screen uses x=104 rather than the x=120 batch anchor so
    // the body never covers the Aether plate at (16,8).
    i16 px = room_camera_x ? 176 : 104;
    i16 py = room_camera_y ? 176 : 64;
    if (room_camera_y) px = 72;
    for (idx = 0; idx < MAX_ENTITIES; ++idx) {
        if (!(entities[idx].flags & EF_ACTIVE)
            || entities[idx].type != ENT_ENEMY) continue;
        entities[idx].x = FIX8(px);
        entities[idx].y = FIX8(py);
        return;
    }
}
