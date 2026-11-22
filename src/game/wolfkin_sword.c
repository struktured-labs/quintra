#pragma bank 28
#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/powerup.h"
#include "game/wolfkin_sword.h"
#include "game/room.h"
#include "audio/sfx.h"
#include "content.h"

BANKREF(wolfkin_sword_fire)

extern const u8 wolfkin_sword_tiles[];
void wolfkin_sword_tiles_load(void) BANKED;

/* Claw Sword (docs/superpowers/specs/2026-11-22-wolfkin-claw-sword-spin.md).
 * Neutral A is a 360-degree spin: a 3-frame cock-back, then the blade steps
 * clockwise through all 8 headings, 2 frames each, and returns to the front.
 * A held d-pad is the unchanged long stab. */
#define STAB_LIFE   10
#define STAB_SEGS   4
#define DIAG_SEGS   3
#define DIAG_STEP   6          /* diagonal chain overlaps 2 px: no pinched joints */
#define SPIN_WINDUP 3
#define SPIN_STEP   2
#define SPIN_STEPS  8          /* 8 x 45 deg = one full turn */
#define SPIN_LIFE   (SPIN_WINDUP + (SPIN_STEPS + 1) * SPIN_STEP)   /* 21 */
#define SPIN_SEGS   3          /* guard, blade, tip */
#define SPIN_SMEAR  3          /* segment index of the trailing arc */
#define SPIN_CD     30         /* base recovery; SPD can shorten it to SPIN_CD_MIN */
#define SPIN_CD_MIN 26         /* life + 5 f open window, so the latch never resets mid-swing */
#define STAB_CD_MIN (STAB_LIFE + 2)
#define SPIN_HP     8          /* pierce: the latch, not hp, ends a crowd swing */
#define SWORD_HIT_MAX 8

static u8 sword_hit[SWORD_HIT_MAX];
static u8 sword_hit_n;
static u8 tiles_loaded;

static u8 on_longblade(void) {
    return (u8)(player.class_id == 0
        && player.starter_weapon == classes[0].starter_weapon);
}

/* Every room entry and Pack resume (room_music.c) plus the first swing.
 * The tiles live in a reserved bank-1 OBJ window, but screens outside the
 * room (title, class select, vignettes) may rewrite bank 1, so the room
 * entry hook always refreshes them. */
void wolfkin_sword_load(void) BANKED {
    if (!on_longblade()) return;
    wolfkin_sword_tiles_load();
    tiles_loaded = 1;
}

u8 wolfkin_sword_already_hit(u8 enemy_idx) BANKED {
    u8 i;
    /* A full latch ends the swing's damage: never re-hit an unrecorded body. */
    if (sword_hit_n >= SWORD_HIT_MAX) return 1;
    for (i = 0; i < sword_hit_n; ++i)
        if (sword_hit[i] == enemy_idx) return 1;
    return 0;
}

void wolfkin_sword_mark_hit(u8 enemy_idx) BANKED {
    u8 i;
    for (i = 0; i < sword_hit_n; ++i)
        if (sword_hit[i] == enemy_idx) return;
    if (sword_hit_n < SWORD_HIT_MAX) sword_hit[sword_hit_n++] = enemy_idx;
}

/* Spin step 0..SPIN_STEPS once the cock-back ends; 0xFF during it.
 * Age is 1-based in updates (spawn draws age 0): ages 0..3 cock back,
 * each step owns exactly 2 updates, step 8 (front again) is ages 20..21. */
static u8 spin_step(u8 age) {
    u8 k;
    if (age <= SPIN_WINDUP) return 0xFF;
    k = (u8)((u8)(age - SPIN_WINDUP - 1) >> 1);
    return k > SPIN_STEPS ? SPIN_STEPS : k;
}

u8 wolfkin_sword_live(const entity_t *e) BANKED {
    u8 age = e->ai_data[0];
    if (e->ai_data[7] & 0x80) {
        u8 k = spin_step(age);
        if (k == 0xFF) return 0;
        /* The arc trail only exists (and only cuts) once the blade has moved. */
        if (e->state == SPIN_SMEAR) return (u8)(k >= 1);
        return 1;
    }
    /* stab: live once the segment has grown out (age > seg) */
    return (u8)(age > e->state);
}

