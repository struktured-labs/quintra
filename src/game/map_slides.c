#pragma bank 31
#include <gb/gb.h>
#include <gb/cgb.h>
#include "core/types.h"
#include "game/map_slides.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/tiles.h"

#define BGPAL_SHOP 5

// One-tile hero icons (scripts/gen_map_hero_icons.py). Colour indices match
// the class sprites, so they wear the hero's own palette.
static const u8 map_hero_mini[5][16] = {
    { 0x00, 0x81, 0x00, 0xC3, 0x7E, 0x81, 0x7E, 0xA5, 0x7E, 0x81, 0x3C, 0x42, 0x24, 0x5A, 0x00, 0x66 }, // wolfkin
    { 0x00, 0x30, 0x30, 0x48, 0x38, 0x56, 0x3E, 0x41, 0x3C, 0xC2, 0x5C, 0xA2, 0x14, 0x6A, 0x00, 0x1B }, // sauran
    { 0x00, 0x38, 0x38, 0x44, 0x38, 0x57, 0x3E, 0x43, 0x38, 0x46, 0x7C, 0x82, 0x28, 0x54, 0x00, 0x6C }, // corvin
    { 0x00, 0x18, 0x18, 0x3C, 0x18, 0x66, 0x7E, 0x95, 0x7E, 0x81, 0x3C, 0x42, 0x24, 0x5A, 0x00, 0x66 }, // picsean
    { 0x00, 0x42, 0x00, 0x24, 0x18, 0x24, 0xBD, 0xDB, 0xFF, 0xC3, 0x3C, 0x5A, 0x18, 0x24, 0x00, 0x18 }, // vespine
};

// Slideshow: a map cell that holds two or more icons shows each in turn,
// half a second apiece (#264). Overlays are small marks stamped on top of a
// node (rift diamond, Veil coin); they are re-stamped after every turn.
#define SLIDE_CELLS  6
#define SLIDE_ICONS  4
#define SLIDE_FRAMES 30
#define OVERLAYS     4
u8 map_slide_n;
u8 map_slide_phase;
static u8 slide_clock;
static u8 slide_x[SLIDE_CELLS], slide_y[SLIDE_CELLS], slide_len[SLIDE_CELLS];
static u8 slide_icon[SLIDE_CELLS][SLIDE_ICONS];
static u8 slide_attr[SLIDE_CELLS][SLIDE_ICONS];
static u8 cell_x, cell_y, cell_n;
static u8 cell_icon[SLIDE_ICONS], cell_attr[SLIDE_ICONS];
static u8 overlay_n;
static u8 overlay_x[OVERLAYS], overlay_y[OVERLAYS];
static u8 overlay_tile[OVERLAYS], overlay_attr[OVERLAYS];

static void put_attr(u8 x, u8 y, u8 tile, u8 attr) {
    VBK_REG = 0; set_bkg_tiles(x, y, 1, 1, &tile);
    VBK_REG = 1; set_bkg_tiles(x, y, 1, 1, &attr);
    VBK_REG = 0;
}

// Big dungeon-node icons are four tiles on one palette.
static u8 big_attr(u8 base) {
    if (base == BGT_MAP_BIG_HERE) return 7;
    if (base == BGT_MAP_BIG_GOAL) return BGPAL_CRYSTAL;
    if (base == BGT_MAP_BIG_BOSS) return BGPAL_CRACK;
    if (base == BGT_MAP_BIG_CACHE) return BGPAL_DOOR;
    if (base == BGT_MAP_BIG_SHOP) return BGPAL_SHOP;
    return BGPAL_FLOOR;
}

static u8 is_big(u8 icon) {
    return (icon >= BGT_MAP_BIG_ROOM && icon < BGT_MAP_SHOP) ? 1 : 0;
}

static void draw_icon(u8 x, u8 y, u8 icon, u8 attr) {
    put_attr(x, y, icon, attr);
    if (!is_big(icon)) return;
    put_attr((u8)(x + 1), y, (u8)(icon + 1), attr);
    put_attr(x, (u8)(y + 1), (u8)(icon + 2), attr);
    put_attr((u8)(x + 1), (u8)(y + 1), (u8)(icon + 3), attr);
}

