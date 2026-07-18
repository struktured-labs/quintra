#pragma bank 2
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/enemy_mirror.h"
#include "game/enemy_spore.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

// Per-AI scratch layout in entity_t:
//   ai_data[0] = content enemy id (all AIs)
//   Walker:  state = dir8, state_timer = ticks until new dir
//   Chaser:  state_timer = frame divider
//   Charger: ai_data[2] = mode (0 wander 1 telegraph 2 charge 3 recover),
//            ai_data[3] = mode timer, ai_data[4] = locked dir8

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
        e->sprite_tile = def->sprite_set;
        e->palette     = def->palette;
        e->hp          = def->stats.hp;
        e->damage      = def->stats.damage;
        e->ai_data[0]  = enemy_content_id;
        e->state       = (u8)(rng_next_u8() & 0x07);
        e->state_timer = 30;
        // Flutterbats need champion-sized navigation clearance. Their old
        // 8px footprint could enter one-tile pockets that a 12px hero could
        // neither enter nor reliably reach with a cardinal melee attack.
        if (enemy_content_id == ENEMY_FLUTTERBAT) {
            e->hitbox = (u8)0xAA;
        // Bruiser tier (orc 4, bomber 6, warlock 8) and the Sentinel
        // mini-boss (1) render 16x16 — give them a bigger hitbox so the
        // larger body is hittable and its contact reach matches its size.
        } else if (enemy_content_id == ENEMY_STONE_SENTINEL || enemy_content_id == ENEMY_ORC
            || enemy_content_id == ENEMY_BOMBER || enemy_content_id == ENEMY_WARLOCK) {
            e->hitbox = (u8)0xDD;
        } else {
            e->hitbox = (6 << 4) | 6;
        }
    }
    return idx;
}

// Try to move an enemy 1px by (dx,dy); blocked by solid tiles + room bounds.
// Returns 1 if moved. The Skeleton uses the hero's 12px feet-box clearance:
// it is a persistent chaser and can otherwise enter a one-tile pocket a
// melee hero cannot enter, turning a sealed room into an unwinnable softlock.
// Large bruisers retain their wider 16px movement envelope; other small
// enemies keep their authored, more agile movement identities.
u8 enemy_try_step(entity_t *e, i8 dx, i8 dy) BANKED {
    i16 nx = (i16)(FIX8_TO_INT(e->x) + dx);
    i16 ny = (i16)(FIX8_TO_INT(e->y) + dy);
    i16 ext = ((e->hitbox >> 4) >= 10) ? 14
        : (e->ai_data[0] == ENEMY_SKELETON) ? 13 : 6; // far-corner inset
    if (nx < 8 || ny < 8) return 0;
    if (nx + ext >= (i16)((ROOM_W - 1) * 8 + 8)
        || ny + ext >= (i16)((ROOM_H - 1) * 8 + 8)) return 0;
    if (!room_tile_walkable(room_tile_at_px(nx + 1,   ny + 1))
        || !room_tile_walkable(room_tile_at_px(nx + ext, ny + 1))
        || !room_tile_walkable(room_tile_at_px(nx + 1,   ny + ext))
        || !room_tile_walkable(room_tile_at_px(nx + ext, ny + ext))) return 0;
    e->x = FIX8(nx);
    e->y = FIX8(ny);
    return 1;
}

// Bullet helpers (defined with the boss section below)
static u8 aim_dir8(i16 cx, i16 cy);
static void boss_shot(i16 cx, i16 cy, u8 d, i8 spd, u8 dmg);
static void chaser_tick(entity_t *e, u8 speed);

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

// ---------------- Folding Star: diagonal replication -------------------

