#pragma bank 31

#include <gb/gb.h>
#include <string.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/boss_projectile.h"
#include "game/combat.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/hexa_boss.h"
#include "game/loop.h"
#include "game/magic.h"
#include "game/will_levels.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/projectile.h"
#include "game/rare_enemy.h"
#include "game/room.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/large_boss.h"
#include "render/tiles.h"
#include "content.h"

// Elemental hero magic. Spec: docs/superpowers/specs/
// 2026-11-17-elemental-hero-magic.md
// Max-Will levels: 2026-11-21-max-will-levels.md section 9.
// The shipped kit is L1; L2-L4 widen and embellish (not L4-shrink).
//
// Wolfkin  fire       tap MOONFIRE (homing fireball)   hold FLAME WARD
// Sauran   lightning  tap THUNDER (sure strike, stun)  hold STONESKIN + static
// Corvin   shadow     tap HEX (orb, confusion burst)   hold SHADOW VEIL
// Picsean  ice        tap BLIZZARD (D-pad steered)     hold CURE
// Vespine  poison     tap BRAMBLE (thorn lane)         hold THORN MIRROR
//
// Moving spells are ordinary player projectiles (wall, tree, crack, crystal
// and switch rules for free) tagged in ai_data[7]. Area hits go through a
// transient carrier and combat_apply_player_shot_hit, so weakness, LCK,
// Colossus caps and kill rewards match every weapon. Ward and strike state
// lives here, never in persistent entity slots; visuals are short FX.

u8 combat_apply_player_shot_hit(entity_t *shot, u8 i, entity_t *ej,
                                u8 j, u8 *giant_hits) BANKED;
void secondary_fire(u8 dir, u8 moving, u8 damage) BANKED;
u8 room_input_dir8(u8 keys, u8 facing) BANKED;

#include "game/magic_art.inc"

u8 magic_hold;
u8 magic_last_spell;
u8 magic_casts;
u8 magic_ward_ticks;
u8 magic_ward_kind;
u8 magic_tap_cd;
u8 magic_ward_cd;
u8 magic_cure_used;
u8 magic_room_serial;
static u8 seen_serial;

static u8 charging;
static u8 prev_b;
static u16 last_frame;
static u8 carrier;
// No initialized globals here: _INITIALIZER lives in the full home bank.
// The 0xFF sentinels are set by magic_reset, which magic_room_enter runs
// once per power-on (New Game, Continue and attract all enter a room).
static u8 magic_inited;
static u8 giant_hits;
static i16 hit_cx, hit_cy;       // knockback origin of the current hit batch

#define DPAD (J_LEFT | J_RIGHT | J_UP | J_DOWN)
#define CARRIER_TAG 0xB7
#define BANK1 0x08

static const u8 class_elem[5] = { 1, 4, 8, 2, 16 };
// OBJ palette per element: fire 4 (red/gold), lightning 5 (amber/pale
// yellow), shadow 1 (Corvin violet), ice 1 (Picsean cyan), poison 7 (acid
// green/amber). All tiles live in VRAM bank 1.
static const u8 class_pal[5] = { 4 | BANK1, 5 | BANK1, 1 | BANK1,
                                 1 | BANK1, 7 | BANK1 };
static const u8 tap_cd[5] = { 36, 45, 30, 30, 40 };
static const u8 ward_cost[5] = { 2, 2, 2, 5, 2 };

/* #151 section 9.4: index is clamped maxwill_level - 1. L1 is shipped. */
static const u8 mf_home[4]  = { 96, 120, 144, 168 };
static const u8 mf_burst_r[4] = { 14, 18, 21, 25 };
static const u8 mf_base[4]  = { 4, 5, 5, 6 };
static const u8 mf_bdmg[4]  = { 3, 3, 4, 4 };
static const u8 mf_ttl[4]   = { 80, 90, 100, 110 };
static const u8 th_aim[4]   = { 104, 130, 156, 182 };
static const u8 th_ahead[4] = { 40, 50, 60, 70 };
static const u8 th_chain_r[4] = { 48, 60, 72, 84 };
static const u8 th_splash[4] = { 10, 13, 15, 18 };
static const u8 th_base[4]  = { 5, 6, 7, 7 };
static const u8 hx_ttl[4]   = { 32, 40, 48, 56 };
static const u8 hx_burst_r[4] = { 18, 23, 27, 32 };
static const u8 hx_base[4]  = { 3, 3, 4, 4 };
static const u8 bz_ttl[4]   = { 70, 80, 90, 100 };
static const u8 bz_hits[4]  = { 2, 2, 3, 3 };
static const u8 bz_base[4]  = { 3, 3, 4, 4 };
static const u8 bz_stop[4]  = { 12, 14, 16, 18 };
static const u8 br_dist[4][5] = {
    { 16, 30, 44, 58, 0 },
    { 20, 38, 56, 74, 0 },
    { 24, 45, 66, 87, 108 },
    { 28, 53, 78, 103, 128 },
};
static const u8 br_n[4]     = { 4, 4, 5, 5 };
static const u8 br_splash[4] = { 12, 15, 18, 21 };
static const u8 br_base[4]  = { 3, 3, 4, 4 };
static const u8 fw_orb[4]   = { 20, 25, 30, 35 };
static const u8 fw_chg[4]   = { 2, 2, 3, 3 };
static const u8 sk_time[4]  = { 90, 105, 120, 135 };
static const u8 sk_r[4]     = { 28, 35, 42, 49 };
static const u8 sk_pulse[4] = { 2, 2, 3, 3 };
static const u8 vl_ifr[4]   = { 20, 24, 28, 32 };
static const u8 vl_eat[4]   = { 20, 25, 30, 35 };
static const u8 cu_heal[4]  = { 2, 2, 3, 3 };
static const u8 cu_ifr[4]   = { 20, 24, 24, 30 };
static const u8 tm_r[4]     = { 14, 18, 21, 25 };

static u8 spell_lv(void) {
    u8 lv = player.maxwill_level;
    if (lv < MAXWILL_MIN) lv = MAXWILL_MIN;
    if (lv > MAXWILL_MAX) lv = MAXWILL_MAX;
    return (u8)(lv - 1);
}

