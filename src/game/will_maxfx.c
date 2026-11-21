#pragma bank 30

#include <gb/gb.h>
#include <string.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/hexa_boss.h"
#include "game/rare_enemy.h"
#include "game/loop.h"
#include "game/picsean_vortex.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/status.h"
#include "game/will.h"
#include "game/will_maxfx.h"
#include "render/large_boss.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

// Max-Will v2 controller. Spec: docs/superpowers/specs/2026-11-17-max-will-v2.md
//
// Sauran   Thunderline Bastion + Aftershock: spear, two pylons, slam,
//          then a lateral T-fault (PR aftershock / spec 2026-11-21).
// Vespine  Royal Stinger: lodging poison stinger, pincers, Venom Sac rupture.
// Corvin   Murderstorm Eclipse: Night Veil, Shadow Effigy, four
//          scythe-feathers that fan out, glint, then snap onto the Mark.
// Wolfkin  Moonfang Cross-Rend: beat two of Moonfang Rush (beat one is
//          wolfkin_wave.c): claw scars, then the crescent shears at f34.

u8 combat_apply_player_shot_hit(entity_t *shot, u8 i, entity_t *ej,
                                u8 j, u8 *giant_hits) BANKED;

u8 will_maxfx_live;
u8 will_maxfx_t;
u8 will_maxfx_dir;            // aim of the live art (dir8), for tests

static u8 fx_carrier = 0xFF;
static u8 fx_damage;
static u8 fx_giant_hits;
static u8 fx_reach;
static u8 fx_washed;
static u8 fx_anchor;
static u8 fx_stop;           // Sauran: spear stopped / Vespine: planted
static u8 fx_pyl;            // Sauran: bit0 pylon A placed, bit1 pylon B
static u8 fx_ctile, fx_cflip;
static i8 fx_dx, fx_dy;      // aim (dir8 unit)
static i16 fx_cx, fx_cy;     // cast centre, world px (always floor)
static i16 fx_px, fx_py;     // spear tip / stinger / apex / blade target
static i16 fx_ax, fx_ay;     // Sauran pylon A
static i16 fx_bx, fx_by;     // Sauran pylon B
static i16 fx_kx, fx_ky;     // carrier park point (floor)
static u8 hit_a[(MAX_ENTITIES + 7) / 8];
static u8 hit_b[(MAX_ENTITIES + 7) / 8];
static u8 fx_oam[WILL_MAXFX_OAM_N * 4];
static const i8 sauran_ashock_off4[4] = { -40, -16, 16, 40 };
/* Diagonal steps are ~0.7x so the wall stays ~40 px Euclidean (40/sqrt(2)). */
static const i8 sauran_ashock_off4d[4] = { -28, -12, 12, 28 };


#define FX_T(n) ((u8)(WILL_MAXFX_TILE + (n)))
static const u8 slot_bit[8] = { 1, 2, 4, 8, 16, 32, 64, 128 };
#define MASK_HAS(m, i) ((m)[(u8)((i) >> 3)] & slot_bit[(i) & 7])
#define MASK_SET(m, i) ((m)[(u8)((i) >> 3)] |= slot_bit[(i) & 7])

static const u8 fx_tiles_sauran[64] = {
    0x00, 0x00, 0x20, 0x00, 0x52, 0x20, 0xA5, 0x72,
    0x8A, 0x57, 0x49, 0x06, 0x04, 0x00, 0x00, 0x00,
    0x24, 0x00, 0x76, 0x24, 0x3C, 0x3C, 0xFE, 0x7F,
    0x3C, 0x7E, 0x3C, 0x3C, 0x6E, 0x24, 0x24, 0x00,
    0x18, 0x00, 0x34, 0x18, 0x34, 0x18, 0x4A, 0x3C,
    0x52, 0x3C, 0x4A, 0x3C, 0xD3, 0x3C, 0xA5, 0x7E,
    0x91, 0x7E, 0x89, 0x7E, 0x91, 0x3C, 0x91, 0x7A,
    0x89, 0x5E, 0x89, 0x7C, 0xFF, 0x00, 0x5A, 0x00,
};
static const u8 fx_tiles_sauran_crack[32] = {
    0x10, 0x00, 0x34, 0x10, 0x2A, 0x0C, 0x4A, 0x28,
    0x4A, 0x18, 0x42, 0x24, 0x93, 0x30, 0x85, 0x54,
    0x89, 0x28, 0x89, 0x4A, 0x89, 0x18, 0x81, 0x24,
    0x91, 0x52, 0x09, 0x48, 0xD7, 0x00, 0x52, 0x00,
};
// L4 aftershock cels (vertical bolt, horizontal crack). Quantized from
// GPT Image 2 (gpt-image-2.6-sunburst) onto pal_sauran; magenta is color 0.
static const u8 fx_tiles_sauran_aftershock[32] = {
    /* GPT Image 2 (gpt-image-2.6-sunburst), pal_sauran, magenta=0.
       Vertical bolt + rot90 horizontal crack; gold-core extract. */
    0x5C, 0x28, 0x3A, 0x14, 0x5E, 0x28, 0x2D, 0x1E,
    0x5D, 0x2A, 0x5A, 0x34, 0x5C, 0x28, 0x38, 0x10,
    0x75, 0x00, 0x8A, 0x75, 0xF7, 0xAA, 0xFF, 0x5D,
    0x5D, 0x2A, 0x26, 0x18, 0x18, 0x00, 0x00, 0x00,
};
static const u8 fx_tiles_vespine[64] = {
    0x00, 0x00, 0x80, 0x00, 0xA0, 0x40, 0x8E, 0x7C,
    0x8E, 0x7E, 0xA0, 0x40, 0x80, 0x00, 0x00, 0x00,
    0x38, 0x00, 0x48, 0x30, 0x88, 0x50, 0x94, 0x08,
    0x09, 0x06, 0x07, 0x02, 0x02, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x18, 0x00, 0x2C, 0x18, 0x4A, 0x3C,
    0x42, 0x3C, 0x24, 0x18, 0x18, 0x00, 0x00, 0x00,
    0x3C, 0x00, 0x5A, 0x3C, 0xA5, 0x7E, 0xC3, 0x7E,
    0x91, 0x7E, 0x85, 0x7E, 0x5A, 0x3C, 0x3C, 0x00,
};
static const u8 fx_tiles_corvin[64] = {
    0x03, 0x00, 0x09, 0x06, 0x11, 0x0E, 0x22, 0x1C,
    0x44, 0x38, 0x80, 0x70, 0xA0, 0x40, 0x80, 0x00,
    0x03, 0x01, 0x0B, 0x07, 0x17, 0x0E, 0x3A, 0x1C,
    0x74, 0x38, 0xE0, 0x70, 0xE0, 0x40, 0x80, 0x80,
    0x3C, 0x00, 0x42, 0x3C, 0x7E, 0x24, 0x42, 0x3C,
    0xC3, 0x3C, 0xA5, 0x18, 0x24, 0x18, 0x66, 0x00,
    0x3C, 0x00, 0x42, 0x3C, 0x7E, 0x3C, 0x42, 0x3C,
    0x42, 0x3C, 0xC3, 0x18, 0x24, 0x18, 0x24, 0x00,
};
static const u8 fx_tiles_wolfkin[64] = {
    0xC0, 0x00, 0x80, 0x60, 0x48, 0x30, 0x24, 0x18,
    0x12, 0x0C, 0x09, 0x06, 0x05, 0x02, 0x03, 0x00,
    0xC0, 0x40, 0xE0, 0xE0, 0x70, 0x78, 0x38, 0x3C,
    0x1C, 0x1E, 0x0E, 0x0F, 0x05, 0x07, 0x03, 0x03,
    0xC0, 0xC0, 0xF0, 0xE0, 0x74, 0x78, 0x7A, 0x3C,
    0x3C, 0x1E, 0x0E, 0x1E, 0x07, 0x0E, 0x07, 0x04,
    0x90, 0x81, 0x02, 0x20, 0x48, 0x08, 0x02, 0x80,
    0x01, 0x11, 0x44, 0x40, 0x80, 0x08, 0x21, 0x20,
};

