#pragma bank 14

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "game/curse.h"
#include "game/player.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

#define HUD_NOTICE_STATUS 0x80
#define HUD_NOTICE_FRAMES 45
// Pickup results (stat cards, item words, refusals) hold one extra second so
// a champion mid-fight can actually read what the thing they touched did.
#define HUD_NOTICE_PICKUP_FRAMES (HUD_NOTICE_FRAMES + 60)
// Power-up cards hold one more second than ordinary pickup cards.
#define HUD_NOTICE_POWERUP_FRAMES (HUD_NOTICE_PICKUP_FRAMES + 60)
#define HUD_NOTICE_HUNGER 0x7F
#define HUD_NOTICE_BOOMERANG 0x7E
#define HUD_NOTICE_HOOKSHOT 0x7D
#define HUD_NOTICE_SECONDARY 0x7C
#define HUD_NOTICE_BOSS_LINK 0x7B
#define HUD_NOTICE_NOHEAL 0x7A
#define HUD_NOTICE_MPFULL 0x79
#define HUD_NOTICE_HPFULL 0x78
#define HUD_NOTICE_STATMAX 0x77
#define HUD_NOTICE_GUARD  0x76
#define HUD_NOTICE_CURED 0x75
#define HUD_NOTICE_QUEUE  6

u8 hud_notice_ticks;
static u8 notice_kind;
static u8 notice_amount;
static u8 queued_kind[HUD_NOTICE_QUEUE];
static u8 queued_amount[HUD_NOTICE_QUEUE];
static u8 queue_head;
static u8 queue_count;
static u8 link_mode;

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

static const u8 status_letters[7][16] = {
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
    { 0x42,0x42, 0x42,0x42, 0x24,0x24, 0x18,0x18,
      0x24,0x24, 0x42,0x42, 0x42,0x42, 0x00,0x00 }, // X
    { 0x00,0x00, 0x00,0x00, 0x00,0x00, 0x7E,0x7E,
      0x00,0x00, 0x00,0x00, 0x00,0x00, 0x00,0x00 }, // -
};

void hud_notice_load_glyphs(void) BANKED {
    set_bkg_data(HUD_STATUS_S, 3, status_letters[0]);
    set_bkg_data(HUD_STATUS_B, 2, status_letters[3]);
    set_bkg_data(HUD_STATUS_X, 1, status_letters[5]);
    set_bkg_data(HUD_STATUS_MINUS, 1, status_letters[6]);
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
        case QSTATUS_DISARM:
            row[0]=BGT_AREA_D; row[1]=BGT_AREA_I; row[2]=HUD_STATUS_S;
            row[3]=BGT_AREA_A; row[4]=BGT_AREA_R; row[5]=BGT_AREA_M; return 6;
        case HUD_NOTICE_HUNGER:
            row[0]=BGT_AREA_H; row[1]=HUD_STATUS_U; row[2]=BGT_AREA_N;
            row[3]=BGT_AREA_G; row[4]=BGT_AREA_E; row[5]=BGT_AREA_R; return 6;
        case HUD_NOTICE_NOHEAL:
            row[0]=BGT_AREA_N; row[1]=BGT_AREA_O; row[2]=BGT_AREA_H;
            row[3]=BGT_AREA_E; row[4]=BGT_AREA_A; row[5]=BGT_AREA_L; return 6;
        case HUD_NOTICE_MPFULL:
            row[0]=BGT_AREA_M; row[1]=BGT_AREA_P; row[2]=BGT_AREA_F;
            row[3]=HUD_STATUS_U; row[4]=BGT_AREA_L; row[5]=BGT_AREA_L; return 6;
        case HUD_NOTICE_CURED:
            row[0]=HUD_STATUS_C; row[1]=HUD_STATUS_U; row[2]=BGT_AREA_R;
            row[3]=BGT_AREA_E; row[4]=BGT_AREA_D; return 5;
        case HUD_NOTICE_HPFULL:
            row[0]=BGT_AREA_H; row[1]=BGT_AREA_P; row[2]=BGT_AREA_F;
            row[3]=HUD_STATUS_U; row[4]=BGT_AREA_L; row[5]=BGT_AREA_L; return 6;
        case HUD_NOTICE_GUARD:
            row[0]=BGT_AREA_G; row[1]=HUD_STATUS_U; row[2]=BGT_AREA_A;
            row[3]=BGT_AREA_R; row[4]=BGT_AREA_D; return 5;
        default:
            row[0]=BGT_AREA_I; row[1]=BGT_AREA_N; row[2]=BGT_AREA_V;
            row[3]=BGT_AREA_E; row[4]=BGT_AREA_R; row[5]=BGT_AREA_T; return 6;
    }
}

