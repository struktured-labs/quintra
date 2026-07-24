#pragma bank 5

#include "core/types.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"

// Cold/banked world-coordinate queries live outside the crowded gameplay
// bank. Every caller already uses the BANKED contract declared by room.h.
u8 room_tile_at_px(i16 px, i16 py) BANKED {
    if (px < 0 || py < 0) return BGT_WALL;
    {
        u8 tx = (u8)(px >> 3);
        u8 ty = (u8)(py >> 3);
        if (ty >= ROOM_H) return BGT_WALL;
        if (tx >= ROOM_W) {
            if (room_world_width <= ROOM_VIEW_W_PX
                || tx >= ROOM_WIDE_W_TILES) return BGT_WALL;
            if (run_state.world_mode)
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
