#pragma bank 25

#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/enemy_new_ai.h"
#include "game/enemy_new_draw.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/basilisk_art.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 pending_foyer_warp;
u8 vault_hand_holding;
u8 leybeam_beam_live;
u8 leybeam_flush_pending;
u8 new_monsters_busy;
u8 new_monsters_in_room;
u8 confusion_swirl_live;

extern u8 entity_oam_high;
extern u8 entity_anim_counter;

/* Locked beam lanes (no initializers: banked RAM is set up on first use). */
static u8 beam_dir, beam_w, beam_vert, beam_hot, beam_owner, beam_maxlen;
static i8 beam_step;
static u8 beam_tx0, beam_ty0;
static u8 beam_lane[4];

#define LEY_VBL_BURST 16
static u8 ley_n, ley_k, ley_flush, ley_art_want, ley_art_have;
/* Resident bank-1 OBJ art: 0 none, 1..3 basilisk tier + blast, 4 blast only.
   Cleared on room entry (vignettes and bosses reuse those tiles). */
static u8 bas_art_have;


/* Uploaded to VRAM bank 1 at LEYBEAM_BG_TILE. Ghost dots mark the exact
   lanes during the charge; two solid glow frames shimmer while firing. */
#define LEY_ART_GHOST 1
#define LEY_ART_BEAM  2
#define LEY_ART_BEAM2 3
static const u8 ley_art[4][16] = {
    { 0 },
    { 0x00, 0x00, 0x22, 0x22, 0x00, 0x00, 0x00, 0x00,
      0x00, 0x00, 0x88, 0x88, 0x00, 0x00, 0x00, 0x00 },
    { 0x38, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0xFF, 0xFF,
      0xFF, 0xFF, 0x1C, 0xFF, 0x38, 0xFF, 0x1C, 0xFF },
    { 0x1C, 0xFF, 0x38, 0xFF, 0xFF, 0xFF, 0x38, 0xFF,
      0x1C, 0xFF, 0xFF, 0xFF, 0x1C, 0xFF, 0x38, 0xFF },
};

#define FUSE_FLIGHT 16
#define FUSE_TICKS  40
#define BLAST_FRAMES 22
#define BLAST_HOT    10  /* damage live while the fireball is drawn */
u8  fb_live[FUSE_BOMB_MAX];
u8  fb_phase[FUSE_BOMB_MAX]; /* 0 flight, 1 fuse, 2 blast */
u8  fb_timer[FUSE_BOMB_MAX];
i16 fb_x[FUSE_BOMB_MAX], fb_y[FUSE_BOMB_MAX]; /* centre px */
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

/* ---- Basilisk (Leybeam family): cardinal ghost-lane tell + wide BG beam ----
   [1] timer [2] phase 0 drift 1 charge 2 beam [3] dir 0..3 [4] bit0 face-left
   Three tiers share this tick: Ley (2 tiles wide), Sun (3), Nox (4).
   The 32x32 body (x-8..x+23, y-16..y+15) is drawn from bank-1 OBJ in
   new_monsters_draw(); the entity's own 8x8 tile (219) is blank, and its
   15x15 hitbox is the coil at x..x+15, y..y+15. Lanes leave the mouth. */

static u8 is_basilisk(u8 id) {
    return id == ENEMY_LEYBEAM || id == ENEMY_SUN_BASILISK
        || id == ENEMY_NOX_BASILISK;
}

static u8 basilisk_lanes(u8 id) {
    return id == ENEMY_NOX_BASILISK ? 4 : id == ENEMY_SUN_BASILISK ? 3 : 2;
}

/* Mouth point the beam lanes are centred on. */
static i16 head_x(entity_t *e) {
    return FIX8_TO_INT(e->x) + ((e->ai_data[4] & 1) ? -2 : 18);
}
static i16 head_y(entity_t *e) { return FIX8_TO_INT(e->y) - 6; }

