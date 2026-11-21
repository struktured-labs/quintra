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
        (0, 5, 5, 0),
        (0, 0, 5, 0),
        (5, 5, 5, 0),
        (2, 5, 5, 0),
        (0, 5, 4, 0),
        (0, 4, 5, 0),
        (0, 1, 5, 0),
    )
    seed_fold = (run_seed ^ (run_seed >> 8) ^ (run_seed >> 16)
                 ^ (run_seed >> 24) ^ (stage * 3)) & 7
    lower_first = (upper_row + 1) * GRID_W
    lower_count = min(GRID_W, size - lower_first)
    if lower_count <= 0:
        return None
    service_first = size - 3
    if lower_first < service_first:
        lower_count = min(lower_count, service_first - lower_first)
    fold_col = folds[seed_fold][upper_row]
    if (upper_row + 1) & 1:
        fold_col = max(fold_col, GRID_W - lower_count)
    else:
        fold_col = min(fold_col, lower_count - 1)
    return neighbor if col == fold_col else None


ENTRY_MIN_BOSS_DIST = 7


def dungeon_entry_mix(run_seed: int, stage: int) -> int:
    """Mirror the cartridge's 16-bit start-cell mixer."""
    mix = (run_seed & 0xFF) | (((run_seed >> 8) & 0xFF) << 8)
    mix ^= ((run_seed >> 16) & 0xFF) | (((run_seed >> 24) & 0xFF) << 8)
    mix ^= (stage * 251)
    return mix & 0xFFFF


def dungeon_grid_kind(cell: int, size: int) -> int:
    """0=corner, 1=edge, 2=interior on the occupied 6x5 footprint."""
    col, row = dungeon_cell_xy(cell)
    degree = 0
    for ncol, nrow in ((col, row - 1), (col + 1, row),
                       (col, row + 1), (col - 1, row)):
        if not (0 <= ncol < GRID_W and 0 <= nrow < GRID_H):
            continue
        offset = (GRID_W - 1 - ncol) if nrow & 1 else ncol
        neighbor = nrow * GRID_W + offset
        if neighbor < size:
            degree += 1
    if degree <= 2:
        return 0
    if degree == 3:
        return 1
    return 2


def dungeon_distances_from(size: int, run_seed: int, stage: int,
                           start: int) -> dict[int, int]:
    from collections import deque
    queue = deque([start])
    result = {start: 0}
    while queue:
        cell = queue.popleft()
        for direction in range(4):
            neighbor = dungeon_maze_neighbor(
                cell, size, direction, run_seed, stage)
            if neighbor is not None and neighbor not in result:
                result[neighbor] = result[cell] + 1
                queue.append(neighbor)
    return result


def dungeon_entry_cell(size: int, run_seed: int, stage: int) -> int:
    """Mirror run_state_dungeon_entry_cell."""
    if size < 4:
        return 0
    dist = dungeon_distances_from(size, run_seed, stage, size - 1)
    mix = dungeon_entry_mix(run_seed, stage)
    rot = mix % 3
    for step in range(3):
        kind = (rot + step) % 3
        candidates = [
            cell for cell in range(size - 3)
            if dist.get(cell, 0xFF) >= ENTRY_MIN_BOSS_DIST
            and dist.get(cell, 0xFF) != 0xFF
            and dungeon_grid_kind(cell, size) == kind
            and cell not in (5, 11, 17, 23)
            and sum(
                dungeon_maze_neighbor(cell, size, direction, run_seed, stage)
                is not None for direction in range(4)
            ) <= 2
        ]
        if not candidates:
            continue
        return candidates[(mix >> 3) % len(candidates)]
    return 0


def dungeon_entry_room(stage: int, run_seed: int) -> int:
    """Return the global room counter of a stage's seeded entry room."""
    return STAGE_START[stage] + dungeon_entry_cell(
        dungeon_size(stage), run_seed, stage)


