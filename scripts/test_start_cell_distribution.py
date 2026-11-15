#!/usr/bin/env python3
"""Headless contract: dungeon entry cells vary by seed, not only the upper left."""
from collections import Counter, defaultdict

from quintra_topology import (
    ENTRY_MIN_BOSS_DIST, dungeon_cell_xy, dungeon_distances_from,
    dungeon_entry_cell, dungeon_grid_kind, dungeon_size,
)

SEEDS = tuple((0xB5297A4D * index + 0xF07E0011) & 0xFFFFFFFF
              for index in range(50))
KIND_NAME = ("corner", "edge", "interior")


def main() -> None:
    kinds = defaultdict(Counter)
    cells = defaultdict(Counter)
    positions = defaultdict(Counter)
    max_share = 0.0
    for stage in range(9):
        size = dungeon_size(stage)
        for seed in SEEDS:
            first = dungeon_entry_cell(size, seed, stage)
            again = dungeon_entry_cell(size, seed, stage)
            assert first == again, (
                f"stage {stage + 1} seed {seed:#x} was not deterministic")
            assert 0 <= first < size - 3, (
                f"stage {stage + 1} seed {seed:#x} started in service "
                f"room {first}/{size}")
            dist = dungeon_distances_from(size, seed, stage, first)
            boss = size - 1
            assert boss in dist, (
                f"stage {stage + 1} seed {seed:#x} entry {first} "
                f"cannot reach the boss")
            assert dist[boss] >= ENTRY_MIN_BOSS_DIST, (
                f"stage {stage + 1} seed {seed:#x} entry {first} is only "
                f"{dist[boss]} rooms from the boss")
            kinds[stage][KIND_NAME[dungeon_grid_kind(first, size)]] += 1
            cells[stage][first] += 1
            positions[stage][dungeon_cell_xy(first)] += 1
        unique = len(positions[stage])
        assert unique >= 8, (
            f"stage {stage + 1} only used {unique} start cells "
            f"across {len(SEEDS)} seeds: {sorted(positions[stage])}")
        assert (0, 0) in positions[stage], (
            f"stage {stage + 1} never used the familiar upper-left start")
        assert any(x > 0 or y > 0 for x, y in positions[stage]), (
            f"stage {stage + 1} stayed in the upper-left corner")
        xs = {x for x, _y in positions[stage]}
        ys = {y for _x, y in positions[stage]}
        assert min(xs) == 0 and max(xs) >= 4, (
            f"stage {stage + 1} start columns collapsed to {sorted(xs)}")
        assert 0 in ys and max(ys) >= 1, (
            f"stage {stage + 1} start rows collapsed to {sorted(ys)}")
        for kind in KIND_NAME:
            assert kinds[stage][kind] >= 5, (
                f"stage {stage + 1} under-used {kind} starts: "
                f"{dict(kinds[stage])}")
        share = cells[stage][0] / len(SEEDS)
        max_share = max(max_share, share)
        assert share <= 0.45, (
            f"stage {stage + 1} still starts at cell 0 in {share:.0%} of seeds")

    print(
        "[start-cell-distribution] PASS 50 seeds x 9 stages, "
        f"kinds={[dict(kinds[s]) for s in range(9)]}, "
        f"unique={[len(positions[s]) for s in range(9)]}, "
        f"max_cell0_share={max_share:.2f}"
    )


if __name__ == "__main__":
    main()
