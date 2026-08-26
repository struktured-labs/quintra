#ifndef QUINTRA_GAME_TITLE_H
#define QUINTRA_GAME_TITLE_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

// 0xFF for an ordinary run, otherwise the zero-based destination selected
// through the hidden title-screen Rift Index. RUN_INIT consumes this after
// class/difficulty selection so the normal hero flow remains authoritative.
extern u8 title_stage_warp;

void        title_enter(void);
void        title_exit(void);
screen_id_t title_tick(u8 keys, u8 pressed);
void        title_draw(void);

void        title_cheat_reset(void) BANKED;
u8          title_cheat_code_input(u8 key) BANKED;
void        title_cheat_begin(void) BANKED;
screen_id_t title_cheat_tick(u8 pressed) BANKED;

#endif
