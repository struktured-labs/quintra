#pragma bank 11

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

extern u8 player_penta_aim;
extern u8 aim_release_grace;

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
    // Hold Aim keeps the last 8-way heading, diagonals included. Classic
    // still collapses a released diagonal onto the cardinal facing byte.
    if (player_penta_aim) return (u8)(player_aim_dir & 7);
    switch (facing) {
        case FACE_N: return 0;
        case FACE_E: return 2;
        case FACE_W: return 6;
        default: return 4;
    }
}

// dir8 index for a live step. Callers only pass a nonzero axis pair.
static u8 room_aim_from_step(i8 dx, i8 dy) {
    if (dy < 0) {
        if (dx > 0) return 1;
        if (dx < 0) return 7;
        return 0;
    }
    if (dy > 0) {
        if (dx > 0) return 3;
        if (dx < 0) return 5;
        return 4;
    }
    return (dx < 0) ? 6 : 2;
}

// Hold Aim: a diagonal that collapses to one of its own cardinals must not
// overwrite the stored 8-way heading for a few leftover-key frames. A
// deliberate new cardinal, or holding that leftover key past the window,
// still replaces it. Classic writes every live heading immediately.
void room_retain_aim(i8 dx, i8 dy) BANKED {
    u8 new_aim, stored;
    if (!(dx || dy)) {
        aim_release_grace = 0;
        return;
    }
    new_aim = room_aim_from_step(dx, dy);
    if (dx && dy) {
        player_aim_dir = new_aim;
        aim_release_grace = player_penta_aim ? 5 : 0;
        return;
    }
    if (player_penta_aim && aim_release_grace) {
        stored = (u8)(player_aim_dir & 7);
        if ((stored & 1)
            && (new_aim == (u8)((stored - 1) & 7)
                || new_aim == (u8)((stored + 1) & 7))) {
            if (--aim_release_grace == 0) player_aim_dir = new_aim;
            return;
        }
    }
    player_aim_dir = new_aim;
    aim_release_grace = 0;
}
