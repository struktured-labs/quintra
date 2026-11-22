#ifndef QUINTRA_GAME_BOMB_WALL_H
#define QUINTRA_GAME_BOMB_WALL_H

#include <gb/gb.h>
#include "core/types.h"

/* Seed-stable: is this local dungeon cell one of the 2-3 bomb-wall hosts? */
u8 bomb_wall_is_host(u8 local) BANKED;
/* After procgen + puzzle prepare: stamp or restore the room's bomb wall. */
void bomb_wall_prepare_room(void) BANKED;
/* If (tx,ty) is a bomb wall (or the +1 tile of its pair), open it. */
u8 bomb_wall_try_open(u8 tx, u8 ty) BANKED;
/* Echo Chime / Cave Light: glint only, never open. */
void bomb_wall_chime(void) BANKED;

#endif
