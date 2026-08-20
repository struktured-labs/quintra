#pragma bank 6

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "render/tiles.h"
#include "content.h"

extern u8 entity_anim_counter;
extern u8 entity_oam_high;

static u8 enemy_is_big16(const entity_t *e) {
    u8 eid = e->ai_data[0];
    if (e->type != ENT_ENEMY) return 0;
    if (eid == ENEMY_STONE_SENTINEL) return 1;
    return (eid == ENEMY_ORC || eid == ENEMY_BOMBER || eid == ENEMY_WARLOCK
        || eid == ENEMY_CINDER_MAW);
}

static u8 world_camera_step(u8 current, i16 player_pos,
                            u8 world_extent, u8 view_extent) {
    u8 anchor = (u8)((view_extent - 16) >> 1);
    u8 desired = (player_pos > anchor) ? (u8)(player_pos - anchor) : 0;
    u8 max_camera = (u8)(world_extent - view_extent);
    if (desired > max_camera) desired = max_camera;
    if (current < desired) {
        current = (u8)(current + 2);
        if (current > desired) current = desired;
    } else if (current > desired) {
        current = (current >= 2) ? (u8)(current - 2) : 0;
        if (current < desired) current = desired;
    }
    return current;
}

void entity_draw_all_world(void) BANKED {
    u8 i;
    u8 oam = serpent_tail_active ? 32 : cinder_pack_active ? 22 : 4;
    room_camera_x = (room_world_width > ROOM_VIEW_W_PX)
        ? world_camera_step(room_camera_x, player.x,
            room_world_width, ROOM_VIEW_W_PX) : 0;
    room_camera_y = (room_world_height > ROOM_VIEW_H_PX)
        ? world_camera_step(room_camera_y, player.y,
            room_world_height, ROOM_VIEW_H_PX) : 0;
#define ENTITY_DRAW_SX(e) \
    ((u8)(FIX8_TO_INT((e)->x) - room_camera_x + 8))
#define ENTITY_DRAW_SY(e) \
    ((u8)(FIX8_TO_INT((e)->y) - room_camera_y + 16))
#include "game/entity_draw_core.h"
#undef ENTITY_DRAW_SX
#undef ENTITY_DRAW_SY
}
