#pragma bank 255
// Sun Lattice runtime: VRAM overlay, strikes, Hookshot spin, solve dwell.
// Fixtures are BGT_PILLAR in room_tilemap; beams are pure display over
// floor. Both are painted from VRAM bank 1 tiles 56..62 (spec question 2),
// clear of Hexa's bank-1 40..55 and the Mire roots' bank-0 55..63.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sun_lattice.h"
#include "render/tiles.h"

#define SLT_EMITTER (SUN_LATTICE_TILE + 0)
#define SLT_VANE    (SUN_LATTICE_TILE + 1)
#define SLT_BIFROST (SUN_LATTICE_TILE + 2)
#define SLT_OBELISK (SUN_LATTICE_TILE + 3)
#define SLT_BEAM_H  (SUN_LATTICE_TILE + 4)
#define SLT_BEAM_V  (SUN_LATTICE_TILE + 5)
#define SLT_BEAM_X  (SUN_LATTICE_TILE + 6)
#define SL_ATTR_BANK1 0x08
#define SL_ATTR_HFLIP 0x20

static const u8 sl_tile_art[SUN_LATTICE_TILE_COUNT * 16] = {
    // emitter
    0xDB, 0x3C, 0xBD, 0x7E, 0x66, 0xE7, 0xDB, 0xDB, 0xDB, 0xDB, 0x66, 0xE7, 0xBD, 0x7E, 0xDB, 0x3C,
    // vane
    0x05, 0x03, 0x0A, 0x07, 0x14, 0x0E, 0x28, 0x1C, 0x50, 0x38, 0xA0, 0x70, 0x40, 0xE0, 0x80, 0xC0,
    // bifrost
    0x18, 0x18, 0x24, 0x3C, 0x5A, 0x66, 0xBD, 0xC3, 0xBD, 0xC3, 0x5A, 0x66, 0x24, 0x3C, 0x18, 0x18,
    // obelisk
    0x7E, 0x00, 0x81, 0x7E, 0xBD, 0x7E, 0xBD, 0x66, 0xBD, 0x66, 0xBD, 0x7E, 0x81, 0x7E, 0x7E, 0x00,
    // beam_h
    0x00, 0xFF, 0x00, 0xFF, 0xAA, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x55, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
    // beam_v
    0x38, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0x1C, 0xFF,
    // beam_x
    0x38, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0x1C, 0xFF,
};

static u8 old_h[SL_BITS];
static u8 old_v[SL_BITS];
static u8 sl_deb[SL_MAX_FIX];
static u8 sl_dwell;
static u8 sl_all_lit;

static u8 find_fixture(u8 x, u8 y) {
    u8 i;
    if (x >= SL_MAP_W || y >= SL_MAP_H) return 0xFF;
    for (i = 0; i < sl_n; ++i)
        if (sl_x[i] == x && sl_y[i] == y) return i;
    return 0xFF;
}

