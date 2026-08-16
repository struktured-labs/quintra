#pragma bank 8

#include <gb/gb.h>

#include "core/types.h"
#include "game/run_state.h"

static const u8 regional_return_screen[3] = { 0, 7, 13 };
static const u8 regional_gate_screen[3] = { 6, 11, 12 };

static u8 current_region(void) {
    u8 cleared = run_state.bosses_beaten;
    if (!cleared) return 0;
    cleared--;
    if (cleared >= 6) return 2;
    if (cleared >= 3) return 1;
    return 0;
}

static u8 current_region_step(void) {
    u8 cleared = run_state.bosses_beaten;
    if (!cleared) return 0;
    cleared--;
    while (cleared >= DUNGEONS_PER_REGION)
        cleared = (u8)(cleared - DUNGEONS_PER_REGION);
    return cleared;
}

u8 run_state_riftwild_gate_screen(void) BANKED {
    return regional_gate_screen[current_region_step()];
}

u8 run_state_riftwild_gate_active(u8 screen) BANKED {
    return ((screen & 15) == run_state_riftwild_gate_screen()) ? 1 : 0;
}

void run_state_begin_world(void) BANKED {
    u8 region = current_region();
    u8 step = current_region_step();
    // A region's geography is a run fixture. Returning from its second or
    // third dungeon preserves explored paths and claimed landmarks; only a
    // genuine three-dungeon boundary generates a fresh expedition map.
    if (!(run_state.riftwild_flags & RIFT_REGION_READY_BIT)
        || run_state.riftwild_region != region) {
        run_state.riftwild_region = region;
        run_state.riftwild_flags = RIFT_REGION_READY_BIT;
        run_state.world_seen = 0;
    }
    run_state.world_mode = 1;
    run_state.world_screen = regional_return_screen[step];
    run_state.world_return_screen = 0;
    run_state.world_seen |= (u16)(1u << run_state.world_screen);
    run_state.mission_ready = 0;
}

void run_state_begin_dungeon(void) BANKED {
    run_state.world_mode = 0;
    run_state.world_return_screen = TOWN_ARRIVAL;
    // Town chart knowledge intentionally survives the doorway. The prior
    // chartwright wrote directly to dungeon_seen here, so its visible
    // blessing was silently erased during the transition.
    run_state.dungeon_seen = run_state.next_dungeon_reveal;
    run_state.dungeon_seen_hi = run_state.next_dungeon_reveal_hi;
    run_state.dungeon_seen_xhi = run_state.next_dungeon_reveal_xhi;
    run_state.dungeon_seen_xxhi = run_state.next_dungeon_reveal_xxhi;
    run_state.next_dungeon_reveal = 0;
    run_state.next_dungeon_reveal_hi = 0;
    run_state.next_dungeon_reveal_xhi = 0;
    run_state.next_dungeon_reveal_xxhi = 0;
    run_state.dungeon_puzzles = 0;
    run_state.dungeon_phase = 0;
    run_state.dungeon_law = 0;
    run_state.mission_ready = 0;
    run_state_ensure_dungeon_law();
}
