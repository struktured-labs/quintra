#pragma bank 7

#include <gb/gb.h>
#include <string.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/will.h"

void entity_init_room(void) BANKED {
    u8 i;
    u8 dir;
    u8 large;
    memset(entities, 0, sizeof(entities));
    entity_enemy_count = 0;
    // A target mark belongs to its concrete entity, never to a slot reused
    // after a room transition. Timed self-effects such as Vespine's swarm
    // may continue naturally across that doorway.
    will_corvin_mark_slot = 0xFF;
    will_corvin_mark_ticks = 0;
    // Park entity sprites (slots 4..35) + boss metasprite overlay (36..39).
    for (i = 4; i < 40; ++i)
        move_sprite(i, 0, 0);

    // Spawn just inside the door opposite the exit. The player's wall box is
    // the feet half, so x=72 centers it on north/south doors and y=60 on the
    // east/west pair.
    dir = run_state.entered_from;
    large = (run_state.world_mode || procgen_current_room_is_large) ? 1 : 0;
    if (dir == DIR_N) {
        player.x = 72;
        player.y = large ? (ROOM_WIDE_H_PX - 24) : 112;
    } else if (dir == DIR_S) {
        player.x = 72;
        player.y = 8;
    } else if (dir == DIR_E) {
        player.x = 8;
        player.y = 60;
    } else if (dir == DIR_W) {
        player.x = large ? (ROOM_WIDE_W_PX - 24) : 136;
        player.y = 60;
    } else {
        // Direct checkpoints and nonlinear portals use the intersection of
        // the guaranteed horizontal and vertical trails. A large room's old
        // y=92 fallback occupied only the vertical feet lane: stage scenery
        // could overlap the hero's upper half there and the full-body
        // collision contract would then (correctly) reject every escape step.
        player.x = 72;
        player.y = 60;
    }
}

// Scrolling-field bodies persist across a 248x248 district, but should not
// march or shoot from an unseen camera sector. The shared flag gates AI,
// collision, and OAM allocation until exploration reaches that cluster.
void entity_refresh_world_visibility(void) BANKED {
    u8 i;
    // entity_update_all() calls this only when the camera enters a new 16px
    // sector. Cover every camera position inside that sector, not only the
    // exact boundary position at which the refresh happened. Otherwise a
    // camera that settles later in the same sector can visibly expose an
    // enemy while leaving EF_ON_SCREEN clear forever. Signed bounds avoid
    // wrapping the padded east/south edge of a 248px district.
    i16 left = (i16)room_camera_x - 15;
    i16 top = (i16)room_camera_y - 15;
    i16 right = (i16)room_camera_x + ROOM_VIEW_W_PX + 15;
    i16 bottom = (i16)room_camera_y + ROOM_VIEW_H_PX + 15;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 x, y;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        x = FIX8_TO_INT(e->x);
        y = FIX8_TO_INT(e->y);
        if (x >= left && x < right && y >= top && y < bottom)
            e->flags |= EF_ON_SCREEN;
        else
            e->flags &= (u8)~EF_ON_SCREEN;
    }
}
