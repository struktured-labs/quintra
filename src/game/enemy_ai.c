#pragma bank 2
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/dungeon_director.h"
#include "game/enemy_ai.h"
#include "game/enemy_mirror.h"
#include "game/enemy_spore.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

// Per-AI scratch layout in entity_t:
//   ai_data[0] = content enemy id (all AIs)
//   Walker:  state = dir8, state_timer = ticks until new dir
//   Chaser:  state_timer = frame divider
//   Charger: ai_data[2] = mode (0 wander 1 telegraph 2 charge 3 recover),
//            ai_data[3] = mode timer, ai_data[4] = locked dir8

void enemy_patrol_update(entity_t *e, u8 enemy_content_id) BANKED;

static u8 ground_navigation_enemy(const entity_t *e) {
    // Persistent ground enemies must remain in spaces a champion's 12px feet
    // box can re-enter. Hornets flank forever, Skeletons and Leeches chase
    // through sealed rooms, and ordinary Crawlers can become the final live
    // target; each could otherwise pass through a one-tile lane and strand
    // melee play. Flying/specialist enemies retain their authored envelopes.
    return e->ai_data[0] == ENEMY_HORNET
        || e->ai_data[0] == ENEMY_SKELETON
        || e->ai_data[0] == ENEMY_GLOAM_LEECH
        // A spent Cantor deliberately retreats from the hero and can become
        // the last seal target. Its old 6px navigation envelope admitted the
        // outer eight-pixel floor strip of a scrolling court, but the hero's
        // 12px feet and cardinal shots cannot enter or align with that strip.
        // Give its evasive phase the same reachable-space contract as other
        // persistent ground enemies.
        || e->ai_data[0] == ENEMY_RIFT_CANTOR
        || e->ai_data[0] >= ENEMY_FACET_RAM
        || e->ai_data[0] == ENEMY_BLUE_CRAWLER;
}