// OBJ palette 2 per art (0 transparent, 1 dark, 2 mid, 3 bright).
static const u16 pal_sauran[4] = {
    BGR555(0, 0, 0), BGR555(10, 5, 1), BGR555(28, 18, 4), BGR555(31, 30, 18),
};
static const u16 pal_vespine[4] = {
    BGR555(0, 0, 0), BGR555(8, 1, 10), BGR555(28, 6, 22), BGR555(22, 31, 6),
};
static const u16 pal_corvin[4] = {
    BGR555(0, 0, 0), BGR555(3, 1, 8), BGR555(14, 7, 26), BGR555(29, 28, 31),
};
static const u16 pal_wolfkin[4] = {
    BGR555(0, 0, 0), BGR555(9, 5, 14), BGR555(24, 8, 31), BGR555(31, 23, 31),
};
static const u16 pal_white[4] = {
    BGR555(0, 0, 0), BGR555(18, 16, 28), BGR555(28, 26, 31), BGR555(31, 31, 31),
};
// BG washes: floor then wall, four colours each.
static const u16 wash_ochre[8] = {
    BGR555(4, 2, 0), BGR555(12, 7, 1), BGR555(22, 14, 3), BGR555(30, 24, 10),
    BGR555(2, 1, 0), BGR555(8, 4, 0), BGR555(16, 9, 2), BGR555(26, 18, 6),
};
static const u16 wash_venom[8] = {
    BGR555(2, 5, 0), BGR555(8, 14, 1), BGR555(16, 24, 4), BGR555(26, 31, 12),
    BGR555(1, 3, 0), BGR555(5, 9, 1), BGR555(11, 17, 3), BGR555(20, 26, 8),
};
static const u16 wash_magenta[8] = {
    BGR555(6, 0, 5), BGR555(14, 2, 12), BGR555(24, 6, 20), BGR555(31, 18, 28),
    BGR555(3, 0, 3), BGR555(9, 1, 8), BGR555(17, 4, 14), BGR555(26, 12, 22),
};
static const u16 wash_night[8] = {
    BGR555(1, 1, 4), BGR555(3, 3, 9), BGR555(6, 6, 15), BGR555(12, 12, 22),
    BGR555(0, 0, 3), BGR555(2, 2, 7), BGR555(4, 4, 11), BGR555(9, 9, 18),
};
static const u16 wash_eclipse[8] = {
    BGR555(10, 6, 18), BGR555(18, 12, 26), BGR555(26, 22, 31), BGR555(31, 31, 31),
    BGR555(6, 3, 12), BGR555(13, 8, 21), BGR555(21, 17, 28), BGR555(29, 28, 31),
};
static const u16 wash_moon[8] = {
    BGR555(3, 2, 6), BGR555(9, 7, 14), BGR555(18, 16, 24), BGR555(28, 28, 31),
    BGR555(2, 1, 4), BGR555(6, 4, 10), BGR555(13, 11, 19), BGR555(22, 21, 27),
};

static void wash(const u16 *w) {
    // The sanctum owns its BG palettes; Blind keeps its blackout.
    if (hexa_boss_active || player_status_kind == QSTATUS_BLIND) return;
    palette_bg_load(BGPAL_FLOOR, w);
    palette_bg_load(BGPAL_WALL, w + 4);
    fx_washed = 1;
}

static void unwash(void) {
    if (!fx_washed) return;
    room_status_blind_visual(player_status_kind == QSTATUS_BLIND);
    fx_washed = 0;
}

