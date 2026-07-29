#pragma bank 3
// Projectile suffix dispatcher. The always-mapped prefix scans ordinary
// rooms; once it finds a shot or visual effect, the rest of that same scan
// moves here so both hot updates are direct same-bank calls.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"

// Internal bank-3 entry point from projectile.c. It deliberately is not part
// of the cross-bank public API.
void projectile_update_one(entity_t *e, u8 idx);
void entity_update_nonprojectile(u8 idx);

static void fx_update_one(entity_t *e, u8 idx) {
    if (e->state_timer == 0) {
        entity_kill(idx);
        return;
    }
    e->state_timer--;
}

void entity_update_from(u8 start) BANKED {
    u8 i;
    for (i = start; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type == ENT_PROJECTILE)
            projectile_update_one(&entities[i], i);
        else if (entities[i].type == ENT_FX)
            fx_update_one(&entities[i], i);
        else
            entity_update_nonprojectile(i);
    }
}
