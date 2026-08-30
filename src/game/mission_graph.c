#pragma bank 8

#include <gb/gb.h>

#include "core/types.h"
#include "game/mission_graph.h"
#include "game/run_state.h"

#define MISSION_ROLE_COUNT 7

// WRAM scratch avoids a 90-byte automatic frame on the Game Boy stack. It is
// touched only during room entry or the SELECT-map's cold route calculation.
static u8 mission_seen[MAX_DUNGEON_CELLS];
static u8 mission_queue[MAX_DUNGEON_CELLS];
static u8 mission_eligible[MAX_DUNGEON_CELLS];
static u8 mission_cache_reserve;

static u8 mission_mix(void) {
    u8 mix = (u8)run_state.run_seed;
    mix ^= (u8)(run_state.run_seed >> 8);
    mix ^= (u8)(run_state.run_seed >> 16);
    mix ^= (u8)(run_state.run_seed >> 24);
    return (u8)(mix + run_state.bosses_beaten * 41);
}

static u8 mission_landmark_reserved(u8 cell) {
    return (cell == 0 || cell == 2 || cell == 5 || cell == 8 || cell == 11
        || cell == 15 || cell == 17 || cell == 23) ? 1 : 0;
}

static u8 mission_seed_cache_cell(void) {
    u8 cell = (u8)(run_state_dungeon_size() - 4);
    while (cell > 0) {
        if (!mission_landmark_reserved(cell)) {
            u8 dir, degree = 0;
            for (dir = DIR_N; dir <= DIR_W; ++dir)
                if (run_state_dungeon_cell_neighbor(cell, dir) != 0xFF)
                    degree++;
            if (degree == 1) return cell;
        }
        cell--;
    }
    return 0xFF;
}

static u8 mission_reserved(u8 cell, u8 limit) {
    if (cell == 0 || cell >= limit) return 1;
    // Keep nonlinear wells, quiet witnesses, and the optional third Warden
    // available as stable spatial punctuation around the generated quest.
    return (mission_landmark_reserved(cell)
        || cell == mission_cache_reserve) ? 1 : 0;
}

// Breadth-first discovery orders the actual seed-folded maze from its entry.
// Rotating direction priority per cell makes equally deep arms seed-specific
// while retaining a readable outward escalation.
static u8 mission_discover(void) {
    u8 size = run_state_dungeon_size();
    u8 limit = (u8)(size - 3);
    u8 head = 0, tail = 0, count = 0, i;
    u8 mix = mission_mix();
    mission_cache_reserve = mission_seed_cache_cell();
    for (i = 0; i < MAX_DUNGEON_CELLS; ++i) mission_seen[i] = 0;
    mission_seen[0] = 1;
    mission_queue[tail++] = 0;
    while (head < tail) {
        u8 cell = mission_queue[head++];
        u8 turn = (u8)((mix + cell * 3) & 3);
        u8 step;
        if (!mission_reserved(cell, limit))
            mission_eligible[count++] = cell;
        for (step = 0; step < 4; ++step) {
            u8 dir = (u8)((turn + step) & 3);
            u8 next = run_state_dungeon_cell_neighbor(cell, dir);
            if (next == 0xFF || next >= limit || mission_seen[next]) continue;
            mission_seen[next] = 1;
            mission_queue[tail++] = next;
        }
    }
    return count;
}

static void mission_assign(const u8 *role) {
    run_state.mission_trial_cell = role[0];
    if (run_state.mission_order & 1) {
        run_state.mission_warden_cell = role[1];
        run_state.mission_sigil_cell = role[2];
    } else {
        run_state.mission_sigil_cell = role[1];
        run_state.mission_warden_cell = role[2];
    }
    run_state.mission_waystone_cell = role[3];
    run_state.mission_deep_warden_cell = role[4];
    run_state.mission_deep_switch_cell = role[5];
    run_state.mission_deep_gate_cell = role[6];
}

