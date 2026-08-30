#pragma bank 14

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

#define HUD_NOTICE_STATUS 0x80
#define HUD_NOTICE_FRAMES 45
#define HUD_NOTICE_HUNGER 0x7F
#define HUD_NOTICE_QUEUE  4

u8 hud_notice_ticks;
static u8 notice_kind;
static u8 notice_amount;
static u8 queued_kind[HUD_NOTICE_QUEUE];
static u8 queued_amount[HUD_NOTICE_QUEUE];
static u8 queue_head;
static u8 queue_count;

void hud_notice_restore_context(void) BANKED;

static const u16 notice_green[4] = {
    BGR555(0, 0, 0), BGR555(5, 11, 7), BGR555(12, 22, 10), BGR555(18, 31, 13)
};
static const u16 notice_gold[4] = {
    BGR555(0, 0, 0), BGR555(12, 8, 2), BGR555(24, 15, 3), BGR555(31, 25, 8)
};
static const u16 notice_violet[4] = {
    BGR555(0, 0, 0), BGR555(9, 5, 14), BGR555(18, 8, 24), BGR555(27, 15, 31)
};

static const u8 status_letters[5][16] = {
    { 0x3C,0x3C, 0x42,0x42, 0x40,0x40, 0x3C,0x3C,
      0x02,0x02, 0x42,0x42, 0x3C,0x3C, 0x00,0x00 }, // S
    { 0x3C,0x3C, 0x42,0x42, 0x40,0x40, 0x40,0x40,
      0x40,0x40, 0x42,0x42, 0x3C,0x3C, 0x00,0x00 }, // C
    { 0x00,0x00, 0x18,0x18, 0x18,0x18, 0x7E,0x7E,
      0x18,0x18, 0x18,0x18, 0x00,0x00, 0x00,0x00 }, // +
    { 0x7C,0x7C, 0x42,0x42, 0x42,0x42, 0x7C,0x7C,
      0x42,0x42, 0x42,0x42, 0x7C,0x7C, 0x00,0x00 }, // B
    { 0x42,0x42, 0x42,0x42, 0x42,0x42, 0x42,0x42,
      0x42,0x42, 0x42,0x42, 0x3C,0x3C, 0x00,0x00 }, // U
};

void hud_notice_load_glyphs(void) BANKED {
    set_bkg_data(HUD_STATUS_S, 3, status_letters[0]);
    set_bkg_data(HUD_STATUS_B, 2, status_letters[3]);
}