// ---- sound: direct voices, no SFX_ROAR ------------------------------------
static void fx_ch1(u8 nr10, u8 nr11, u8 nr12, u16 freq, u8 frames) {
    if (sfx_melody_locked()) return;
    sfx_will_active = 0;
    sfx_claim_channels(frames, 0);
    NR10_REG = nr10;
    NR11_REG = nr11;
    NR12_REG = nr12;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

static void fx_ch4(u8 nr42, u8 nr43, u8 frames) {
    if (sfx_melody_locked()) return;
    sfx_claim_channels(0, frames);
    NR41_REG = 0;
    NR42_REG = nr42;
    NR43_REG = nr43;
    NR44_REG = 0x80;
}

// Sauran: square drop plus gravel. Three steps fall in pitch.
static void sfx_thud(u16 freq) {
    fx_ch1(0x1B, 0x80, 0xF1, freq, 14);
    fx_ch4(0xA2, 0x66, 12);
}

void will_maxfx_surf(u8 step) BANKED {
    // Picsean's crest: a filtered surf crash (about 28 frames of decay) under
    // a quick three-note bubbling run. Damage and timing are untouched.
    if (!step) fx_ch4(0xF2, 0x57, 30);
    fx_ch1(0x00, 0x40, (u8)(0x82 - (step << 3) - (step << 1)),
        (u16)(1750 + (u16)step * 17), 4);
}

// ---- shared helpers --------------------------------------------------------
u8 will_maxfx_locked(void) BANKED {
    return picsean_vortex_slow_charge
        && (u16)(loop_frame_counter - picsean_vortex_ready_at) >= 0x8000;
}

void will_maxfx_arm_lock(void) BANKED {
    picsean_vortex_slow_charge = 1;
    picsean_vortex_ready_at = (u16)(loop_frame_counter
        + PICSEAN_VORTEX_RECAST_FRAMES);
}

static u16 vdist(i16 dx, i16 dy) {
    u16 ax = (u16)(dx < 0 ? -dx : dx);
    u16 ay = (u16)(dy < 0 ? -dy : dy);
    if (ax < ay) { u16 t = ax; ax = ay; ay = t; }
    return (u16)(ax + (ay >> 2) + (ay >> 3));
}

static u8 fx_floor(i16 x, i16 y) {
    u8 t;
    if (x < 8 || y < 8 || x > (i16)room_world_width - 8
        || y > (i16)room_world_height - 8) return 0;
    t = room_tile_at_px(x, y);
    return t <= BGT_FLOOR3 && t != BGT_WALL;
}

static u8 fx_heavy(const entity_t *e, u8 j) {
    u8 eid = e->ai_data[0];
    if (e->flags & (EF_ELITE | EF_ALPHA | EF_RARE)) return 1;
    if (eid == ENEMY_STONE_SENTINEL || eid == ENEMY_STAGE_REAPER) return 1;
    if (e->ai_data[2] == ENEMY_AUX_BELLWARDEN) return 1;
    if (j == large_boss_index || hexa_boss_active) return 1;
    return 0;
}

static u8 carrier_ok(void) {
    entity_t *c;
    if (fx_carrier == 0xFF) return 0;
    c = &entities[fx_carrier];
    return (c->flags & (EF_ACTIVE | EF_PLAYER_PROJ)) == (EF_ACTIVE | EF_PLAYER_PROJ)
        && c->type == ENT_PROJECTILE && c->ai_data[6] == PROJ_AUX_VORTEX;
}

static void carrier_park(void) {
    entity_t *c = &entities[fx_carrier];
    c->x = (ppos_t)(fx_kx - 4);
    c->y = (ppos_t)(fx_ky - 4);
    c->vx = c->vy = 0;
    c->hp = 200;
    c->state_timer = 60;
    c->hitbox = 0x88;
    c->sprite_tile = fx_ctile;
    c->palette = 2;
    c->ai_data[4] = fx_cflip;
}

static u8 carrier_ensure(void) {
    u8 s;
    entity_t *c;
    if (carrier_ok()) return 1;
    s = projectile_spawn_player(1, 0, fx_damage, PROJ_BUBBLE);
    if (s == 0xFF) { fx_carrier = 0xFF; return 0; }
    c = &entities[s];
    c->ai_data[2] = 0;
    c->ai_data[3] = PROJ_FLAG_CONVERGENCE;
    c->ai_data[6] = PROJ_AUX_VORTEX;
    fx_carrier = s;
    carrier_park();
    return 1;
}

static void fx_hit(u8 j, u8 dmg) {
    entity_t *c;
    entity_t *ej = &entities[j];
    i16 dx, dy;
    if (!carrier_ensure()) return;
    c = &entities[fx_carrier];
    if (fx_heavy(ej, j) && dmg > WILL_MAXFX_HEAVY_CAP)
        dmg = WILL_MAXFX_HEAVY_CAP;
    dx = (i16)(ej->x - fx_cx);
    dy = (i16)(ej->y - fx_cy);
    c->damage = dmg;
    c->hp = 200;
    c->x = ej->x;
    c->y = ej->y;
    c->vx = (i8)(dx > 0 ? 1 : dx < 0 ? -1 : 0);
    c->vy = (i8)(dy > 0 ? 1 : dy < 0 ? -1 : 0);
    combat_apply_player_shot_hit(c, fx_carrier, ej, j, &fx_giant_hits);
    if (carrier_ok()) carrier_park();
    else fx_carrier = 0xFF;
}

#define BODY_X(e) ((i16)((e)->x + (i16)((e)->hitbox >> 5)))
#define BODY_Y(e) ((i16)((e)->y + (i16)(((e)->hitbox & 0x0F) >> 1)))

static u8 is_body(const entity_t *e) {
    return (e->flags & (EF_ACTIVE | EF_ON_SCREEN)) == (EF_ACTIVE | EF_ON_SCREEN)
        && e->type == ENT_ENEMY;
}

// Hit every on-screen body within r of (x, y) once per mask. Returns the
// first slot hit (0xFF when none).
static u8 hit_ring(i16 x, i16 y, u8 r, u8 *mask, u8 dmg) {
    u8 i, first = 0xFF;
    entity_t *e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        if (!is_body(e) || MASK_HAS(mask, i)) continue;
        if (vdist(BODY_X(e) - x, BODY_Y(e) - y) > r) continue;
        MASK_SET(mask, i);
        if (first == 0xFF) first = i;
        fx_hit(i, dmg);
        if (fx_carrier == 0xFF) break;
    }
    return first;
}

