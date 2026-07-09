#ifndef QUINTRA_GAME_VICTORY_H
#define QUINTRA_GAME_VICTORY_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

void        victory_enter(void);
void        victory_exit(void);
screen_id_t victory_tick(u8 keys, u8 pressed);
void        victory_draw(void);

#endif
