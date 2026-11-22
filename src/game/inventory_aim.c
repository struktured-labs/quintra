#pragma bank 22

// B-item icon picker and bidirectional B-item walk. Pinned to bank 22 so
// bank 14 (inventory.c) and bank 16 (hookshot.c) keep their emergency floors.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <stdio.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/inventory_aim.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "render/palette.h"
#include "render/text.h"
#include "render/tiles.h"

BANKREF(inventory_aim_enter)

#define INV_FRAME_H    ((u8)0xF6u)
#define INV_FRAME_VL   ((u8)0xF7u)
#define INV_FRAME_VR   ((u8)0xF8u)
#define INV_FRAME_TL   ((u8)0xF9u)
#define INV_FRAME_TR   ((u8)0xFAu)
#define INV_FRAME_BL   ((u8)0xFBu)
#define INV_FRAME_BR   ((u8)0xFCu)

static const u8 inv_frame_tiles[7][16] = {
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
};

// Class power, Boomerang, Hookshot, Morningstar, Bomb Bag.
static const u8 k_items[5] = {
    0, ITEM_ID_BOOMERANG, ITEM_ID_HOOKSHOT, ITEM_ID_MORNINGSTAR, ITEM_ID_BOMBS
};

static u8 *bg_map(void) {
    return (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
}

static u8 class_item(void) {
    return (u8)(10 + player.class_id);
}

static u8 slot_item(u8 slot) {
    return slot == 0 ? class_item() : k_items[slot];
}

static u8 owns(u8 id) {
    u8 i;
    if (id == class_item()) return 1;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == id) return 1;
    return 0;
}

void secondary_cycle_step(i8 dir) BANKED {
    u8 items[5];
    u8 n = 0;
    u8 i, cur = 0;
    items[n++] = class_item();
    if (owns(ITEM_ID_BOOMERANG)) items[n++] = ITEM_ID_BOOMERANG;
    if (owns(ITEM_ID_HOOKSHOT)) items[n++] = ITEM_ID_HOOKSHOT;
    if (owns(ITEM_ID_MORNINGSTAR)) items[n++] = ITEM_ID_MORNINGSTAR;
    if (owns(ITEM_ID_BOMBS)) items[n++] = ITEM_ID_BOMBS;
    for (i = 0; i < n; ++i)
        if (items[i] == player.active_item) { cur = i; break; }
    if (dir < 0) cur = (u8)(cur == 0 ? (u8)(n - 1) : (u8)(cur - 1));
    else cur = (u8)(cur + 1 >= n ? 0 : cur + 1);
    player.active_item = items[cur];
}

void secondary_cycle(void) BANKED {
    secondary_cycle_step(1);
}


static const char *item_name(u8 id) {
    if (id == ITEM_ID_BOOMERANG) return "BOOMERANG";
    if (id == ITEM_ID_HOOKSHOT) return "HOOKSHOT";
    if (id == ITEM_ID_MORNINGSTAR) return "MORNINGSTAR";
    if (id == ITEM_ID_BOMBS) return "BOMB BAG";
    switch (id) {
        case 10: return "MOONFIRE";
        case 11: return "THUNDER";
        case 12: return "HEX";
        case 13: return "BLIZZARD";
        case 14: return "BRAMBLE";
        default: return "ITEM";
    }
}

static const char *item_tip(u8 id) {
    if (id == ITEM_ID_BOOMERANG) return "STUN AND FETCH";
    if (id == ITEM_ID_HOOKSHOT) return "LATCH AND PULL";
    if (id == ITEM_ID_MORNINGSTAR) return "SWING AROUND YOU";
    if (id == ITEM_ID_BOMBS) return "2 MP THROW OR DROP";
    switch (id) {
        case 10: return "HOLD: FLAME WARD";
        case 11: return "HOLD: STONESKIN";
        case 12: return "HOLD: SHADOW VEIL";
        case 13: return "HOLD: CURE 5 MP";
        case 14: return "HOLD THORN MIRROR";
        default: return "SEE SIG";
    }
}

static u8 item_tile(u8 id, u8 *prop) {
    *prop = 3;
    if (id == 10) return SPR_ITEM_SWIFT_FANG;
    if (id == 11) return SPR_ITEM_WARD_CHARM;
    if (id == 12) return SPR_ITEM_HUNTER_EYE;
    if (id == 13) return SPR_ITEM_MANA_GEM;
    if (id == 14) return SPR_ITEM_THORN;
    if (id == ITEM_ID_BOOMERANG) return SPR_ITEM_BOOMERANG;
    if (id == ITEM_ID_HOOKSHOT) return SPR_WAYGEAR_HOOK;
    if (id == ITEM_ID_MORNINGSTAR) {
        *prop = 11;
        return SPR_ITEM_MORNINGSTAR;
    }
    if (id == ITEM_ID_BOMBS) {
        *prop = SPR_BOMB_BAG_PROP;
        return SPR_ITEM_BOMB_BAG;
    }
    return SPR_ITEM_ASCEND;
}

static void write_field(const char *s, u8 width) {
    while (width && *s) { putchar(*s++); width--; }
    while (width--) putchar(' ');
}

static void frame_row(u8 y, u8 left, u8 right) {
    u8 row[20];
    u8 x;
    row[0] = left;
    for (x = 1; x < 19; ++x) row[x] = INV_FRAME_H;
    row[19] = right;
    set_tiles(0, y, 20, 1, bg_map(), row);
}

static void frame_sides(u8 y) {
    u8 tile = INV_FRAME_VL;
    set_tiles(0, y, 1, 1, bg_map(), &tile);
    tile = INV_FRAME_VR;
    set_tiles(19, y, 1, 1, bg_map(), &tile);
}

