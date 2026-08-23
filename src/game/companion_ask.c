#pragma bank 9

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/companion.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"
#include "game/status.h"
#include "game/sram.h"
#include "render/tiles.h"
#include "content.h"

#define COMPANION_ASK_COOLDOWN 20

static entity_t *ask_companion_entity(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PICKUP
            && entities[i].ai_data[0] == PICKUP_COMPANION)
            return &entities[i];
    }
    return 0;
}

static void companion_reveal_route(void) {
    u8 dir;
    if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        run_state.next_dungeon_reveal |= 0x0F;
        return;
    }
    if (run_state.world_mode) {
        u8 here = run_state.world_screen;
        u8 edges = zelda_overworlds[0].screen_grid[here].edges;
        if ((edges & 1) && here >= ZELDA_WORLD_W)
            run_state_reveal_world_cell((u8)(here - ZELDA_WORLD_W));
        if ((edges & 2) && (here % ZELDA_WORLD_W) + 1 < ZELDA_WORLD_W)
            run_state_reveal_world_cell((u8)(here + 1));
        if ((edges & 4) && here + ZELDA_WORLD_W < ZELDA_WORLD_W * ZELDA_WORLD_H)
            run_state_reveal_world_cell((u8)(here + ZELDA_WORLD_W));
        if ((edges & 8) && (here % ZELDA_WORLD_W))
            run_state_reveal_world_cell((u8)(here - 1));
        return;
    }
    for (dir = DIR_N; dir <= DIR_W; ++dir) {
        u8 next = run_state_dungeon_cell_neighbor(
            run_state_dungeon_cell(), dir);
        if (next != 0xFF) run_state_reveal_dungeon_cell(next);
    }
}

u8 companion_ask(void) BANKED {
    entity_t *e = ask_companion_entity();
    u8 kind = companion_active_kind();
    if (run_state.companion_cooldown) {
        sfx_play(SFX_HURT);
        return 0;
    }
    if (kind == COMPANION_HEARTH) {
        if (player.hp >= player.hp_max || STATUS_PLAYER_HEALING_BLOCKED()) {
            sfx_play(SFX_HURT);
            return 0;
        }
        player.hp = (u8)(player.hp + 2);
        if (player.hp > player.hp_max) player.hp = player.hp_max;
        sfx_play(SFX_HEART);
    } else if (kind == COMPANION_AETHER) {
        if (player.mp >= player.mp_max) {
            sfx_play(SFX_HURT);
            return 0;
        }
        player.mp = (u8)(player.mp + 2);
        if (player.mp > player.mp_max) player.mp = player.mp_max;
        sfx_play_reward(SFX_REWARD_MAGIC);
    } else {
        companion_reveal_route();
        if (player.iframes < 45) player.iframes = 45;
        sfx_play(SFX_PUZZLE);
    }
    run_state.companion_cooldown = COMPANION_ASK_COOLDOWN;
    if (e) {
        e->state = 32;
        fx_spawn(SPR_FX_IMPACT, e->palette,
            FIX8_TO_INT(e->x), FIX8_TO_INT(e->y) - 8, 20);
    }
    sram_save_run();
    return 1;
}
