#ifndef QUINTRA_RENDER_HEXA_BG_H
#define QUINTRA_RENDER_HEXA_BG_H

#include <gb/gb.h>
#include "core/types.h"

/* Upload the sanctum dragon and write its tile ids into room_tilemap.
   Call before room_draw_tilemap. Attributes are stamped afterwards. */
void hexa_bg_prepare(void) BANKED;
/* Full attribute, palette, and core-tile pass. spotlight is 0..4 or 0xFF. */
void hexa_bg_stamp(u8 spotlight, u8 phase) BANKED;
/* Recolor only the sockets that changed, plus the core. */
void hexa_bg_retint(u8 previous, u8 next, u8 phase) BANKED;
/* Swap the 2x2 core between sealed, open, and phase-2 iris. */
void hexa_bg_set_phase(u8 phase, u8 spotlight) BANKED;
/* Heartbeat: dim=1 uses body palette 5, dim=0 restores palette 6. */
void hexa_bg_core_blink(u8 dim) BANKED;

#endif
