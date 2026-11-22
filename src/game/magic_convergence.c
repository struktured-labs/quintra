#pragma bank 23

#include <gb/gb.h>
#include <string.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/loop.h"
#include "game/magic.h"
#include "game/magic_cv.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/rare_enemy.h"
#include "game/room.h"
#include "game/hexa_boss.h"
#include "game/status.h"
#include "game/will_levels.h"
#include "render/large_boss.h"
#include "render/class_palettes.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

/* Spirit Convergence residue and fire (#151 section 10). Tables live in
 * bank 31 (magic.c); this pinned bank holds the code so bank 31 stays
 * under the ceiling. */

#define CV_TAG 0xC0
#define CV_SUB_BURST 0
#define CV_SUB_SHARD 1
#define CV_SUB_CHAIN 2

#define BODY_X(e) ((i16)((e)->x + (i16)((e)->hitbox >> 5)))
#define BODY_Y(e) ((i16)((e)->y + (i16)(((e)->hitbox & 0x0F) >> 1)))
#define HERO_X ((i16)player.x + 6)
#define HERO_Y ((i16)player.y + 6)
#define BANK1 0x08

u8 magic_cv_busy;

static u8 cv_slot[8];
static i16 cv_lx[8], cv_ly[8];
static u8 cv_dir[8];
static u8 cv_lv, cv_shards, cv_chain_used, cv_chain_from;
static u8 cv_burst_dmg, cv_pal, cv_borrow, cv_borrow_slot;
static u16 cv_saved[4];
static u16 cv_reach_mul, cv_dmg_mul;