static u8 nearest_cardinal(i16 ex, i16 ey) {
    i16 dx = (i16)player.x + 8 - ex;
    i16 dy = (i16)player.y + 12 - ey;
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

/* Lane cell (k across, n along) in room tile coordinates. */
static u8 lane_tx(u8 k, u8 n) {
    return beam_vert ? (u8)(beam_tx0 + k) : (u8)(beam_tx0 + (i8)n * beam_step);
}
static u8 lane_ty(u8 k, u8 n) {
    return beam_vert ? (u8)(beam_ty0 + (i8)n * beam_step) : (u8)(beam_ty0 + k);
}

/* Called right after VBlank. ley_flush 1 stamps the locked lanes, 2 puts
   the floor back. The shared BG tile's art (ghost dots during the charge,
   solid glow while firing) is a single 16-byte upload, so the whole lane
   flips from tell to beam on one frame no matter how wide it is. */
void leybeam_vblank_flush(void) BANKED {
    u8 burst = 0;
    if (ley_art_want != ley_art_have) {
        VBK_REG = 1;
        set_bkg_data(LEYBEAM_BG_TILE, 1, ley_art[ley_art_want]);
        VBK_REG = 0;
        ley_art_have = ley_art_want;
        burst += 2;
    }
    if (ley_flush == 2) {
        /* Restore straight from the RAM map: exact tiles and attrs. */
        room_draw_tilemap();
        ley_flush = 0;
    }
    while (ley_flush && burst < LEY_VBL_BURST) {
        if (ley_n >= beam_maxlen) {
            ley_flush = 0;
            break;
        }
        if (ley_n < beam_lane[ley_k]) {
            u8 tx = lane_tx(ley_k, ley_n);
            u8 ty = lane_ty(ley_k, ley_n);
            u8 t = room_tile_at_px((i16)tx << 3, (i16)ty << 3);
            if (ley_floorish(t))
                ley_put(tx, ty, LEYBEAM_BG_TILE, (u8)(0x08 | BGPAL_CRYSTAL));
        }
        burst++;
        if (++ley_k >= beam_w) { ley_k = 0; ley_n++; }
    }
    leybeam_flush_pending = (u8)(ley_flush || ley_art_want != ley_art_have);
}

static void leybeam_restore(void) {
    if (!leybeam_beam_live) return;
    leybeam_beam_live = 0;
    beam_hot = 0;
    ley_n = 0;
    ley_k = 0;
    ley_flush = 2;
    leybeam_flush_pending = 1;
}

void leybeam_clear_beam(void) BANKED {
    leybeam_restore();
}

/* Lock the lanes at the start of the charge. Each lane runs from the body's
   centre row/column until its own first wall, so a pillar shadows only the
   lanes it actually blocks and the damage test reads the same table. */
static void leybeam_lock(entity_t *e) {
    i16 cx = head_x(e);
    i16 cy = head_y(e);
    u8 d = e->ai_data[3] & 3;
    u8 k, n;
    i16 across = (d == 0 || d == 2) ? cx : cy;
    i16 first = (i16)((across + 4 - (i16)basilisk_lanes(e->ai_data[0]) * 4) >> 3);
    if (first < 0) first = 0;
    beam_dir = d;
    beam_w = basilisk_lanes(e->ai_data[0]);
    beam_vert = (d == 0 || d == 2) ? 1 : 0;
    beam_step = (d == 1 || d == 2) ? 1 : -1;
    if (beam_vert) { beam_tx0 = (u8)first; beam_ty0 = (u8)(cy >> 3); }
    else { beam_ty0 = (u8)first; beam_tx0 = (u8)(cx >> 3); }
    beam_maxlen = 0;
    for (k = 0; k < beam_w; ++k) {
        for (n = 0; n < 24; ++n) {
            i16 tx = (i16)lane_tx(k, n);
            i16 ty = (i16)lane_ty(k, n);
            if (tx < 1 || ty < 1 || tx >= (i16)(room_world_width >> 3) - 1
                || ty >= (i16)(room_world_height >> 3) - 1) break;
            /* Stop at the first cell that cannot carry the stamp, so no
               live cell is ever invisible. */
            if (!ley_floorish(room_tile_at_px(tx << 3, ty << 3))) break;
        }
        beam_lane[k] = n;
        if (n > beam_maxlen) beam_maxlen = n;
    }
    ley_n = 0;
    ley_k = 0;
    ley_flush = 1;
    ley_art_want = LEY_ART_GHOST;
    leybeam_flush_pending = 1;
    leybeam_beam_live = 1;
    beam_hot = 0;
}

/* Hurtbox (x+5..x+10, y+9..y+14) against the stamped lanes, inset 1 px so
   grazing the glow edge never costs a heart. */
u8 leybeam_hits_player(void) {
    i16 lo, hi, along, a0, base;
    u8 k, n;
    if (!beam_hot) return 0;
    if (beam_vert) {
        lo = (i16)player.x + 6; hi = (i16)player.x + 9;
        along = (i16)player.y + 12;
        base = (i16)beam_tx0 << 3;
        a0 = (i16)beam_ty0;
    } else {
        lo = (i16)player.y + 10; hi = (i16)player.y + 13;
        along = (i16)player.x + 8;
        base = (i16)beam_ty0 << 3;
        a0 = (i16)beam_tx0;
    }
    {
        i16 dn = (i16)((along >> 3) - a0);
        if (beam_step < 0) dn = (i16)-dn;
        if (dn < 0 || dn >= 24) return 0;
        n = (u8)dn;
    }
    for (k = 0; k < beam_w; ++k) {
        i16 l0 = (i16)(base + ((i16)k << 3));
        if (hi < l0 || lo > l0 + 7) continue;
        if (n < beam_lane[k]) return 1;
    }
    return 0;
}

/* Body-aware drift: the 32x32 body (x-8..x+23, y-16..y+15) stays on
   floor, so the head never pokes through a wall. walkable_px tests the
   tile under (x+4, y+4). */
static u8 basilisk_clear(i16 x, i16 y) {
    return walkable_px(x - 8, y - 16) && walkable_px(x + 16, y - 16)
        && walkable_px(x - 8, y + 8) && walkable_px(x + 16, y + 8)
        && walkable_px(x + 4, y - 4);
}

static void basilisk_face(entity_t *e) {
    u8 d = e->ai_data[3] & 3;
    if (PHASE && (d == 1 || d == 3)) {
        e->ai_data[4] = (d == 3) ? 1 : 0;
        return;
    }
    e->ai_data[4] = ((i16)player.x + 8 < FIX8_TO_INT(e->x) + 8) ? 1 : 0;
}

static void bas_art_need(u8 want) {
    if (bas_art_have == want || (want == 4 && bas_art_have)) return;
    basilisk_art_load(want == 4 ? 0xFF : (u8)(want - 1));
    bas_art_have = want;
}

static void leybeam_tick(entity_t *e, const enemy_def_t *def) {
    u8 tell = def->ai_p0 ? def->ai_p0 : 40;
    u8 beam = def->ai_p1 ? def->ai_p1 : 36;
    u8 cool = def->ai_p2 ? def->ai_p2 : 100;
    u8 me = (u8)(e - entities);
    if (RUN_IS_EASY() && tell < 200) tell = (u8)(tell + (tell >> 2));

    if (!(e->flags & EF_ACTIVE) || !e->hp) {
        if (beam_owner == me) leybeam_restore();
        return;
    }
    bas_art_need((u8)(basilisk_lanes(e->ai_data[0]) - 1));
    if (PHASE == 0) {
        if ((++e->state_timer & 7) == 0) {
            u8 h = e->state & 3;
            i16 x = FIX8_TO_INT(e->x) + card_dx[h];
            i16 y = FIX8_TO_INT(e->y) + card_dy[h];
            if (basilisk_clear(x, y)) { e->x = FIX8(x); e->y = FIX8(y); }
            else e->state = (u8)(rng_next_u8() & 3);
        }
        basilisk_face(e);
        if (++TIMER >= cool) {
            /* One lane on the map at a time; a second caster waits. */
            if (leybeam_beam_live || ley_flush) { TIMER = cool - 1; return; }
            PHASE = 1;
            TIMER = 0;
            e->ai_data[3] = nearest_cardinal(head_x(e), head_y(e));
            basilisk_face(e);   /* turn first: the mouth moves with facing */
            beam_owner = me;
            leybeam_lock(e);
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (TIMER + 8 == tell || TIMER + 16 == tell) sfx_play(SFX_TICK);
        if (++TIMER >= tell) {
            PHASE = 2;
            TIMER = 0;
            beam_hot = 1;
            ley_art_want = LEY_ART_BEAM;
            leybeam_flush_pending = 1;
            sfx_play(SFX_ROAR);
            room_shake(1, 6);
        }
        return;
    }
    /* fire: damage at most once per 20-frame window via ordinary iframes */
    if ((TIMER & 3) == 0) {
        ley_art_want = (TIMER & 4) ? LEY_ART_BEAM2 : LEY_ART_BEAM;
        leybeam_flush_pending = 1;
    }
    if (leybeam_hits_player() && player.iframes == 0 && player.hp && !death_timer) {
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

/* ---- Fuse Hurler: lobbed fused bomb + close-range wind-up ----
   Bomb phases: 0 flight, 1 fuse, 2 exploding (fb_timer counts up). */

static void fuse_bombs_clear(void) {
    u8 i;
    for (i = 0; i < FUSE_BOMB_MAX; ++i) fb_live[i] = 0;
}

static void fuse_hurt_at(i16 x, i16 y, u8 radius) {
    i16 px = (i16)player.x + 8;
    i16 py = (i16)player.y + 12;
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
}

/* Deep noise thump on CH4 plus a falling CH1 growl. Owns both channels
   briefly so the score cannot swallow it. */
static void boom_sfx(u8 big) {
    sfx_claim_channels(big ? 20 : 8, big ? 36 : 18);
    NR42_REG = big ? 0xF7 : 0xC4;
    NR43_REG = big ? 0x71 : 0x54;
    NR44_REG = 0x80;
    if (big) {
        NR10_REG = 0x7F;
        NR11_REG = 0xC0;
        NR12_REG = 0xF5;
        NR13_REG = 0x40;
        NR14_REG = 0x82;
    }
}

/* Start a blast centred on (cx, cy). Damage follows the visible burst:
   the Chebyshev square FUSE_RADIUS around the centre is live for the first
   BLAST_HOT frames, which is exactly while the fireball is on screen. */
static void blast_start(u8 i, i16 cx, i16 cy) {
    bas_art_need(4);
    fb_live[i] = 1;
    fb_phase[i] = 2;
    fb_timer[i] = 0;
    fb_x[i] = cx;
    fb_y[i] = cy;
    room_shake(3, 14);
    boom_sfx(1);
}

static void blast_tick(u8 i) {
    u8 t = fb_timer[i];
    i16 x = fb_x[i], y = fb_y[i];
    if (t < BLAST_HOT) fuse_hurt_at(x, y, FUSE_RADIUS);
    if (t == 2) {
        /* Debris kicked to the corners of the damage square. */
        u8 pal = BLAST_PAL | 0x08;
        fx_spawn(BLAST_TILE_DEBRIS, pal, x - FUSE_RADIUS - 4, y - FUSE_RADIUS - 4, 12);
        fx_spawn(BLAST_TILE_DEBRIS, (u8)(pal | S_FLIPX), x + FUSE_RADIUS - 4, y - FUSE_RADIUS - 4, 12);
        fx_spawn(BLAST_TILE_DEBRIS, (u8)(pal | S_FLIPY), x - FUSE_RADIUS - 4, y + FUSE_RADIUS - 4, 12);
        fx_spawn(BLAST_TILE_DEBRIS, (u8)(pal | S_FLIPX | S_FLIPY), x + FUSE_RADIUS - 4, y + FUSE_RADIUS - 4, 12);
    }
    if (t == 7) boom_sfx(0); /* crackle tail */
    if (++fb_timer[i] >= BLAST_FRAMES) fb_live[i] = 0;
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
    puff_at(sx - 4, sy - 4);
    sfx_play(SFX_TICK);
    return 1;
}

static void fuse_bombs_tick(void) {
    u8 i;
    for (i = 0; i < FUSE_BOMB_MAX; ++i) {
        if (!fb_live[i]) continue;
        if (fb_phase[i] == 2) { blast_tick(i); continue; }
        if (fb_phase[i] == 0) {
            fb_x[i] += fb_vx[i];
            fb_y[i] += fb_vy[i];
            if (fb_timer[i]) fb_timer[i]--;
            if (!fb_timer[i] || !walkable_px(fb_x[i] - 4, fb_y[i] - 4)) {
                fb_phase[i] = 1;
                fb_timer[i] = FUSE_TICKS;
            }
            continue;
        }
        /* The fuse tell (eight corner/edge sparks on the damage square) is
           drawn every frame in new_monsters_draw; tick faster near the end. */
        if ((fb_timer[i] & ((fb_timer[i] < 16) ? 3 : 7)) == 0) sfx_play(SFX_TICK);
        if (fb_timer[i]) fb_timer[i]--;
        if (!fb_timer[i]) blast_start(i, fb_x[i], fb_y[i]);
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
    adx = (i16)player.x + 4 - ex;
    ady = (i16)player.y + 8 - ey;
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
                    (i16)player.x + 8, (i16)player.y + 12)) {
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
        /* Close-range wind-up: long flash, then the same full blast centred
           on the Hurler. The Hurler survives (not the Bomber death burst). */
        if ((TIMER & 3) == 0) e->ai_data[7] = 2;
        if ((TIMER & 7) == 0) sfx_play(SFX_TICK);
        if (++TIMER >= 28) {
            u8 i;
            for (i = 0; i < FUSE_BOMB_MAX; ++i) if (!fb_live[i]) break;
            if (i < FUSE_BOMB_MAX) blast_start(i, ex + 4, ey + 4);
            else {
                room_shake(3, 14);
                boom_sfx(1);
                fuse_hurt_at(ex + 4, ey + 4, FUSE_RADIUS);
            }
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
            || is_basilisk(cur) || cur == ENEMY_VEIL_MAGUS
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

static u8 basilisk_count(void) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && is_basilisk(entities[i].ai_data[0])) n++;
    return n;
}

/* Tier of the room's (single) basilisk: 0 Ley, 1 Sun, 2 Nox, 0xFF none. */
static u8 basilisk_tier(void) {
    u8 i, id;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        id = entities[i].ai_data[0];
        if (is_basilisk(id)) return (u8)(basilisk_lanes(id) - 2);
    }
    return 0xFF;
}

/* One basilisk per room (they share one beam and one art slot). The keeper
   gets the blank core tile, the full 15x15 coil hitbox, and a nudge until
   its 32x32 body sits on open floor. */
static void basilisk_setup(void) {
    static const i8 nudge_x[8] = { 0, 8, -8, 0, 16, -16, 8, -8 };
    static const i8 nudge_y[8] = { 8, 0, 0, 16, 8, 8, 16, 16 };
    u8 i, k, kept = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 x, y;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY
            || !is_basilisk(e->ai_data[0])) continue;
        if (kept) { entity_kill(i); continue; }
        kept = 1;
        e->sprite_tile = SPR_ENEMY_LEYBEAM;   /* blank: body is drawn in OAM */
        e->hitbox = 0xFF;
        e->ai_data[4] = 0;
        x = FIX8_TO_INT(e->x);
        y = FIX8_TO_INT(e->y);
        if (basilisk_clear(x, y)) continue;
        for (k = 0; k < 8; ++k) {
            if (basilisk_clear(x + nudge_x[k], y + nudge_y[k])) {
                e->x = FIX8(x + nudge_x[k]);
                e->y = FIX8(y + nudge_y[k]);
                break;
            }
        }
    }
}

void new_monsters_post_spawn(void) BANKED {
    u8 allies = 0, i;
    leybeam_beam_live = 0;
    ley_n = 0;
    ley_flush = 0;
    leybeam_flush_pending = 0;
    ley_art_have = 0xFF;   /* tile 63's art may have been replaced: re-upload */
    ley_art_want = 0;
    beam_hot = 0;
    nm_xo_hi = 0;          /* room entry already cleared OAM 4..39 */
    pending_foyer_warp = 0;
    vault_hand_holding = 0;
    fuse_bombs_clear();
    new_monsters_busy = 0;
    new_monsters_in_room = 0;
    confusion_swirl_live = 0;

    despawn_extra(ENEMY_VEIL_MAGUS, 2);
    despawn_extra(ENEMY_ZAG_DART, 2);
    despawn_extra(ENEMY_HEX_WALKER, 3);
    despawn_extra(ENEMY_VAULT_HAND, 1);
    basilisk_setup();
    despawn_extra(ENEMY_BANE_BRUTE, 1);
    despawn_extra(ENEMY_FUSE_HURLER, 2);

    if (count_id(ENEMY_VAULT_HAND) && !vault_hand_may_act())
        despawn_extra(ENEMY_VAULT_HAND, 0);

    new_monsters_busy = (u8)(count_id(ENEMY_VEIL_MAGUS)
        || count_id(ENEMY_HEX_WALKER)
        || count_id(ENEMY_VAULT_HAND)
        || count_id(ENEMY_BANE_BRUTE)
        || count_id(ENEMY_ZAG_DART)
        || basilisk_count()
        || count_id(ENEMY_FUSE_HURLER));
    new_monsters_in_room = new_monsters_busy;

    bas_art_have = 0;
    {
        u8 tier = basilisk_tier();
        if (tier != 0xFF) bas_art_need((u8)(tier + 1));
        else if (count_id(ENEMY_FUSE_HURLER)) bas_art_need(4);
    }

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
        || basilisk_count()
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
    /* A pending lane restore keeps the room flag up until the floor is back. */
    if (leybeam_beam_live || vault_hand_holding || ley_flush
        || leybeam_flush_pending) any = 1;
    if (!any) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            entity_t *e = &entities[i];
            u8 id;
            if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
            id = e->ai_data[0];
            if (id >= ENEMY_VEIL_MAGUS && id <= ENEMY_NOX_BASILISK) {
                any = 1;
                break;
            }
        }
    }
    if (!any && player_status_kind != QSTATUS_CONFUSION) {
        new_monsters_busy = 0;
        new_monsters_in_room = 0;
        confusion_swirl_live = 0;
        move_sprite(35, 0, 0);
        move_sprite(36, 0, 0);
        move_sprite(37, 0, 0);
        move_sprite(38, 0, 0);
        move_sprite(39, 0, 0);
        nm_extras_park();
        return;
    }
    if (any) { new_monsters_busy = 1; new_monsters_in_room = 1; }
    fuse_bombs_tick();
    if (leybeam_beam_live) {
        for (i = 0; i < MAX_ENTITIES; ++i)
            if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
                && is_basilisk(entities[i].ai_data[0]) && entities[i].hp)
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
        confusion_swirl_live = 1;
    } else {
        move_sprite(38, 0, 0);
        confusion_swirl_live = 0;
    }
    /* The basilisk's open jaw and orb are the muzzle now; 37 stays parked. */
    move_sprite(37, 0, 0);
    for (bi = 0; bi < FUSE_BOMB_MAX; ++bi) {
        u8 slot = (u8)(35 + used);
        if (!fb_live[bi] || fb_phase[bi] == 2) continue;
        {
            i16 wx = (i16)(fb_x[bi] + 4 - (i16)room_camera_x);
            i16 wy = (i16)(fb_y[bi] + 12 - (i16)room_camera_y);
            u8 sx = (u8)wx, sy = (u8)wy;
            if (wx <= 0 || wx >= 168 || wy <= 0 || wy >= 160) sx = sy = 0;
            move_sprite(slot, sx, sy);
            set_sprite_tile(slot, SPR_FX_IMPACT);
            set_sprite_prop(slot, (u8)((fb_phase[bi] && (fb_timer[bi] & 2)) ? 5 : 4));
            used++;
        }
    }
    if (used < 1) move_sprite(35, 0, 0);
    if (used < 2) move_sprite(36, 0, 0);
    nm_extras_draw();
}

