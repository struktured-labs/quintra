#pragma bank 255
// Law Lock generator and product-graph validator. Plain C: also compiled on
// the host (LL_HOST) by the quintra-procgen `law_lock_parity` cargo test
// against tools/crates/quintra-procgen/src/law_lock.rs. Keep every step in
// explicit u8 arithmetic so SDCC and a 32-bit host compiler agree.
//
// Model (Argon review, spec §9): a gate is a doorway pair on one maze edge,
// solid pillars while closed, so a cell is never split in two. Every region
// the gates cut the maze into owns one explicit altar, so from any
// (cell, Law state) the player can flip locally and every node stays
// reachable: no state can softlock, including a suspend/reload.

#include "game/law_lock.h"

u8 ll_size;
u8 ll_nb[LL_CELLS][4];
u8 ll_entry;
u8 ll_role[LL_ROLES];
u8 ll_cache;
u8 ll_order;
u8 ll_mix;
u8 ll_bb;

u8 ll_gate_n;
u8 ll_gate_a[LL_MAX_GATES];
u8 ll_gate_b[LL_MAX_GATES];
u8 ll_gate_dir[LL_MAX_GATES];
u8 ll_gate_open[LL_MAX_GATES];
u8 ll_altar_n;
u8 ll_altar[LL_MAX_ALTARS];
u8 ll_plain_boss;
u8 ll_law_boss;
u8 ll_plain_tour;
u8 ll_law_tour;

// An altar stands at most this many rooms from the gate it serves.
#define LL_ALTAR_REACH 3

#define LL_MODE_PLAIN  0   // the maze without Law gates
#define LL_MODE_FROZEN 1   // gates honoured, altars ignored
#define LL_MODE_LAW    2   // gates honoured, altars flip

static u8 ll_dist[LL_CELLS * 2];   // product BFS: steps + 1, 0 = unseen
static u8 ll_from[LL_CELLS * 2];   // product BFS parent node
static u8 ll_queue[LL_CELLS * 2];
static u8 ll_par[LL_CELLS];
static u8 ll_path[LL_CELLS];
static u8 ll_cand[LL_CELLS];
static u8 ll_comp[LL_CELLS];
static u8 ll_depth[LL_CELLS];
static u8 ll_cand_n;

static u8 ll_portal_peer(u8 cell) {
    // Stage 2+ pairs local rooms 2 and 8 with a reversible rift portal.
    if (ll_bb == 0 || ll_size <= 8) return LL_NONE;
    if (cell == 2) return 8;
    if (cell == 8) return 2;
    return LL_NONE;
}

static u8 ll_gate_at(u8 cell, u8 dir) {
    u8 g;
    for (g = 0; g < ll_gate_n; ++g) {
        if (ll_gate_a[g] == cell && ll_gate_dir[g] == dir) return g;
        if (ll_gate_b[g] == cell && (u8)((ll_gate_dir[g] + 2) & 3) == dir)
            return g;
    }
    return LL_NONE;
}

u8 ll_edge_open(u8 cell, u8 dir, u8 state) LL_BANKED {
    u8 g = ll_gate_at(cell, dir);
    if (g == LL_NONE) return 1;
    return (ll_gate_open[g] == state) ? 1 : 0;
}

u8 ll_is_altar(u8 cell) LL_BANKED {
    u8 i;
    for (i = 0; i < ll_altar_n; ++i)
        if (ll_altar[i] == cell) return 1;
    return 0;
}

static u8 ll_is_role(u8 cell) {
    u8 i;
    for (i = 0; i < LL_ROLES; ++i)
        if (ll_role[i] == cell) return 1;
    return 0;
}


// Gate rooms: never the foyer, services, the deep phase switch or gate
// (Argon: no compound hard lock), stage-1 start 0, or the seeded
// combat-seal rooms 1 and 2.
static u8 ll_gate_cell_ok(u8 cell) {
    if (cell == ll_entry || cell >= (u8)(ll_size - 3) || cell < 3) return 0;
    return (cell == ll_role[5] || cell == ll_role[6]) ? 0 : 1;
}

// Altar rooms: additionally never a mission room, the rift-portal room 8,
// the Reaper's room 15, the cache, or a gate room, so an altar is never
// inside a puzzle or a sealed fight. The quiet witness waypoints 5/11/17/23
// make natural altar courts.
static u8 ll_altar_cell_ok(u8 cell) {
    // The sanctuary (a quiet rest court) may hold the last region's altar.
    if ((!ll_gate_cell_ok(cell) && cell != (u8)(ll_size - 2))
        || ll_is_role(cell) || cell == 8 || cell == 15
        || cell == ll_cache)
        return 0;
    return (ll_gate_at(cell, 0) == LL_NONE && ll_gate_at(cell, 1) == LL_NONE
        && ll_gate_at(cell, 2) == LL_NONE && ll_gate_at(cell, 3) == LL_NONE)
        ? 1 : 0;
}

