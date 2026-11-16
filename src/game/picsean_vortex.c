#pragma bank 18

#include <gb/gb.h>
#include <string.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/hexa_boss.h"
#include "game/picsean_vortex.h"
#include "game/cinder_big.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/rare_enemy.h"
#include "game/room.h"
#include "game/status.h"
#include "render/large_boss.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

// Picsean's full-Will Tide Vortex.
// Spec: docs/superpowers/specs/2026-11-15-picsean-tide-vortex.md
//
// Damage goes through the ordinary player-shot path by way of one inert
// "carrier" projectile (PROJ_AUX_VORTEX). combat_player_shots skips it, so
// the carrier never hits anything by itself; this file moves it onto each
// body the vortex reaches and applies one hit. That keeps weakness, LCK,
// status, Colossus/Hexa/return-echo caps, boss links and kill rewards
// exactly the same as every other weapon.

u8 combat_apply_player_shot_hit(entity_t *shot, u8 i, entity_t *ej,
                                u8 j, u8 *giant_hits) BANKED;
extern u8 entity_oam_high;

u8 picsean_vortex_ticks;
u8 picsean_vortex_radius;
u8 picsean_vortex_abort;

static u8 vortex_carrier = 0xFF;
static u8 vortex_damage;
static u8 vortex_rmax;
// World-space eye, snapped in begin() so the spiral stays at the
// cast point while Picsean swims away (Argon's Abyssal Maelstrom default).
static i16 vortex_wx, vortex_wy;
static u8 vortex_giant_hits;
static u8 vortex_fx_budget;
static u8 vortex_flashing;
// One front hit and one arm hit per slot per cast.
static u8 front_hit[MAX_ENTITIES / 8];
static u8 arm_hit[MAX_ENTITIES / 8];
// Bearing (64ths, screen Y down) and distance of each body when the front
// reached it. An arm crosses the body when its spiral angle at that
// distance lines up with the bearing.
static u8 body_phi[MAX_ENTITIES];
static u8 body_d[MAX_ENTITIES];
// This tick's arm points as ready-made OAM bytes (screen space, Y=0 hides).
// The draw is a plain copy and the arm test reuses the same bytes.
static u8 seg_oam[PICSEAN_VORTEX_SEGS * 4];
static u8 seg_n;

// 64-step sine, amplitude 64.
static const i8 vortex_sin[64] = {
    0, 6, 12, 19, 24, 30, 36, 41, 45, 49, 53, 56, 59, 61, 63, 64,
    64, 64, 63, 61, 59, 56, 53, 49, 45, 41, 36, 30, 24, 19, 12, 6,
    0, -6, -12, -19, -24, -30, -36, -41, -45, -49, -53, -56, -59, -61,
    -63, -64, -64, -64, -63, -61, -59, -56, -53, -49, -45, -41, -36,
    -30, -24, -19, -12, -6,
};

// Smoothstep 0..255 over the 72 growth ticks: a slow wind-up at the hero,
// a fast sweep through the middle of the room, then a settling crest.
static const u8 vortex_ease[PICSEAN_VORTEX_GROW_TICKS + 1] = {
    0, 0, 1, 1, 2, 4, 5, 7, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40, 44,
    48, 52, 57, 61, 66, 71, 76, 81, 86, 91, 96, 101, 106, 112, 117, 122,
    128, 133, 138, 143, 149, 154, 159, 164, 169, 174, 179, 184, 189, 194,
    198, 203, 207, 211, 215, 219, 223, 226, 230, 233, 236, 239, 242, 244,
    246, 248, 250, 251, 253, 254, 254, 255, 255,
};

