#pragma bank 255
#include <gb/gb.h>

#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "render/tiles.h"
#include "content.h"

// Per-AI scratch layout in entity_t:
//   ai_data[0] = content enemy id (all AIs)
//   Walker:  state = dir8, state_timer = ticks until new dir
//   Chaser:  state_timer = frame divider
//   Charger: ai_data[2] = mode (0 wander 1 telegraph 2 charge 3 recover),
//            ai_data[3] = mode timer, ai_data[4] = locked dir8

// Map content enemy_id to OBJ tile slot in VRAM.
static u8 sprite_for_enemy(u8 enemy_content_id) {
    switch (enemy_content_id) {
        case 0: return SPR_ENEMY_CRAWLER;
        case 1: return SPR_BOSS;
        case 2: return SPR_ENEMY_HORNET;
        case 3: return SPR_ENEMY_SKELETON;
        case 4: return SPR_ENEMY_ORC;
        case 5: return SPR_ENEMY_WISP;
        default: return SPR_ENEMY_CRAWLER;
    }
}

// Per-enemy OBJ palette (loaded in room_enter): crawler blue(3),
// hornet amber(5, shares coin gold), skeleton bone(0), orc green(7),
// sentinel granite(6), wisp bone-ghost(0).
static u8 palette_for_enemy(u8 enemy_content_id) {
    switch (enemy_content_id) {
        case 1:  return 0x06;
        case 2:  return 0x05;
        case 3:  return 0x00;
        case 4:  return 0x07;
        case 5:  return 0x00;
        default: return 0x03;
    }
}

u8 enemy_spawn(u8 enemy_content_id, u8 tile_x, u8 tile_y) BANKED {
    u8 idx;
    entity_t *e;
    if (enemy_content_id >= N_ENEMIES) return 0xFF;
    idx = entity_spawn(ENT_ENEMY);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    {
        const enemy_def_t *def = &enemies[enemy_content_id];
        e->x           = FIX8((i16)tile_x * 8);
        e->y           = FIX8((i16)tile_y * 8);
        e->vx = e->vy  = 0;
        e->sprite_tile = sprite_for_enemy(enemy_content_id);
        e->palette     = palette_for_enemy(enemy_content_id);
        def;
        e->hp          = def->stats.hp;
        e->damage      = def->stats.damage;
        e->ai_data[0]  = enemy_content_id;
        e->state       = (u8)(rng_next_u8() & 0x07);
        e->state_timer = 30;
        e->hitbox      = (6 << 4) | 6;
    }
    return idx;
}

// Try to move an enemy 1px by (dx,dy); blocked by solid tiles + room bounds.
// Returns 1 if moved.
u8 enemy_try_step(entity_t *e, i8 dx, i8 dy) BANKED {
    i16 nx = (i16)(FIX8_TO_INT(e->x) + dx);
    i16 ny = (i16)(FIX8_TO_INT(e->y) + dy);
    if (nx < 8 || nx >= (i16)((ROOM_W - 1) * 8)) return 0;
    if (ny < 8 || ny >= (i16)((ROOM_H - 1) * 8)) return 0;
    // Center-point tile check (cheap; 8x8 bodies)
    if (!room_tile_walkable(room_tile_at_px(nx + 4, ny + 4))) return 0;
    e->x = FIX8(nx);
    e->y = FIX8(ny);
    return 1;
}

// ---------------- Walker: random 8-dir wander --------------------------

static void walker_tick(entity_t *e) {
    if (e->state_timer == 0) {
        e->state       = (u8)(rng_next_u8() & 0x07);
        e->state_timer = (u8)(20 + (rng_next_u8() & 0x1F));
    }
    e->state_timer--;

    if ((e->state_timer & 0x03) == 0) {
        i8 dx = dir8_dx[e->state & 0x07];
        i8 dy = dir8_dy[e->state & 0x07];
        if (!enemy_try_step(e, dx, dy)) {
            e->state_timer = 0;   // blocked — pick a new direction next tick
        }
    }
}

// ---------------- Chaser: home toward player ---------------------------

static void chaser_tick(entity_t *e, u8 speed) {
    u8 div = (speed >= 96) ? 2 : 3;   // faster stat = steps more often
    e->state_timer++;
    if (e->state_timer < div) return;
    e->state_timer = 0;
    {
        i16 ex = FIX8_TO_INT(e->x);
        i16 ey = FIX8_TO_INT(e->y);
        i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
        i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
        // Step each axis independently; if the diagonal is blocked one axis
        // still slides along the obstacle.
        if (sx) enemy_try_step(e, sx, 0);
        if (sy) enemy_try_step(e, 0, sy);
    }
}

// ---------------- Charger: telegraph then dash --------------------------

#define CHG_WANDER    0
#define CHG_TELEGRAPH 1
#define CHG_CHARGE    2
#define CHG_RECOVER   3