static u8 status_word(u8 status, u8 *row) {
    switch (status) {
        case QSTATUS_POISON:
            row[0]=BGT_AREA_P; row[1]=BGT_AREA_O; row[2]=BGT_AREA_I;
            row[3]=HUD_STATUS_S; row[4]=BGT_AREA_O; row[5]=BGT_AREA_N; return 6;
        case QSTATUS_BURN:
            row[0]=HUD_STATUS_B; row[1]=HUD_STATUS_U;
            row[2]=BGT_AREA_R; row[3]=BGT_AREA_N; return 4;
        case QSTATUS_SLOW:
            row[0]=HUD_STATUS_S; row[1]=BGT_AREA_L;
            row[2]=BGT_AREA_O; row[3]=BGT_AREA_W; return 4;
        case QSTATUS_STOP:
            row[0]=HUD_STATUS_S; row[1]=BGT_AREA_T;
            row[2]=BGT_AREA_O; row[3]=BGT_AREA_P; return 4;
        case QSTATUS_BLIND:
            row[0]=HUD_STATUS_B; row[1]=BGT_AREA_L; row[2]=BGT_AREA_I;
            row[3]=BGT_AREA_N; row[4]=BGT_AREA_D; return 5;
        case QSTATUS_CONFUSION:
            row[0]=HUD_STATUS_C; row[1]=BGT_AREA_O; row[2]=BGT_AREA_N;
            row[3]=BGT_AREA_F; row[4]=HUD_STATUS_U; row[5]=HUD_STATUS_S; return 6;
        case QSTATUS_MUTE:
            row[0]=BGT_AREA_M; row[1]=HUD_STATUS_U;
            row[2]=BGT_AREA_T; row[3]=BGT_AREA_E; return 4;
        case QSTATUS_BRITTLE:
            row[0]=HUD_STATUS_B; row[1]=BGT_AREA_R; row[2]=BGT_AREA_I;
            row[3]=BGT_AREA_T; row[4]=BGT_AREA_T; row[5]=BGT_AREA_L; return 6;
        case QSTATUS_BLEED:
            row[0]=HUD_STATUS_B; row[1]=BGT_AREA_L; row[2]=BGT_AREA_E;
            row[3]=BGT_AREA_E; row[4]=BGT_AREA_D; return 5;
        case QSTATUS_CURSE:
            row[0]=HUD_STATUS_C; row[1]=HUD_STATUS_U; row[2]=BGT_AREA_R;
            row[3]=HUD_STATUS_S; row[4]=BGT_AREA_E; return 5;
        case QSTATUS_REGEN:
            row[0]=BGT_AREA_R; row[1]=BGT_AREA_E; row[2]=BGT_AREA_G;
            row[3]=BGT_AREA_E; row[4]=BGT_AREA_N; return 5;
        case QSTATUS_HASTE:
            row[0]=BGT_AREA_H; row[1]=BGT_AREA_A; row[2]=HUD_STATUS_S;
            row[3]=BGT_AREA_T; row[4]=BGT_AREA_E; return 5;
        case HUD_NOTICE_HUNGER:
            row[0]=BGT_AREA_H; row[1]=HUD_STATUS_U; row[2]=BGT_AREA_N;
            row[3]=BGT_AREA_G; row[4]=BGT_AREA_E; row[5]=BGT_AREA_R; return 6;
        default:
            row[0]=BGT_AREA_I; row[1]=BGT_AREA_N; row[2]=BGT_AREA_V;
            row[3]=BGT_AREA_E; row[4]=BGT_AREA_R; row[5]=BGT_AREA_T; return 6;
    }
}

static u8 notice_palette(u8 kind) {
    u8 value = kind & 0x7F;
    if (!(kind & HUD_NOTICE_STATUS)) {
        if (value == STAT_MP || value == STAT_SPD) return 6;
        if (value == STAT_DEF) { palette_bg_load(5, notice_violet); return 5; }
        if (value == STAT_LCK) { palette_bg_load(5, notice_gold); return 5; }
        return 7;
    }
    if (value == QSTATUS_POISON || value == QSTATUS_REGEN) {
        palette_bg_load(5, notice_green); return 5;
    }
    if (value == QSTATUS_BURN || value == QSTATUS_BRITTLE
        || value == QSTATUS_BLEED) return 7;
    if (value == QSTATUS_SLOW || value == QSTATUS_STOP
        || value == QSTATUS_HASTE) return 6;
    palette_bg_load(5, notice_violet);
    return 5;
}

static void draw_notice(u8 kind, u8 amount) {
    u8 row[6] = { HUD_BLANK, HUD_BLANK, HUD_BLANK,
        HUD_BLANK, HUD_BLANK, HUD_BLANK };
    u8 attrs[6];
    u8 width;
    u8 start;
    u8 i;
    u8 pal = notice_palette(kind);
    if (kind & HUD_NOTICE_STATUS) width = status_word((u8)(kind & 0x7F), row);
    else {
        switch (kind) {
            case STAT_HP:
                row[0]=BGT_AREA_H; row[1]=BGT_AREA_P; width=2; break;
            case STAT_MP:
                row[0]=BGT_AREA_M; row[1]=BGT_AREA_P; width=2; break;
            case STAT_ATK:
                row[0]=BGT_AREA_A; row[1]=BGT_AREA_T;
                row[2]=BGT_AREA_K; width=3; break;
            case STAT_DEF:
                row[0]=BGT_AREA_D; row[1]=BGT_AREA_E;
                row[2]=BGT_AREA_F; width=3; break;
            case STAT_SPD:
                row[0]=HUD_STATUS_S; row[1]=BGT_AREA_P;
                row[2]=BGT_AREA_D; width=3; break;
            default:
                row[0]=BGT_AREA_L; row[1]=HUD_STATUS_C;
                row[2]=BGT_AREA_K; width=3; break;
        }
        row[width++] = HUD_STATUS_PLUS;
        if (amount > 9) amount = 9;
        row[width++] = (u8)(HUD_DIGIT_0 + amount);
    }
    start = (u8)((6 - width) >> 1);
    if (start) {
        for (i = width; i > 0; --i) row[start + i - 1] = row[i - 1];
        for (i = 0; i < start; ++i) row[i] = HUD_BLANK;
    }
    for (i = 0; i < 6; ++i) attrs[i] = pal;
    VBK_REG = 0; set_win_tiles(10, 0, 6, 1, row);
    VBK_REG = 1; set_win_tiles(10, 0, 6, 1, attrs);
    VBK_REG = 0;
}