// floor(n*n/4) for n = 0..304: a*b = qsq[a+b] - qsq[a-b] for a >= b.
// SDCC would otherwise call the 16-bit __mulint for every arm point.
static const u16 qsq[305] = {
    0, 0, 1, 2, 4, 6, 9, 12, 16, 20,
    25, 30, 36, 42, 49, 56, 64, 72, 81, 90,
    100, 110, 121, 132, 144, 156, 169, 182, 196, 210,
    225, 240, 256, 272, 289, 306, 324, 342, 361, 380,
    400, 420, 441, 462, 484, 506, 529, 552, 576, 600,
    625, 650, 676, 702, 729, 756, 784, 812, 841, 870,
    900, 930, 961, 992, 1024, 1056, 1089, 1122, 1156, 1190,
    1225, 1260, 1296, 1332, 1369, 1406, 1444, 1482, 1521, 1560,
    1600, 1640, 1681, 1722, 1764, 1806, 1849, 1892, 1936, 1980,
    2025, 2070, 2116, 2162, 2209, 2256, 2304, 2352, 2401, 2450,
    2500, 2550, 2601, 2652, 2704, 2756, 2809, 2862, 2916, 2970,
    3025, 3080, 3136, 3192, 3249, 3306, 3364, 3422, 3481, 3540,
    3600, 3660, 3721, 3782, 3844, 3906, 3969, 4032, 4096, 4160,
    4225, 4290, 4356, 4422, 4489, 4556, 4624, 4692, 4761, 4830,
    4900, 4970, 5041, 5112, 5184, 5256, 5329, 5402, 5476, 5550,
    5625, 5700, 5776, 5852, 5929, 6006, 6084, 6162, 6241, 6320,
    6400, 6480, 6561, 6642, 6724, 6806, 6889, 6972, 7056, 7140,
    7225, 7310, 7396, 7482, 7569, 7656, 7744, 7832, 7921, 8010,
    8100, 8190, 8281, 8372, 8464, 8556, 8649, 8742, 8836, 8930,
    9025, 9120, 9216, 9312, 9409, 9506, 9604, 9702, 9801, 9900,
    10000, 10100, 10201, 10302, 10404, 10506, 10609, 10712, 10816, 10920,
    11025, 11130, 11236, 11342, 11449, 11556, 11664, 11772, 11881, 11990,
    12100, 12210, 12321, 12432, 12544, 12656, 12769, 12882, 12996, 13110,
    13225, 13340, 13456, 13572, 13689, 13806, 13924, 14042, 14161, 14280,
    14400, 14520, 14641, 14762, 14884, 15006, 15129, 15252, 15376, 15500,
    15625, 15750, 15876, 16002, 16129, 16256, 16384, 16512, 16641, 16770,
    16900, 17030, 17161, 17292, 17424, 17556, 17689, 17822, 17956, 18090,
    18225, 18360, 18496, 18632, 18769, 18906, 19044, 19182, 19321, 19460,
    19600, 19740, 19881, 20022, 20164, 20306, 20449, 20592, 20736, 20880,
    21025, 21170, 21316, 21462, 21609, 21756, 21904, 22052, 22201, 22350,
    22500, 22650, 22801, 22952, 23104,
};

static u16 mul8(u8 a, u8 b) {
    if (a < b) { u8 t = a; a = b; b = t; }
    return (u16)(qsq[(u16)a + b] - qsq[(u8)(a - b)]);
}

// Arm points along each arm in sixteenths of the front radius. Even ticks
// draw 3/7/12, odd ticks 5/9/16, so 24 points flicker in 12 OBJ.
static const u8 seg_frac[6] = { 3, 5, 7, 9, 12, 16 };

// drop, curl, crest, eye (colour 1 deep blue, 2 aqua, 3 foam).
static const u8 vortex_tiles[64] = {
    0x00, 0x00, 0x3C, 0x00, 0x4E, 0x3C, 0x5A, 0x3C,
    0x42, 0x3C, 0x66, 0x18, 0x3C, 0x00, 0x00, 0x00,
    0x3C, 0x00, 0x42, 0x3C, 0xB9, 0x66, 0xB1, 0x62,
    0xA9, 0x72, 0x45, 0x22, 0x2A, 0x04, 0x0C, 0x00,
    0x0F, 0x00, 0x37, 0x0E, 0x4D, 0x3E, 0x9B, 0x7C,
    0x96, 0x78, 0x8C, 0x70, 0x98, 0x60, 0x70, 0x00,
    0x00, 0x3C, 0x3C, 0x42, 0x7E, 0xBD, 0x72, 0xA1,
    0x4E, 0x85, 0x7E, 0xBD, 0x3C, 0x42, 0x00, 0x3C,
};