// Wash out hostile shots within r of (x, y); front limits it to the aim
// half-plane from the hero. The Reaper's warned scythe keeps its contract.
static void eat_shots(i16 x, i16 y, u8 r, u8 front) {
    u8 i, budget = 2;
    entity_t *e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        i16 ex, ey;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
            || (e->flags & EF_PLAYER_PROJ)
            || e->ai_data[6] == PROJ_AUX_MORTAL_SCYTHE) continue;
        ex = (i16)(e->x + 3);
        ey = (i16)(e->y + 3);
        if (vdist(ex - x, ey - y) > r) continue;
        if (front && (i16)((ex - x) * fx_dx + (ey - y) * fx_dy) < 0) continue;
        if (budget) {
            budget--;
            fx_spawn(SPR_FX_IMPACT, 2, (i16)e->x, (i16)e->y, 6);
        }
        entity_kill(i);
    }
}

// Screen-space OAM entry for a sprite centred on world (x, y).
static void put(u8 k, i16 x, i16 y, u8 tile, u8 prop) {
    u8 *o;
    if (k >= WILL_MAXFX_OAM_N) return;
    o = &fx_oam[(u8)(k << 2)];
    i16 sx = (i16)(x - (i16)room_camera_x + 4);
    i16 sy = (i16)(y - (i16)room_camera_y + 12);
    if (sx < 1 || sx > 167 || sy < 9 || sy > 147) { o[0] = 0; return; }
    o[0] = (u8)sy;
    o[1] = (u8)sx;
    o[2] = tile;
    o[3] = (u8)(prop | 2);
}

static void hide_all(void) {
    u8 k;
    for (k = 0; k < WILL_MAXFX_OAM_N; ++k) fx_oam[(u8)(k << 2)] = 0;
}

/* Recomputed each aftershock frame from the placed pylons (no BSS). */
static void sauran_mid(i16 *mx, i16 *my) {
    if ((fx_pyl & 3) == 3) {
        *mx = (i16)((fx_ax + fx_bx) >> 1);
        *my = (i16)((fx_ay + fx_by) >> 1);
    } else if (fx_pyl & 1) {
        *mx = fx_ax; *my = fx_ay;
    } else {
        *mx = fx_bx; *my = fx_by;
    }
}

static void fx_end(void) {
    if (carrier_ok()) entity_kill(fx_carrier);
    fx_carrier = 0xFF;
    unwash();
    hide_all();
    will_maxfx_draw();
    will_maxfx_live = 0;
    picsean_vortex_ticks = 0;
    picsean_vortex_abort = 0;
    // Weapon and hero OBJ palettes come back from the champion appearance.
    room_refresh_player_appearance(0);
}

