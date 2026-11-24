#ifndef QUINTRA_RENDER_CROWN_TILES_H
#define QUINTRA_RENDER_CROWN_TILES_H

#include <gb/gb.h>

// Past font_min on CLASS_SELECT. Column 12 of each hero name row.
#define BGT_CROWN_EASY    0x70
#define BGT_CROWN_NORMAL  0x71
#define CS_CROWN_COL      12

void class_select_load_crowns(void) BANKED;
void class_select_draw_crowns(void) BANKED;

#endif