// 8-way ring, radius 14 (diagonals 10).
static const i8 ring_x[8] = { 0, 10, 14, 10, 0, -10, -14, -10 };
static const i8 ring_y[8] = { -14, -10, 0, 10, 14, 10, 0, -10 };
// 12-step orbit, radius 16 (30 degree steps).
static const i8 orb_x[12] = { 20, 17, 10, 0, -10, -17, -20, -17, -10, 0, 10, 17 };
static const i8 orb_y[12] = { 0, 10, 17, 20, 17, 10, 0, -10, -17, -20, -17, -10 };

// ---- tracked moving spells ------------------------------------------------
#define SHOTS 3
static u8 shot_slot[SHOTS];
static u8 shot_kind[SHOTS];
static u8 shot_dir[SHOTS];
static u8 shot_direct[SHOTS];     // body slot the shot struck (burst skips it)
static u8 shot_age[SHOTS];
static u8 shot_dmg[SHOTS];
static u8 shot_lv[SHOTS];
static i16 shot_lx[SHOTS], shot_ly[SHOTS];

// ---- strikes ----------------------------------------------------------------
static u8 th_t, th_target, th_chain, th_dmg, th_lv;
static i16 th_x, th_y;
static u8 br_t, br_step, br_dmg, br_lv;
static i16 br_x, br_y;
static i8 br_dx, br_dy;
static u8 ice_lv;
static u8 br_mask[(MAX_ENTITIES + 7) / 8];
static u8 ring_mask[(MAX_ENTITIES + 7) / 8];
static u8 ice_mask[(MAX_ENTITIES + 7) / 8];

// ---- wards ------------------------------------------------------------------
static u8 wisp_live, ward_angle, ward_beat;
static u8 wisp_charges[3], wisp_cd[3], wisp_fx[3];
static u8 mirror_voice;

#define MASK_SET(m, i) ((m)[(u8)(i) >> 3] |= (u8)(1u << ((i) & 7)))
#define MASK_HAS(m, i) ((m)[(u8)(i) >> 3] & (u8)(1u << ((i) & 7)))
#define BODY_X(e) ((i16)((e)->x + (i16)((e)->hitbox >> 5)))
#define BODY_Y(e) ((i16)((e)->y + (i16)(((e)->hitbox & 0x0F) >> 1)))
#define HERO_X ((i16)player.x + 6)
#define HERO_Y ((i16)player.y + 6)

// ---- sound -----------------------------------------------------------------
static void v1(u8 nr10, u8 nr11, u8 nr12, u16 freq, u8 frames) {
    if (sfx_melody_locked()) return;
    sfx_will_active = 0;
    sfx_claim_channels(frames, 0);
    NR10_REG = nr10;
    NR11_REG = nr11;
    NR12_REG = nr12;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

static void v4(u8 nr42, u8 nr43, u8 frames) {
    if (sfx_melody_locked()) return;
    sfx_claim_channels(0, frames);
    NR41_REG = 0;
    NR42_REG = nr42;
    NR43_REG = nr43;
    NR44_REG = 0x80;
}

static void refuse(void) { sfx_play(SFX_REFUSE); }

// ---- geometry ----------------------------------------------------------------
static u16 vdist(i16 dx, i16 dy) {
    u16 ax = (u16)(dx < 0 ? -dx : dx);
    u16 ay = (u16)(dy < 0 ? -dy : dy);
    if (ax < ay) { u16 t = ax; ax = ay; ay = t; }
    return (u16)(ax + (ay >> 2) + (ay >> 3));
}

static u8 dir_toward(i16 dx, i16 dy) {
    u16 ax = dx < 0 ? (u16)-dx : (u16)dx;
    u16 ay = dy < 0 ? (u16)-dy : (u16)dy;
    if (ax > (ay << 1)) return dx < 0 ? 6 : 2;
    if (ay > (ax << 1)) return dy < 0 ? 0 : 4;
    if (dx >= 0) return dy < 0 ? 1 : 3;
    return dy < 0 ? 7 : 5;
}

// One dir8 step from cur toward want (never a U-turn in one step).
static u8 turn_toward(u8 cur, u8 want) {
    u8 diff = (u8)((want - cur) & 7);
    if (!diff) return cur;
    return (u8)((diff <= 4 ? cur + 1 : cur + 7) & 7);
}

static u8 is_body(const entity_t *e) {
    return (e->flags & (EF_ACTIVE | EF_ON_SCREEN)) == (EF_ACTIVE | EF_ON_SCREEN)
        && e->type == ENT_ENEMY;
}

static u8 is_heavy(const entity_t *e, u8 j) {
    u8 eid = e->ai_data[0];
    if (e->flags & (EF_ELITE | EF_ALPHA | EF_RARE)) return 1;
    if (eid == ENEMY_STONE_SENTINEL || eid == ENEMY_STAGE_REAPER) return 1;
    if (e->ai_data[2] == ENEMY_AUX_BELLWARDEN) return 1;
    if (j == large_boss_index || hexa_boss_active) return 1;
    return 0;
}

static u8 is_floor(i16 x, i16 y) {
    u8 t;
    if (x < 8 || y < 8 || x > (i16)room_world_width - 8
        || y > (i16)room_world_height - 8) return 0;
    t = room_tile_at_px(x, y);
    return t <= BGT_FLOOR3 && t != BGT_WALL;
}

static u8 spell_damage(u8 base) {
    u8 atk = STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_ATK) : player.atk;
    return (u8)(base + (atk >> 1));
}

static void fx(u8 tile, u8 pal, i16 cx, i16 cy, u8 ttl) {
    fx_spawn(tile, pal, (i16)(cx - 4), (i16)(cy - 4), ttl);
}

// ---- transient hit carrier -----------------------------------------------------
static u8 carrier_ok(void) {
    entity_t *c;
    if (carrier == 0xFF) return 0;
    c = &entities[carrier];
    return (c->flags & (EF_ACTIVE | EF_PLAYER_PROJ)) == (EF_ACTIVE | EF_PLAYER_PROJ)
        && c->type == ENT_PROJECTILE && c->ai_data[6] == PROJ_AUX_VORTEX
        && c->ai_data[7] == CARRIER_TAG;
}

static u8 carrier_open(void) {
    u8 s;
    entity_t *c;
    if (carrier_ok()) return 1;
    s = entity_spawn(ENT_PROJECTILE);
    if (s == 0xFF) { carrier = 0xFF; return 0; }
    c = &entities[s];
    c->flags |= EF_PLAYER_PROJ;
    c->x = player.x;
    c->y = player.y;
    c->vx = c->vy = 0;
    c->hp = 200;
    c->state_timer = 2;
    c->hitbox = 0x88;
    c->sprite_tile = SPR_BULLET;
    c->palette = 2;
    memset(c->ai_data, 0, sizeof(c->ai_data));
    c->ai_data[6] = PROJ_AUX_VORTEX;
    c->ai_data[7] = CARRIER_TAG;
    carrier = s;
    return 1;
}