// ---- Sauran: Thunderline Bastion -------------------------------------------
static void sauran_tick(u8 t) {
    u8 k;
    if (!fx_stop && t <= 12) {
        // The fault spear rides out about 12px a tick and stops at a wall.
        u8 step = (fx_dx && fx_dy) ? 9 : 12;
        i16 nx = (i16)(fx_px + fx_dx * (i8)step);
        i16 ny = (i16)(fx_py + fx_dy * (i8)step);
        hit_ring(fx_px, fx_py, (u8)(12 + fx_reach), hit_a,
            (u8)(fx_damage + 4));
        if (!(t & 1))
            fx_spawn(WILL_MAXFX_TILE, 2, (i16)(fx_px - 4), (i16)(fx_py - 4),
                (u8)(44 - t));
        if (!fx_floor(nx, ny) || t == 12) fx_stop = 1;
        else { fx_px = nx; fx_py = ny; }
    }
    if (t == 6 && fx_floor(fx_ax, fx_ay)) { fx_pyl |= 1; sfx_thud(1060); }
    if (t == 14 && fx_floor(fx_bx, fx_by)) { fx_pyl |= 2; sfx_thud(960); }
    if (t == 10) unwash();
    if (t == 44) {
        // Crack and slam: one tremor hit around each standing pylon.
        set_sprite_data(FX_T(2), 2, fx_tiles_sauran_crack);
        wash(wash_ochre);
        room_shake(3, 8);
        fx_ch1(0x2F, 0x80, 0xF2, 900, 20);
        fx_ch4(0xF4, 0x77, 24);
        if (fx_pyl & 1)
            hit_ring(fx_ax, fx_ay, (u8)(24 + fx_reach), hit_b,
                (u8)(fx_damage + 2));
        if (fx_pyl & 2)
            hit_ring(fx_bx, fx_by, (u8)(24 + fx_reach), hit_b,
                (u8)(fx_damage + 2));
    }
    if (t == 43) palette_obj_load(2, pal_white);
    if (t == 44) {
        if (fx_pyl & 1)
            fx_spawn(SPR_FX_IMPACT, 2, (i16)(fx_ax - 4), (i16)(fx_ay - 4), 10);
        if (fx_pyl & 2)
            fx_spawn(SPR_FX_IMPACT, 2, (i16)(fx_bx - 4), (i16)(fx_by - 4), 10);
    }
    if (t == 46) palette_obj_load(2, pal_sauran);
    if (t == 48) unwash();
    if (t == 48) {
        // Lateral T-fault: one AABB 16 px deep around the pylon mid,
        // +/-40 px off-axis (dot-space spans grow on diagonals so the
        // Euclidean size stays honest). Hits bodies the slam missed.
        // Aftershock itself does not eat shots.
        u8 i, diag;
        entity_t *e;
        i16 span, wide;
        if (fx_pyl & 3) {
            i16 mx, my;
            sauran_mid(&mx, &my);
            diag = (fx_dx && fx_dy) ? 1 : 0;
            /* 8 px along-aim each way (~11 in diagonal dot space);
               40 px off-axis (~56 in diagonal dot space = 28*2).
               Pad +8 so a 0x77 body at a sprite end still counts;
               56 on the nose missed SE fixtures in the headless test. */
            span = diag ? 16 : 8;
            wide = diag ? 64 : 40;
            room_shake(2, 6);
            fx_ch1(0x1F, 0x80, 0xE3, 1100, 12);
            fx_ch4(0xC3, 0x55, 16);
            set_sprite_data(FX_T(2), 2, fx_tiles_sauran_aftershock);
            for (i = 0, e = entities; i < MAX_ENTITIES; ++i, ++e) {
                i16 ad, cd, bx, by;
                if (!is_body(e) || MASK_HAS(hit_b, i)) continue;
                bx = BODY_X(e);
                by = BODY_Y(e);
                /* Measure from the pylon mid so a single surviving pylon
                   keeps the hitbox on the visual wall (offset +/-10). */
                ad = (i16)((bx - mx) * (i16)fx_dx
                    + (by - my) * (i16)fx_dy);
                cd = (i16)((bx - mx) * (i16)(-fx_dy)
                    + (by - my) * (i16)fx_dx);
                if (ad < (i16)-span || ad > span) continue;
                if (cd < 0) cd = (i16)-cd;
                if (cd > wide) continue;
                MASK_SET(hit_b, i);
                fx_hit(i, (u8)(fx_damage + 1));
                if (fx_carrier == 0xFF) break;
            }
        }
    }
    // Standing pylons are a gate: they eat hostile shots and stall rushers
    // until they finish sinking (spec: keep eating through the aftershock).
    if (t < 56 && (t & 1)) {
        for (k = 0; k < 2; ++k) {
            i16 x = k ? fx_bx : fx_ax, y = k ? fx_by : fx_ay;
            u8 i;
            entity_t *e = entities;
            if (!(fx_pyl & (u8)(1 << k))) continue;
            eat_shots(x, y, 10, 0);
            for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
                i16 dx, dy;
                if (!is_body(e) || i == large_boss_index) continue;
                dx = BODY_X(e) - x;
                dy = BODY_Y(e) - y;
                if (vdist(dx, dy) > 11) continue;
                enemy_try_step(e, (i8)(dx > 0 ? 1 : dx < 0 ? -1 : 0),
                    (i8)(dy > 0 ? 1 : dy < 0 ? -1 : 0));
            }
        }
    }
    // Draw: spear head (gone by t13), then pylon A in OAM 1/2 and pylon B
    // in 3/0. Pylons rise over 4 ticks and sink after the slam.
    hide_all();
    if (!fx_stop) put(0, fx_px, fx_py, FX_T(1),
        (t & 2) ? S_FLIPX : 0);
    for (k = 0; k < 2; ++k) {
        u8 born = k ? 14 : 6, off;
        i16 x = k ? fx_bx : fx_ax, y = k ? fx_by : fx_ay;
        if (!(fx_pyl & (u8)(1 << k)) || t < born) continue;
        if (t < (u8)(born + 4)) off = (u8)((born + 4 - t) << 1);
        else if (t >= 44) off = (u8)(t - 44);
        else off = 0;
        if (t >= 48) continue;
        if (t >= 46 && (t & 1)) continue;
        put((u8)(k ? 3 : 1), x, (i16)(y - 8 + off), FX_T(2), 0);
        put((u8)(k ? 0 : 2), x, (i16)(y + off), FX_T(3), 0);
    }
    if (t >= 48 && t < WILL_MAXFX_SAURAN_TICKS && (fx_pyl & 3)) {
        // Cosmetic T-fault wall in the 32..35 tail (pylons already hidden).
        // Hits were resolved at t==48 from the AABB.
        const i8 *off;
        u8 s;
        i16 mx, my;
        i8 qx = (i8)-fx_dy, qy = fx_dx;
        u8 vert = (fx_dx != 0 && fx_dy == 0) ? 1 : 0;
        u8 diag = (fx_dx && fx_dy) ? 1 : 0;
        sauran_mid(&mx, &my);
        off = diag ? sauran_ashock_off4d : sauran_ashock_off4;
        for (s = 0; s < 4; ++s) {
            u8 tile = (u8)(FX_T(2) + (vert ? 0 : 1));
            u8 prop = 0;
            i16 x = (i16)(mx + (i16)qx * off[s]);
            i16 y = (i16)(my + (i16)qy * off[s]);
            if ((t + s) & 1) prop = vert ? S_FLIPY : S_FLIPX;
            put(s, x, y, tile, prop);
        }
    }
}

