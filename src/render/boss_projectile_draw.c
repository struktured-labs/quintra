#pragma bank 26
// Boss / heavy-B projectile OAM writer, split from boss_projectile_art.c
// (bank 15 had no room for the batched writer). Art and palettes stay there.
#include <gb/gb.h>
#include "game/boss_projectile.h"
#include "game/projectile.h"
#include "game/entity.h"

// Batched OAM writer for one boss shot. C decides the cell layout once into
// bp_*; bp_emit streams y,x,tile,prop for each cell through one pointer.
// SDCC spilled every local of the old per-cell setter loop (~1.2 KB of
// stack shuffling); this keeps the per-cell cost to a few register moves.
static u8 bp_yx[8];
static u8 bp_t, bp_p, bp_n;

static void bp_emit(u8 *p) __naked {
    p;  /* DE */
    __asm
        ld  h, d
        ld  l, e
        ld  de, #_bp_yx
        ld  a, (_bp_t)
        ld  b, a
        ld  a, (_bp_n)
        ld  c, a
    1$:
        ld  a, (de)
        inc de
        ld  (hl+), a
        ld  a, (de)
        inc de
        ld  (hl+), a
        ld  a, b
        inc b
        ld  (hl+), a
        ld  a, (_bp_p)
        ld  (hl+), a
        dec c
        jr  nz, 1$
        ret
    __endasm;
}

u8 boss_projectile_draw(entity_t *e, u8 oam, u8 x, u8 y) BANKED {
    if (!(e->flags & EF_BOSS_PROJECTILE)) {
        if (e->ai_data[6] == PROJ_AUX_MORNINGSTAR) return morningstar_draw(e,oam,x,y);
        if (e->ai_data[6] != PROJ_AUX_FUSE_BOMB) return hookshot_draw(e,oam,x,y);
        if (oam>=entity_oam_cap) return oam;
        set_sprite_tile(oam,e->sprite_tile); set_sprite_prop(oam,e->palette);
        move_sprite(oam,x,y); return oam+1;
    }
    u8 shape = e->ai_data[4];
    u8 ang = e->ai_data[0] & 31;
    u8 prop = e->palette;
    u8 aux = e->ai_data[5];
    u8 lane, count;
    u8 x0 = x, x1 = (u8)(x + 8), y0 = y, y1 = (u8)(y + 8);
    // 1 = north, 2 = south. One load instead of the lane compares on every shot.
    static const u8 vertical_lane[32] = {
        1,1,1,1,
        0,0,0,0, 0,0,0,0, 0,
        2,2,2,2,2,2,2,
        0,0,0,0, 0,0,0,0, 0,
        1,1,1
    };
    count = shape == BOSS_SHAPE_SEED || shape == BOSS_SHAPE_CRESCENT ? 4
        : shape == BOSS_SHAPE_BOLT ? 2 : 1;
    if (oam + count > entity_oam_cap) return oam;
    // The old per-cell |= reached this same prop before the first write.
    if (aux & 0x08) prop |= S_FLIPX;
    if (aux & 0x10) prop |= S_FLIPY;
    bp_t = e->sprite_tile;
    lane = (shape == BOSS_SHAPE_BOLT || shape == BOSS_SHAPE_CRESCENT)
        ? vertical_lane[ang] : 0;
    if (lane) {
        // North-leading bank-1 glyphs; a south lane flips Y and swaps rows.
        bp_t = shape == BOSS_SHAPE_BOLT ? 208 : 210;
        prop |= 0x08;
        if (lane == 2) { prop |= S_FLIPY; y0 = (u8)(y + 8); y1 = y; }
        if (shape == BOSS_SHAPE_BOLT) x1 = x;   /* one column, two rows */
    } else if ((shape == BOSS_SHAPE_BOLT && ang > 16)
        || (shape == BOSS_SHAPE_CRESCENT && ang > 0 && ang < 16)) {
        prop |= S_FLIPX;
        if (count > 1) { x0 = (u8)(x + 8); x1 = x; }
    }
    bp_yx[0] = y0; bp_yx[1] = x0;
    bp_yx[2] = (lane && shape == BOSS_SHAPE_BOLT) ? y1 : y0; bp_yx[3] = x1;
    bp_yx[4] = y1; bp_yx[5] = x0;
    bp_yx[6] = y1; bp_yx[7] = x1;
    bp_p = prop;
    bp_n = count;
    bp_emit((u8 *)&shadow_OAM[oam]);
    return (u8)(oam + count);
}