// The carrier never survives the frame: it cannot be drawn or collide.
static void carrier_close(void) {
    if (carrier_ok()) entity_kill(carrier);
    carrier = 0xFF;
}

// One authored hit on body j: damage via the shared pipeline, then the
// spell's guaranteed condition on a survivor. Returns 1 if the hit landed.
static u8 hit_body(u8 j, u8 dmg, u8 elem, u8 kind, u8 ticks) {
    entity_t *c;
    entity_t *ej = &entities[j];
    i16 dx, dy;
    if (!carrier_open()) return 0;
    c = &entities[carrier];
    dx = (i16)(ej->x - hit_cx);
    dy = (i16)(ej->y - hit_cy);
    c->damage = dmg;
    c->hp = 200;
    c->x = ej->x;
    c->y = ej->y;
    c->vx = (i8)(dx > 0 ? 1 : dx < 0 ? -1 : 0);
    c->vy = (i8)(dy > 0 ? 1 : dy < 0 ? -1 : 0);
    c->ai_data[1] = elem;
    combat_apply_player_shot_hit(c, carrier, ej, j, &giant_hits);
    if (!carrier_ok()) carrier = 0xFF;
    if (kind && (ej->flags & EF_ACTIVE) && ej->type == ENT_ENEMY)
        status_enemy_apply(j, kind, ticks);
    return 1;
}

// Hit every on-screen body within r of (x, y) once per mask.
static u8 hit_ring(i16 x, i16 y, u8 r, u8 *mask, u8 dmg, u8 elem,
                   u8 kind, u8 ticks) {
    u8 i, n = 0;
    entity_t *e = entities;
    hit_cx = x;
    hit_cy = y;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        if (!is_body(e) || MASK_HAS(mask, i)) continue;
        if (vdist(BODY_X(e) - x, BODY_Y(e) - y) > r) continue;
        MASK_SET(mask, i);
        if (!hit_body(i, dmg, elem, kind, ticks)) break;
        n++;
    }
    return n;
}

static u8 hostile_shot(const entity_t *e) {
    return (e->flags & EF_ACTIVE) && e->type == ENT_PROJECTILE
        && !(e->flags & EF_PLAYER_PROJ)
        && e->ai_data[6] != PROJ_AUX_MORTAL_SCYTHE;
}

// Erase hostile shots within r of (x, y). Returns how many.
static u8 eat_shots(i16 x, i16 y, u8 r) {
    u8 i, n = 0;
    entity_t *e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        if (!hostile_shot(e)) continue;
        if (vdist((i16)(e->x + 3) - x, (i16)(e->y + 3) - y) > r) continue;
        if (n < 2) fx_spawn(SPR_FX_IMPACT, 2, e->x, e->y, 6);
        entity_kill(i);
        n++;
    }
    return n;
}

// Best body in the aim half-plane within range (Raven Mark scoring).
static u8 aimed_body(u8 dir, u16 range, u8 skip) {
    u8 i, best = 0xFF;
    u16 best_score = 0xFFFF;
    entity_t *e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        i16 dx, dy, dot, cross;
        u16 score, d;
        if (i == skip || !is_body(e)) continue;
        dx = BODY_X(e) - HERO_X;
        dy = BODY_Y(e) - HERO_Y;
        d = vdist(dx, dy);
        if (d > range) continue;
        dot = (i16)(dx * dir8_dx[dir] + dy * dir8_dy[dir]);
        cross = (i16)(dx * dir8_dy[dir] - dy * dir8_dx[dir]);
        if (cross < 0) cross = -cross;
        score = (u16)(d + ((u16)cross << 1));
        if (dot <= 0) score = (u16)(score + 1024);
        if (score < best_score) { best_score = score; best = i; }
    }
    return best;
}

static u8 nearest_body(i16 x, i16 y, u16 range, u8 skip) {
    u8 i, best = 0xFF;
    u16 bd = 0xFFFF;
    entity_t *e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        u16 d;
        if (i == skip || !is_body(e)) continue;
        d = vdist(BODY_X(e) - x, BODY_Y(e) - y);
        if (d <= range && d < bd) { bd = d; best = i; }
    }
    return best;
}

// ---- moving spells ---------------------------------------------------------------
static void set_heading(entity_t *e, u8 dir, u8 speed) {
    e->vx = (i8)(dir8_dx[dir] * (i8)speed);
    e->vy = (i8)(dir8_dy[dir] * (i8)speed);
}

static u8 spawn_shot(u8 kind, u8 dir, u8 dmg, u8 speed, u8 ttl, u8 pierce,
                     u8 tile) {
    u8 k, s;
    entity_t *e;
    for (k = 0; k < SHOTS; ++k) if (shot_slot[k] == 0xFF) break;
    if (k == SHOTS) return 0;
    g_shot_element = class_elem[player.class_id];
    s = projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_BULLET);
    if (s == 0xFF) return 0;
    e = &entities[s];
    set_heading(e, dir, speed);
    e->state_timer = ttl;
    e->hp = pierce;
    e->sprite_tile = tile;
    e->palette = class_pal[player.class_id];
    e->hitbox = 0x77;
    e->ai_data[2] = 0;
    shot_lv[k] = spell_lv();
    e->ai_data[3] = 0;   // spells are not relic carriers (no splash/echo)
    e->ai_data[4] = 0;
    e->ai_data[7] = (u8)(MAGIC_SHOT_TAG | kind);
    shot_slot[k] = s;
    shot_kind[k] = kind;
    shot_dir[k] = dir;
    shot_direct[k] = 0xFF;
    shot_age[k] = 0;
    shot_dmg[k] = dmg;
    shot_lx[k] = e->x + 3;
    shot_ly[k] = e->y + 3;
    return 1;
}

static u8 shot_alive(u8 k) {
    entity_t *e;
    u8 s = shot_slot[k];
    if (s == 0xFF) return 0;
    e = &entities[s];
    return (e->flags & EF_ACTIVE) && e->type == ENT_PROJECTILE
        && e->ai_data[7] == (u8)(MAGIC_SHOT_TAG | shot_kind[k]);
}

