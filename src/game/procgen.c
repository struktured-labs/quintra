#include <gb/gb.h>

#include "core/types.h"
#include "core/rng.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"
#include "core/types.h"
#include "content.h"

u32 procgen_room_seed(u32 run_seed, u8 biome_id, u8 room_counter) {
    return run_seed ^ ((u32)biome_id << 16) ^ ((u32)room_counter * 0x9E3779B9UL);
}

// Sample an enemy from the biome's enemy_pool using cumulative weights.
static u8 pick_enemy_from_biome(const biome_def_t *bio) {
    u16 total = 0;
    u8 i;
    for (i = 0; i < bio->n_enemy_pool; ++i) total = (u16)(total + bio->enemy_pool[i].weight);
    if (total == 0) return bio->enemy_pool[0].enemy_id;
    {
        u16 roll = (u16)((rng_next() & 0xFFFFUL) % total);
        u16 acc  = 0;
        for (i = 0; i < bio->n_enemy_pool; ++i) {
            acc = (u16)(acc + bio->enemy_pool[i].weight);
            if (roll < acc) return bio->enemy_pool[i].enemy_id;
        }
    }
    return bio->enemy_pool[0].enemy_id;
}

// Place player at the door opposite the one they entered from.
static void place_player_after_entry(void) {
    u8 dir = run_state.entered_from;
    u8 tx, ty;
    if (dir == DIR_N)      { tx = ROOM_W / 2; ty = ROOM_H - 3; }
    else if (dir == DIR_S) { tx = ROOM_W / 2; ty = 2; }
    else if (dir == DIR_E) { tx = 2;          ty = ROOM_H / 2; }
    else if (dir == DIR_W) { tx = ROOM_W - 3; ty = ROOM_H / 2; }
    else                   { tx = ROOM_W / 2; ty = ROOM_H / 2; }
    player.x = (ppos_t)((i16)tx * 8);
    player.y = (ppos_t)((i16)ty * 8);
}

void procgen_generate_current_room(void) {
    const biome_def_t *bio = &biomes[run_state.biome_id];
    u32 seed = procgen_room_seed(run_state.run_seed, run_state.biome_id, run_state.room_counter);
    rng_seed(seed);

    // Build the room from a template (Phase 7: just the first template in
    // biome's room_template_pool — a 4-door empty Small room).
    // Real Phase 9 will pick by kind + door-mask compatibility.
    bio;
    {
        u8 x, y;
        u8 is_boss_room = (run_state.room_counter == BOSS_ROOM_DEPTH && !run_state.victory) ? 1 : 0;
        for (y = 0; y < ROOM_H; ++y) {
            for (x = 0; x < ROOM_W; ++x) {
                if (y == 0 || y == ROOM_H - 1 || x == 0 || x == ROOM_W - 1) {
                    room_tilemap[y][x] = BGT_WALL;
                } else {
                    room_tilemap[y][x] = BGT_FLOOR;
                }
            }
        }
        // Boss room: doors sealed (locked-in fight). Otherwise: open all 4.
        if (!is_boss_room) {
            room_tilemap[0][ROOM_W / 2]            = BGT_DOOR;
            room_tilemap[ROOM_H - 1][ROOM_W / 2]   = BGT_DOOR;
            room_tilemap[ROOM_H / 2][0]            = BGT_DOOR;
            room_tilemap[ROOM_H / 2][ROOM_W - 1]   = BGT_DOOR;
        }
    }

    // Clear entity table — fresh enemies per room
    entity_init_all();

    // Debug markers (HRAM) — kept for ongoing diagnosis
    *(volatile u8*)0xFFFE = run_state.room_counter;
    *(volatile u8*)0xFFFD = run_state.victory;

    if (run_state.room_counter == BOSS_ROOM_DEPTH && !run_state.victory) {
        *(volatile u8*)0xFFFC = 0xBB;
        u8 idx = enemy_spawn(1, ROOM_W / 2, ROOM_H / 2);
        if (idx != 0xFF) {
            entities[idx].palette     = 0x06;
            entities[idx].sprite_tile = SPR_BOSS;
            entities[idx].hitbox      = (8 << 4) | 8;
        }
    } else {
        *(volatile u8*)0xFFFC = 0x00;
        u8 enemy_count = (u8)(1 + rng_range(4));   // 1..4
        u8 i;
        for (i = 0; i < enemy_count; ++i) {
            u8 tx = (u8)(2 + rng_range(ROOM_W - 4));
            u8 ty = (u8)(2 + rng_range(ROOM_H - 4));
            if (tx == (u8)(FIX8_TO_INT(player.x) >> 3)
                && ty == (u8)(FIX8_TO_INT(player.y) >> 3)) {
                continue;
            }
            {
                // Filter out the boss enemy from regular spawns
                u8 eid = pick_enemy_from_biome(&biomes[run_state.biome_id]);
                if (eid == 1) eid = 0;   // demote sentinel to crawler in normal rooms
                {
                    u8 idx = enemy_spawn(eid, tx, ty);
                    if (idx != 0xFF) entities[idx].palette = 0x03;
                }
            }
        }
    }

    place_player_after_entry();
    player.iframes = 60;    // brief invuln on room entry
}
