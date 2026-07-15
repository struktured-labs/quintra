// Deterministic on-cartridge room, landmark, and encounter generation.
#ifndef QUINTRA_GAME_PROCGEN_H
#define QUINTRA_GAME_PROCGEN_H


#include <gb/gb.h>
#include "core/types.h"

// Identity of the currently generated room. Entry presentation reads this
// explicit state instead of an undocumented HRAM scratch byte.
extern u8 procgen_current_room_is_boss;

// Compute the per-room RNG seed from (run_seed, biome, room_counter).
// Must match the reference impl in quintra-procgen if/when we pin it.
u32 procgen_room_seed(u32 run_seed, u8 biome_id, u8 room_counter) BANKED;

// Build the room_tilemap + spawn enemies for the current run_state.
// Uses run_state.entered_from to position the player near the opposite door.
void procgen_generate_current_room(void) BANKED;

#endif