// Breadth-first search over (cell, state). Returns steps to `goal` in any
// state (a flip costs one step) or LL_NONE; ll_dist keeps every visit.
static u8 ll_bfs(u8 start, u8 state, u8 mode, u8 goal) {
    u8 head = 0, tail = 0, i, found = LL_NONE;
    for (i = 0; i < (u8)(LL_CELLS * 2); ++i) ll_dist[i] = 0;
    ll_dist[(u8)(start * 2 + state)] = 1;
    ll_from[(u8)(start * 2 + state)] = (u8)(start * 2 + state);
    ll_queue[tail++] = (u8)(start * 2 + state);
    while (head < tail) {
        u8 node = ll_queue[head++];
        u8 cell = (u8)(node >> 1), st = (u8)(node & 1), d;
        u8 step = (u8)(ll_dist[node] + 1);
        if (cell == goal && found == LL_NONE) found = (u8)(ll_dist[node] - 1);
        for (d = 0; d < 6; ++d) {
            u8 next, nst = st, idx;
            if (d < 4) {
                next = ll_nb[cell][d];
                if (next == LL_NONE) continue;
                if (mode != LL_MODE_PLAIN && !ll_edge_open(cell, d, st))
                    continue;
            } else if (d == 4) {
                next = ll_portal_peer(cell);
                if (next == LL_NONE) continue;
            } else {
                if (mode != LL_MODE_LAW || !ll_is_altar(cell)) continue;
                next = cell;
                nst = (u8)(st ^ 1);
            }
            idx = (u8)(next * 2 + nst);
            if (ll_dist[idx]) continue;
            ll_dist[idx] = step;
            ll_from[idx] = node;
            ll_queue[tail++] = idx;
        }
    }
    return found;
}

static u8 ll_reached(u8 cell) {
    return (ll_dist[(u8)(cell * 2)] || ll_dist[(u8)(cell * 2 + 1)]) ? 1 : 0;
}

// Candidate gate edges: every maze edge on the entry's BFS tree path to a
// mission room or the sanctuary, so each gate stands on the required tour.
// An edge is named by its far ("child") cell; ll_par holds the near cell.
// Candidates are ordered outward by depth, then by cell number.
static void ll_find_candidates(void) {
    u8 head = 0, tail = 0, i, d, at, depth;
    for (i = 0; i < LL_CELLS; ++i) {
        ll_par[i] = LL_NONE;
        ll_path[i] = 0;          // reused: depth from the entry
        ll_comp[i] = 0;          // reused: on-tour edge flag
    }
    ll_par[ll_entry] = ll_entry;
    ll_queue[tail++] = ll_entry;
    while (head < tail) {
        at = ll_queue[head++];
        for (d = 0; d < 4; ++d) {
            u8 next = ll_nb[at][d];
            if (next == LL_NONE || ll_par[next] != LL_NONE) continue;
            ll_par[next] = at;
            ll_path[next] = (u8)(ll_path[at] + 1);
            ll_queue[tail++] = next;
        }
    }
    for (i = 0; i <= LL_ROLES; ++i) {
        at = (i < LL_ROLES) ? ll_role[i] : (u8)(ll_size - 2);
        if (at >= ll_size || ll_par[at] == LL_NONE) continue;
        while (at != ll_entry) {
            ll_comp[at] = 1;
            at = ll_par[at];
        }
    }
    ll_cand_n = 0;
    for (depth = 1; depth < LL_CELLS; ++depth)
        for (i = 0; i < ll_size; ++i)
            if (ll_comp[i] && ll_path[i] == depth && ll_path[ll_par[i]] >= 2
                && ll_gate_cell_ok(i) && ll_gate_cell_ok(ll_par[i]))
                ll_cand[ll_cand_n++] = i;
}

// Label the region holding `seed` (gates are walls, the portal is not) and
// return its nearest legal altar cell, or LL_NONE.
static u8 ll_label(u8 seed, u8 label) {
    u8 head = 0, tail = 0, d, altar = LL_NONE;
    ll_comp[seed] = label;
    ll_depth[seed] = 0;
    ll_queue[tail++] = seed;
    while (head < tail) {
        u8 at = ll_queue[head++];
        if (altar == LL_NONE && ll_depth[at] <= LL_ALTAR_REACH
            && ll_altar_cell_ok(at)) altar = at;
        for (d = 0; d < 5; ++d) {
            u8 next;
            if (d < 4) {
                next = ll_nb[at][d];
                if (next == LL_NONE || ll_gate_at(at, d) != LL_NONE) continue;
            } else {
                next = ll_portal_peer(at);
                if (next == LL_NONE) continue;
            }
            if (ll_comp[next] != LL_NONE) continue;
            ll_comp[next] = label;
            ll_depth[next] = (u8)(ll_depth[at] + 1);
            ll_queue[tail++] = next;
        }
    }
    return altar;
}

