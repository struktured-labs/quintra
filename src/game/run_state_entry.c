#pragma bank 5

#include "core/types.h"
#include "game/run_state.h"

// Seeded foyer picker, kept off bank 14 so the topology solver still
// holds the 256-byte emergency floor after the start-cell variety work.

#define ENTRY_MIN_BOSS_DIST 7

static u8 entry_cell_at(u8 col, u8 row, u8 size) {
    u8 cell;
    if (col >= DUNGEON_GRID_W || row >= DUNGEON_GRID_H) return 0xFF;
    cell = (u8)(row * DUNGEON_GRID_W
        + ((row & 1) ? (u8)((DUNGEON_GRID_W - 1) - col) : col));
    return (cell < size) ? cell : 0xFF;
}

static u8 entry_grid_kind(u8 cell, u8 size) {
    u8 row = (u8)(cell / DUNGEON_GRID_W);
    u8 offset = (u8)(cell % DUNGEON_GRID_W);
    u8 col = (row & 1) ? (u8)((DUNGEON_GRID_W - 1) - offset) : offset;
    u8 degree = 0;
    if (row > 0 && entry_cell_at(col, (u8)(row - 1), size) != 0xFF) degree++;
    if (entry_cell_at((u8)(col + 1), row, size) != 0xFF) degree++;
    if (entry_cell_at(col, (u8)(row + 1), size) != 0xFF) degree++;
    if (col > 0 && entry_cell_at((u8)(col - 1), row, size) != 0xFF) degree++;
    if (degree <= 2) return 0;
    if (degree == 3) return 1;
    return 2;
}

static u8 entry_maze_degree(u8 cell) {
    u8 dir, degree = 0;
    for (dir = DIR_N; dir <= DIR_W; ++dir)
        if (run_state_dungeon_cell_neighbor(cell, dir) != 0xFF) degree++;
    return degree;
}

static u8 entry_candidate_ok(u8 cell, u8 size, u8 dist) {
    if (cell >= (u8)(size - 3)) return 0;
    if (dist == 0xFF || dist < ENTRY_MIN_BOSS_DIST) return 0;
    /* Junctions eat too much spawn apron for a foyer pack. */
    if (entry_maze_degree(cell) > 2) return 0;
    /* Turn courts cap at a pair of bodies; they cannot be the stage foyer. */
    if (cell == 5 || cell == 11 || cell == 17 || cell == 23) return 0;
    return 1;
}

static u16 entry_mix(void) {
    u16 mix = (u16)((u8)run_state.run_seed
        | ((u16)(u8)(run_state.run_seed >> 8) << 8));
    mix ^= (u16)((u8)(run_state.run_seed >> 16)
        | ((u16)(u8)(run_state.run_seed >> 24) << 8));
    mix ^= (u16)((u16)run_state.bosses_beaten * 251u);
    return mix;
}

/* The foyer is a pure function of (run_seed, bosses_beaten), but the solver
 * walks the folded maze through ~100 banked neighbour probes. Uncached, each
 * call cost 15-35 frames and room entry makes about five of them, stalling
 * every dungeon doorway by a second or more. Memoize per seed and stage.
 * The tag stores bosses_beaten + 1 so zeroed WRAM reads as "empty" without
 * an initializer in the home bank. */
static u32 entry_cache_seed;
static u8 entry_cache_tag;
static u8 entry_cache_cell;

