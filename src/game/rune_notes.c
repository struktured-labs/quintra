#pragma bank 21
// Bank 21 since the Riftwild tile-life pass (bank 19 filled up).

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "render/palette.h"
#include "render/tiles.h"

static const u8 bgt_note_a[16] = { 0x00, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x00, 0x00 };
static const u8 bgt_note_b[16] = { 0x00, 0x00, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x7E, 0x00, 0x00 };
static const u8 bgt_note_c[16] = { 0x00, 0x00, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x7E, 0x00, 0x00 };
/* Sunken/pressed variants: a thicker top and left shadow with a smaller
   fill shifted down-right, so a latched plate stays visually distinct
   after the flash without spending another tile id or palette slot. */
static const u8 bgt_note_lit_a[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7C, 0x00, 0x7C, 0x00, 0x7C, 0x00, 0x7C, 0x00, 0x00, 0x00 };
static const u8 bgt_note_lit_b[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7C, 0x00, 0x7C, 0x00, 0x7C, 0x00, 0x7C, 0x00, 0x00 };
static const u8 bgt_note_lit_c[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x7C, 0x00, 0x00 };

/* Packed note palettes, borrowed only while a rune-sequence room is loaded.
   Colour 0 is a shared dark outline. Pitches differ in both hue and
   luminance so red-green colour blindness still separates them. */
static const u16 rune_pal_low[4] = {
    BGR555(2, 2, 4),
    BGR555(4, 8, 28),
    BGR555(4, 24, 24),
    BGR555(31, 28, 4),
};
static const u16 rune_pal_high[4] = {
    BGR555(2, 2, 4),
    BGR555(31, 16, 2),
    BGR555(28, 8, 24),
    BGR555(31, 31, 26),
};

static u8 rune_flash_index = 0xFF;
static u8 rune_flash_frames;

static void set_tile_live(u8 x, u8 y, u8 tile, u8 attr) {
    room_tilemap[y][x] = tile;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

void tiles_load_note_plates(void) BANKED {
    set_bkg_data(BGT_NOTE_0,     1, bgt_note_a);
    set_bkg_data(BGT_NOTE_1,     1, bgt_note_b);
    set_bkg_data(BGT_NOTE_2,     1, bgt_note_c);
    set_bkg_data(BGT_NOTE_3,     1, bgt_note_a);
    set_bkg_data(BGT_NOTE_4,     1, bgt_note_b);
    set_bkg_data(BGT_NOTE_LIT_0, 1, bgt_note_lit_a);
    set_bkg_data(BGT_NOTE_LIT_1, 1, bgt_note_lit_b);
    set_bkg_data(BGT_NOTE_LIT_2, 1, bgt_note_lit_c);
    set_bkg_data(BGT_NOTE_LIT_3, 1, bgt_note_lit_a);
    set_bkg_data(BGT_NOTE_LIT_4, 1, bgt_note_lit_b);
    set_bkg_data(BGT_NOTE_FLASH, 1, bgt_note_c);
}

static void load_note_slot(u8 slot, const u16 *pal, u8 dim) {
    u16 tmp[4];
    u8 i;
    if (!dim) {
        palette_bg_load(slot, pal);
        return;
    }
    for (i = 0; i < 4; ++i) tmp[i] = (u16)((pal[i] >> 1) & 0x3DEF);
    palette_bg_load(slot, tmp);
}

/* 60% of the way toward white, so a latched plate keeps its hue but
   clearly steps up in luminance once the flash is over. */
static u16 brighten_colour(u16 c) {
    u8 r = (u8)(c & 31);
    u8 g = (u8)((c >> 5) & 31);
    u8 b = (u8)((c >> 10) & 31);
    r = (u8)(r + (u8)(((u8)(31 - r) * 3u) / 5u));
    g = (u8)(g + (u8)(((u8)(31 - g) * 3u) / 5u));
    b = (u8)(b + (u8)(((u8)(31 - b) * 3u) / 5u));
    return BGR555(r, g, b);
}

void puzzle_apply_note_palettes(u8 dim) BANKED {
    u16 low[4], high[4];
    u8 i;
    if (!PUZZLE_KIND_HAS_NOTES(room_puzzle_kind) || !room_rune_count)
        return;
    for (i = 0; i < 4; ++i) {
        low[i] = rune_pal_low[i];
        high[i] = rune_pal_high[i];
    }
    for (i = 0; i < room_rune_count; ++i) {
        if (puzzle_plate_is_lit(i)) {
            u8 pitch = room_rune_pitch[i];
            if (pitch <= 2)
                low[pitch + 1] = brighten_colour(rune_pal_low[pitch + 1]);
            else
                high[(u8)(pitch - 2)] = brighten_colour(rune_pal_high[(u8)(pitch - 2)]);
        }
    }
    load_note_slot(BGPAL_CRYSTAL, low, dim);
    load_note_slot(BGPAL_DOOR, high, dim);
}

void puzzle_load_note_palettes(void) BANKED {
    if (!PUZZLE_KIND_HAS_NOTES(room_puzzle_kind) || !room_rune_count)
        return;
    tiles_load_note_plates();
    puzzle_apply_note_palettes(0);
}

static void rune_paint_plate(u8 plate) {
    u8 pitch = room_rune_pitch[plate];
    u8 tile = puzzle_plate_is_lit(plate) ? RUNE_LIT_TILE(pitch)
                                         : RUNE_IDLE_TILE(pitch);
    set_tile_live(room_rune_x[plate], room_rune_y[plate],
                  tile, RUNE_NOTE_PAL(pitch));
}

void rune_cancel_flash(void) BANKED {
    rune_flash_index = 0xFF;
    rune_flash_frames = 0;
}

void rune_start_flash(u8 plate) BANKED {
    if (rune_flash_index != 0xFF && rune_flash_index != plate)
        rune_paint_plate(rune_flash_index);
    rune_flash_index = plate;
    rune_flash_frames = 8;
    set_tile_live(room_rune_x[plate], room_rune_y[plate],
                  RUNE_FLASH_TILE, RUNE_FLASH_PAL);
}

void tick_rune_flash(void) BANKED {
    if (rune_flash_index == 0xFF) return;
    if (--rune_flash_frames) return;
    rune_paint_plate(rune_flash_index);
    rune_cancel_flash();
}

void rune_paint_all(void) BANKED {
    u8 i;
    rune_cancel_flash();
    puzzle_apply_note_palettes(0);
    for (i = 0; i < room_rune_count; ++i)
        rune_paint_plate(i);
}

void voice_plate(u8 plate) BANKED {
    sfx_play_rune(room_rune_pitch[plate]);
    puzzle_apply_note_palettes(0);
    rune_start_flash(plate);
}

u8 puzzle_rune_attr(u8 tile) BANKED {
    if (tile == BGT_NOTE_FLASH) return BGPAL_DOOR;
    if (tile >= BGT_NOTE_0 && tile <= BGT_NOTE_LIT_4)
        return RUNE_NOTE_PAL(RUNE_PITCH_FROM_TILE(tile));
    if (tile == BGT_DOOR || tile == BGT_DOOR_LOCKED
        || tile == BGT_CRYSTAL || tile == BGT_PORTAL)
        return BGPAL_CRACK;
    return 0xFF;
}
