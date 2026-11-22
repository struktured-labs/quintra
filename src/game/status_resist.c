#pragma bank 24
#include <gb/gb.h>
#include "core/rng.h"
#include "core/types.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/run_state.h"
#include "game/status.h"

BANKREF(status_tick_gate)

const u8 status_class_resist_kind[5] = {
    QSTATUS_BLEED,
    QSTATUS_BRITTLE,
    QSTATUS_BLIND,
    QSTATUS_BURN,
    QSTATUS_POISON
};

/* 0xFF = shrugged the identity ailment. Otherwise the duration after
 * the 25% cut, Easy half, 24-tick floor, and max re-apply. */
u8 status_resist_adjust(u8 kind, u8 ticks) BANKED {
    u8 identity;

    identity = (player.class_id < 5)
        && (kind == status_class_resist_kind[player.class_id]);
    if (identity) {
        if (rng_range(100) < 50) return 0xFF;
        ticks = (u8)(ticks - (ticks >> 2));
    }
    if (RUN_IS_EASY() && kind != QSTATUS_REGEN && kind != QSTATUS_HASTE)
        ticks = (u8)((ticks + 1) >> 1);
    if (identity) {
        if (ticks < 24) ticks = 24;
        if (player_status_kind == kind && player_status_ticks > ticks)
            ticks = player_status_ticks;
    }
    return ticks;
}

void status_tick_gate(void) BANKED {
    if (status_apply_req) {
        u8 req = status_apply_req;
        status_apply_req = 0;
        status_player_apply(req, 0);
    }
    if (player_status_kind != QSTATUS_NONE || status_enemy_active
        || powerup_id || powerup_world_live || confusion_immune)
        status_tick();
    else
        status_clock++;
}