static void put_cell(u8 x, u8 y, u8 tile, u8 attr) {
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

static void paint_fixture(u8 i) {
    u8 k = sl_kind[i];
    u8 tile = SLT_OBELISK;
    u8 attr = SL_ATTR_BANK1;
    if (k == SLK_EMITTER) {
        tile = SLT_EMITTER; attr |= BGPAL_CRACK;
    } else if (k == SLK_VANE || k == SLK_FIXED) {
        tile = SLT_VANE;
        attr |= (k == SLK_FIXED) ? BGPAL_WALL : BGPAL_CRYSTAL;
        if (sl_ang[i]) attr |= SL_ATTR_HFLIP;
    } else if (k == SLK_BIFROST) {
        tile = SLT_BIFROST; attr |= BGPAL_CRYSTAL;
    } else {
        attr |= sl_lit[i] ? BGPAL_CRACK : BGPAL_WALL;
    }
    put_cell(sl_x[i], sl_y[i], tile, attr);
}

static u8 bit_of(const u8 *b, u16 c) {
    return (u8)(b[(u8)(c >> 3)] & (u8)(1u << (u8)(c & 7)));
}

// Beams draw only over plain floor. Over spikes, plates, water or chasm
// the ray still travels but stays submerged so no hazard art is hidden.
static void paint_cell(u8 x, u8 y, u16 c) {
    u8 t = room_tilemap[y][x];
    u8 h, v;
    if (t != BGT_FLOOR && t != BGT_FLOOR2 && t != BGT_FLOOR3) return;
    h = bit_of(sl_beam_h, c);
    v = bit_of(sl_beam_v, c);
    if (h || v)
        put_cell(x, y, (h && v) ? SLT_BEAM_X : h ? SLT_BEAM_H : SLT_BEAM_V,
            SL_ATTR_BANK1 | BGPAL_FLOOR);
    else put_cell(x, y, t, BGPAL_FLOOR);
}

static void remember_beams(void) {
    u8 i;
    for (i = 0; i < SL_BITS; ++i) {
        old_h[i] = sl_beam_h[i];
        old_v[i] = sl_beam_v[i];
    }
}

static void repaint_changed(void) {
    u8 i, b, x = 0, y = 0;
    u16 c = 0;
    for (i = 0; i < SL_BITS; ++i) {
        u8 diff = (u8)((old_h[i] ^ sl_beam_h[i]) | (old_v[i] ^ sl_beam_v[i]));
        for (b = 0; b < 8; ++b) {
            if ((diff & (u8)(1u << b)) && c < (u16)(SL_MAP_W * SL_MAP_H))
                paint_cell(x, y, c);
            c++;
            if (++x == SL_MAP_W) { x = 0; y++; }
        }
    }
    for (i = 0; i < sl_n; ++i)
        if (sl_kind[i] == SLK_OBELISK) paint_fixture(i);
    remember_beams();
}

static void carve(u8 cx, u8 cy, u8 r) {
    u8 x, y;
    u8 x0 = (cx > r) ? (u8)(cx - r) : 0;
    u8 y0 = (cy > r) ? (u8)(cy - r) : 0;
    u8 x1 = (u8)(cx + r), y1 = (u8)(cy + r);
    if (x0 < 1) x0 = 1;
    if (y0 < 1) y0 = 1;
    if (x1 > SL_MAP_W - 2) x1 = SL_MAP_W - 2;
    if (y1 > SL_MAP_H - 2) y1 = SL_MAP_H - 2;
    for (y = y0; y <= y1; ++y)
        for (x = x0; x <= x1; ++x)
            room_tilemap[y][x] = BGT_FLOOR;
}

void sun_lattice_prepare(u32 seed, u8 role, u8 solved) BANKED {
    u8 i, x, y;
    u16 c;
    sl_generate(seed, run_state.bosses_beaten, role);
    // Carve the solved light path as a 3-wide floor road, a 5x5 apron
    // around every fixture, and the body-width cross that joins all four
    // door thresholds. Every mandatory vane is therefore reachable by
    // melee from dry floor (spec question 4), even in Mire or Keep courts.
    for (i = 0; i < sl_n; ++i) {
        u8 a = sl_ang[i];
        if (sl_kind[i] == SLK_VANE) sl_ang[i] = sl_solved_ang[i];
        sl_solved_ang[i] = a;   // temporarily holds the scrambled angle
    }
    sl_trace(0);
    c = 0;
    for (y = 0; y < SL_MAP_H; ++y)
        for (x = 0; x < SL_MAP_W; ++x, ++c)
            if (bit_of(sl_beam_h, c) || bit_of(sl_beam_v, c)) carve(x, y, 1);
    for (i = 0; i < SL_MAP_W - 2; ++i) {
        room_tilemap[7][i + 1] = room_tilemap[8][i + 1] = room_tilemap[9][i + 1] = BGT_FLOOR;
    }
    for (i = 1; i < SL_MAP_H - 1; ++i) {
        room_tilemap[i][9] = room_tilemap[i][10] = room_tilemap[i][11] = BGT_FLOOR;
    }
    for (i = 0; i < sl_n; ++i) {
        u8 a = sl_solved_ang[i];
        sl_solved_ang[i] = sl_ang[i];
        if (!solved) sl_ang[i] = a;
        carve(sl_x[i], sl_y[i], 2);
    }
    // Join the Brazier's apron to the central cross.
    y = sl_y[0];
    for (x = (sl_x[0] < 10) ? sl_x[0] : 10; x <= ((sl_x[0] > 10) ? sl_x[0] : 10); ++x)
        carve(x, y, 1);
    for (i = 0; i < sl_n; ++i) room_tilemap[sl_y[i]][sl_x[i]] = BGT_PILLAR;
    if (sl_crystal_x != 0xFF && !solved)
        room_tilemap[sl_crystal_y][sl_crystal_x] = BGT_CRYSTAL;
    for (i = 0; i < SL_MAX_FIX; ++i) sl_deb[i] = 0;
    sl_dwell = 0;
    sl_all_lit = sl_trace(1);
    remember_beams();
}

void sun_lattice_paint_all(void) BANKED {
    u8 i, x, y;
    u16 c = 0;
    if (room_puzzle_kind != PUZZLE_SUN_LATTICE) return;
    VBK_REG = 1;
    set_bkg_data(SUN_LATTICE_TILE, SUN_LATTICE_TILE_COUNT, sl_tile_art);
    VBK_REG = 0;
    sl_all_lit = sl_trace(1);
    for (i = 0; i < sl_n; ++i) paint_fixture(i);
    for (y = 0; y < SL_MAP_H; ++y)
        for (x = 0; x < SL_MAP_W; ++x, ++c)
            if (bit_of(sl_beam_h, c) || bit_of(sl_beam_v, c))
                paint_cell(x, y, c);
    remember_beams();
}

void sun_lattice_retrace(void) BANKED {
    if (room_puzzle_kind != PUZZLE_SUN_LATTICE) return;
    sl_all_lit = sl_trace(1);
    repaint_changed();
}

static u8 spin(u8 i) {
    if (sl_kind[i] != SLK_VANE || !room_puzzle_locked) return 0;
    if (sl_deb[i]) return 1;
    sl_deb[i] = SL_DEBOUNCE;
    sl_ang[i] ^= 1;
    paint_fixture(i);
    sun_lattice_retrace();
    sfx_play(SFX_WEAK);
    return 1;
}

u8 sun_lattice_strike(u8 tx, u8 ty) BANKED {
    u8 i;
    if (room_puzzle_kind != PUZZLE_SUN_LATTICE) return 0;
    i = find_fixture(tx, ty);
    if (i == 0xFF) return 0;
    spin(i);
    return 1;
}

u8 sun_lattice_hook(u8 tx, u8 ty) BANKED {
    u8 i;
    if (room_puzzle_kind != PUZZLE_SUN_LATTICE) return 0;
    i = find_fixture(tx, ty);
    if (i == 0xFF) return 0;
    // Snag-and-spin (spec question 3): a rotatable vane turns 90 degrees
    // and the hook retracts. Fixed vanes, Wedges, Braziers, Obelisks and
    // a solved room's frozen vanes keep the ordinary latch-and-pull.
    return spin(i);
}

u8 sun_lattice_tick(void) BANKED {
    u8 i;
    for (i = 0; i < sl_n; ++i)
        if (sl_deb[i]) sl_deb[i]--;
    if (!room_puzzle_locked) return 0;
    if (!sl_all_lit) {
        sl_dwell = 0;
        return 0;
    }
    if (++sl_dwell < SL_DWELL) return 0;
    return 1;
}
