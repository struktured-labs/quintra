#pragma bank 25

#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/enemy_new_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 pending_foyer_warp;
u8 vault_hand_holding;
u8 leybeam_beam_live;
u8 leybeam_flush_pending;
u8 new_monsters_busy;
u8 new_monsters_in_room;

static u8 beam_dir;
static u8 beam_len;
static i16 beam_ox, beam_oy;

#define LEY_STAMP_MAX 48
#define LEY_VBL_BURST 16
static u8 ley_n, ley_i, ley_flush, ley_art_ok;
static u8 ley_tx[LEY_STAMP_MAX], ley_ty[LEY_STAMP_MAX];

/* Uploaded to VRAM bank 1, index LEYBEAM_BG_TILE. Crossing-bar glow so
   the same 8x8 reads as a shaft in both orientations. */
static const u8 ley_beam_art[16] = {
    0x38, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0x1C, 0xFF
};

#define FUSE_BOMB_MAX 2
#define FUSE_FLIGHT 16
#define FUSE_TICKS  40
#define FUSE_RADIUS 16
static u8  fb_live[FUSE_BOMB_MAX];
static u8  fb_phase[FUSE_BOMB_MAX]; /* 0 flight, 1 fuse */
static u8  fb_timer[FUSE_BOMB_MAX];
static i16 fb_x[FUSE_BOMB_MAX], fb_y[FUSE_BOMB_MAX];
static i8  fb_vx[FUSE_BOMB_MAX], fb_vy[FUSE_BOMB_MAX];

#define PHASE e->ai_data[2]
#define TIMER e->ai_data[1]

static i8 sign8(i16 v) {
    return (v > 0) ? 1 : (v < 0) ? (i8)-1 : 0;
}

static u8 walkable_px(i16 x, i16 y) {
    if (x < 8 || y < 8) return 0;
    if (x >= (i16)(room_world_width - 8)) return 0;
    if (y >= (i16)(room_world_height - 8)) return 0;
    return room_tile_walkable(room_tile_at_px(x + 4, y + 4));
}

static void aim_shot(entity_t *e, const enemy_def_t *def, u8 speed) {
    i16 ex = FIX8_TO_INT(e->x);
    i16 ey = FIX8_TO_INT(e->y);
    i8 sx = sign8((i16)player.x - ex);
    i8 sy = sign8((i16)player.y - ey);
    if (!sx && !sy) sy = -1;
    projectile_spawn_enemy_v(ex, ey, (i8)(sx * speed), (i8)(sy * speed),
        def->stats.damage);
}

static void puff_at(i16 x, i16 y) {
    fx_spawn(SPR_FX_IMPACT, 2, x, y, 8);
}

/* ---- Veil Magus: vanish, reappear, tell, bolt ---- */
/* ai_data: [1] timer [2] phase 0 tell, 1 hold, 2 gone [7] shimmer */

