#pragma bank 255
/* Appended OAM for the bank-25 specialists: the 32x32 basilisk bodies, the
   32x32 bomb burst, and fuse/wind-up blast-edge markers. Split from
   enemy_new_ai.c (bank 25 is full); the AI state it reads is shared through
   game/enemy_new_draw.h. */
#include <gb/gb.h>
#include "core/types.h"
#include "game/enemy_new_ai.h"
#include "game/enemy_new_draw.h"
#include "game/entity.h"
#include "game/room.h"
#include "game/status.h"
#include "render/basilisk_art.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(nm_extras_draw)

#define PHASE e->ai_data[2]
#define TIMER e->ai_data[1]

extern u8 entity_oam_high;
extern u8 entity_anim_counter;

u8 nm_xo_hi;
static u8 xo;

static u8 is_basilisk(u8 id) {
    return id == ENEMY_LEYBEAM || id == ENEMY_SUN_BASILISK
        || id == ENEMY_NOX_BASILISK;
}

static u8 basilisk_lanes(u8 id) {
    return id == ENEMY_NOX_BASILISK ? 4 : id == ENEMY_SUN_BASILISK ? 3 : 2;
}

/* ---- appended OAM: basilisk bodies, blasts, fuse tells ----
   The shared allocator has already written entities into 4..entity_oam_high.
   These extras go after it (below the fixed 35..39 specialist slots); a
   blast is written before a body so the hazard wins any shortfall. When a
   crowded scene leaves no room they borrow the top of the entity range on
   alternate frames, which is the same fair flicker the allocator uses. */
#define XO_CAP 35

/* The extras never raise entity_oam_high: the allocator would park their
   slots at the top of its next pass, and a frame that overruns VBlank
   between that park and the rewrite below would DMA a missing burst. They
   park their own leftovers instead. */
static void xo_park(u8 from) {
    if (from < entity_oam_high) from = entity_oam_high;
    while (from < nm_xo_hi) {
        shadow_OAM[from].y = 0;
        from++;
    }
    nm_xo_hi = 0;
}

static void xo_begin(u8 need) {
    xo = entity_oam_high;
    if (xo < 4) xo = 4;
    if ((u8)(xo + need) > XO_CAP)
        xo = (entity_anim_counter & 1) ? (u8)(XO_CAP - need) : XO_CAP;
}

/* World-space 8x8 put with per-sprite clipping (slow path). */
static void xo_put(i16 wx, i16 wy, u8 tile, u8 prop) {
    i16 ox = (i16)(wx - (i16)room_camera_x + 8);
    i16 oy = (i16)(wy - (i16)room_camera_y + 16);
    OAM_item_t *it;
    if (xo >= XO_CAP) return;
    if (ox <= 0 || ox >= 168 || oy <= 0 || oy >= 160) return;
    it = &shadow_OAM[xo++];
    it->y = (u8)oy;
    it->x = (u8)ox;
    it->tile = tile;
    it->prop = prop;
}

/* 4x4 block of OAM. Fully visible blocks take the u8 fast path; edge
   blocks clip per sprite. tiles[] is row-major, already mirrored. */
static void xo_block(i16 wx, i16 wy, const u8 *tiles, const u8 *props) {
    i16 ox = (i16)(wx - (i16)room_camera_x + 8);
    i16 oy = (i16)(wy - (i16)room_camera_y + 16);
    u8 r, c, k = 0;
    if (ox >= 1 && ox <= 136 && oy >= 1 && oy <= 128 && xo + 16 <= XO_CAP) {
        OAM_item_t *it = &shadow_OAM[xo];
        u8 y = (u8)oy;
        for (r = 0; r < 4; ++r, y += 8) {
            u8 x = (u8)ox;
            for (c = 0; c < 4; ++c, ++k, x += 8, ++it) {
                it->y = y;
                it->x = x;
                it->tile = tiles[k];
                it->prop = props[k];
            }
        }
        xo += 16;
        return;
    }
    for (r = 0; r < 4; ++r)
        for (c = 0; c < 4; ++c, ++k)
            xo_put(wx + (i16)(c << 3), wy + (i16)(r << 3), tiles[k], props[k]);
}

static u8 xb_tile[16], xb_prop[16];

