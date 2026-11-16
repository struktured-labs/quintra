#pragma bank 18
// Pinned: autobank first-fit left bank 5 under the 256-byte layout floor.
// Law Lock cartridge glue: feeds the seeded maze to the plain-C generator
// (law_lock_gen.c), paints the gated doorways and the altar of the current
// room, and answers the Compass/director's product-graph route questions.
// No SRAM: gates and altars are a pure function of (run seed, stage), and
// the WAX/WANE state is the existing Dungeon Law bit.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "game/law_lock.h"
#include "game/mission_graph.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

u8 law_lock_gate_dirs;
u8 law_lock_closed_dirs;
u8 law_lock_waypoint;
u8 law_lock_east;
u8 law_lock_south;
u8 law_lock_wane_dirs;   // gated doorways that open in WANE
u8 law_lock_has_altar;
u8 law_lock_altar_x;
u8 law_lock_altar_y;

static u32 law_lock_seed;
static u8 law_lock_tag;   // bosses_beaten + 1; 0 = nothing cached

void law_lock_ensure(void) BANKED {
    u8 c, d, mix;
    if (law_lock_tag == (u8)(run_state.bosses_beaten + 1)
        && law_lock_seed == run_state.run_seed) return;
    mission_graph_ensure();
    ll_size = run_state_dungeon_size();
    if (ll_size > LL_CELLS) ll_size = LL_CELLS;
    for (c = 0; c < ll_size; ++c)
        for (d = 0; d < 4; ++d)
            ll_nb[c][d] = run_state_dungeon_cell_neighbor(c, d);
    ll_entry = run_state_dungeon_entry_cell();
    ll_role[0] = run_state.mission_trial_cell;
    ll_role[1] = run_state.mission_sigil_cell;
    ll_role[2] = run_state.mission_warden_cell;
    ll_role[3] = run_state.mission_waystone_cell;
    ll_role[4] = run_state.mission_deep_warden_cell;
    ll_role[5] = run_state.mission_deep_switch_cell;
    ll_role[6] = run_state.mission_deep_gate_cell;
    ll_order = (u8)(run_state.mission_order & 1);
    ll_cache = run_state_dungeon_cache_cell();
    mix = (u8)run_state.run_seed;
    mix ^= (u8)(run_state.run_seed >> 8);
    mix ^= (u8)(run_state.run_seed >> 16);
    mix ^= (u8)(run_state.run_seed >> 24);
    ll_mix = mix;
    ll_bb = run_state.bosses_beaten;
    ll_generate();
    law_lock_seed = run_state.run_seed;
    law_lock_tag = (u8)(run_state.bosses_beaten + 1);
}

u8 law_lock_active(void) BANKED {
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter))
        return 0;
    law_lock_ensure();
    return ll_gate_n ? 1 : 0;
}

u8 law_lock_cell_is_altar(u8 cell) BANKED {
    return (law_lock_active() && ll_is_altar(cell)) ? 1 : 0;
}

static u8 law_state(void) {
    return (run_state.dungeon_law & DUNGEON_LAW_STATE_BIT) ? 1 : 0;
}

// Cool (Crystal) opens in WAX, warm (Crack) opens in WANE.
static u8 law_state_attr(u8 state) {
    return state ? BGPAL_CRACK : BGPAL_CRYSTAL;
}

static void law_lock_set(u8 x, u8 y, u8 tile, u8 attr, u8 live) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
    if (!live) return;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

static u8 door_x(u8 dir, u8 half) {
    if (dir == DIR_E) return law_lock_east;
    if (dir == DIR_W) return 0;
    return (u8)(9 + half);
}

static u8 door_y(u8 dir, u8 half) {
    if (dir == DIR_N) return 0;
    if (dir == DIR_S) return law_lock_south;
    return (u8)(8 + half);
}

