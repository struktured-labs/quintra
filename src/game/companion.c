#pragma bank 10

#include <gb/gb.h>

#include "core/types.h"
#include "game/companion.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

#define COMPANION_FOLLOW_GAP   22
#define COMPANION_WARP_GAP     88

static u8 companion_seed_kind(void) {
    u8 mix = (u8)run_state.run_seed;
    mix ^= (u8)(run_state.run_seed >> 8);
    mix ^= (u8)(run_state.run_seed >> 16);
    mix ^= (u8)(run_state.run_seed >> 24);
    mix = (u8)(mix + run_state.bosses_beaten * 17);
    return (u8)(mix % COMPANION_COUNT);
}

static entity_t *companion_entity(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PICKUP
            && entities[i].ai_data[0] == PICKUP_COMPANION)
            return &entities[i];
    }
    return 0;
}

u8 companion_active_kind(void) BANKED {
    entity_t *e = companion_entity();
    return e ? e->ai_data[1] : companion_seed_kind();
}

u8 companion_ask_ready(void) BANKED {
    return run_state.companion_cooldown == 0;
}

static u8 companion_palette(u8 kind) {
    // Hearth borrows the heart-red voice, Aether the stage-magic voice, and
    // Way the gold landmark voice. No new palette upload is needed per room.
    return kind == COMPANION_HEARTH ? 4
        : kind == COMPANION_AETHER ? 6 : 5;
}

static u8 companion_position_clear(i16 x, i16 y) {
    // Entity coordinates are a civic feet anchor; the room collision helper
    // consumes the same top-left convention as the champion.
    return room_player_position_clear(x - 4, y - 8);
}

static void companion_place_near_player(entity_t *e) {
    static const i8 ox[4] = { -20, 20, 0, 0 };
    static const i8 oy[4] = { 0, 0, -20, 20 };
    i16 cx = (i16)player.x + 4;
    i16 cy = (i16)player.y + 8;
    u8 i;
    for (i = 0; i < 4; ++i) {
        i16 nx = cx + ox[i];
        i16 ny = cy + oy[i];
        if (companion_position_clear(nx, ny)) {
            e->x = (ppos_t)nx;
            e->y = (ppos_t)ny;
            return;
        }
    }
    // The follower has no collision body. Overlap is a safe last resort at
    // an unusually tight generated arrival, and separates naturally as soon
    // as either adjacent body position opens.
    e->x = (ppos_t)cx;
    e->y = (ppos_t)cy;
}

void companion_spawn_current(void) BANKED {
    u8 idx, kind;
    entity_t *e;
    if (run_state.victory || companion_entity()) return;
    idx = entity_spawn(ENT_PICKUP);
    if (idx == 0xFF) return;
    kind = companion_seed_kind();
    e = &entities[idx];
    e->ai_data[0] = PICKUP_COMPANION;
    e->ai_data[1] = kind;
    e->ai_data[2] = (u8)run_state.run_timer;
    e->sprite_tile = SPR_COMPANION_WALK_A;
    e->palette = companion_palette(kind);
    e->hitbox = 0;       // ally: neither loot nor a blocking resident
    e->state_timer = (u8)(36 + kind * 18);
    companion_place_near_player(e);
}

static u8 companion_try_step(entity_t *e, i8 dx, i8 dy) {
    i16 nx = FIX8_TO_INT(e->x) + dx;
    i16 ny = FIX8_TO_INT(e->y) + dy;
    if (!companion_position_clear(nx, ny)) return 0;
    e->x = (ppos_t)nx;
    e->y = (ppos_t)ny;
    return 1;
}

static void companion_tick_cooldown(entity_t *e) {
    u8 now = (u8)run_state.run_timer;
    u8 elapsed = (u8)(now - e->ai_data[2]);
    if (!elapsed) return;
    e->ai_data[2] = now;
    if (elapsed >= run_state.companion_cooldown)
        run_state.companion_cooldown = 0;
    else
        run_state.companion_cooldown =
            (u8)(run_state.companion_cooldown - elapsed);
}