static void moonfire_burst(u8 k) {
    i16 x = shot_lx[k], y = shot_ly[k];
    u8 lv = shot_lv[k];
    memset(ring_mask, 0, sizeof(ring_mask));
    if (shot_direct[k] != 0xFF) MASK_SET(ring_mask, shot_direct[k]);
    hit_ring(x, y, mf_burst_r[lv], ring_mask, mf_bdmg[lv], 1, 0, 0);
    fx(MAGIC_T_FLASH, 4 | BANK1, x, y, (u8)(10 + (lv >= 2 ? 4 : 0)));
    fx(MAGIC_T_WISP, 4 | BANK1, x - 8, y - 6, 8);
    fx(MAGIC_T_WISP, 4 | BANK1, x + 8, y - 6, 8);
    if (lv >= 3) {
        fx(MAGIC_T_FIRE_B, 4 | BANK1, x, y - 8, 10);
        fx(MAGIC_T_WISP, 4 | BANK1, x, y + 8, 8);
    }
    v4(0xC2, 0x45, 14);
}

static void hex_burst(u8 k) {
    u8 i;
    i16 x = shot_lx[k], y = shot_ly[k];
    entity_t *e = entities;
    memset(ring_mask, 0, sizeof(ring_mask));
    if (shot_direct[k] != 0xFF) MASK_SET(ring_mask, shot_direct[k]);
    hit_cx = x;
    hit_cy = y;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        u8 kind;
        if (!is_body(e) || MASK_HAS(ring_mask, i)) continue;
        if (vdist(BODY_X(e) - x, BODY_Y(e) - y) > hx_burst_r[shot_lv[k]]) continue;
        MASK_SET(ring_mask, i);
        kind = (rng_next_u8() & 1)
            ? (is_heavy(e, i) ? QSTATUS_MUTE : QSTATUS_CONFUSION) : 0;
        if (!hit_body(i, shot_dmg[k], 8, kind, 16)) break;
    }
    {
        u8 step = (shot_lv[k] >= 2) ? 1 : 2;
        for (i = (u8)(step == 1 ? 0 : 1); i < 8; i = (u8)(i + step))
            fx(MAGIC_T_HEX_B, 1 | BANK1, x + ring_x[i], y + ring_y[i], 10);
    }
    fx(MAGIC_T_HEX_A, 1 | BANK1, x, y, 12);
    v1(0x2F, 0x40, 0x93, 1500, 16);
}

// One hook before the normal combat damage branch. Keep the tag test and
// guaranteed spell status here, away from the near-full combat bank.
u8 magic_hit_status(u8 j, u8 i, u8 survives) BANKED {
    u8 k;
    entity_t *shot = &entities[i];
    entity_t *ej = &entities[j];
    if (!MAGIC_IS_SHOT(shot)) {
        if (!survives) return 1;
        status_try_player_shot(j, i);
        // Wolfkin's Fang Claw (slow contact arc, see projectile.c) shoves
        // light bodies 1 px beyond the ordinary knockback, so they stay
        // inside his follow-up arc (Carbon balance review).
        if (shot->ai_data[6] == PROJ_AUX_WOLFKIN_FANG
            && shot->vx >= -2 && shot->vx <= 2
            && shot->vy >= -2 && shot->vy <= 2 && !is_heavy(ej, j)) {
            i8 kx = (i8)(shot->vx > 0 ? 1 : shot->vx < 0 ? -1 : 0);
            i8 ky = (i8)(shot->vy > 0 ? 1 : shot->vy < 0 ? -1 : 0);
            enemy_try_step(ej, kx, ky);
        }
        return 1;
    }
    for (k = 0; k < SHOTS; ++k) {
        if (shot_slot[k] != i) continue;
        if (shot_direct[k] == 0xFF) shot_direct[k] = j;
        shot_lx[k] = shot->x + 3;
        shot_ly[k] = shot->y + 3;
        break;
    }
    if ((shot->ai_data[7] & 15) == SPELL_MOONFIRE) g_hitstop = 3;
    if ((shot->ai_data[7] & 15) == SPELL_BLIZZARD && MASK_HAS(ice_mask, j))
        return 0;
    if (!survives) return 1;
    switch (shot->ai_data[7] & 15) {
        case SPELL_MOONFIRE:
            status_enemy_apply(j, QSTATUS_BURN, 0);
            break;
        case SPELL_HEX:
            status_enemy_apply(j, is_heavy(ej, j)
                ? QSTATUS_MUTE : QSTATUS_CONFUSION, 16);
            break;
        case SPELL_BLIZZARD:
            MASK_SET(ice_mask, j);
            status_enemy_apply(j, QSTATUS_STOP, bz_stop[ice_lv]);
            fx(MAGIC_T_CURE, 1 | BANK1, BODY_X(ej), BODY_Y(ej) - 4, 8);
            break;
    }
    return 1;
}

