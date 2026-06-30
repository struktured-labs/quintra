// Quintra — Phase 1 bootstrap
// Goal: ROM boots in CGB mode, shows a colored background, sits in vblank loop.
// Real screen state machine, ECS, etc. arrive in Phase 3+.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
// rBCPS/rBCPD/rOCPS/rOCPD are provided by gb/hardware.h via gb.h

// Pack RGB555 -> BGR555 word (CGB native)
#define RGB555(r,g,b)  ((u16)(((b) & 0x1F) << 10) | (((g) & 0x1F) << 5) | ((r) & 0x1F))

// Boot palette: deep purple-blue background gradient (placeholder title screen vibe)
static const u16 boot_bg_pal[4] = {
    RGB555( 0,  0,  3),    // 0 — near-black blue
    RGB555( 4,  2, 12),    // 1 — deep indigo
    RGB555(14,  6, 20),    // 2 — magenta-blue
    RGB555(28, 20, 31),    // 3 — pale lilac (highlight)
};

static void load_bg_palette_0(void) {
    rBCPS = 0x80;  // auto-increment, start at palette 0 / color 0
    rBCPD = boot_bg_pal[0] & 0xFF; rBCPD = boot_bg_pal[0] >> 8;
    rBCPD = boot_bg_pal[1] & 0xFF; rBCPD = boot_bg_pal[1] >> 8;
    rBCPD = boot_bg_pal[2] & 0xFF; rBCPD = boot_bg_pal[2] >> 8;
    rBCPD = boot_bg_pal[3] & 0xFF; rBCPD = boot_bg_pal[3] >> 8;
}

// 16-byte gradient tile (8x8, 2bpp): rows pick varying color indices
static const u8 gradient_tile[16] = {
    0x00, 0x00,  // row 0: all color 0
    0xFF, 0x00,  // row 1: all color 1
    0xFF, 0x00,
    0xFF, 0xFF,  // row 3: all color 3
    0xFF, 0xFF,
    0xFF, 0x00,
    0xFF, 0x00,
    0x00, 0x00,
};

void main(void) {
    DISPLAY_OFF;

    load_bg_palette_0();

    // Load one gradient tile to VRAM index 0
    set_bkg_data(0, 1, gradient_tile);

    // Fill BG tilemap with tile 0 (default uses BG palette 0)
    {
        u8 fill[20];
        u8 y;
        for (y = 0; y < 20; ++y) fill[y] = 0;
        for (y = 0; y < 18; ++y) {
            set_bkg_tiles(0, y, 20, 1, fill);
        }
    }

    SHOW_BKG;
    DISPLAY_ON;

    // Idle loop — real game loop arrives in Phase 3
    for (;;) {
        wait_vbl_done();
    }
}
