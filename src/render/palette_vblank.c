#pragma bank 4
// Banked so the VBlank OBJ-palette commit cannot push home/GSINIT
// past 0x4000 (a silent white-screen boot failure).

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "content.h"
#include "game/class_select.h"
#include "render/class_palettes.h"
#include "render/palette.h"

u16 obj_pal_cache[8][4];
volatile u8 palette_obj_pending_commit;
u16 bg_pal_cache[8][4];
volatile u8 palette_bg_pending_commit;

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


void palette_bg_commit_vblank(void) BANKED {
    u8 i, ci, start;

    /* Start-of-VBlank only. Skip (and retry later) if this call is late. */
    if (LY_REG < 144u || LY_REG >= 150u)
        return;

    start = (u8)((PALETTE_OBJ_COMMIT_PASSES - palette_bg_pending_commit) & 7);
    for (i = 0; i < 8; ++i) {
        u8 slot = (u8)((start + i) & 7);
        for (ci = 0; ci < 4; ++ci) {
            u8 lo = (u8)(bg_pal_cache[slot][ci] & 0xFF);
            u8 hi = (u8)(bg_pal_cache[slot][ci] >> 8);
            rBCPS = (u8)(0x80 | (slot << 3) | (ci << 1));
            rBCPD = lo;
            rBCPD = hi;
        }
    }
    if (palette_bg_pending_commit)
        palette_bg_pending_commit--;
}

void palette_obj_cache_title(void) BANKED {
    u8 spirit, i;
    for (spirit = 0; spirit < 5; ++spirit)
        class_palette_cache_obj((u8)(spirit + 1), spirit);
    // Slots 0, 6 and 7 stay black. The bytes are zero, so this does not
    // read title.c's bank.
    for (i = 0; i < 4; ++i) {
        obj_pal_cache[0][i] = 0;
        obj_pal_cache[6][i] = 0;
        obj_pal_cache[7][i] = 0;
    }
}

#define CS_PAL_BODY 0
#define CS_PAL_GOLD 1
#define CS_PAL_ACCENT 2
#define CS_PAL_LAVENDER 3

static u8 *cs_attr_map(void) {
    return (u8 *)((LCDC_REG & LCDCF_BG9C00) ? 0x9C00 : 0x9800);
}

static void cs_attr_span(u8 x, u8 y, u8 n, u8 pal) {
    u8 *cell;
    u8 i;
    if (n == 0) return;
    cell = cs_attr_map() + (u16)y * 32u + x;
    VBK_REG = 1;
    for (i = 0; i < n; ++i) cell[i] = (u8)(pal & 7);
    VBK_REG = 0;
}

static void cs_fill_rows(u8 y0, u8 n) {
    u8 *map = cs_attr_map();
    u8 row, col;
    VBK_REG = 1;
    for (row = 0; row < n; ++row) {
        u8 *line = map + (u16)(y0 + row) * 32u;
        for (col = 0; col < 20; ++col) line[col] = CS_PAL_BODY;
    }
    VBK_REG = 0;
}

static void cs_paint_spans(void) {
    u8 *map = cs_attr_map();
    u8 col, name_len;
    u8 stats[20];

    cs_attr_span(2, 1, 16, CS_PAL_GOLD);
    name_len = 0;
    {
        const char *name = classes[class_select_cursor].name;
        while (name[name_len]) name_len++;
    }
    cs_attr_span(4, (u8)(3 + class_select_cursor), name_len, CS_PAL_ACCENT);
    cs_attr_span(0, 9, 4, CS_PAL_GOLD);
    cs_attr_span(6, 9, 14, CS_PAL_ACCENT);
    cs_attr_span(0, 10, 1, CS_PAL_GOLD);
    cs_attr_span(0, 11, 1, CS_PAL_GOLD);
    cs_attr_span(0, 12, 5, CS_PAL_GOLD);
    for (col = 0; col < 20; ++col) {
        u8 t = map[(u16)(14 * 32 + col)];
        stats[col] = (t >= 11 && t <= 36) ? CS_PAL_GOLD : CS_PAL_BODY;
    }
    VBK_REG = 1;
    for (col = 0; col < 20; ++col) map[(u16)(14 * 32 + col)] = stats[col];
    VBK_REG = 0;
    if (class_select_easy_mode) {
        cs_attr_span(0, 16, 4, CS_PAL_GOLD);
        cs_attr_span(5, 16, 15, CS_PAL_LAVENDER);
    } else {
        cs_attr_span(8, 16, 12, CS_PAL_LAVENDER);
    }
    cs_attr_span(1, 17, 1, CS_PAL_GOLD);
    cs_attr_span(3, 17, 6, CS_PAL_LAVENDER);
    cs_attr_span(12, 17, 1, CS_PAL_GOLD);
    cs_attr_span(14, 17, 4, CS_PAL_LAVENDER);
}

// Phases 1..3 store six body rows. Phase 4 stamps the colored spans.
// Called after loop_frame_counter increments. Six direct stores fit in
// the blank; the old set_tiles fill inside enter did not.
void class_select_attr_vblank(void) BANKED {
    if (class_select_attr_phase == 0) return;
    if (class_select_attr_phase <= 3) {
        cs_fill_rows((u8)((class_select_attr_phase - 1) * 6), 6);
        class_select_attr_phase++;
        return;
    }
    cs_paint_spans();
    class_select_attr_phase = 0;
}
