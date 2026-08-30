#pragma bank 9

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/dungeon_director.h"
#include "game/pickup.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/stage_event.h"
#include "render/tiles.h"

#define ROOT_COUNT 3
#define FURNACE_TILE_COUNT 10

u8 room_stage_event_kind;
u8 room_stage_event_phase;
u8 room_stage_event_remaining;

static u8 event_x[FURNACE_TILE_COUNT];
static u8 event_y[FURNACE_TILE_COUNT];
static u8 event_timer;
static u8 event_cursor;
static u8 event_rewarded;

static void event_set_raw(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
}

static void event_set_live(u8 x, u8 y, u8 tile, u8 attr) {
    event_set_raw(x, y, tile);
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

static u8 root_site_occupied(u8 tx, u8 ty) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 dx, dy;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        dx = FIX8_TO_INT(entities[i].x) + 4 - (i16)(tx * 8 + 4);
        dy = FIX8_TO_INT(entities[i].y) + 4 - (i16)(ty * 8 + 4);
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if (dx < 12 && dy < 12) return 1;
    }
    return 0;
}

static void prepare_roots(void) {
    static const u8 rx[6] = { 5, 14, 10, 5, 14, 10 };
    static const u8 ry[6] = { 5, 5, 12, 11, 11, 4 };
    u8 i, found = 0;
    // Dense procgen can legitimately place a body on one candidate. Select
    // three from a larger seed-stable set instead of deleting that enemy or
    // silently dropping the whole biome event.
    for (i = 0; i < 6 && found < ROOT_COUNT; ++i) {
        if (root_site_occupied(rx[i], ry[i])) continue;
        event_x[found] = rx[i];
        event_y[found] = ry[i];
        found++;
    }
    if (found < ROOT_COUNT) return;
    for (i = 0; i < ROOT_COUNT; ++i) {
        u8 x = event_x[i], y = event_y[i];
        // Each knot sits in a small cuttable lane, so it reshapes navigation
        // without becoming a mandatory door or an obvious puzzle block.
        event_set_raw((u8)(x - 1), y, BGT_FLOOR);
        event_set_raw((u8)(x + 1), y, BGT_FLOOR);
        event_set_raw(x, (u8)(y - 1), BGT_FLOOR);
        event_set_raw(x, (u8)(y + 1), BGT_FLOOR);
        event_set_raw(x, y, BGT_CRYSTAL);
    }
    room_stage_event_kind = STAGE_EVENT_ROOTS;
    room_stage_event_remaining = ROOT_COUNT;
}

static void prepare_furnace(void) {
    static const u8 fx[FURNACE_TILE_COUNT] = {
        5, 7, 9, 11, 13, 15, 6, 9, 12, 15
    };
    static const u8 fy[FURNACE_TILE_COUNT] = {
        5, 5, 5, 5, 5, 5, 11, 11, 11, 11
    };
    u8 i;
    for (i = 0; i < FURNACE_TILE_COUNT; ++i) {
        event_x[i] = fx[i];
        event_y[i] = fy[i];
        event_set_raw(fx[i], fy[i], BGT_FLOOR2);
    }
    room_stage_event_kind = STAGE_EVENT_FURNACE;
    room_stage_event_remaining = FURNACE_TILE_COUNT;
    // The room director already owns one per-frame update call. Animated
    // hazards use that slot instead of taxing every ordinary room.
    room_encounter_kind = ENCOUNTER_STAGE_EVENT;
}

void stage_event_prepare_room(void) BANKED {
    u8 local;
    room_stage_event_kind = STAGE_EVENT_NONE;
    room_stage_event_phase = 0;
    room_stage_event_remaining = 0;
    event_timer = event_cursor = event_rewarded = 0;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)
        || procgen_current_room_is_boss || run_state.secret_pending
        || run_state_is_shop() || run_state_is_sanctuary()
        || room_encounter_kind == ENCOUNTER_HUNT
        || room_puzzle_kind != PUZZLE_NONE
        || room_hidden_secret_kind != HIDDEN_SECRET_NONE) return;
    local = run_state_dungeon_local();
    // Let the opening four-cell phrase establish the biome's ordinary combat
    // grammar before introducing its signature verb. Thereafter, one event
    // in each four-cell phrase is common enough to define the region without
    // turning the first post-foyer route into an unexplained mandatory gate.
    if (local < 5 || (local & 3) != 1) return;
    if (run_state.bosses_beaten == 1) prepare_roots();
    else if (run_state.bosses_beaten == 2) prepare_furnace();
    else if (run_state.bosses_beaten == 3) stage_event_prepare_arrows();
    else if (run_state.bosses_beaten == 5) stage_event_prepare_fading();
}

void stage_event_on_crystal_break(u8 tx, u8 ty) BANKED {
    u8 i;
    if (room_stage_event_kind != STAGE_EVENT_ROOTS) return;
    for (i = 0; i < ROOT_COUNT; ++i) {
        if (event_x[i] != tx || event_y[i] != ty) continue;
        event_x[i] = event_y[i] = 0xFF;
        if (room_stage_event_remaining) room_stage_event_remaining--;
        if (room_stage_event_remaining == 0) {
            pickup_spawn_surge(FIX8((i16)tx * 8), FIX8((i16)ty * 8));
            room_shake(2, 20);
            sfx_play(SFX_PUZZLE);
        } else {
            sfx_play_rune((u8)(ROOT_COUNT - room_stage_event_remaining - 1));
        }
        return;
    }
}

void stage_event_tick(void) BANKED {
    u8 tile, attr;
    if (room_stage_event_kind >= STAGE_EVENT_ARROW_TRAPS) {
        stage_event_tick_hazard();
        return;
    }
    if (room_stage_event_kind != STAGE_EVENT_FURNACE) return;
    event_timer++;
    switch (room_stage_event_phase) {
        case 0: // cool reward/routing window
            if (event_timer < 90) return;
            event_timer = event_cursor = 0;
            room_stage_event_phase = 1;
            sfx_play_rune(0);
            return;
        case 1: // gold plates announce each soon-hot lane
            if (event_timer & 1) return;
            tile = BGT_SWITCH; attr = BGPAL_DOOR;
            break;
        case 2: // hold the complete warning long enough to route around it
            if (event_timer < 30) return;
            event_timer = event_cursor = 0;
            room_stage_event_phase = 3;
            room_shake(1, 10);
            sfx_play(SFX_ROAR);
            return;
        case 3: // a visible ignition wave, one tile every other frame
            if (event_timer & 1) return;
            tile = BGT_SPIKES; attr = BGPAL_CRACK;
            break;
        case 4: // fully hot
            if (event_timer < 90) return;
            event_timer = event_cursor = 0;
            room_stage_event_phase = 5;
            return;
        default: // cooling wave restores the cracked-floor route
            if (event_timer & 1) return;
            tile = BGT_FLOOR2; attr = BGPAL_CRYSTAL;
            break;
    }
    event_set_live(event_x[event_cursor], event_y[event_cursor], tile, attr);
    event_cursor++;
    if (event_cursor < FURNACE_TILE_COUNT) return;
    event_cursor = event_timer = 0;
    if (room_stage_event_phase == 1) room_stage_event_phase = 2;
    else if (room_stage_event_phase == 3) room_stage_event_phase = 4;
    else {
        room_stage_event_phase = 0;
        if (!event_rewarded) {
            event_rewarded = 1;
            pickup_spawn_surge(FIX8(80), FIX8(64));
            room_shake(1, 16);
            sfx_play(SFX_PUZZLE);
        }
    }
}
