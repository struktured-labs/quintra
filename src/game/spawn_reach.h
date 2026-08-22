#ifndef QUINTRA_GAME_SPAWN_REACH_H
#define QUINTRA_GAME_SPAWN_REACH_H

#include "core/types.h"

// Temporarily marks the player's strictly-walkable tile component in bit 7.
void mark_spawn_reachable(void) BANKED;
void clear_spawn_reachable(void) BANKED;

// Move a pixel-space reward origin onto the nearest safe 16x16 footprint in
// that component. This is deliberately a cold, major-treasure path: ordinary
// enemy coins already originate from reachable enemies and must not pay for a
// whole-room flood in the middle of combat.
u8 snap_reward_to_reachable(i16 *px, i16 *py) BANKED;

// Cold wrapper used by the shared pickup constructor. Classification and
// pixel/fixed conversion live beside the flood rather than consuming the
// nearly-full pickup bank for a path used only by authored major treasure.
void snap_major_pickup_to_reachable(u8 kind, fix8_t *x, fix8_t *y) BANKED;

#endif
