#ifndef GAME_ENTITY_DRAW_RUN_H
#define GAME_ENTITY_DRAW_RUN_H
#include <gb/gb.h>
#include "core/types.h"

// See entity_draw_run.c (compact-room renderer only).
extern u8 edr_i, edr_rot, edr_oam;
void entity_draw_run(void) BANKED __naked;

#endif