static void veil_magus_tick(entity_t *e, const enemy_def_t *def) {
    u8 vanish = def->ai_p0 ? def->ai_p0 : 20;
    u8 tell = def->ai_p1 ? def->ai_p1 : 24;
    if (RUN_IS_EASY() && tell < 250) tell = (u8)(tell + (tell >> 2));

    if (PHASE == 2) {
        if (++TIMER < 30 && TIMER < vanish) return;
        {
            u8 tries = 8;
            TIMER = 0;
            while (tries--) {
                i16 nx = (i16)(8 + rng_range((u8)(room_world_width - 16)));
                i16 ny = (i16)(8 + rng_range((u8)(room_world_height - 16)));
                i16 adx = nx - (i16)player.x; if (adx < 0) adx = -adx;
                i16 ady = ny - (i16)player.y; if (ady < 0) ady = -ady;
                if (adx + ady < 24) continue;
                if (adx + ady < 16) continue;
                if (!walkable_px(nx, ny)) continue;
                e->x = FIX8(nx);
                e->y = FIX8(ny);
                e->flags |= EF_ON_SCREEN;
                e->ai_data[7] = 6;
                PHASE = 0;
                TIMER = 0;
                puff_at(nx, ny);
                sfx_play(SFX_TICK);
                return;
            }
            /* stay gone, retry later */
        }
        return;
    }
    if (PHASE == 0) {
        if ((++TIMER & 3) == 0) e->ai_data[7] = 4;
        if (TIMER >= tell) {
            aim_shot(e, def, 2);
            sfx_play(SFX_WEAK);
            PHASE = 1;
            TIMER = 0;
        }
        return;
    }
    /* hold, then vanish */
    if (++TIMER >= 16) {
        puff_at(FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
        e->flags &= (u8)~EF_ON_SCREEN;
        e->x = FIX8(80);
        e->y = FIX8(200);
        PHASE = 2;
        TIMER = 0;
    }
}

/* ---- Hex Walker: walk, tell, one bolt ---- */
/* [1] timer [2] phase 0 walk 1 tell 2 recover [3] heading 0..3 */

static const i8 card_dx[4] = { 0, 1, 0, -1 };
static const i8 card_dy[4] = { -1, 0, 1, 0 };

static void hex_walker_tick(entity_t *e, const enemy_def_t *def) {
    u8 walk = def->ai_p0 ? def->ai_p0 : 48;
    u8 tell = def->ai_p1 ? def->ai_p1 : 16;
    if (PHASE == 0) {
        if ((++e->state_timer & 3) == 0) {
            u8 h = e->ai_data[3] & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->ai_data[3] = (u8)((h + 1 + (rng_next_u8() & 1)) & 3);
        }
        if (++TIMER >= walk) {
            PHASE = 1;
            TIMER = 0;
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (++TIMER >= tell) {
            aim_shot(e, def, 2);
            PHASE = 2;
            TIMER = 0;
        }
        return;
    }
    if (++TIMER >= 12) {
        PHASE = 0;
        TIMER = 0;
        /* new cardinal: heading +/- 90 */
        e->ai_data[3] = (u8)((e->ai_data[3] + ((rng_next_u8() & 1) ? 1 : 3)) & 3);
    }
}

/* ---- Bane Brute: slow walk toward the hero ---- */

static void bane_brute_tick(entity_t *e) {
    if ((++e->state_timer & 31) != 0) return;
    {
        i8 dx = sign8((i16)player.x - FIX8_TO_INT(e->x));
        i8 dy = sign8((i16)player.y - FIX8_TO_INT(e->y));
        if (dx && !enemy_try_step(e, dx, 0) && dy) enemy_try_step(e, 0, dy);
        else if (dy) enemy_try_step(e, 0, dy);
        else if (dx) enemy_try_step(e, dx, 0);
    }
}

/* ---- Zag Dart ---- */
/* [1] timer [2] phase 0 idle 1 tell 2 burst
   [3] lock sx [4] lock sy [5] leg [6] bolt-used */

static void zag_dart_tick(entity_t *e, const enemy_def_t *def) {
    u8 tell = def->ai_p0 ? def->ai_p0 : 18;
    u8 burst = def->ai_p1 ? def->ai_p1 : 28;
    u8 cool = def->ai_p2 ? def->ai_p2 : 90;
    if (PHASE == 0) {
        if ((++e->state_timer & 3) == 0) {
            u8 h = e->state & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->state = (u8)(rng_next_u8() & 3);
        }
        if (++TIMER >= cool) {
            PHASE = 1;
            TIMER = 0;
            e->ai_data[3] = (u8)sign8((i16)player.x - FIX8_TO_INT(e->x));
            e->ai_data[4] = (u8)sign8((i16)player.y - FIX8_TO_INT(e->y));
            if (!e->ai_data[3] && !e->ai_data[4]) e->ai_data[3] = 1;
            e->ai_data[5] = 0;
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        } else if (TIMER == 20 && !e->ai_data[6]) {
            /* one 1-in-4 roll per cooldown, never the encounter's centre */
            e->ai_data[6] = 1;
            if ((rng_next_u8() & 3) == 0) aim_shot(e, def, 1);
        }
        return;
    }
    if (PHASE == 1) {
        if (++TIMER >= tell) {
            PHASE = 2;
            TIMER = 0;
            e->damage = 2;
        }
        return;
    }
    /* burst: 7-frame legs, axis then perpendicular */
    {
        i8 ax = (i8)e->ai_data[3];
        i8 ay = (i8)e->ai_data[4];
        u8 leg = e->ai_data[5];
        i8 dx, dy;
        if ((leg & 1) == 0) { dx = ax; dy = ay; }
        else { dx = (i8)-ay; dy = ax; }
        if (!dx && !dy) dx = 1;
        enemy_try_step(e, dx, 0);
        enemy_try_step(e, 0, dy);
        if ((++TIMER % 7) == 0) e->ai_data[5] = (u8)(leg + 1);
        if (TIMER >= burst) {
            PHASE = 0;
            TIMER = 0;
            e->ai_data[6] = 0;
            e->damage = 1;
        }
    }
}

/* ---- Leybeam: cardinal tell + 16-px BG beam ---- */
/* [1] timer [2] phase 0 cool 1 tell 2 beam [3] dir 0..3 */

static u8 nearest_cardinal(i16 ex, i16 ey) {
    i16 dx = (i16)player.x - ex;
    i16 dy = (i16)player.y - ey;
    i16 ax = dx < 0 ? (i16)-dx : dx;
    i16 ay = dy < 0 ? (i16)-dy : dy;
    if (ax >= ay) return (dx >= 0) ? 1 : 3;
    return (dy >= 0) ? 2 : 0;
}

static u8 ley_floorish(u8 tile) {
    return (u8)(tile == BGT_FLOOR || tile == BGT_FLOOR2
        || tile == BGT_FLOOR3 || tile == BGT_RUBBLE);
}

static void ley_put(u8 tx, u8 ty, u8 tile, u8 attr) {
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &attr);
    VBK_REG = 0;
}

void leybeam_vblank_flush(void) BANKED {
    u8 burst = 0;
    if (!ley_flush) return;
    if (ley_flush == 1 && !ley_art_ok) {
        VBK_REG = 1;
        set_bkg_data(LEYBEAM_BG_TILE, 1, ley_beam_art);
        VBK_REG = 0;
        ley_art_ok = 1;
        burst++;
    }
    while (ley_i < ley_n && burst < LEY_VBL_BURST) {
        u8 tx = ley_tx[ley_i];
        u8 ty = ley_ty[ley_i];
        if (ley_flush == 1) {
            /* Bank-1 glow tile, stage crystal palette. */
            ley_put(tx, ty, LEYBEAM_BG_TILE, (u8)(0x08 | BGPAL_CRYSTAL));
        } else {
            u8 t = room_tile_at_px((i16)tx << 3, (i16)ty << 3);
            ley_put(tx, ty, t, BGPAL_FLOOR);
        }
        ley_i++;
        burst++;
    }
    if (ley_i >= ley_n) {
        if (ley_flush == 2) room_draw_tilemap(); /* exact attrs from the RAM map */
        ley_flush = 0;
    }
    leybeam_flush_pending = ley_flush;
}

static void leybeam_restore(void) {
    if (!leybeam_beam_live && !ley_n) return;
    leybeam_beam_live = 0;
    if (ley_n) {
        ley_i = 0;
        ley_flush = 2;
        leybeam_flush_pending = 1;
    } else {
        room_draw_tilemap();
    }
}

void leybeam_clear_beam(void) BANKED {
    leybeam_restore();
}

static void leybeam_collect(void) {
    i8 dx = card_dx[beam_dir];
    i8 dy = card_dy[beam_dir];
    i8 ax = (beam_dir == 0 || beam_dir == 2) ? 1 : 0;
    i8 ay = (beam_dir == 1 || beam_dir == 3) ? 1 : 0;
    u8 n;
    ley_n = 0;
    for (n = 0; n <= beam_len; ++n) {
        i16 px = beam_ox + (i16)dx * (i16)n * 8;
        i16 py = beam_oy + (i16)dy * (i16)n * 8;
        i8 across;
        for (across = -8; across <= 0; across += 8) {
            i16 x = px + (i16)ax * across;
            i16 y = py + (i16)ay * across;
            u8 tx, ty, tile;
            if (x < 0 || y < 0) continue;
            tx = (u8)(x >> 3);
            ty = (u8)(y >> 3);
            if ((u16)tx >= (u16)(room_world_width >> 3)
                || (u16)ty >= (u16)(room_world_height >> 3)) continue;
            tile = room_tile_at_px(x, y);
            if (!ley_floorish(tile)) continue;
            if (ley_n < LEY_STAMP_MAX) {
                ley_tx[ley_n] = tx;
                ley_ty[ley_n] = ty;
                ley_n++;
            }
        }
    }
}

static void leybeam_stamp(void) {
    leybeam_collect();
    ley_i = 0;
    ley_flush = 1;
    leybeam_flush_pending = 1;
    leybeam_beam_live = 1;
    puff_at(beam_ox, beam_oy);
}

u8 leybeam_hits_player(void) {
    i16 px, py, along, across;
    if (!leybeam_beam_live) return 0;
    px = (i16)player.x + 4;
    py = (i16)player.y + 4;
    if (beam_dir == 0 || beam_dir == 2) {
        across = px - beam_ox;
        along = (beam_dir == 2) ? (py - beam_oy) : (beam_oy - py);
    } else {
        across = py - beam_oy;
        along = (beam_dir == 1) ? (px - beam_ox) : (beam_ox - px);
    }
    if (across < 0) across = (i16)-across;
    if (along < 0) return 0;
    if (along > (i16)beam_len * 8) return 0;
    return (across <= 8) ? 1 : 0;
}

static void leybeam_lock_length(i16 ox, i16 oy, u8 dir) {
    i8 dx = card_dx[dir];
    i8 dy = card_dy[dir];
    u8 n;
    beam_len = 0;
    for (n = 1; n < 24; ++n) {
        i16 x = ox + (i16)dx * (i16)n * 8;
        i16 y = oy + (i16)dy * (i16)n * 8;
        if (x < 8 || y < 8 || x >= (i16)room_world_width
            || y >= (i16)room_world_height) break;
        if (!room_tile_walkable(room_tile_at_px(x, y))) break;
        beam_len = n;
    }
}

static void leybeam_tick(entity_t *e, const enemy_def_t *def) {
    u8 tell = def->ai_p0 ? def->ai_p0 : 40;
    u8 beam = def->ai_p1 ? def->ai_p1 : 36;
    u8 cool = def->ai_p2 ? def->ai_p2 : 100;
    if (RUN_IS_EASY() && tell < 200) tell = (u8)(tell + (tell >> 2));

    if (!(e->flags & EF_ACTIVE) || !e->hp) {
        leybeam_restore();
        return;
    }
    if (PHASE == 0) {
        if ((++e->state_timer & 7) == 0) {
            u8 h = e->state & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->state = (u8)(rng_next_u8() & 3);
        }
        if (++TIMER >= cool) {
            PHASE = 1;
            TIMER = 0;
            e->ai_data[3] = nearest_cardinal(FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (TIMER == 0 || TIMER + 8 == tell) sfx_play(SFX_TICK);
        /* Start the VBlank shaft in the last charge frames so the full
           16-px band is on the map when the beam goes live. */
        if (!leybeam_beam_live && (u8)(TIMER + 3) >= tell) {
            beam_dir = e->ai_data[3] & 3;
            beam_ox = FIX8_TO_INT(e->x) + 4;
            beam_oy = FIX8_TO_INT(e->y) + 4;
            leybeam_lock_length(beam_ox, beam_oy, beam_dir);
            leybeam_stamp();
        }
        if (++TIMER >= tell) {
            if (!leybeam_beam_live) {
                beam_dir = e->ai_data[3] & 3;
                beam_ox = FIX8_TO_INT(e->x) + 4;
                beam_oy = FIX8_TO_INT(e->y) + 4;
                leybeam_lock_length(beam_ox, beam_oy, beam_dir);
                leybeam_stamp();
            }
            PHASE = 2;
            TIMER = 0;
        }
        return;
    }
    /* fire: damage at most once per 20-frame window via ordinary iframes */
    if (leybeam_hits_player() && player.iframes == 0 && player.hp) {
        if (player.hp > 1) player.hp--;
        else player.hp = 1; /* leave death to combat; beam never instant-kills */
        player.iframes = 20;
        hud_redraw_hp();
        sfx_play(SFX_HURT);
        room_shake(1, 4);
    }
    if (++TIMER >= beam) {
        leybeam_restore();
        PHASE = 0;
        TIMER = 0;
    }
}


/* ---- Fuse Hurler: lobbed fused bomb + close-range wind-up ---- */

static void fuse_bombs_clear(void) {
    u8 i;
    for (i = 0; i < FUSE_BOMB_MAX; ++i) fb_live[i] = 0;
}

static void fuse_hurt_at(i16 x, i16 y, u8 radius) {
    i16 px = (i16)player.x + 4;
    i16 py = (i16)player.y + 4;
    i16 dx = px - x;
    i16 dy = py - y;
    if (dx < 0) dx = (i16)-dx;
    if (dy < 0) dy = (i16)-dy;
    if (dx > radius || dy > radius) return;
    if (player.iframes || !player.hp || death_timer) return;
    if (player.hp > 1) player.hp--;
    else player.hp = 1;
    player.iframes = 24;
    hud_redraw_hp();
    sfx_play(SFX_HURT);
    room_shake(1, 6);
}

static void fuse_explode(u8 i) {
    i16 x = fb_x[i], y = fb_y[i];
    fb_live[i] = 0;
    puff_at(x, y);
    puff_at(x - FUSE_RADIUS, y);
    puff_at(x + FUSE_RADIUS, y);
    puff_at(x, y - FUSE_RADIUS);
    puff_at(x, y + FUSE_RADIUS);
    room_shake(2, 8);
    sfx_play(SFX_ROAR);
    fuse_hurt_at(x, y, FUSE_RADIUS);
}

static u8 fuse_bomb_lob(i16 sx, i16 sy, i16 tx, i16 ty) {
    u8 i;
    i16 dx, dy, land_x, land_y;
    for (i = 0; i < FUSE_BOMB_MAX; ++i) if (!fb_live[i]) break;
    if (i >= FUSE_BOMB_MAX) return 0;
    dx = tx - sx;
    dy = ty - sy;
    /* Land about three-quarters of the way to the hero, on walkable floor. */
    land_x = sx + dx - (dx >> 2);
    land_y = sy + dy - (dy >> 2);
    if (!walkable_px(land_x - 4, land_y - 4)) {
        land_x = tx;
        land_y = ty;
        if (!walkable_px(land_x - 4, land_y - 4)) {
            land_x = sx + sign8(dx) * 24;
            land_y = sy + sign8(dy) * 24;
        }
    }
    fb_live[i] = 1;
    fb_phase[i] = 0;
    fb_timer[i] = FUSE_FLIGHT;
    fb_x[i] = sx;
    fb_y[i] = sy;
    fb_vx[i] = (i8)((land_x - sx) / (i8)FUSE_FLIGHT);
    fb_vy[i] = (i8)((land_y - sy) / (i8)FUSE_FLIGHT);
    if (!fb_vx[i] && !fb_vy[i]) {
        fb_vx[i] = sign8(land_x - sx);
        fb_vy[i] = sign8(land_y - sy);
    }
    puff_at(sx, sy);
    sfx_play(SFX_TICK);
    return 1;
}

static void fuse_bombs_tick(void) {
    u8 i;
    for (i = 0; i < FUSE_BOMB_MAX; ++i) {
        if (!fb_live[i]) continue;
        if (fb_phase[i] == 0) {
            fb_x[i] += fb_vx[i];
            fb_y[i] += fb_vy[i];
            if (fb_timer[i]) fb_timer[i]--;
            if (!fb_timer[i] || !walkable_px(fb_x[i] - 4, fb_y[i] - 4)) {
                fb_phase[i] = 1;
                fb_timer[i] = FUSE_TICKS;
                puff_at(fb_x[i], fb_y[i]);
            }
            continue;
        }
        /* Visible blast-radius tell: pulse sparks on the four cardinals. */
        if ((fb_timer[i] & 7) == 0) {
            puff_at(fb_x[i] - FUSE_RADIUS, fb_y[i]);
            puff_at(fb_x[i] + FUSE_RADIUS, fb_y[i]);
            puff_at(fb_x[i], fb_y[i] - FUSE_RADIUS);
            puff_at(fb_x[i], fb_y[i] + FUSE_RADIUS);
            sfx_play(SFX_TICK);
        }
        if (fb_timer[i]) fb_timer[i]--;
        if (!fb_timer[i]) fuse_explode(i);
    }
}

static void fuse_hurler_tick(entity_t *e, const enemy_def_t *def) {
    u8 walk = def->ai_p0 ? def->ai_p0 : 48;
    u8 tell = def->ai_p1 ? def->ai_p1 : 20;
    u8 cool = def->ai_p2 ? def->ai_p2 : 90;
    i16 ex, ey, manh, adx, ady;
    if (RUN_IS_EASY() && tell < 200) tell = (u8)(tell + (tell >> 2));
    if (!(e->flags & EF_ACTIVE) || !e->hp) return;
    ex = FIX8_TO_INT(e->x);
    ey = FIX8_TO_INT(e->y);
    adx = (i16)player.x - ex;
    ady = (i16)player.y - ey;
    if (adx < 0) adx = (i16)-adx;
    if (ady < 0) ady = (i16)-ady;
    manh = (i16)(adx + ady);

    if (PHASE == 0) {
        if (manh < 20) {
            PHASE = 3;
            TIMER = 0;
            puff_at(ex, ey);
            sfx_play(SFX_TICK);
            return;
        }
        if ((++e->state_timer & 7) == 0) {
            u8 h = e->state & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->state = (u8)(rng_next_u8() & 3);
        }
        if (++TIMER >= walk) {
            PHASE = 1;
            TIMER = 0;
            puff_at(ex, ey);
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (TIMER == 0 || (TIMER & 7) == 0) sfx_play(SFX_TICK);
        if (++TIMER >= tell) {
            if (fuse_bomb_lob(ex + 4, ey + 4,
                    (i16)player.x + 4, (i16)player.y + 4)) {
                PHASE = 2;
                TIMER = 0;
            } else {
                TIMER = tell; /* hold the tell until a bomb slot frees */
                if (TIMER) TIMER--;
            }
        }
        return;
    }
    if (PHASE == 3) {
        /* Close-range exploder wind-up: long flash, then a self-centered
           burst. The Hurler survives (this is not the Bomber death burst). */
        if ((TIMER & 3) == 0) puff_at(ex, ey);
        if ((TIMER & 7) == 0) sfx_play(SFX_TICK);
        if (++TIMER >= 28) {
            puff_at(ex - FUSE_RADIUS, ey);
            puff_at(ex + FUSE_RADIUS, ey);
            puff_at(ex, ey - FUSE_RADIUS);
            puff_at(ex, ey + FUSE_RADIUS);
            room_shake(2, 8);
            sfx_play(SFX_ROAR);
            fuse_hurt_at(ex + 4, ey + 4, FUSE_RADIUS);
            PHASE = 2;
            TIMER = 0;
        }
        return;
    }
    if (++TIMER >= cool) {
        PHASE = 0;
        TIMER = 0;
    }
}

/* ---- Vault Hand ---- */
/* [1] timer [2] phase 0 hunt 1 lock 2 drop 3 grab 4 cool
   [3] mash [4] shadow x [5] shadow y */

u8 vault_hand_may_act(void) BANKED {
    if (run_state.world_mode) return 0;
    if (run_state_is_boss_room() || run_state_is_miniboss()) return 0;
    if (run_state_was_cleared_boss()) return 0;
    if (run_state_is_shop()) return 0;
    if (RUN_ROOM_IS_TOWN(run_state.room_counter)) return 0;
    if (run_state_dungeon_cell() == run_state_dungeon_entry_cell()) return 0;
    if (death_timer) return 0;
    return 1;
}

static void hand_hide(entity_t *e) {
    e->flags &= (u8)~EF_ON_SCREEN;
    e->x = FIX8(80);
    e->y = FIX8(200);
}

static void vault_hand_tick(entity_t *e, const enemy_def_t *def) {
    u8 shadow_t = def->ai_p0 ? def->ai_p0 : 48;
    u8 grab_t = def->ai_p1 ? def->ai_p1 : 48;

    if (!vault_hand_may_act()) {
        if (PHASE == 3) {
            vault_hand_holding = 0;
            PHASE = 4;
            TIMER = 0;
            hand_hide(e);
        }
        return;
    }
    if (player_status_kind == QSTATUS_STOP && PHASE == 3) {
        vault_hand_holding = 0;
        PHASE = 4;
        TIMER = 0;
        player.iframes = 30;
        hand_hide(e);
        return;
    }
    if (PHASE == 4) {
        if (++TIMER >= 160) { PHASE = 0; TIMER = 0; }
        return;
    }
    if (PHASE == 0) {
        hand_hide(e);
        /* track hero, grow shadow */
        e->ai_data[4] = (u8)player.x;
        e->ai_data[5] = (u8)player.y;
        if (++TIMER >= shadow_t) {
            PHASE = 1;
            TIMER = 0;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (++TIMER >= 16) {
            PHASE = 2;
            TIMER = 0;
            e->x = FIX8((i16)e->ai_data[4]);
            e->y = FIX8((i16)e->ai_data[5]);
            e->flags |= EF_ON_SCREEN;
            puff_at(FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
        }
        return;
    }
    if (PHASE == 2) {
        /* drop window: 12 frames plus 20-frame grab offer */
        if (++TIMER >= 32) {
            PHASE = 4;
            TIMER = 0;
            hand_hide(e);
        }
        return;
    }
    if (PHASE == 3) {
        vault_hand_holding = 1;
        player.x = (ppos_t)FIX8_TO_INT(e->x);
        player.y = (ppos_t)FIX8_TO_INT(e->y);
        {
            static u8 prev = 0;
            u8 raw = joypad();
            u8 edge = (u8)(raw & (u8)~prev);
            prev = raw;
            if (edge & (J_A | J_B | J_LEFT | J_RIGHT | J_UP | J_DOWN)) {
                e->ai_data[3]++;
                sfx_play(SFX_HIT);
            }
        }
        if (e->ai_data[3] >= 8 || !e->hp) {
            vault_hand_holding = 0;
            PHASE = 4;
            TIMER = 0;
            player.iframes = 30;
            hand_hide(e);
            return;
        }
        if (++TIMER >= grab_t) {
            vault_hand_holding = 0;
            pending_foyer_warp = 1;
            PHASE = 4;
            TIMER = 0;
            hand_hide(e);
            sfx_play(SFX_PORTAL);
        }
        return;
    }
}

/* Contact during drop starts a grab. Called from update after drop tick. */
static void vault_hand_offer_grab(entity_t *e) {
    i16 dx, dy;
    if (PHASE != 2) return;
    dx = FIX8_TO_INT(e->x) - (i16)player.x; if (dx < 0) dx = -dx;
    dy = FIX8_TO_INT(e->y) - (i16)player.y; if (dy < 0) dy = -dy;
    if (dx < 10 && dy < 10) {
        PHASE = 3;
        TIMER = 0;
        e->ai_data[3] = 0;
        vault_hand_holding = 1;
    }
}

void new_monster_update(entity_t *e, const enemy_def_t *def) BANKED {
    u8 kind = def->ai_kind;
    if (kind == AI_BLINK_CASTER) veil_magus_tick(e, def);
    else if (kind == AI_WALK_CASTER) hex_walker_tick(e, def);
    else if (kind == AI_SHOVER) bane_brute_tick(e);
    else if (kind == AI_ZIGZAG) zag_dart_tick(e, def);
    else if (kind == AI_BEAM_CASTER) leybeam_tick(e, def);
    else if (kind == AI_BOMB_LOBBER) fuse_hurler_tick(e, def);
    else if (kind == AI_GRABBER) {
        vault_hand_tick(e, def);
        vault_hand_offer_grab(e);
        if (!e->hp && vault_hand_holding) vault_hand_holding = 0;
    }
}

/* ---- grouping / caps after room population ---- */

static u8 is_status_ally(u8 id) {
    return id == ENEMY_SHADE || id == ENEMY_RUNE_LANTERN
        || id == ENEMY_DUSK_MIDGE || id == ENEMY_FROST_LANCER
        || id == ENEMY_MIRE_SPORE || id == ENEMY_BRAMBLE_SPRITE
        || id == ENEMY_GLOAM_LEECH || id == ENEMY_CINDER_MAW
        || id == ENEMY_CINDER_KITE || id == ENEMY_BOG_TOAD
        || id == ENEMY_MIRROR_MOTH || id == ENEMY_FOLD_STAR
        || id == ENEMY_WARLOCK || id == ENEMY_DREAD_BELL;
}

static u8 count_id(u8 id) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == id) n++;
    return n;
}

static void despawn_extra(u8 id, u8 keep) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        if (entities[i].ai_data[0] != id) continue;
        n++;
        if (n > keep) entity_kill(i);
    }
}

static u8 stage_status_pick(void) {
    static const u8 cands[14] = {
        ENEMY_SHADE, ENEMY_RUNE_LANTERN, ENEMY_DUSK_MIDGE, ENEMY_FROST_LANCER,
        ENEMY_MIRE_SPORE, ENEMY_BRAMBLE_SPRITE, ENEMY_GLOAM_LEECH,
        ENEMY_CINDER_MAW, ENEMY_CINDER_KITE, ENEMY_BOG_TOAD, ENEMY_MIRROR_MOTH,
        ENEMY_FOLD_STAR, ENEMY_WARLOCK, ENEMY_DREAD_BELL
    };
    u8 s = run_state.bosses_beaten % N_STAGES;
    u8 i, k;
    for (k = 0; k < 14; ++k) {
        for (i = 0; i < stage_pool_n[s]; ++i)
            if (stage_pool_ids[s][i] == cands[k]) return cands[k];
    }
    return 0xFF;
}

static u8 convert_slot_to(u8 id) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 cur;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        cur = e->ai_data[0];
        if (cur == ENEMY_BANE_BRUTE || cur == ENEMY_VAULT_HAND
            || cur == ENEMY_LEYBEAM || cur == ENEMY_VEIL_MAGUS
            || cur == ENEMY_FUSE_HURLER
            || is_status_ally(cur)) continue;
        /* Replace this rolled body with a status ally. */
        {
            const enemy_def_t *def = &enemies[id];
            e->ai_data[0] = id;
            e->sprite_tile = def->sprite_set;
            e->palette = def->palette;
            e->hp = def->stats.hp;
            e->damage = def->stats.damage;
            e->hitbox = (6 << 4) | 6;
            return 1;
        }
    }
    return 0;
}

