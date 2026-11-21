#pragma bank 5
// M5a Conduit: setup (layout stamp, entity cleanup; bank 5). Paint /
// restore in conduit_paint.c (bank 16), OBJ list in conduit_draw.c (bank 14),
// rules in conduit_room.c (bank 24) and conduit_lane.c (bank 16).
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

// '#' wall, '.' floor, '=' stone groove, 'G' goal; '1' teleport pad,
// '2' gold switch, '3' plate (reset / spawn) -- one quadrant id each,
// mirrored per cell. Side door (6,3..4) and Star door (5..6,12) are regions.
static const char cd_layout[CD_H][CD_W + 1] = {
    "############",
    "#11...#....#",   // teleport pad | turret alcove (9..10,1..2)
    "#11...#....#",
    "#.....#....#",   // side door (6,3..4): starts shut
    "#33...#..22#",   // reset plate | gold switch (9..10,4..5)
    "#33.33#..22#",   //   Rime pedestal (4..5,5..6)
    "....33#....#",   // entrance rows 6..7 | Star key (8..9,6..7)
    "......#....#",
    "####33######",   // spawn plate (4..5,8..9) in the gap
    "#...33.....#",   // hall landing row
    "#==========#",   // rolling-stone lane rows 10..11 (Jagger guards it)
    "#==========#",
    "############",   // Star door (5..6,12)
    "#..........#",   // vault
    "#..........#",
    "#....GG....#",
    "#..........#",
    "############",
};

static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

static u8 in_zone(u8 ex, u8 ey) {
    if (ex >= (u8)(CD_X0 - 4) && ey >= CD_Y0 && ey < (u8)(CD_Y0 + CD_H)) return 1;
    return (ex >= 11 && ey >= (u8)(WY(CD_ENTRY_Y) - 1)
        && ey <= (u8)(WY(CD_ENTRY_Y) + 2)) ? 1 : 0;
}

u8 cd_prepare(void) BANKED {
    u8 i, x, y, ex, ey, id;
    entity_t *e;
    cd_live = 0;
    if (!procgen_current_room_is_large || room_world_width < ROOM_WIDE_W_PX
        || room_world_height < ROOM_WIDE_H_PX) return 0;
    cd_pack_id = 0xFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        e = &entities[i];
        if (!(e->flags & EF_ACTIVE)) continue;
        ex = (u8)((e->x + 8) >> 3);
        ey = (u8)((e->y + 8) >> 3);
        id = e->ai_data[0];
        if (e->type == ENT_PICKUP && in_zone(ex, ey) && id != PICKUP_HEART_HALF
            && id != PICKUP_COIN_1 && id != PICKUP_COIN_5 && id != PICKUP_MP) return 0;
        // The pack is two of an ordinary enemy already in this room (its
        // tiles are loaded).
        if (e->type == ENT_ENEMY && cd_pack_id == 0xFF && id < ENEMY_FACET_RAM
            && id != ENEMY_LEYBEAM && id != ENEMY_SUN_BASILISK && id != ENEMY_NOX_BASILISK)
            cd_pack_id = id;
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        e = &entities[i];
        if (!(e->flags & EF_ACTIVE)) continue;
        id = e->ai_data[0];
        if (e->type == ENT_ENEMY && (id == ENEMY_LEYBEAM
                || id == ENEMY_SUN_BASILISK || id == ENEMY_NOX_BASILISK)) {
            entity_kill(i);
            continue;
        }
        if (e->type != ENT_ENEMY && e->type != ENT_PICKUP) continue;
        if (in_zone((u8)((e->x + 8) >> 3), (u8)((e->y + 8) >> 3))) entity_kill(i);
    }
    for (y = 0; y < CD_H; ++y)
        for (x = 0; x < CD_W; ++x) {
            char c = cd_layout[y][x];
            u8 t = BGT_FLOOR;
            if (c == '#') t = BGT_WALL;
            else if (c == '=') t = CD_T_TRACK;
            else if (c == '1') t = 106;
            else if (c == '2') t = 107;
            else if (c == '3') t = 96;
            else if (c == 'G') t = (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)
                ? BGT_SWITCH_PRESSED : BGT_SWITCH;
            wset(WX(x), WY(y), t);
        }
    for (y = (u8)(CD_ENTRY_Y - 1); y <= (u8)(CD_ENTRY_Y + 2); ++y)
        for (x = (u8)(CD_X0 - 4); x < CD_X0; ++x)
            wset(x, WY(y), BGT_FLOOR);
    for (y = CD_ENTRY_Y; y <= (u8)(CD_ENTRY_Y + 1); ++y)
        for (x = 11; x < (u8)(CD_X0 - 4); ++x)
            wset(x, WY(y), BGT_FLOOR);
    cd_shot[0] = cd_shot[1] = cd_pack[0] = cd_pack[1] = 0xFF;
    cd_restore();
    cd_resets = cd_refusals = cd_flips = cd_crushed = cd_shoves = 0;
    cd_inside = 0;
    cd_frame = 0;
    cd_safe_x = (u8)player.x;
    cd_safe_y = (u8)player.y;
    cd_epoch = (u8)(tiles_bg_epoch - 1);
    puzzle_keep_x0 = (u8)((CD_X0 - 1) * 8);
    puzzle_keep_y0 = (u8)(CD_Y0 * 8);
    puzzle_keep_y1 = (u8)((CD_Y0 + CD_H) * 8);
    puzzle_keep_on = 1;
    puzzle_pack_n = 2;
    cd_live = 1;
    new_monsters_in_room = 1;
    return 1;
}

