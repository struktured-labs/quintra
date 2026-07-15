#ifndef QUINTRA_GAME_ENEMY_SPORE_H
#define QUINTRA_GAME_ENEMY_SPORE_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

void mire_spore_update(entity_t *e, u8 trigger_radius, u8 fuse_ticks) BANKED;

#endif