static void place_allies_behind_brute(void) {
    u8 i, b = 0xFF, placed = 0;
    i16 bx, by;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == ENEMY_BANE_BRUTE) { b = i; break; }
    if (b == 0xFF) return;
    bx = FIX8_TO_INT(entities[b].x);
    by = FIX8_TO_INT(entities[b].y);
    for (i = 0; i < MAX_ENTITIES && placed < 2; ++i) {
        i16 nx, ny;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        if (!is_status_ally(entities[i].ai_data[0])) continue;
        nx = bx + (placed ? 24 : -24);
        ny = by;
        if (!walkable_px(nx, ny)) { nx = bx; ny = by + (placed ? 24 : -24); }
        if (!walkable_px(nx, ny)) continue;
        entities[i].x = FIX8(nx);
        entities[i].y = FIX8(ny);
        placed++;
    }
}


void bane_brute_apply_knockback(i8 kx, i8 ky) BANKED {
    u8 n;
    u8 steps = (kx && ky) ? 13 : 18;
    for (n = 0; n < steps; ++n) {
        i16 nx = (i16)(player.x + kx);
        i16 ny = (i16)(player.y + ky);
        if (!room_player_position_clear(nx, ny)) {
            if (kx && ky) {
                if (room_player_position_clear((i16)(player.x + kx), (i16)player.y)) {
                    player.x = (ppos_t)(player.x + kx);
                    continue;
                }
                if (room_player_position_clear((i16)player.x, (i16)(player.y + ky))) {
                    player.y = (ppos_t)(player.y + ky);
                    continue;
                }
            }
            break;
        }
        player.x = (ppos_t)nx;
        player.y = (ppos_t)ny;
    }
}

