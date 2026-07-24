#pragma bank 4
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

// Giant bosses own a movement identity as well as a projectile identity.
// `vx` is a phase timer and `vy` a saved direction; these fields are unused
// by enemy bodies, so the state survives an emulator save without new WRAM.
static void boss_chase_tick(entity_t *e, u8 divider) {
    e->state_timer++;
    if (e->state_timer >= divider) {
        i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
        i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
        i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
        e->state_timer = 0;
        if (sx) enemy_try_step(e, sx, 0);
        if (sy) enemy_try_step(e, 0, sy);
    }
}

// Use the same four-corner clearance as enemy_try_step.  A blink therefore
// cannot land inside scenery or directly on top of the champion.
static u8 boss_warp_near_player(entity_t *e) {
    u8 tries, start = (u8)(rng_next_u8() & 7);
    // Three radii give the teleport a reliable destination even in the
    // obstacle-dense boss arenas, while every option remains visibly close
    // enough to read as a flank rather than an unfair off-screen jump. The
    // Spider's closest flank begins just outside a short weapon's body-reset
    // band: it creates an attack decision after the warning, not an instant
    // forced retreat into its own web.
    for (tries = 0; tries < 24; ++tries) {
        u8 d = (u8)((start + tries) & 7);
        i16 dist = (i16)(44 + (tries >> 3) * 12);
        i16 nx = (i16)player.x + (i16)dir8_dx[d] * dist - 12;
        i16 ny = (i16)player.y + (i16)dir8_dy[d] * dist - 12;
        // Collision uses the giant's deliberately fair 13px body, but blink
        // placement must reserve its full 32px visual footprint. Using the
        // hitbox extent here could put a perfectly legal body at y=104 while
        // the lower half of the Spider rendered beyond the room edge.
        i16 ext = ((e->ai_data[3] & 1) != 0) ? 30 : 6;
        if (nx < 8 || ny < 8 || nx + ext >= (i16)((ROOM_W - 1) * 8 + 8)
            || ny + ext >= (i16)((ROOM_H - 1) * 8 + 8)) continue;
        if (!room_tile_walkable(room_tile_at_px(nx + 1, ny + 1))
            || !room_tile_walkable(room_tile_at_px(nx + ext, ny + 1))
            || !room_tile_walkable(room_tile_at_px(nx + 1, ny + ext))
            || !room_tile_walkable(room_tile_at_px(nx + ext, ny + ext))) continue;
        fx_spawn(SPR_FX_IMPACT, 2, FIX8_TO_INT(e->x) + 8, FIX8_TO_INT(e->y) + 8, 10);
        e->x = FIX8(nx); e->y = FIX8(ny); e->ai_data[7] = 10;
        fx_spawn(SPR_FX_IMPACT, 2, nx + 8, ny + 8, 12);
        return 1;
    }
    return 0;
}

static u8 boss_aim_dir8(const entity_t *e) {
    i16 cx = FIX8_TO_INT(e->x) + 12, cy = FIX8_TO_INT(e->y) + 12;
    i8 sx = ((i16)player.x > cx) ? 1 : ((i16)player.x < cx) ? -1 : 0;
    i8 sy = ((i16)player.y > cy) ? 1 : ((i16)player.y < cy) ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 0;
}

static void boss_bounce_tick(entity_t *e, u8 divider) {
    u8 d;
    i8 dx, dy;
    u8 moved_x, moved_y;
    if (!(e->state & 1)) e->state = (u8)(e->state + 1);
    if (++e->state_timer < divider) return;
    e->state_timer = 0; d = (u8)(e->state & 7);
    dx = dir8_dx[d]; dy = dir8_dy[d];
    moved_x = enemy_try_step(e, dx, 0);
    moved_y = enemy_try_step(e, 0, dy);
    // Reflect only the blocked component: a clean pinball line that slides
    // around arena pillars rather than stuttering in front of them.
    if (!moved_x) d = (u8)((8 - d) & 7);
    if (!moved_y) d = (u8)((4 - d) & 7);
    e->state = d;
}

