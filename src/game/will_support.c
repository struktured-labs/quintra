#pragma bank 11

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/will.h"
#include "render/tiles.h"

void will_begin_signature(void) BANKED {
    u8 cd;
    u8 speed_bonus = (player.spd > 5) ? (u8)((player.spd - 5) * 3) : 0;
    switch (player.class_id) {
        case 0: cd = SIGNATURE_CD_WOLFKIN; break;
        case 1: cd = SIGNATURE_CD_SAURAN;  break;
        case 2: cd = SIGNATURE_CD_CORVIN;  break;
        case 3: cd = SIGNATURE_CD_PICSEAN; break;
        default: cd = SIGNATURE_CD_VESPINE; break;
    }
    // Speed Ring and Swift Fang now change a real decision, not just held-A
    // cadence. Clamp the gain so a stacked run never turns B into autofire.
    player.active_charge = (cd > (u8)(SIGNATURE_CD_MIN + speed_bonus))
        ? (u8)(cd - speed_bonus) : SIGNATURE_CD_MIN;
}

// Howl is the close-range champion's answer to a screen that has become too
// noisy: erase only nearby hostile shots, leaving enemy bodies and distant
// patterns intact. This both creates a readable opening and relieves entity
// pressure instead of answering bullet hell with still more persistent fire.
void will_howl_clear_nearby_shots(void) BANKED {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 dx, dy;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
            || (e->flags & EF_PLAYER_PROJ)) continue;
        dx = (i16)FIX8_TO_INT(e->x) - (i16)player.x;
        dy = (i16)FIX8_TO_INT(e->y) - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if ((u16)dx + (u16)dy <= 52) {
            fx_spawn(SPR_FX_IMPACT, 6,
                (i16)FIX8_TO_INT(e->x), (i16)FIX8_TO_INT(e->y), 5);
            entity_kill(i);
        }
    }
}
