#ifndef QUINTRA_GAME_INVENTORY_AIM_H
#define QUINTRA_GAME_INVENTORY_AIM_H

#include "core/types.h"

// Zelda-style B-item icon picker (Pack SELECT page).
// See docs/superpowers/specs/2026-11-15-b-item-icon-picker.md.
void inventory_aim_enter(void) BANKED;

// 0 = stay on the page, 1 = resume the room, 2 = open Gear.
u8 inventory_aim_tick(u8 pressed) BANKED;

#endif
