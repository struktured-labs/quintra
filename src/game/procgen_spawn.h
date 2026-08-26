#ifndef QUINTRA_GAME_PROCGEN_SPAWN_H
#define QUINTRA_GAME_PROCGEN_SPAWN_H

#include "core/types.h"

// Cold wide-field placement lives outside procgen's tight fixed bank.
void procgen_place_wide_enemies(u8 formation) BANKED;
// Puzzle fields additionally guarantee one guard in the arrival camera.
void procgen_place_visible_puzzle_guard(void) BANKED;

#endif
