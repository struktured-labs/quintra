#ifndef QUINTRA_GAME_PROCGEN_SPAWN_H
#define QUINTRA_GAME_PROCGEN_SPAWN_H

#include "core/types.h"

// Cold wide-field placement lives outside procgen's tight fixed bank.
void procgen_place_wide_enemies(u8 formation) BANKED;

#endif