static const u16 tide_obj_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555( 2,  7, 20),
    BGR555( 5, 22, 31),
    BGR555(27, 31, 31),
};
static const u16 crest_obj_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555( 6, 16, 31),
    BGR555(18, 30, 31),
    BGR555(31, 31, 31),
};
// BG floor/wall surge: the whole room goes under water for a few frames.
static const u16 tide_bg_floor[4] = {
    BGR555( 0,  3,  8), BGR555( 1,  8, 16),
    BGR555( 4, 16, 26), BGR555(14, 28, 31),
};
static const u16 tide_bg_wall[4] = {
    BGR555( 0,  1,  5), BGR555( 1,  5, 12),
    BGR555( 3, 11, 20), BGR555(10, 22, 29),
};

static u16 vdist(i16 dx, i16 dy) {
    u16 ax = (u16)(dx < 0 ? -dx : dx);
    u16 ay = (u16)(dy < 0 ? -dy : dy);
    if (ax < ay) { u16 t = ax; ax = ay; ay = t; }
    // Octagonal estimate of sqrt(ax^2 + ay^2), within about 7%.
    return (u16)(ax + (ay >> 2) + (ay >> 3));
}

// atan(k/16) in 64ths of a turn, k = 0..16 (one octant).
static const u8 vortex_atan[17] = { 0, 1, 1, 2, 2, 3, 4, 4, 5, 5, 6, 6, 7, 7, 7, 8, 8 };

// Bearing of (dx, dy) in 64ths with screen Y down (matches the arm layout).
// One 16-bit division; called once per body per cast.
static u8 vortex_bearing(i16 dx, i16 dy) {
    u16 ax = (u16)(dx < 0 ? -dx : dx);
    u16 ay = (u16)(dy < 0 ? -dy : dy);
    u8 a;
    if (!ax && !ay) return 0;
    if (ax >= ay) a = vortex_atan[(u8)((ay << 4) / ax)];
    else a = (u8)(16 - vortex_atan[(u8)((ax << 4) / ay)]);
    if (dx < 0) a = (u8)(32 - a);
    if (dy < 0) a = (u8)(64 - a);
    return (u8)(a & 63);
}

static u8 vortex_heavy(const entity_t *e, u8 j) {
    u8 eid = e->ai_data[0];
    if (e->flags & (EF_ELITE | EF_ALPHA | EF_RARE)) return 1;
    if (eid == ENEMY_STONE_SENTINEL || eid == ENEMY_STAGE_REAPER) return 1;
    if (e->ai_data[2] == ENEMY_AUX_BELLWARDEN) return 1;
    if (j == large_boss_index || hexa_boss_active) return 1;
    return 0;
}

static u8 carrier_ok(void) {
    entity_t *c;
    if (vortex_carrier == 0xFF) return 0;
    c = &entities[vortex_carrier];
    return (c->flags & (EF_ACTIVE | EF_PLAYER_PROJ)) == (EF_ACTIVE | EF_PLAYER_PROJ)
        && c->type == ENT_PROJECTILE && c->ai_data[6] == PROJ_AUX_VORTEX;
}

static void carrier_park(void) {
    entity_t *c = &entities[vortex_carrier];
    c->x = (ppos_t)(vortex_wx - 4);
    c->y = (ppos_t)(vortex_wy - 4);
    c->vx = c->vy = 0;
    c->hp = 200;
    c->state_timer = 60;
    c->hitbox = 0x88;
    // The eye spins at the cast point (projectile shimmer is undone).
    c->sprite_tile = SPR_FX_VORTEX_EYE;
    c->palette = 2;
    c->ai_data[4] = (u8)((picsean_vortex_ticks & 4)
        ? (PROJ_VIS_FLIP_X | PROJ_VIS_FLIP_Y) : 0);
}

// Any live carrier in the table (the tracked one may have been lost).
static u8 carrier_find(void) {
    u8 s;
    for (s = 0; s < MAX_ENTITIES; ++s) {
        vortex_carrier = s;
        if (carrier_ok()) return s;
    }
    vortex_carrier = 0xFF;
    return 0xFF;
}