// ---- Vespine: Royal Stinger and Venom Sac -----------------------------------
static void vespine_tick(u8 t) {
    u8 k;
    if (t <= 6) eat_shots((i16)player.x + 8, (i16)player.y + 8, 18, 1);
    if (!fx_stop) {
        // The stinger flies about 6px a tick and lodges in the first body.
        u8 j = hit_ring(fx_px, fx_py, 9, hit_a, (u8)(fx_damage + 4));
        if (j != 0xFF) {
            if (entities[j].flags & EF_ACTIVE) {
                status_enemy_apply(j, QSTATUS_POISON, 60);
                fx_anchor = j;
            }
            fx_stop = 1;
        } else {
            u8 step = (fx_dx && fx_dy) ? 4 : 6;
            i16 nx = (i16)(fx_px + fx_dx * (i8)step);
            i16 ny = (i16)(fx_py + fx_dy * (i8)step);
            if (t >= 8 || !fx_floor(nx, ny)) fx_stop = 1;
            else { fx_px = nx; fx_py = ny; }
        }
        if (fx_stop) {
            // Pincers snap shut on the stinger: a nip on its neighbours.
            hit_ring(fx_px, fx_py, 14, hit_a, fx_damage);
            fx_spawn(SPR_FX_IMPACT, 2, (i16)(fx_px - 4), (i16)(fx_py - 4), 8);
            fx_ch4(0x81, 0x22, 6);
        }
    } else if (fx_anchor != 0xFF) {
        entity_t *e = &entities[fx_anchor];
        // The sac rides its host until the host dies.
        if (is_body(e)) { fx_px = BODY_X(e); fx_py = BODY_Y(e); }
        else fx_anchor = 0xFF;
    }
    if (t == 6) unwash();
    if (t == 45) {
        // Rupture: acid burst, washes shots, feeds an active Swarm.
        wash(wash_magenta);
        hit_ring(fx_px, fx_py, fx_reach, hit_b, (u8)(fx_damage + 4));
        eat_shots(fx_px, fx_py, fx_reach, 0);
        if (will_vespine_swarm_ticks)
            will_vespine_swarm_ticks = (will_vespine_swarm_ticks > 210)
                ? 255 : (u8)(will_vespine_swarm_ticks + 45);
        room_shake(2, 6);
        fx_ch1(0x15, 0x80, 0xC1, 1500, 6);
        fx_ch4(0x67, 0x11, 30);
    }
    if (t == 49) unwash();
    // The carrier is the stinger, then the throbbing sac (faster near the
    // rupture), parked on floor at the sac.
    if (fx_floor(fx_px, fx_py)) { fx_kx = fx_px; fx_ky = fx_py; }
    if (!fx_stop) {
        fx_ctile = WILL_MAXFX_TILE;
        fx_cflip = (u8)((fx_dx < 0 ? PROJ_VIS_FLIP_X : 0)
            | (fx_dy < 0 && !fx_dx ? PROJ_VIS_FLIP_Y : 0));
    } else if (t < 45) {
        k = (t < 30) ? 8 : (t < 40) ? 4 : 2;
        fx_ctile = (u8)(WILL_MAXFX_TILE + ((t & k) ? 3 : 2));
        fx_cflip = 0;
    } else {
        fx_ctile = FX_T(3);
        fx_cflip = (t & 2) ? (PROJ_VIS_FLIP_X | PROJ_VIS_FLIP_Y) : 0;
    }
    if (carrier_ok()) carrier_park();
    hide_all();
    if (t <= 8) {
        // Two pincers close in from either flank of the stinger.
        u8 gap = (u8)(t >= 8 ? 0 : (u8)(16 - (t << 1)));
        i16 qx = (i16)(-fx_dy * (i8)gap), qy = (i16)(fx_dx * (i8)gap);
        put(0, (i16)(fx_px + qx), (i16)(fx_py + qy),
            FX_T(1), 0);
        put(1, (i16)(fx_px - qx), (i16)(fx_py - qy),
            FX_T(1), S_FLIPY);
    }
    if (t >= 45 && t < 54 && !(t & 1)) {
        // Four acid droplets burst out on the diagonals.
        i16 r = (i16)((t - 44) << 2);
        put(0, (i16)(fx_px + r), (i16)(fx_py + r), FX_T(2), 0);
        put(1, (i16)(fx_px - r), (i16)(fx_py + r), FX_T(2), 0);
        put(2, (i16)(fx_px + r), (i16)(fx_py - r), FX_T(2), 0);
        put(3, (i16)(fx_px - r), (i16)(fx_py - r), FX_T(2), 0);
    }
}

// ---- Corvin: Murderstorm Eclipse + Night Veil -------------------------------
static const i8 diag_x[4] = { 1, 1, -1, -1 };
static const i8 diag_y[4] = { 1, -1, 1, -1 };
// tile 200 is a "/" feather pointing up-right; mirror it outward per blade.
static const u8 diag_prop[4] = { S_FLIPY, 0, S_FLIPX | S_FLIPY, S_FLIPX };

static void blade_pos(u8 k, u8 t, i16 *x, i16 *y) {
    u8 r = (u8)((t > 20 ? 20 : t) * 3);
    i16 o = (i16)((r * 11) >> 4);     // r * 0.7 on the diagonal
    i16 hx = (i16)(fx_cx + diag_x[k] * o);
    i16 hy = (i16)(fx_cy + diag_y[k] * o);
    if (t > 28) {
        u8 s = (u8)(t > 40 ? 12 : t - 28);
        hx = (i16)(hx + (i16)((fx_px - hx) * (i16)s) / 12);
        hy = (i16)(hy + (i16)((fx_py - hy) * (i16)s) / 12);
    }
    if (t >= 40) {
        // The four feathers lock into a white X-crest over the target.
        hx = (i16)(fx_px + diag_x[k] * 5);
        hy = (i16)(fx_py + diag_y[k] * 5);
    }
    *x = hx;
    *y = hy;
}

