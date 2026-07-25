"""Shared developer-side mirror of Quintra's cartridge campaign topology."""

GRID_W, GRID_H = 6, 5
STAGE_START = (0, 20, 41, 64, 87, 111, 137, 163, 191)
STAGE_BOSS_ROOM = (19, 40, 62, 86, 110, 135, 162, 190, 220)
VILLAGE_ROOM = {3: 63, 6: 136}


def dungeon_size(stage: int) -> int:
    return STAGE_BOSS_ROOM[stage] - STAGE_START[stage] + 1


def dungeon_local(room: int, stage: int) -> int:
    return max(0, min(room - STAGE_START[stage], dungeon_size(stage) - 1))


def dungeon_cell_xy(cell: int) -> tuple[int, int]:
    """Return the displayed 6x5 snake coordinate for one local room cell."""
    row, offset = divmod(cell, GRID_W)
    return ((GRID_W - 1 - offset) if row & 1 else offset), row


def dungeon_neighbor(cell: int, size: int, direction: int) -> int | None:
    """Mirror run_state_dungeon_neighbor for DIR_N/E/S/W = 0/1/2/3."""
    col, row = dungeon_cell_xy(cell)
    if direction == 0:
        row -= 1
    elif direction == 1:
        col += 1
    elif direction == 2:
        row += 1
    elif direction == 3:
        col -= 1
    if not (0 <= col < GRID_W and 0 <= row < GRID_H):
        return None
    offset = (GRID_W - 1 - col) if row & 1 else col
    neighbor = row * GRID_W + offset
    return neighbor if neighbor < size else None


def dungeon_maze_neighbor(cell: int, size: int, direction: int,
                          run_seed: int, stage: int) -> int | None:
    """Mirror the cartridge's seed-selected safe fold and objective loop."""
    col, row = dungeon_cell_xy(cell)
    upper_row = row - 1 if direction == 0 else row
    neighbor = dungeon_neighbor(cell, size, direction)
    if neighbor is None or direction not in (0, 2):
        return neighbor
    if upper_row == 0 and col == 1:
        return neighbor
    folds = (
        (2, 0, 5, 0),
        (0, 4, 5, 0),
        (0, 5, 5, 0),
        (0, 0, 5, 0),
        (0, 1, 5, 0),
        (5, 0, 5, 0),
        (2, 5, 5, 0),
        (5, 5, 5, 0),
    )
    seed_fold = (run_seed ^ (run_seed >> 8) ^ (run_seed >> 16)
                 ^ (run_seed >> 24) ^ (stage * 3)) & 7
    lower_first = (upper_row + 1) * GRID_W
    lower_count = min(GRID_W, size - lower_first)
    if lower_count <= 0:
        return None
    fold_col = folds[seed_fold][upper_row]
    if (upper_row + 1) & 1:
        fold_col = max(fold_col, GRID_W - lower_count)
    else:
        fold_col = min(fold_col, lower_count - 1)
    return neighbor if col == fold_col else None


def dungeon_direction(source: int, target: int) -> int:
    sx, sy = dungeon_cell_xy(source)
    tx, ty = dungeon_cell_xy(target)
    return {
        (0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3,
    }[(tx - sx, ty - sy)]


def dungeon_predecessor(target: int, size: int, run_seed: int,
                        stage: int) -> tuple[int, int]:
    """Return one real source cell and direction leading into ``target``."""
    sources = list(range(size))
    # Preserve the familiar numeric predecessor when that edge exists, then
    # fall back to the closest real arm in the generated fold.
    sources.sort(key=lambda source: (
        source != target - 1, abs(source - target), source))
    for source in sources:
        for direction in range(4):
            if dungeon_maze_neighbor(
                    source, size, direction, run_seed, stage) == target:
                return source, direction
    raise ValueError(f"no graph approach to stage {stage + 1} cell {target}")
