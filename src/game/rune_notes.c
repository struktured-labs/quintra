#pragma bank 19

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
static const u8 bgt_note_lit_a[16] = { 0x00, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x24, 0x00, 0x24, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const u8 bgt_note_lit_b[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x3C, 0x00, 0x24, 0x00, 0x24, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x00 };
static const u8 bgt_note_lit_c[16] = { 0x00, 0x00, 0x00, 0x00, 0x3C, 0x3C, 0x24, 0x24, 0x24, 0x24, 0x3C, 0x3C, 0x00, 0x00, 0x00, 0x00 };

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

void puzzle_load_note_palettes(void) BANKED {
    tiles_load_note_plates();
    if (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE && room_rune_count) {
        palette_bg_load(BGPAL_CRYSTAL, rune_pal_low);
        palette_bg_load(BGPAL_DOOR, rune_pal_high);
    }
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
    for (i = 0; i < room_rune_count; ++i)
        rune_paint_plate(i);
}

void voice_plate(u8 plate) BANKED {
    sfx_play_rune(room_rune_pitch[plate]);
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
