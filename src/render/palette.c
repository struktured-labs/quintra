#include <gb/gb.h>
#include <gb/cgb.h>

#include "render/palette.h"

static void load_to_pal(u8 ps_reg_select_lo, u8 slot, const u16 *colors) {
    // Auto-increment + start at (slot * 8) — each palette is 4 colors × 2 bytes
    if (ps_reg_select_lo == 0) {
        rBCPS = 0x80 | (u8)(slot << 3);
        rBCPD = (u8)(colors[0] & 0xFF); rBCPD = (u8)(colors[0] >> 8);
        rBCPD = (u8)(colors[1] & 0xFF); rBCPD = (u8)(colors[1] >> 8);
        rBCPD = (u8)(colors[2] & 0xFF); rBCPD = (u8)(colors[2] >> 8);
        rBCPD = (u8)(colors[3] & 0xFF); rBCPD = (u8)(colors[3] >> 8);
    } else {
        rOCPS = 0x80 | (u8)(slot << 3);
        rOCPD = (u8)(colors[0] & 0xFF); rOCPD = (u8)(colors[0] >> 8);
        rOCPD = (u8)(colors[1] & 0xFF); rOCPD = (u8)(colors[1] >> 8);
        rOCPD = (u8)(colors[2] & 0xFF); rOCPD = (u8)(colors[2] >> 8);
        rOCPD = (u8)(colors[3] & 0xFF); rOCPD = (u8)(colors[3] >> 8);
    }
}

void palette_bg_load(u8 slot, const u16 *colors) {
    load_to_pal(0, slot, colors);
}

void palette_obj_load(u8 slot, const u16 *colors) {
    load_to_pal(1, slot, colors);
}

void palette_bg_load_n(u8 first_slot, u8 n, const u16 *colors) {
    u8 i;
    for (i = 0; i < n; ++i) {
        palette_bg_load((u8)(first_slot + i), colors + (u16)(i * 4));
    }
}

void palette_bg_fill_attrs(u8 slot) {
    u8 row[20];
    u8 x, y;
    u8 *map = (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
    slot &= 7;
    for (x = 0; x < 20; ++x) row[x] = slot;
    VBK_REG = 1;
    // set_bkg_tiles honors the console's global font tile offset, which is
    // correct for glyph IDs but corrupts raw attribute zeroes. set_tiles uses
    // the explicit map address and writes the palette bytes verbatim.
    for (y = 0; y < 18; ++y) set_tiles(0, y, 20, 1, map, row);
    VBK_REG = 0;
}
