#pragma bank 6

#include <gb/gb.h>

#include "audio/audio.h"
#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

// The seam owns OAM positions only. The resident room renderer has already
// selected the champion's current pose, tiles, palette, and flip attributes.
static void seam_place_player(u8 sx, u8 sy) {
    move_sprite(0, sx, sy);
    move_sprite(1, (u8)(sx + 8), sy);
    move_sprite(2, sx, (u8)(sy + 8));
    move_sprite(3, (u8)(sx + 8), (u8)(sy + 8));
}

static void seam_vbl(void) {
    wait_vbl_done();
    audio_tick();
}

// Stream one complete 31x31 destination through the hardware map ring while
// its shared edge crosses the LCD. Unlike the compact Zelda room slide, the
// champion remains visible and the LCD never blanks: consecutive wide graph
// nodes therefore read as one continuous district even though each node keeps
// independent procgen, enemies, objectives, and Compass identity.
void room_stream_wide_seam(u8 dir) BANKED {
    u8 step;
    u8 steps = (dir == DIR_E || dir == DIR_W) ? 20 : 17;
    u8 remainder = (dir == DIR_E || dir == DIR_W) ? 16 : 10;
    u8 error = 0;
    i16 sprite_pos;
    i8 sprite_sign;
    u8 fixed_pos;
    u8 start_scroll;
    u8 target_x = room_bg_origin_x;
    u8 target_y = room_bg_origin_y;

    if (dir == DIR_E) {
        target_x = (u8)((room_bg_origin_x + 31) & 31);
        sprite_pos = 152; sprite_sign = -1; fixed_pos = 76;
        start_scroll = (u8)((room_bg_origin_x << 3) + 88);
    } else if (dir == DIR_W) {
        target_x = (u8)((room_bg_origin_x + 1) & 31);
        sprite_pos = 8; sprite_sign = 1; fixed_pos = 76;
        start_scroll = (u8)(room_bg_origin_x << 3);
    } else if (dir == DIR_S) {
        target_y = (u8)((room_bg_origin_y + 31) & 31);
        sprite_pos = 136; sprite_sign = -1; fixed_pos = 80;
        start_scroll = (u8)((room_bg_origin_y << 3) + 112);
    } else {
        target_y = (u8)((room_bg_origin_y + 1) & 31);
        sprite_pos = 16; sprite_sign = 1; fixed_pos = 80;
        start_scroll = (u8)(room_bg_origin_y << 3);
    }

    for (step = 0; step < steps; ++step) {
        seam_vbl();
        if (dir == DIR_E) {
            u8 logical = step;
            tiles_stream_wide_column(logical,
                (u8)((target_x + logical) & 31));
            SCX_REG = (u8)(start_scroll + ((step + 1) << 3));
        } else if (dir == DIR_W) {
            u8 logical = (u8)(30 - step);
            tiles_stream_wide_column(logical,
                (u8)((target_x + logical) & 31));
            SCX_REG = (u8)(start_scroll - ((step + 1) << 3));
        } else if (dir == DIR_S) {
            u8 logical = step;
            tiles_stream_wide_row(logical,
                (u8)((target_y + logical) & 31));
            SCY_REG = (u8)(start_scroll + ((step + 1) << 3));
        } else {
            u8 logical = (u8)(30 - step);
            tiles_stream_wide_row(logical,
                (u8)((target_y + logical) & 31));
            SCY_REG = (u8)(start_scroll - ((step + 1) << 3));
        }
        sprite_pos += (i16)sprite_sign * 6;
        error = (u8)(error + remainder);
        if (error >= steps) {
            error = (u8)(error - steps);
            sprite_pos += sprite_sign;
        }
        if (dir == DIR_E || dir == DIR_W)
            seam_place_player((u8)sprite_pos, fixed_pos);
        else
            seam_place_player(fixed_pos, (u8)sprite_pos);
    }

    // Finish the destination's offscreen half one line per VBlank. These
    // writes cannot appear on the LCD, but completing them now guarantees
    // immediate free camera travel and reversible backtracking.
    if (dir == DIR_E) {
        for (step = 20; step < 32; ++step) {
            seam_vbl();
            tiles_stream_wide_column(step, (u8)((target_x + step) & 31));
        }
    } else if (dir == DIR_W) {
        for (step = 0; step < 11; ++step) {
            seam_vbl();
            tiles_stream_wide_column(step, (u8)((target_x + step) & 31));
        }
        seam_vbl();
        tiles_stream_wide_column(31, (u8)((target_x + 31) & 31));
    } else if (dir == DIR_S) {
        for (step = 17; step < 32; ++step) {
            seam_vbl();
            tiles_stream_wide_row(step, (u8)((target_y + step) & 31));
        }
    } else {
        for (step = 0; step < 14; ++step) {
            seam_vbl();
            tiles_stream_wide_row(step, (u8)((target_y + step) & 31));
        }
        seam_vbl();
        tiles_stream_wide_row(31, (u8)((target_y + 31) & 31));
    }
    // Publish the rotated origin only after every logical line is resident.
    // Emulator tests, SELECT/START resumes, and ordinary room drawing can
    // therefore treat an origin change as an atomic completed seam.
    room_bg_origin_x = target_x;
    room_bg_origin_y = target_y;
    SCX_REG = (u8)((room_bg_origin_x << 3) + room_camera_x);
    SCY_REG = (u8)((room_bg_origin_y << 3) + room_camera_y);
    seam_place_player(
        (u8)((i16)player.x - room_camera_x + 8),
        (u8)((i16)player.y - room_camera_y + 16));
    // The destination atlas has just rotated into place. Restore its
    // display-only geographic sign here in the roomy streaming bank instead
    // of burdening the resident combat loop.
    if (run_state.world_mode)
        tiles_draw_area_label(1);
    else if (room_encounter_kind != ENCOUNTER_SKIRMISH)
        room_show_directive_label((u8)(9 + room_encounter_kind));
    else
        room_show_district_label((u8)(5
            + run_state_dungeon_local() / DUNGEON_GRID_W));
}