void boss_motion_tick(entity_t *e) BANKED {
    // Mini-bosses retain the simpler pursuit behavior; giant stages receive
    // the more theatrical movement language below.
    if (!(e->ai_data[3] & 1)) { boss_chase_tick(e, 3); return; }

    switch (e->ai_data[2]) {
        case 0: { // Crystal Dragon: warned jumps among three distant wells
            static const u8 anchor_x[3] = { 24, 96, 176 };
            static const u8 anchor_y[3] = { 48, 32, 72 };
            if (e->vx == 0) { e->vx = 96; e->state = 1; }
            if (e->vx == 18) {
                e->ai_data[7] = 12;
                sfx_play(SFX_TICK);
            }
            if (--e->vx == 0) {
                u8 next = (u8)((e->state + 1) % 3);
                fx_spawn(SPR_FX_IMPACT, 2, FIX8_TO_INT(e->x) + 12,
                    FIX8_TO_INT(e->y) + 12, 12);
                e->state = next;
                e->x = FIX8(anchor_x[next]);
                e->y = FIX8(anchor_y[next]);
                e->ai_data[7] = 12;
                e->ai_data[1] = 32;
                fx_spawn(SPR_FX_IMPACT, 2, anchor_x[next] + 12,
                    anchor_y[next] + 12, 14);
                e->vx = 96;
                sfx_play(SFX_ROAR);
            }
            return;
        }

        case 1: // Storm Serpent: diagonal wall bounces with attack windows
            // Two-frame movement made Verdant's 220-HP giant cross an entire
            // melee lane before Wolfkin could complete a single claw cycle.
            // Four frames remains visibly faster than the Hydra's broad
            // weave, but the matched Normal matrix showed the three-frame
            // body defeated or timed out three of five kits at boss two.
            // Preserve its HP and dense rotating cross; this changes tracking
            // pressure, not the Serpent's projectile or endurance identity.
            boss_bounce_tick(e, 4);
            return;

        case 2: // Cinder Maw: wind-up, hard lunge, recover
            if (e->vx == 0) { e->state = 0; e->vx = 34; }
            if (e->state == 0) {
                if (e->vx == 10) { e->ai_data[7] = 10; sfx_play(SFX_TICK); }
                if (--e->vx == 0) {
                    e->vy = (i8)boss_aim_dir8(e);
                    e->state = 1; e->vx = 15; sfx_play(SFX_ROAR);
                }
            } else if (e->state == 1) {
                i8 dx = dir8_dx[(u8)e->vy & 7], dy = dir8_dy[(u8)e->vy & 7];
                u8 moved = enemy_try_step(e, dx, 0);
                if (enemy_try_step(e, 0, dy)) moved = 1;
                if (moved) { enemy_try_step(e, dx, 0); enemy_try_step(e, 0, dy); }
                if (!moved || --e->vx == 0) { e->state = 2; e->vx = 22; }
            } else if (--e->vx == 0) { e->state = 0; e->vx = 30; }
            return;

        case 3: // Frost Spider: warning flash followed by fair blink-step
            if (e->vx == 0) { e->vx = 92; e->state = 0; }
            if (e->vx == 16) { e->state = 1; e->ai_data[7] = 12; sfx_play(SFX_TICK); }
            if (--e->vx == 0) {
                boss_warp_near_player(e);
                // The warning only reads as a real opening if the web cannot
                // resolve on the very frame the Spider reappears. Preserve
                // its blink cadence and four-lane pattern, but grant a short
                // re-engagement beat for close weapons after every flank.
                e->ai_data[1] = 18;
                e->state = 0; e->vx = 92; sfx_play(SFX_ROAR);
            }
            return;

        case 4: // Mire: pulse outward, then contract into a crushing advance
            if (e->vx == 0) { e->vx = 48; e->state = 0; }
            if ((e->vx & 7) == 0)
                fx_spawn(SPR_FX_IMPACT, 0x05, FIX8_TO_INT(e->x) + 10,
                    FIX8_TO_INT(e->y) + 10, 8);
            if ((e->vx & 3) == 0) {
                i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
                i8 sx = ((i16)player.x > ex) ? 1 : ((i16)player.x < ex) ? -1 : 0;
                i8 sy = ((i16)player.y > ey) ? 1 : ((i16)player.y < ey) ? -1 : 0;
                if (e->state) { sx = -sx; sy = -sy; }
                if (sx) enemy_try_step(e, sx, 0);
                if (sy) enemy_try_step(e, 0, sy);
            }
            if (--e->vx == 0) { e->state ^= 1; e->vx = 48; sfx_play(SFX_TICK); }
            return;

        case 5: // Reaper: hunt, telegraph, then re-enter at a new flank
            if (e->vx == 0) e->vx = 84;
            if (e->vx == 14) { e->ai_data[7] = 10; sfx_play(SFX_TICK); }
            if (--e->vx == 0) { boss_warp_near_player(e); e->vx = 84; sfx_play(SFX_ROAR); }
            else boss_chase_tick(e, 5);
            return;

        case 7: // Hydra: a broad slower weave, distinct from the Serpent
            // Keep its three staggered projectile streams threatening, but
            // move only every fifth beat.  This gives the later boss a
            // recognizably different lane rhythm from Verdant's fast Serpent
            // instead of two differently coloured pinballs.
            boss_bounce_tick(e, 5);
            return;

        case 8: { // Void Lord: weak point jumps between the colossal body's anchors
            static const u8 anchor_x[4] = { 40, 88, 64, 64 };
            static const u8 anchor_y[4] = { 32, 32, 64, 40 };
            u8 next = (u8)((e->state + 1) & 3);
            // Hold each exposed point long enough to read and punish. Without
            // this divider the core jumped every game update and its paired
            // warp FX exhausted the fixed entity pool, hiding Collapse cues.
            if (++e->state_timer < 36) return;
            e->state_timer = 0;
            fx_spawn(SPR_FX_IMPACT, 2, FIX8_TO_INT(e->x) + 12,
                FIX8_TO_INT(e->y) + 12, 10);
            e->state = next;
            e->x = FIX8(anchor_x[next]);
            e->y = FIX8(anchor_y[next]);
            e->ai_data[7] = 12;
            fx_spawn(SPR_FX_IMPACT, 2, anchor_x[next] + 12,
                anchor_y[next] + 12, 12);
            sfx_play(SFX_ROAR);
            return;
        }
        default: boss_chase_tick(e, 3); return;
    }
}
