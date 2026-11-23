#ifndef QUINTRA_GAME_ENEMY_BUBBLE_H
#define QUINTRA_GAME_ENEMY_BUBBLE_H

#include "core/types.h"
#include "game/entity.h"

void bubble_tick(entity_t *e) BANKED;
void tiles_load_bubble_sprite(void) BANKED;
u8 bubble_reject_hit(u8 shot_idx, u8 enemy_idx) BANKED;

#endif