// Compass entry, after the map atlas is loaded and with the LCD off. The
// "you" marks become the current hero: the dungeon node is the class's real
// 16x16 sprite, copied from OBJ VRAM, and the one-tile mark is that class's
// mini. Both wear the hero's live OBJ palette (gear tier included) over the
// map's dark ground.
void map_marks_begin(void) BANKED {
    u8 buf[64];
    u16 pal[4];
    u8 c = player.class_id < 5 ? player.class_id : 0;
    map_slide_n = 0;
    map_slide_phase = 0;
    slide_clock = 0;
    overlay_n = 0;
    VBK_REG = 0;
    // The LCD is off here, so OBJ VRAM reads directly. (GBDK's
    // get_sprite_data would add a library routine to the full home bank.)
    {
        const u8 *src = (const u8 *)(0x8000u
            + (u16)(SPR_CLASS_BASE + c * SPR_CLASS_STRIDE) * 16u);
        u8 k;
        for (k = 0; k < 64; ++k) buf[k] = src[k];
    }
    set_bkg_data(BGT_MAP_BIG_HERE, 4, buf);
    set_bkg_data(BGT_MAP_HERE, 1, map_hero_mini[c]);
    pal[0] = BGR555(1, 3, 2);
    pal[1] = obj_pal_cache[1][1];
    pal[2] = obj_pal_cache[1][2];
    pal[3] = obj_pal_cache[1][3];
    palette_bg_load(7, pal);
}

static void cell_begin(u8 x, u8 y) {
    cell_x = x;
    cell_y = y;
    cell_n = 0;
}

static void cell_add(u8 icon, u8 attr) {
    u8 k;
    for (k = 0; k < cell_n; ++k) if (cell_icon[k] == icon) return;
    if (cell_n >= SLIDE_ICONS) return;
    cell_icon[cell_n] = icon;
    cell_attr[cell_n] = attr;
    cell_n++;
}

// First icon to draw now; two or more also join the slideshow.
static u8 cell_end(u8 fallback) {
    u8 k;
    if (!cell_n) return fallback;
    if (cell_n >= 2 && map_slide_n < SLIDE_CELLS) {
        slide_x[map_slide_n] = cell_x;
        slide_y[map_slide_n] = cell_y;
        slide_len[map_slide_n] = cell_n;
        for (k = 0; k < cell_n; ++k) {
            slide_icon[map_slide_n][k] = cell_icon[k];
            slide_attr[map_slide_n][k] = cell_attr[k];
        }
        map_slide_n++;
    }
    return cell_icon[0];
}

// Every icon dungeon cell i holds. flags: 1 seen, 2 boss hint, 4 unclaimed
// cache charted. The hero leads; the rest keep the old single-icon
// precedence, so a cell's first slide is what the static map used to show.
u8 map_dungeon_node_icon(u8 i, u8 here, u8 goal, u8 flags, u8 x, u8 y) BANKED {
    cell_begin(x, y);
    if (i == here) cell_add(BGT_MAP_BIG_HERE, 7);
    if (flags & 1) {
        if ((i == run_state_dungeon_shop_cell()
                && run_state_dungeon_cell_visited(i))
            || powerup_shrine_map_mark(i))
            cell_add(BGT_MAP_BIG_SHOP, BGPAL_SHOP);
    }
    if (flags & 4) cell_add(BGT_MAP_BIG_CACHE, BGPAL_DOOR);
    if (flags & 2) cell_add(BGT_MAP_BIG_BOSS, BGPAL_CRACK);
    if (i == goal) cell_add(BGT_MAP_BIG_GOAL, BGPAL_CRYSTAL);
    return cell_end(BGT_MAP_BIG_ROOM);
}

// The hero's cell on a one-tile map (Riftwild, town). `under` is what the
// cell would show without the hero; a real landmark shares the cell.
u8 map_here_over(u8 x, u8 y, u8 under, u8 under_attr) BANKED {
    cell_begin(x, y);
    cell_add(BGT_MAP_HERE, 7);
    if (under != BGT_MAP_ROOM && under != BGT_MAP_UNKNOWN
        && under != BGT_MAP_HERE && !(under & 0x80))
        cell_add(under, under_attr);
    return cell_end(BGT_MAP_HERE);
}

// A small mark stamped over a node. Remembered so a slide turn cannot
// erase it.
void map_overlay_put(u8 x, u8 y, u8 tile, u8 attr) BANKED {
    put_attr(x, y, tile, attr);
    if (overlay_n >= OVERLAYS) return;
    overlay_x[overlay_n] = x;
    overlay_y[overlay_n] = y;
    overlay_tile[overlay_n] = tile;
    overlay_attr[overlay_n] = attr;
    overlay_n++;
}

void map_slide_tick(void) BANKED {
    u8 c, k;
    if (!map_slide_n) return;
    if (++slide_clock < SLIDE_FRAMES) return;
    slide_clock = 0;
    map_slide_phase++;
    // Start at the top of VBlank so a node never shows a new tile on its
    // old palette for a frame.
    wait_vbl_done();
    for (c = 0; c < map_slide_n; ++c) {
        k = (u8)(map_slide_phase % slide_len[c]);
        draw_icon(slide_x[c], slide_y[c], slide_icon[c][k], slide_attr[c][k]);
    }
    for (c = 0; c < overlay_n; ++c)
        put_attr(overlay_x[c], overlay_y[c], overlay_tile[c], overlay_attr[c]);
}