static u8 notice_palette(u8 kind, u8 amount) {
    u8 value = kind & 0x7F;
    if (!(kind & HUD_NOTICE_STATUS)) {
        if (kind == HUD_NOTICE_BOOMERANG || kind == HUD_NOTICE_HOOKSHOT
            || kind == HUD_NOTICE_SECONDARY) {
            palette_bg_load(5, notice_gold); return 5;
        }
        if (kind == HUD_NOTICE_STATMAX) value = amount;
        if (value == STAT_MP || value == STAT_SPD) return 6;
        if (value == STAT_DEF) { palette_bg_load(5, notice_violet); return 5; }
        if (value == STAT_LCK) { palette_bg_load(5, notice_gold); return 5; }
        return 7;
    }
    if (value == QSTATUS_POISON || value == QSTATUS_REGEN
        || value == HUD_NOTICE_CURED) {
        palette_bg_load(5, notice_green); return 5;
    }
    if (value == QSTATUS_BURN || value == QSTATUS_BRITTLE
        || value == QSTATUS_BLEED) return 7;
    if (value == HUD_NOTICE_MPFULL) return 6;
    if (value == HUD_NOTICE_HPFULL || value == HUD_NOTICE_GUARD) return 7;
    if (value == QSTATUS_SLOW || value == QSTATUS_STOP
        || value == QSTATUS_HASTE) return 6;
    palette_bg_load(5, notice_violet);
    return 5;
}

static u8 stat_word(u8 stat, u8 *row) {
    switch (stat) {
        case STAT_HP:
            row[0]=BGT_AREA_H; row[1]=BGT_AREA_P; return 2;
        case STAT_MP:
            row[0]=BGT_AREA_M; row[1]=BGT_AREA_P; return 2;
        case STAT_ATK:
            row[0]=BGT_AREA_A; row[1]=BGT_AREA_T; row[2]=BGT_AREA_K; return 3;
        case STAT_DEF:
            row[0]=BGT_AREA_D; row[1]=BGT_AREA_E; row[2]=BGT_AREA_F; return 3;
        case STAT_SPD:
            row[0]=HUD_STATUS_S; row[1]=BGT_AREA_P; row[2]=BGT_AREA_D; return 3;
        default:
            row[0]=BGT_AREA_L; row[1]=HUD_STATUS_C; row[2]=BGT_AREA_K; return 3;
    }
}

static u8 pal_code(u8 code) {
    if (code == 0) { palette_bg_load(5, notice_gold); return 5; }
    if (code == 1) { palette_bg_load(5, notice_violet); return 5; }
    if (code == 2) { palette_bg_load(5, notice_green); return 5; }
    return code;
}

