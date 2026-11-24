#pragma bank 27
// CLASS_SELECT crown tiles and blit. Lives in a roomy bank so class-select and meta
// page stays above the 256-byte emergency floor.

#include <gb/gb.h>
#include <gbdk/console.h>

#include "core/types.h"
#include "game/class_select.h"
#include "game/sram.h"
#include "render/crown_tiles.h"
#include "render/text.h"
#include "content.h"
#include <string.h>

// Easy: simple 3-point gold crown (GPT Image 2.6 Sunburst, quantized 8x8).
// Normal: jeweled crown, gold points and a ruby cluster (royal palette).
static const u8 crown_tiles[2][16] = {
    {0x08,0x2A,0x08,0x7F,0x00,0x7F,0x00,0x7F,0x00,0x3E,0x00,0x00,0x00,0x00,0x00,0x00},
    {0x00,0xAA,0x00,0xFF,0x5A,0xFF,0x3C,0xFF,0x81,0x7E,0x66,0x18,0x00,0x00,0x00,0x00},
};

void class_select_load_crowns(void) BANKED {
    set_bkg_data(BGT_CROWN_EASY, 2, crown_tiles[0]);
    sram_meta_hero_trophies(class_select_hero_wins, class_select_hero_tier);
}

void class_select_draw_crowns(void) BANKED {
    u8 i;
    for (i = 0; i < HERO_TROPHY_SLOTS; ++i) {
        if (!class_select_hero_wins[i]) continue;
        {
            u8 tile = (class_select_hero_tier[i] >= CROWN_TIER_NORMAL)
                ? BGT_CROWN_NORMAL : BGT_CROWN_EASY;
            u8 w = class_select_hero_wins[i];
            set_bkg_tile_xy(CS_CROWN_COL, (u8)(3 + i), tile);
            gotoxy((u8)(CS_CROWN_COL + 1), (u8)(3 + i));
            if (w >= 100) text_digit((u8)(w / 100));
            if (w >= 10) text_digit((u8)((w / 10) % 10));
            text_digit((u8)(w % 10));
        }
    }
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
    // Every name row: selected name in its accent, optional crown and
    // count in gold (or royal for a Normal-tier jeweled crown). The
    // "> " cursor stays body white.
    for (i = 0; i < HERO_TROPHY_SLOTS; ++i) {
        memset(cs_row_names[i], CS_PAL_BODY, 20);
        if (i == class_select_cursor)
            memset(cs_row_names[i] + 4, CS_PAL_ACCENT, class_select_name_len);
        if (class_select_hero_wins[i]) {
            u8 pal = (class_select_hero_tier[i] >= CROWN_TIER_NORMAL)
                ? CS_PAL_ROYAL : CS_PAL_GOLD;
            u8 w = class_select_hero_wins[i];
            u8 col = CS_CROWN_COL;
            cs_row_names[i][col++] = pal;
            if (w >= 100) cs_row_names[i][col++] = CS_PAL_GOLD;
            if (w >= 10) cs_row_names[i][col++] = CS_PAL_GOLD;
            cs_row_names[i][col] = CS_PAL_GOLD;
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