static void companion_fire(entity_t *from, i8 dx, i8 dy) {
    u8 idx = entity_spawn(ENT_PROJECTILE);
    entity_t *shot;
    if (idx == 0xFF) return;
    shot = &entities[idx];
    shot->flags |= EF_PLAYER_PROJ;
    shot->x = (ppos_t)(from->x + 1);
    shot->y = (ppos_t)(from->y - 4);
    shot->vx = (i8)(dx * 2);
    shot->vy = (i8)(dy * 2);
    shot->sprite_tile = SPR_BULLET;
    shot->palette = from->palette;
    shot->hp = 1;
    shot->state_timer = 52;
    shot->hitbox = 0x55;
    shot->damage = 1;
    shot->ai_data[1] = from->ai_data[1] == COMPANION_HEARTH ? 1
        : from->ai_data[1] == COMPANION_AETHER ? 8 : 4;
}

static u8 companion_aim(entity_t *e, i8 *dx, i8 *dy) {
    u8 i, found = 0;
    u16 best = 0xFFFF;
    i16 ex = FIX8_TO_INT(e->x);
    i16 ey = FIX8_TO_INT(e->y);
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 ax, ay;
        u16 dist;
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_ENEMY
            || !(entities[i].flags & EF_ON_SCREEN)) continue;
        ax = FIX8_TO_INT(entities[i].x) - ex;
        ay = FIX8_TO_INT(entities[i].y) - ey;
        dist = (u16)(ax < 0 ? -ax : ax) + (u16)(ay < 0 ? -ay : ay);
        if (dist >= best || dist > 104) continue;
        best = dist;
        *dx = ax > 5 ? 1 : ax < -5 ? -1 : 0;
        *dy = ay > 5 ? 1 : ay < -5 ? -1 : 0;
        found = (*dx || *dy) ? 1 : 0;
    }
    return found;
}

void companion_update(entity_t *e, u8 idx) BANKED {
    i16 tx, ty, dx, dy;
    u8 moved = 0;
    i8 aim_x, aim_y;
    idx;
    companion_tick_cooldown(e);

    tx = (i16)player.x + 4;
    ty = (i16)player.y + 8;
    dx = tx - FIX8_TO_INT(e->x);
    dy = ty - FIX8_TO_INT(e->y);
    if (dx > COMPANION_WARP_GAP || dx < -COMPANION_WARP_GAP
        || dy > COMPANION_WARP_GAP || dy < -COMPANION_WARP_GAP) {
        companion_place_near_player(e);
        moved = 1;
    } else {
        i16 ax = dx < 0 ? -dx : dx;
        i16 ay = dy < 0 ? -dy : dy;
        i8 sx = dx > 0 ? 1 : dx < 0 ? -1 : 0;
        i8 sy = dy > 0 ? 1 : dy < 0 ? -1 : 0;
        if (ax > COMPANION_FOLLOW_GAP || ay > COMPANION_FOLLOW_GAP) {
            if (ax >= ay) {
                moved = companion_try_step(e, (i8)(sx * 2), 0);
                if (!moved) moved = companion_try_step(e, 0, (i8)(sy * 2));
            } else {
                moved = companion_try_step(e, 0, (i8)(sy * 2));
                if (!moved) moved = companion_try_step(e, (i8)(sx * 2), 0);
            }
        }
    }
    if (moved) e->ai_data[4] = (u8)(e->ai_data[4] + 2);
    e->sprite_tile = (moved && (e->ai_data[4] & 8))
        ? SPR_COMPANION_WALK_B : SPR_COMPANION_WALK_A;

    if (e->state) {
        e->state = e->state > 2 ? (u8)(e->state - 2) : 0;
        e->palette = (e->state & 2) ? 0 : companion_palette(e->ai_data[1]);
    }
    if (e->state_timer) {
        e->state_timer = e->state_timer > 2
            ? (u8)(e->state_timer - 2) : 0;
    } else if (companion_aim(e, &aim_x, &aim_y)) {
        companion_fire(e, aim_x, aim_y);
        // The follower assists without becoming a second primary weapon.
        e->state_timer = (u8)(82 + e->ai_data[1] * 18);
    }
}
