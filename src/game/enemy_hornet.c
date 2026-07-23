#pragma bank 6
#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "content.h"

// A Hornet group is a small formation only when the procgen roster has
// naturally placed at least two. The first Hornet stays on the direct pressure
// line; the others take alternating flanks around the champion. A lone Hornet
// returns 0 so enemy_ai.c retains its established direct-chaser behavior.
u8 hornet_swarm_tick(entity_t *e, u8 idx) BANKED {
    u8 i, rank = 0, packed = 0;
    i16 tx = (i16)player.x, ty = (i16)player.y;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (i == idx || !(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_ENEMY
            || entities[i].ai_data[0] != ENEMY_HORNET) continue;
        packed = 1;
        if (i < idx) rank++;
    }
    if (!packed) return 0;

    // Wingmates alternate upper-right and lower-left, forming a readable curl
    // rather than visually stacking on the player-facing leader.
    if (rank & 1) { tx += 12; ty -= 8; }
    else if (rank) { tx -= 12; ty += 8; }
    if ((++e->state_timer & 1) == 0) {
        i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
        i8 sx = (tx > ex) ? 1 : (tx < ex) ? -1 : 0;
        i8 sy = (ty > ey) ? 1 : (ty < ey) ? -1 : 0;
        if (sx) enemy_try_step(e, sx, 0);
        if (sy) enemy_try_step(e, 0, sy);
    }
    return 1;
}
