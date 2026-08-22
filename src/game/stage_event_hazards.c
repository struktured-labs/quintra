#pragma bank 10

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/stage_event.h"
#include "render/tiles.h"

#define ARROW_TRAP_COUNT 4
#define FADING_TILE_COUNT 8

static u8 hazard_x[FADING_TILE_COUNT];
static u8 hazard_y[FADING_TILE_COUNT];
static u8 hazard_timer;
static u8 hazard_cursor;

static void hazard_set_raw(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
}

static void hazard_set_live(u8 x, u8 y, u8 tile, u8 attr) {
    hazard_set_raw(x, y, tile);
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

void stage_event_prepare_arrows(void) BANKED {
    u8 i;
    u8 max_x = (u8)((room_world_width >> 3) - 1);
    u8 max_y = (u8)((room_world_height >> 3) - 1);
    hazard_x[0] = 0;     hazard_y[0] = 4;
    hazard_x[1] = max_x; hazard_y[1] = (u8)(max_y - 4);
    hazard_x[2] = max_x; hazard_y[2] = 4;
    hazard_x[3] = 0;     hazard_y[3] = (u8)(max_y - 4);
    for (i = 0; i < ARROW_TRAP_COUNT; ++i)
        hazard_set_raw(hazard_x[i], hazard_y[i], BGT_ARROW_TRAP);
    hazard_timer = hazard_cursor = 0;
    room_stage_event_kind = STAGE_EVENT_ARROW_TRAPS;
    room_stage_event_remaining = ARROW_TRAP_COUNT;
    room_encounter_kind = ENCOUNTER_STAGE_EVENT;
}

void stage_event_prepare_fading(void) BANKED {
    u8 i;
    // Every panel borders the permanent two-tile east/west processional.
    // When one drops away, an intact row is always one step north or south.
    hazard_x[0] = hazard_x[4] = 4;
    hazard_x[1] = hazard_x[5] =
        (room_world_width > ROOM_VIEW_W_PX) ? 12 : 7;
    hazard_x[2] = hazard_x[6] =
        (room_world_width > ROOM_VIEW_W_PX) ? 20 : 12;
    hazard_x[3] = hazard_x[7] =
        (room_world_width > ROOM_VIEW_W_PX) ? 27 : 15;
    for (i = 0; i < 4; ++i) {
        hazard_y[i] = 7;
        hazard_y[i + 4] = 10;
    }
    for (i = 0; i < FADING_TILE_COUNT; ++i)
        hazard_set_raw(hazard_x[i], hazard_y[i], BGT_FLOOR2);
    hazard_timer = hazard_cursor = 0;
    room_stage_event_kind = STAGE_EVENT_FADING_FLOOR;
    room_stage_event_remaining = FADING_TILE_COUNT;
    room_encounter_kind = ENCOUNTER_STAGE_EVENT;
}

static void tick_arrows(void) {
    u8 idx, left;
    hazard_timer++;
    if (room_stage_event_phase == 0) {
        if (hazard_timer < 64) return;
        hazard_timer = 0;
        room_stage_event_phase = 1;
        hazard_set_live(hazard_x[hazard_cursor], hazard_y[hazard_cursor],
            BGT_ARROW_TRAP, BGPAL_CRACK);
        sfx_play(SFX_TICK);
        return;
    }
    if (hazard_timer < 22) return;
    hazard_timer = 0;
    room_stage_event_phase = 0;
    left = (hazard_x[hazard_cursor] == 0);
    hazard_set_live(hazard_x[hazard_cursor], hazard_y[hazard_cursor],
        BGT_ARROW_TRAP, BGPAL_WALL);
    idx = projectile_spawn_enemy_v(
        left ? 8 : (i16)(room_world_width - 16),
        (i16)(hazard_y[hazard_cursor] * 8 + 2), left ? 4 : -4, 0, 2);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_FX_ARROW;
        entities[idx].palette = 4;
        entities[idx].state_timer = 64;
        entities[idx].hitbox = 0x84;
        if (!left) entities[idx].ai_data[4] = PROJ_VIS_FLIP_X;
    }
    sfx_play(SFX_FIRE);
    hazard_cursor++;
    if (hazard_cursor == ARROW_TRAP_COUNT) hazard_cursor = 0;
}

static void tick_fading(void) {
    u8 tile, attr;
    hazard_timer++;
    switch (room_stage_event_phase) {
        case 0:
            if (hazard_timer < 90) return;
            hazard_timer = hazard_cursor = 0;
            room_stage_event_phase = 1;
            sfx_play(SFX_TICK);
            return;
        case 1:
            if (hazard_timer & 1) return;
            tile = BGT_SWITCH; attr = BGPAL_DOOR;
            break;
        case 2:
            if (hazard_timer < 36) return;
            hazard_timer = hazard_cursor = 0;
            room_stage_event_phase = 3;
            room_shake(1, 8);
            sfx_play(SFX_ROAR);
            return;
        case 3:
            if (hazard_timer & 1) return;
            tile = BGT_VOID; attr = BGPAL_WALL;
            break;
        case 4:
            if (hazard_timer < 84) return;
            hazard_timer = hazard_cursor = 0;
            room_stage_event_phase = 5;
            sfx_play(SFX_TICK);
            return;
        default:
            if (hazard_timer & 1) return;
            tile = BGT_FLOOR2; attr = BGPAL_CRYSTAL;
            break;
    }
    hazard_set_live(hazard_x[hazard_cursor], hazard_y[hazard_cursor], tile, attr);
    hazard_cursor++;
    if (hazard_cursor < FADING_TILE_COUNT) return;
    hazard_cursor = hazard_timer = 0;
    if (room_stage_event_phase == 1) room_stage_event_phase = 2;
    else if (room_stage_event_phase == 3) room_stage_event_phase = 4;
    else room_stage_event_phase = 0;
}

void stage_event_tick_hazard(void) BANKED {
    if (room_stage_event_kind == STAGE_EVENT_ARROW_TRAPS) tick_arrows();
    else tick_fading();
}
