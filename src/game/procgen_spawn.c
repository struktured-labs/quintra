#pragma bank 1

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/procgen_spawn.h"
#include "game/run_state.h"

// Twenty non-overlapping, body-valid anchors span the central cross and both
// guaranteed-open distant aprons. Late Normal districts can reach 18 bodies,
// so a 16-slot table made the final two silently stack on earlier monsters.
// Steps 1/3/7/9 are each coprime with 20: every formation visits every anchor
// exactly once without consuming or perturbing combat RNG.
void procgen_place_wide_enemies(u8 formation) BANKED {
    static const u8 spawn_x[20] = {
        72, 72, 72, 24, 120, 176, 216, 176, 216, 120,
        168, 216, 192, 224, 192, 224, 72, 72, 144, 192,
    };
    static const u8 spawn_y[20] = {
        24, 112, 200, 64, 64, 64, 64, 40, 40, 152,
        152, 152, 200, 200, 224, 224, 176, 224, 160, 160,
    };
    static const u8 steps[4] = { 1, 3, 7, 9 };
    u8 idx;
    u8 sector = (u8)run_state.run_seed;
    u8 step = steps[formation & 3];
    while (sector >= 20) sector = (u8)(sector - 20);
    for (idx = 0; idx < MAX_ENTITIES; ++idx) {
        if (!(entities[idx].flags & EF_ACTIVE)
            || entities[idx].type != ENT_ENEMY) continue;
        entities[idx].x = FIX8(spawn_x[sector]);
        entities[idx].y = FIX8(spawn_y[sector]);
        sector = (u8)(sector + step);
        if (sector >= 20) sector = (u8)(sector - 20);
    }
}