// The director's objective order: Trial, Sigil/Warden (mission_order),
// Waystone, Deep Warden, Deep Switch, Deep Gate, then the sanctuary.
static u8 ll_tour_cell(u8 i) {
    if (i == 0) return ll_role[0];
    if (i == 1) return ll_order ? ll_role[2] : ll_role[1];
    if (i == 2) return ll_order ? ll_role[1] : ll_role[2];
    if (i < LL_ROLES) return ll_role[i];
    return (u8)(ll_size - 2);
}

// Steps for the director-order tour from the entry (WAX), carrying the
// best cost per Law state from one objective to the next.
static u8 ll_tour(u8 mode) {
    u16 cost[2], next_cost[2];
    u8 at = ll_entry, i, s, s2;
    cost[0] = 0;
    cost[1] = 0xFFFF;
    for (i = 0; i <= LL_ROLES; ++i) {
        u8 next = ll_tour_cell(i);
        next_cost[0] = next_cost[1] = 0xFFFF;
        for (s = 0; s < 2; ++s) {
            if (cost[s] == 0xFFFF) continue;
            ll_bfs(at, s, mode, next);
            for (s2 = 0; s2 < 2; ++s2) {
                u8 d = ll_dist[(u8)(next * 2 + s2)];
                if (d && (u16)(cost[s] + d - 1) < next_cost[s2])
                    next_cost[s2] = (u16)(cost[s] + d - 1);
            }
        }
        cost[0] = next_cost[0];
        cost[1] = next_cost[1];
        at = next;
    }
    if (cost[1] < cost[0]) cost[0] = cost[1];
    return (cost[0] > 250) ? LL_NONE : (u8)cost[0];
}

static u8 ll_tour_slack(void) {
    // Argon's full-tour caps: +6 (Stages 2-3), +10 (4-6), +12 (7-9).
    return (ll_bb <= 2) ? 6 : (ll_bb <= 5) ? 10 : 12;
}

static u8 ll_boss_slack(void) {
    // Argon's direct-route caps: +4 room steps (Stages 2-3), +6 (4-6),
    // +7 (7-9), and never more than 1.5x the plain route.
    return (ll_bb <= 2) ? 4 : (ll_bb <= 5) ? 6 : 7;
}

// Label every region the current gates cut the maze into and give each its
// legal altar nearest the gate that bounds it. 0 when a region has none.
static u8 ll_place_altars(void) {
    u8 g, i, label = 0;
    ll_altar_n = 0;
    for (i = 0; i < LL_CELLS; ++i) ll_comp[i] = LL_NONE;
    for (g = 0; g < (u8)(ll_gate_n * 2); ++g) {
        u8 anchor = (g & 1) ? ll_gate_b[g >> 1] : ll_gate_a[g >> 1];
        u8 altar;
        if (ll_comp[anchor] != LL_NONE) continue;
        if (ll_altar_n >= LL_MAX_ALTARS) return 0;
        altar = ll_label(anchor, label++);
        if (altar == LL_NONE) return 0;
        ll_altar[ll_altar_n++] = altar;
    }
    // Any region no gate touches (none in today's mazes) needs one too.
    for (i = 0; i < ll_size; ++i) {
        u8 altar;
        if (ll_comp[i] != LL_NONE) continue;
        if (ll_altar_n >= LL_MAX_ALTARS) return 0;
        altar = ll_label(i, label++);
        if (altar == LL_NONE) return 0;
        ll_altar[ll_altar_n++] = altar;
    }
    return 1;
}