static u8 carrier_ensure(void) {
    u8 s;
    entity_t *c;
    if (carrier_ok()) return 1;
    // Adopt a stray carrier instead of leaving it orphaned.
    if (carrier_find() != 0xFF) {
        carrier_park();
        return 1;
    }
    s = projectile_spawn_player(1, 0, vortex_damage, PROJ_BUBBLE);
    if (s == 0xFF) return 0;
    c = &entities[s];
    c->ai_data[2] = 0;
    // A single authored MAX: convergence-limited on a Colossus. No relic
    // ricochet/splash riders on the carrier.
    c->ai_data[3] = PROJ_FLAG_CONVERGENCE;
    c->ai_data[6] = PROJ_AUX_VORTEX;
    vortex_carrier = s;
    carrier_park();
    return 1;
}

static void vortex_hit(u8 j, u8 dmg, i16 dx, i16 dy) {
    entity_t *c = &entities[vortex_carrier];
    entity_t *ej = &entities[j];
    if (vortex_heavy(ej, j) && dmg > PICSEAN_VORTEX_HEAVY_CAP)
        dmg = PICSEAN_VORTEX_HEAVY_CAP;
    c->damage = dmg;
    c->hp = 200;
    // Impact FX are spawned at the carrier: put it on the body.
    c->x = ej->x;
    c->y = ej->y;
    // Knockback only reads the sign: survivors are flung outward.
    c->vx = (i8)(dx > 0 ? 1 : dx < 0 ? -1 : 0);
    c->vy = (i8)(dy > 0 ? 1 : dy < 0 ? -1 : 0);
    combat_apply_player_shot_hit(c, vortex_carrier, ej, j, &vortex_giant_hits);
    if (carrier_ok()) carrier_park();
    else vortex_carrier = 0xFF;
}

static void vortex_flash(u8 on, u8 crest) {
    if (hexa_boss_active) return;   // the sanctum owns its BG palettes
    if (on) {
        palette_bg_load(BGPAL_FLOOR, tide_bg_floor);
        palette_bg_load(BGPAL_WALL, tide_bg_wall);
        palette_obj_load(2, crest ? crest_obj_palette : tide_obj_palette);
        vortex_flashing = 1;
    } else if (vortex_flashing) {
        room_status_blind_visual(player_status_kind == QSTATUS_BLIND);
        palette_obj_load(2, tide_obj_palette);
        vortex_flashing = 0;
    }
}

static void vortex_hide_oam(void) {
    u8 k;
    for (k = PICSEAN_VORTEX_OAM_LO; k < PICSEAN_VORTEX_OAM_HI; ++k)
        move_sprite(k, 0, 0);
}

static void vortex_end(void) {
    if (carrier_ok()) entity_kill(vortex_carrier);
    while (carrier_find() != 0xFF) entity_kill(vortex_carrier);
    picsean_vortex_ticks = 0;
    picsean_vortex_radius = 0;
    picsean_vortex_abort = 0;
    seg_n = 0;
    vortex_flash(0, 0);
    vortex_flashing = 0;
    // Weapon and hero OBJ palettes come back from the champion appearance.
    room_refresh_player_appearance(0);
    vortex_hide_oam();
}

void picsean_vortex_begin(u8 damage) BANKED {
    u8 k;
    i16 cx = (i16)player.x + 8;
    i16 cy = (i16)player.y + 8;
    i16 ax, ay;
    u16 r;
    for (k = 0; k < (u8)sizeof(front_hit); ++k) front_hit[k] = arm_hit[k] = 0;
    for (k = 0; k < (u8)sizeof(seg_oam); k += 4) seg_oam[k] = 0;
    vortex_damage = damage;
    vortex_giant_hits = 0;
    picsean_vortex_abort = 0;
    // Reach the farthest corner of the visible room from the cast point.
    ax = cx - (i16)room_camera_x;
    if ((i16)room_camera_x + ROOM_VIEW_W_PX - cx > ax)
        ax = (i16)room_camera_x + ROOM_VIEW_W_PX - cx;
    ay = cy - (i16)room_camera_y;
    if ((i16)room_camera_y + ROOM_VIEW_H_PX - cy > ay)
        ay = (i16)room_camera_y + ROOM_VIEW_H_PX - cy;
    r = vdist(ax, ay) + 12;
    vortex_rmax = (u8)(r > PICSEAN_VORTEX_MAX_R ? PICSEAN_VORTEX_MAX_R : r);
    vortex_wx = cx;
    vortex_wy = cy;
    set_sprite_data(SPR_FX_VORTEX_DROP, 4, vortex_tiles);
    palette_obj_load(2, tide_obj_palette);
    picsean_vortex_ticks = PICSEAN_VORTEX_TICKS;
    picsean_vortex_radius = PICSEAN_VORTEX_START_R;
    seg_n = 0;
    // A recast while the last vortex runs keeps its carrier (no orphan).
    carrier_ensure();
    vortex_flash(1, 0);
    sfx_play_weapon(PROJ_BUBBLE);
}

