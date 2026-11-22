// Batched shadow-OAM grid writer shared by the large boss renderers.
//
// SDCC spills every local of a nested r/c setter loop to the stack and
// recomputes &shadow_OAM[n] for each of set_sprite_tile/prop/move_sprite.
// This writes y,x,tile,prop for og_h rows of og_w cells through one pointer
// with the whole state in registers: about 60 clocks per cell instead of a
// few hundred. Parameters live in og_* (all registers are caller-saved).
//   cell (r,c): y = og_y + r*og_dy, x = og_x + c*og_dx (u8 wrap),
//               tile = og_tile + r*og_w + c, prop = og_prop.
// og_w and og_h must be non-zero. og_h is consumed; og_ptr is advanced.
#include <gb/gb.h>
#include "core/types.h"
#include "render/oam_grid.h"

u8 *og_ptr;
u8 og_y, og_x, og_w, og_h, og_tile, og_prop, og_dx, og_dy;

void oam_grid(void) __naked {
    __asm
        ld  hl, #_og_ptr
        ld  a, (hl+)
        ld  h, (hl)
        ld  l, a
        ld  a, (_og_tile)
        ld  b, a
        ld  a, (_og_y)
        ld  d, a
    1$:
        ld  a, (_og_x)
        ld  e, a
        ld  a, (_og_w)
        ld  c, a
    2$:
        ld  a, d
        ld  (hl+), a
        ld  a, e
        ld  (hl+), a
        ld  a, (_og_dx)
        add a, e
        ld  e, a
        ld  a, b
        inc b
        ld  (hl+), a
        ld  a, (_og_prop)
        ld  (hl+), a
        dec c
        jr  nz, 2$
        ld  a, (_og_dy)
        add a, d
        ld  d, a
        ld  a, (_og_h)
        dec a
        ld  (_og_h), a
        jr  nz, 1$
        ld  a, l
        ld  (_og_ptr), a
        ld  a, h
        ld  (_og_ptr + 1), a
        ret
    __endasm;
}
