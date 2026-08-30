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