void new_monsters_post_spawn(void) BANKED {
    u8 allies = 0, i;
    leybeam_beam_live = 0;
    ley_n = 0;
    ley_flush = 0;
    leybeam_flush_pending = 0;
    pending_foyer_warp = 0;
    vault_hand_holding = 0;
    fuse_bombs_clear();
    new_monsters_busy = 0;
    new_monsters_in_room = 0;

    despawn_extra(ENEMY_VEIL_MAGUS, 2);
    despawn_extra(ENEMY_ZAG_DART, 2);
    despawn_extra(ENEMY_HEX_WALKER, 3);
    despawn_extra(ENEMY_VAULT_HAND, 1);
    despawn_extra(ENEMY_LEYBEAM, 1);
    despawn_extra(ENEMY_BANE_BRUTE, 1);
    despawn_extra(ENEMY_FUSE_HURLER, 2);

    if (count_id(ENEMY_VAULT_HAND) && !vault_hand_may_act())
        despawn_extra(ENEMY_VAULT_HAND, 0);

    new_monsters_busy = (u8)(count_id(ENEMY_VEIL_MAGUS)
        || count_id(ENEMY_HEX_WALKER)
        || count_id(ENEMY_VAULT_HAND)
        || count_id(ENEMY_BANE_BRUTE)
        || count_id(ENEMY_ZAG_DART)
        || count_id(ENEMY_LEYBEAM)
        || count_id(ENEMY_FUSE_HURLER));
    new_monsters_in_room = new_monsters_busy;

    if (!count_id(ENEMY_BANE_BRUTE)) return;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && is_status_ally(entities[i].ai_data[0])) allies++;
    while (allies < 2) {
        u8 sid = stage_status_pick();
        if (sid == 0xFF || !convert_slot_to(sid)) break;
        allies++;
    }
    if (allies < 2) despawn_extra(ENEMY_BANE_BRUTE, 0);
    else place_allies_behind_brute();
    new_monsters_busy = (u8)(count_id(ENEMY_VEIL_MAGUS)
        || count_id(ENEMY_HEX_WALKER)
        || count_id(ENEMY_VAULT_HAND)
        || count_id(ENEMY_BANE_BRUTE)
        || count_id(ENEMY_ZAG_DART)
        || count_id(ENEMY_LEYBEAM)
        || count_id(ENEMY_FUSE_HURLER));
    new_monsters_in_room = new_monsters_busy;
}