static u8 mission_sequence_cell(u8 i) {
    if (i == 0) return run_state.mission_trial_cell;
    if (i == 1) return (run_state.mission_order & 1)
        ? run_state.mission_warden_cell : run_state.mission_sigil_cell;
    if (i == 2) return (run_state.mission_order & 1)
        ? run_state.mission_sigil_cell : run_state.mission_warden_cell;
    if (i == 3) return run_state.mission_waystone_cell;
    if (i == 4) return run_state.mission_deep_warden_cell;
    if (i == 5) return run_state.mission_deep_switch_cell;
    return run_state.mission_deep_gate_cell;
}

u8 mission_graph_valid(void) BANKED {
    u8 count, role, i, j, prior = 0;
    if (run_state.mission_ready != MISSION_GRAPH_READY) return 0;
    count = mission_discover();
    if (count < MISSION_ROLE_COUNT) return 0;
    for (i = 0; i < MISSION_ROLE_COUNT; ++i) {
        u8 pos = 0xFF;
        role = mission_sequence_cell(i);
        for (j = 0; j < count; ++j)
            if (mission_eligible[j] == role) { pos = j; break; }
        if (pos == 0xFF || (i && pos <= prior)) return 0;
        prior = pos;
        for (j = 0; j < i; ++j)
            if (mission_sequence_cell(j) == role) return 0;
    }
    return 1;
}

void mission_graph_ensure(void) BANKED {
    u8 count, i;
    u8 role[MISSION_ROLE_COUNT];
    if (run_state.mission_ready == MISSION_GRAPH_READY) return;
    count = mission_discover();
    run_state.mission_order = mission_mix() & 1;
    if (count >= MISSION_ROLE_COUNT) {
        // Span the available outward traversal rather than clustering seven
        // objectives in the foyer. The small rounded division is entry-time
        // only and gives every stage a full early/middle/deep quest rhythm.
        for (i = 0; i < MISSION_ROLE_COUNT; ++i) {
            u8 pick = (u8)((i * (count - 1) + 3) / 6);
            role[i] = mission_eligible[pick];
        }
    } else {
        // Defensive old-save fallback; current 20..30-cell footprints always
        // expose at least eleven legal mission nodes.
        static const u8 safe[MISSION_ROLE_COUNT] = { 1,3,4,6,7,9,10 };
        for (i = 0; i < MISSION_ROLE_COUNT; ++i) role[i] = safe[i];
    }
    mission_assign(role);
    run_state.mission_ready = MISSION_GRAPH_READY;
    if (!mission_graph_valid()) {
        // The discovery list itself is necessarily valid and ordered. This
        // fallback makes a malformed future topology fail playable, not soft.
        count = mission_discover();
        for (i = 0; i < MISSION_ROLE_COUNT; ++i)
            role[i] = mission_eligible[i];
        mission_assign(role);
    }
}

u8 mission_graph_cell_is_role(u8 cell) BANKED {
    mission_graph_ensure();
    return (cell == run_state.mission_trial_cell
        || cell == run_state.mission_sigil_cell
        || cell == run_state.mission_warden_cell
        || cell == run_state.mission_waystone_cell
        || cell == run_state.mission_deep_warden_cell
        || cell == run_state.mission_deep_switch_cell
        || cell == run_state.mission_deep_gate_cell) ? 1 : 0;
}

u8 run_state_is_miniboss(void) BANKED {
    u8 local;
    if (run_state.world_mode || run_state_is_boss_room()) return 0;
    mission_graph_ensure();
    local = run_state_dungeon_local();
    return (local == run_state.mission_warden_cell
        || local == run_state.mission_deep_warden_cell) ? 1 : 0;
}

u8 run_state_dungeon_cache_cell(void) BANKED {
    u8 size = run_state_dungeon_size();
    u8 cell = (u8)(size - 4);
    mission_graph_ensure();
    while (cell > 0) {
        if (cell != 2 && cell != 5 && cell != 8 && cell != 11
            && cell != 15 && cell != 17 && cell != 23
            && !mission_graph_cell_is_role(cell)) {
            u8 dir;
            u8 degree = 0;
            for (dir = DIR_N; dir <= DIR_W; ++dir)
                if (run_state_dungeon_cell_neighbor(cell, dir) != 0xFF)
                    degree++;
            if (degree == 1) return cell;
        }
        cell--;
    }
    for (cell = 1; cell < (u8)(size - 3); ++cell)
        if (!mission_graph_cell_is_role(cell)) return cell;
    return 1;
}
