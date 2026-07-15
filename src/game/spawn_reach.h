#ifndef QUINTRA_GAME_SPAWN_REACH_H
#define QUINTRA_GAME_SPAWN_REACH_H

// Temporarily marks the player's strictly-walkable tile component in bit 7.
void mark_spawn_reachable(void) BANKED;
void clear_spawn_reachable(void) BANKED;

#endif
