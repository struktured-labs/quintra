#pragma bank 22
// Pack/help carved-frame tiles and row helpers. Moved out of bank 14 so
// inventory.c stays on the 256-byte emergency floor.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "game/inventory_frame.h"

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

static const u8 inv_frame_tiles[9][16] = {
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

static u8 *inventory_bg_map(void) {
    return (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
}

static void frame_row(u8 y, u8 left, u8 right) {
    u8 row[20];
    u8 x;
    row[0] = left;
    for (x = 1; x < 19; ++x) row[x] = INV_FRAME_H;
    row[19] = right;
    set_tiles(0, y, 20, 1, inventory_bg_map(), row);
}

static void frame_sides(u8 y) {
    u8 tile = INV_FRAME_VL;
    set_tiles(0, y, 1, 1, inventory_bg_map(), &tile);
    tile = INV_FRAME_VR;
    set_tiles(19, y, 1, 1, inventory_bg_map(), &tile);
}

void inventory_draw_pack_frames(void) BANKED {
    u8 y;
    VBK_REG = 0;
    set_bkg_data(INV_FRAME_BASE, 9, inv_frame_tiles[0]);
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

void inventory_attr_row(u8 y, u8 slot) BANKED {
    u8 attrs[20];
    u8 x;
    u8 *map = (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
    for (x = 0; x < 20; ++x) attrs[x] = slot;
    VBK_REG = 1;
    set_tiles(0, y, 20, 1, map, attrs);
    VBK_REG = 0;
}

