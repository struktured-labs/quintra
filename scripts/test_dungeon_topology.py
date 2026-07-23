#!/usr/bin/env python3
"""Pure contract for the 6x5 campaign maze and its procedural loops."""
from collections import deque

from quintra_topology import (
    GRID_H, GRID_W, STAGE_BOSS_ROOM, STAGE_START, VILLAGE_ROOM,
    dungeon_maze_neighbor, dungeon_size,
)


def distances(size: int, seed: int, stage: int) -> dict[int, int]:
    queue = deque([0])
    result = {0: 0}
    while queue:
        cell = queue.popleft()
        for direction in range(4):
            neighbor = dungeon_maze_neighbor(
                cell, size, direction, seed, stage)
            if neighbor is not None and neighbor not in result:
                result[neighbor] = result[cell] + 1
                queue.append(neighbor)
    return result


def main() -> None:
    sizes = tuple(dungeon_size(stage) for stage in range(9))
    assert (GRID_W, GRID_H) == (6, 5)
    assert sizes == (20, 21, 22, 23, 24, 25, 26, 28, 30)
    assert sum(sizes) == 219 and max(sizes) == GRID_W * GRID_H
    assert VILLAGE_ROOM == {3: 63, 6: 136}
    assert all(STAGE_START[i] <= STAGE_BOSS_ROOM[i] < 256
               for i in range(9))

    route_lengths = []
    loop_signatures = set()
    for stage, size in enumerate(sizes):
        for seed in (0xCAFE1234, 0xCAFE1235, 0x51A6D00D, 0xDEADBEEF):
            seen = distances(size, seed, stage)
            assert len(seen) == size, (
                f"stage {stage + 1} seed {seed:08x} disconnected: "
                f"{sorted(set(range(size)) - seen.keys())}")
            # Consecutive cells are the guaranteed winding spine.
            assert all(any(dungeon_maze_neighbor(
                    cell, size, direction, seed, stage) == cell + 1
                    for direction in range(4))
                for cell in range(size - 1))
            route_lengths.append(seen[size - 1])
            loop_signatures.add(tuple(
                dungeon_maze_neighbor(cell, size, 2, seed, stage)
                for cell in range(size)))

    assert len(loop_signatures) >= 8, "maze seams do not vary across runs/stages"
    assert min(route_lengths) >= 7, (
        f"procedural seams collapsed a boss route to {min(route_lengths)} rooms")
    print("[dungeon-topology] PASS 20→30 rooms, 219-screen campaign, "
          f"seeded loop variants={len(loop_signatures)}, "
          f"boss distance={min(route_lengths)}..{max(route_lengths)}")


if __name__ == "__main__":
    main()
