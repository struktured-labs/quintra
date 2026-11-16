#pragma bank 18
#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/cinder_big.h"
#include "game/entity.h"
#include "game/boss_projectile.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

u8 cinder_oam_end;
u8 cinder_oam_limit;
u8 cinder_fire_tx[8];
u8 cinder_fire_ty[8];
u8 cinder_fire_size[8];
u8 cinder_fire_delay[8];
u8 cinder_fire_ttl[8];
static u8 fire_painted[8];      /* 0 none, 1 warning ring, 2 burning */
static u8 fire_save_t[8][9];    /* floor under the pool, from VRAM */
static u8 fire_save_a[8][9];
static u8 fire_cursor;

/* Warning: dark scorched square with a dotted orange ring and an ember.
   Burning: solid flame, orange tongues and yellow sparks. Each state is a
   corner, a top edge, a side edge and a centre; flips make the rest. */
static const u8 fire_art[128] = {
0x00, 0x00, 0x00, 0x00, 0x00, 0x16, 0x00, 0x20, 0x00, 0x20, 0x00, 0x00, 0x00, 0x20, 0x00, 0x20,
0x00, 0x00, 0x00, 0x00, 0x00, 0xDB, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
0x00, 0x20, 0x00, 0x20, 0x00, 0x00, 0x00, 0x20, 0x00, 0x20, 0x00, 0x00, 0x00, 0x20, 0x00, 0x20,
0x00, 0x00, 0x00, 0x00, 0x10, 0x00, 0x38, 0x10, 0x10, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
0x00, 0x00, 0x00, 0x09, 0x09, 0x1D, 0x1C, 0x3E, 0x3F, 0x73, 0x3F, 0x20, 0x3F, 0x70, 0x3F, 0x20,
0x00, 0x88, 0x88, 0xDD, 0xEE, 0xFF, 0xFF, 0xDD, 0xFF, 0x82, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00,
0x3F, 0x30, 0x3F, 0x70, 0x7F, 0xF0, 0x3F, 0x20, 0x3F, 0x30, 0x3F, 0x60, 0x7F, 0xF0, 0x3F, 0x20,
0xFF, 0x00, 0xFF, 0x10, 0xFF, 0x00, 0xFF, 0x04, 0xFF, 0x40, 0xFF, 0x00, 0xFF, 0x02, 0xFF, 0x00
};

#define FIRE_ATTR (BGPAL_CRACK | 0x08)

void cinder_big_load(void) BANKED {
    cinder_rex_big_load();
    VBK_REG = 1;
    set_bkg_data(CINDER_FIRE_TILE, CINDER_FIRE_TILES, fire_art);
    VBK_REG = 0;
}

void cinder_fire_reset(void) BANKED {
    u8 i;
    for (i = 0; i < 8; ++i)
        cinder_fire_ttl[i] = cinder_fire_delay[i] = fire_painted[i] = 0;
    fire_cursor = 0;
}

static u8 fire_cell(u8 i, u8 cx, u8 cy, u8 *attr) {
    u8 s = cinder_fire_size[i];
    u8 base = (u8)(CINDER_FIRE_TILE + (fire_painted[i] == 2 ? 4 : 0));
    u8 last = (u8)(s - 1);
    u8 a = FIRE_ATTR, t;
    if (s == 3 && cx == 1 && cy == 1) t = (u8)(base + 3);
    else if (s == 3 && cx == 1) { t = (u8)(base + 1); if (cy == last) a |= 0x40; }
    else if (s == 3 && cy == 1) { t = (u8)(base + 2); if (cx == last) a |= 0x20; }
    else {
        t = base;
        if (cx == last) a |= 0x20;
        if (cy == last) a |= 0x40;
    }
    *attr = a;
    return t;
}

static u8 fire_covers(u8 j, u8 x, u8 y) {
    return fire_painted[j]
        && x >= cinder_fire_tx[j] && x < (u8)(cinder_fire_tx[j] + cinder_fire_size[j])
        && y >= cinder_fire_ty[j] && y < (u8)(cinder_fire_ty[j] + cinder_fire_size[j]);
}

