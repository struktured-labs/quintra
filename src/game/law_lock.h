#ifndef QUINTRA_GAME_LAW_LOCK_H
#define QUINTRA_GAME_LAW_LOCK_H

// Law Lock: the Dungeon Law's WAX/WANE state gates 1-3 doorways on the
// required entry->sanctuary route (Stage 2+). Spec:
// docs/superpowers/specs/2026-11-15-puzzle-variety-and-dungeon-wide-puzzles.md
// §4.1 and §9 (Argon review).
//
// law_lock_gen.c is plain C with no GBDK dependency: the cargo test
// `law_lock_parity` compiles it on the host (LL_HOST) and compares it with
// tools/crates/quintra-procgen/src/law_lock.rs for every stage over many
// seeds. law_lock.c is the cartridge glue (topology input, doorway pillars,
// altar, Compass routing).

#include "core/types.h"

#ifdef LL_HOST
#define LL_BANKED
#else
#include <gb/gb.h>
#define LL_BANKED BANKED
#endif

#define LL_CELLS      30
#define LL_MAX_GATES   3
#define LL_MAX_ALTARS  (LL_MAX_GATES + 1)
#define LL_ROLES       7
#define LL_NONE     0xFF

// Generator input (filled by the caller).
extern u8 ll_size;
extern u8 ll_nb[LL_CELLS][4];      // DIR_N/E/S/W neighbour or LL_NONE
extern u8 ll_entry;
extern u8 ll_role[LL_ROLES];       // trial, sigil, warden, waystone,
                                   // deep warden, deep switch, deep gate
extern u8 ll_cache;
extern u8 ll_order;                // mission_order bit 0 (Warden first)
extern u8 ll_mix;                  // xor of the run-seed bytes
extern u8 ll_bb;                   // bosses beaten (stage index)

// Generator output.
extern u8 ll_gate_n;
extern u8 ll_gate_a[LL_MAX_GATES];     // nearer the entry
extern u8 ll_gate_b[LL_MAX_GATES];
extern u8 ll_gate_dir[LL_MAX_GATES];   // direction a -> b
extern u8 ll_gate_open[LL_MAX_GATES];  // Law state (0 WAX, 1 WANE) that opens
extern u8 ll_altar_n;
extern u8 ll_altar[LL_MAX_ALTARS];
extern u8 ll_plain_boss;               // plain maze steps entry -> sanctuary
extern u8 ll_law_boss;                 // product-graph steps (a flip costs 1)
extern u8 ll_plain_tour;               // director-order mission tour, plain
extern u8 ll_law_tour;                 // the same tour under the Law Lock

void ll_generate(void) LL_BANKED;
// Shortest product-graph route from (start, state) to goal in any state:
// the first doorway (DIR_N..DIR_W), LL_ROUTE_FLIP when the first move is
// this room's altar, LL_ROUTE_PORTAL for the rift portal, or LL_NONE.
// ll_route_altar is the first altar the route flips at (LL_NONE if none).
#define LL_ROUTE_FLIP   4
#define LL_ROUTE_PORTAL 5
extern u8 ll_route_altar;
u8 ll_route_first(u8 start, u8 state, u8 goal) LL_BANKED;
// Is the edge (cell, dir) passable in Law state `state`? (Portal excluded.)
u8 ll_edge_open(u8 cell, u8 dir, u8 state) LL_BANKED;
u8 ll_is_altar(u8 cell) LL_BANKED;

#ifndef LL_HOST
// Cartridge runtime (law_lock.c).
extern u8 law_lock_gate_dirs;   // current room: doorways that carry a gate
extern u8 law_lock_closed_dirs; // current room: gates closed right now
extern u8 law_lock_has_altar;   // current room holds a Law Lock altar
extern u8 law_lock_altar_x;
extern u8 law_lock_altar_y;
// Gate pillars wear the colour of the state that opens them; the altar wears
// the current state's colour. 0xFF = no override.
#define LAW_LOCK_ATTR_OVERRIDE(x, y, tile) \
    ((((tile) == BGT_PILLAR && law_lock_gate_dirs) \
        || ((tile) == BGT_SWITCH && law_lock_has_altar)) \
        ? law_lock_attr_at((x), (y)) : 0xFF)
void law_lock_ensure(void) BANKED;
u8 law_lock_cache_hit(void) LL_BANKED;
u8 law_lock_active(void) BANKED;
u8 law_lock_cell_is_altar(u8 cell) BANKED;
// Paint (or repaint live) the current room's gated doorways.
void law_lock_apply_room(u8 live) BANKED;
// BG palette for a gate pillar at (x, y), 0xFF if not a gate tile.
u8 law_lock_attr_at(u8 x, u8 y) BANKED;
// Compass (cold, kept out of the map's bank): cyan = opens in WAX, warm =
// opens in WANE. Corridor (a, b) palette or LL_NONE when it has no gate;
// a charted altar node's lower half in the active colour; the LAW legend.
u8 law_lock_edge_attr(u8 a, u8 b) BANKED;
void law_lock_map_altar(u8 x, u8 y, u8 cell) BANKED;
void law_lock_map_legend(void) BANKED;
// Product-graph route from `start` toward `target` in the current state.
// Returns the first doorway or DIR_NONE; law_lock_waypoint is the altar the
// route must flip at first (or `target` when no flip is needed).
u8 law_lock_route(u8 start, u8 target) BANKED;
extern u8 law_lock_waypoint;
#endif

#endif