static u8 spell_lv_local(void) {
    u8 lv = player.maxwill_level;
    if (lv < MAXWILL_MIN) lv = MAXWILL_MIN;
    if (lv > MAXWILL_MAX) lv = MAXWILL_MAX;
    return (u8)(lv - 1);
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

static u8 cv_alive(u8 s) {
    entity_t *e;
    if (s == 0xFF) return 0;
    e = &entities[s];
    return (e->flags & EF_ACTIVE) && e->type == ENT_PROJECTILE
        && (e->ai_data[7] & 0xF0) == CV_TAG;
}

static void cv_restore_pal(void) {
    if (!cv_borrow) return;
    palette_obj_load(cv_borrow_slot, cv_saved);
    cv_borrow = 0;
}

static u8 cv_pick_pal(void) {
    u8 c = player.class_id < 5 ? player.class_id : 0;
    u8 slot = magic_cv_pal_at(c);
    if (c == 2 || c == 3) {
        memcpy(cv_saved, obj_pal_cache[slot], 8);
        cv_borrow_slot = slot;
        cv_borrow = 1;
        class_palette_load_obj(slot, c);
    }
    return slot;
}

static u8 dir_toward(i16 dx, i16 dy) {
    u16 ax = dx < 0 ? (u16)-dx : (u16)dx;
    u16 ay = dy < 0 ? (u16)-dy : (u16)dy;
    if (ax > (ay << 1)) return dx < 0 ? 6 : 2;
    if (ay > (ax << 1)) return dy < 0 ? 0 : 4;
    if (dx >= 0) return dy < 0 ? 1 : 3;
    return dy < 0 ? 7 : 5;
}

static u16 vdist(i16 dx, i16 dy) {
    u16 ax = (u16)(dx < 0 ? -dx : dx);
    u16 ay = (u16)(dy < 0 ? -dy : dy);
    if (ax < ay) { u16 t = ax; ax = ay; ay = t; }
    return (u16)(ax + (ay >> 2) + (ay >> 3));
}

static u8 nearest_body(i16 x, i16 y, u16 range, u8 skip) {
    u8 i, best = 0xFF;
    u16 bd = range;
    entity_t *e = entities;
    for (i = 0; i < MAX_ENTITIES; ++i, ++e) {
        u16 d;
        if (i == skip || !is_body(e)) continue;
        d = vdist(BODY_X(e) - x, BODY_Y(e) - y);
        if (d < bd) { bd = d; best = i; }
    }
    return best;
}

static u8 cv_spawn_extra(i16 x, i16 y, i8 dx, i8 dy, u8 dmg,
    u8 tile, u8 pal, u8 ttl, u8 sub) {
    u8 s;
    entity_t *e;
    if (x < 8 || y < 8 || x > (i16)room_world_width - 8
        || y > (i16)room_world_height - 8) return 0xFF;
    s = entity_spawn(ENT_PROJECTILE);
    if (s == 0xFF) return 0xFF;
    e = &entities[s];
    e->flags |= EF_PLAYER_PROJ;
    e->x = (ppos_t)x;
    e->y = (ppos_t)y;
    e->vx = (i8)(dx + dx);
    e->vy = (i8)(dy + dy);
    if (!e->vx && !e->vy) e->vx = 2;
    e->sprite_tile = tile;
    e->palette = pal;
    e->hp = 1;
    e->state_timer = ttl;
    e->hitbox = 0x77;
    e->damage = dmg ? dmg : 1;
    e->ai_data[1] = g_shot_element;
    e->ai_data[3] = PROJ_FLAG_CONVERGENCE;
    e->ai_data[7] = (u8)(CV_TAG | sub);
    return s;
}

static void cv_shatter(i16 x, i16 y, u8 dir) {
    u8 cap, a, b, pal;
    if (cv_lv < 1) return;
    cap = (cv_lv >= 3) ? 8 : 4;
    if (cv_shards >= cap) return;
    pal = (u8)(cv_pal | BANK1);
    a = (u8)((dir + 2) & 7);
    b = (u8)((dir + 6) & 7);
    if (cv_spawn_extra(x, y, dir8_dx[a], dir8_dy[a],
            (u8)((cv_burst_dmg + 1) >> 1), MAGIC_T_ICE, pal, 12,
            CV_SUB_SHARD) != 0xFF)
        cv_shards++;
    if (cv_shards >= cap) return;
    if (cv_spawn_extra(x, y, dir8_dx[b], dir8_dy[b],
            (u8)((cv_burst_dmg + 1) >> 1), MAGIC_T_ICE, pal, 12,
            CV_SUB_SHARD) != 0xFF)
        cv_shards++;
}

static void cv_fire_chain(void) {
    u8 src, dst, dmg, ttl, dir;
    i16 x, y;
    entity_t *e;
    if (cv_chain_used || cv_chain_from == 0xFF) return;
    src = cv_chain_from;
    cv_chain_from = 0xFF;
    cv_chain_used = 1;
    e = &entities[src];
    if (!is_body(e)) return;
    x = BODY_X(e);
    y = BODY_Y(e);
    dst = nearest_body(x, y,
        (u16)((48u * cv_reach_mul + 128) >> 8), src);
    if (dst == 0xFF) return;
    dir = dir_toward(BODY_X(&entities[dst]) - x, BODY_Y(&entities[dst]) - y);
    dmg = (u8)((cv_burst_dmg + 1) >> 1);
    if (!dmg) dmg = 1;
    /* Search range is (48 * reach_mul) >> 8 (48/72/84). Spawn at speed 4
     * with ttl (12 * reach_mul) >> 8 so the bolt can actually cover it.
     * cv_spawn_extra doubles the dir vector, so pass 2*dir8 for speed 4. */
    ttl = (u8)((12u * cv_reach_mul + 128) >> 8);
    if (!ttl) ttl = 1;
    cv_spawn_extra(x, y, (i8)(dir8_dx[dir] * 2), (i8)(dir8_dy[dir] * 2),
        dmg, MAGIC_T_BOLT, cv_pal, ttl, CV_SUB_CHAIN);
    fx_spawn(MAGIC_T_BOLT, 5, (i16)(x - 4), (i16)(y - 12), 8);
}

void magic_convergence_reset(void) BANKED {
    memset(cv_slot, 0xFF, sizeof(cv_slot));
    cv_chain_from = 0xFF;
    cv_restore_pal();
    magic_cv_busy = 0;
}

void magic_convergence_fire(u8 damage) BANKED {
    u8 sd, lv, dmg, pal;
    u16 scaled;
    lv = spell_lv_local();
    dmg = damage;
    cv_reach_mul = magic_cv_reach_at(lv);
    cv_dmg_mul = magic_cv_dmg_at(lv);
    if (lv) {
        scaled = (u16)(((u32)damage * cv_dmg_mul + 128) >> 8);
        if (scaled > 255) scaled = 255;
        if (!scaled) scaled = 1;
        dmg = (u8)scaled;
    }
    cv_lv = lv;
    cv_shards = 0;
    cv_chain_used = 0;
    cv_chain_from = 0xFF;
    cv_burst_dmg = dmg;
    pal = cv_pick_pal();
    cv_pal = pal;
    magic_cv_busy = 1;
    for (sd = 0; sd < 8; ++sd) {
        u8 shot = projectile_spawn_player(dir8_dx[sd], dir8_dy[sd],
            dmg, PROJ_SPIKE);
        cv_slot[sd] = 0xFF;
        if (shot == 0xFF) continue;
        entities[shot].ai_data[3] |= PROJ_FLAG_CONVERGENCE;
        entities[shot].ai_data[7] = (u8)(CV_TAG | CV_SUB_BURST);
        entities[shot].palette = pal;
        if (lv) {
            scaled = entities[shot].state_timer;
            scaled = (u16)((scaled * cv_reach_mul + 128) >> 8);
            if (scaled > 255) scaled = 255;
            if (!scaled) scaled = 1;
            entities[shot].state_timer = (u8)scaled;
        }
        cv_slot[sd] = shot;
        cv_lx[sd] = (i16)(entities[shot].x + 3);
        cv_ly[sd] = (i16)(entities[shot].y + 3);
        cv_dir[sd] = sd;
    }
    fx_spawn(MAGIC_T_FLASH, pal, (i16)(HERO_X - 4), (i16)(HERO_Y - 4), 6);
    if (lv >= 1) {
        u8 c = player.class_id < 5 ? player.class_id : 0;
        if (c == 1)
            fx_spawn(MAGIC_T_FLASH, pal, (i16)(HERO_X - 4), (i16)(HERO_Y - 14), 8);
        else if (c == 4) {
            fx_spawn(MAGIC_T_MOTE, (u8)(pal | BANK1),
                (i16)(HERO_X - 4), (i16)(HERO_Y - 4), 2);
            fx_spawn(MAGIC_T_MOTE, (u8)(pal | BANK1),
                (i16)(HERO_X + 2), (i16)(HERO_Y - 4), 2);
        }
    }
}

u8 magic_convergence_hit(u8 j, u8 i, u8 survives) BANKED {
    entity_t *shot;
    u8 sub, c;
    (void)survives;
    shot = &entities[i];
    if ((shot->ai_data[7] & 0xF0) != CV_TAG) return 1;
    sub = (u8)(shot->ai_data[7] & 15);
    if (sub == CV_SUB_SHARD) return 1;
    if (sub == CV_SUB_CHAIN) {
        status_enemy_apply(j, QSTATUS_SLOW, 12);
        return 1;
    }
    if (cv_lv < 2) return 1;
    c = player.class_id < 5 ? player.class_id : 0;
    if (c == 0) status_enemy_apply(j, QSTATUS_BURN, 0);
    else if (c == 1) {
        if (!cv_chain_used && cv_chain_from == 0xFF) cv_chain_from = j;
    } else if (c == 2) {
        status_enemy_apply(j, is_heavy(&entities[j], j)
            ? QSTATUS_MUTE : QSTATUS_CONFUSION, 16);
    } else if (c == 3) status_enemy_apply(j, QSTATUS_STOP, 12);
    else status_enemy_apply(j, QSTATUS_POISON, 60);
    return 1;
}

void magic_convergence_tick(void) BANKED {
    u8 sd, live, c, motes;
    live = 0;
    motes = 0;
    c = player.class_id < 5 ? player.class_id : 0;
    for (sd = 0; sd < 8; ++sd) {
        u8 s = cv_slot[sd];
        if (s == 0xFF) continue;
        if (cv_alive(s)) {
            entity_t *e = &entities[s];
            cv_lx[sd] = (i16)(e->x + 3);
            cv_ly[sd] = (i16)(e->y + 3);
            live++;
            if (cv_lv >= 1 && motes < 4 && ((sd + loop_frame_counter) & 3) == 0) {
                if (c == 0)
                    fx_spawn(MAGIC_T_MOTE, (u8)(cv_pal | BANK1),
                        (i16)(cv_lx[sd] - 4), (i16)(cv_ly[sd] - 4), 6);
                else if (c == 2)
                    fx_spawn(MAGIC_T_VEIL, cv_pal,
                        (i16)(cv_lx[sd] - 4), (i16)(cv_ly[sd] - 4), 4);
                else if (c == 4 && cv_lv >= 3)
                    fx_spawn(MAGIC_T_MOTE, (u8)(cv_pal | BANK1),
                        (i16)(cv_lx[sd] - 4), (i16)(cv_ly[sd] - 4), 4);
                motes++;
            }
        } else {
            if (c == 3) cv_shatter(cv_lx[sd], cv_ly[sd], cv_dir[sd]);
            cv_slot[sd] = 0xFF;
        }
    }
    if (cv_chain_from != 0xFF) cv_fire_chain();
    if (!live && cv_borrow) {
        for (sd = 0; sd < MAX_ENTITIES; ++sd) {
            if (cv_alive(sd)) { live = 1; break; }
        }
        if (!live) cv_restore_pal();
    }
    if (!live && !cv_borrow) magic_cv_busy = 0;
}
