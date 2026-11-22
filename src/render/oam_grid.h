#ifndef RENDER_OAM_GRID_H
#define RENDER_OAM_GRID_H
#include "core/types.h"

// See oam_grid.c. Home bank: callable from any ROM bank.
extern u8 *og_ptr;
extern u8 og_y, og_x, og_w, og_h, og_tile, og_prop, og_dx, og_dy;
void oam_grid(void) __naked;

#endif