static i16 body_edge_x(u8 dir) {
    i16 x = player.x;
    if (dir8_dx[dir] > 0) x = (i16)(x + 16);
    else if (dir8_dx[dir] < 0) x = (i16)(x - 8);
    else x = (i16)(x + 4);
    return x;
}

static i16 body_edge_y(u8 dir) {
    i16 y = player.y;
    if (dir8_dy[dir] > 0) y = (i16)(y + 16);
    else if (dir8_dy[dir] < 0) y = (i16)(y - 8);
    else y = (i16)(y + 4);
    return y;
}

/* Trailing-arc tile centres 15 deg behind the blade (30 + 45h deg),
 * radius 25 px from Wolfkin's centre, as top-left offsets from player.x/y,
 * so the arc kisses the back of the tip instead of floating. */
static const i8 smear_ox[8] = { 17, 28, 26, 10, -8, -20, -18, -2 };
static const i8 smear_oy[8] = { -18, -2, 16, 28, 26, 10, -9, -20 };

static u8 spin_dir(u8 aim, u8 age) {
    u8 k = spin_step(age);
    if (k == 0xFF) return (u8)((aim + 7) & 7);   /* cocked back one heading */
    return (u8)((aim + k) & 7);
}

static void place_seg(entity_t *e, u8 dir, u8 slash, u8 seg, u8 age) {
    i16 x, y;
    i8 dx, dy;
    if (slash) {
        u8 d = spin_dir(dir, age);
        if (seg == SPIN_SMEAR) {
            u8 h = (u8)((d + 7) & 7);
            x = (i16)(player.x + smear_ox[h]);
            y = (i16)(player.y + smear_oy[h]);
        } else {
            i16 off;
            dx = dir8_dx[d];
            dy = dir8_dy[d];
            /* Centre-relative: cardinal tiles at 12/20/28 px, diagonal at
             * 8/14/20 px per axis (28 px Euclidean), clear of the body corner. */
            if (dx && dy) off = (i16)(8 + DIAG_STEP * seg);
            else off = (i16)(12 + 8 * seg);
            x = (i16)(player.x + 4 + dx * off);
            y = (i16)(player.y + 4 + dy * off);
        }
        /* Hitboxes anchor top-left; centre the 10x10 (Longreach 12x12) box
         * on the 8x8 tile so reach is the same on every side. */
        {
            u8 c = (u8)((u8)((e->hitbox >> 4) - 8) >> 1);
            x = (i16)(x - c);
            y = (i16)(y - c);
        }
    } else {
        u8 n = seg;
        dx = dir8_dx[dir];
        dy = dir8_dy[dir];
        if (age < n) n = age;           /* thrust grows out from the hand */
        if (dx && dy) {
            x = (i16)(body_edge_x(dir) + dx * (i16)(DIAG_STEP * n));
            y = (i16)(body_edge_y(dir) + dy * (i16)(DIAG_STEP * n));
        } else {
            x = (i16)(body_edge_x(dir) + dx * (i16)(8 * n));
            y = (i16)(body_edge_y(dir) + dy * (i16)(8 * n));
        }
    }
    e->x = (ppos_t)x;
    e->y = (ppos_t)y;
    e->vx = 0;
    e->vy = 0;
}

/* Tile + flip for a blade segment pointing along dir. `piece` is the tile
 * within the chain (cardinal 0 pommel..3 tip, diagonal 0 hilt..2 tip). */
static void blade_tile(entity_t *e, u8 dir, u8 piece, u8 spin) {
    u8 f = 0;
    u8 tile;
    if (dir & 1) {
        tile = (u8)(SPR_CLAW_DIAG + piece);
        if (dir == 7 || dir == 5) f |= PROJ_VIS_FLIP_X;
        if (dir == 3 || dir == 5) f |= PROJ_VIS_FLIP_Y;
    } else if (dir == 0 || dir == 4) {
        tile = (u8)(SPR_CLAW_V + piece);
        if (dir == 4) f |= PROJ_VIS_FLIP_Y;
        /* Spin turns clockwise: keep the pale cutting edge leading. */
        if (spin && dir == 4) f |= PROJ_VIS_FLIP_X;
    } else {
        tile = (u8)(SPR_CLAW_H + piece);
        if (dir == 6) f |= PROJ_VIS_FLIP_X;
        if (spin && dir == 6) f |= PROJ_VIS_FLIP_Y;
    }
    e->sprite_tile = tile;
    e->ai_data[4] = f;
}

