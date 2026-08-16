#pragma bank 7

#include <gb/gb.h>
#include <gb/cgb.h>

#include "game/dungeon_director.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

static u8 unseal_x(u8 dir, u8 half, u8 east) {
    if (dir == DIR_E) return east;
    if (dir == DIR_W) return 0;
    return (u8)(9 + half);
}

static u8 unseal_y(u8 dir, u8 half, u8 south) {
    if (dir == DIR_N) return 0;
    if (dir == DIR_S) return south;
    return (u8)(8 + half);
}

// Cold seal-release rendering lives outside the resident combat bank. It
// runs only after a puzzle, directive, or boss resolves, while the hot room
// loop keeps more than the required development headroom.
void room_unseal_doors(void) BANKED {
    u8 dir, half;
    u8 east = (u8)((room_world_width >> 3) - 1);
    u8 south = (u8)((room_world_height >> 3) - 1);
    u8 cleared_boss = run_state_was_cleared_boss();
    // Ordinary exits already retain BGT_DOOR beneath their amber seal, so
    // releasing a puzzle/combat room is only a palette change. A defeated
    // Colossus is the exception: it authors fresh compact exits here.
    if (cleared_boss)
        for (dir = 0; dir < 4; ++dir) {
            if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
            for (half = 0; half < 2; ++half)
                room_tilemap[unseal_y(dir, half, ROOM_H - 1)]
                    [unseal_x(dir, half, ROOM_W - 1)] = BGT_DOOR;
        }
    wait_vbl_done();
    {
        u8 door = BGT_DOOR, attr = BGPAL_DOOR;
        // Locked ordinary exits are rendered with the barred tile while the
        // logical terrain remains BGT_DOOR. Restore their visible tile as the
        // latch opens; a palette-only change left an amber portcullis behind.
        VBK_REG = 0;
        for (dir = 0; dir < 4; ++dir) {
            if (!cleared_boss && run_state_dungeon_neighbor(dir) == 0xFF)
                continue;
            if (cleared_boss && dir == DIR_E
                && room_world_width > ROOM_VIEW_W_PX) continue;
            for (half = 0; half < 2; ++half) {
                u8 x = unseal_x(dir, half,
                    cleared_boss ? (ROOM_W - 1) : east);
                u8 y = unseal_y(dir, half,
                    cleared_boss ? (ROOM_H - 1) : south);
                set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y),
                    1, 1, &door);
            }
        }
        VBK_REG = 1;
        for (dir = 0; dir < 4; ++dir) {
            if (!cleared_boss && run_state_dungeon_neighbor(dir) == 0xFF)
                continue;
            if (cleared_boss && dir == DIR_E
                && room_world_width > ROOM_VIEW_W_PX) continue;
            attr = (dir == room_objective_dir)
                ? BGPAL_CRYSTAL : BGPAL_DOOR;
            for (half = 0; half < 2; ++half) {
                u8 x = unseal_x(dir, half,
                    cleared_boss ? (ROOM_W - 1) : east);
                u8 y = unseal_y(dir, half,
                    cleared_boss ? (ROOM_H - 1) : south);
                set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y),
                    1, 1, &attr);
            }
        }
        VBK_REG = 0;
    }
    if (procgen_current_room_is_boss
        && room_world_width > ROOM_VIEW_W_PX)
        tiles_open_crystal_far_exit();
}
