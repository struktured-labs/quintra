"""Shared developer-side mirror of Quintra's cartridge campaign topology."""

GRID_W, GRID_H = 5, 4
STAGE_START = (0, 14, 29, 46, 62, 79, 98, 116, 135)
STAGE_BOSS_ROOM = (13, 28, 44, 61, 78, 96, 115, 134, 154)
VILLAGE_ROOM = {3: 45, 6: 97}


def dungeon_size(stage: int) -> int:
    return STAGE_BOSS_ROOM[stage] - STAGE_START[stage] + 1


def dungeon_local(room: int, stage: int) -> int:
    return max(0, min(room - STAGE_START[stage], dungeon_size(stage) - 1))


def dungeon_cell_xy(cell: int) -> tuple[int, int]:
    """Return the displayed 5x4 snake coordinate for one local room cell."""
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


def dungeon_direction(source: int, target: int) -> int:
    sx, sy = dungeon_cell_xy(source)
    tx, ty = dungeon_cell_xy(target)
    return {
        (0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3,
    }[(tx - sx, ty - sy)]