static void replicator_tick(entity_t *e, const enemy_def_t *def) {
    // state 0 = contracted and vulnerable; state 1 = expanded/untouchable.
    // ai_data[1] is the phase clock, ai_data[2] selects the odd 7/13/9 beat,
    // ai_data[3] rotates the diagonal sequence.
    static const u8 beat[3] = { 7, 13, 9 };
    if (e->ai_data[1] == 0) {
        if (e->state == 0) {
            e->state = 1;
            e->ai_data[1] = def->ai_p0;
            e->palette = 0x00; // pale and diffuse while expanded
        } else {
            e->state = 0;
            e->ai_data[1] = def->ai_p1;
            e->palette = 0x05; // bright core announces damage window
            sfx_play(SFX_WEAK);
        }
    }
    e->ai_data[1]--;

    if (e->state == 0) {
        // Contract toward the player: a slow, readable diagonal hunt.
        if ((e->ai_data[1] & 3) == 0) {
            i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
            i8 dx = (player.x > ex) ? 1 : -1;
            i8 dy = (player.y > ey) ? 1 : -1;
            enemy_try_step(e, dx, dy);
        }
        return;
    }

    // Expanded: shed four short-lived replicas on diagonal rays. They are FX,
    // not extra hostiles, so room-clear accounting and the 32-entity budget
    // remain stable. The core itself steps through the same diagonal sequence.
    if ((e->ai_data[1] % beat[e->ai_data[2] % 3]) == 0) {
        i16 x = FIX8_TO_INT(e->x), y = FIX8_TO_INT(e->y);
        u8 d = (u8)(6 + ((e->ai_data[3] & 3) << 1));
        fx_spawn(e->sprite_tile, 0x05, x - d, y - d, 16);
        fx_spawn(e->sprite_tile, 0x05, x + d, y - d, 16);
        fx_spawn(e->sprite_tile, 0x05, x - d, y + d, 16);
        fx_spawn(e->sprite_tile, 0x05, x + d, y + d, 16);
        e->ai_data[2] = (u8)((e->ai_data[2] + 1) % 3);
        e->ai_data[3]++;
        enemy_try_step(e, dir8_dx[(u8)((e->ai_data[3] * 2 + 1) & 7)],
                          dir8_dy[(u8)((e->ai_data[3] * 2 + 1) & 7)]);
    }
}

// Keese-like cadence: cling motionless, flutter diagonally, dart, settle.
static void flutterbat_tick(entity_t *e) {
    if (e->state_timer == 0) {
        e->state = (u8)((e->state + 1) % 3);
        e->state_timer = (e->state == 0) ? (u8)(28 + (rng_next_u8() & 31))
                       : (e->state == 1) ? (u8)(36 + (rng_next_u8() & 15)) : 14;
        e->ai_data[2] = (u8)(rng_next_u8() | 1); // diagonal direction seed
    }
    e->state_timer--;
    if (e->state == 0) return;
    if ((e->state_timer & ((e->state == 2) ? 1 : 3)) == 0) {
        u8 d = (u8)((e->ai_data[2] + ((e->state_timer >> 2) & 2)) & 7);
        i8 dx = dir8_dx[d], dy = dir8_dy[d];
        u8 moved;
        // Resolve diagonals by axis. A direct diagonal lets this 8px flyer cut
        // across two solid corners into a notch no 12px champion can enter;
        // axis motion keeps the Keese-like slant in open space and slides the
        // bat along either wall when only one component is legal.
        if (dx && dy) {
            moved = enemy_try_step(e, dx, 0);
            if (enemy_try_step(e, 0, dy)) moved = 1;
        } else {
            moved = enemy_try_step(e, dx, dy);
        }
        if (!moved) e->state_timer = 0;
    }
}

// Metroid-like latch: pursue, attach, pulse-drain, and ride the hero until
// killed. Dashing shakes it loose through the hero's extended iframes.
static void leech_tick(entity_t *e) {
    if (e->ai_data[6]) {
        e->x = FIX8((i16)player.x + 4);
        e->y = FIX8((i16)player.y + 1);
        if (player.iframes >= 12) { // dodge dash shakes the latch
            e->ai_data[6] = 0; e->state_timer = 30; return;
        }
        if (++e->ai_data[5] >= 45) {
            e->ai_data[5] = 0;
            if (player.hp > 1) { player.hp--; hud_redraw_hp(); sfx_play(SFX_HURT); }
        }
        return;
    }
    chaser_tick(e, 72);
    if (e->state_timer == 0 && aabb_overlap_player(e)) {
        e->ai_data[6] = 1; e->ai_data[5] = 0; sfx_play(SFX_HURT);
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
        // Pursue one axis at a time. If it blocks, keep one perpendicular
        // edge-follow direction until the pursuit axis opens; reverse only
        // when that slide also blocks. This avoids pillar oscillation.
        u8 moved = sx ? enemy_try_step(e, sx, 0)
                      : (sy ? enemy_try_step(e, 0, sy) : 1);
        if (!moved) {
            i8 side = (e->state & 1) ? 1 : -1;
            if (!enemy_try_step(e, sx ? 0 : side, sx ? side : 0)) e->state++;
        }
    }
}