u8 run_state_dungeon_entry_cell(void) BANKED {
    /* WRAM scratch: a 30-cell BFS from the boss would overflow the stack. */
    static u8 dist[MAX_DUNGEON_CELLS];
    static u8 queue[MAX_DUNGEON_CELLS];
    static u8 cand_kind[MAX_DUNGEON_CELLS];
    u8 size, boss, limit;
    u8 head = 0, tail = 0, i, dir, cell;
    u8 result = 0;
    u16 mix;
    u8 rot;

    if (entry_cache_tag == (u8)(run_state.bosses_beaten + 1)
        && entry_cache_seed == run_state.run_seed)
        return entry_cache_cell;

    size = run_state_dungeon_size();
    if (size >= 4) {
        boss = (u8)(size - 1);
        limit = (u8)(size - 3);
        for (i = 0; i < MAX_DUNGEON_CELLS; ++i) dist[i] = 0xFF;
        dist[boss] = 0;
        queue[tail++] = boss;
        while (head < tail) {
            u8 at = queue[head++];
            for (dir = DIR_N; dir <= DIR_W; ++dir) {
                u8 next = run_state_dungeon_cell_neighbor(at, dir);
                if (next == 0xFF || dist[next] != 0xFF) continue;
                dist[next] = (u8)(dist[at] + 1);
                queue[tail++] = next;
            }
        }
        /* One candidate/kind pass instead of re-probing the maze per kind. */
        for (cell = 0; cell < limit; ++cell)
            cand_kind[cell] = entry_candidate_ok(cell, size, dist[cell])
                ? entry_grid_kind(cell, size) : 0xFF;

        mix = entry_mix();
        rot = (u8)(mix % 3);
        for (i = 0; i < 3; ++i) {
            u8 kind = (u8)((u8)(rot + i) % 3);
            u8 count = 0;
            for (cell = 0; cell < limit; ++cell)
                if (cand_kind[cell] == kind) count++;
            if (!count) continue;
            {
                u8 index = (u8)((mix >> 3) % count);
                u8 seen = 0;
                for (cell = 0; cell < limit; ++cell) {
                    if (cand_kind[cell] != kind) continue;
                    if (seen == index) { result = cell; break; }
                    seen++;
                }
            }
            break;
        }
    }
    entry_cache_seed = run_state.run_seed;
    entry_cache_tag = (u8)(run_state.bosses_beaten + 1);
    entry_cache_cell = result;
    return result;
}

void run_state_place_at_entry(void) BANKED {
    u8 entry = run_state_dungeon_entry_cell();
    run_state.room_counter = (u8)(run_state_stage_start(run_state.bosses_beaten)
        + entry);
    run_state.dungeon_seen = 0;
    run_state.dungeon_seen_hi = 0;
    run_state.dungeon_seen_xhi = 0;
    run_state.dungeon_seen_xxhi = 0;
    run_state.dungeon_visited = 0;
    run_state.dungeon_visited_hi = 0;
    run_state.dungeon_visited_xhi = 0;
    run_state.dungeon_visited_xxhi = 0;
    run_state_mark_visited();
}

static void queue_next_dungeon_bit(u8 cell) {
    if (cell < 8) run_state.next_dungeon_reveal |= (u8)(1u << cell);
    else if (cell < 16)
        run_state.next_dungeon_reveal_hi |= (u8)(1u << (cell - 8));
    else if (cell < 24)
        run_state.next_dungeon_reveal_xhi |= (u8)(1u << (cell - 16));
    else if (cell < MAX_DUNGEON_CELLS)
        run_state.next_dungeon_reveal_xxhi |= (u8)(1u << (cell - 24));
}

void run_state_queue_next_dungeon_prefix(u8 count) BANKED {
    static u8 seen[MAX_DUNGEON_CELLS];
    static u8 queue[MAX_DUNGEON_CELLS];
    u8 entry;
    u8 head = 0, tail = 0, marked = 0, i, dir;
    if (!count) return;
    entry = run_state_dungeon_entry_cell();
    for (i = 0; i < MAX_DUNGEON_CELLS; ++i) seen[i] = 0;
    seen[entry] = 1;
    queue[tail++] = entry;
    while (head < tail && marked < count) {
        u8 cell = queue[head++];
        queue_next_dungeon_bit(cell);
        marked++;
        for (dir = DIR_N; dir <= DIR_W; ++dir) {
            u8 next = run_state_dungeon_cell_neighbor(cell, dir);
            if (next == 0xFF || seen[next]) continue;
            seen[next] = 1;
            queue[tail++] = next;
        }
    }
}