// Screen-space clip helpers in 8-bit math (SDCC's 16-bit compares cost
// several times more). OAM X must be 1..167 and Y 9..147 (above the HUD).
#define VX_HI 168
#define VY_LO 9
#define VY_HI 148
#define ADD_CLIP(c, o, hi) ((u8)(o) < (u8)((hi) - (c)) ? (u8)((c) + (o)) : 0)
#define SUB_CLIP(c, o, lo) ((c) > (u8)(o) && (u8)((c) - (o)) >= (lo) \
    ? (u8)((c) - (o)) : 0)
static u8 clip_oam_x(i16 x) {
    return (x >= 1 && x < VX_HI) ? (u8)x : 0;
}
static u8 clip_oam_y(i16 y) {
    return (y >= VY_LO && y < VY_HI) ? (u8)y : 0;
}
#define SEG_PUT(o, X, Y, T, P) do { \
    u8 x_ = (X), y_ = (Y); \
    if (x_ && y_) { (o)[0] = y_; (o)[1] = x_; (o)[2] = (T); (o)[3] = (P); } \
    else (o)[0] = 0; \
} while (0)

static void vortex_layout(u8 t, u8 r) {
    u8 j;
    u8 *o = seg_oam;
    u8 phase = (u8)(t << 1);
    // Cels fatten as the vortex grows.
    u8 grow = (u8)(t >= 56 ? 2 : t >= 28 ? 1 : 0);
    // Cast-point centre in OAM space (OBJ origin is -8,-16; cels are 8x8).
    i16 ocx = vortex_wx + 4 - (i16)room_camera_x;
    i16 ocy = vortex_wy + 12 - (i16)room_camera_y;
    // Fast 8-bit path when the eye is on screen (fixed rooms, and the
    // start of a scrolling room). Off-screen origins still draw any arm
    // point that has scrolled into view.
    u8 on = (u8)(ocx >= 1 && ocx < VX_HI && ocy >= VY_LO && ocy < VY_HI);
    u8 cx = on ? (u8)ocx : 0;
    u8 cy = on ? (u8)ocy : 0;
    for (j = (u8)(t & 1); j < 6; j += 2) {
        u8 rho = (u8)(mul8(r, seg_frac[j]) >> 4);
        u8 cel = (u8)((j >> 1) + grow);
        // Twist grows with radius: each arm is a spiral, not a spoke.
        u8 th = (u8)((phase + (rho >> 2)) & 63);
        i8 cs = vortex_sin[(u8)((th + 16) & 63)];
        i8 sn = vortex_sin[th];
        u8 ax = (u8)(mul8(rho, (u8)(cs < 0 ? -cs : cs)) >> 6);
        u8 ay = (u8)(mul8(rho, (u8)(sn < 0 ? -sn : sn)) >> 6);
        // Signed offsets of arm 0: (ox, oy). Arms 1..3 are quarter turns:
        // (-oy, ox), (-ox, -oy), (oy, -ox).
        u8 x_pox, x_mox, x_poy, x_moy, y_pox, y_mox, y_poy, y_moy, tile;
        if (cel > 2) cel = 2;
        tile = (u8)(SPR_FX_VORTEX_DROP + cel);
        if (!on) {
            i16 ox = (i16)(cs < 0 ? -(i16)ax : ax);
            i16 oy = (i16)(sn < 0 ? -(i16)ay : ay);
            SEG_PUT(o,      clip_oam_x(ocx + ox), clip_oam_y(ocy + oy), tile, 2);
            SEG_PUT(o + 4,  clip_oam_x(ocx - oy), clip_oam_y(ocy + ox), tile, 2 | S_FLIPX);
            SEG_PUT(o + 8,  clip_oam_x(ocx - ox), clip_oam_y(ocy - oy), tile, 2 | S_FLIPX | S_FLIPY);
            SEG_PUT(o + 12, clip_oam_x(ocx + oy), clip_oam_y(ocy - ox), tile, 2 | S_FLIPY);
            o += 16;
            continue;
        }
        if (cs < 0) {   // ox = -ax
            x_pox = SUB_CLIP(cx, ax, 1);  x_mox = ADD_CLIP(cx, ax, VX_HI);
            y_pox = SUB_CLIP(cy, ax, VY_LO); y_mox = ADD_CLIP(cy, ax, VY_HI);
        } else {
            x_pox = ADD_CLIP(cx, ax, VX_HI); x_mox = SUB_CLIP(cx, ax, 1);
            y_pox = ADD_CLIP(cy, ax, VY_HI); y_mox = SUB_CLIP(cy, ax, VY_LO);
        }
        if (sn < 0) {   // oy = -ay
            x_poy = SUB_CLIP(cx, ay, 1);  x_moy = ADD_CLIP(cx, ay, VX_HI);
            y_poy = SUB_CLIP(cy, ay, VY_LO); y_moy = ADD_CLIP(cy, ay, VY_HI);
        } else {
            x_poy = ADD_CLIP(cx, ay, VX_HI); x_moy = SUB_CLIP(cx, ay, 1);
            y_poy = ADD_CLIP(cy, ay, VY_HI); y_moy = SUB_CLIP(cy, ay, VY_LO);
        }
        // Mirror bits alternate so the spiral reads as churning water.
        SEG_PUT(o,      x_pox, y_poy, tile, 2);
        SEG_PUT(o + 4,  x_moy, y_pox, tile, 2 | S_FLIPX);
        SEG_PUT(o + 8,  x_mox, y_moy, tile, 2 | S_FLIPX | S_FLIPY);
        SEG_PUT(o + 12, x_poy, y_mox, tile, 2 | S_FLIPY);
        o += 16;
    }
    seg_n = 12;
}

