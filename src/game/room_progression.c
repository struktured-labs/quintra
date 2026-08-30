#pragma bank 13

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dialog.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

extern u8 room_mire_projection_state;
extern u8 room_resume_flag;
extern u8 shake_timer;
extern u8 shake_mag;

void room_shake(u8 mag, u8 frames) BANKED {
    shake_mag = mag;
    if (frames > shake_timer) shake_timer = frames;
}

void room_request_resume(void) BANKED {
    room_resume_flag = 1;
}

// Dungeon arrivals reuse one three-region fanfare policy regardless of
// whether the transition came from a cardinal path or a Riftwild portal.
// Keeping this cold block out of room's nearly-full hot bank also prevents
// the two paths from drifting apart again.
void room_prepare_stage_arrival(u8 stage) BANKED {
    dialog_prepare_stage(stage);
    if (stage < 3) sfx_play_reward(SFX_REWARD_UNLOCK);
    else if (stage < 6) sfx_play_reward(SFX_REWARD_MAGIC);
    else sfx_play_reward(SFX_REWARD_RELIC);
}

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
