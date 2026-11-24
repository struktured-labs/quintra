#pragma bank 16

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/mission_graph.h"
#include "game/procgen_spawn.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/waygear.h"
#include "render/tiles.h"
#include "content.h"

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
    // (tx, ty) is on the compact 20x17 plane (same origin as the primary
    // Sentinel spawn). procgen_repair_enemy_spawns runs before
    // room_draw_tilemap, so writing room_tilemap here is the live collision
    // and render source; the 31x31 extensions only store x>=20 / y>=17.
    room_tilemap[ty][tx]         = BGT_FLOOR;
    room_tilemap[ty][tx + 1]     = BGT_FLOOR;
    room_tilemap[ty + 1][tx]     = BGT_FLOOR;
    room_tilemap[ty + 1][tx + 1] = BGT_FLOOR;
}

static void evict_apron_occupants(u8 tx, u8 ty) {
    u8 i;
    i16 x0 = (i16)tx * 8;
    i16 y0 = (i16)ty * 8;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 ex, ey;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        ex = FIX8_TO_INT(entities[i].x);
        ey = FIX8_TO_INT(entities[i].y);
        if (ex < x0 + 16 && ex + 8 > x0 && ey < y0 + 16 && ey + 8 > y0)
            entities[i].flags &= (u8)~EF_ACTIVE;
    }
}

static void evict_one_non_warden(void) {
    u8 i = MAX_ENTITIES;
    while (i) {
        i--;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        if (entities[i].ai_data[0] == ENEMY_STONE_SENTINEL) continue;
        if (entities[i].ai_data[0] == ENEMY_DREAD_BELL
            && entities[i].ai_data[2] == ENEMY_AUX_BELLWARDEN)
            continue;
        entities[i].flags &= (u8)~EF_ACTIVE;
        return;
    }
}

void procgen_ensure_required_warden(void) BANKED {
    u8 local, idx, stage, tx, ty;
    u8 world_guard = 0;
    if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        world_guard_unrepaired = 0;
        return;
    }
    if (run_state.world_mode) {
        // Riftwild guard fields are the world-mode equivalent of a tagged
        // Warden cell. Compact-plane reachability can still miss the body
        // (#242, #245); do not leave the regional gate asleep.
        if (RUN_IN_RIFT_DEN()) {
            world_guard_unrepaired = 0;
            return;
        }
        if (!run_state_riftwild_guard_active(run_state.world_screen)) {
            world_guard_unrepaired = 0;
            return;
        }
        world_guard = 1;
    } else {
        if (run_state_is_boss_room() || run_state_is_shop()
            || run_state_is_sanctuary())
            return;
        mission_graph_ensure();
        local = run_state_dungeon_local();
        if (local != run_state.mission_warden_cell
            && local != run_state.mission_deep_warden_cell)
            return;
        // Don't respawn a Warden after a real kill or the clear-room safety net.
        if (local == run_state.mission_deep_warden_cell
            && (run_state.dungeon_phase & RUN_DEEP_WARDEN_BIT))
            return;
        if (local == run_state.mission_warden_cell
            && (run_state.dungeon_puzzles & RUN_WARDEN_BOON_BIT))
            return;
    }
    if (required_warden_present()) {
        if (world_guard) world_guard_unrepaired = 0;
        return;
    }
    if (world_guard) world_guard_unrepaired = 1; // until the spawn below lands

    // Authored Sentinel / Bellwarden origin. Column 9 is already a
    // reserved N/S door lane on the compact plane, so a 2x2 here cannot
    // block circulation. Matches the primary is_miniboss spawn exactly.
    tx = (u8)((ROOM_W / 2) - 1);
    ty = 3;
    carve_warden_apron(tx, ty);
    if (world_guard) {
        // Keep a body-wide corridor on that reserved lane down to the
        // field's east-west trail (rows 8/9). Climate or the adjacent
        // waygear pocket (x=12..18, y=2..7) must not isolate the apron.
        u8 y;
        for (y = 3; y <= 8; ++y) {
            room_tilemap[y][tx] = BGT_FLOOR;
            room_tilemap[y][tx + 1] = BGT_FLOOR;
        }
    }
    evict_apron_occupants(tx, ty);
    stage = run_state.bosses_beaten;
    if (stage >= 6) {
        idx = enemy_spawn(ENEMY_DREAD_BELL, tx, ty);
        if (idx == 0xFF) {
            evict_one_non_warden();
            idx = enemy_spawn(ENEMY_DREAD_BELL, tx, ty);
        }
        if (idx != 0xFF) configure_bellwarden(idx, stage);
    } else {
        idx = enemy_spawn(ENEMY_STONE_SENTINEL, tx, ty);
        if (idx == 0xFF) {
            evict_one_non_warden();
            idx = enemy_spawn(ENEMY_STONE_SENTINEL, tx, ty);
        }
        if (idx != 0xFF) configure_sentinel_miniboss(idx, stage);
    }
    if (world_guard)
        world_guard_unrepaired = required_warden_present() ? 0 : 1;
}
