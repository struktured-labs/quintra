#ifndef QUINTRA_GAME_OATH_ARTS_H
#define QUINTRA_GAME_OATH_ARTS_H

#include <gb/gb.h>
#include "core/types.h"

#define OATH_ART_COUNT 9
#define OATH_MP_COST 1
#define OATH_COOLDOWN 96

// Pack UX: stage victories unlock arts in campaign order; Up/Down selects
// one of the verbs already earned this run.
void oath_arts_draw_pack(void) BANKED;
u8 oath_arts_pack_input(u8 pressed) BANKED;

// Invoke the selected art toward an 8-way direction. Returns nonzero only
// when an unlocked art actually committed its world action.
u8 oath_arts_fire(u8 dir) BANKED;

#endif
