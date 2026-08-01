#pragma bank 7

#include <gb/gb.h>
#include <gb/cgb.h>

#include "game/dungeon_director.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

// Cold seal-release rendering lives outside the resident combat bank. It
// runs only after a puzzle, directive, or boss resolves, while the hot room
// loop keeps more than the required development headroom.
void room_unseal_doors(void) BANKED {
    static const u8 dxs[4][2] = {
        { 9, 10 }, { ROOM_W - 1, ROOM_W - 1 },
        { 9, 10 }, { 0, 0 },
    };
    static const u8 dys[4][2] = {
        { 0, 0 }, { 8, 9 },
        { ROOM_H - 1, ROOM_H - 1 }, { 8, 9 },
    };
    u8 dir, half;
    for (dir = 0; dir < 4; ++dir) {
        if (!run_state_was_cleared_boss()
            && run_state_dungeon_neighbor(dir) == 0xFF) continue;
        if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
        for (half = 0; half < 2; ++half)
            room_tilemap[dys[dir][half]][dxs[dir][half]] = BGT_DOOR;
    }
    wait_vbl_done();
    {
        u8 door = BGT_DOOR, attr = BGPAL_DOOR;
        VBK_REG = 0;
        for (dir = 0; dir < 4; ++dir) {
            if (!run_state_was_cleared_boss()
                && run_state_dungeon_neighbor(dir) == 0xFF) continue;
            if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
            for (half = 0; half < 2; ++half)
                set_bkg_tiles(ROOM_BG_MAP_X(dxs[dir][half]),
                    ROOM_BG_MAP_Y(dys[dir][half]), 1, 1, &door);
        }
        VBK_REG = 1;
        for (dir = 0; dir < 4; ++dir) {
            if (!run_state_was_cleared_boss()
                && run_state_dungeon_neighbor(dir) == 0xFF) continue;
            if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
            attr = (dir == room_objective_dir)
                ? BGPAL_CRYSTAL : BGPAL_DOOR;
            for (half = 0; half < 2; ++half)
                set_bkg_tiles(ROOM_BG_MAP_X(dxs[dir][half]),
                    ROOM_BG_MAP_Y(dys[dir][half]), 1, 1, &attr);
        }
        VBK_REG = 0;
    }
    if (procgen_current_room_is_boss
        && room_world_width > ROOM_VIEW_W_PX)
        tiles_open_crystal_far_exit();
}
