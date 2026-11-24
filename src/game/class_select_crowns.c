#pragma bank 27
// CLASS_SELECT crown tiles, name-row counts, and the selected-hero head
// sprite. Lives in a roomy bank so class-select and meta stay above the
// 256-byte emergency floor.

#include <gb/gb.h>
#include <gbdk/console.h>

#include "core/types.h"
#include "game/class_select.h"
#include "game/sram.h"
#include "render/crown_tiles.h"
#include "render/palette.h"
#include "render/text.h"
#include "content.h"
#include <string.h>

// Easy: simple 3-point gold crown (GPT Image 2.6 Sunburst, quantized 8x8).
// Normal: jeweled crown, gold points and a ruby cluster (royal palette).
static const u8 crown_tiles[2][16] = {
    {0x08,0x2A,0x08,0x7F,0x00,0x7F,0x00,0x7F,0x00,0x3E,0x00,0x00,0x00,0x00,0x00,0x00},
    {0x00,0xAA,0x00,0xFF,0x5A,0xFF,0x3C,0xFF,0x81,0x7E,0x66,0x18,0x00,0x00,0x00,0x00},
};

// Pixels right of the 16x16 preview origin, and pixels to lift the 8x8
// crown. Lift 4 puts the Easy band on the first preview row (1px overlap
// with ear/crest/antenna tips; the taller Normal jewel overlaps 1px more).
static const u8 crown_ox[HERO_TROPHY_SLOTS]   = { 4, 4, 3, 4, 4 };
static const u8 crown_lift[HERO_TROPHY_SLOTS] = { 4, 4, 4, 4, 4 };


// Same metal/ruby as the BG gold/royal slots, but color 0 is transparent.
static const u16 crown_obj_gold[4] = {
    0,
    BGR555(12,  8,  2),
    BGR555(22, 16,  4),
    BGR555(31, 25,  6),
};
static const u16 crown_obj_royal[4] = {
    0,
    BGR555(12,  8,  2),
    BGR555(31, 25,  6),
    BGR555(31,  6,  8),
};

void class_select_arm_crown_pals(void) BANKED {
    u8 i;
    for (i = 0; i < 4; ++i) {
        obj_pal_cache[CS_PAL_OBJ_GOLD][i] = crown_obj_gold[i];
        obj_pal_cache[CS_PAL_OBJ_ROYAL][i] = crown_obj_royal[i];
    }
}

void class_select_load_crowns(void) BANKED {
    set_sprite_data(SPR_CROWN_EASY, 2, crown_tiles[0]);
    sram_meta_hero_trophies(class_select_hero_wins, class_select_hero_tier);
}

void class_select_draw_crowns(void) BANKED {
    u8 i;
    for (i = 0; i < HERO_TROPHY_SLOTS; ++i) {
        if (!class_select_hero_wins[i]) continue;
        {
            u8 w = class_select_hero_wins[i];
            gotoxy(CS_COUNT_COL, (u8)(3 + i));
            if (w >= 100) text_digit((u8)(w / 100));
            if (w >= 10) text_digit((u8)((w / 10) % 10));
            text_digit((u8)(w % 10));
        }
    }
}

void class_select_hide_head_crown(void) BANKED {
    move_sprite(SPR_CROWN_OBJ, 0, 0);
}

void class_select_place_head_crown(u8 sx, u8 sy) BANKED {
    u8 id = class_select_cursor;
    u8 tile, pal;
    if (id >= HERO_TROPHY_SLOTS || !class_select_hero_wins[id]) {
        class_select_hide_head_crown();
        return;
    }
    if (class_select_hero_tier[id] >= CROWN_TIER_NORMAL) {
        tile = SPR_CROWN_NORMAL;
        pal = CS_PAL_OBJ_ROYAL;
    } else {
        tile = SPR_CROWN_EASY;
        pal = CS_PAL_OBJ_GOLD;
    }
    set_sprite_tile(SPR_CROWN_OBJ, tile);
    set_sprite_prop(SPR_CROWN_OBJ, pal);
    move_sprite(SPR_CROWN_OBJ,
                (u8)(sx + crown_ox[id]),
                (u8)(sy - crown_lift[id]));
}

u8 cs_row_names[HERO_TROPHY_SLOTS][20];
u8 cs_row_stats[20];

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
    u8 i;
    // Every name row: selected name in its accent, optional win count
    // in gold (Easy) or royal (Normal+). The "> " cursor stays body white.
    // The crown itself is an OBJ on the selected preview's head.
    for (i = 0; i < HERO_TROPHY_SLOTS; ++i) {
        memset(cs_row_names[i], CS_PAL_BODY, 20);
        if (i == class_select_cursor)
            memset(cs_row_names[i] + 4, CS_PAL_ACCENT, class_select_name_len);
        if (class_select_hero_wins[i]) {
            u8 pal = (class_select_hero_tier[i] >= CROWN_TIER_NORMAL)
                ? CS_PAL_ROYAL : CS_PAL_GOLD;
            u8 w = class_select_hero_wins[i];
            u8 col = CS_COUNT_COL;
            if (w >= 100) cs_row_names[i][col++] = pal;
            if (w >= 10) cs_row_names[i][col++] = pal;
            cs_row_names[i][col] = pal;
        }
    }
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
