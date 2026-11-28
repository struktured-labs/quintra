#ifndef QUINTRA_GAME_MAP_SLIDES_H
#define QUINTRA_GAME_MAP_SLIDES_H
#include "core/types.h"

// Compass hero icons and the multi-icon slideshow (#264). Pinned to bank 31
// so the Compass's own banks (7, 17) keep their layout and headroom.
// Compass entry: hero icons in the hero's palette; clears the slideshow.
void map_marks_begin(void) BANKED;
// Icon for dungeon cell i at node (x, y). flags: 1 seen, 2 boss hint,
// 4 unclaimed cache charted. Cells with 2+ icons join the slideshow.
u8   map_dungeon_node_icon(u8 i, u8 here, u8 goal, u8 flags, u8 x, u8 y) BANKED;
// Hero's cell on a one-tile map; a landmark under the hero shares the cell.
u8   map_here_over(u8 x, u8 y, u8 under, u8 under_attr) BANKED;
// Small mark over a node, kept across slideshow turns.
void map_overlay_put(u8 x, u8 y, u8 tile, u8 attr) BANKED;
// Once per Compass frame: every half second, multi-icon cells turn.
void map_slide_tick(void) BANKED;
extern u8 map_slide_n;
extern u8 map_slide_phase;

#endif