static void begin_notice(u8 kind, u8 amount) {
    notice_kind = kind;
    notice_amount = amount;
    hud_notice_ticks = HUD_NOTICE_FRAMES;
    draw_notice(notice_kind, notice_amount);
}

void hud_notice_reset(void) BANKED {
    hud_notice_ticks = 0;
    notice_kind = 0xFF;
    queue_head = 0;
    queue_count = 0;
}

static u8 notice_already_queued(u8 kind) {
    u8 i;
    if (hud_notice_ticks && notice_kind == kind) return 1;
    for (i = 0; i < queue_count; ++i)
        if (queued_kind[(u8)((queue_head + i) % HUD_NOTICE_QUEUE)] == kind)
            return 1;
    return 0;
}

static void queue_notice(u8 kind, u8 amount) {
    u8 tail;
    if (queue_count >= HUD_NOTICE_QUEUE) return;
    tail = (u8)((queue_head + queue_count) % HUD_NOTICE_QUEUE);
    queued_kind[tail] = kind;
    queued_amount[tail] = amount;
    queue_count++;
}

void hud_show_stat_gain(u8 stat, u8 amount) BANKED {
    if (!amount) return;
    if (hud_notice_ticks) {
        queue_notice(stat, amount);
        return;
    }
    begin_notice(stat, amount);
}

void hud_show_status(u8 status) BANKED {
    u8 kind;
    if (status == QSTATUS_NONE || status >= QSTATUS_COUNT) return;
    kind = (u8)(HUD_NOTICE_STATUS | status);
    if (hud_notice_ticks) {
        if (notice_already_queued(kind)) return;
        queue_notice(kind, 0);
        return;
    }
    begin_notice(kind, 0);
}

void hud_show_healing_blocked(void) BANKED {
    u8 kind = (u8)(HUD_NOTICE_STATUS | HUD_NOTICE_HUNGER);
    if (hud_notice_ticks) {
        if (!notice_already_queued(kind)) queue_notice(kind, 0);
        return;
    }
    begin_notice(kind, 0);
}

void hud_tick_notice(void) BANKED {
    if (!hud_notice_ticks || --hud_notice_ticks) return;
    if (queue_count) {
        u8 kind = queued_kind[queue_head];
        u8 amount = queued_amount[queue_head];
        queue_head = (u8)((queue_head + 1) % HUD_NOTICE_QUEUE);
        queue_count--;
        begin_notice(kind, amount);
        return;
    }
    {
        static const u8 clear[6] = { HUD_BLANK, HUD_BLANK, HUD_BLANK,
            HUD_BLANK, HUD_BLANK, HUD_BLANK };
        static const u8 attrs[6] = { 7, 7, 7, 7, 7, 7 };
        VBK_REG = 0; set_win_tiles(10, 0, 6, 1, clear);
        VBK_REG = 1; set_win_tiles(10, 0, 6, 1, attrs);
        VBK_REG = 0;
    }
    hud_notice_restore_context();
}