static void draw_notice(u8 kind, u8 amount) {
    u8 row[6] = { HUD_BLANK, HUD_BLANK, HUD_BLANK,
        HUD_BLANK, HUD_BLANK, HUD_BLANK };
    u8 attrs[6];
    u8 width;
    u8 start;
    u8 i;
    u8 pal;
    if (kind == HUD_NOTICE_BOSS_LINK) {
        palette_bg_load(5, amount == 0 ? notice_gold
            : amount == 1 ? notice_violet : notice_green);
        pal = 5;
    } else pal = notice_palette(kind, amount);
    if (kind & HUD_NOTICE_STATUS) width = status_word((u8)(kind & 0x7F), row);
    else if (kind == HUD_NOTICE_SECONDARY) {
        row[0]=amount ? HUD_STATUS_B : HUD_STATUS_S;
        row[1]=amount ? BGT_AREA_O : BGT_AREA_T;
        row[2]=amount ? BGT_AREA_M : BGT_AREA_A;
        row[3]=amount ? HUD_STATUS_B : BGT_AREA_R; width=4;
    }
    else if (kind == HUD_NOTICE_HOOKSHOT) {
        row[0]=BGT_AREA_H; row[1]=BGT_AREA_O;
        row[2]=BGT_AREA_O; row[3]=BGT_AREA_K; width=4;
    }
    else if (kind == HUD_NOTICE_BOOMERANG) {
        row[0]=HUD_STATUS_B; row[1]=BGT_AREA_O; row[2]=BGT_AREA_O;
        row[3]=BGT_AREA_M; row[4]=BGT_AREA_E; row[5]=BGT_AREA_R;
        width=6;
    }
    else if (kind == HUD_NOTICE_BOSS_LINK) {
        if (amount == 0) {
            row[0]=BGT_AREA_L; row[1]=BGT_AREA_I;
            row[2]=BGT_AREA_N; row[3]=BGT_AREA_K; width=4;
        } else if (amount == 1) {
            row[0]=BGT_AREA_N; row[1]=BGT_AREA_O;
            row[3]=BGT_AREA_A; row[4]=BGT_AREA_T; row[5]=BGT_AREA_K; width=6;
        } else {
            row[0]=BGT_AREA_A; row[1]=BGT_AREA_T; row[2]=BGT_AREA_T;
            row[3]=BGT_AREA_A; row[4]=HUD_STATUS_C; row[5]=BGT_AREA_K; width=6;
        }
    }
    else if (kind == HUD_NOTICE_STATMAX) {
        if (amount == STAT_HP) {
            // Max HP reads as a gold heart container, not the red refill.
            pal = pal_code(0);
            row[0] = HUD_HEART_FULL; width = 1;
        } else width = stat_word(amount, row);
        row[width++] = BGT_AREA_M;
        row[width++] = BGT_AREA_A;
        row[width++] = HUD_STATUS_X;
    }
    else if (kind == HUD_NOTICE_WORD) {
        pal = pal_code(hud_notice_word_fill(amount, row));
        width = 6;
        while (width && row[width - 1] == HUD_BLANK) width--;
    }
    else if (kind == HUD_NOTICE_NEED) {
        row[0]=BGT_AREA_N; row[1]=BGT_AREA_E; row[2]=BGT_AREA_E; row[3]=BGT_AREA_D;
        width = 4;
        if (amount > 99) amount = 99;
        if (amount >= 10) row[width++] = (u8)(HUD_DIGIT_0 + amount / 10);
        row[width++] = (u8)(HUD_DIGIT_0 + amount % 10);
        pal = 7;
    }
    else if (kind == HUD_NOTICE_COIN) {
        row[0] = HUD_COIN; row[1] = HUD_STATUS_PLUS; width = 2;
        if (amount > 99) amount = 99;
        if (amount >= 10) row[width++] = (u8)(HUD_DIGIT_0 + amount / 10);
        row[width++] = (u8)(HUD_DIGIT_0 + amount % 10);
        pal = pal_code(0);
    }
    else {
        u8 sign = HUD_STATUS_PLUS;
        u8 stat = kind;
        if (kind == HUD_NOTICE_HEAL || kind == HUD_NOTICE_MANA) {
            row[0] = kind == HUD_NOTICE_HEAL ? BGT_AREA_H : BGT_AREA_M;
            row[1] = kind == HUD_NOTICE_HEAL ? BGT_AREA_E : BGT_AREA_A;
            row[2] = kind == HUD_NOTICE_HEAL ? BGT_AREA_A : BGT_AREA_N;
            row[3] = kind == HUD_NOTICE_HEAL ? BGT_AREA_L : BGT_AREA_A;
            width = 4;
            pal = kind == HUD_NOTICE_HEAL ? 7 : 6;
            stat = 0xFF;
        } else if (kind == HUD_NOTICE_LOSS) {
            stat = (u8)(amount >> 4);
            amount &= 0x0F;
            sign = HUD_STATUS_MINUS;
            pal = 7;
        }
        if (stat == STAT_HP) {
            // Item HP is permanent max HP: MAX(heart)+2 / MAX(heart)-2.
            row[0]=BGT_AREA_M; row[1]=BGT_AREA_A; row[2]=HUD_STATUS_X;
            row[3]=HUD_HEART_FULL; width = 4;
            if (kind == STAT_HP) pal = pal_code(0);
        } else if (stat != 0xFF) width = stat_word(stat, row);
        row[width++] = sign;
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
    // Real status ailments keep the short card; every pickup result,
    // refusal, and curse holds HUD_NOTICE_PICKUP_FRAMES.
    hud_notice_ticks = ((kind & HUD_NOTICE_STATUS)
            && (u8)(kind & 0x7F) < QSTATUS_COUNT
            && (u8)(kind & 0x7F) != QSTATUS_CURSE)
        ? HUD_NOTICE_FRAMES
        : (kind == HUD_NOTICE_WORD && amount >= NW_AEGIS)
            ? HUD_NOTICE_POWERUP_FRAMES : HUD_NOTICE_PICKUP_FRAMES;
    draw_notice(notice_kind, notice_amount);
}

void hud_notice_reset(void) BANKED {
    hud_notice_ticks = 0;
    notice_kind = 0xFF;
    queue_head = 0;
    queue_count = 0;
    link_mode = 0xFF;
}

static u8 notice_already_queued(u8 kind) {
    u8 i;
    if (hud_notice_ticks && notice_kind == kind) return 1;
    for (i = 0; i < queue_count; ++i)
        if (queued_kind[(u8)((queue_head + i) % HUD_NOTICE_QUEUE)] == kind)
            return 1;
    return 0;
}

static u8 notice_pair_queued(u8 kind, u8 amount) {
    u8 i, q;
    if (hud_notice_ticks && notice_kind == kind && notice_amount == amount)
        return 1;
    for (i = 0; i < queue_count; ++i) {
        q = (u8)((queue_head + i) % HUD_NOTICE_QUEUE);
        if (queued_kind[q] == kind && queued_amount[q] == amount) return 1;
    }
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

static void show_pair(u8 kind, u8 amount) {
    if (hud_notice_ticks) {
        if (!notice_pair_queued(kind, amount)) queue_notice(kind, amount);
        return;
    }
    begin_notice(kind, amount);
}

void hud_show_stat_gain(u8 stat, u8 amount) BANKED {
    // A boost that could not move its stat says so (SPDMAX) instead of
    // silently dropping one line of a multi-stat relic.
    if (!amount) { hud_show_stat_max(stat); return; }
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

static void show_unique_notice(u8 kind) {
    if (hud_notice_ticks) {
        if (!notice_already_queued(kind)) queue_notice(kind, 0);
        return;
    }
    begin_notice(kind, 0);
}

// Heart/shop refusals under Hunger spell out the rule: HUNGER, NOHEAL.
// A short Curse status blocks healing too; name that instead of HUNGER.
void hud_show_healing_blocked(void) BANKED {
    show_unique_notice(CURSE_PLAYER_HEALING_BLOCKED()
        ? (u8)(HUD_NOTICE_STATUS | HUD_NOTICE_HUNGER)
        : (u8)(HUD_NOTICE_STATUS | QSTATUS_CURSE));
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_NOHEAL));
}

// A Hunger curse names both itself and its effect: HUNGER, then NOHEAL.
void hud_show_hunger_curse(void) BANKED {
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_HUNGER));
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_NOHEAL));
}