void law_lock_apply_room(u8 live) BANKED {
    u8 cell, state, d, half, g;
    law_lock_gate_dirs = 0;
    law_lock_closed_dirs = 0;
    law_lock_wane_dirs = 0;
    law_lock_has_altar = 0;
    if (!law_lock_active()) return;
    cell = run_state_dungeon_local();
    state = law_state();
    law_lock_east = (u8)((room_world_width >> 3) - 1);
    law_lock_south = (u8)((room_world_height >> 3) - 1);
    // Gated doorway: a solid two-tile pillar pair while closed (tinted by
    // the state that opens it), an ordinary door while open. Never a
    // mid-room divider, so the room itself is always one connected court.
    for (g = 0; g < ll_gate_n; ++g) {
        if (ll_gate_a[g] == cell) d = ll_gate_dir[g];
        else if (ll_gate_b[g] == cell) d = (u8)((ll_gate_dir[g] + 2) & 3);
        else continue;
        law_lock_gate_dirs |= (u8)(1 << d);
        if (ll_gate_open[g]) law_lock_wane_dirs |= (u8)(1 << d);
        if (ll_gate_open[g] != state) law_lock_closed_dirs |= (u8)(1 << d);
        for (half = 0; half < 2; ++half) {
            u8 closed = (law_lock_closed_dirs >> d) & 1;
            law_lock_set(door_x(d, half), door_y(d, half),
                closed ? BGT_PILLAR : BGT_DOOR,
                closed ? law_state_attr(ll_gate_open[g]) : BGPAL_DOOR, live);
        }
    }
    if (!ll_is_altar(cell)) return;
    // The altar stands three tiles inside the room's first real doorway
    // (W, N, E, S), on a carved body-wide apron so it is always reachable.
    for (d = 0; d < 4; ++d) {
        static const u8 pref[4] = { DIR_W, DIR_N, DIR_E, DIR_S };
        u8 dir = pref[d], step;
        if (run_state_dungeon_cell_neighbor(cell, dir) == 0xFF) continue;
        for (step = 1; step <= 4; ++step)
            for (half = 0; half < 2; ++half) {
                u8 x = door_x(dir, half), y = door_y(dir, half);
                if (dir == DIR_W) x = step;
                else if (dir == DIR_E) x = (u8)(law_lock_east - step);
                else if (dir == DIR_N) y = step;
                else y = (u8)(law_lock_south - step);
                if (step == 3 && half == 0) {
                    law_lock_has_altar = 1;
                    law_lock_altar_x = x;
                    law_lock_altar_y = y;
                    law_lock_set(x, y, BGT_SWITCH, law_state_attr(state), live);
                } else if (!live) {
                    law_lock_set(x, y, BGT_FLOOR, BGPAL_FLOOR, 0);
                }
            }
        break;
    }
}

u8 law_lock_attr_at(u8 x, u8 y) BANKED {
    if (law_lock_has_altar && x == law_lock_altar_x && y == law_lock_altar_y)
        return law_state_attr(law_state());
    // Each gated doorway wears the colour of the state that opens it (two
    // gates in one room may open in different states).
    {
        u8 d = (x == 0) ? DIR_W : (y == 0) ? DIR_N
            : (x == law_lock_east) ? DIR_E : (y == law_lock_south) ? DIR_S
            : 0xFF;
        if (d != 0xFF && ((law_lock_gate_dirs >> d) & 1))
            return law_state_attr((law_lock_wane_dirs >> d) & 1);
    }
    return 0xFF;
}

static u8 law_map_attr(u8 state) {
    return state ? BGPAL_CRACK : BGPAL_DOOR;
}

static void law_map_put(u8 x, u8 y, u8 tile, u8 attr) {
    VBK_REG = 0; set_bkg_tiles(x, y, 1, 1, &tile);
    VBK_REG = 1; set_bkg_tiles(x, y, 1, 1, &attr);
    VBK_REG = 0;
}

u8 law_lock_edge_attr(u8 a, u8 b) BANKED {
    u8 g;
    if (!law_lock_active()) return LL_NONE;
    for (g = 0; g < ll_gate_n; ++g)
        if ((ll_gate_a[g] == a && ll_gate_b[g] == b)
            || (ll_gate_a[g] == b && ll_gate_b[g] == a))
            return law_map_attr(ll_gate_open[g]);
    return LL_NONE;
}

void law_lock_map_altar(u8 x, u8 y, u8 cell) BANKED {
    u8 attr;
    if (!ll_is_altar(cell)) return;
    attr = law_map_attr(law_state());
    law_map_put(x, (u8)(y + 1), BGT_MAP_BIG_ROOM + 2, attr);
    law_map_put((u8)(x + 1), (u8)(y + 1), BGT_MAP_BIG_ROOM + 3, attr);
}

void law_lock_map_legend(void) BANKED {
    u8 attr = law_map_attr(law_state());
    law_map_put(16, 16, BGT_AREA_L, attr);
    law_map_put(17, 16, BGT_AREA_A, attr);
    law_map_put(18, 16, BGT_AREA_W, attr);
}

u8 law_lock_route(u8 start, u8 target) BANKED {
    u8 first;
    law_lock_waypoint = target;
    first = ll_route_first(start, law_state(), target);
    if (ll_route_altar != LL_NONE) law_lock_waypoint = ll_route_altar;
    return (first < 4) ? first : DIR_NONE;
}
