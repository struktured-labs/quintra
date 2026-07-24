#pragma bank 5

#include "core/types.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 room_apply_world_arena(void) BANKED {
    u8 stage;
    u8 generated_wide = (run_state.world_mode
        || procgen_current_room_is_large) ? 1 : 0;
    // Generation always returns to the one-screen contract first. The pack
    // resume path skips this function, preserving a live scrolling camera.
    room_world_width = generated_wide ? ROOM_WIDE_W_PX : ROOM_VIEW_W_PX;
    room_world_height = generated_wide ? ROOM_WIDE_H_PX : ROOM_VIEW_H_PX;
    // Entering a field from its eastern/northern neighbour must reveal the
    // arrival immediately rather than parking the hero beyond the viewport.
    room_camera_x = (generated_wide && run_state.entered_from == DIR_W)
        ? (ROOM_WIDE_W_PX - ROOM_VIEW_W_PX) : 0;
    room_camera_y = (generated_wide && run_state.entered_from == DIR_N)
        ? (ROOM_WIDE_H_PX - ROOM_VIEW_H_PX) : 0;
    if (generated_wide || !procgen_current_room_is_boss) return 0xFF;

    stage = run_state.bosses_beaten;
    if (stage >= N_STAGES) stage = (u8)(stage % N_STAGES);
    if (stage == 0) {
        room_world_width = ROOM_CRYSTAL_W_PX;
        tiles_paint_crystal_projection();
    } else if (stage == 1) {
        tiles_paint_serpent_projection();
    } else if (stage == 2) {
        tiles_paint_cinder_projection();
    } else if (stage == 3) {
        tiles_paint_spider_projection();
    } else if (stage == 4) {
        tiles_paint_mire_projection(0, 0);
    } else if (stage == 5) {
        tiles_paint_reaper_projection();
    } else if (stage == 6) {
        tiles_paint_golem_projection();
    } else if (stage == 7) {
        tiles_paint_hydra_projection();
    } else {
        tiles_paint_void_projection();
    }
    return stage;
}

// Cold/banked world-coordinate queries live outside the crowded gameplay
// bank. Every caller already uses the BANKED contract declared by room.h.
u8 room_tile_at_px(i16 px, i16 py) BANKED {
    if (px < 0 || py < 0) return BGT_WALL;
    {
        u8 tx = (u8)(px >> 3);
        u8 ty = (u8)(py >> 3);
        if (room_world_height > ROOM_VIEW_H_PX && ty >= ROOM_H) {
            if (tx >= ROOM_WIDE_W_TILES || ty >= ROOM_WIDE_H_TILES)
                return BGT_WALL;
            return (u8)(room_world_bottom[ty - ROOM_H][tx] & 0x7F);
        }
        if (ty >= ROOM_H) return BGT_WALL;
        if (tx >= ROOM_W) {
            if (room_world_width <= ROOM_VIEW_W_PX
                || tx >= ROOM_WIDE_W_TILES) return BGT_WALL;
            if (room_world_height > ROOM_VIEW_H_PX)
                return (u8)(room_world_extension[ty][tx - ROOM_W] & 0x7F);
            // The far east threshold replaces the obsolete viewport seam
            // after Crystal falls. Before then it remains a real arena wall.
            if (tx == ROOM_CRYSTAL_W_TILES - 1) {
                if ((ty == 8 || ty == 9) && run_state_was_cleared_boss())
                    return BGT_DOOR;
                return BGT_WALL;
            }
            if (ty == 0 || ty == ROOM_H - 1) return BGT_WALL;
            // Extension projection tiles are visual, walkable spirit-space.
            return BGT_FLOOR;
        }
        // Bit 7 is generator-only reachability scratch. Room preparation
        // clears it before rendering, but collision must remain correct even
        // if a later diagnostic/placement pass marks the same WRAM tile.
        return (u8)(room_tilemap[ty][tx] & 0x7F);
    }
}

u8 room_tile_walkable(u8 t) BANKED {
    return (t == BGT_FLOOR || t == BGT_FLOOR2 || t == BGT_FLOOR3
         || t == BGT_GRASS || t == BGT_PATH || t == BGT_WILD_FLOWER
         || t == BGT_RUBBLE || t == BGT_DOOR || t == BGT_SPIKES
         || t == BGT_SWITCH || t == BGT_PORTAL
         || (t >= BGT_COLOSSUS_VOID && t <= BGT_COLOSSUS_HORN)
         // Shop price tags are painted floor (coin glyph + digits)
         || t == HUD_COIN || (t >= HUD_DIGIT_0 && t <= HUD_DIGIT_0 + 9));
}
