#pragma bank 10

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <stdio.h>

#include "audio/sfx.h"
#include "game/inventory_visual.h"
#include "game/inventory_waygear.h"
#include "game/player.h"
#include "game/waygear.h"
#include "render/palette.h"
#include "render/text.h"
#include "content.h"

static u8 waygear_cursor;

static const char *const waygear_names[WAYGEAR_COUNT] = {
    "TITAN GLOVE", "TIDE RAFT", "RIFT HOOK"
};

static const char *const nature_names[5] = {
    "THORN CUT", "LIFT STONE", "CROSS GAPS", "DEEP WATER", "HIVE VENTS"
};

#define INV_FRAME_BASE ((u8)0xF6u)
#define INV_FRAME_H    ((u8)0xF6u)
#define INV_FRAME_VL   ((u8)0xF7u)
#define INV_FRAME_VR   ((u8)0xF8u)
#define INV_FRAME_TL   ((u8)0xF9u)
#define INV_FRAME_TR   ((u8)0xFAu)
#define INV_FRAME_BL   ((u8)0xFBu)
#define INV_FRAME_BR   ((u8)0xFCu)
#define INV_FRAME_TLJ  ((u8)0xFDu)
#define INV_FRAME_TRJ  ((u8)0xFEu)

static const u8 waygear_frame_tiles[9][16] = {
    { 0,0, 0,0, 0,0, 0xFF,0xFF, 0,0xFF, 0,0, 0,0, 0,0 },
    { 0x10,0x18, 0x10,0x18, 0x10,0x18, 0x10,0x18,
      0x10,0x18, 0x10,0x18, 0x10,0x18, 0x10,0x18 },
    { 0x08,0x18, 0x08,0x18, 0x08,0x18, 0x08,0x18,
      0x08,0x18, 0x08,0x18, 0x08,0x18, 0x08,0x18 },
    { 0,0, 0,0, 0,0, 0x1F,0x1F, 0x10,0x1F,
      0x10,0x18, 0x10,0x18, 0x10,0x18 },
    { 0,0, 0,0, 0,0, 0xF8,0xF8, 0x08,0xF8,
      0x08,0x18, 0x08,0x18, 0x08,0x18 },
    { 0x10,0x18, 0x10,0x18, 0x10,0x18, 0x1F,0x1F,
      0,0x1F, 0,0, 0,0, 0,0 },
    { 0x08,0x18, 0x08,0x18, 0x08,0x18, 0xF8,0xF8,
      0,0xF8, 0,0, 0,0, 0,0 },
    { 0x10,0x18, 0x10,0x18, 0x10,0x18, 0x1F,0x1F,
      0x10,0x1F, 0x10,0x18, 0x10,0x18, 0x10,0x18 },
    { 0x08,0x18, 0x08,0x18, 0x08,0x18, 0xF8,0xF8,
      0x08,0xF8, 0x08,0x18, 0x08,0x18, 0x08,0x18 },
};

