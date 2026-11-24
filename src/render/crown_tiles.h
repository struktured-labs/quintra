#ifndef QUINTRA_RENDER_CROWN_TILES_H
#define QUINTRA_RENDER_CROWN_TILES_H

#include <gb/gb.h>

// Win-count column on each CLASS_SELECT name row (no BG crown there).
#define CS_COUNT_COL      12
// OBJ tiles 20-21 are the room enemy/boss atlas; CLASS_SELECT overwrites
// them after the preview upload and parks the sprite on exit.
#define SPR_CROWN_EASY    20
#define SPR_CROWN_NORMAL  21
#define SPR_CROWN_OBJ     5
// CGB OBJ palettes for the head crown (color 0 is transparent).
#define CS_PAL_OBJ_GOLD   3
#define CS_PAL_OBJ_ROYAL  4

void class_select_load_crowns(void) BANKED;
void class_select_draw_crowns(void) BANKED;
void class_select_arm_crown_pals(void) BANKED;
void class_select_place_head_crown(u8 sx, u8 sy) BANKED;
void class_select_hide_head_crown(void) BANKED;

#endif
