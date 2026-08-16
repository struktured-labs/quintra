#ifndef QUINTRA_GAME_DUNGEON_TOOLS_H
#define QUINTRA_GAME_DUNGEON_TOOLS_H

#include <gb/gb.h>
#include "core/types.h"

void dungeon_tools_draw_pack(void) BANKED;
// 0 = no action, 1 = screen redrawn, 2 = charge consumed and room requested.
u8 dungeon_tools_pack_input(u8 pressed) BANKED;
void dungeon_tools_apply_pending(void) BANKED;

#endif
