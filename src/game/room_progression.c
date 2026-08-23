#pragma bank 13

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

extern u8 room_mire_projection_state;

// Progression fixtures run after procgen has populated geometry. Keeping this
// cold transaction out of the every-frame room bank preserves emergency ROM
// headroom for collision and transition fixes.
void room_spawn_progression_fixture(void) BANKED {
    u8 i;
    u8 arena_stage = room_apply_world_arena();
    if (arena_stage == 4) room_mire_projection_state = 0xFF;
    room_sigil_status = 1;
    if (run_state.world_mode) return;
    room_sigil_status = 2;
    if (run_state_dungeon_local() != run_state.mission_sigil_cell) return;
    room_sigil_status = 3;
    if (run_state.rift_sigils
        & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten)) return;
    room_sigil_status = 4;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PICKUP
            && entities[i].ai_data[0] == PICKUP_RIFT_SIGIL) {
            room_sigil_status = 5;
            return;
        }
    }
    {
        u8 sigil = pickup_spawn(PICKUP_RIFT_SIGIL, FIX8(80), FIX8(64));
        if (sigil != 0xFF) {
            room_sigil_status = 5;
            entities[sigil].sprite_tile = SPR_ITEM_RIFT_SIGIL;
            entities[sigil].palette = 0x06;
            entities[sigil].state_timer = 0;
        }
    }
}