static void charger_tick(entity_t *e, const enemy_def_t *def) {
    u8 mode = e->ai_data[2];

    if (mode == CHG_WANDER) {
        walker_tick(e);
        // Alignment check: same column or row as the player → wind up
        {
            i16 ex = FIX8_TO_INT(e->x);
            i16 ey = FIX8_TO_INT(e->y);
            i16 adx = (i16)player.x - ex; if (adx < 0) adx = -adx;
            i16 ady = (i16)player.y - ey; if (ady < 0) ady = -ady;
            if (adx < 8) {
                e->ai_data[4] = ((i16)player.y > ey) ? 4 : 0;   // S or N
                e->ai_data[2] = CHG_TELEGRAPH;
                e->ai_data[3] = def->ai_p0;                      // telegraph_ticks
            } else if (ady < 8) {
                e->ai_data[4] = ((i16)player.x > ex) ? 2 : 6;   // E or W
                e->ai_data[2] = CHG_TELEGRAPH;
                e->ai_data[3] = def->ai_p0;
            }
        }
    } else if (mode == CHG_TELEGRAPH) {
        // Wind-up: hold still (visible pause reads as the tell)
        if (--e->ai_data[3] == 0) {
            e->ai_data[2] = CHG_CHARGE;
            e->ai_data[3] = 60;   // max charge duration
        }
    } else if (mode == CHG_CHARGE) {
        i8 dx = dir8_dx[e->ai_data[4] & 0x07];
        i8 dy = dir8_dy[e->ai_data[4] & 0x07];
        // 2 px per tick dash
        u8 ok = enemy_try_step(e, dx, dy);
        if (ok) ok = enemy_try_step(e, dx, dy);
        if (!ok || --e->ai_data[3] == 0) {
            e->ai_data[2] = CHG_RECOVER;
            e->ai_data[3] = 25;
        }
    } else {   // CHG_RECOVER
        if (--e->ai_data[3] == 0) {
            e->ai_data[2] = CHG_WANDER;
            e->state_timer = 0;
        }
    }
}

// ---------------- Shooter: drift + aimed shots ---------------------------

static void shooter_tick(entity_t *e, const enemy_def_t *def) {
    // Slow wander (half walker cadence) + fire toward player on a timer.
    // ai_data[1] = fire countdown.
    if ((e->state_timer & 0x07) == 0) {
        i8 dx = dir8_dx[e->state & 0x07];
        i8 dy = dir8_dy[e->state & 0x07];
        if (!enemy_try_step(e, dx, dy)) {
            e->state = (u8)(rng_next_u8() & 0x07);
        }
    }
    e->state_timer++;
    if (e->state_timer > 40) {
        e->state_timer = 0;
        e->state = (u8)(rng_next_u8() & 0x07);
    }

    if (e->ai_data[1] == 0) {
        e->ai_data[1] = def->ai_p0;   // fire_rate
        {
            i16 ex = FIX8_TO_INT(e->x);
            i16 ey = FIX8_TO_INT(e->y);
            i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
            i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
            projectile_spawn_enemy(ex, ey, sx, sy, def->stats.damage);
        }
    } else {
        e->ai_data[1]--;
    }
}

// ---------------- Boss: bullet-hell patterns -----------------------------
// Slow chase + volleys. Each of the 9 large stage bosses fires a distinct
// pattern (ai_data[2] = pattern id = stage), so they read differently even
// though they share this driver. The 16x16 mini-boss keeps the classic
// alternating-spread. Cadence tightens below half HP (enrage).
//
// Boss ai_data layout:
//   [0]=content id  [1]=volley timer  [2]=pattern id (0..8)  [3]=giant flag
//   [4]=burst counter (Reaper)  [5]=rotation counter  [6]=max hp (enrage)

// Index into dir8_* that points from (cx,cy) toward the player.
static u8 aim_dir8(i16 cx, i16 cy) {
    i8 sx = ((i16)player.x > cx) ? 1 : ((i16)player.x < cx) ? -1 : 0;
    i8 sy = ((i16)player.y > cy) ? 1 : ((i16)player.y < cy) ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 0;   // on top of player -> fire up
}

// Fire one enemy bullet along dir8 index d, scaled to `spd` px/tick.
static void boss_shot(i16 cx, i16 cy, u8 d, i8 spd, u8 dmg) {
    projectile_spawn_enemy_v(cx, cy, (i8)(dir8_dx[d] * spd), (i8)(dir8_dy[d] * spd), dmg);
}