static u8 ll_try(u8 want) {
    u8 g, i;
    u8 sanctuary = (u8)(ll_size - 2);
    ll_gate_n = 0;
    ll_altar_n = 0;
    if (ll_cand_n < want) return 0;
    for (g = 0; g < want; ++g) {
        // Gate g takes a candidate from its share of the outward-ordered
        // list: the seeded one first, then the rest of the share in turn.
        u8 lo = (u8)((u8)(g * ll_cand_n) / want);
        u8 hi = (u8)((u8)((u8)(g + 1) * ll_cand_n) / want);
        u8 span = (u8)(hi - lo), off, t, placed = 0;
        if (hi <= lo) return 0;
        off = (u8)((u8)(ll_mix + (u8)(g * 5)) % span);
        for (t = 0; t < span && !placed; ++t) {
            u8 b = ll_cand[(u8)(lo + (u8)((u8)(off + t) % span))];
            u8 a = ll_par[b], d, j, clash = 0;
            // Two gates never share a room: each side keeps its own altar.
            for (j = 0; j < g; ++j)
                if (ll_gate_a[j] == a || ll_gate_a[j] == b
                    || ll_gate_b[j] == a || ll_gate_b[j] == b) clash = 1;
            if (clash) continue;
            for (d = 0; d < 4; ++d)
                if (ll_nb[a][d] == b) break;
            ll_gate_a[g] = a;
            ll_gate_b[g] = b;
            ll_gate_dir[g] = d;
            // The first gate is closed on arrival (state WAX = 0); the rest
            // alternate, so every further gate asks for one more flip.
            ll_gate_open[g] = (u8)((g & 1) ^ 1);
            ll_gate_n = (u8)(g + 1);
            if (ll_place_altars()) placed = 1;
        }
        if (!placed) return 0;
    }
    // Nontrivial: without a flip some mission room or the sanctuary stays
    // out of reach.
    ll_bfs(ll_entry, 0, LL_MODE_FROZEN, sanctuary);
    for (i = 0, g = 1; i < LL_ROLES; ++i)
        if (!ll_reached(ll_role[i])) g = 0;
    if (g && ll_reached(sanctuary)) return 0;
    // Solvable: every cell (all missions, sanctuary, boss) is reachable from
    // the arrival node. The product graph is undirected, so every node
    // reached can also return: no reachable state is a trap.
    ll_law_boss = ll_bfs(ll_entry, 0, LL_MODE_LAW, sanctuary);
    if (ll_law_boss == LL_NONE) return 0;
    for (i = 0; i < ll_size; ++i)
        if (!ll_reached(i)) return 0;
    if ((u8)(ll_law_boss - ll_plain_boss) > ll_boss_slack()) return 0;
    if ((u16)ll_law_boss * 2u > (u16)ll_plain_boss * 3u) return 0;
    ll_law_tour = ll_tour(LL_MODE_LAW);
    if (ll_law_tour == LL_NONE
        || (u8)(ll_law_tour - ll_plain_tour) > ll_tour_slack()) return 0;
    return 1;
}

void ll_generate(void) LL_BANKED {
    u8 want;
    ll_gate_n = 0;
    ll_altar_n = 0;
    ll_plain_boss = ll_bfs(ll_entry, 0, LL_MODE_PLAIN, (u8)(ll_size - 2));
    ll_law_boss = ll_plain_boss;
    ll_plain_tour = ll_tour(LL_MODE_PLAIN);
    ll_law_tour = ll_plain_tour;
    want = (ll_bb == 0) ? 0 : (ll_bb <= 2) ? 1 : (ll_bb <= 5) ? 2 : 3;
    if (!want || ll_size < 8 || ll_plain_boss == LL_NONE) return;
    ll_find_candidates();
    for (; want; --want)
        if (ll_try(want)) return;
    ll_gate_n = 0;
    ll_altar_n = 0;
    ll_law_boss = ll_plain_boss;
    ll_law_tour = ll_plain_tour;
}

u8 ll_route_altar;

u8 ll_route_first(u8 start, u8 state, u8 goal) LL_BANKED {
    u8 node, prev, d, best = LL_NONE, first;
    ll_route_altar = LL_NONE;
    if (start == goal) return LL_NONE;
    ll_bfs(start, state, LL_MODE_LAW, goal);
    // The nearer of the goal's two state nodes (BFS: smaller ll_dist).
    for (d = 0; d < 2; ++d) {
        node = (u8)(goal * 2 + d);
        if (ll_dist[node]
            && (best == LL_NONE || ll_dist[node] < ll_dist[best])) best = node;
    }
    if (best == LL_NONE) return LL_NONE;
    // Walk back to the start, remembering the earliest flip on the way.
    node = best;
    first = best;
    while (node != (u8)(start * 2 + state)) {
        prev = ll_from[node];
        if ((prev >> 1) == (node >> 1)) ll_route_altar = (u8)(node >> 1);
        first = node;
        node = prev;
    }
    if ((first >> 1) == start) return LL_ROUTE_FLIP;
    for (d = 0; d < 4; ++d)
        if (ll_nb[start][d] == (u8)(first >> 1)) return d;
    return LL_ROUTE_PORTAL;
}
