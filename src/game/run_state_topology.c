#pragma bank 14

#include "core/types.h"
#include "game/run_state.h"

// Eight seed-selected "folds" replace the old identical snake in every
// dungeon. Keeping this cold topology solver out of fixed ROM also preserves
// headroom for interrupt-safe gameplay helpers.
static const u8 dungeon_fold_cols[32] = {
    2, 0, 5, 0,
    0, 5, 5, 0,
    0, 0, 5, 0,
    5, 5, 5, 0,
    2, 5, 5, 0,
    0, 5, 4, 0,
    0, 4, 5, 0,
    0, 1, 5, 0
};

void run_state_ensure_dungeon_law(void) BANKED {
    u8 mix;
    if (run_state.dungeon_law & DUNGEON_LAW_READY_BIT) return;
    mix = (u8)run_state.run_seed;
    mix ^= (u8)(run_state.run_seed >> 8);
    mix ^= (u8)(run_state.run_seed >> 16);
    mix ^= (u8)(run_state.run_seed >> 24);
    mix = (u8)(mix + run_state.bosses_beaten * 29);
    run_state.dungeon_law = (u8)(DUNGEON_LAW_READY_BIT + (mix % 3));
}

static u8 dungeon_fold_variant(void) {
    u8 fold = (u8)run_state.run_seed;
    fold ^= (u8)(run_state.run_seed >> 8);
    fold ^= (u8)(run_state.run_seed >> 16);
    fold ^= (u8)(run_state.run_seed >> 24);
    fold ^= (u8)(run_state.bosses_beaten * 3);
    return (u8)(fold & 7);
}

static u8 dungeon_fold_col(u8 upper_row) {
    u8 lower_first = (u8)((upper_row + 1) * DUNGEON_GRID_W);
    u8 lower_count;
    u8 service_first = (u8)(run_state_dungeon_size() - 3);
    u8 col;
    if (lower_first >= run_state_dungeon_size()) return 0xFF;
    lower_count = (u8)(run_state_dungeon_size() - lower_first);
    if (lower_count > DUNGEON_GRID_W) lower_count = DUNGEON_GRID_W;
    if (lower_first < service_first
        && lower_count > (u8)(service_first - lower_first))
        lower_count = (u8)(service_first - lower_first);
    col = dungeon_fold_cols[(u8)((dungeon_fold_variant() << 2) + upper_row)];
    if ((upper_row + 1) & 1) {
        u8 min_col = (u8)(DUNGEON_GRID_W - lower_count);
        if (col < min_col) col = min_col;
    } else if (col >= lower_count) col = (u8)(lower_count - 1);
    return col;
}

u8 run_state_dungeon_cell_neighbor(u8 local, u8 dir) BANKED {
    u8 row, offset, col, old_row, next;
    if (local >= run_state_dungeon_size()) return 0xFF;
    row = (u8)(local / DUNGEON_GRID_W);
    offset = (u8)(local % DUNGEON_GRID_W);
    col = (row & 1) ? (u8)((DUNGEON_GRID_W - 1) - offset) : offset;
    old_row = row;
    if (dir == DIR_N) {
        if (row == 0) return 0xFF;
        row--;
    } else if (dir == DIR_E) {
        if (col == DUNGEON_GRID_W - 1) return 0xFF;
        col++;
    } else if (dir == DIR_S) {
        if (row == DUNGEON_GRID_H - 1) return 0xFF;
        row++;
    } else if (dir == DIR_W) {
        if (col == 0) return 0xFF;
        col--;
    } else return 0xFF;
    next = (u8)(row * DUNGEON_GRID_W
        + ((row & 1) ? ((DUNGEON_GRID_W - 1) - col) : col));
    if (next >= run_state_dungeon_size()) return 0xFF;
    if (dir == DIR_N || dir == DIR_S) {
        u8 upper_row = (dir == DIR_N) ? row : old_row;
        if (col != dungeon_fold_col(upper_row)
            && !(upper_row == 0 && col == 1)) return 0xFF;
    }
    return next;
}

u8 run_state_dungeon_cells_connected(u8 a, u8 b) BANKED {
    u8 dir;
    if (a >= run_state_dungeon_size() || b >= run_state_dungeon_size())
        return 0;
    for (dir = DIR_N; dir <= DIR_W; ++dir)
        if (run_state_dungeon_cell_neighbor(a, dir) == b) return 1;
    return 0;
}

u8 run_state_dungeon_neighbor(u8 dir) BANKED {
    u8 next = run_state_dungeon_cell_neighbor(run_state_dungeon_local(), dir);
    return (next == 0xFF) ? 0xFF
        : (u8)(run_state_stage_start(run_state.bosses_beaten) + next);
}

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

u8 run_state_dungeon_entry_cell(void) BANKED {
    /* WRAM scratch: a 30-cell BFS from the boss would overflow the stack. */
    static u8 dist[MAX_DUNGEON_CELLS];
    static u8 queue[MAX_DUNGEON_CELLS];
    u8 size = run_state_dungeon_size();
    u8 boss = (u8)(size - 1);
    u8 head = 0, tail = 0, i, dir;
    u16 mix;
    u8 rot;

    if (size < 4) return 0;
    for (i = 0; i < MAX_DUNGEON_CELLS; ++i) dist[i] = 0xFF;
    dist[boss] = 0;
    queue[tail++] = boss;
    while (head < tail) {
        u8 cell = queue[head++];
        for (dir = DIR_N; dir <= DIR_W; ++dir) {
            u8 next = run_state_dungeon_cell_neighbor(cell, dir);
            if (next == 0xFF || dist[next] != 0xFF) continue;
            dist[next] = (u8)(dist[cell] + 1);
            queue[tail++] = next;
        }
    }

    mix = entry_mix();
    rot = (u8)(mix % 3);
    for (i = 0; i < 3; ++i) {
        u8 kind = (u8)((u8)(rot + i) % 3);
        u8 count = 0;
        u8 cell;
        for (cell = 0; cell < (u8)(size - 3); ++cell) {
            if (!entry_candidate_ok(cell, size, dist[cell])) continue;
            if (entry_grid_kind(cell, size) == kind) count++;
        }
        if (!count) continue;
        {
            u8 index = (u8)((mix >> 3) % count);
            u8 seen = 0;
            for (cell = 0; cell < (u8)(size - 3); ++cell) {
                if (!entry_candidate_ok(cell, size, dist[cell])) continue;
                if (entry_grid_kind(cell, size) != kind) continue;
                if (seen == index) return cell;
                seen++;
            }
        }
    }
    return 0;
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
