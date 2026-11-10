#pragma bank 4
// Banked so the VBlank OBJ-palette commit cannot push home/GSINIT
// past 0x4000 (a silent white-screen boot failure).

#include <gb/gb.h>
#include <gb/cgb.h>
#include <string.h>

#include "core/types.h"
#include "content.h"
#include "game/class_select.h"
#include "render/class_palettes.h"
#include "render/palette.h"

u16 obj_pal_cache[8][4];
volatile u8 palette_obj_pending_commit;
u16 bg_pal_cache[8][4];

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

#define G CS_PAL_GOLD
#define A CS_PAL_ACCENT
#define L CS_PAL_LAVENDER

// Final 20-column attribute rows. The VBlank job only memcpy's rows, so
// every stored row costs the same few hundred cycles and no frame overruns.
static const u8 cs_row_zero[20];
static const u8 cs_row_title[20] = {
    0, 0, G, G, G, G, G, G, G, G, G, G, G, G, G, G, G, G, 0, 0 };
static const u8 cs_row_role[20] = {
    G, G, G, G, 0, 0, A, A, A, A, A, A, A, A, A, A, A, A, A, A };
static const u8 cs_row_ab[20] = { G };
static const u8 cs_row_trait[20] = { G, G, G, G, G };
static const u8 cs_row_normal[20] = {
    0, 0, 0, 0, 0, 0, 0, 0, L, L, L, L, L, L, L, L, L, L, L, L };
static const u8 cs_row_easy[20] = {
    G, G, G, G, 0, L, L, L, L, L, L, L, L, L, L, L, L, L, L, L };
static const u8 cs_row_prompt[20] = {
    0, G, 0, L, L, L, L, L, L, 0, 0, 0, G, 0, L, L, L, L, 0, 0 };

static const u8 *const cs_rows[18] = {
    cs_row_zero, cs_row_title, cs_row_zero,
    cs_row_zero, cs_row_zero, cs_row_zero, cs_row_zero, cs_row_zero,
    cs_row_zero, cs_row_role, cs_row_ab, cs_row_ab, cs_row_trait,
    cs_row_zero, 0, cs_row_zero, 0, cs_row_prompt,
};

#undef G
#undef A
#undef L

// Page-dependent rows, built outside VBlank by class_select_attr_prepare.
static u8 cs_row_name[20];
static u8 cs_row_stats[20];

// First row of each VBlank job; job n stores rows [start[n], start[n+1]).
static const u8 cs_job_rows[7] = { 0, 3, 6, 9, 12, 15, 18 };

static u8 *cs_digits(u8 *p, u8 v) {
    *p++ = CS_PAL_BODY;
    if (v >= 10) *p++ = CS_PAL_BODY;
    if (v >= 100) *p++ = CS_PAL_BODY;
    return p;
}

static u8 *cs_label(u8 *p, u8 space) {
    if (space) *p++ = CS_PAL_BODY;
    *p++ = CS_PAL_GOLD;
    *p++ = CS_PAL_GOLD;
    return p;
}

void class_select_attr_prepare(void) BANKED {
    const class_def_t *c = &classes[class_select_cursor];
    u8 *p = cs_row_stats;
    // Selected name in its accent; the "> " cursor stays body white.
    memset(cs_row_name, CS_PAL_BODY, sizeof cs_row_name);
    memset(cs_row_name + 4, CS_PAL_ACCENT, class_select_name_len);
    // Stat row, mirroring write_stats(): labels gold, digits and spaces
    // body. Built from the numbers, not read back from VRAM.
    memset(cs_row_stats, CS_PAL_BODY, sizeof cs_row_stats);
    p = cs_label(p, 0);
    p = cs_digits(p, c->base_stats.hp_max);
    p = cs_label(p, c->base_stats.mp_max < 10);
    p = cs_digits(p, c->base_stats.mp_max);
    p = cs_label(p, 1);
    p = cs_digits(p, c->base_stats.atk);
    p = cs_label(p, 1);
    p = cs_digits(p, c->base_stats.def);
    p = cs_label(p, 1);
    cs_digits(p, c->base_stats.spd);
}

static void cs_store_rows(u8 job) {
    u8 r = cs_job_rows[job];
    u8 end = cs_job_rows[job + 1];
    u8 *dst = (u8 *)((LCDC_REG & LCDCF_BG9C00) ? 0x9C00 : 0x9800)
              + (u16)r * 32u;
    u8 name_row = (u8)(3 + class_select_cursor);
    VBK_REG = 1;
    do {
        const u8 *src = cs_rows[r];
        if (r == name_row) src = cs_row_name;
        else if (r == 14) src = cs_row_stats;
        else if (r == 16)
            src = class_select_easy_mode ? cs_row_easy : cs_row_normal;
        memcpy(dst, src, 20);
        dst += 32;
    } while (++r != end);
    VBK_REG = 0;
}

// Four consecutive palettes from base, re-arming the index before every
// color so a dropped data write cannot desync auto-increment.
static void cs_burst_bg(u8 base) {
    u8 n = 4;
    do {
        u8 slot = (u8)(base & 7);
        const u8 *src = (const u8 *)bg_pal_cache[slot];
        u8 idx = (u8)(0x80 | (slot << 3));
        u8 ci = 4;
        do {
            rBCPS = idx;
            rBCPD = *src++;
            rBCPD = *src++;
            idx += 2;
        } while (--ci);
        base++;
    } while (--n);
}

static void cs_burst_obj(u8 base) {
    u8 n = 4;
    do {
        u8 slot = (u8)(base & 7);
        const u8 *src = (const u8 *)obj_pal_cache[slot];
        u8 idx = (u8)(0x80 | (slot << 3));
        u8 ci = 4;
        do {
            rOCPS = idx;
            rOCPD = *src++;
            rOCPD = *src++;
            idx += 2;
        } while (--ci);
        base++;
    } while (--n);
}

// One job per frame, from the top of class_select_tick (right after
// loop_run's input_poll), while LY is at the top of VBlank. Attribute
// jobs 1..6 store three finished rows each (0-2 ... 15-17). Then palette
// half-bursts: step k (0..PASSES*4-1) uses bit 0 for the half, bit 1 for
// BG or OBJ, and k>>2 as the pass, rotating the start slot like the
// title's commit so the MiSTer core's dropped-write window cannot pin one
// slot. Nothing
// here touches the frame counter or delays the input sample, and the
// tick skips it on A/B frames, so New Game seeds and timing match main.
void class_select_vblank_step(void) BANKED {
    /* Top of VBlank only (the enter frame polls mid-screen). */
    if (LY_REG < 144u || LY_REG >= 150u)
        return;
    if (class_select_attr_phase) {
        cs_store_rows((u8)(class_select_attr_phase - 1));
        if (++class_select_attr_phase > 6)
            class_select_attr_phase = 0;
    } else if (class_select_pal_steps) {
        u8 k;
        class_select_pal_steps--;
        k = (u8)(PALETTE_OBJ_COMMIT_PASSES * 4 - 1 - class_select_pal_steps);
        if (k & 2) cs_burst_obj((u8)((k >> 2) + ((k & 1) << 2)));
        else       cs_burst_bg((u8)((k >> 2) + ((k & 1) << 2)));
    }
    class_select_vbl_work = (u8)(class_select_attr_phase | class_select_pal_steps);
}
