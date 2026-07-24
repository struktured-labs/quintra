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


def distance(size: int, seed: int, stage: int, start: int, goal: int) -> int:
    queue = deque([start])
    result = {start: 0}
    while queue:
        cell = queue.popleft()
        if cell == goal:
            return result[cell]
        for direction in range(4):
            neighbor = dungeon_maze_neighbor(
                cell, size, direction, seed, stage)
            if neighbor is not None and neighbor not in result:
                result[neighbor] = result[cell] + 1
                queue.append(neighbor)
    raise AssertionError(f"no route {start}->{goal}")


def main() -> None:
    sizes = tuple(dungeon_size(stage) for stage in range(9))
    assert (GRID_W, GRID_H) == (6, 5)
    assert sizes == (20, 21, 22, 23, 24, 25, 26, 28, 30)
    assert sum(sizes) == 219 and max(sizes) == GRID_W * GRID_H
    assert VILLAGE_ROOM == {3: 63, 6: 136}
    assert all(STAGE_START[i] <= STAGE_BOSS_ROOM[i] < 256
               for i in range(9))

    route_lengths = []
    required_lengths = []
    for stage, size in enumerate(sizes):
        for seed in (0xCAFE1234, 0xCAFE1235, 0x51A6D00D, 0xDEADBEEF):
            seen = distances(size, seed, stage)
            assert len(seen) == size, (
                f"stage {stage + 1} seed {seed:08x} disconnected: "
                f"{sorted(set(range(size)) - seen.keys())}")
            # Consecutive cells remain the guaranteed winding spine.
            assert all(any(dungeon_maze_neighbor(
                    cell, size, direction, seed, stage) == cell + 1
                    for direction in range(4))
                for cell in range(size - 1))
            assert dungeon_maze_neighbor(1, size, 2, seed, stage) == 10
            assert dungeon_maze_neighbor(10, size, 0, seed, stage) == 1
            route_lengths.append(seen[size - 1])
            # The fixed 1<->10 seam creates one large objective wing. Keeping
            # every other non-turn seam closed prevents the 6x5 field from
            # collapsing back into a compact Manhattan grid.
            extra_seams = 0
            for cell in range(size):
                col, row = divmod(cell, GRID_W)[1], cell // GRID_W
                if row & 1:
                    col = GRID_W - 1 - col
                neighbor = dungeon_maze_neighbor(
                    cell, size, 2, seed, stage)
                turn_col = GRID_W - 1 if row % 2 == 0 else 0
                if neighbor is not None and col != turn_col:
                    extra_seams += 1
            assert extra_seams == 1, (
                f"stage {stage + 1} seed {seed:08x} has "
                f"{extra_seams} extra vertical seams")

            # The actual progression route visits the staged Sigil, Wardens,
            # and Waystone before the boss. It must occupy almost the full
            # room budget rather than letting cardinal shortcuts turn a
            # 30-room dungeon into a fifteen-room playthrough.
            goals = (2, 3, 7, 9, 15, size - 1)
            cursor = 0
            required = 0
            for goal in goals:
                required += distance(size, seed, stage, cursor, goal)
                cursor = goal
            required_lengths.append(required)
            assert required >= size - 5, (
                f"stage {stage + 1} seed {seed:08x} required route "
                f"collapsed to {required}/{size}")
    assert min(route_lengths) >= 11, (
        f"objective junction collapsed a boss route to {min(route_lengths)} rooms")
    print("[dungeon-topology] PASS 20→30 rooms, 219-screen campaign, "
          "fixed objective wing, "
          f"boss distance={min(route_lengths)}..{max(route_lengths)}, "
          f"required route={min(required_lengths)}..{max(required_lengths)}")


if __name__ == "__main__":
    main()