// First hit raises a counter-rush (armed by combat.c), followed by a long,
// pale punish window. ai_data[6]=guard cooldown; state 0=ready, 1=rushing,
// 2=exposed. ai_data[1] is a private movement divider.
static void counter_guard_tick(entity_t *e, const enemy_def_t *def) {
    if (e->ai_data[6] > 0) e->ai_data[6]--;
    if (e->state == 1) {
        if (e->state_timer > 0) e->state_timer--;
        if ((e->state_timer & 1) == 0) {
            i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
            i16 dx = (i16)player.x - ex, dy = (i16)player.y - ey;
            i16 ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
            if (ax >= ay) enemy_try_step(e, dx > 0 ? 1 : -1, 0);
            else enemy_try_step(e, 0, dy > 0 ? 1 : -1);
        }
        if (e->state_timer == 0) {
            e->state = 2;
            e->palette = 0;       // pale = shield down, safe to punish
        }
        return;
    }
    if (e->state == 2) {
        if (e->ai_data[6] == 0) {
            e->state = 0;
            e->palette = def->palette;
            sfx_play(SFX_TICK);
        } else if ((++e->ai_data[1] & 7) == 0) {
            // Keep light pressure without erasing the exposed opening.
            chaser_tick(e, 48);
        }
        return;
    }
    // Shield-ready stance advances deliberately; the bright gold silhouette
    // and first blocked hit teach the bait-then-punish rhythm.
    if ((++e->ai_data[1] & 3) == 0) chaser_tick(e, def->stats.speed);
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
        // Wind-up: hold still + blink white + click, same language as
        // the boss volley tells (a pause alone reads as idling)
        if (e->ai_data[3] == def->ai_p0 && e->ai_data[7] == 0) {
            e->ai_data[7] = (u8)(def->ai_p0 > 20 ? 20 : def->ai_p0);
            sfx_play(SFX_TICK);
        }
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
            // Shot pattern from content: ai_p2 low nibble = kind
            // (0 single, 1 fan, 2 ring), high nibble = N.
            i16 ex = FIX8_TO_INT(e->x);
            i16 ey = FIX8_TO_INT(e->y);
            u8 pat = (u8)(def->ai_p2 & 0x0F);
            u8 n   = (u8)(def->ai_p2 >> 4);
            // Shooter identities also differ kinetically: wisps cast slow
            // readable motes, warlocks own the baseline, Cinder Maws spit
            // fast bolts. Pattern density and bullet speed are independent.
            u8 shot_speed = (e->ai_data[0] == ENEMY_WISP) ? 1
                : (e->ai_data[0] == ENEMY_CINDER_MAW
                   || e->ai_data[0] == ENEMY_DREAD_BELL) ? 3 : 2;
            u8 d, k;
            switch (pat) {
                case 1:   // Fan(n): aimed center + (n-1)/2 each side
                    d = aim_dir8(ex, ey);
                    boss_shot(ex, ey, d, shot_speed, def->stats.damage);
                    for (k = 1; k <= (u8)(n >> 1); ++k) {
                        boss_shot(ex, ey, (u8)((d + k) & 7), shot_speed, def->stats.damage);
                        boss_shot(ex, ey, (u8)((d + 8 - k) & 7), shot_speed, def->stats.damage);
                    }
                    break;
                case 2: { // Ring(n): n of the 8 directions, evenly spaced
                    u8 step = (n != 0 && n <= 8) ? (u8)(8 / n) : 2;
                    for (d = 0; d < 8; d = (u8)(d + step))
                        boss_shot(ex, ey, d, shot_speed, def->stats.damage);
                    break;
                }
                default: { // Single: aimed sign-step (original behavior)
                    i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
                    i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
                    projectile_spawn_enemy_v(ex, ey,
                        (i8)(sx * shot_speed), (i8)(sy * shot_speed), def->stats.damage);
                    break;
                }
            }
        }
    } else {
        e->ai_data[1]--;
    }
}