static u8 *waygear_bg_map(void) {
    return (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
}

static void frame_row(u8 y, u8 left, u8 right) {
    u8 row[20];
    u8 x;
    row[0] = left;
    for (x = 1; x < 19; ++x) row[x] = INV_FRAME_H;
    row[19] = right;
    set_tiles(0, y, 20, 1, waygear_bg_map(), row);
}

static void frame_sides(u8 y) {
    u8 tile = INV_FRAME_VL;
    set_tiles(0, y, 1, 1, waygear_bg_map(), &tile);
    tile = INV_FRAME_VR;
    set_tiles(19, y, 1, 1, waygear_bg_map(), &tile);
}

static void draw_frames(void) {
    u8 y;
    VBK_REG = 0;
    set_bkg_data(INV_FRAME_BASE, 9, waygear_frame_tiles[0]);
    frame_row(0, INV_FRAME_TL, INV_FRAME_TR);
    for (y = 1; y <= 3; ++y) frame_sides(y);
    frame_row(4, INV_FRAME_TLJ, INV_FRAME_TRJ);
    for (y = 5; y <= 7; ++y) frame_sides(y);
    frame_row(8, INV_FRAME_TLJ, INV_FRAME_TRJ);
    for (y = 9; y <= 12; ++y) frame_sides(y);
    frame_row(13, INV_FRAME_TLJ, INV_FRAME_TRJ);
    for (y = 14; y <= 16; ++y) frame_sides(y);
    frame_row(17, INV_FRAME_BL, INV_FRAME_BR);
}

static void attr_row(u8 y, u8 slot) {
    u8 attrs[20];
    u8 x;
    for (x = 0; x < 20; ++x) attrs[x] = slot;
    VBK_REG = 1;
    set_tiles(0, y, 20, 1, waygear_bg_map(), attrs);
    VBK_REG = 0;
}

static void draw_page(void) {
    u8 i;
    DISPLAY_OFF;
    cls();
    draw_frames();
    gotoxy(4, 0); text_write(" WAYGEAR ");
    gotoxy(5, 4); text_write(" NATURE ");
    gotoxy(6, 8); text_write(" LOADOUT ");
    gotoxy(6, 13); text_write(" RULE ");
    gotoxy(1, 1); text_write(player.class_id < N_CLASSES
        ? classes[player.class_id].name : "?");
    gotoxy(1, 2); text_write("INNATE ");
    text_write(player.class_id < 5 ? nature_names[player.class_id] : "?");
    gotoxy(1, 5); text_write("HERO POWER IS FREE");
    gotoxy(1, 6); text_write("GEAR OPENS ALT WAY");
    gotoxy(1, 7); text_write("ONE ITEM RESONATES");

    inventory_prepare_sprites();
    for (i = 4; i < 10; ++i) move_sprite(i, 0, 0);
    for (i = 0; i < WAYGEAR_COUNT; ++i) {
        u8 row = (u8)(9 + i);
        gotoxy(1, row);
        putchar(i == waygear_cursor ? '>' : ' ');
        putchar(player.waygear_equipped == i ? '*' : ' ');
        text_write((player.waygear_owned & WAYGEAR_BIT(i))
            ? waygear_names[i] : "???????????");
        set_sprite_tile((u8)(4 + i), (u8)(SPR_WAYGEAR_GLOVE + i));
        set_sprite_prop((u8)(4 + i),
            (player.waygear_owned & WAYGEAR_BIT(i)) ? 3 : 1);
        move_sprite((u8)(4 + i), 144, (u8)(88 + i * 8));
    }
    gotoxy(1, 14); text_write("* EQUIPPED SLOT");
    gotoxy(1, 15); text_write("UP/DN PICK A EQUIP");
    gotoxy(1, 16); text_write("SEL PACK B RETURN");
    gotoxy(2, 17); text_write("EXPLORE. REMEMBER.");
    palette_bg_fill_attrs(0);
    attr_row(0, 1); attr_row(4, 1); attr_row(8, 2);
    for (i = 9; i <= 12; ++i) attr_row(i, 2);
    attr_row(13, 3);
    for (i = 14; i <= 16; ++i) attr_row(i, 3);
    attr_row(17, 1);
    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void inventory_waygear_enter(void) BANKED {
    waygear_cursor = player.waygear_equipped < WAYGEAR_COUNT
        ? player.waygear_equipped : 0;
    draw_page();
}

u8 inventory_waygear_tick(u8 pressed) BANKED {
    if (pressed & (J_START | J_B)) return INVENTORY_WAYGEAR_EXIT;
    if (pressed & J_SELECT) return INVENTORY_WAYGEAR_PACK;
    if (pressed & J_UP) {
        waygear_cursor = waygear_cursor
            ? (u8)(waygear_cursor - 1) : WAYGEAR_COUNT - 1;
        sfx_play(SFX_DOOR);
        draw_page();
    } else if (pressed & J_DOWN) {
        waygear_cursor++;
        if (waygear_cursor >= WAYGEAR_COUNT) waygear_cursor = 0;
        sfx_play(SFX_DOOR);
        draw_page();
    } else if (pressed & J_A) {
        if (player.waygear_owned & WAYGEAR_BIT(waygear_cursor)) {
            player.waygear_equipped = waygear_cursor;
            sfx_play(SFX_CLEAR);
        } else {
            sfx_play(SFX_HURT);
        }
        draw_page();
    }
    return INVENTORY_WAYGEAR_STAY;
}
