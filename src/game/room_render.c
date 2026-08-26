#pragma bank 6

#include <gb/gb.h>

#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

u8 room_district_label_ticks;
static u8 room_district_label_kind;
static u8 room_district_label_stage;

void room_show_district_label(u8 kind) BANKED {
    if (kind != room_district_label_kind
        || run_state.bosses_beaten != room_district_label_stage) {
        room_district_label_kind = kind;
        room_district_label_stage = run_state.bosses_beaten;
        room_district_label_ticks = 120; // two-second Zelda-style arrival beat
        tiles_draw_area_label(kind);
    } else {
        // A redraw or a seam within the same district restores ordinary
        // terrain. Do not turn the callout into permanent map signage.
        room_district_label_ticks = 0;
        tiles_stream_wide_row(1, ROOM_BG_MAP_Y(1));
    }
}

void room_show_directive_label(u8 kind) BANKED {
    // Unlike a district name, a directive is a new first-visit event even if
    // the previous room happened to roll the same verb. Always replay its
    // compact arrival card, then let the ordinary row restore erase it.
    room_district_label_ticks = 90;
    tiles_draw_area_label(kind);
}

static u8 render_attr(u8 x, u8 y, u8 tile) {
    if (room_puzzle_kind == PUZZLE_PHASE_SWITCH && y == 8
        && (x == 4 || x == 8 || x == 12 || x == 16)
        && tile == BGT_FLOOR2) return BGPAL_CRYSTAL;
    if (room_puzzle_kind == PUZZLE_PHASE_GATE
        && y == room_puzzle_visual_y && x >= 4 && x < ROOM_W - 4)
        return (run_state.dungeon_phase & room_puzzle_phase_bit)
            ? BGPAL_CRYSTAL : BGPAL_CRACK;
    switch (tile) {
        case BGT_WALL:
        case BGT_ARROW_TRAP:
        case BGT_PILLAR:
        case BGT_ROOF:
        case BGT_FENCE:
        case BGT_TREE:
        case BGT_WILD_STONE:
        case BGT_GATE_BOULDER:
        case BGT_GATE_THORNS:
        case BGT_GATE_VENT:
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
        case BGT_GATE_WATER:
        case BGT_GATE_CHASM:
        case BGT_COLOSSUS_VOID:
        case BGT_COLOSSUS_RUNE:
        case BGT_COLOSSUS_MAW:
            return BGPAL_CRYSTAL;
        case BGT_DOOR_LOCKED:
            return BGPAL_CRACK;
        case BGT_DOOR:
            if ((y == 0 && room_objective_dir == DIR_N)
                || (x == ROOM_W - 1 && room_objective_dir == DIR_E)
                || (y == ROOM_H - 1 && room_objective_dir == DIR_S)
                || (x == 0 && room_objective_dir == DIR_W))
                return BGPAL_CRYSTAL;
            return BGPAL_DOOR;
        default:
            if (tile == HUD_COIN
                || (tile >= HUD_DIGIT_0 && tile <= HUD_DIGIT_0 + 9))
                return BGPAL_CRACK;
            return BGPAL_FLOOR;
    }
}

static u8 compact_door_locked(u8 x, u8 y) {
    u8 dir = DIR_NONE;
    u8 neighbor;
    if (!(room_combat_sealed || room_puzzle_locked)) return 0;
    if (y == 0) dir = DIR_N;
    else if (x == ROOM_W - 1) dir = DIR_E;
    else if (y == ROOM_H - 1) dir = DIR_S;
    else if (x == 0) dir = DIR_W;
    if (dir == DIR_NONE) return 0;
    if (run_state.entered_from != DIR_NONE
        && dir == (u8)((run_state.entered_from + 2) & 3)) return 0;
    if (!run_state.world_mode) {
        neighbor = run_state_dungeon_neighbor(dir);
        if (neighbor != 0xFF) {
            u8 local = (u8)(neighbor
                - run_state_stage_start(run_state.bosses_beaten));
            if (run_state_dungeon_cell_seen(local)) return 0;
        }
    }
    return 1;
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
            for (x = 0; x < ROOM_W; ++x) {
                u8 tile = room_tilemap[y][x];
                tile_row[x] = (tile == BGT_DOOR
                    && compact_door_locked(x, y))
                    ? BGT_DOOR_LOCKED : tile;
            }
            VBK_REG = 0;
            set_bkg_tiles(0, y, ROOM_W, 1, tile_row);
            for (x = 0; x < ROOM_W; ++x)
                attr_row[x] = render_attr(x, y, tile_row[x]);
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
    else if (room_return_echo_kind)
        room_show_directive_label(14); // unmistakable RIFT return card
    else if (room_encounter_kind != ENCOUNTER_SKIRMISH)
        room_show_directive_label((u8)(9 + room_encounter_kind));
    else if (procgen_current_room_is_large)
        room_show_district_label((u8)(5
            + run_state_dungeon_local() / DUNGEON_GRID_W));
}
