#ifndef QUINTRA_GAME_INVENTORY_WAYGEAR_H
#define QUINTRA_GAME_INVENTORY_WAYGEAR_H

#include <gb/gb.h>
#include "core/types.h"

enum {
    INVENTORY_WAYGEAR_STAY = 0,
    INVENTORY_WAYGEAR_EXIT,
    INVENTORY_WAYGEAR_PACK,
};

void inventory_waygear_enter(void) BANKED;
u8 inventory_waygear_tick(u8 pressed) BANKED;

#endif