static void tick_shots(u8 keys) {
    u8 k;
    for (k = 0; k < SHOTS; ++k) {
        entity_t *e;
        if (shot_slot[k] == 0xFF) continue;
        if (!shot_alive(k)) {
            // Moonfire and Hex burst where they ended: a body, a wall, or
            // the end of their flight.
            if (shot_kind[k] == SPELL_MOONFIRE) moonfire_burst(k);
            else if (shot_kind[k] == SPELL_HEX) hex_burst(k);
            shot_slot[k] = 0xFF;
            continue;
        }
        e = &entities[shot_slot[k]];
        shot_age[k]++;
        shot_lx[k] = e->x + 3;
        shot_ly[k] = e->y + 3;
        if (shot_kind[k] == SPELL_MOONFIRE) {
            e->sprite_tile = (shot_age[k] & 4) ? MAGIC_T_FIRE_B : MAGIC_T_FIRE_A;
            // FFA Fire: re-target the nearest body ahead every 3 frames and
            // turn one 45-degree step toward it.
            if ((shot_age[k] % 3) == 0) {
                u8 i, best = 0xFF;
                u16 bd = (u16)(mf_home[shot_lv[k]] + 1);
                entity_t *b = entities;
                for (i = 0; i < MAX_ENTITIES; ++i, ++b) {
                    i16 dx, dy;
                    u16 d;
                    if (!is_body(b)) continue;
                    dx = BODY_X(b) - shot_lx[k];
                    dy = BODY_Y(b) - shot_ly[k];
                    if ((i16)(dx * e->vx + dy * e->vy) < 0) continue;
                    d = vdist(dx, dy);
                    if (d < bd) { bd = d; best = i; }
                }
                if (best != 0xFF) {
                    u8 want = dir_toward(
                        BODY_X(&entities[best]) - shot_lx[k],
                        BODY_Y(&entities[best]) - shot_ly[k]);
                    shot_dir[k] = turn_toward(shot_dir[k], want);
                    set_heading(e, shot_dir[k], 3);
                }
            }
        } else if (shot_kind[k] == SPELL_BLIZZARD) {
            // FFA Ice: the held D-pad steers the icicle after release.
            if ((shot_age[k] & 3) == 0 && (keys & DPAD)) {
                u8 want = room_input_dir8(keys, player.facing);
                shot_dir[k] = turn_toward(shot_dir[k], want);
                set_heading(e, shot_dir[k], 3);
            }
            {
                u8 d = shot_dir[k];
                // ICE points north, ICE_D north-east; flips cover the rest.
                e->sprite_tile = (d & 1) ? MAGIC_T_ICE_D : MAGIC_T_ICE;
                e->ai_data[4] = 0;
                if (d & 1) {
                    if (d == 5 || d == 7) e->ai_data[4] |= PROJ_VIS_FLIP_X;
                    if (d == 3 || d == 5) e->ai_data[4] |= PROJ_VIS_FLIP_Y;
                } else if (d == 4) e->ai_data[4] = PROJ_VIS_FLIP_Y;
                else if (d == 2 || d == 6) {
                    // ICE_H points west.
                    e->sprite_tile = MAGIC_T_ICE_H;
                    e->ai_data[4] = (d == 2) ? PROJ_VIS_FLIP_X : 0;
                }
            }
            if ((shot_age[k] & (shot_lv[k] ? 3 : 7)) == 0)
                fx(MAGIC_T_MOTE, 1 | BANK1, shot_lx[k], shot_ly[k], 6);
            if (shot_lv[k] >= 3 && (shot_age[k] & 1) == 0)
                fx(MAGIC_T_ICE, 1 | BANK1, shot_lx[k], shot_ly[k] - 4, 4);
        } else {
            e->sprite_tile = (shot_age[k] & 4) ? MAGIC_T_HEX_B : MAGIC_T_HEX_A;
        }
    }
}

// ---- strikes ------------------------------------------------------------------
static void bolt_column(i16 x, i16 y, u8 tall) {
    fx(MAGIC_T_BOLT, 5 | BANK1, x, y - 16, 10);
    if (tall) fx(MAGIC_T_BOLT, 5 | BANK1, x, y - 24, 8);
    fx(MAGIC_T_BOLT, 5 | BANK1, x, y - 8, 10);
    fx(MAGIC_T_FLASH, 5 | BANK1, x, y, 10);
}

static void tick_thunder(void) {
    entity_t *t;
    if (!th_t) return;
    th_t++;
    if (th_target != 0xFF) {
        t = &entities[th_target];
        if (is_body(t)) { th_x = BODY_X(t); th_y = BODY_Y(t); }
        else th_target = 0xFF;
    }
    if (th_t == 7) {
        bolt_column(th_x, th_y, 1);
        hit_cx = HERO_X;
        hit_cy = HERO_Y;
        if (th_target != 0xFF) {
            hit_body(th_target, th_dmg, 4, QSTATUS_STOP, 10);
            g_hitstop = 3;   // weight only on a real strike
        } else {
            memset(ring_mask, 0, sizeof(ring_mask));
            hit_ring(th_x, th_y, th_splash[th_lv], ring_mask, th_dmg, 4, QSTATUS_STOP, 10);
            if (th_x >= 0 && th_y >= 0)
                room_elemental_tile((u8)(th_x >> 3), (u8)(th_y >> 3), 4);
        }
        room_shake(1, 6);
        v4(0xF3, 0x52, 20);
        v1(0x00, 0x80, 0xF2, 380, 12);
        th_chain = nearest_body(th_x, th_y, th_chain_r[th_lv], th_target);
    } else if (th_t == 15) {
        if (th_chain != 0xFF && is_body(&entities[th_chain])) {
            t = &entities[th_chain];
            bolt_column(BODY_X(t), BODY_Y(t), 0);
            hit_cx = th_x;
            hit_cy = th_y;
            hit_body(th_chain, (u8)((th_dmg + 1) >> 1), 4, QSTATUS_SLOW, 12);
            v4(0xB2, 0x43, 10);
        }
        th_t = 0;
    }
}

static void tick_bramble(void) {
    i16 x, y;
    u8 dist, t;
    if (!br_t) return;
    br_t++;
    if ((u8)((br_t - 2) % 5) != 0) return;
    if (br_step >= br_n[br_lv]) { br_t = 0; return; }
    dist = br_dist[br_lv][br_step];
    if (br_dx && br_dy) dist = (u8)((dist * 3) >> 2);
    x = (i16)(br_x + br_dx * (i16)dist);
    y = (i16)(br_y + br_dy * (i16)dist);
    br_step++;
    if (x < 8 || y < 8 || x > (i16)room_world_width - 8
        || y > (i16)room_world_height - 8) { br_t = 0; return; }
    t = room_tile_at_px(x, y);
    if (t == BGT_TREE) {
        // Thorns choke wild growth: the bramble clears it like fire.
        room_elemental_tile((u8)(x >> 3), (u8)(y >> 3), 1);
    } else if (!(t <= BGT_FLOOR3 && t != BGT_WALL) && t != BGT_RUBBLE
               && t != BGT_SPIKES) {
        br_t = 0;
        return;
    }
    hit_ring(x, y, br_splash[br_lv], br_mask, br_dmg, 16, QSTATUS_POISON, 60);
    fx(MAGIC_T_THORN_B, 7 | BANK1, x, y, 16);
    fx(MAGIC_T_THORN_A, 7 | BANK1, x + (br_dy ? 6 : 0), y + (br_dx ? 6 : 0), 12);
    if (br_lv >= 3)
        fx(MAGIC_T_THORN_B, 7 | BANK1, x - (br_dy ? 6 : 0), y - (br_dx ? 6 : 0), 10);
    v4(0x92, 0x5D, 6);
}

