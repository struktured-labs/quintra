#ifndef QUINTRA_GAME_INVENTORY_COPY_H
#define QUINTRA_GAME_INVENTORY_COPY_H

#include "core/types.h"

// Draw the weapon reminder while its bank is mapped. Returning a pointer to
// banked text would leave the string inaccessible after the trampoline
// restores the Pack screen's bank.
void inventory_write_weapon_tip(u8 index) BANKED;
void inventory_write_current_goal(void) BANKED;

#endif
