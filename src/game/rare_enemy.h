#ifndef QUINTRA_RARE_ENEMY_H
#define QUINTRA_RARE_ENEMY_H
#include <gb/gb.h>
#include "game/entity.h"
#define EF_RARE 0x80
void rare_enemy_prepare(void) BANKED;
u8 rare_enemy_tick(entity_t *e) BANKED;
#endif