// ---- wards ---------------------------------------------------------------------
static void wisp_fx_drop(void) {
    u8 k;
    for (k = 0; k < 3; ++k) {
        u8 s = wisp_fx[k];
        if (s != 0xFF && entities[s].type == ENT_FX
            && entities[s].sprite_tile == MAGIC_T_WISP)
            entity_kill(s);
        wisp_fx[k] = 0xFF;
    }
}

static void tick_flame_ward(void) {
    u8 k, i;
    i16 wx[3], wy[3];
    entity_t *e;
    if (!(ward_beat & 3)) ward_angle = (u8)((ward_angle + 1) % 12);
    for (k = 0; k < 3; ++k) {
        u8 idx = (u8)((ward_angle + k * 4) % 12);
        u8 orb = fw_orb[spell_lv()];
        wx[k] = (i16)(HERO_X + ((i16)orb_x[idx] * (i16)orb) / 20);
        wy[k] = (i16)(HERO_Y + ((i16)orb_y[idx] * (i16)orb) / 20);
        if (wisp_cd[k]) wisp_cd[k]--;
    }
    // One pass over the room with a cheap box reject around the hero: a
    // wisp eats a hostile shot it touches and sears one body at a time.
    e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        u8 shot, box;
        i16 ex, ey, dx, dy;
        if (!(e->flags & EF_ACTIVE)) continue;
        shot = hostile_shot(e);
        if (shot) { ex = (i16)(e->x + 3); ey = (i16)(e->y + 3); }
        else if (is_body(e)) { ex = BODY_X(e); ey = BODY_Y(e); }
        else continue;
        dx = ex - HERO_X;
        dy = ey - HERO_Y;
        box = (u8)(fw_orb[spell_lv()] + 6);
        if (dx < -(i16)box || dx > (i16)box || dy < -(i16)box || dy > (i16)box) continue;
        for (k = 0; k < 3; ++k) {
            if (!(wisp_live & (u8)(1 << k)) || !wisp_charges[k]) continue;
            if (vdist(ex - wx[k], ey - wy[k]) > (shot ? 7 : 9)) continue;
            if (shot) {
                fx_spawn(SPR_FX_IMPACT, 4, e->x, e->y, 6);
                entity_kill(i);
                wisp_charges[k]--;
                v4(0x81, 0x33, 4);
                break;
            }
            if (!wisp_cd[k]) {
                hit_cx = HERO_X;
                hit_cy = HERO_Y;
                wisp_charges[k]--;
                wisp_cd[k] = 24;
                hit_body(i, 2, 1, QSTATUS_BURN, 0);
                break;
            }
        }
    }
    for (k = 0; k < 3; ++k) {
        u8 bit = (u8)(1 << k), s;
        if (!(wisp_live & bit)) continue;
        s = wisp_fx[k];
        if (!wisp_charges[k]) {
            wisp_live &= (u8)~bit;
            fx(SPR_FX_IMPACT, 4, wx[k], wy[k], 8);
            if (s != 0xFF && entities[s].type == ENT_FX
                && entities[s].sprite_tile == MAGIC_T_WISP)
                entity_kill(s);
            wisp_fx[k] = 0xFF;
            continue;
        }
        // Visual: one short FX per wisp, re-parked each frame.
        if (s == 0xFF || entities[s].type != ENT_FX
            || entities[s].sprite_tile != MAGIC_T_WISP
            || !(entities[s].flags & EF_ACTIVE)) {
            s = fx_spawn(MAGIC_T_WISP, 4 | BANK1, wx[k] - 4, wy[k] - 4, 4);
            wisp_fx[k] = s;
        }
        if (s != 0xFF) {
            entities[s].x = (ppos_t)(wx[k] - 4);
            entities[s].y = (ppos_t)(wy[k] - 4);
            entities[s].state_timer = 4;
        }
    }
    if (!wisp_live) magic_ward_ticks = 1;   // ends below
}

static void reflect_shot(u8 i) {
    entity_t *e = &entities[i];
    if (e->flags & EF_BOSS_PROJECTILE) {
        fx_spawn(SPR_FX_IMPACT, 7, e->x, e->y, 6);
        entity_kill(i);
        return;
    }
    e->flags |= EF_PLAYER_PROJ;
    if (!e->vx && !e->vy) {
        e->vx = (i8)(e->x + 3 > HERO_X ? 2 : -2);
    } else {
        e->vx = (i8)-e->vx;
        e->vy = (i8)-e->vy;
    }
    e->damage = 3;
    e->hp = 1;
    e->state = 0;
    e->state_timer = 60;
    memset(e->ai_data, 0, sizeof(e->ai_data));
    e->ai_data[1] = 16;
    e->palette = 7;
    fx(MAGIC_T_MIRROR, 7 | BANK1, e->x + 3, e->y + 3, 6);
    if (!mirror_voice) {
        v1(0x00, 0x80, 0x82, 1985, 5);
        mirror_voice = 6;
    }
}

static void tick_thorn_mirror(void) {
    u8 i;
    entity_t *e = entities;
    if (mirror_voice) mirror_voice--;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        if (!hostile_shot(e)) continue;
        if (vdist((i16)(e->x + 3) - HERO_X, (i16)(e->y + 3) - HERO_Y) > tm_r[spell_lv()])
            continue;
        reflect_shot(i);
    }
    if ((ward_beat & 7) == 0)
        fx(MAGIC_T_MIRROR, 7 | BANK1,
            HERO_X + ((ward_beat & 8) ? 9 : -9), HERO_Y, 6);
}

static void tick_wards(void) {
    if (!magic_ward_ticks) return;
    ward_beat++;
    if (magic_ward_kind == SPELL_FLAME_WARD) tick_flame_ward();
    else if (magic_ward_kind == SPELL_THORN_MIRROR) tick_thorn_mirror();
    else if (magic_ward_kind == SPELL_SHADOW_VEIL && (ward_beat & 15) == 0)
        fx(MAGIC_T_VEIL, 1 | BANK1, HERO_X, HERO_Y - 6, 8);
    if (--magic_ward_ticks == 0) {
        if (magic_ward_kind == SPELL_FLAME_WARD) wisp_fx_drop();
        wisp_live = 0;
        magic_ward_cd = 60;
    }
}

// ---- casting --------------------------------------------------------------------
static u8 mp_ok(u8 cost) {
    return POWERUP_FREE_MP() || player.mp >= cost;
}

static void spend(u8 spell, u8 cost) {
    if (!POWERUP_FREE_MP()) player.mp = (u8)(player.mp - cost);
    magic_last_spell = spell;
    magic_casts++;
    hud_redraw_mp();
}

