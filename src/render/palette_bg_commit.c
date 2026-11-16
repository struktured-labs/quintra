#pragma bank 14
// Banked BG palette helpers. palette.c lives in home, which has no spare
// bytes, so only palette_bg_load (which must read the caller's bank) stays
// there.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "render/palette.h"

// Heal mid-frame BG palette writes (see palette_bg_load). Same contract as
// the OBJ commit: top of VBlank only, BCPS re-armed before every colour,
// start slot rotated between passes, only slots written with the LCD on.
void palette_bg_commit_vblank(void) BANKED {
    u8 i, ci, start, mask;

    if (LY_REG < 144u || LY_REG >= 150u)
        return;

    mask = palette_bg_dirty;
    start = palette_bg_pending_commit;
    start = (u8)(start % PALETTE_BG_HEAL_SLOTS);
    for (i = 0; i < PALETTE_BG_HEAL_SLOTS; ++i) {
        u8 slot = (u8)(start + i);
        if (slot >= PALETTE_BG_HEAL_SLOTS) slot -= PALETTE_BG_HEAL_SLOTS;
        const u8 *src;
        u8 idx;
        if (!(mask & (u8)(1u << slot))) continue;
        src = (const u8 *)palette_bg_shadow[slot];
        idx = (u8)(0x80 | (slot << 3));
        for (ci = 0; ci < 4; ++ci) {
            rBCPS = idx;
            rBCPD = *src++;
            rBCPD = *src++;
            idx += 2;
        }
    }
    if (palette_bg_pending_commit && --palette_bg_pending_commit == 0)
        palette_bg_dirty = 0;
}

void palette_bg_fill_attrs(u8 slot) BANKED {
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
