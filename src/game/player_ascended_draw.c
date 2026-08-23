#pragma bank 11

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

// Cold powered-form OAM helper: paid only during the 18-second convergence,
// keeping the always-hot room bank comfortably below its emergency floor.
void room_draw_ascended_walk_lower(u8 class_id, u8 frame, u8 prop) BANKED {
    u8 step = (u8)(SPR_CLASS_ASCENDED_STEP_BASE + (u8)(class_id * 2));
    if (frame & 0x08) {
        set_sprite_tile(2, (u8)(step + 1));
        set_sprite_tile(3, step);
        set_sprite_prop(2, (u8)(prop | S_FLIPX));
        set_sprite_prop(3, (u8)(prop | S_FLIPX));
    } else {
        set_sprite_tile(2, step);
        set_sprite_tile(3, (u8)(step + 1));
        set_sprite_prop(2, prop);
        set_sprite_prop(3, prop);
    }
}

u8 room_input_dir8(u8 keys, u8 facing) BANKED {
    if (keys & J_UP) {
        if (keys & J_RIGHT) return 1;
        if (keys & J_LEFT) return 7;
        return 0;
    }
    if (keys & J_DOWN) {
        if (keys & J_RIGHT) return 3;
        if (keys & J_LEFT) return 5;
        return 4;
    }
    if (keys & J_RIGHT) return 2;
    if (keys & J_LEFT) return 6;
    switch (facing) {
        case FACE_N: return 0;
        case FACE_E: return 2;
        case FACE_W: return 6;
        default: return 4;
    }
}