def dungeon_entry_prefix(size: int, run_seed: int, stage: int,
                         count: int) -> list[int]:
    """First ``count`` cells discovered from the seeded entry, including it."""
    if count <= 0:
        return []
    entry = dungeon_entry_cell(size, run_seed, stage)
    from collections import deque
    seen = {entry}
    queue = deque([entry])
    prefix = []
    while queue and len(prefix) < count:
        cell = queue.popleft()
        prefix.append(cell)
        for direction in range(4):
            neighbor = dungeon_maze_neighbor(
                cell, size, direction, run_seed, stage)
            if neighbor is None or neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    return prefix


def dungeon_entry_prefix_mask(size: int, run_seed: int, stage: int,
                              count: int) -> int:
    """Bit 0 of the low byte is cell 0, matching next_dungeon_reveal."""
    mask = 0
    for cell in dungeon_entry_prefix(size, run_seed, stage, count):
        mask |= 1 << cell
    return mask


def mission_graph(size: int, run_seed: int, stage: int) -> dict[str, int]:
    """Mirror the cartridge's pre-room seeded objective graph."""
    limit = size - 3
    mix = (run_seed ^ (run_seed >> 8) ^ (run_seed >> 16)
           ^ (run_seed >> 24)) & 0xFF
    mix = (mix + stage * 41) & 0xFF
    entry = dungeon_entry_cell(size, run_seed, stage)
    landmarks = {0, 2, 5, 8, 11, 15, 17, 23}
    cache_reserve = next((cell for cell in range(size - 4, 0, -1)
        if cell not in landmarks and sum(
            dungeon_maze_neighbor(cell, size, direction, run_seed, stage)
            is not None for direction in range(4)) == 1), None)
    reserved = set(landmarks)
    reserved.add(entry)
    if cache_reserve is not None:
        reserved.add(cache_reserve)
    queue = [entry]
    seen = {entry}
    eligible = []
    for cell in queue:
        if cell < limit and cell not in reserved:
            eligible.append(cell)
        turn = (mix + cell * 3) & 3
        for step in range(4):
            neighbor = dungeon_maze_neighbor(
                cell, size, (turn + step) & 3, run_seed, stage)
            if (neighbor is None or neighbor >= limit or neighbor in seen):
                continue
            seen.add(neighbor)
            queue.append(neighbor)
    if len(eligible) < 7:
        selected = [1, 3, 4, 6, 7, 9, 10]
    else:
        selected = [eligible[(i * (len(eligible) - 1) + 3) // 6]
                    for i in range(7)]
    graph = {
        "order": mix & 1,
        "trial": selected[0],
        "waystone": selected[3],
        "deep_warden": selected[4],
        "deep_switch": selected[5],
        "deep_gate": selected[6],
    }
    if graph["order"]:
        graph["warden"], graph["sigil"] = selected[1:3]
    else:
        graph["sigil"], graph["warden"] = selected[1:3]
    graph["sequence"] = tuple(selected)
    graph["discovery"] = tuple(eligible)
    return graph


def dungeon_cache_cell(size: int, run_seed: int, stage: int) -> int:
    """Mirror the cartridge's deepest optional dead-end cache selection."""
    graph = mission_graph(size, run_seed, stage)
    fixtures = {0, 2, 5, 8, 11, 15, 17, 23}
    fixtures.update(graph["sequence"])
    for cell in range(size - 4, 0, -1):
        if cell in fixtures:
            continue
        degree = sum(
            dungeon_maze_neighbor(cell, size, direction, run_seed, stage)
            is not None
            for direction in range(4)
        )
        if degree == 1:
            return cell
    return next(cell for cell in range(1, size - 3) if cell not in fixtures)


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


PUZZLE_PUSH_SEAL = 1
PUZZLE_RUNE_SEQUENCE = 2
PUZZLE_SUN_LATTICE = 5
PUZZLE_PRISM_TOGGLE = 6
_EARLY_POOL = (
    (PUZZLE_PUSH_SEAL, PUZZLE_RUNE_SEQUENCE, PUZZLE_PRISM_TOGGLE),
    (PUZZLE_RUNE_SEQUENCE, PUZZLE_PRISM_TOGGLE, PUZZLE_PUSH_SEAL),
)


def puzzle_slot_kind(run_seed: int, stage: int, slot: int) -> int:
    """Mirror puzzle_slot_kind() in src/game/puzzle.c (slot 0 Trial, 1 Waystone)."""
    mix = (run_seed ^ (run_seed >> 8) ^ (run_seed >> 16) ^ (run_seed >> 24)) & 0xFF
    mix = (mix + stage * 51) & 0xFF
    if stage < 2:
        first = mix % 3
        if slot:
            first = (first + 1 + ((mix >> 2) & 1)) % 3
        return _EARLY_POOL[stage][first]
    if slot and stage <= 5 and (mix >> 3) & 1:
        return PUZZLE_PRISM_TOGGLE
    return PUZZLE_SUN_LATTICE


def room_seed(run_seed: int, biome: int, room_counter: int) -> int:
    """Mirror procgen_room_seed()."""
    return (run_seed ^ (biome << 16) ^ ((room_counter * 0x9E3779B9) & 0xFFFFFFFF)) & 0xFFFFFFFF


_VEIL_GOLDEN = (0x00000000, 0x9E3779B9, 0x3C6EF372, 0xDAA66D2B, 0x78DDE6E4,
                0x1715609D, 0xB54CDA56, 0x5384540F, 0xF1BBCDC8)


def veil_host_cell(run_seed: int, stage: int) -> int | None:
    """Mirror secret_merchant_host_cell: the stage's hidden Veil vault host."""
    size = dungeon_size(stage)
    entry = dungeon_entry_cell(size, run_seed, stage)
    cache = dungeon_cache_cell(size, run_seed, stage)
    roles = set(mission_graph(size, run_seed, stage)["sequence"])
    h = (run_seed ^ _VEIL_GOLDEN[stage] ^ 0x5645494C) & 0xFFFFFFFF or 0x2545F491
    h ^= (h << 13) & 0xFFFFFFFF
    h ^= h >> 17
    h ^= (h << 5) & 0xFFFFFFFF
    start = ((h >> 8) & 0xFF) % size
    for dead_end_only in (True, False):
        for i in range(size):
            cell = (start + i) % size
            if (cell in (0, entry, cache) or cell + 3 >= size
                    or cell in (2, 5, 8, 11, 15, 17, 23) or cell in roles):
                continue
            degree = sum(dungeon_maze_neighbor(cell, size, d, run_seed, stage)
                         is not None for d in range(4))
            if dead_end_only and degree != 1:
                continue
            return cell
    return None


RIME_STAGE = 1
RW_STAGE = 2   # M2 Cairn Ford shares the pocket-cell rule
KT_STAGE = 3   # M3 Kite Kennel too
LK_STAGE = 4   # M4 Lockmire Ferry too
CD_STAGE = 5   # M5a Ember Conduit too
_RIME_LANDMARKS = (0, 2, 5, 8, 11, 15, 17, 23)


def rime_cell_candidates(run_seed: int, stage: int) -> list[int]:
    """Mirror rime_pick_cell (M1 Rime chamber) in scan order.

    The cartridge takes the first candidate; if an ambient Dungeon Law
    altar owns it the floor has no chamber at all (altars are not mirrored
    here, so treat the first candidate as reserved either way).
    """
    if stage not in (RIME_STAGE, RW_STAGE, KT_STAGE, LK_STAGE, CD_STAGE):
        return []
    size = dungeon_size(stage)
    entry = dungeon_entry_cell(size, run_seed, stage)
    cache = dungeon_cache_cell(size, run_seed, stage)
    host = veil_host_cell(run_seed, stage)
    roles = set(mission_graph(size, run_seed, stage)["sequence"])
    out = []
    for cell in range(size - 4, 0, -1):
        if (cell in (entry, cache, host) or cell in _RIME_LANDMARKS
                or cell % 6 == 0 or cell in roles):
            continue
        out.append(cell)
    return out


def rime_reserved_cells(run_seed: int, stage: int) -> set[int]:
    """The cell that may host the Rime chamber (first candidate)."""
    return set(rime_cell_candidates(run_seed, stage)[:1])