static void corvin_tick(u8 t) {
    u8 k;
    i16 x, y;
    if (t < 32) eat_shots(fx_kx, fx_ky, 18, 0);
    if (t <= 20 || (t >= 28 && t < 40)) {
        // Fan-out sweep and the snap flight: one feather hit per body. The
        // slow fan visits a quarter of the table per tick; the fast snap
        // visits all of it.
        u8 i, step = (t >= 28) ? 1 : 4;
        for (k = 0; k < 4; ++k) {
            entity_t *e;
            blade_pos(k, t, &x, &y);
            for (i = (step == 1) ? 0 : (u8)(t & 3), e = &entities[i];
                 i < MAX_ENTITIES; i += step, e += step) {
                if (!is_body(e) || MASK_HAS(hit_a, i)) continue;
                if (vdist(BODY_X(e) - x, BODY_Y(e) - y) > 12) continue;
                MASK_SET(hit_a, i);
                fx_hit(i, (u8)(fx_damage + 3));
                if (fx_carrier == 0xFF) break;
            }
        }
    }
    if (t == 28) {
        // Snap target: the Raven Mark if it is live, else the nearest body
        // ahead (within 96px), else 48px ahead.
        u8 m = will_corvin_mark_slot;
        if (will_corvin_mark_ticks && m < MAX_ENTITIES
            && is_body(&entities[m])) {
            fx_px = BODY_X(&entities[m]);
            fx_py = BODY_Y(&entities[m]);
        } else {
            u8 i;
            u16 best = 97;
            entity_t *e = entities;
            for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
                i16 dx, dy;
                u16 d;
                if (!is_body(e)) continue;
                dx = BODY_X(e) - fx_cx;
                dy = BODY_Y(e) - fx_cy;
                if ((i16)(dx * fx_dx + dy * fx_dy) <= 0) continue;
                d = vdist(dx, dy);
                if (d < best) {
                    best = d;
                    fx_px = BODY_X(e);
                    fx_py = BODY_Y(e);
                }
            }
        }
        fx_ch4(0x3D, 0x34, 10);
    }
    if (t == 40) {
        u8 i;
        entity_t *e = entities;
        wash(wash_eclipse);
        palette_obj_load(2, pal_white);
        room_shake(2, 6);
        fx_ch1(0x00, 0x80, 0xC5, 1899, 6);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)(fx_px - 4), (i16)(fx_py - 4), 10);
        for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
            u8 d = (u8)(fx_damage + 7);
            if (!is_body(e) || MASK_HAS(hit_b, i)) continue;
            if (vdist(BODY_X(e) - fx_px, BODY_Y(e) - fx_py) > fx_reach)
                continue;
            MASK_SET(hit_b, i);
            if (i == will_corvin_mark_slot && will_corvin_mark_ticks) {
                d += 3;
                will_corvin_mark_ticks = (will_corvin_mark_ticks > 210)
                    ? 255 : (u8)(will_corvin_mark_ticks + 45);
            }
            fx_hit(i, d);
            if (fx_carrier == 0xFF) break;
        }
    }
    if (t == 43) fx_ch1(0x00, 0x80, 0xA4, 1890, 6);
    if (t == 44) unwash();
    // Effigy: the carrier holds the cast tile.
    fx_ctile = (u8)(WILL_MAXFX_TILE + ((t & 8) ? 3 : 2));
    fx_cflip = 0;
    if (carrier_ok()) carrier_park();
    hide_all();
    if (t < 44 && !(t > 41 && (t & 1))) {
        for (k = 0; k < 4; ++k) {
            u8 tile = (t >= 20 && t < 28 && ((t >> 1) & 1))
                ? FX_T(1) : WILL_MAXFX_TILE;
            blade_pos(k, t, &x, &y);
            put(k, x, y, tile, diag_prop[k]);
        }
    }
}

// ---- Wolfkin: Moonfang Cross-Rend (beat two) --------------------------------
static void wolfkin_tick(u8 t) {
    i16 qx = (i16)(-fx_dy * 4), qy = (i16)(fx_dx * 4);
    if (t == 6) unwash();
    if (t == 17) {
        // The Will wave's crescent cels are done (14 frames): borrow 200..203.
        set_sprite_data(WILL_MAXFX_TILE, 4, fx_tiles_wolfkin);
        palette_obj_load(2, pal_wolfkin);
    }
    if (t == 28) palette_obj_load(2, pal_white);
    if (t == 34) {
        // The crescent shears inward: one more chord on each nearby body.
        fx_kx = fx_floor(fx_px, fx_py) ? fx_px : (i16)player.x + 8;
        fx_ky = fx_floor(fx_px, fx_py) ? fx_py : (i16)player.y + 8;
        fx_ctile = FX_T(3);
        fx_cflip = 0;
        hit_ring(fx_px, fx_py, fx_reach, hit_a, (u8)(fx_damage + 1));
        wash(wash_eclipse);
        room_shake(2, 6);
        fx_ch1(0x16, 0x40, 0xD3, 1800, 10);
        fx_ch4(0x81, 0x1B, 8);
    }
    if (t == 36) palette_obj_load(2, pal_wolfkin);
    if (t == 38) unwash();
    if (carrier_ok()) carrier_park();
    hide_all();
    if (t <= 16) {
        // Two claw scars flicker along the dash path.
        if (!(t & 1)) {
            put(0, (i16)(fx_cx + fx_dx * 14 + qx), (i16)(fx_cy + fx_dy * 14 + qy),
                SPR_FX_SWING, fx_dx < 0 ? S_FLIPX : 0);
            put(1, (i16)(fx_cx + fx_dx * 28 - qx), (i16)(fx_cy + fx_dy * 28 - qy),
                SPR_FX_SWING, fx_dx < 0 ? S_FLIPX : 0);
        }
    } else if (t < 34) {
        // The crescent hangs at the dash apex, a crossed pair of claws.
        u8 tile = (t >= 28) ? FX_T(1) : WILL_MAXFX_TILE;
        if (t >= 28 || (t & 1)) {
            put(0, (i16)(fx_px - 3), fx_py, tile, 0);
            put(1, (i16)(fx_px + 3), fx_py, tile, S_FLIPX);
        }
    } else {
        // f34: a 16x16 X shears closed, then shatters outward and blinks.
        u8 s = (u8)(t - 34);
        u8 tile = (s < 3) ? FX_T(2) : FX_T(3);
        if (s >= 3 && (t & 1)) return;
        put(0, (i16)(fx_px - 4 - s), (i16)(fx_py - 4 - s), tile, 0);
        put(1, (i16)(fx_px + 4 + s), (i16)(fx_py - 4 - s), tile, S_FLIPX);
        put(2, (i16)(fx_px - 4 - s), (i16)(fx_py + 4 + s), tile, S_FLIPY);
        put(3, (i16)(fx_px + 4 + s), (i16)(fx_py + 4 + s), tile,
            S_FLIPX | S_FLIPY);
    }
}

