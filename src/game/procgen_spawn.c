#pragma bank 10

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/mission_graph.h"
#include "game/player.h"
#include "game/procgen_spawn.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"
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
    procgen_ensure_required_warden();
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

// A required Warden is a progression lock, not an ordinary pack member.
// Compact-plane reachability can fail to mark any legal 2x2 (wide-room
// arrival, partitioned Mire scenery, a door-edge flood start). If this
// dungeon cell is a Warden or deep Warden room and the tagged body is
// missing, carve the authored upper-centre apron and spawn it directly
// so the sanctuary door can never soft-lock.
static u8 required_warden_present(void) {
    u8 i;
    u8 late = (run_state.bosses_beaten >= 6) ? 1 : 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        if (late) {
            if (entities[i].ai_data[0] == ENEMY_DREAD_BELL
                && entities[i].ai_data[2] == ENEMY_AUX_BELLWARDEN)
                return 1;
        } else if (entities[i].ai_data[0] == ENEMY_STONE_SENTINEL) {
            return 1;
        }
    }
    return 0;
}

static void configure_sentinel_miniboss(u8 idx, u8 stage) {
    static const u8 mb_pal[5] = { 0x06, 0x07, 0x00, 0x04, 0x03 };
    u8 mb_pow = (stage < 9) ? stage : 8;
    u8 mb_var = stage_mb_variant[stage % 9];
    entities[idx].sprite_tile = SPR_BOSS;
    entities[idx].palette     = mb_pal[mb_var];
    entities[idx].hitbox      = (u8)0xEE;
    entities[idx].ai_data[2]  = mb_var;
    entities[idx].hp = (u8)(entities[idx].hp + 25u + (u8)(mb_pow * 14));
    entities[idx].damage++;
    if (RUN_IS_EASY()) entities[idx].hp = (u8)((entities[idx].hp + 1) >> 1);
}

static void configure_bellwarden(u8 idx, u8 stage) {
    entities[idx].palette = 0x06;
    entities[idx].ai_data[2] = ENEMY_AUX_BELLWARDEN;
    entities[idx].hp = (u8)(entities[idx].hp + 22 + (u8)((stage - 6) * 4));
    if (RUN_IS_EASY())
        entities[idx].hp = (u8)((entities[idx].hp + 1) >> 1);
    entities[idx].ai_data[1] = 42;
}

static void carve_warden_apron(u8 tx, u8 ty) {
    room_tilemap[ty][tx]         = BGT_FLOOR;
    room_tilemap[ty][tx + 1]     = BGT_FLOOR;
    room_tilemap[ty + 1][tx]     = BGT_FLOOR;
    room_tilemap[ty + 1][tx + 1] = BGT_FLOOR;
}

void procgen_ensure_required_warden(void) BANKED {
    u8 local, idx, stage, tx, ty;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter))
        return;
    if (run_state_is_boss_room() || run_state_is_shop()
        || run_state_is_sanctuary())
        return;
    mission_graph_ensure();
    local = run_state_dungeon_local();
    if (local != run_state.mission_warden_cell
        && local != run_state.mission_deep_warden_cell)
        return;
    if (required_warden_present()) return;

    // Authored Sentinel / Bellwarden origin. Column 9 is already a
    // reserved N/S door lane, so a 2x2 here cannot block circulation.
    tx = (u8)((ROOM_W / 2) - 1);
    ty = 3;
    carve_warden_apron(tx, ty);
    stage = run_state.bosses_beaten;
    if (stage >= 6) {
        idx = enemy_spawn(ENEMY_DREAD_BELL, tx, ty);
        if (idx != 0xFF) configure_bellwarden(idx, stage);
    } else {
        idx = enemy_spawn(ENEMY_STONE_SENTINEL, tx, ty);
        if (idx != 0xFF) configure_sentinel_miniboss(idx, stage);
    }
}
