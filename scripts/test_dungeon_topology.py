#!/usr/bin/env python3
"""Pure contract for the 6x5 campaign maze and its procedural folds."""
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
    graph_signatures = set()
    for stage, size in enumerate(sizes):
        for seed in (0xCAFE1234, 0xCAFE1235, 0x51A6D00D, 0xDEADBEEF):
            seen = distances(size, seed, stage)
            assert len(seen) == size, (
                f"stage {stage + 1} seed {seed:08x} disconnected: "
                f"{sorted(set(range(size)) - seen.keys())}")
            # Every horizontal district remains readable, but crossings
            # between rows are seed-selected rather than the same snake turn.
            for cell in range(size - 1):
                if cell // GRID_W == (cell + 1) // GRID_W:
                    assert any(dungeon_maze_neighbor(
                        cell, size, direction, seed, stage) == cell + 1
                        for direction in range(4))
            assert dungeon_maze_neighbor(1, size, 2, seed, stage) == 10
            assert dungeon_maze_neighbor(10, size, 0, seed, stage) == 1
            route_lengths.append(seen[size - 1])
            # One connector joins every populated row band. The fixed 1<->10
            # seam is distinct from the first fold, so the graph has exactly
            # one large loop plus real arms/dead ends rather than either a
            # linear snake or a compact fully connected rectangle.
            seams_by_band = []
            edges = set()
            for cell in range(size):
                for direction in range(4):
                    neighbor = dungeon_maze_neighbor(
                        cell, size, direction, seed, stage)
                    if neighbor is not None:
                        edges.add(tuple(sorted((cell, neighbor))))
            for upper_row in range(GRID_H - 1):
                if (upper_row + 1) * GRID_W >= size:
                    break
                seams = [
                    edge for edge in edges
                    if edge[0] // GRID_W == upper_row
                    and edge[1] // GRID_W == upper_row + 1
                ]
                seams_by_band.append(len(seams))
            assert seams_by_band[0] == 2 and all(
                count == 1 for count in seams_by_band[1:]
            ), (stage + 1, f"{seed:08x}", seams_by_band)
            assert len(edges) == size, (
                f"stage {stage + 1} seed {seed:08x} should own one cycle, "
                f"got {len(edges)} edges/{size} cells")
            degrees = {
                cell: sum(cell in edge for edge in edges)
                for cell in range(size)
            }
            assert sum(degree == 1 for degree in degrees.values()) >= 2
            assert any(degree >= 3 for degree in degrees.values())
            graph_signatures.add(tuple(sorted(edges)))

            # The actual progression route visits the staged Sigil, Wardens,
            # and Waystone before the boss. Every approved fold occupies at
            # least all but one cell's worth of traversal, so making the
            # dungeon broader does not quietly make it shorter.
            goals = (2, 3, 7, 9, 15, size - 1)
            cursor = 0
            required = 0
            for goal in goals:
                required += distance(size, seed, stage, cursor, goal)
                cursor = goal
            required_lengths.append(required)
            assert required >= size - 1, (
                f"stage {stage + 1} seed {seed:08x} required route "
                f"collapsed to {required}/{size}")
    assert len(graph_signatures) >= 6, (
        f"safe folds produced only {len(graph_signatures)} graph variants")
    assert min(route_lengths) >= 7, (
        f"objective loop collapsed a boss route to {min(route_lengths)} rooms")
    print("[dungeon-topology] PASS 20→30 rooms, 219-screen campaign, "
          f"{len(graph_signatures)} seed/stage folds, one objective loop, "
          f"boss distance={min(route_lengths)}..{max(route_lengths)}, "
          f"required route={min(required_lengths)}..{max(required_lengths)}")


if __name__ == "__main__":
    main()