// ---------------- Turret: stationary rotating-spread bullet-hell zoner ----
// Doesn't move. Fires a 4-way cross that rotates each volley by ai_p0, on
// an ai_p1-frame cadence, with the standard white-blink + click telegraph.
// ai_data[1] = fire cooldown, ai_data[5] = rotation counter.
static void turret_tick(entity_t *e, const enemy_def_t *def) {
    i16 cx = FIX8_TO_INT(e->x) + 4;
    i16 cy = FIX8_TO_INT(e->y) + 4;
    if (e->ai_data[1] != 0) {
        e->ai_data[1]--;
        // Void Lord world-collapse telegraph: one flickering safe pocket.
        // ai_data[4]=1 while charging; ai_data[5] selects a corner.
        if (e->ai_data[3] && e->ai_data[2] == 8 && e->ai_data[4]
            && (e->ai_data[1] & 7) == 0) {
            static const u8 safe_x[4] = { 20, 124, 20, 124 };
            static const u8 safe_y[4] = { 20, 20, 100, 100 };
            fx_spawn(SPR_FX_IMPACT, 1, safe_x[e->ai_data[5] & 3],
                safe_y[e->ai_data[5] & 3], 10);
            sfx_play(SFX_TICK);
        }
        if (e->ai_data[1] == 8 && e->ai_data[7] == 0) {
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }
    {
        u8 k;
        for (k = 0; k < 4; ++k)
            boss_shot(cx, cy, (u8)((e->ai_data[5] + k * 2) & 7), 2, def->stats.damage);
    }
    e->ai_data[5] = (u8)(e->ai_data[5] + (def->ai_p0 ? def->ai_p0 : 1));
    e->ai_data[1] = def->ai_p1 ? def->ai_p1 : 55;   // fire_rate
}

// ---------------- Teleporter: vanish, reappear beside the player ---------
// ai_data[1] = phase timer, ai_data[2] = phase (0 present, 1 gone).
// While gone the shade parks at y=200 — offscreen, uncollidable,
// unhittable — then materializes a fair distance from the player.

static void teleport_tick(entity_t *e, const enemy_def_t *def) {
    if (e->ai_data[2] == 0) {
        chaser_tick(e, 48);                       // slow stalk
        if (++e->ai_data[1] >= def->ai_p0) {      // blink_rate
            e->ai_data[1] = 0;
            e->ai_data[2] = 1;
            fx_spawn(SPR_FX_IMPACT, 2,
                (i16)FIX8_TO_INT(e->x), (i16)FIX8_TO_INT(e->y), 8);
            e->x = FIX8(80);
            e->y = FIX8(200);                     // limbo
        }
    } else if (++e->ai_data[1] >= 45) {           // gone ~0.75s, then try
        u8 tries = 8;
        e->ai_data[1] = 0;
        while (tries--) {
            u8 span = (u8)(def->ai_p1 << 1);      // appear_dist each way
            i16 nx = (i16)player.x
                + (i16)(rng_next_u8() % span) - (i16)def->ai_p1;
            i16 ny = (i16)player.y
                + (i16)(rng_next_u8() % span) - (i16)def->ai_p1;
            i16 adx = nx - (i16)player.x; if (adx < 0) adx = -adx;
            i16 ady = ny - (i16)player.y; if (ady < 0) ady = -ady;
            if (adx + ady < 16) continue;          // never on top of you
            if (nx < 8 || nx >= (i16)((ROOM_W - 1) * 8)) continue;
            if (ny < 8 || ny >= (i16)((ROOM_H - 1) * 8)) continue;
            if (!room_tile_walkable(room_tile_at_px(nx + 4, ny + 4))) continue;
            e->x = FIX8(nx);
            e->y = FIX8(ny);
            e->ai_data[2] = 0;
            e->ai_data[7] = 6;                    // materialize shimmer
            fx_spawn(SPR_FX_IMPACT, 2, nx, ny, 8);
            break;
        }
        // No spot found: stay gone, retry in another 45 frames
    }
}

// ---------------- Boss: bullet-hell patterns -----------------------------
// Slow chase + volleys. Each of the 9 large stage bosses fires a distinct
// pattern (ai_data[2] = pattern id = stage), so they read differently even
// though they share this driver. The 16x16 mini-boss keeps the classic
// alternating-spread. Cadence tightens below half HP (enrage).
//
// Boss ai_data layout:
//   [0]=content id  [1]=volley timer  [2]=pattern id (0..8)
//   [3]=bit0 giant flag; bit7 one-time giant phase break
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

    // A boss used to turn its below-half enrage into a nearly invisible
    // cadence subtraction.  Give every large encounter one readable second
    // phase instead: the slow four-way riftbreak is announced by a shake and
    // bright flash, then the existing pattern resumes in its faster state.
    // The marker shares the giant byte's high bit—mini-boss counters and all
    // instrumentation keep their established entity layout.
    if ((e->ai_data[3] & 1) && !(e->ai_data[3] & 0x80)
        && e->hp <= (u8)(e->ai_data[6] >> 1)) {
        i16 bx = FIX8_TO_INT(e->x) + 12;
        i16 by = FIX8_TO_INT(e->y) + 12;
        u8 d;
        e->ai_data[3] |= 0x80;
        e->ai_data[1] = 30;   // readable beat before the normal next volley
        e->ai_data[7] = 20;   // visible white riftbreak flash
        room_shake(1, 12);
        sfx_play(SFX_ROAR);
        for (d = 0; d < 8; d = (u8)(d + 2))
            boss_shot(bx, by, d, 1, e->damage);
        return;
    }

    // Creep toward the player. The Void Lord keeps its pressure through
    // bullets and World Collapse; moving its 32px body every third tick made
    // that body-pin a harsher, less readable threat than either intended
    // mechanic. Its slower fifth-tick drift preserves the closing silhouette
    // without invalidating ranged positioning.
    e->state_timer++;
    if (e->state_timer >= ((e->ai_data[3] & 1) && e->ai_data[2] == 8 ? 5 : 3)) {
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

    if (e->ai_data[1] != 0) {
        e->ai_data[1]--;
        // Telegraph: blink white + a quiet click ~8 frames before every
        // volley (reuses the hit-flash pathway) so patterns read as
        // dodgeable, not random.
        if (e->ai_data[1] == 8 && e->ai_data[7] == 0) {
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }

    {
        u8 giant = e->ai_data[3] & 1;
        u8 dmg   = e->damage;
        u8 d, k;
        // Both mini-boss and giant are 16x16+; center the volley origin.
        i16 cx = FIX8_TO_INT(e->x) + (giant ? 12 : 8);
        i16 cy = FIX8_TO_INT(e->y) + (giant ? 12 : 8);
        u8 cadence;

        if (!giant) {
            // Three distinct mini-boss archetypes (ai_data[2] = variant:
            // 0 Sentinel / 1 Orc / 2 Skeleton) so they play differently,
            // not just recolored. Enrage tightens the slow ones below.
            switch (e->ai_data[2]) {
                case 1:   // Orc — relentless aimed 3-shot spear, fast & heavy
                    d = aim_dir8(cx, cy);
                    boss_shot(cx, cy, d, 3, dmg);
                    boss_shot(cx, cy, (u8)((d + 1) & 7), 3, dmg);
                    boss_shot(cx, cy, (u8)((d + 7) & 7), 3, dmg);
                    cadence = 46;
                    break;
                case 2:   // Skeleton — slow dense full 8-ring to weave through
                    for (d = 0; d < 8; ++d) boss_shot(cx, cy, d, 2, dmg);
                    cadence = 90;
                    break;
                case 3:   // Bomber — fast rotating cross that sweeps the room
                    for (k = 0; k < 4; ++k)
                        boss_shot(cx, cy, (u8)((e->ai_data[5] * 3 + k * 2) & 7), 2, dmg);
                    cadence = 34;
                    break;
                case 4:   // Warlock — aimed 5-shot cone (spread bolt volley)
                    d = aim_dir8(cx, cy);
                    boss_shot(cx, cy, d, 2, dmg);
                    boss_shot(cx, cy, (u8)((d + 1) & 7), 2, dmg);
                    boss_shot(cx, cy, (u8)((d + 7) & 7), 2, dmg);
                    boss_shot(cx, cy, (u8)((d + 2) & 7), 2, dmg);
                    boss_shot(cx, cy, (u8)((d + 6) & 7), 2, dmg);
                    cadence = 58;
                    break;
                case 0:   // Sentinel — steady alternating half-ring zoner
                default:
                    for (d = (u8)(e->ai_data[5] & 1); d < 8; d = (u8)(d + 2))
                        boss_shot(cx, cy, d, 2, dmg);
                    cadence = 70;
                    break;
            }
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
            case 8:   // Void Lord — WORLD COLLAPSE, room-wide except one pocket
                if (!e->ai_data[4]) {
                    e->ai_data[4] = 1;
                    e->ai_data[5] = (u8)rng_range(4);
                    // A diagonal-to-diagonal safe pocket can demand a full
                    // room crossing. 132 frames keeps World Collapse nearly
                    // unavoidable once it resolves, but makes its visible
                    // corner marker a reachable positional test instead of
                    // depending on which RNG corner happened to be nearby.
                    cadence = 132;
                } else {
                    static const u8 safe_x[4] = { 20, 124, 20, 124 };
                    static const u8 safe_y[4] = { 20, 20, 100, 100 };
                    i16 dx = (i16)player.x - safe_x[e->ai_data[5] & 3];
                    i16 dy = (i16)player.y - safe_y[e->ai_data[5] & 3];
                    if (dx < 0) dx = -dx; if (dy < 0) dy = -dy;
                    room_shake(3, 40);
                    for (d = 0; d < 8; ++d) boss_shot(cx, cy, d, 3, dmg);
                    if ((u16)(dx + dy) > 20 && player.shield_timer == 0) {
                        u8 blast = (u8)(dmg + 4);
                        player.hp = (player.hp > blast) ? (u8)(player.hp - blast) : 0;
                        player.iframes = 60;
                        hud_redraw_hp();
                        sfx_play(SFX_DEATH);
                    } else {
                        sfx_play(SFX_CLEAR);
                    }
                    e->ai_data[4] = 0;
                    cadence = 150;
                }
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
    if (e->ai_data[0] == ENEMY_STONE_SENTINEL) { boss_tick(e); return; }
    if (e->ai_data[0] == ENEMY_FLUTTERBAT) { flutterbat_tick(e); return; }
    if (e->ai_data[0] == ENEMY_GLOAM_LEECH) { leech_tick(e); return; }
    switch (def->ai_kind) {
        case AI_CHASER:  chaser_tick(e, def->stats.speed); break;
        case AI_CHARGER: charger_tick(e, def);             break;
        case AI_SHOOTER: shooter_tick(e, def);             break;
        case AI_SPINNER: spinner_update(e, def);           break;
        case AI_TELEPORT: teleport_tick(e, def);           break;
        case AI_TURRET:   turret_tick(e, def);             break;
        case AI_REPLICATOR: replicator_tick(e, def);        break;
        case AI_MIRROR: mirror_moth_update(e, def->ai_p0);   break;
        case AI_SPORE_MINE: mire_spore_update(e, def->ai_p0, def->ai_p1); break;
        case AI_COUNTER_GUARD: counter_guard_tick(e, def);                break;
        default:         walker_tick(e);                   break;
    }
}
