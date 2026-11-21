#pragma bank 16
// M5a Conduit: BG regions, redress, solve, restore (bank 16).
#include <gb/gb.h>
#include <gbdk/console.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/enemy_ai.h"
#include "game/enemy_new_ai.h"
#include "game/entity.h"
#include "game/lock_room.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/conduit_art.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

#define PX CD_PX
#define PY CD_PY
#define WX CD_WX
#define WY CD_WY

extern u8 cd_on, cd_inside, cd_dirty, cd_epoch, cd_safe_x, cd_safe_y;

static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

static void put2(u8 x, u8 y, u8 w, u8 h, const u8 *t, const u8 *a) {
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), w, h, t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), w, h, a);
    VBK_REG = 0;
}

// r 0: side door (1x2, bars / floor); r 1: Star door (2x1, door / floor).
void cd_paint(u8 r) BANKED {
    u8 t[2], a[2], x, y, open;
    x = r ? WX(CD_DOOR_X) : WX(CD_SIDE_X);
    y = r ? WY(CD_DOOR_Y) : WY(CD_SIDE_Y);
    open = r ? cd_open : cd_side;
    t[0] = t[1] = open ? BGT_FLOOR : (r ? CD_T_DOOR : CD_T_BARS);
    a[0] = open ? BGPAL_FLOOR : (r ? BGPAL_CRACK : BGPAL_WALL);
    a[1] = (u8)(a[0] | ((r && !open) ? 0x20 : 0));
    wset(x, y, t[0]);
    wset(r ? (u8)(x + 1) : x, r ? y : (u8)(y + 1), t[1]);
    put2(x, y, r ? 2 : 1, r ? 1 : 2, t, a);
}

static const u8 quad_flip[4] = { 0, 0x20, 0x40, 0x60 };

// One mirrored 2x2 pad (top-left local cell lx, ly).
static void pad(u8 lx, u8 ly, u8 id, u8 pal) {
    u8 t[4], a[4], i;
    for (i = 0; i < 4; ++i) { t[i] = id; a[i] = (u8)(pal | quad_flip[i]); }
    put2(WX(lx), WY(ly), 2, 2, t, a);
}

void cd_redress(void) BANKED {
    u8 t[10], a[10], i;
    cd_bg_art_load();
    cd_art_load();
    for (i = 0; i < 10; ++i) { t[i] = CD_T_TRACK; a[i] = BGPAL_FLOOR; }
    put2(WX(1), WY(CD_LANE_Y), 10, 1, t, a);
    put2(WX(1), WY(CD_LANE_Y + 1), 10, 1, t, a);
    pad(CD_TP_X, CD_TP_Y, 106, BGPAL_CRYSTAL);
    pad(CD_SW_X, CD_SW_Y, 107, BGPAL_DOOR);
    pad(CD_RESET_X, CD_RESET_Y, 96, BGPAL_DOOR);
    pad(CD_FRZ_X, CD_FRZ_Y, 96, BGPAL_CRYSTAL);
    pad(CD_SPAWN_X, CD_SPAWN_Y, 96, cd_armed ? BGPAL_FLOOR : BGPAL_CRACK);
    cd_paint(0);
    cd_paint(1);
    if (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT) {
        t[0] = t[1] = BGT_SWITCH_PRESSED; a[0] = a[1] = BGPAL_DOOR;
        put2(WX(CD_GOAL_X), WY(CD_GOAL_Y), 2, 1, t, a);
    }
}

void cd_solve(void) BANKED {
    u8 t[2] = { BGT_SWITCH_PRESSED, BGT_SWITCH_PRESSED };
    u8 a[2] = { BGPAL_DOOR, BGPAL_DOOR };
    run_state.dungeon_puzzles |= RUN_RIME_SOLVED_BIT;
    wset(WX(CD_GOAL_X), WY(CD_GOAL_Y), BGT_SWITCH_PRESSED);
    wset(WX(CD_GOAL_X + 1), WY(CD_GOAL_Y), BGT_SWITCH_PRESSED);
    put2(WX(CD_GOAL_X), WY(CD_GOAL_Y), 2, 1, t, a);
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed + rime_cell) % 3),
        player.x, player.y);
}

static void kill_slot(u8 *s, u8 type) {
    // Only our own entity: a freed slot may have been reused since.
    if (*s != 0xFF && (entities[*s].flags & (EF_ACTIVE | EF_PLAYER_PROJ)) == EF_ACTIVE
        && entities[*s].type == type) entity_kill(*s);
    *s = 0xFF;
}

// Entry state of every moving part.
void cd_restore(void) BANKED {
    kill_slot(&cd_shot[0], ENT_PROJECTILE);
    kill_slot(&cd_shot[1], ENT_PROJECTILE);
    kill_slot(&cd_pack[0], ENT_ENEMY);
    kill_slot(&cd_pack[1], ENT_ENEMY);
    cd_side = cd_open = cd_held = cd_charge = cd_armed = cd_pend = 0;
    cd_key = 1;
    cd_thp = 4;
    cd_tt = 60;
    cd_tell = cd_lock = cd_tflash = 0;
    cd_sst = 0;
    cd_st = 90;
    cd_jx = PX(5);
    cd_jy = PY(CD_LANE_Y);
    cd_jst = CD_J_GUARD;
    room_freeze_beats = 0;
    puzzle_keep_on = 1;
    cd_on = 0xFF;                   // nothing fires until stepped on afresh
    cd_dirty = 0;
    if (cd_live) {
        cd_paint(0);
        cd_paint(1);
        pad(CD_SPAWN_X, CD_SPAWN_Y, 96, BGPAL_CRACK);
    }
}