static u8 fire_owner(u8 except, u8 x, u8 y) {
    u8 j;
    for (j = 0; j < 8; ++j)
        if (j != except && fire_covers(j, x, y)) return j;
    return 0xFF;
}

/* Direct map writes. GBDK's set_bkg_tiles recomputes the address and pays
   call overhead per cell; a 24px pool is 18 bytes, and the slam lights five
   at once, so poke the live map with the usual non-busy STAT wait instead. */
static void vram_poke(u8 bank, u8 x, u8 y, u8 v) {
    volatile u8 *p = (volatile u8 *)(0x9800u
        + ((u16)ROOM_BG_MAP_Y(y) << 5) + ROOM_BG_MAP_X(x));
    __critical {
        VBK_REG = bank;
        while (STAT_REG & 2) ;
        *p = v;
        VBK_REG = 0;
    }
}

static void put_cell(u8 x, u8 y, u8 t, u8 a) {
    vram_poke(0, x, y, t);
    vram_poke(1, x, y, a);
}

static void fire_stamp(u8 i) {
    u8 cx, cy, s = cinder_fire_size[i];
    for (cy = 0; cy < s; ++cy) {
        u8 y = (u8)(cinder_fire_ty[i] + cy);
        for (cx = 0; cx < s; ++cx) {
            u8 a, t = fire_cell(i, cx, cy, &a);
            put_cell((u8)(cinder_fire_tx[i] + cx), y, t, a);
        }
    }
}

/* Restore one pool's footprint. Cells still under another live pool show
   that pool instead, so overlapping brands never punch holes. */
static void fire_unstamp(u8 i) {
    u8 cx, cy, k = 0, s = cinder_fire_size[i];
    if (!fire_painted[i]) return;
    fire_painted[i] = 0;
    for (cy = 0; cy < s; ++cy) {
        for (cx = 0; cx < s; ++cx, ++k) {
            u8 x = (u8)(cinder_fire_tx[i] + cx), y = (u8)(cinder_fire_ty[i] + cy);
            u8 j = fire_owner(i, x, y);
            if (j != 0xFF) {
                u8 a, t = fire_cell(j, (u8)(x - cinder_fire_tx[j]),
                    (u8)(y - cinder_fire_ty[j]), &a);
                put_cell(x, y, t, a);
            } else put_cell(x, y, fire_save_t[i][k], fire_save_a[i][k]);
        }
    }
}

/* Read one live map byte. GBDK's get_bkg_tiles would pull ~100 bytes into
   the nearly full home bank, so wait for a non-busy STAT mode here. */
static u8 vram_peek(u8 bank, u8 x, u8 y) {
    volatile u8 *p = (volatile u8 *)(0x9800u
        + ((u16)ROOM_BG_MAP_Y(y) << 5) + ROOM_BG_MAP_X(x));
    u8 v;
    __critical {
        VBK_REG = bank;
        while (STAT_REG & 2) ;
        v = *p;
        VBK_REG = 0;
    }
    return v;
}

static void fire_save(u8 i) {
    u8 cx, cy, k = 0, s = cinder_fire_size[i];
    for (cy = 0; cy < s; ++cy) {
        for (cx = 0; cx < s; ++cx, ++k) {
            u8 x = (u8)(cinder_fire_tx[i] + cx), y = (u8)(cinder_fire_ty[i] + cy);
            u8 j = fire_owner(i, x, y);
            if (j != 0xFF) {
                /* Already under another pool: inherit its saved floor. */
                u8 jk = (u8)((y - cinder_fire_ty[j]) * cinder_fire_size[j]
                    + (x - cinder_fire_tx[j]));
                fire_save_t[i][k] = fire_save_t[j][jk];
                fire_save_a[i][k] = fire_save_a[j][jk];
            } else {
                fire_save_t[i][k] = vram_peek(0, x, y);
                fire_save_a[i][k] = vram_peek(1, x, y);
            }
        }
    }
}

