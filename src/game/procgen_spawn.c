#pragma bank 10

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/procgen_spawn.h"
#include "game/room.h"
#include "game/run_state.h"
#include "content.h"

static u8 enemy_spawn_position_clear(entity_t *e, i16 x, i16 y) {
    u8 id = e->ai_data[0];
    u8 ext_x, ext_y;
    if (id == ENEMY_BLUE_CRAWLER || id == ENEMY_HORNET
        || id == ENEMY_SKELETON || id == ENEMY_GLOAM_LEECH
        || id == ENEMY_RIFT_CANTOR || id >= ENEMY_FACET_RAM)
        return room_player_position_clear(x, y);

    ext_x = ((e->hitbox >> 4) >= 10) ? 14 : 6;
    ext_y = ((e->hitbox & 0x0F) >= 10) ? 14 : 6;
    // Flutterbat's authored flight contract is always a full 16px square,
    // independently of its deliberately tiny contact hurtbox.
    if (id == ENEMY_FLUTTERBAT) ext_x = ext_y = 14;
    if (x < 8 || y < 8
        || x + ext_x >= (i16)room_world_width
        || y + ext_y >= (i16)room_world_height) return 0;
    return room_tile_walkable(room_tile_at_px(x + 1, y + 1))
        && room_tile_walkable(room_tile_at_px(x + ext_x, y + 1))
        && room_tile_walkable(room_tile_at_px(x + 1, y + ext_y))
        && room_tile_walkable(room_tile_at_px(x + ext_x, y + ext_y));
}

// Authored anchors describe encounter composition, not permission to overlap
// later stage scenery. Validate each complete champion-sized body, then peel
// outward in deterministic tile rings if a biome pillar occupies that site.
// This is generation-time only, so the cold collision calls never tax play.
static void place_wide_enemy_clear(entity_t *e, i16 px, i16 py) {
    i8 radius, dx, dy;
    if (enemy_spawn_position_clear(e, px, py)) {
        e->x = FIX8(px); e->y = FIX8(py);
        return;
    }
    for (radius = 1; radius <= 8; ++radius) {
        for (dy = (i8)-radius; dy <= radius; ++dy) {
            for (dx = (i8)-radius; dx <= radius; ++dx) {
                i8 ax = dx < 0 ? (i8)-dx : dx;
                i8 ay = dy < 0 ? (i8)-dy : dy;
                i16 nx, ny;
                if ((i8)(ax + ay) != radius) continue;
                nx = px + (i16)dx * 8;
                ny = py + (i16)dy * 8;
                if (enemy_spawn_position_clear(e, nx, ny)) {
                    e->x = FIX8(nx); e->y = FIX8(ny);
                    return;
                }
            }
        }
    }
    // The central cross is carved body-wide in every scrolling court.
    if (enemy_spawn_position_clear(e, player.x, player.y)) {
        e->x = FIX8(player.x); e->y = FIX8(player.y);
    } else {
        e->x = FIX8(120); e->y = FIX8(64);
    }
}

void procgen_repair_enemy_spawns(void) BANKED {
    u8 idx;
    for (idx = 0; idx < MAX_ENTITIES; ++idx) {
        entity_t *e = &entities[idx];
        i16 px, py;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        px = FIX8_TO_INT(e->x);
        py = FIX8_TO_INT(e->y);
        if (!enemy_spawn_position_clear(e, px, py))
            place_wide_enemy_clear(e, px, py);
    }
}

// Twenty non-overlapping, body-valid anchors span the central cross and both
// guaranteed-open distant aprons. Late Normal districts can reach 18 bodies,
// so a 16-slot table made the final two silently stack on earlier monsters.
// Steps 1/3/7/9 are each coprime with 20: every formation visits every anchor
// exactly once without consuming or perturbing combat RNG.
void procgen_place_wide_enemies(u8 formation) BANKED {
    static const u8 spawn_x[20] = {
        72, 72, 72, 24, 120, 176, 216, 176, 216, 120,
        168, 216, 192, 224, 192, 224, 72, 72, 144, 192,
    };
    static const u8 spawn_y[20] = {
        24, 112, 200, 64, 64, 64, 64, 40, 40, 152,
        152, 152, 200, 200, 224, 224, 176, 224, 160, 160,
    };
    static const u8 steps[4] = { 1, 3, 7, 9 };
    u8 idx;
    u8 sector = (u8)run_state.run_seed;
    u8 step = steps[formation & 3];
    while (sector >= 20) sector = (u8)(sector - 20);
    for (idx = 0; idx < MAX_ENTITIES; ++idx) {
        if (!(entities[idx].flags & EF_ACTIVE)
            || entities[idx].type != ENT_ENEMY) continue;
        place_wide_enemy_clear(&entities[idx], spawn_x[sector], spawn_y[sector]);
        sector = (u8)(sector + step);
        if (sector >= 20) sector = (u8)(sector - 20);
    }
}