void wolfkin_sword_update(entity_t *e) BANKED {
    u8 dir = (u8)(e->ai_data[7] & 7);
    u8 slash = (u8)(e->ai_data[7] & 0x80);
    u8 age = e->ai_data[0];
    u8 seg = e->state;
    if (age < 0xF0) e->ai_data[0] = (u8)(age + 1);
    age = e->ai_data[0];
    place_seg(e, dir, slash, seg, age);
    if (!slash) {
        blade_tile(e, dir, seg, 0);
        return;
    }
    if (seg == SPIN_SMEAR) {
        u8 h = (u8)((spin_dir(dir, age) + 7) & 7);
        u8 f = 0;
        if (spin_step(age) == 0xFF || spin_step(age) == 0) {
            e->sprite_tile = SPR_CLAW_BLANK;
            e->ai_data[4] = 0;
            return;
        }
        e->sprite_tile = (h == 0 || h == 3 || h == 4 || h == 7)
            ? SPR_CLAW_SMEAR_A : SPR_CLAW_SMEAR_B;
        if (h >= 4) f |= PROJ_VIS_FLIP_X;
        if (h >= 2 && h <= 5) f |= PROJ_VIS_FLIP_Y;
        e->ai_data[4] = f;
        return;
    }
    {
        u8 d = spin_dir(dir, age);
        /* Cardinal spin skips the pommel tile (it sits in the paw). */
        blade_tile(e, d, (d & 1) ? seg : (u8)(seg + 1), 1);
    }
}

static u8 spawn_seg(u8 dir, u8 slash, u8 seg, u8 dmg, u8 life) {
    u8 idx = entity_spawn(ENT_PROJECTILE);
    entity_t *e;
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    e->flags |= EF_PLAYER_PROJ;
    e->state = seg;
    e->ai_data[0] = 0;
    e->ai_data[1] = 1; /* fire */
    e->ai_data[2] = 1; /* physical */
    e->ai_data[5] = 0xFF;
    e->ai_data[6] = PROJ_AUX_WOLFKIN_FANG;
    e->ai_data[7] = (u8)(dir | (slash ? 0x80 : 0));
    e->hp = slash ? SPIN_HP : 2;
    e->state_timer = life;
    e->damage = dmg;
    e->hitbox = slash ? 0xAA : 0x88;
    e->palette = SPR_SWORD_PROP;
    place_seg(e, dir, slash, seg, 0);
    if (slash) {
        if (seg == SPIN_SMEAR) e->sprite_tile = SPR_CLAW_BLANK;
        else blade_tile(e, (u8)((dir + 7) & 7),
            ((dir + 7) & 1) ? seg : (u8)(seg + 1), 1);
    } else {
        blade_tile(e, dir, seg, 0);
    }
    /* No ricochet on parented blade segments: they never travel. */
    return idx;
}

u8 wolfkin_beam_spawn(i16 x, i16 y, u8 dir, u8 dmg, u8 ttl, u8 aux) BANKED {
    u8 idx = entity_spawn(ENT_PROJECTILE);
    entity_t *e;
    i8 dx, dy;
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    dx = dir8_dx[dir];
    dy = dir8_dy[dir];
    e->flags |= EF_PLAYER_PROJ;
    e->x = (ppos_t)x;
    e->y = (ppos_t)y;
    e->vx = (i8)((i16)dx * 3);
    e->vy = (i8)((i16)dy * 3);
    e->sprite_tile = (u8)SPR_SWORD_BEAM_TILE;
    e->palette = SPR_SWORD_PROP;
    e->hp = 1;
    e->state_timer = ttl;
    e->hitbox = 0x88;
    e->damage = dmg;
    e->ai_data[1] = 1;
    e->ai_data[6] = aux;
    e->ai_data[5] = 0xFF;
    if (dx < 0) e->ai_data[4] |= PROJ_VIS_FLIP_X;
    if (dy > 0) e->ai_data[4] |= PROJ_VIS_FLIP_Y;
    return idx;
}

