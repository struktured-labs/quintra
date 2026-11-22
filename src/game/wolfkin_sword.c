#pragma bank 23
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

#define SLASH_LIFE 8
#define STAB_LIFE  10
#define SLASH_SEGS 3
#define STAB_SEGS  4
#define DIAG_SEGS  3
#define SLASH_REACH 22
#define STAB_REACH  32

static u8 sword_hit[4];
static u8 sword_hit_n;
static u8 tiles_loaded;

static u8 on_longblade(void) {
    return (u8)(player.class_id == 0
        && player.starter_weapon == classes[0].starter_weapon);
}

void wolfkin_sword_load(void) BANKED {
    if (!on_longblade()) return;
    wolfkin_sword_tiles_load();
    tiles_loaded = 1;
}

u8 wolfkin_sword_already_hit(u8 enemy_idx) BANKED {
    u8 i;
    for (i = 0; i < sword_hit_n; ++i)
        if (sword_hit[i] == enemy_idx) return 1;
    return 0;
}

void wolfkin_sword_mark_hit(u8 enemy_idx) BANKED {
    if (sword_hit_n >= 4) return;
    if (wolfkin_sword_already_hit(enemy_idx)) return;
    sword_hit[sword_hit_n++] = enemy_idx;
}

u8 wolfkin_sword_live(const entity_t *e) BANKED {
    u8 age = e->ai_data[0];
    if (e->ai_data[7] & 0x80) {
        /* slash: contact frames 2..5 */
        return (u8)(age >= 2 && age <= 5);
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

static void place_seg(entity_t *e, u8 dir, u8 slash, u8 seg, u8 age) {
    i16 reach, x, y;
    i8 dx = dir8_dx[dir];
    i8 dy = dir8_dy[dir];
    if (slash) {
        /* 12x12 boxes cannot sit at the tip: that leaves a hole in the
         * near arc. The center segment tucks against the body edge; the
         * two side segments are fanned on the perpendicular so the 12x12
         * still reaches SLASH_REACH past the edge and covers the diagonals. */
        reach = SLASH_REACH;
        if (age < 2) reach = (i16)(reach >> 1);
        if (seg == 0) {
            x = body_edge_x(dir);
            y = body_edge_y(dir);
            if (dx == 0) x = (i16)(player.x + 2);
            if (dy == 0) y = (i16)(player.y + 2);
        } else {
            i16 ext = (i16)(reach - 12);
            i8 rx, ry;
            if (ext < 0) ext = 0;
            /* Perpendicular of facing (rotate 90°): east fans N/S, etc. */
            rx = (i8)-dy;
            ry = dx;
            if (seg == 2) {
                rx = (i8)-rx;
                ry = (i8)-ry;
            }
            x = (i16)(body_edge_x(dir) + dx * ext + (i16)rx * 12);
            y = (i16)(body_edge_y(dir) + dy * ext + (i16)ry * 12);
        }
    } else {
        reach = (i16)((seg + 1) * 8);
        if (age < (u8)(seg + 1))
            reach = (i16)((age + 1) * 8);
        if (reach > STAB_REACH) reach = STAB_REACH;
        x = (i16)(body_edge_x(dir) + dx * (i16)(reach - 8));
        y = (i16)(body_edge_y(dir) + dy * (i16)(reach - 8));
    }
    e->x = (ppos_t)x;
    e->y = (ppos_t)y;
    e->vx = 0;
    e->vy = 0;
}

void wolfkin_sword_update(entity_t *e) BANKED {
    u8 dir = (u8)(e->ai_data[7] & 7);
    u8 slash = (u8)(e->ai_data[7] & 0x80);
    u8 age = e->ai_data[0];
    if (age < 0xF0) e->ai_data[0] = (u8)(age + 1);
    place_seg(e, dir, slash, e->state, e->ai_data[0]);
    /* Tile: slash uses 0..3, cardinal stab 4..7 (H) or 8..11 (V),
       diagonal 12..14, chosen by dir and segment. */
    {
        u8 tile;
        if (slash) tile = (u8)(SPR_SWORD_BASE + (e->state & 3));
        else if (dir & 1) tile = (u8)(SPR_SWORD_BASE + 12 + (e->state % 3));
        else if (dir == 0 || dir == 4)
            tile = (u8)(SPR_SWORD_BASE + 8 + (e->state & 3));
        else
            tile = (u8)(SPR_SWORD_BASE + 4 + (e->state & 3));
        e->sprite_tile = tile;
        e->ai_data[4] = 0;
        if (dir == 6 || dir == 7 || dir == 5) e->ai_data[4] |= PROJ_VIS_FLIP_X;
        if (dir == 4 || dir == 3 || dir == 5) e->ai_data[4] |= PROJ_VIS_FLIP_Y;
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
    e->hp = slash ? 3 : 2;
    e->state_timer = life;
    e->damage = dmg;
    e->hitbox = slash ? 0xCC : 0x88;
    e->palette = SPR_SWORD_PROP;
    e->sprite_tile = SPR_SWORD_BASE;
    place_seg(e, dir, slash, seg, 0);
    if (g_player_ricochet) e->ai_data[3] |= PROJ_FLAG_RICOCHET;
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
    sword_hit_n = 0;
    life = slash ? SLASH_LIFE : STAB_LIFE;
    n = slash ? SLASH_SEGS : ((dir & 1) ? DIAG_SEGS : STAB_SEGS);
    first = 0xFF;
    for (i = 0; i < n; ++i) {
        shot = spawn_seg(dir, slash, i, damage, life);
        if (first == 0xFF) first = shot;
        if (shot != 0xFF && powerup_id == POWERUP_LONGREACH) {
            /* Cap growth: +4 slash / +8 stab, never a mid-range wall. */
            u8 hb = entities[shot].hitbox;
            u8 add = slash ? 4 : 8;
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
    if (shot != 0xFF && !muted) player.will_charge = 0;
    echo = (u8)(weapon_dmg + atk + 2);
    if (room_weapon_surge_ticks) echo++;
    powerup_echo_primary(shot, dir, echo);
    cd = slash ? weapon_rate : 26;
    player.fire_cooldown = player_fire_delay(cd);
}
