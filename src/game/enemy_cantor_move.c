#pragma bank 8

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"

// The spent caller's four-way recovery lives in the expansion bank: each
// banked enemy_try_step call is intentionally expensive on SDCC, while the
// summoner bank must retain its emergency free-space floor.
void enemy_cantor_evade(entity_t *e) BANKED {
    i16 ex = FIX8_TO_INT(e->x);
    i16 ey = FIX8_TO_INT(e->y);
    i8 dx = ex < (i16)player.x ? -1 : 1;
    i8 dy = ey < (i16)player.y ? -1 : 1;
    // A spent caller normally withdraws from the champion. Inside the outer
    // two-tile band that vector can point into one corner forever, so move
    // inward until there is enough field to resume the evasive rule.
    if (ex < 32 || ey < 32
        || ex + 32 >= (i16)room_world_width
        || ey + 32 >= (i16)room_world_height) {
        dx = (i8)-dx;
        dy = (i8)-dy;
    }
    if (e->ai_data[4] & 8) {
        if (!enemy_try_step(e, dx, 0)
            && !enemy_try_step(e, 0, dy)
            && !enemy_try_step(e, 0, (i8)-dy))
            (void)enemy_try_step(e, (i8)-dx, 0);
    } else if (!enemy_try_step(e, 0, dy)
        && !enemy_try_step(e, dx, 0)
        && !enemy_try_step(e, (i8)-dx, 0)) {
        (void)enemy_try_step(e, 0, (i8)-dy);
    }
}