void cinder_fire_clear_all(void) BANKED {
    u8 i;
    for (i = 0; i < 8; ++i) {
        fire_unstamp(i);
        cinder_fire_ttl[i] = cinder_fire_delay[i] = 0;
    }
}

void cinder_fire_add(u8 x, u8 y, u8 delay, u8 ttl, u8 size) BANKED {
    u8 i = fire_cursor;
    i16 tx, ty;
    u8 max_x = (u8)((room_world_width >> 3) - 1 - size);
    u8 max_y = (u8)((room_world_height >> 3) - 1 - size);
    fire_cursor = (u8)((fire_cursor + 1) & 7);
    fire_unstamp(i);
    /* Snap the centre to the tile grid and keep the pool on the floor,
       never on the boundary wall. */
    tx = ((i16)x - (i16)size * 4 + 4) >> 3;
    ty = ((i16)y - (i16)size * 4 + 4) >> 3;
    if (tx < 1) tx = 1;
    if (ty < 1) ty = 1;
    if (tx > max_x) tx = max_x;
    if (ty > max_y) ty = max_y;
    cinder_fire_tx[i] = (u8)tx;
    cinder_fire_ty[i] = (u8)ty;
    cinder_fire_size[i] = size;
    cinder_fire_delay[i] = delay;
    cinder_fire_ttl[i] = ttl;
    fire_save(i);
    fire_painted[i] = delay ? 1 : 2;
    fire_stamp(i);
}

u8 cinder_fire_tick(void) BANKED {
    u8 i, hit = 0;
    u8 px = (u8)(player.x + 8);
    u8 py = (u8)(player.y + 12);
    for (i = 0; i < 8; ++i) {
        u8 x0, y0, span;
        if (!cinder_fire_ttl[i]) continue;
        if (!--cinder_fire_ttl[i]) { fire_unstamp(i); continue; }
        if (cinder_fire_delay[i]) {
            u8 d = --cinder_fire_delay[i];
            if (!d) {
                fire_painted[i] = 2;
                fire_stamp(i);
                sfx_play(SFX_TICK);
            } else if (d == CINDER_POOL_FLASH || d == CINDER_POOL_FLASH / 2) {
                /* Last-6-frame flash: flame for 3, ring for 3, then it burns. */
                fire_painted[i] = d == CINDER_POOL_FLASH ? 2 : 1;
                fire_stamp(i);
            }
            continue;
        }
        /* The drawn square is the hazard, less a 2px forgiving rim. */
        x0 = (u8)((cinder_fire_tx[i] << 3) + 2);
        y0 = (u8)((cinder_fire_ty[i] << 3) + 2);
        span = (u8)((cinder_fire_size[i] << 3) - 4);
        if (px >= x0 && px < (u8)(x0 + span) && py >= y0 && py < (u8)(y0 + span))
            hit = 1;
    }
    return hit;
}

void cinder_fire_repaint(void) BANKED {
    u8 i;
    for (i = 0; i < 8; ++i)
        if (fire_painted[i]) fire_stamp(i);
}

/* Rex owns the LAST 24 OAM entries (16..39). On the GBC the first ten
   entries on a scanline win, so a bullet crossing the hound is never the
   sprite that drops: at worst an edge of the boss blinks, never a shot.
   Shots also draw over the body, never hidden under it. */