u8 wolfkin_sword_fire(u8 dir, u8 slash, u8 damage) BANKED {
    u8 n, i, first, life, shot;
    if (dir >= 8) dir = 0;
    if (!tiles_loaded) wolfkin_sword_load();
    life = slash ? SPIN_LIFE : STAB_LIFE;
    n = slash ? (SPIN_SEGS + 1) : ((dir & 1) ? DIAG_SEGS : STAB_SEGS);
    /* Never draw a stub sword: wait for room for the whole blade. */
    {
        u8 j, free = 0;
        for (j = 0; j < MAX_ENTITIES; ++j)
            if (!(entities[j].flags & EF_ACTIVE)) ++free;
        if (free < n) return 0xFF;
    }
    sword_hit_n = 0;
    first = 0xFF;
    for (i = 0; i < n; ++i) {
        shot = spawn_seg(dir, slash, i, damage, life);
        if (first == 0xFF) first = shot;
        if (shot != 0xFF && powerup_id == POWERUP_LONGREACH) {
            /* Cap growth: +2 spin / +8 stab, never a mid-range wall. */
            u8 hb = entities[shot].hitbox;
            u8 add = slash ? 2 : 8;
            u8 w = (u8)((hb >> 4) + add);
            u8 h = (u8)((hb & 0x0F) + add);
            if (w > 15) w = 15;
            if (h > 15) h = 15;
            /* Keep stab narrow in the cross axis. */
            if (!slash) {
                if (dir == 2 || dir == 6) h = (u8)(entities[shot].hitbox & 0x0F);
                else if (dir == 0 || dir == 4) w = (u8)(entities[shot].hitbox >> 4);
            }
            entities[shot].hitbox = (u8)((w << 4) | h);
        }
    }
    if (player.hp == player.hp_max) {
        u8 ttl = 36;
        if (powerup_id == POWERUP_LONGREACH) ttl = (u8)(ttl + (ttl >> 1));
        shot = wolfkin_beam_spawn(
            body_edge_x(dir), body_edge_y(dir), dir, 3, ttl,
            PROJ_AUX_SWORD_BEAM);
        if (shot != 0xFF && (g_player_attack_traits & ATTACK_TRAIT_SPLASH
            || powerup_id == POWERUP_BLAST))
            entities[shot].ai_data[3] |= PROJ_FLAG_SPLASH;
    }
    sfx_play_weapon(PROJ_SPIKE);
    return first;
}

extern u8 player_penta_aim;
extern u8 room_weapon_surge_ticks;
u8 room_input_dir8(u8 keys, u8 facing) BANKED;
void powerup_echo_primary(u8 primary, u8 dir, u8 damage) BANKED;

void wolfkin_sword_try_fire(u8 keys, u8 atk, u8 weapon_dmg,
    u8 weapon_rate, u8 muted) BANKED {
    u8 pad, slash, dir, dmg, shot, echo, cd;
    if (player.fire_cooldown) return;
    pad = (u8)(keys & (J_LEFT | J_RIGHT | J_UP | J_DOWN));
    slash = pad ? 0 : 1;
    dir = player_penta_aim ? (u8)(player_aim_dir & 7)
        : room_input_dir8(keys, player.facing);
    dmg = (u8)(weapon_dmg + atk);
    if (room_weapon_surge_ticks) dmg++;
    dmg = (u8)(dmg + (slash ? 2 : 6));
    shot = wolfkin_sword_fire(dir, slash, dmg);
    if (shot == 0xFF) return;   /* no slots: retry next frame, no cooldown */
    if (!muted) player.will_charge = 0;
    echo = (u8)(weapon_dmg + atk + 2);
    if (room_weapon_surge_ticks) echo++;
    powerup_echo_primary(shot, dir, echo);
    (void)weapon_rate;
    cd = slash ? SPIN_CD : 26;
    cd = player_fire_delay(cd);
    /* SPD may shorten recovery, never the swing itself (latch safety). */
    if (slash) { if (cd < SPIN_CD_MIN) cd = SPIN_CD_MIN; }
    else if (cd < STAB_CD_MIN) cd = STAB_CD_MIN;
    player.fire_cooldown = cd;
}
