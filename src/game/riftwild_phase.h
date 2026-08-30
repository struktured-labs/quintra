#ifndef QUINTRA_GAME_RIFTWILD_PHASE_H
#define QUINTRA_GAME_RIFTWILD_PHASE_H

#include <gb/gb.h>
#include "core/types.h"

// Waking/Hollow counterpart systems. Worldglass shifts only in Riftwild and
// owns its complete blocking transition, so ordinary room frames pay one
// short input predicate and no animation/update cost.
void riftwild_load_world_palettes(u8 dim) BANKED;
u8 riftwild_shift_execute(u8 keys, u8 pressed) BANKED;
void riftwild_prepare_hollow_field(void) BANKED;
void riftwild_harden_enemy(u8 idx, u8 spawn_ordinal) BANKED;
u8 riftwild_claim_hollow_relic(u8 item_id, u8 claim_bit) BANKED;

#endif
