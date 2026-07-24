#pragma bank 6

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "game/room.h"
#include "content.h"

extern u8 entity_anim_counter;

static u8 enemy_is_big16(const entity_t *e) {
    u8 eid = e->ai_data[0];
    if (e->type != ENT_ENEMY) return 0;
    if (eid == ENEMY_STONE_SENTINEL) return 1;
    return (eid == ENEMY_ORC || eid == ENEMY_BOMBER || eid == ENEMY_WARLOCK);
}

void entity_draw_all_world(void) BANKED {
    u8 i;
    u8 oam = 4;
#define ENTITY_DRAW_SX(e) \
    ((u8)(FIX8_TO_INT((e)->x) - room_camera_x + 8))
#define ENTITY_DRAW_SY(e) \
    ((u8)(FIX8_TO_INT((e)->y) - room_camera_y + 16))
#include "game/entity_draw_core.h"
#undef ENTITY_DRAW_SX
#undef ENTITY_DRAW_SY
}