static const u8 slot_bit[8] = { 1, 2, 4, 8, 16, 32, 64, 128 };

void picsean_vortex_tick(void) BANKED {
    u8 t, i, r, wa;
    i16 cx, cy;
    entity_t *e;
    if (!picsean_vortex_ticks) return;
    if (picsean_vortex_abort || player.class_id != 3) {
        vortex_end();
        return;
    }
    t = (u8)(PICSEAN_VORTEX_TICKS - picsean_vortex_ticks);
    picsean_vortex_ticks--;
    if (t <= PICSEAN_VORTEX_GROW_TICKS)
        r = (u8)(PICSEAN_VORTEX_START_R + (u8)(((u16)(vortex_rmax
            - PICSEAN_VORTEX_START_R) * vortex_ease[t]) >> 8));
    else
        r = vortex_rmax;
    picsean_vortex_radius = r;
    vortex_layout(t, r);

    // Surges: the cast, the mid-sweep, and the crest.
    if (t == 6 || t == 38 || t == 78) vortex_flash(0, 0);
    else if (t == 34) {
        // Re-upload the cels at each surge: a Pack/map visit mid-cast may
        // have borrowed the shared 0x8800 tile block.
        set_sprite_data(SPR_FX_VORTEX_DROP, 4, vortex_tiles);
        vortex_flash(1, 0);
        sfx_play_weapon(PROJ_BUBBLE);
    } else if (t == PICSEAN_VORTEX_GROW_TICKS) {
        set_sprite_data(SPR_FX_VORTEX_DROP, 4, vortex_tiles);
        vortex_flash(1, 1);
        room_shake(3, 10);
        sfx_play(SFX_ROAR);
    }

    if (!carrier_ensure()) {
        // Full table: try again next tick; nothing is marked as hit.
        if (!picsean_vortex_ticks) vortex_end();
        return;
    }
    cx = vortex_wx;
    cy = vortex_wy;
    // Arm half-width in 64ths of a turn widens 4..6 as the vortex grows.
    // A body is visited every 4 ticks while the arms turn 8/64, so a
    // half-width of 4 can never skip over it.
    wa = (u8)(4 + (t >= 36) + (t >= 60));
    vortex_fx_budget = 2;
    // Each tick visits a quarter of the table (slot & 3 == tick & 3). The
    // front moves at most ~6px a tick, so a body is reached within four
    // ticks of the ring crossing it, at a quarter of the CPU.
    i = (u8)(t & 3);
    e = &entities[i];
    for (; i < MAX_ENTITIES; i += 4, e += 4) {
        i16 dx, dy;
        u8 bit, byte, flags = e->flags;
        if (!(flags & EF_ACTIVE) || i == vortex_carrier) continue;
        if (e->type == ENT_PROJECTILE) {
            if (flags & EF_PLAYER_PROJ) continue;
            // The Reaper's warned scythe keeps its own contract.
            if (e->ai_data[6] == PROJ_AUX_MORTAL_SCYTHE) continue;
            if (vdist((i16)(e->x + 3) - cx, (i16)(e->y + 3) - cy) > r)
                continue;
            if (vortex_fx_budget) {
                vortex_fx_budget--;
                fx_spawn(SPR_FX_IMPACT, 2, (i16)e->x, (i16)e->y, 6);
            }
            entity_kill(i);
            continue;
        }
        if (e->type != ENT_ENEMY || !(flags & EF_ON_SCREEN)) continue;
        bit = slot_bit[i & 7];
        byte = (u8)(i >> 3);
        if (arm_hit[byte] & bit) continue;
        dx = (i16)(e->x + (i16)(e->hitbox >> 5)) - cx;
        dy = (i16)(e->y + (i16)((e->hitbox & 0x0F) >> 1)) - cy;
        if (!(front_hit[byte] & bit)) {
            u16 d = vdist(dx, dy);
            if (d > r) continue;
            front_hit[byte] |= bit;
            body_phi[i] = vortex_bearing(dx, dy);
            body_d[i] = (u8)(d > 255 ? 255 : d);
            vortex_hit(i, (u8)(vortex_damage + PICSEAN_VORTEX_FRONT_BONUS),
                dx, dy);
            if (vortex_carrier == 0xFF) break;
            continue;
        }
        {
            // The arm through this body's distance sits at the layout's
            // spiral angle; the four arms repeat every quarter (16).
            u8 diff = (u8)((body_phi[i] - (u8)(t << 1)
                - (u8)(body_d[i] >> 2)) & 15);
            if (diff > wa && diff < (u8)(16 - wa)) continue;
        }
        arm_hit[byte] |= bit;
        vortex_hit(i, (u8)(vortex_damage + PICSEAN_VORTEX_ARM_BONUS), dx, dy);
        if (vortex_carrier == 0xFF) break;
    }
    if (!picsean_vortex_ticks) vortex_end();
}

void picsean_vortex_draw(void) BANKED {
    // Big bodies own the OAM tail (Serpent 4..31, Cinder Rex 16..39): the
    // vortex keeps only its last four segments there rather than tearing
    // twelve pieces out of the champion.
    u8 oam = (serpent_tail_active
              || (cinder_pack_active && cinder_oam_limit < 40))
        ? 32 : PICSEAN_VORTEX_OAM_LO;
    u8 *dst = (u8 *)&shadow_OAM[oam];
    u8 k = (u8)(PICSEAN_VORTEX_OAM_HI - oam);
    // Last eight ticks: blink out.
    if (picsean_vortex_ticks < 8 && (picsean_vortex_ticks & 1)) {
        do { *dst = 0; dst += 4; } while (--k);
        return;
    }
    memcpy(dst, seg_oam, (u8)(k << 2));
}

// room_draw tail: OBJ overlays drawn after the entity pass and the champion.
// Lives here rather than in room.c so bank 1 stays above its 256-byte floor.
void room_draw_overlays(void) BANKED {
    if (serpent_tail_active) serpent_draw();
    if (cinder_pack_active) cinder_draw();
    if (picsean_vortex_ticks) picsean_vortex_draw();
}