static u8 cast_tap(u8 dir) {
    u8 c = player.class_id < 5 ? player.class_id : 0;
    u8 made = 0;
    switch (c) {
        case 0: { // MOONFIRE
            u8 lv = spell_lv();
            made = spawn_shot(SPELL_MOONFIRE, dir, spell_damage(mf_base[lv]), 3,
                mf_ttl[lv], 1, MAGIC_T_FIRE_A);
            if (made) {
                v4(0xA2, 0x36, 10);
                v1(0x16, 0x80, 0xA2, 1450, 10);
            }
            break;
        }
        case 1: { // THUNDER
            u8 lv = spell_lv();
            if (th_t) break;
            th_lv = lv;
            th_dmg = spell_damage(th_base[lv]);
            th_target = aimed_body(dir, th_aim[lv], 0xFF);
            if (th_target != 0xFF) {
                th_x = BODY_X(&entities[th_target]);
                th_y = BODY_Y(&entities[th_target]);
            } else {
                th_x = (i16)(HERO_X + dir8_dx[dir] * (i8)th_ahead[lv]);
                th_y = (i16)(HERO_Y + dir8_dy[dir] * (i8)th_ahead[lv]);
            }
            th_t = 1;
            th_chain = 0xFF;
            fx(MAGIC_T_BOLT, 5 | BANK1, th_x, th_y - 24, 6);
            v4(0x61, 0x21, 5);
            made = 1;
            break;
        }
        case 2: { // HEX
            u8 lv = spell_lv();
            made = spawn_shot(SPELL_HEX, dir, spell_damage(hx_base[lv]), 2,
                hx_ttl[lv], 1, MAGIC_T_HEX_A);
            if (made) v1(0x27, 0x40, 0x83, 1650, 10);
            break;
        }
        case 3: { // BLIZZARD
            u8 lv = spell_lv();
            ice_lv = lv;
            memset(ice_mask, 0, sizeof(ice_mask));
            made = spawn_shot(SPELL_BLIZZARD, dir, spell_damage(bz_base[lv]), 3,
                bz_ttl[lv], bz_hits[lv], MAGIC_T_ICE);
            if (made) v1(0x00, 0x00, 0x92, 1950, 8);
            break;
        }
        default: { // BRAMBLE
            u8 lv = spell_lv();
            if (br_t) break;
            br_x = HERO_X;
            br_y = HERO_Y;
            br_dx = dir8_dx[dir];
            br_dy = dir8_dy[dir];
            br_lv = lv;
            br_dmg = spell_damage(br_base[lv]);
            memset(br_mask, 0, sizeof(br_mask));
            br_step = 0;
            br_t = 1;
            made = 1;
            v4(0x72, 0x6E, 6);
            break;
        }
    }
    if (made) {
        spend((u8)(c << 1), 1);
        magic_tap_cd = tap_cd[c];
    }
    return made;
}

static u8 cast_ward(void) {
    u8 c = player.class_id < 5 ? player.class_id : 0;
    u8 i;
    switch (c) {
        case 0: { // FLAME WARD
            u8 lv = spell_lv();
            wisp_live = 7;
            for (i = 0; i < 3; ++i) {
                wisp_charges[i] = fw_chg[lv];
                wisp_cd[i] = 0;
                wisp_fx[i] = 0xFF;
            }
            ward_angle = 0;
            magic_ward_ticks = 180;
            v4(0xC3, 0x47, 18);
            v1(0x15, 0x80, 0xB3, 1300, 14);
            break;
        }
        case 1: { // STONESKIN + STATIC
            u8 lv = spell_lv();
            player.shield_timer = sk_time[lv];
            if (player.iframes < 8) player.iframes = 8;
            memset(ring_mask, 0, sizeof(ring_mask));
            hit_ring(HERO_X, HERO_Y, sk_r[lv], ring_mask, sk_pulse[lv], 4, QSTATUS_STOP, 8);
            for (i = 1; i < 8; i += 2)
                fx(MAGIC_T_FLASH, 5 | BANK1,
                    HERO_X + ring_x[i], HERO_Y + ring_y[i], 8);
            magic_ward_ticks = sk_time[lv];
            v4(0xF2, 0x66, 14);
            v1(0x00, 0xC0, 0xC2, 640, 14);
            break;
        }
        case 2: { // SHADOW VEIL
            u8 lv = spell_lv();
            status_player_apply(QSTATUS_HASTE, vl_ifr[lv]);
            if (player.iframes < vl_ifr[lv]) player.iframes = vl_ifr[lv];
            eat_shots(HERO_X, HERO_Y, vl_eat[lv]);
            for (i = 1; i < 8; i += 2)
                fx(MAGIC_T_VEIL, 1 | BANK1,
                    HERO_X + ring_x[i], HERO_Y + ring_y[i], 12);
            magic_ward_ticks = 160;
            v1(0x2F, 0x80, 0x72, 1900, 16);
            v4(0x51, 0x23, 12);
            break;
        }
        case 3: { // CURE
            u8 harm = STATUS_KIND_IS_HARM(player_status_kind);
            u8 can_heal = !STATUS_PLAYER_HEALING_BLOCKED()
                && player.hp < player.hp_max;
            if (magic_cure_used || (!can_heal && !harm)) return 0;
            {
                u8 lv = spell_lv();
                if (can_heal) {
                    player.hp = (u8)(player.hp + cu_heal[lv]);
                    if (player.hp > player.hp_max) player.hp = player.hp_max;
                }
                if (harm) status_player_cure();
                if (player.iframes < cu_ifr[lv]) player.iframes = cu_ifr[lv];
                hud_redraw_hp();
                magic_cure_used = 1;
                {
                    u8 step = (lv >= 2) ? 1 : 2;
                    for (i = (u8)(step == 1 ? 0 : 0); i < 8; i = (u8)(i + step))
                        fx(MAGIC_T_CURE, 1 | BANK1,
                            HERO_X + ring_x[i], HERO_Y + ring_y[i], 14);
                }
                fx(MAGIC_T_CURE, 1 | BANK1, HERO_X, HERO_Y - 12, 18);
                if (lv >= 1) {
                    fx(MAGIC_T_MOTE, 1 | BANK1, HERO_X - 6, HERO_Y - 16, 12);
                    fx(MAGIC_T_MOTE, 1 | BANK1, HERO_X + 6, HERO_Y - 16, 12);
                }
                if (lv >= 3) {
                    fx(MAGIC_T_CURE, 1 | BANK1, HERO_X, HERO_Y - 20, 16);
                    fx(MAGIC_T_CURE, 1 | BANK1, HERO_X, HERO_Y - 28, 14);
                }
            }
            sfx_play(SFX_HEART);
            magic_ward_cd = 120;
            break;
        }
        default:  // THORN MIRROR
            magic_ward_ticks = 120;
            ward_beat = 0;
            v1(0x00, 0x40, 0xA3, 1880, 10);
            break;
    }
    magic_ward_kind = (u8)((c << 1) | 1);
    ward_beat = 0;
    spend(magic_ward_kind, ward_cost[c]);
    return 1;
}