static void basilisk_draw(u8 slot, entity_t *e) {
    static const u8 tier_pal[3] = { 7, 4, 6 };   /* green, red, Void stage */
    u8 base = BAS_TILE_IDLE, prop, k, left;
    u8 pal = tier_pal[(u8)(basilisk_lanes(e->ai_data[0]) - 2)];
    if (!(e->flags & EF_ON_SCREEN)) return;
    if (e->ai_data[7] & 1) return;             /* hit flash (allocator ticks it) */
    if (PHASE == 2 || (PHASE == 1 && TIMER >= 16)) base = BAS_TILE_FIRE;
    else if (PHASE == 0 && ((entity_anim_counter >> 4) & 1)) base = BAS_TILE_WALK;
    if (PHASE == 1 && (TIMER & 4)) pal = 5;    /* charge strobe: gold */
    if (enemy_status_kind[slot] != QSTATUS_NONE && (entity_anim_counter & 8))
        pal = status_enemy_palette_prop(slot) & 7;
    left = e->ai_data[4] & 1;
    prop = (u8)(pal | 0x08 | (left ? S_FLIPX : 0));
    for (k = 0; k < 16; ++k) {
        xb_tile[k] = (u8)(base + (left ? ((k & 0x0C) | (3 - (k & 3))) : k));
        xb_prop[k] = prop;
    }
    xo_block(FIX8_TO_INT(e->x) - 8, FIX8_TO_INT(e->y) - 16, xb_tile, xb_prop);
}

/* 32x32 burst from one 16x16 GPT quadrant, mirrored four ways. */
static const u8 blast_q[16] = { 0, 1, 1, 0,  2, 3, 3, 2,  2, 3, 3, 2,  0, 1, 1, 0 };
static const u8 blast_f[16] = {
    0, 0, S_FLIPX, S_FLIPX,  0, 0, S_FLIPX, S_FLIPX,
    S_FLIPY, S_FLIPY, S_FLIPX | S_FLIPY, S_FLIPX | S_FLIPY,
    S_FLIPY, S_FLIPY, S_FLIPX | S_FLIPY, S_FLIPX | S_FLIPY };

static void blast_draw(u8 i) {
    u8 t = fb_timer[i], k;
    u8 f = t < 3 ? 0 : t < 8 ? 1 : t < 14 ? 2 : 3;
    for (k = 0; k < 16; ++k) {
        xb_tile[k] = BLAST_TILE(f, blast_q[k]);
        xb_prop[k] = (u8)(BLAST_PAL | 0x08 | blast_f[k]);
    }
    xo_block(fb_x[i] - 16, fb_y[i] - 16, xb_tile, xb_prop);
}

/* Fuse tell: the eight edge points of the exact damage square, corners and
   edge midpoints alternating every 4 frames, bomb flashing faster late. */
static void fuse_tell_at(i16 x, i16 y, u8 left) {
    u8 p = (left < 16 && (left & 2)) ? 5 : 4;
    x -= 4;
    y -= 4;
    if (left & 4) {
        xo_put(x - FUSE_RADIUS, y - FUSE_RADIUS, SPR_FX_IMPACT, p);
        xo_put(x + FUSE_RADIUS, y - FUSE_RADIUS, SPR_FX_IMPACT, p);
        xo_put(x - FUSE_RADIUS, y + FUSE_RADIUS, SPR_FX_IMPACT, p);
        xo_put(x + FUSE_RADIUS, y + FUSE_RADIUS, SPR_FX_IMPACT, p);
    } else {
        xo_put(x - FUSE_RADIUS, y, SPR_FX_IMPACT, p);
        xo_put(x + FUSE_RADIUS, y, SPR_FX_IMPACT, p);
        xo_put(x, y - FUSE_RADIUS, SPR_FX_IMPACT, p);
        xo_put(x, y + FUSE_RADIUS, SPR_FX_IMPACT, p);
    }
}

void nm_extras_draw(void) BANKED {
    u8 i, need = 0, nb = 0, pick;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && is_basilisk(entities[i].ai_data[0]) && entities[i].hp) need += 16;
    for (i = 0; i < FUSE_BOMB_MAX; ++i)
        if (fb_live[i]) {
            if (fb_phase[i] == 2) { need += 16; nb++; }
            else if (fb_phase[i] == 1) need += 4;
        }
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == ENEMY_FUSE_HURLER
            && entities[i].ai_data[2] == 3) need += 4;
    if (!need) { xo_park(4); return; }
    xo_begin(need > 31 ? 31 : need);
    /* Two overlapping blasts share the burst by alternating frames. */
    pick = (nb > 1) ? (u8)(entity_anim_counter & 1) : 0xFF;
    for (i = 0; i < FUSE_BOMB_MAX; ++i) {
        if (!fb_live[i]) continue;
        if (fb_phase[i] == 2) {
            if (pick == 0xFF || pick == i) blast_draw(i);
        } else if (fb_phase[i] == 1) fuse_tell_at(fb_x[i], fb_y[i], fb_timer[i]);
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        if (is_basilisk(e->ai_data[0]) && e->hp) basilisk_draw(i, e);
        else if (e->ai_data[0] == ENEMY_FUSE_HURLER && PHASE == 3)
            /* Close-range wind-up shows the same blast edge as a bomb. */
            fuse_tell_at(FIX8_TO_INT(e->x) + 4, FIX8_TO_INT(e->y) + 4,
                (u8)(28 - TIMER));
    }
    {
        u8 end = xo;
        xo_park(end);
        if (end > entity_oam_high) nm_xo_hi = end;
    }
}


void nm_extras_park(void) BANKED {
    xo_park(4);
}
