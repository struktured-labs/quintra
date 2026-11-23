#pragma bank 27

/* Roulette capsule FX and four replacement faces.
   GPT Image 2.6 Sunburst, quantized and cleaned to 8x8 2bpp.
   OBJ VRAM bank 1, tiles 192-199 (gap after bomb-wave 188-191,
   before WILL_MAXFX 200-203).
   Tile 0 is a top-left quarter-bezel; the other three corners are
   the same tile with S_FLIPX / S_FLIPY around the 8x8 icon. */
#include <gb/gb.h>
#include "render/tiles.h"

const u8 sprite_roulette_fx[8][16] = {
    { 0x3F, 0x7F, 0x7F, 0xC0, 0x40, 0xC0, 0x40, 0xC0, 0x40, 0xC0, 0x40, 0xC0, 0x40, 0xC0, 0x00, 0x80 }, /* frame_corner */
    { 0x01, 0x01, 0x08, 0x0A, 0x20, 0x04, 0x40, 0x50, 0x82, 0x12, 0x04, 0x10, 0x20, 0x20, 0x00, 0x40 }, /* smear */
    { 0x10, 0x00, 0x08, 0x00, 0x08, 0x24, 0x99, 0x08, 0x7E, 0x18, 0x10, 0x14, 0x08, 0x00, 0x10, 0x00 }, /* spark_a */
    { 0x10, 0x10, 0x11, 0x44, 0x38, 0x10, 0xFE, 0x92, 0x38, 0x10, 0x88, 0x22, 0x10, 0x10, 0x00, 0x00 }, /* spark_b */
    { 0x22, 0x66, 0x66, 0xC3, 0x66, 0x42, 0x66, 0x00, 0x7E, 0x99, 0x66, 0x00, 0x66, 0x00, 0x00, 0x42 }, /* face_formation */
    { 0x3C, 0x18, 0x42, 0x42, 0x81, 0x00, 0x81, 0x81, 0x81, 0x81, 0x81, 0x00, 0x42, 0x42, 0x3C, 0x18 }, /* face_halo */
    { 0x03, 0x06, 0x06, 0x0E, 0x0E, 0x18, 0x18, 0x30, 0x30, 0x60, 0x60, 0xC0, 0x80, 0xC0, 0x00, 0x80 }, /* face_longreach */
    { 0x00, 0x42, 0xC3, 0xA5, 0xE7, 0xA5, 0x66, 0x00, 0x66, 0xC3, 0x42, 0x42, 0x00, 0x00, 0x00, 0x00 }, /* face_wingmates */
};

void tiles_load_roulette_fx(void) BANKED {
    /* Caller must have VBK_REG = 1. */
    set_sprite_data(SPR_ROULETTE_FRAME, 8, sprite_roulette_fx[0]);
}

#include "game/entity.h"
#include "game/pickup.h"
#include "game/powerup.h"


i8 powerup_roulette_bob;
u8 powerup_roulette_fxflags;
u8 powerup_roulette_spark_t;

static u8 roulette_pop;
static u8 roulette_smear_t;
static const i8 roulette_pop_bob[3] = { -2, -3, -1 };
static const i8 roulette_lock_bob[8] = { -2, -4, -3, -1, 1, 0, 0, 0 };

void powerup_roulette_clear_fx(void) BANKED {
    powerup_roulette_bob = 0;
    powerup_roulette_fxflags = 0;
    powerup_roulette_spark_t = 0;
    roulette_pop = 0;
    roulette_smear_t = 0;
}

void powerup_roulette_tick_fx(u8 just_changed, u8 locking, u8 lock_frame) BANKED {
    u8 flags = RF_FRAME;
    powerup_roulette_bob = 0;
    if (just_changed) {
        roulette_pop = 3;
        roulette_smear_t = 2;
    }
    if (locking) {
        if (lock_frame && lock_frame <= 8)
            powerup_roulette_bob = roulette_lock_bob[lock_frame - 1];
        if (lock_frame && lock_frame <= 16) flags |= RF_SPARK;
        if (lock_frame && lock_frame <= 3) {
            flags |= RF_SMEAR;
            roulette_smear_t = 1;
        }
        powerup_roulette_spark_t = lock_frame;
    } else {
        if (roulette_pop) {
            powerup_roulette_bob = roulette_pop_bob[3 - roulette_pop];
            roulette_pop--;
        }
        if (roulette_smear_t) {
            flags |= RF_SMEAR;
            roulette_smear_t--;
        }
    }
    powerup_roulette_fxflags = flags;
}


static const i8 spark_ox[8] = { 8, 6, 0, -6, -8, -6,  0,  6 };
static const i8 spark_oy[8] = { 0,-6,-8, -6,  0,  6,  8,  6 };

static u8 emit(u8 oam, u8 x, u8 y, u8 tile, u8 prop) {
    OAM_item_t *it;
    if (oam >= entity_oam_cap) return oam;
    if (y <= 8 || y >= 160 || x >= 176) return oam;
    it = &shadow_OAM[oam];
    it->y = y;
    it->x = x;
    it->tile = tile;
    it->prop = prop;
    return (u8)(oam + 1);
}

u8 powerup_roulette_decorate(u8 oam, u8 sx, u8 sy) BANKED {
    u8 flags = powerup_roulette_fxflags;
    u8 t, i, k, tile, pal;
    if (!flags) return oam;

    if (flags & RF_FRAME) {
        pal = SPR_ROULETTE_PROP;
        oam = emit(oam, (u8)(sx - 4), (u8)(sy - 4), SPR_ROULETTE_FRAME, pal);
        oam = emit(oam, (u8)(sx + 4), (u8)(sy - 4), SPR_ROULETTE_FRAME,
            (u8)(pal | S_FLIPX));
        oam = emit(oam, (u8)(sx - 4), (u8)(sy + 4), SPR_ROULETTE_FRAME,
            (u8)(pal | S_FLIPY));
        oam = emit(oam, (u8)(sx + 4), (u8)(sy + 4), SPR_ROULETTE_FRAME,
            (u8)(pal | S_FLIPX | S_FLIPY));
    }
    if (flags & RF_SMEAR)
        oam = emit(oam, sx, sy, SPR_ROULETTE_SMEAR, SPR_ROULETTE_PROP);
    if (flags & RF_SPARK) {
        t = powerup_roulette_spark_t;
        pal = ((t & 2) ? (u8)(S_BANK) : SPR_ROULETTE_PROP);
        for (i = 0; i < 4; ++i) {
            k = (u8)(((t >> 1) + (u8)(i << 1)) & 7);
            tile = (u8)(((t + i) & 1) ? SPR_ROULETTE_SPARK_B
                : SPR_ROULETTE_SPARK_A);
            oam = emit(oam, (u8)(sx + spark_ox[k]), (u8)(sy + spark_oy[k]),
                tile, pal);
        }
    }
    return oam;
}
