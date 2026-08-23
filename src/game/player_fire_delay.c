#pragma bank 13

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/status.h"
#include "content.h"

// Starter cadence is authored as the no-upgrade baseline. SPD earned during
// the run removes two frames per point, with a six-frame floor so turbo fire
// stays controllable and attack-speed relics have an obvious payoff.
u8 player_fire_delay(u8 base) BANKED {
    u8 start_spd;
    u8 effective_spd;
    u8 haste;
    if (player.class_id >= N_CLASSES) return base;
    start_spd = classes[player.class_id].base_stats.spd;
    // Wolfkin's +20% movement passive is pre-applied to SPD, but is not a
    // free attack-speed relic. Treat that point as part of Fang Forms'
    // authored baseline so only run-earned speed shortens its combo cadence.
    if (player.class_id == 0 && classes[0].passive_perk == 1) start_spd++;
    effective_spd = STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_SPD) : player.spd;
    haste = (effective_spd > start_spd)
        ? (u8)(effective_spd - start_spd) : 0;
    haste = (u8)(haste << 1);
    return (base > (u8)(haste + 6)) ? (u8)(base - haste) : 6;
}