// ---- charge tell (Sword of Mana: the spirit circles the hero) ------------------
static void charge_tell(void) {
    u8 c = player.class_id < 5 ? player.class_id : 0;
    u8 pal = mp_ok(ward_cost[c]) && !magic_ward_ticks && !magic_ward_cd
        && !(c == 3 && magic_cure_used)
        ? class_pal[c] : (u8)(0 | BANK1);
    u8 h = magic_hold;
    if (h < MAGIC_MOTE_FRAMES) return;
    if (h < MAGIC_HOLD_FRAMES) {
        if (((h - MAGIC_MOTE_FRAMES) & 3) == 0)
            fx(MAGIC_T_MOTE, pal, HERO_X + ring_x[(h >> 2) & 7],
                HERO_Y + ring_y[(h >> 2) & 7], 6);
    } else if (h == MAGIC_HOLD_FRAMES) {
        u8 i;
        for (i = 1; i < 8; i += 2)
            fx(MAGIC_T_MOTE, pal, HERO_X + ring_x[i], HERO_Y + ring_y[i], 10);
        if (pal != (0 | BANK1)) v1(0x00, 0x80, 0x73, 1798, 6);
        else refuse();
    } else if ((h & 7) == 0) {
        fx(MAGIC_T_MOTE, pal, HERO_X + ring_x[(h >> 3) & 7],
            HERO_Y + ring_y[(h >> 3) & 7], 8);
    }
    if (h == MAGIC_HOLD_FRAMES + 3 && pal != (0 | BANK1))
        v1(0x00, 0x80, 0x73, 1849, 8);
}

static u8 hero_power_selected(void) {
    u8 id = player.active_item;
    return id != ITEM_ID_HOOKSHOT && id != ITEM_ID_BOOMERANG
        && id != ITEM_ID_MORNINGSTAR && id != ITEM_ID_BOMBS;
}

// A new room (entity_init_room) wipes every slot: drop tracked shots and
// pending strikes silently. Wards are self-effects and cross the doorway.
static void drop_room_state(void) {
    u8 k;
    for (k = 0; k < SHOTS; ++k) shot_slot[k] = 0xFF;
    for (k = 0; k < 3; ++k) wisp_fx[k] = 0xFF;
    th_t = 0;
    br_t = 0;
    memset(ice_mask, 0, sizeof(ice_mask));
    carrier = 0xFF;
    magic_cure_used = 0;
}

static void tick_live(u8 keys) {
    if (seen_serial != magic_room_serial) {
        seen_serial = magic_room_serial;
        drop_room_state();
    }
    if (magic_tap_cd) magic_tap_cd--;
    if (magic_ward_cd && !magic_ward_ticks) magic_ward_cd--;
    tick_shots(keys);
    tick_thunder();
    tick_bramble();
    tick_wards();
    carrier_close();
}

void magic_input(u8 keys, u8 pressed, u8 damage) BANKED {
    u8 hold;
    u8 b_edge = ((keys & J_B) && !prev_b) ? 1 : 0;
    prev_b = (keys & J_B) ? 1 : 0;
    // A gap in room frames (Pack, map, dialogue, transitions) drops a
    // charge, so a B release after a menu never ghost-casts.
    if ((u16)(loop_frame_counter - last_frame) > 8) {
        charging = 0;
        magic_hold = 0;
    }
    last_frame = loop_frame_counter;
    tick_live(keys);

    if (!hero_power_selected()) {
        charging = 0;
        magic_hold = 0;
        if ((pressed & J_B) && !(keys & J_A))
            secondary_fire(room_input_dir8(keys, player.facing),
                keys & DPAD, damage);
        return;
    }
    if (charging) {
        // A during the hold is the A+B chord: room.c already ran it this
        // frame. The spell never casts.
        if (keys & J_A) { charging = 0; magic_hold = 0; return; }
        if (STATUS_PLAYER_MUTED()) {
            charging = 0; magic_hold = 0; refuse(); return;
        }
        if (keys & J_B) {
            if (magic_hold < 250) magic_hold++;
            charge_tell();
            return;
        }
        hold = magic_hold;
        charging = 0;
        magic_hold = 0;
        if (hold >= MAGIC_HOLD_FRAMES) {
            u8 c = player.class_id < 5 ? player.class_id : 0;
            if (magic_ward_ticks || magic_ward_cd || !mp_ok(ward_cost[c])
                || !cast_ward()) refuse();
        } else {
            if (magic_tap_cd || !mp_ok(1)
                || !cast_tap(room_input_dir8(keys, player.facing))) refuse();
        }
        return;
    }
    // Own B edge: a press that lands on a hitstop frame (the room skips
    // its input edge then) still starts the charge on the next room frame.
    if (b_edge && !(keys & J_A)) {
        if (STATUS_PLAYER_MUTED() || !mp_ok(1)) { refuse(); return; }
        charging = 1;
        magic_hold = 1;
    }
}

// Every room entry and Pack resume: reload the spell tiles (other screens
// reuse bank-1 OBJ VRAM) and drop any charge.
void magic_room_enter(void) BANKED {
    if (!magic_inited) magic_reset();
    VBK_REG = 1;
    set_sprite_data(MAGIC_TILE, MAGIC_TILE_COUNT, magic_art);
    VBK_REG = 0;
    charging = 0;
    magic_hold = 0;
}

void magic_reset(void) BANKED {
    magic_inited = 1;
    charging = 0;
    magic_hold = 0;
    drop_room_state();
    magic_ward_ticks = 0;
    magic_ward_kind = 0xFF;
    magic_ward_cd = 0;
    magic_tap_cd = 0;
    wisp_live = 0;
    magic_last_spell = 0xFF;
    magic_casts = 0;
}
