#ifndef QUINTRA_GAME_MAP_H
#define QUINTRA_GAME_MAP_H
#include "core/types.h"
#include "game/screen.h"
void map_enter(void);
void map_exit(void);
screen_id_t map_tick(u8 keys, u8 pressed);
void map_draw(void);
#endif
