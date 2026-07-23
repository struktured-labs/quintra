"""Shared developer-side mirror of Quintra's cartridge campaign topology."""

STAGE_START = (0, 10, 21, 34, 46, 59, 74, 88, 103)
STAGE_BOSS_ROOM = (9, 20, 32, 45, 58, 72, 87, 102, 118)
VILLAGE_ROOM = {3: 33, 6: 73}


def dungeon_size(stage: int) -> int:
    return STAGE_BOSS_ROOM[stage] - STAGE_START[stage] + 1


def dungeon_local(room: int, stage: int) -> int:
    return max(0, min(room - STAGE_START[stage], dungeon_size(stage) - 1))


def dungeon_cell_xy(cell: int) -> tuple[int, int]:
    """Return the displayed 4x4 snake coordinate for one local room cell."""
    row, offset = divmod(cell, 4)
    return ((3 - offset) if row & 1 else offset), row


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
    if not (0 <= col < 4 and 0 <= row < 4):
        return None
    offset = (3 - col) if row & 1 else col
    neighbor = row * 4 + offset
    return neighbor if neighbor < size else None


def dungeon_direction(source: int, target: int) -> int:
    sx, sy = dungeon_cell_xy(source)
    tx, ty = dungeon_cell_xy(target)
    return {
        (0, -1): 0, (1, 0): 1, (0, 1): 2, (-1, 0): 3,
    }[(tx - sx, ty - sy)]
