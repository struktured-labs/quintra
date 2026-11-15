#include <gb/gb.h>
#include <gb/cgb.h>

#include "render/palette.h"

const u16 boss_arena_floor_palette[4] = {
    BGR555(1,1,3), BGR555(3,4,7), BGR555(6,7,10), BGR555(12,13,16)
};

static void load_to_pal(u8 ps_reg_select_lo, u8 slot, const u16 *colors) {
    // Auto-increment + start at (slot * 8): 4 colours x 2 bytes, low first.
    const u8 *src = (const u8 *)colors;
    u8 n = 8;
    if (ps_reg_select_lo == 0) {
        rBCPS = 0x80 | (u8)(slot << 3);
        do { rBCPD = *src++; } while (--n);
    } else {
        // OBJ stays unrolled: it races one HBlank after the STAT wait.
        rOCPS = 0x80 | (u8)(slot << 3);
        rOCPD = (u8)(colors[0] & 0xFF); rOCPD = (u8)(colors[0] >> 8);
        rOCPD = (u8)(colors[1] & 0xFF); rOCPD = (u8)(colors[1] >> 8);
        rOCPD = (u8)(colors[2] & 0xFF); rOCPD = (u8)(colors[2] >> 8);
        rOCPD = (u8)(colors[3] & 0xFF); rOCPD = (u8)(colors[3] >> 8);
    }
}

// Every BG palette write is mirrored here. A write made while the LCD is on
// can land in STAT mode 3, where the CGB (and the MiSTer Gameboy core)
// ignores BCPD; the room then keeps a half-written mix of old and new
// colours (a dimmed green pops "brown") until a menu reloads it. Mid-room
// writes therefore also arm a short VBlank re-commit of that slot, so the
// palette heals within a frame. LCD-off writes are reliable and disarm it.
u16 palette_bg_shadow[PALETTE_BG_HEAL_SLOTS][4];
volatile u8 palette_bg_dirty;
volatile u8 palette_bg_pending_commit;

void palette_bg_load(u8 slot, const u16 *colors) {
    u8 bit;
    load_to_pal(0, slot, colors);
    // Only the room slots (floor, wall, crystal, door, crack) are healed.
    // HUD lanes 5..7 are rewritten by their owners on every change and
    // must not steal the top of VBlank from tile streaming. LCD-off loads
    // (room entry, menus) are reliable and skip the copy entirely.
    if (slot >= PALETTE_BG_HEAL_SLOTS) return;
    bit = (u8)(1u << slot);
    if (LCDC_REG & LCDCF_ON) {
        u8 *dst = (u8 *)palette_bg_shadow[slot];
        const u8 *src = (const u8 *)colors;
        u8 n = 8;
        do { *dst++ = *src++; } while (--n);
        palette_bg_dirty |= bit;
        palette_bg_pending_commit = PALETTE_BG_COMMIT_PASSES;
    } else {
        palette_bg_dirty &= (u8)~bit;
    }
}

static void palette_obj_wait_access(void) {
    // CGB OBJ palette RAM is writable while the LCD is off, or in STAT
    // mode 0/1 (HBlank/VBlank). STATF_BUSY is set in modes 2 and 3.
    if (LCDC_REG & LCDCF_ON) {
        while (STAT_REG & STATF_BUSY)
            ;
    }
}

void palette_obj_load(u8 slot, const u16 *colors) {
    palette_obj_wait_access();
    load_to_pal(1, slot, colors);
}