void new_monsters_foyer_warp(void) BANKED {
    u8 entry = run_state_dungeon_entry_cell();
    u8 i;
    pending_foyer_warp = 0;
    vault_hand_holding = 0;
    leybeam_restore();
    fuse_bombs_clear();
    for (i = 0; i < MAX_ENTITIES; ++i)
        if (entities[i].flags & EF_ACTIVE) entity_kill(i);
    run_state.room_counter = (u8)(run_state_stage_start(run_state.bosses_beaten)
        + entry);
    run_state.entered_from = DIR_S;
    player.iframes = 60;
    /* room_tick reloads the foyer in-place (same as a door seam). Do not
       call room_enter() from inside the tick — the loop will not re-enter
       SCREEN_ROOM, and the nested enter crashes the machine. post_spawn
       already despawns a Hand in the foyer. */
}

void new_monsters_draw(void) BANKED {
    u8 i, live_beam = 0, bi, used = 0, any = 0;
    /* Drop the sticky busy flag once no specialist, bomb, or beam remains
       so a converted/cleared room does not bank-call this every frame. */
    for (i = 0; i < FUSE_BOMB_MAX; ++i) if (fb_live[i]) any = 1;
    if (leybeam_beam_live || vault_hand_holding) any = 1;
    if (!any) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            entity_t *e = &entities[i];
            u8 id;
            if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
            id = e->ai_data[0];
            if (id >= ENEMY_VEIL_MAGUS && id <= ENEMY_FUSE_HURLER) {
                any = 1;
                break;
            }
        }
    }
    if (!any && player_status_kind != QSTATUS_CONFUSION) {
        new_monsters_busy = 0;
        new_monsters_in_room = 0;
        move_sprite(35, 0, 0);
        move_sprite(36, 0, 0);
        move_sprite(37, 0, 0);
        move_sprite(38, 0, 0);
        move_sprite(39, 0, 0);
        return;
    }
    if (any) { new_monsters_busy = 1; new_monsters_in_room = 1; }
    fuse_bombs_tick();
    if (leybeam_beam_live) {
        for (i = 0; i < MAX_ENTITIES; ++i)
            if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
                && entities[i].ai_data[0] == ENEMY_LEYBEAM && entities[i].hp)
                live_beam = 1;
        if (!live_beam) leybeam_clear_beam();
    }
    /* Shadow for a hunting Vault Hand, plus confusion swirl over the hero. */
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        if (e->ai_data[0] == ENEMY_VAULT_HAND && (PHASE == 0 || PHASE == 1)) {
            u8 sx = (u8)(e->ai_data[4] - room_camera_x + 8);
            u8 sy = (u8)(e->ai_data[5] - room_camera_y + 16);
            move_sprite(39, sx, sy);
            set_sprite_tile(39, SPR_FX_IMPACT);
            set_sprite_prop(39, 0);
        }
    }
    if (player_status_kind == QSTATUS_CONFUSION && !vault_hand_holding
        && !death_timer) {
        u8 sx = (u8)((u8)player.x - room_camera_x + 8);
        u8 sy = (u8)((u8)player.y - room_camera_y + 8);
        /* Status glyph 13 at tile 237 is a star-burst; flip for a swirl. */
        move_sprite(38, sx, sy);
        set_sprite_tile(38, 237);
        set_sprite_prop(38, (u8)(((sys_time >> 3) & 1) ? S_FLIPX : 0) | 6);
    } else {
        move_sprite(38, 0, 0);
    }
    if (leybeam_beam_live) {
        /* Muzzle flare at the locked origin. The shaft is a VBlank-stamped
           BG strip; a spark at the far end marks the lane end. */
        u8 sx = (u8)(beam_ox - room_camera_x + 8);
        u8 sy = (u8)(beam_oy - room_camera_y + 16);
        move_sprite(37, sx, sy);
        set_sprite_tile(37, SPR_FX_MUZZLE);
        set_sprite_prop(37, 5);
    } else {
        move_sprite(37, 0, 0);
    }
    for (bi = 0; bi < FUSE_BOMB_MAX; ++bi) {
        u8 slot = (u8)(35 + used);
        if (!fb_live[bi]) continue;
        {
            u8 sx = (u8)(fb_x[bi] - room_camera_x + 8);
            u8 sy = (u8)(fb_y[bi] - room_camera_y + 16);
            move_sprite(slot, sx, sy);
            set_sprite_tile(slot, SPR_FX_IMPACT);
            set_sprite_prop(slot, (u8)((fb_phase[bi] && (fb_timer[bi] & 2)) ? 5 : 4));
            used++;
        }
    }
    if (used < 1) move_sprite(35, 0, 0);
    if (used < 2) move_sprite(36, 0, 0);
}

