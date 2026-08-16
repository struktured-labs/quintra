#pragma bank 5

#include <gb/gb.h>

#include "core/types.h"
#include "game/procgen.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

void serpent_tail_reset(u8 head_x, u8 head_y) BANKED {
    u8 i;
    serpent_tail_x[0] = head_x;
    serpent_tail_y[0] = head_y;
    // Seed a short connected neck behind the head. The trail replaces these
    // points naturally as soon as the Serpent begins hunting its first mote.
    for (i = 1; i < SERPENT_TAIL_POINTS; ++i) {
        serpent_tail_x[i] = (head_x > (u8)(i * 5))
            ? (u8)(head_x - i * 5) : 4;
        serpent_tail_y[i] = head_y;
    }
    serpent_tail_count = SERPENT_TAIL_POINTS;
    serpent_tail_visible = 2;
    serpent_tail_active = 1;
    serpent_head_index = 0xFF;
    // Procgen creates the giant before applying its wide-arena fixture. Bind
    // the dedicated renderer here, after the fixture reset, so the generic
    // 4x4 Colossus path can never reclaim the Serpent head.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
            && (entities[i].ai_data[3] & 1)
            && entities[i].ai_data[2] == 1) {
            serpent_head_index = i;
            // enemy_spawn gives ordinary enemies a random heading in state.
            // For the Serpent that byte is a strict feed/AOE/contract phase;
            // random 1 or 2 would skip Snake play entirely on room entry.
            entities[i].state = 0;
            entities[i].state_timer = 0;
            entities[i].ai_data[4] = 0;
            entities[i].vx = entities[i].vy = 0;
            break;
        }
    }
}

u8 room_apply_world_arena(void) BANKED {
    u8 stage;
    u8 generated_wide = (run_state.world_mode
        || procgen_current_room_is_large) ? 1 : 0;
    if (serpent_tail_active) {
        u8 oam;
        for (oam = 4; oam < 30; ++oam) move_sprite(oam, 0, 0);
    }
    serpent_tail_active = 0;
    serpent_head_index = 0xFF;
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
    // Penta Dragon's stage bosses are not only large pictures: their fights
    // occupy fields wider than the handheld viewport. Give every Colossus
    // that same arena language. The far-east chamber stays within the 32x32
    // hardware map, so this adds a genuine camera traverse without the
    // transition and ring-buffer complexity of a second dungeon district.
    room_world_width = ROOM_COLOSSUS_W_PX;
    room_camera_x = (run_state.entered_from == DIR_W)
        ? (ROOM_COLOSSUS_W_PX - ROOM_VIEW_W_PX) : 0;
    // Leaving a sanctuary west means entering the arena through its eastern
    // threshold. Procgen positions compact rooms at x=136; move that arrival
    // to the real far edge so the fight opens with a readable approach rather
    // than materialising near its centre.
    if (run_state.entered_from == DIR_W)
        player.x = (ppos_t)(ROOM_COLOSSUS_W_PX - 24);
    // Column 19 was the compact room border. It is now the walkable seam into
    // the far chamber for every stage, not just Crystal's tutorial arena.
    {
        u8 y;
        for (y = 1; y < ROOM_H - 1; ++y)
            room_tilemap[y][ROOM_W - 1] = BGT_FLOOR;
    }
    if (stage == 0) {
        tiles_paint_crystal_projection();
    } else if (stage == 1) {
        // Spawn coordinates are (64,48), with the broad 32x24 head's route
        // anchor at (76,60). Its tail is entirely OBJ-based and connected to
        // that moving head; no detached background body is painted here.
        serpent_tail_reset(76, 60);
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

// Tile lookup is shared by several switchable gameplay banks and sits on
// collision/hazard hot paths. Keeping it always mapped avoids a ROM-bank
// round trip for every sampled tile while the colder world builders remain
// in bank 5.
u8 room_tile_at_px(i16 px, i16 py) NONBANKED {
    if (px < 0 || py < 0) return BGT_WALL;
    {
        u8 tx = (u8)(px >> 3);
        u8 ty = (u8)(py >> 3);
        // Keep the row test outermost. SDCC 4.4 can corrupt the temporary
        // for `height > view && ty >= ROOM_H` in this banked function after
        // the 31x31 index arithmetic is introduced, turning every southern
        // field row into a wall. The nested form is equivalent C but compiles
        // into independent comparisons on real hardware.
        if (ty >= ROOM_H) {
            if (room_world_height <= ROOM_VIEW_H_PX
                || tx >= ROOM_WIDE_W_TILES || ty >= ROOM_WIDE_H_TILES)
                return BGT_WALL;
            return (u8)(room_world_bottom[ty - ROOM_H][tx] & 0x7F);
        }
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

u8 room_player_position_in_bounds(i16 x, i16 y) BANKED {
    return (x >= 0 && y >= 0
        && x <= (i16)(room_world_width - 16)
        && y <= (i16)(room_world_height - 16)) ? 1 : 0;
}

// Like room_tile_at_px(), this predicate is used many times per movement
// probe from several gameplay banks. Keep it always mapped so stricter
// six-point collision does not pay a ROM-bank round trip for every sample.
u8 room_tile_walkable(u8 t) NONBANKED {
    return (t == BGT_FLOOR || t == BGT_FLOOR2 || t == BGT_FLOOR3
         || t == BGT_GRASS || t == BGT_PATH || t == BGT_WILD_FLOWER
         || t == BGT_RUBBLE || t == BGT_DOOR || t == BGT_SPIKES
         || t == BGT_SWITCH || t == BGT_PORTAL
         || (t >= BGT_COLOSSUS_VOID && t <= BGT_COLOSSUS_HORN)
         // Shop price tags are painted floor (coin glyph + digits)
         || t == HUD_COIN || (t >= HUD_DIGIT_0 && t <= HUD_DIGIT_0 + 9));
}
