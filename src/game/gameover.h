#ifndef QUINTRA_GAME_GAMEOVER_H
#define QUINTRA_GAME_GAMEOVER_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

void        gameover_enter(void);
void        gameover_exit(void);
screen_id_t gameover_tick(u8 keys, u8 pressed);
void        gameover_draw(void);

#endif
