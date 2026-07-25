#pragma bank 6

#include <gb/gb.h>

#include "core/types.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

static u8 render_attr(u8 x, u8 y, u8 tile) {
    if (room_puzzle_kind == PUZZLE_PHASE_GATE
        && y == room_puzzle_visual_y && x >= 2 && x < ROOM_W - 2)
        return (run_state.dungeon_phase & RUN_PHASE_OPEN_BIT)
            ? BGPAL_CRYSTAL : BGPAL_CRACK;
    switch (tile) {
        case BGT_WALL:
        case BGT_PILLAR:
        case BGT_ROOF:
        case BGT_FENCE:
        case BGT_TREE:
        case BGT_WILD_STONE:
        case BGT_BLOCK:
        case BGT_BLOCK_TR:
        case BGT_BLOCK_BL:
        case BGT_BLOCK_BR:
        case BGT_COLOSSUS_SCALE:
        case BGT_COLOSSUS_EDGE_L:
        case BGT_COLOSSUS_EDGE_R:
        case BGT_COLOSSUS_HORN:
            return BGPAL_WALL;
        case BGT_WALL_CRACK:
        case BGT_SPIKES:
        case BGT_BOSS_GATE_L:
        case BGT_BOSS_GATE_R:
        case BGT_BOSS_GATE_TOP:
        case BGT_BOSS_GATE_BOTTOM:
        case BGT_COLOSSUS_EYE:
        case BGT_COLOSSUS_FANG:
            return BGPAL_CRACK;
        case BGT_POT:
        case BGT_SWITCH:
        case BGT_WILD_STUMP:
            return BGPAL_DOOR;
        case BGT_CRYSTAL:
        case BGT_PORTAL:
        case BGT_WILD_FLOWER:
        case BGT_WILD_WATER:
        case BGT_COLOSSUS_VOID:
        case BGT_COLOSSUS_RUNE:
        case BGT_COLOSSUS_MAW:
            return BGPAL_CRYSTAL;
        case BGT_DOOR:
            return (room_combat_sealed || room_puzzle_locked)
                ? BGPAL_CRACK : BGPAL_DOOR;
        default:
            if (tile == HUD_COIN
                || (tile >= HUD_DIGIT_0 && tile <= HUD_DIGIT_0 + 9))
                return BGPAL_CRACK;
            return BGPAL_FLOOR;
    }
}

void room_draw_tilemap(void) BANKED {
    u8 x, y;
    u8 attr_row[ROOM_W];
    u8 tile_row[ROOM_W];
    u8 horizontal_boss = (procgen_current_room_is_boss
        && room_world_width > ROOM_VIEW_W_PX
        && room_world_height == ROOM_VIEW_H_PX) ? 1 : 0;
    if ((room_world_width > ROOM_VIEW_W_PX
            || room_world_height > ROOM_VIEW_H_PX)
        && !horizontal_boss) {
        // The full renderer owns all 32 physical rows because a continuous
        // seam may rotate logical tile (0,0) away from hardware map (0,0).
        tiles_prepare_wide_field();
    } else {
        // A horizontal Colossus arena deliberately retains the compact
        // 17-row ABI. Render its western 20 columns normally, then the
        // specialist pass below authors columns 20..28. Previously only the
        // first boss used the far chamber and its western projection could
        // inherit the sanctuary's stale BG tiles.
        for (y = 0; y < ROOM_H; ++y) {
            for (x = 0; x < ROOM_W; ++x)
                tile_row[x] = room_tilemap[y][x];
            VBK_REG = 0;
            set_bkg_tiles(0, y, ROOM_W, 1, tile_row);
            for (x = 0; x < ROOM_W; ++x)
                attr_row[x] = render_attr(x, y, room_tilemap[y][x]);
            VBK_REG = 1;
            set_bkg_tiles(0, y, ROOM_W, 1, attr_row);
        }
    }
    tiles_draw_boss_cue(run_state.entered_from);
    if (procgen_current_room_is_boss && room_world_width > ROOM_VIEW_W_PX)
        tiles_prepare_crystal_wide_arena();
    else if (procgen_current_room_is_boss)
        tiles_prepare_colossal_edges();
    VBK_REG = 0;
    if (run_state.world_mode) tiles_draw_area_label(1);
    else if (RUN_ROOM_IS_TOWN(run_state.room_counter))
        tiles_draw_area_label((u8)(2 + run_state.world_return_screen));
}