static void boss_tick(entity_t *e) {
    if (e->ai_data[6] == 0) e->ai_data[6] = e->hp;

    // Creep toward the player (1px every 3rd tick)
    e->state_timer++;
    if (e->state_timer >= 3) {
        e->state_timer = 0;
        {
            i16 ex = FIX8_TO_INT(e->x);
            i16 ey = FIX8_TO_INT(e->y);
            i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
            i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
            if (sx) enemy_try_step(e, sx, 0);
            if (sy) enemy_try_step(e, 0, sy);
        }
    }

    if (e->ai_data[1] != 0) { e->ai_data[1]--; return; }

    {
        u8 giant = e->ai_data[3];
        u8 dmg   = e->damage;
        u8 d, k;
        i16 cx = FIX8_TO_INT(e->x) + (giant ? 12 : 4);
        i16 cy = FIX8_TO_INT(e->y) + (giant ? 12 : 4);
        u8 cadence;

        if (!giant) {
            // Mini-boss Sentinel: 4 shots, alternating cardinal/diagonal.
            for (d = (u8)(e->ai_data[5] & 1); d < 8; d = (u8)(d + 2))
                boss_shot(cx, cy, d, 2, dmg);
            cadence = 70;
        } else switch (e->ai_data[2]) {
            case 1:   // Serpent — rotating 4-cross (sweeps a spiral)
                for (k = 0; k < 4; ++k)
                    boss_shot(cx, cy, (u8)((e->ai_data[5] + k * 2) & 7), 2, dmg);
                cadence = 20;
                break;
            case 2:   // Maw — fast aimed 3-shot breath
                d = aim_dir8(cx, cy);
                boss_shot(cx, cy, d, 3, dmg);
                boss_shot(cx, cy, (u8)((d + 1) & 7), 3, dmg);
                boss_shot(cx, cy, (u8)((d + 7) & 7), 3, dmg);
                cadence = 28;
                break;
            case 3:   // Spider — alternating cardinal/diagonal web + aimed
                for (d = (u8)(e->ai_data[5] & 1); d < 8; d = (u8)(d + 2))
                    boss_shot(cx, cy, d, 2, dmg);
                boss_shot(cx, cy, aim_dir8(cx, cy), 3, dmg);
                cadence = 38;
                break;
            case 4:   // Mire — chaotic scatter spray (random dir + speed)
                for (k = 0; k < 6; ++k)
                    boss_shot(cx, cy, (u8)rng_range(8), (i8)(1 + rng_range(3)), dmg);
                cadence = 26;
                break;
            case 5:   // Reaper — 3-shot aimed burst, then a long pause
                boss_shot(cx, cy, aim_dir8(cx, cy), 3, dmg);
                e->ai_data[4]++;
                if (e->ai_data[4] < 3) { e->ai_data[1] = 8; e->ai_data[5]++; return; }
                e->ai_data[4] = 0;
                cadence = 72;
                break;
            case 6:   // Golem — slow heavy full ring (dense wall)
                for (d = 0; d < 8; ++d) boss_shot(cx, cy, d, 1, dmg);
                cadence = 58;
                break;
            case 7:   // Hydra — three aimed streams at staggered speeds
                d = aim_dir8(cx, cy);
                boss_shot(cx, cy, d, 1, dmg);
                boss_shot(cx, cy, d, 2, dmg);
                boss_shot(cx, cy, d, 3, dmg);
                boss_shot(cx, cy, (u8)((d + 1) & 7), 2, dmg);
                boss_shot(cx, cy, (u8)((d + 7) & 7), 2, dmg);
                cadence = 24;
                break;
            case 8:   // Void Lord — rotating fast cross + diagonal ring + aimed
                for (k = 0; k < 4; ++k)
                    boss_shot(cx, cy, (u8)((e->ai_data[5] + k * 2) & 7), 3, dmg);
                for (d = 1; d < 8; d = (u8)(d + 2)) boss_shot(cx, cy, d, 1, dmg);
                boss_shot(cx, cy, aim_dir8(cx, cy), 2, dmg);
                cadence = 30;
                break;
            case 0:   // Colossus — full ring + aimed (the classic)
            default:
                for (d = 0; d < 8; ++d) boss_shot(cx, cy, d, 2, dmg);
                boss_shot(cx, cy, aim_dir8(cx, cy), 2, dmg);
                cadence = 55;
                break;
        }

        e->ai_data[5]++;
        // Enrage below half HP — only tighten the longer cadences so short
        // burst timers can't underflow.
        if (cadence > 34 && e->hp < (u8)(e->ai_data[6] >> 1))
            cadence = (u8)(cadence - 18);
        e->ai_data[1] = cadence;
    }
}

// ---------------- Dispatch ----------------------------------------------

void enemy_update(entity_t *e, u8 idx) BANKED {
    const enemy_def_t *def = &enemies[e->ai_data[0]];
    idx;
    if (e->ai_data[0] == 1) { boss_tick(e); return; }   // Sentinel
    switch (def->ai_kind) {
        case AI_CHASER:  chaser_tick(e, def->stats.speed); break;
        case AI_CHARGER: charger_tick(e, def);             break;
        case AI_SHOOTER: shooter_tick(e, def);             break;
        default:         walker_tick(e);                   break;
    }
}
