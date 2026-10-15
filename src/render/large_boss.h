#ifndef QUINTRA_LARGE_BOSS_H
#define QUINTRA_LARGE_BOSS_H
#include "game/entity.h"
extern u8 large_boss_index;
void large_boss_load(u8 stage) BANKED;
void large_boss_reset(void) BANKED;
u8 large_boss_draw(u8 oam) BANKED;
#endif