// ---- entry points ------------------------------------------------------------
u8 will_maxfx_begin(u8 class_id, u8 dir, u8 damage) BANKED {
    u8 k, level = player.will_level;
    if (level > WILL_LEVEL_CAP) level = WILL_LEVEL_CAP;
    if (!level) level = 1;
    if (will_maxfx_live) fx_end();
    for (k = 0; k < (u8)sizeof(hit_a); ++k) hit_a[k] = hit_b[k] = 0;
    will_maxfx_dir = (u8)(dir & 7);
    fx_dx = dir8_dx[dir & 7];
    fx_dy = dir8_dy[dir & 7];
    fx_cx = (i16)player.x + 8;
    fx_cy = (i16)player.y + 8;
    fx_kx = fx_cx;
    fx_ky = fx_cy;
    fx_px = (i16)(fx_cx + fx_dx * 8);
    fx_py = (i16)(fx_cy + fx_dy * 8);
    fx_damage = damage;
    fx_giant_hits = 0;
    fx_stop = 0;
    fx_pyl = 0;
    fx_anchor = 0xFF;
    fx_washed = 0;
    fx_cflip = 0;
    fx_ctile = WILL_MAXFX_TILE;
    picsean_vortex_abort = 0;
    will_maxfx_t = 0;
    hide_all();
    switch (class_id) {
        case 1: {
            // Pylons 24px and 40px ahead, offset 10px to either side so a
            // horizontal cast never stacks them on one scanline.
            i8 px = (i8)-fx_dy, py = fx_dx;
            fx_ax = (i16)(fx_cx + fx_dx * 24 + px * 10);
            fx_ay = (i16)(fx_cy + fx_dy * 24 + py * 10);
            fx_bx = (i16)(fx_cx + fx_dx * 40 - px * 10);
            fx_by = (i16)(fx_cy + fx_dy * 40 - py * 10);
            fx_reach = (u8)((level - 1) << 2);
            if (!carrier_ensure()) return 0;
            set_sprite_data(WILL_MAXFX_TILE, 4, fx_tiles_sauran);
            palette_obj_load(2, pal_sauran);
            wash(wash_ochre);
            room_shake(2, 10);
            sfx_thud(1160);
            break;
        }
        case 4:
            fx_reach = (u8)(28 + ((level - 1) << 2));
            if (!carrier_ensure()) return 0;
            set_sprite_data(WILL_MAXFX_TILE, 4, fx_tiles_vespine);
            palette_obj_load(2, pal_vespine);
            wash(wash_venom);
            // Wing buzz.
            fx_ch1(0x00, 0x00, 0xB3, 1780, 10);
            fx_ch4(0x31, 0x21, 6);
            break;
        case 2:
            fx_reach = (u8)(20 + ((level - 1) << 2));
            fx_px = (i16)(fx_cx + fx_dx * ((fx_dx && fx_dy) ? 34 : 48));
            fx_py = (i16)(fx_cy + fx_dy * ((fx_dx && fx_dy) ? 34 : 48));
            fx_ctile = FX_T(2);
            {
                // The effigy stays a step behind where Corvin stood.
                u8 back = (fx_dx && fx_dy) ? 9 : 12;
                i16 ex = (i16)(fx_cx - fx_dx * (i8)back);
                i16 ey = (i16)(fx_cy - fx_dy * (i8)back);
                if (fx_floor(ex, ey)) { fx_kx = ex; fx_ky = ey; }
            }
            if (!carrier_ensure()) return 0;
            set_sprite_data(WILL_MAXFX_TILE, 4, fx_tiles_corvin);
            palette_obj_load(2, pal_corvin);
            wash(wash_night);
            // Soft feather whoosh: a rising noise swell.
            fx_ch4(0x2D, 0x45, 16);
            break;
        default: {
            // Wolfkin: beat one (the guarded dash and the Will wave) is
            // already live; this adds the scars and the f34 cross-rend.
            u8 reach = (fx_dx && fx_dy) ? 31 : 44;
            fx_reach = (u8)(20 + ((level - 1) << 2));
            fx_px = (i16)(fx_cx + fx_dx * (i8)reach);
            fx_py = (i16)(fx_cy + fx_dy * (i8)reach);
            if (fx_px < 12) fx_px = 12;
            if (fx_py < 12) fx_py = 12;
            if (fx_px > (i16)room_world_width - 12)
                fx_px = (i16)room_world_width - 12;
            if (fx_py > (i16)room_world_height - 12)
                fx_py = (i16)room_world_height - 12;
            fx_carrier = 0xFF;
            wash(wash_moon);
            // A snarling dash-cut instead of the shared roar.
            fx_ch1(0x00, 0x80, 0xC2, 1300, 8);
            fx_ch4(0x92, 0x34, 8);
            break;
        }
    }
    will_maxfx_live = (u8)(class_id + 1);
    // Ride the Tide Vortex's existing per-frame dispatch (combat tick, room
    // overlay draw, room-exit abort) instead of adding hooks to the hot
    // combat loop: only one champion is ever in a run.
    picsean_vortex_ticks = 1;
    will_maxfx_arm_lock();
    return 1;
}

void will_maxfx_tick(void) BANKED {
    u8 t;
    if (!will_maxfx_live) return;
    picsean_vortex_ticks = 1;
    if (picsean_vortex_abort || player.class_id != (u8)(will_maxfx_live - 1)) {
        fx_end();
        return;
    }
    t = will_maxfx_t;
    switch (will_maxfx_live - 1) {
        case 1:
            sauran_tick(t);
            if (t >= WILL_MAXFX_SAURAN_TICKS) { fx_end(); return; }
            break;
        case 4:
            vespine_tick(t);
            if (t >= WILL_MAXFX_VESPINE_TICKS) { fx_end(); return; }
            break;
        case 2:
            corvin_tick(t);
            if (t >= WILL_MAXFX_CORVIN_TICKS) { fx_end(); return; }
            break;
        default:
            wolfkin_tick(t);
            if (t >= WILL_MAXFX_WOLFKIN_TICKS) { fx_end(); return; }
            break;
    }
    will_maxfx_t = (u8)(t + 1);
}

void will_maxfx_draw(void) BANKED {
    // put(0..3) always occupies the legacy tail at 32..35, zeros included,
    // so hide_all / fx_end clear those four slots.
    memcpy((u8 *)&shadow_OAM[WILL_MAXFX_OAM_LO], fx_oam,
        (size_t)((u16)WILL_MAXFX_OAM_N << 2));
}
