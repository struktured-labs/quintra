#ifndef QUINTRA_GAME_MAP_MARKS_H
#define QUINTRA_GAME_MAP_MARKS_H
#include "core/types.h"

// Bank 17 helpers so the Compass shop mark does not consume bank 7 headroom.
void map_load_shop_palette(void) BANKED;
void map_draw_dungeon_legend(void) BANKED;
void map_draw_world_legend(void) BANKED;
u8   map_world_shop_icon(u8 cell, u8 icon) BANKED;
u8   map_dungeon_shop_icon(u8 cell, u8 here, u8 icon) BANKED;
u8   map_town_shop_center(u8 visual_i, u8 here, u8 fallback) BANKED;

#endif
