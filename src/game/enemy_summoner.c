#pragma bank 7

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"
#include "content.h"

// Cantor scratch:
// ai_data[2] = mode (0 listening, 1 chanting, 2 wave spent)
// ai_data[3] = chant countdown
// ai_data[4] = post-wave movement divider

static u8 cantor_abs(i16 n) {
    return (u8)(n < 0 ? -n : n);
}

static u8 cantor_spots_player(const entity_t *e, u8 radius) {
    i16 dx = (i16)player.x - FIX8_TO_INT(e->x);
    i16 dy = (i16)player.y - FIX8_TO_INT(e->y);
    u8 ax = cantor_abs(dx);
    u8 ay = cantor_abs(dy);
    // A diamond-shaped awareness field reads naturally in cardinal rooms
    // and cannot trigger from the opposite end of a 31x31 scrolling court.
    return ax <= radius && ay <= radius && (u16)ax + ay <= radius;
}

static u8 cantor_spawn_cell_clear(u8 tx, u8 ty) {
    i16 px = (i16)tx << 3;
    i16 py = (i16)ty << 3;
    i16 dx = px - (i16)player.x;
    i16 dy = py - (i16)player.y;
    if (tx == 0 || ty == 0
        || px + 15 >= (i16)room_world_width
        || py + 15 >= (i16)room_world_height) return 0;
    // Escorts resolve outside immediate contact range even if the champion
    // walks directly into the chant. The long tell is meaningful warning,
    // not permission to materialize damage inside the hurtbox.
    if (cantor_abs(dx) < 20 && cantor_abs(dy) < 20) return 0;
    return room_tile_walkable(room_tile_at_px(px + 1, py + 1))
        && room_tile_walkable(room_tile_at_px(px + 14, py + 1))
        && room_tile_walkable(room_tile_at_px(px + 1, py + 14))
        && room_tile_walkable(room_tile_at_px(px + 14, py + 14));
}

static u8 cantor_escort_id(u8 ordinal) {
    u8 stage = run_state.bosses_beaten;
    if (stage >= 9) stage = (u8)(stage % 9);
    if (stage == 3) return ordinal ? ENEMY_WISP : ENEMY_SKELETON;
    if (stage == 4) return ordinal ? ENEMY_BLUE_CRAWLER : ENEMY_WISP;
    if (stage == 5) return ordinal ? ENEMY_SKELETON : ENEMY_SHADE;
    if (stage == 6) return ordinal ? ENEMY_WISP : ENEMY_ORC;
    if (stage == 7) return ordinal ? ENEMY_ROPE : ENEMY_SHADE;
    if (stage == 8) return ordinal ? ENEMY_SKELETON : ENEMY_SHADE;
    return ordinal ? ENEMY_HORNET : ENEMY_BLUE_CRAWLER;
}

static void cantor_call_escort(entity_t *e, u8 ordinal) {
    static const i8 ox[8] = { 3, -3, 0, 0, 3, -3, 3, -3 };
    static const i8 oy[8] = { 0, 0, 3, -3, 3, -3, -3, 3 };
    i16 bx = FIX8_TO_INT(e->x) >> 3;
    i16 by = FIX8_TO_INT(e->y) >> 3;
    u8 start = (u8)((e->state + ordinal * 3) & 7);
    u8 i;
    for (i = 0; i < 8; ++i) {
        u8 site = (u8)((start + i) & 7);
        i16 tx = bx + ox[site];
        i16 ty = by + oy[site];
        if (tx <= 0 || ty <= 0 || tx > 30 || ty > 30) continue;
        if (!cantor_spawn_cell_clear((u8)tx, (u8)ty)) continue;
        if (enemy_spawn(cantor_escort_id(ordinal), (u8)tx, (u8)ty) != 0xFF)
            return;
        // No entity headroom. A failed call is final rather than retrying
        // forever once projectiles and pickups release their slots.
        return;
    }
}

void rift_cantor_update(entity_t *e, const enemy_def_t *def) BANKED {
    if (e->ai_data[2] == 0) {
        if (!cantor_spots_player(e, def->ai_p0)) return;
        e->ai_data[2] = 1;
        e->ai_data[3] = def->ai_p1;
        e->ai_data[7] = 12;
        sfx_play(SFX_TICK);
        (void)fx_spawn(SPR_FX_MUZZLE, 2,
            FIX8_TO_INT(e->x), FIX8_TO_INT(e->y), 10);
        return;
    }
    if (e->ai_data[2] == 1) {
        if (e->ai_data[3]) e->ai_data[3]--;
        // Four visible pulses make the summoning rule legible even with
        // music muted. They reuse the existing muzzle FX and decay quickly.
        if ((e->ai_data[3] & 15) == 8) {
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
            (void)fx_spawn(SPR_FX_MUZZLE, 2,
                FIX8_TO_INT(e->x), FIX8_TO_INT(e->y), 8);
        }
        if (e->ai_data[3]) return;
        e->ai_data[2] = 2;
        cantor_call_escort(e, 0);
        if (!RUN_IS_EASY()) cantor_call_escort(e, 1);
        e->ai_data[7] = 16;
        sfx_play(SFX_ROAR);
        return;
    }

    // After its one wave, the Cantor becomes a slow evasive target instead
    // of beginning another chant. This is bounded by construction: summoned
    // IDs never include the Cantor, and this mode never returns to zero.
    if ((++e->ai_data[4] & 7) == 0) enemy_cantor_evade(e);
}