// Try to move an enemy 1px by (dx,dy); blocked by solid tiles + room bounds.
// Returns 1 if moved. Hornets use the hero's 12px feet-box clearance: a
// persistent chaser can otherwise enter a one-tile pocket the melee hero
// cannot enter, turning a sealed encounter into an unwinnable softlock. Its
// movement must probe the same
// feet-anchored corners as the player: a generic sprite rectangle can skip
// over a one-tile wall between its top and bottom samples, admitting an enemy
// to a corridor that the player cannot enter. Large bruisers retain their
// wider 16px movement envelope; other small enemies keep their authored, more
// agile movement identities.
u8 enemy_try_step(entity_t *e, i8 dx, i8 dy) BANKED {
    i16 nx = (i16)(FIX8_TO_INT(e->x) + dx);
    i16 ny = (i16)(FIX8_TO_INT(e->y) + dy);
    u8 ground = ground_navigation_enemy(e);
    i16 ext_x = ((e->hitbox >> 4) >= 10) ? 14 : 6;
    i16 ext_y = ((e->hitbox & 0x0F) >= 10) ? 14 : 6;
    if (nx < 8 || ny < 8) return 0;
    if (nx + (ground ? 15 : ext_x) >= (i16)room_world_width
        || ny + (ground ? 15 : ext_y) >= (i16)room_world_height) return 0;
    if (ground) {
        // This shared cold-path predicate includes both the six feet samples
        // and the full visible faces of pillars/push-blocks. Feet-only enemy
        // collision let small Rift Ooze fragments tuck beneath an overhang
        // into a pocket no champion or cardinal projectile could reach,
        // leaving an otherwise-cleared sealed room permanently locked.
        if (!room_player_position_clear(nx, ny)) return 0;
    } else if (!room_tile_walkable(room_tile_at_px(nx + 1,     ny + 1))
        || !room_tile_walkable(room_tile_at_px(nx + ext_x, ny + 1))
        || !room_tile_walkable(room_tile_at_px(nx + 1,     ny + ext_y))
        || !room_tile_walkable(room_tile_at_px(nx + ext_x, ny + ext_y))) return 0;
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

// Metroid-like latch: pursue, attach, pulse-drain, and ride the hero until
// killed. Dashing shakes it loose through the hero's extended iframes.
static u8 leech_release_place(entity_t *e, i16 nx, i16 ny) {
    if (nx < 8 || ny < 8
        || nx + 13 >= (i16)room_world_width
        || ny + 13 >= (i16)room_world_height) return 0;
    if (!room_tile_walkable(room_tile_at_px(nx + 1,  ny + 1))
        || !room_tile_walkable(room_tile_at_px(nx + 13, ny + 1))
        || !room_tile_walkable(room_tile_at_px(nx + 1,  ny + 13))
        || !room_tile_walkable(room_tile_at_px(nx + 13, ny + 13))) return 0;
    e->x = FIX8(nx);
    e->y = FIX8(ny);
    return 1;
}

static void leech_release(entity_t *e) {
    i16 nx = (i16)player.x + 4;
    i16 ny = (i16)player.y + 1;
    // A dash can detach a Leech while the champion occupies a door-edge
    // pixel. Clamp its usual riding position back to the legal navigation
    // band, then try nearby real floor before leaving it behind.
    if (nx < 8) nx = 8;
    if (ny < 8) ny = 8;
    // We only need to repair the impossible top/left attachment release.
    // At a normal in-bounds release preserve the exact former position and
    // timing of every chaser; this avoids changing unrelated route entropy.
    if (leech_release_place(e, nx, ny)) return;
    if (leech_release_place(e, nx + 16, ny)) return;
    if (leech_release_place(e, nx - 16, ny)) return;
    if (leech_release_place(e, nx, ny + 16)) return;
    (void)leech_release_place(e, nx, ny - 16);
}

static void leech_tick(entity_t *e) {
    if (e->ai_data[6]) {
        e->x = FIX8((i16)player.x + 4);
        e->y = FIX8((i16)player.y + 1);
        // The dash begins at 14 recovery frames, but room/combat update
        // ordering can present the Leech one or two beats later. Six frames
        // still uniquely identifies the dodge window while avoiding a failed
        // release when that dash starts at a sealed doorway edge.
        if (player.iframes >= 6) {
            e->ai_data[6] = 0;
            // state_timer is the chaser movement divider, not a countdown:
            // storing 30 there made the next update reset it to zero and let
            // an edge-rehomed Leech immediately latch onto the same feet box.
            // ai_data[4] is otherwise unused by this species and owns the
            // real post-dash attach lockout.
            e->state_timer = 0;
            e->ai_data[4] = 30;
            leech_release(e);
            return;
        }
        if (++e->ai_data[5] >= (RUN_IS_EASY() ? 120 : 45)) {
            e->ai_data[5] = 0;
            if (player.hp > 1) { player.hp--; hud_redraw_hp(); sfx_play(SFX_HURT); }
        }
        return;
    }
    {
        u8 attach_locked = e->ai_data[4];
        if (attach_locked) e->ai_data[4]--;
        chaser_tick(e, 72);
        if (!attach_locked && e->state_timer == 0 && aabb_overlap_player(e)) {
        e->ai_data[6] = 1; e->ai_data[5] = 0; sfx_play(SFX_HURT);
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

// Counter guards reserve state for their shell cycle (ready/rush/exposed),
// so they cannot borrow chaser_tick(): that helper uses state for wall-slide
// direction. Keep their deliberately slow pressure state-safe instead.
static void counter_guard_step(entity_t *e) {
    i16 ex = FIX8_TO_INT(e->x);
    i16 ey = FIX8_TO_INT(e->y);
    i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
    i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
    if (sx && !enemy_try_step(e, sx, 0) && sy) enemy_try_step(e, 0, sy);
    else if (!sx && sy) enemy_try_step(e, 0, sy);
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
            counter_guard_step(e);
        }
        return;
    }
    // Shield-ready stance advances deliberately; the bright gold silhouette
    // and first blocked hit teach the bait-then-punish rhythm.
    if ((++e->ai_data[1] & 3) == 0) counter_guard_step(e);
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
        // The content table owns this cadence.  96 is the established
        // two-pixel charger lane; 120 is the intentionally faster Bog Toad
        // pounce.  Keeping the quantization tiny makes every lane readable
        // on the 8px grid while finally honoring the authored charge_speed
        // field instead of silently flattening every charger to the same AI.
        u8 steps = (def->ai_p1 >= 112) ? 3 : 2;
        u8 ok = 1;
        while (steps--) {
            if (!enemy_try_step(e, dx, dy)) { ok = 0; break; }
        }
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
    // Slow wander + fire toward player on a timer. Authoring speed normally
    // describes the body, but Shooters historically ignored it and every
    // caster drifted at the same rate. Fast (72+) harriers now move every
    // four ticks; established casters retain the original eight-tick beat.
    // ai_data[1] = fire countdown.
    u8 drift_mask = (def->stats.speed >= 72) ? 0x03 : 0x07;
    if ((e->state_timer & drift_mask) == 0) {
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
        u8 fire_rate = def->ai_p0;
        if (!RUN_IS_EASY()) {
            if (fire_rate > 32) fire_rate -= 4;
            if (run_state.bosses_beaten >= 3 && fire_rate > 32)
                fire_rate -= 6;
            if (run_state.bosses_beaten >= 6 && fire_rate > 32)
                fire_rate -= 6;
        }
        e->ai_data[1] = fire_rate;
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
            // A vanished Shade must keep ticking its return timer while it is
            // absent from a scrolling camera sector. Rendering and both
            // collision sweeps recognize this phase explicitly.
            e->flags &= (u8)~EF_ON_SCREEN;
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
            if (nx < 8 || nx >= (i16)(room_world_width - 8)) continue;
            if (ny < 8 || ny >= (i16)(room_world_height - 8)) continue;
            if (!room_tile_walkable(room_tile_at_px(nx + 4, ny + 4))) continue;
            e->x = FIX8(nx);
            e->y = FIX8(ny);
            e->ai_data[2] = 0;
            // The destination is generated around the hero, so materialize
            // immediately instead of waiting for a camera-sector transition
            // that may never occur while the player holds a firing lane.
            e->flags |= EF_ON_SCREEN;
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
//   [3]=bit0 giant flag; bit7 signature spent; bit6 signature charging
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

    // Ember is a bespoke two-act encounter. Its five physical Kilnbacks,
    // formation windows, metamorphosis, and Cinder Rex attacks own the full
    // update rather than layering another sprite over the shared Colossus
    // chase/volley/signature driver.
    if ((e->ai_data[3] & 1) && e->ai_data[2] == 2) {
        cinder_boss_tick(e);
        return;
    }

    // The Void Lord slowly knits itself back together. One HP every six
    // seconds is visible in a stalled fight without erasing decisive damage;
    // its locomotion leaves `vy` free, so save states retain the partial beat.
    if ((e->ai_data[3] & 1) && e->ai_data[2] == 8) {
        if (e->hp < e->ai_data[6]) {
            u8 regen = (u8)e->vy + 1;
            e->vy = (i8)regen;
            if (regen >= 180) { e->vy = 0; e->hp++; }
        } else e->vy = 0;
    }

    // Verdant's articulated body remains a live contact hazard even while
    // the signature dispatcher freezes ordinary movement and volleys. Keeping
    // this before the early return closes the former harmless warning phase.
    if ((e->ai_data[3] & 1) && e->ai_data[2] == 1)
        serpent_tail_contact();

    // The old shared four-shot riftbreak has become nine authored, warned
    // screen-shaping attacks. The banked dispatcher owns its countdown and
    // freezes ordinary movement/volleys until the announced geometry fires.
    if (colossus_signature_tick(e)) return;

    boss_motion_tick(e);

    if (e->ai_data[1] != 0) {
        e->ai_data[1]--;
        // World Collapse's one survivable corner flickers throughout the
        // charge from the actual large-boss driver. ai_data[4] is the charge
        // flag and ai_data[5] remains the announced/resolved corner slot.
        if ((e->ai_data[3] & 1) && e->ai_data[2] == 8 && e->ai_data[4]
            && (e->ai_data[1] & 7) == 0) {
            static const u8 safe_x[4] = { 20, 188, 20, 188 };
            static const u8 safe_y[4] = { 20, 20, 100, 100 };
            fx_spawn(SPR_FX_IMPACT, 1, safe_x[e->ai_data[5] & 3],
                safe_y[e->ai_data[5] & 3], 10);
            sfx_play(SFX_TICK);
        }
        // Telegraph: blink white + a quiet click ~8 frames before every
        // volley (reuses the hit-flash pathway) so patterns read as
        // dodgeable, not random.
        if (e->ai_data[1] == 8 && e->ai_data[7] == 0) {
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }

    // Giant projectile identities live with the bespoke encounter code in
    // roomy bank 9. Bank 2 retains only miniboss volleys and roster AI; this
    // also leaves enough emergency headroom for cartridge-safe hot fixes.
    if (e->ai_data[3] & 1) {
        boss_volley_tick(e);
        return;
    }

    {
        u8 dmg   = e->damage;
        u8 d, k;
        i16 cx = FIX8_TO_INT(e->x) + 8;
        i16 cy = FIX8_TO_INT(e->y) + 8;
        u8 cadence;

        {
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
        }

        // Void Lord reserves ai_data[5] for the announced safe-corner slot;
        // rotating it after selection made the marker and resolved blast
        // disagree by one corner. Other bosses retain their rotation counter.
        if (e->ai_data[2] != 8) e->ai_data[5]++;
        // Enrage below half HP — only tighten the longer cadences so short
        // burst timers can't underflow.
        if (cadence > 34 && e->hp < (u8)(e->ai_data[6] >> 1))
            cadence = (u8)(cadence - 18);
        e->ai_data[1] = cadence;
    }
}

// ---------------- Dispatch ----------------------------------------------

void enemy_update(entity_t *e, u8 idx) BANKED {
    u8 id = e->ai_data[0];
    const enemy_def_t *def = &enemies[id];
    if (id == ENEMY_STONE_SENTINEL) { boss_tick(e); return; }
    // Return-echo minibosses supplement their native charge, bomb, or caster
    // behavior with a warned three-lane scale volley. Bit 7 requests the
    // tighter miniboss cadence without consuming another entity scratch byte.
    if (room_return_echo_kind == 4 && (e->flags & EF_ELITE))
        weak_pattern_tick(e, (u8)(0x80 | idx));
    if (id == ENEMY_HORNET && hornet_swarm_tick(e, idx)) return;
    if (id == ENEMY_BLUE_CRAWLER
        && e->ai_data[2] == ENEMY_AUX_OOZE_FRAGMENT) {
        ooze_fragment_update(e, idx); return;
    }
    if (id == ENEMY_BLUE_CRAWLER)
        blue_crawler_pattern_tick(e, idx);
    if (id == ENEMY_FLUTTERBAT) { flutterbat_update(e); return; }
    if (id == ENEMY_GLOAM_LEECH) { leech_tick(e); return; }
    if (id >= ENEMY_FACET_RAM) { enemy_patrol_update(e, id); return; }
    switch (def->ai_kind) {
        case AI_CHASER:  chaser_tick(e, def->stats.speed); break;
        case AI_CHARGER: charger_tick(e, def);             break;
        case AI_SHOOTER: shooter_tick(e, def);             break;
        case AI_SPINNER: spinner_update(e, def);           break;
        case AI_TELEPORT: teleport_tick(e, def);           break;
        case AI_TURRET:   turret_tick(e, def);             break;
        case AI_REPLICATOR: fold_star_update(e, def);        break;
        case AI_MIRROR: mirror_moth_update(e, def->ai_p0);   break;
        case AI_SPORE_MINE: mire_spore_update(e, def->ai_p0, def->ai_p1); break;
        case AI_COUNTER_GUARD: counter_guard_tick(e, def);                break;
        case AI_SUMMONER: rift_cantor_update(e, def);                     break;
        default:         walker_tick(e);                   break;
    }
}
