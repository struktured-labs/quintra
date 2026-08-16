#ifndef QUINTRA_GAME_DUNGEON_LAW_H
#define QUINTRA_GAME_DUNGEON_LAW_H

#include <gb/gb.h>
#include "core/types.h"

// Project the dungeon's persistent WAX/WANE rule into the current room.
// `live` animates each changed tile; room generation uses the silent path.
void dungeon_law_apply_room(u8 live) BANKED;
void dungeon_law_draw_pack(void) BANKED;

// Contextual switch activation. The player path computes its feet tile;
// elemental/Oath projectiles can target the explicit coordinates directly.
u8 dungeon_law_try_player_toggle(void) BANKED;
u8 dungeon_law_try_toggle_at(u8 tx, u8 ty) BANKED;

#endif