void cinder_rex_big_draw(i16 sx, i16 sy, u8 facing, u8 pose, u8 prop) BANKED {
    u8 colx[6];
    u8 *o = (u8 *)&shadow_OAM[CINDER_REX_OAM_BASE];
    u8 r, c;
    prop |= 0x08;                       /* both frames live in VRAM bank 1 */
    if (!facing) prop |= S_FLIPX;
    for (c = 0; c < 6; ++c) {
        i16 x = sx + (c << 3);
        colx[c] = (x <= 0 || x >= 168) ? 0 : (u8)x;
    }
    for (r = 0; r < 4; ++r) {
        i16 y16 = sy + (r << 3);
        u8 y = (y16 <= 0 || y16 >= 160) ? 0 : (u8)y16;
        u8 band = r < 2 ? (pose & 1) : (pose & 2);
        u8 base = (u8)((band ? 88 : 64) + r * 6);
        for (c = 0; c < 6; ++c) {
            u8 x = colx[c];
            /* A clipped column parks Y too: an X=0 sprite still costs the
               scanline. */
            *o++ = x ? y : 0;
            *o++ = x;
            *o++ = facing ? (u8)(base + c) : (u8)(base + 5 - c);
            *o++ = prop;
        }
    }
}

void cinder_rex_big_park(void) BANKED {
    u8 *o = (u8 *)&shadow_OAM[CINDER_REX_OAM_BASE];
    u8 n;
    for (n = 0; n < CINDER_REX_OAM; ++n) { *o = 0; o[1] = 0; o += 4; }
}

/* Fairness (Argon review): a bigger square needs more lead time, so every
   pool warns for at least CINDER_POOL_WARN_P1 / _P2 frames and keeps its
   authored burn time. While the 48x32 body is within 48px of a wall, pools
   keep 16px off that wall, so the body plus a pool cluster can never seal
   the champion into a corner. */
void cinder_fire_add_fair(u8 x, u8 y, u8 delay, u8 ttl, u8 size,
    u8 bx, u8 by) BANKED {
    u8 floor = size == 3 ? CINDER_POOL_WARN_P2 : CINDER_POOL_WARN_P1;
    if (delay < floor) {
        ttl = (u8)(ttl + (floor - delay));
        delay = floor;
    }
    if (bx != 0xFF) {
        u8 half = (u8)(size << 2);
        u8 lo = (u8)(8 + CINDER_POOL_WALL_GAP + half);
        u8 hi_x = (u8)(room_world_width - 8 - CINDER_POOL_WALL_GAP - half);
        u8 hi_y = (u8)(room_world_height - 8 - CINDER_POOL_WALL_GAP - half);
        if (bx < (u8)(8 + CINDER_POOL_REX_NEAR) && x < lo) x = lo;
        if ((u16)bx + CINDER_REX_W + CINDER_POOL_REX_NEAR
                > (u16)(room_world_width - 8) && x > hi_x) x = hi_x;
        if (by < (u8)(8 + CINDER_POOL_REX_NEAR) && y < lo) y = lo;
        if ((u16)by + CINDER_REX_H + CINDER_POOL_REX_NEAR
                > (u16)(room_world_height - 8) && y > hi_y) y = hi_y;
    }
    cinder_fire_add(x, y, delay, ttl, size);
}

/* A Furnace Breath lane that reaches the body hops to its far edge: the
   wall keeps going behind the hound (no safe pocket on either side) and
   never puts a lane sprite on the scanlines the body already fills. */
void cinder_lanes_skip_body(i16 bx, i16 by) BANKED {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *s = &entities[i];
        u8 w, h;
        if ((s->flags & (EF_ACTIVE | EF_BOSS_PROJECTILE))
                != (EF_ACTIVE | EF_BOSS_PROJECTILE)
            || s->ai_data[1] != BOSS_SHOT_LANE) continue;
        w = s->hitbox >> 4; h = s->hitbox & 15;
        if (s->x + w <= bx || s->x >= bx + CINDER_REX_W) continue;
        /* Look 4px ahead: the lane moves after this check this frame. */
        if (s->ai_data[0] == 16) {
            if (s->y + h + 4 > by && s->y < by + CINDER_REX_H)
                s->y = by + CINDER_REX_H;
        } else if (s->ai_data[0] == 0) {
            if (s->y < by + CINDER_REX_H + 4 && s->y + h > by)
                s->y = by - h;
        }
    }
}
