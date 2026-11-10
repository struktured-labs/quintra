#pragma bank 4
// Banked so the VBlank OBJ-palette commit cannot push home/GSINIT
// past 0x4000 (a silent white-screen boot failure).

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "render/palette.h"

u16 obj_pal_cache[8][4];
volatile u8 palette_obj_pending_commit;

// Called only after loop_run actually waited for VBlank (not on frames
// that already crossed LY=144 during draw). Write each color once per
// pass and repeat across PALETTE_OBJ_COMMIT_PASSES frames.
//
// Re-arm OCPS before every color so a dropped OCPD cannot desync the
// auto-increment index. The start slot rotates each pass: identical
// bursts starting at the same LY drop the same mid-burst colors on the
// MiSTer Gameboy core (retries of one fixed order cannot fill those
// holes). Rotation places every slot at every burst offset so a
// deterministic drop window cannot keep zeroing the same champion.
// No mid-burst LY early-out: aborting left palettes half-written and
// broke the PyBoy title tests.
void palette_obj_commit_vblank(void) BANKED {
    u8 i, ci, start;

    /* Start-of-VBlank only. Skip (and retry later) if this call is late. */
    if (LY_REG < 144u || LY_REG >= 150u)
        return;

    start = (u8)((PALETTE_OBJ_COMMIT_PASSES - palette_obj_pending_commit) & 7);
    for (i = 0; i < 8; ++i) {
        u8 slot = (u8)((start + i) & 7);
        for (ci = 0; ci < 4; ++ci) {
            u8 lo = (u8)(obj_pal_cache[slot][ci] & 0xFF);
            u8 hi = (u8)(obj_pal_cache[slot][ci] >> 8);
            rOCPS = (u8)(0x80 | (slot << 3) | (ci << 1));
            rOCPD = lo;
            rOCPD = hi;
        }
    }
    if (palette_obj_pending_commit)
        palette_obj_pending_commit--;
}