void hud_show_mp_full(void) BANKED {
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_MPFULL));
}

void hud_show_hp_full(void) BANKED {
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_HPFULL));
}

void hud_show_cured(void) BANKED {
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_CURED));
}

// A Farfold Cache relic stays put while its reliquary still has living
// foes. The red orb used to ignore the hero with no word of why.
void hud_show_cache_guarded(void) BANKED {
    show_unique_notice((u8)(HUD_NOTICE_STATUS | HUD_NOTICE_GUARD));
}

void hud_show_stat_max(u8 stat) BANKED {
    show_pair(HUD_NOTICE_STATMAX, stat);
}

void hud_notice_pair(u8 kind, u8 amount) BANKED {
    show_pair(kind, amount);
}

void hud_show_boomerang(void) BANKED {
    if (hud_notice_ticks) {
        if (!notice_already_queued(HUD_NOTICE_BOOMERANG))
            queue_notice(HUD_NOTICE_BOOMERANG, 0);
        return;
    }
    begin_notice(HUD_NOTICE_BOOMERANG, 0);
}

void hud_show_hookshot(void) BANKED {
    if (hud_notice_ticks) queue_notice(HUD_NOTICE_HOOKSHOT, 0);
    else begin_notice(HUD_NOTICE_HOOKSHOT, 0);
}

void hud_show_secondary(u8 bomb) BANKED {
    if (hud_notice_ticks) queue_notice(HUD_NOTICE_SECONDARY,bomb);
    else begin_notice(HUD_NOTICE_SECONDARY,bomb);
}

void hud_show_boss_link(u8 mode) BANKED {
    if (mode == 3) {
        link_mode = 0xFF;
        if (notice_kind == HUD_NOTICE_BOSS_LINK && hud_notice_ticks) {
            hud_notice_ticks = 1;
            hud_tick_notice();
        }
        return;
    }
    if (link_mode == mode) return;
    link_mode = mode;
    if (hud_notice_ticks && notice_kind != HUD_NOTICE_BOSS_LINK)
        queue_notice(notice_kind, notice_amount);
    begin_notice(HUD_NOTICE_BOSS_LINK, mode);
    if (mode == 0) hud_notice_ticks = 32;
    else if (mode == 1) hud_notice_ticks = 96;
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