static void attr_cells(u8 x, u8 y, u8 w, u8 h, u8 slot) {
    u8 row[20];
    u8 i, r;
    u8 *map = bg_map();
    for (i = 0; i < w; ++i) row[i] = slot;
    VBK_REG = 1;
    for (r = 0; r < h; ++r) set_tiles(x, (u8)(y + r), w, 1, map, row);
    VBK_REG = 0;
}

static void draw_outer_frame(void) {
    u8 y;
    VBK_REG = 0;
    set_bkg_data(INV_FRAME_H, 7, inv_frame_tiles[0]);
    frame_row(0, INV_FRAME_TL, INV_FRAME_TR);
    for (y = 1; y <= 16; ++y) frame_sides(y);
    frame_row(17, INV_FRAME_BL, INV_FRAME_BR);
}

static void draw_well(u8 col, u8 pal) {
    u8 row[3];
    u8 *map = bg_map();
    row[0] = INV_FRAME_TL; row[1] = INV_FRAME_H; row[2] = INV_FRAME_TR;
    set_tiles(col, 4, 3, 1, map, row);
    row[0] = INV_FRAME_VL; row[1] = 0; row[2] = INV_FRAME_VR;
    set_tiles(col, 5, 3, 1, map, row);
    row[0] = INV_FRAME_BL; row[1] = INV_FRAME_H; row[2] = INV_FRAME_BR;
    set_tiles(col, 6, 3, 1, map, row);
    attr_cells(col, 4, 3, 3, pal);
}

static u8 selected_slot(void) {
    u8 i, id = player.active_item;
    if (id == class_item() || id < ITEM_ID_BOOMERANG) return 0;
    for (i = 1; i < 5; ++i) if (k_items[i] == id) return i;
    return 0;
}

static void place_icons(u8 reload) {
    u8 i, tile, prop, pal, col;
    u8 sel = selected_slot();
    if (reload) tiles_load_pickup_sprites();
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
    for (i = 0; i < 5; ++i) {
        if (!owns(slot_item(i))) continue;
        tile = item_tile(slot_item(i), &prop);
        pal = (i == sel) ? (u8)((prop & 0x08) | 2) : prop;
        col = (u8)(2 + i * 3);
        set_sprite_tile(i, tile);
        set_sprite_prop(i, pal);
        move_sprite(i, (u8)(8 + (col + 1) * 8), (u8)(16 + 5 * 8));
    }
}

// LCD-on update used when the cursor or aim mode changes. A full
// DISPLAY_OFF / cls / tile-reload flashes the CGB screen on every step.
static void inventory_aim_refresh(void) {
    u8 i, pal, col;
    u8 sel = selected_slot();
    u8 id = slot_item(sel);
    extern u8 player_penta_aim;

    for (i = 0; i < 5; ++i) {
        col = (u8)(2 + i * 3);
        if (i == sel) pal = 1;
        else if (owns(slot_item(i))) pal = 2;
        else pal = 0;
        attr_cells(col, 4, 3, 3, pal);
    }
    gotoxy(1, 8); write_field(item_name(id), 18);
    attr_cells(1, 8, 18, 1, 1);
    gotoxy(1, 9); write_field(item_tip(id), 18);
    attr_cells(1, 9, 18, 1, 3);
    gotoxy(1, 12); text_write(player_penta_aim ? "MODE  HOLD AIM" : "MODE  CLASSIC");
    attr_cells(1, 12, 18, 1, 2);
    place_icons(0);
}

void inventory_aim_enter(void) BANKED {
    u8 i, pal, col;
    u8 sel = selected_slot();
    u8 id = slot_item(sel);
    extern u8 player_penta_aim;

    DISPLAY_OFF;
    HIDE_SPRITES;
    cls();
    draw_outer_frame();
    palette_bg_fill_attrs(0);
    attr_cells(0, 0, 20, 1, 1);

    gotoxy(5, 0); text_write(" B ITEMS ");
    gotoxy(2, 2); text_write("PICK YOUR B ITEM");
    attr_cells(1, 2, 18, 1, 1);

    for (i = 0; i < 5; ++i) {
        col = (u8)(2 + i * 3);
        if (i == sel) pal = 1;
        else if (owns(slot_item(i))) pal = 2;
        else pal = 0;
        draw_well(col, pal);
    }

    gotoxy(1, 8); write_field(item_name(id), 18);
    attr_cells(1, 8, 18, 1, 1);
    gotoxy(1, 9); write_field(item_tip(id), 18);
    attr_cells(1, 9, 18, 1, 3);
    gotoxy(1, 10); text_write("B FIRES THIS ITEM");

    gotoxy(1, 12); text_write(player_penta_aim ? "MODE  HOLD AIM" : "MODE  CLASSIC");
    attr_cells(1, 12, 18, 1, 2);
    gotoxy(1, 13); text_write("A SWITCHES MODE");
    gotoxy(1, 14); text_write("LEFT RIGHT TO PICK");
    gotoxy(1, 16); text_write("SEL GEAR  B PLAY");

    place_icons(1);
    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

u8 inventory_aim_tick(u8 pressed) BANKED {
    extern u8 player_penta_aim;
    if (pressed & (J_START | J_B)) return 1;
    if (pressed & J_SELECT) return 2;
    if (pressed & J_A) {
        player_penta_aim ^= 1;
        sfx_play(SFX_TICK);
        inventory_aim_refresh();
        return 0;
    }
    if (pressed & (J_RIGHT | J_DOWN)) {
        secondary_cycle_step(1);
        sfx_play(SFX_TICK);
        inventory_aim_refresh();
        return 0;
    }
    if (pressed & (J_LEFT | J_UP)) {
        secondary_cycle_step((i8)-1);
        sfx_play(SFX_TICK);
        inventory_aim_refresh();
        return 0;
    }
    return 0;
}
