#pragma bank 25

#include <gb/gb.h>

#include "core/types.h"
#include "game/cinder_big.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/room.h"
#include "render/tiles.h"

// Lower-flank seats for the two half-hearts dropped at the pack-to-Rex
// metamorphosis. They sit below the authored transform fire band
// (x=96..120, y=66) and the 48x32 Rex unfold at (88, 50).
#define CINDER_HEAL_X0 72
#define CINDER_HEAL_Y0 96
#define CINDER_HEAL_X1 144
#define CINDER_HEAL_Y1 96

static u8 cinder_heart_tile_ok(u8 tile) {
    return room_tile_walkable(tile) && tile != BGT_SPIKES
        && tile != BGT_PORTAL && tile != BGT_SWITCH;
}

static u8 cinder_heart_walkable(u8 x, u8 y) {
    return cinder_heart_tile_ok(room_tile_at_px((i16)x + 1, (i16)y + 1))
        && cinder_heart_tile_ok(room_tile_at_px((i16)x + 14, (i16)y + 1))
        && cinder_heart_tile_ok(room_tile_at_px((i16)x + 1, (i16)y + 14))
        && cinder_heart_tile_ok(room_tile_at_px((i16)x + 14, (i16)y + 14));
}

static u8 cinder_fire_overlaps_px(u8 x, u8 y) {
    u8 i;
    u8 tx0 = (u8)(x >> 3), ty0 = (u8)(y >> 3);
    u8 tx1 = (u8)((x + 15) >> 3), ty1 = (u8)((y + 15) >> 3);
    for (i = 0; i < 8; ++i) {
        u8 fx, fy, s;
        if (!cinder_fire_ttl[i]) continue;
        fx = cinder_fire_tx[i];
        fy = cinder_fire_ty[i];
        s = cinder_fire_size[i];
        if (tx1 >= fx && tx0 < (u8)(fx + s)
            && ty1 >= fy && ty0 < (u8)(fy + s))
            return 1;
    }
    return 0;
}

// Keep the 16x16 pickup out of the authored transform corridor and any
// live floor brands, including warning-only pools that are about to ignite.
static u8 cinder_heart_spot_ok(u8 x, u8 y) {
    if (x + 16 > 88 && x < 136 && y + 16 > 56 && y < 80) return 0;
    return !cinder_fire_overlaps_px(x, y);
}

static u8 cinder_heart_overlaps_sibling(u8 x, u8 y, u8 self_idx) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        u8 hx, hy;
        if (i == self_idx) continue;
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type != ENT_PICKUP) continue;
        if (entities[i].ai_data[0] != PICKUP_HEART_HALF) continue;
        hx = (u8)FIX8_TO_INT(entities[i].x);
        hy = (u8)FIX8_TO_INT(entities[i].y);
        if (x + 16 > hx && x < hx + 16 && y + 16 > hy && y < hy + 16)
            return 1;
    }
    return 0;
}

static u8 cinder_try_heart_at(i16 x, i16 y) {
    u8 idx, ax, ay;
    if (x < 8 || y < 8) return 0xFF;
    if (x > (i16)room_world_width - 16) return 0xFF;
    if (y > (i16)room_world_height - 16) return 0xFF;
    if (!cinder_heart_spot_ok((u8)x, (u8)y)) return 0xFF;
    if (!cinder_heart_walkable((u8)x, (u8)y)) return 0xFF;
    if (cinder_heart_overlaps_sibling((u8)x, (u8)y, 0xFF)) return 0xFF;
    idx = pickup_spawn(PICKUP_HEART_HALF, FIX8((u8)x), FIX8((u8)y));
    if (idx == 0xFF) {
        u8 i;
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if ((entities[i].flags & (EF_ACTIVE | EF_PLAYER_PROJ))
                    == EF_ACTIVE
                && entities[i].type == ENT_PROJECTILE) {
                entity_kill(i);
                idx = pickup_spawn(PICKUP_HEART_HALF, FIX8((u8)x), FIX8((u8)y));
                break;
            }
        }
    }
    if (idx == 0xFF) return 0xFF;
    ax = (u8)FIX8_TO_INT(entities[idx].x);
    ay = (u8)FIX8_TO_INT(entities[idx].y);
    if (!cinder_heart_spot_ok(ax, ay)
        || cinder_heart_overlaps_sibling(ax, ay, idx)) {
        entity_kill(idx);
        return 0xFF;
    }
    pickup_mark_persistent(idx);
    return idx;
}

static void cinder_place_heart(u8 preferred_x, u8 preferred_y) {
    static const i8 dx[13] = {
        0, -16, 16, 0, 0, -16, 16, -16, 16, -32, 32, -32, 32
    };
    static const i8 dy[13] = {
        0, 0, 0, -16, 16, -16, -16, 16, 16, 0, 0, 16, -16
    };
    u8 i;
    for (i = 0; i < 13; ++i) {
        if (cinder_try_heart_at((i16)preferred_x + dx[i],
                                (i16)preferred_y + dy[i]) != 0xFF)
            return;
    }
}

void cinder_drop_phase_hearts(void) BANKED {
    cinder_place_heart(CINDER_HEAL_X0, CINDER_HEAL_Y0);
    cinder_place_heart(CINDER_HEAL_X1, CINDER_HEAL_Y1);
}
